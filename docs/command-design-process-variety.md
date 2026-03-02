# count-process-variety 设计文档

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
