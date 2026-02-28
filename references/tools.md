# Perf Expert 工具参考

基于 SPEAR 方法论的 Linux 性能诊断工具集，分析 `perf script` 采样数据。

---

## 内核函数名规范化

工具自动处理内核函数名，合并编译器优化产生的变体：

| 原始函数名 | 规范化后 | 说明 |
|-----------|---------|------|
| `func_[k]` | `func` | 内核标记后缀 |
| `func.isra.7_[k]` | `func` | GCC `.isra.N` 优化 + 内核标记 |
| `func.part.3_[k]` | `func` | GCC `.part.N` 部分内联 + 内核标记 |
| `func.constprop.5` | `func` | GCC `.constprop.N` 常量传播 |

**说明**：`.isra`、`.part`、`.constprop` 是 GCC/Clang 编译器自动添加的优化标记，工具会自动合并这些变体。

---

## CPU 利用率计算

工具使用 perf 提供的 `core/s` 值计算 CPU 利用率：

```
CPU利用率(%) = (total_core_seconds / duration) × 100
```

- `core/s`：perf script 中的 core/s 值，表示该调用链每秒消耗的 CPU 核秒数
- `total_core_seconds`：所有样本的 core/s 值之和
- `duration`：采样持续时间（秒）

**core/s 值说明**：
- 表示采样时刻的 CPU 核心秒数/秒（即利用率比例）
- 例如 `0.0526 core/s` = 5.26% 的单核利用率
- 累加所有样本的 core/s 值，除以 duration，得到平均 CPU 利用率

**可靠性指标中的字段**：
```json
{
  "cpu_utilization_pct": 6276.51,    // CPU 利用率（多核可超过 100%）
  "utilization_source": "core/s",     // 计算来源：core/s
  "total_core_seconds": 406.66,      // 所有样本的 core/s 累加
  "avg_core_per_sec": 62.77          // 平均每秒 core/s 值
}
```

---

## 数据可靠性评估

工具基于 **CPU 利用率** 和 **样本数** 综合评估数据可靠性，**不再依赖 `--freq` 参数**。

### 评估标准

| 等级 | 条件 | 误差范围 | 建议 |
|-----|------|---------|------|
| **CRITICAL** | CPU<3% 或 样本<10 | 不可信 | 延长采样时间后重新采集 |
| **WARNING** | CPU<10% 且 样本<30 | > ±25% | 关注趋势而非精确值 |
| **ACCEPTABLE** | CPU 10-30% 且 样本<100 | ±10-15% | 可用于粗略趋势分析 |
| **GOOD** | CPU 30-60% 且 样本≥100 | ±5-10% | 结论可信 |
| **EXCELLENT** | CPU≥60% 且 样本≥200 | < ±3% | 统计结论高度可信 |

### 可靠性输出示例
```json
{
  "reliability": {
    "level": "EXCELLENT",
    "warning": "CPU利用率很高 (6276.5%)，样本数优秀 (6479)。统计结论高度可信，百分比误差 < ±3%。",
    "metrics": {
      "sample_count": 6479,
      "samples_per_sec": 1000.0,
      "cpu_utilization_pct": 6276.51,
      "utilization_source": "core/s",
      "duration_sec": 6.48,
      "total_core_seconds": 406.6554,
      "avg_core_per_sec": 62.7651
    }
  }
}
```

**注意**：
- 多核系统上 CPU 利用率可能超过 100%（如 64 核系统最高 6400%）
- 可靠性评估直接基于实际 CPU 利用率，无需指定采样频率

---

## 子功能清单

| 命令 | 类别 | 用途 |
|------|------|------|
| `check-cpu-bottleneck` | 资源边界 | 检测 Cgroup 限流、单核饱和 |
| `show-cpu-usage` | 资源消耗 | 系统/进程 CPU 利用率（user/kernel） |
| `analyze-core-distribution` | 资源消耗 | 分析各核心负载分布和线程状态 |
| `get-process-top` | 资源消耗 | TopN 进程 CPU 排名 |
| `cluster-comm` | 资源消耗 | 按进程名聚类分析 |
| `count-process-variety` | 行为分析 | 检测短生命周期进程风暴 |
| `get-hotspots` | 热点识别 | 热点函数排名（self/inclusive） |
| `cluster-symbols` | 热点识别 | 按专家规则聚类（调度/锁/内存/IRQ） |
| `cluster-paths` | 路径分析 | 调用路径聚类（Trie） |
| `find-callers` | 路径分析 | 热点函数调用溯源 |
| `detect-anomalies` | 时序分析 | CPU 利用率异常检测 |
| `generate-flamegraph` | 可视化 | FlameGraph 格式导出 |
| `generate-callgraph` | 可视化 | 调用图（DOT/JSON） |

---

## 使用模式

```bash
# 模式 1: 探索式诊断（未知问题）
check-cpu-bottleneck → cluster-paths → find-callers --auto-target

# 模式 2: 定向分析（已知热点）
get-hotspots → find-callers --target <func>

# 模式 3: 异常调查（有时序线索）
detect-anomalies → cluster-paths --start-time <t1> --end-time <t2>

# 模式 4: 负载不均衡分析（新增）
check-cpu-bottleneck → analyze-core-distribution → find-callers --target <调度函数>
```

---

## 命令详情

### 1. 资源边界

**check-cpu-bottleneck**

```bash
python3 scripts/perf_expert.py check-cpu-bottleneck \
  --data <perf.script.txt> \
  [--cpu-limit <cores>] \
  [--pid <PID>] \
  [--comm <name>]
```

输出判定: `CPU_LIMIT_SATURATION` | `SINGLE_CORE_SATURATION` | `HEALTHY`

---

### 2. 资源消耗

**show-cpu-usage**

```bash
python3 scripts/perf_expert.py show-cpu-usage \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--cpu-id <ID>]
```

**analyze-core-distribution** (新增)

分析进程在各 CPU 核心的负载分布，识别负载不均衡和线程休眠模式。

```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--cpu-id <ID>]
```

输出关键字段:
- `total_cores_with_activity`: 活跃核心数
- `imbalance_level`: 不均衡级别 (LOW/MEDIUM/HIGH/CRITICAL)
- `imbalance_description`: 不均衡描述
- `cores`: 各核心详细数据 (utilization_pct, states: sleeping/active)
- `patterns`: 检测到的模式 (SINGLE_CORE_SATURATION, MAJORITY_SLEEPING 等)

典型用途:
- 区分"锁竞争"vs"主动休眠"导致的单核瓶颈
- 识别线程是否在主动休眠 (nanosleep/epoll_wait)
- 评估负载均衡度

**get-process-top**

```bash
python3 scripts/perf_expert.py get-process-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>]
```

**cluster-comm**

```bash
python3 scripts/perf_expert.py cluster-comm \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>]
```

**count-process-variety**

```bash
python3 scripts/perf_expert.py count-process-variety \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--storm-pid-threshold <N>] \
  [--storm-ratio-threshold <ratio>] \
  [--cpu-id <ID>]
```

参数:
- `--storm-pid-threshold`: 进程风暴检测的 PID 数量阈值（默认 50）
- `--storm-ratio-threshold`: 进程风暴检测的样本/PID 比值阈值（默认 2.0）

行为模式检测:
- `PROCESS_STORM`: PID 数量 ≥ 阈值 且 样本/PID ≤ 阈值，表示短生命周期进程风暴
- `SHORT_LIVED_HEAVY`: 单样本进程占比 > 80% 且 PID 数量 > 20
- `LONG_RUNNING`: 单进程长期运行

---

### 3. 热点识别

**get-hotspots**

```bash
python3 scripts/perf_expert.py get-hotspots \
  --data <perf.script.txt> \
  [--sort-by inclusive|self] \
  [--top-n <N>] \
  [--pid <PID>] \
  [--comm <name>]
```

**cluster-symbols**

```bash
python3 scripts/perf_expert.py cluster-symbols \
  --data <perf.script.txt> \
  [--no-include-experts] \
  [--custom-rules <json>] \
  [--pid <PID>]
```

内置规则分类:
- `EVENT_IRQ_OFF`: IRQ off, spin_unlock 等长临界区
- `EVENT_SCHEDULER`: 调度器活动
- `EVENT_MEM_RECLAIM`: 内存回收、TLB 操作
- `EVENT_LOCK_CONTENTION`: 锁竞争
- `EVENT_SYNC_PRIMITIVE`: pthread 同步

**自定义规则** (`--custom-rules`):

支持两种格式:

1. **字符串格式** (正则表达式):
```bash
--custom-rules '{"MY_SCHEDULING": "schedule|nanosleep|epoll_wait"}'
```

2. **列表格式** (自动转换):
```bash
--custom-rules '{"MY_SCHEDULING": ["schedule", "nanosleep", "epoll_wait"]}'
```

---

### 4. 路径分析

**cluster-paths**

```bash
python3 scripts/perf_expert.py cluster-paths \
  --data <perf.script.txt> \
  [--min-depth <N>] \
  [--min-samples <N>] \
  [--top-n <N>]
```

参数:
- `--min-depth`: 最小公共前缀深度（默认 2）
- `--min-samples`: 形成 cluster 的最小样本数（默认 5）

**find-callers**

```bash
# 指定 target 模式
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --target <function> \
  [--min-ratio <pct>]

# 自动模式
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --auto-target \
  [--auto-target-top-n <N>]
```

---

### 5. 时序分析

**detect-anomalies**

```bash
python3 scripts/perf_expert.py detect-anomalies \
  --data <perf.script.txt> \
  [--window-size <sec>] \
  [--spike-threshold <ratio>] \
  [--cpu-id <ID>]
```

参数:
- `--window-size`: 分析窗口（默认 0.5s）
- `--spike-threshold`: 变化率阈值（默认 0.5）
- `--export-mode`: 导出原始窗口数据

检测类型: `SPIKE` | `DROP` | `LEVEL_SHIFT` | `BURST`

---

### 6. 可视化

**generate-flamegraph**

```bash
python3 scripts/perf_expert.py generate-flamegraph \
  --data <perf.script.txt> \
  [--format folded|json] \
  [--pid <PID>]
```

**generate-callgraph**

```bash
python3 scripts/perf_expert.py generate-callgraph \
  --data <perf.script.txt> \
  [--format dot|json] \
  [--max-nodes <N>] \
  [--min-edge-count <N>]
```

---

## 通用参数

所有命令支持:

| 参数 | 说明 | 示例 |
|------|------|------|
| `--data <path>` | perf script 文件路径（必填） | `--data perf.txt` |
| `--cpu-id <ID>` | 仅分析指定 CPU | `--cpu-id 0` |
| `--pid <PID>` | 仅分析指定进程 | `--pid 1234` |
| `--comm <name>` | 按进程名过滤（逗号分隔多值） | `--comm nginx,php-fpm` |
| `--comm-regex <pattern>` | 按进程名正则匹配 | `--comm-regex 'java.*'` |
| `--start-time <ts>` | 起始时间戳（含） | `--start-time 1000.5` |
| `--end-time <ts>` | 结束时间戳（含） | `--end-time 1010.0` |

**注意**：`--freq` 参数已在 v2.0 中移除。CPU 利用率和数据可靠性直接基于 perf script 的 `core/s` 字段计算。

---

## 典型工作流

```bash
# 工作流 1: 系统级概览
check-cpu-bottleneck → get-process-top → cluster-paths → find-callers --auto-target

# 工作流 2: 特定进程深度分析
show-cpu-usage --pid 1234 → cluster-symbols --pid 1234 → cluster-paths --pid 1234

# 工作流 3: 异常时间窗口分析
detect-anomalies → cluster-paths --start-time 15.0 --end-time 16.0

# 工作流 4: 进程风暴检测（高频进程创建问题）
count-process-variety → 对风暴进程使用 cluster-symbols --comm <name> → find-callers
```

---

## 可靠性提示

工具输出可靠性等级:
- `CRITICAL`: 样本数 < 10 或 CPU 利用率 < 3%，结论不可信
- `WARNING`: CPU 利用率较低或样本数偏少，百分比误差可能 > ±20%
- `ACCEPTABLE`: CPU 利用率中等，样本数尚可，关注相对排序
- `GOOD`/`EXCELLENT`: CPU 利用率高且样本充足，结论可信

低频率采样场景下，**关注相对排序而非精确百分比**。
