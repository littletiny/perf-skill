# count-process-variety 设计文档

## 工具现状

### 功能定位

`count-process-variety` 是一个进程风暴检测工具，用于识别短时间内大量创建短生命周期进程的场景。该工具通过统计每个进程名（comm）对应的唯一 PID 数量及其生命周期特征，判断是否存在异常的大量进程创建行为。

### 命令行接口

**基本用法**
```bash
spear count-process-variety --data <perf.data>
```

**支持参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--data` | string | 必填 | perf script 输出文件路径 |
| `--freq` | int | 19 | 采样频率（Hz），仅对原始 perf 格式有效 |
| `--top-n`, `--limit` | int | 20 | 显示前 N 个进程名 |
| `--storm-pid-threshold` | int | 50 | PID 数量阈值，超过此值考虑为风暴 |
| `--storm-ratio-threshold` | float | 2.0 | samples/PID 阈值，低于此值说明进程生命周期短 |
| `--cpu-id` | int | - | 按 CPU ID 过滤 |
| `--comm` | string | - | 按进程名过滤，支持逗号分隔多个值 |
| `--comm-regex` | string | - | 按进程名正则表达式过滤 |
| `--start-time` | string | - | 起始时间过滤（支持 Unix 时间戳、ISO 8601、datetime 等格式） |
| `--end-time` | string | - | 结束时间过滤 |

### 核心功能

**1. 进程多样性统计**
- 按进程名（comm）聚合，统计每个 comm 对应的唯一 PID 数量
- 记录每个 PID 出现的秒级时间戳集合，用于判断生命周期
- 计算总 CPU 权重（通过 engine 统一接口）

**2. 进程风暴检测**
- 基础阈值：PID 数量 ≥ 10（避免偶发情况误判）
- 短生命周期判定：50% 以上 PID 仅出现在单秒时间内
- 风暴判定条件：
  - `samples_per_pid <= 2.0`（每个 PID 平均采样数极少）
  - 或 `cpu_per_pid <= 0.5 core/s`（每个 PID CPU 消耗极低）

**3. 输出指标**
- `pids_per_min`: 每分钟创建的进程数（去重后），使用速率消除采样时长差异
- `cpu_util`: 该进程名的总 CPU 利用率
- `behavior`: 行为模式（`process_storm` 或 `normal`）

### 输出格式

**正常输出（无风暴）**
```json
{
  "_risk": {"level": "none"},
  "process_variety": [],
  "summary": {
    "total_processes": 0,
    "storm_detected": false,
    "storm_count": 0
  }
}
```

**检测到进程风暴**
```json
{
  "_risk": {
    "level": "critical",
    "message": "检测到 3 个进程风暴（短生命周期进程）",
    "hint": "必须对每个进程运行: cluster-symbols --comm netstat; cluster-symbols --comm python3; cluster-symbols --comm sh",
    "patterns": ["PROCESS_STORM"],
    "pending_targets": ["netstat", "python3", "sh"]
  },
  "process_variety": [
    {"comm": "netstat", "pids_per_min": 2633, "cpu_util": "243.87%", "behavior": "process_storm"},
    {"comm": "python3", "pids_per_min": 829, "cpu_util": "207.17%", "behavior": "process_storm"},
    {"comm": "sh", "pids_per_min": 409, "cpu_util": "35.91%", "behavior": "process_storm"}
  ],
  "summary": {
    "total_processes": 3,
    "storm_detected": true,
    "storm_count": 3
  }
}
```

### 适用场景

- **fork 炸弹检测**：识别异常的大量 fork 行为
- **连接风暴**：如每连接创建一个 netstat 进程的反模式
- **worker 进程频繁创建销毁**：不合理的进程池管理
- **脚本循环中反复启动子进程**：shell 脚本中的低效实现

### 关联命令

- `cluster-symbols --comm <name>`: 对进程名进行详细分析，查看调用栈分布
- `get-comm-top`: 查看进程组 CPU 排行
- `get-process-top`: 查看单个进程 CPU 排行

## 概述

`count-process-variety` 用于检测进程风暴（Process Storm），即短时间内大量创建短生命周期进程的场景。

## 检测算法

### 核心逻辑

```python
# 1. 聚合 comm-pid 统计
for sample in samples:
    comm_pid_stats[comm][pid]['weight'] += weight
    comm_pid_stats[comm][pid]['seconds'].add(int(timestamp))

# 2. 计算指标
pid_count = len(pid_dict)  # 去重后的唯一 PID 数
samples_per_pid = total_samples / pid_count
short_lived_ratio = single_second_pids / pid_count

# 3. 风暴判定
if pid_count >= 10:
    if samples_per_pid <= STORM_RATIO_THRESHOLD and short_lived_ratio > 0.5:
        behavior = "process_storm"
    elif cpu_per_pid <= STORM_CPU_THRESHOLD and short_lived_ratio > 0.5:
        behavior = "process_storm"
```

### 阈值参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `storm_pid_threshold` | 50 | PID 数量阈值，超过此值考虑为风暴 |
| `storm_ratio_threshold` | 2.0 | samples/PID 阈值，低于此值说明进程生命周期短 |
| `storm_cpu_threshold` | 0.5 | 每 PID CPU 阈值（core/s），低于此值说明进程消耗少、生命周期短 |

### 检测模式

| 模式 | 条件 | 含义 |
|------|------|------|
| `PROCESS_STORM` | PID≥10 ∧ (samples_per_pid≤2.0 ∨ cpu_per_pid≤0.5) ∧ short_lived_ratio>0.5 | 大量短生命周期进程 |
| `normal` | 不满足风暴条件 | 正常进程行为 |

**说明：**
- `short_lived_ratio` = 仅出现 1 秒的 PID 数 / 总 PID 数
- 要求 `pid_count >= 10` 才考虑风暴（避免偶发情况）

## 字段计算

### pids_per_min

```python
duration_minutes = duration / 60
pids_per_min = int(pid_count / duration_minutes) if duration_minutes > 0 else 0
```

**设计理由：**
- 使用速率而非累积值，消除采样时长差异带来的误导
- 例如：60 秒内 120 个进程 → `120/min`，600 秒内 120 个进程 → `12/min`
- 使用 `int()` 取整，简化阅读

### cpu_util

```python
cpu_util = (total_comm_weight / duration * 100) if duration > 0 else 0
```

该进程名的总 CPU 利用率（所有 PID 聚合）。

## 输出格式

```
# PROCESS_STORM: comm,pids_per_min,cpu_util
netstat 2633 243.87%
python3 829 207.17%
sh 409 35.91%
```

**字段说明：**
- `comm`: 进程名
- `pids_per_min`: 每分钟创建的进程数（去重后）
- `cpu_util`: 总 CPU 利用率

## 适用场景

- fork 炸弹检测
- 连接风暴（如每连接一个 netstat 进程）
- worker 进程频繁创建销毁
- 脚本循环中反复启动子进程

## 关联命令

- `cluster-symbols --comm <name>`: 对进程名进行详细分析
- `get-comm-top`: 查看进程组 CPU 排行
