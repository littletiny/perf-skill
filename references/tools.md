# Perf Expert 工具命令参考

> 纯命令参考手册。分析策略和方法论请查阅 [workflow-patterns.md](./workflow-patterns.md) 和 [workflow-core.md](./workflow-core.md)。

---

## 快速使用

### 方式 1: wrap 脚本（推荐）

使用 `spear` wrap 脚本简化命令执行，自动注入 `--data` 参数：

```bash
# 1. 初始化（配置数据路径，只需一次）
$SKILL_DIR/scripts/spear init --data-path <perf.data> [--freq <hz>]

# 2. 后续命令大幅简化
spear get-hotspots --comm myapp
spear check-cpu-bottleneck --cpu-limit 0.5c
spear find-callers --target pthread_mutex_lock

# 3. 查看当前配置
spear status
```

**特点**:
- 自动从 `.spear_env` 加载配置
- 自动为子命令注入 `--data` 参数
- 自动注入 `--freq` 参数（如配置了采样频率）
- 支持 `SPEAR_DATA` 环境变量临时覆盖数据文件
- **注意**: 若需修改频率，请重新运行 `spear init --freq <hz>`

### 方式 2: 直接调用

```bash
python3 $SKILL_DIR/scripts/perf_expert.py <subcommand> --data <perf.data> [options]
```

---

## 命令速查表

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `check-cpu-bottleneck` | 资源限制判定 | 环境边界检查 |
| `show-cpu-usage` | CPU 利用率概览 | user/kernel 分解 |
| `detect-anomalies` | 时序异常定位 | 突发问题分析 |
| `analyze-core-distribution` | 核心级负载分析 | 负载不均衡检查 |
| `get-process-top` | 高消耗单进程识别 | 定位主要消耗者 |
| `get-comm-top` | 高消耗进程组识别 | 大量小进程场景 |
| `get-hotspots` | 热点函数排名 | 代码级优化 |
| `find-callers` | 热点函数溯源 | 调用链分析 |
| `cluster-paths` | 调用路径聚类 | 共同前缀模式 |
| `cluster-symbols` | 语义规则聚类 | 行为模式识别 |
| `count-process-variety` | 进程风暴检测 | 短生命周期进程 |
| `cluster-comm` | 进程名聚类 | 进程组行为分析 |
| `generate-flamegraph` | FlameGraph 导出 | 可视化报告 |
| `generate-callgraph` | 调用图导出 | 可视化报告 |

---

## 环境评估工具

### check-cpu-bottleneck

检查资源限制和单核饱和。

```bash
python3 scripts/perf_expert.py check-cpu-bottleneck \
  --data <perf.script.txt> \
  [--cpu-limit-threshold <ratio>]
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `--data` | string | perf script 文件路径（必填） |
| `--cpu-limit-threshold` | float | CPU 限制阈值比例（默认 0.8） |

**退出码**:
| 码值 | 含义 |
|------|------|
| 0 | 无瓶颈 |
| 1 | 检测到 CPU 限制瓶颈 |
| 2 | 检测到单核饱和 |
| 3 | 同时存在限制和单核饱和 |

---

### show-cpu-usage

查看 CPU 利用率 (user/kernel)。

```bash
python3 scripts/perf_expert.py show-cpu-usage \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--cpu-id <ID>]
```

**输出字段**:
| 字段 | 说明 |
|------|------|
| `user_pct` | 用户态 CPU 百分比 |
| `kernel_pct` | 内核态 CPU 百分比 |
| `total_pct` | 总 CPU 利用率 |
| `user_records` | 用户态聚合记录数 |
| `kernel_records` | 内核态聚合记录数 |

---

### detect-anomalies

时序异常检测与窗口定位。

```bash
python3 scripts/perf_expert.py detect-anomalies \
  --data <perf.script.txt> \
  [--window-size <sec>] \
  [--spike-threshold <ratio>] \
  [--min-utilization <ratio>] \
  [--cpu-id <ID>]
```

**检测类型**:
| 类型 | 说明 |
|------|------|
| `SPIKE` | 利用率突增 |
| `DROP` | 利用率突降 |
| `LEVEL_SHIFT` | 水平迁移 |
| `BURST` | 短时爆发 |

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--window-size` | int | 5 | 滑动窗口大小（秒） |
| `--spike-threshold` | float | 2.0 | 变化倍数阈值 |
| `--min-utilization` | float | 0.05 | 最小利用率阈值 |

---

### analyze-core-distribution

核心级负载分布与均衡性分析。

```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>]
```

**输出字段**:
| 字段 | 说明 |
|------|------|
| `imbalance_level` | 不均衡等级: LOW/MEDIUM/HIGH/CRITICAL |
| `max_utilization_pct` | 最高核心利用率 |
| `min_utilization_pct` | 最低核心利用率 |
| `patterns` | 检测到的模式数组 |

**检测模式**:
| 模式 | 说明 |
|------|------|
| `SINGLE_CORE_SATURATION` | 单核满载，其他核心空闲 |
| `WIDE_DISTRIBUTION_LOW_UTIL` | 广泛分布但利用率低 |

---

## 进程分析工具

### get-process-top

识别高消耗单个进程。

```bash
python3 scripts/perf_expert.py get-process-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 10 | 显示进程数 |
| `--cpu-id` | int | - | 仅分析指定 CPU |

**输出格式**:
```
# Format: comm(pid) total_util/kernel_util
nginx(1234) 45.50%/12.30%
redis(5678) 23.40%/5.60%
...
```

**字段说明**:
| 字段 | 说明 |
|------|------|
| `comm` | 进程名 |
| `pid` | 进程 ID |
| `total_util` | 总 CPU 利用率（包含 user + kernel） |
| `kernel_util` | 内核态 CPU 利用率占比 |

---

### get-comm-top

识别高消耗进程组（大量小进程场景）。

```bash
python3 scripts/perf_expert.py get-comm-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--sort-by-density] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 10 | 显示进程组数 |
| `--sort-by-density` | flag | - | 按密度指数排序 |
| `--comm` | string | - | 过滤指定进程名 |

**输出字段**:
| 字段 | 说明 |
|------|------|
| `comm` | 进程名 |
| `pid_count` | 进程数量 |
| `aggregate_cpu_pct` | 聚合 CPU 利用率 |
| `kernel_pct` | 平均内核态占比 |
| `density_index` | 密度指数（总CPU/进程数） |

---

## 热点分析工具

### get-hotspots

识别热点函数。

```bash
python3 scripts/perf_expert.py get-hotspots \
  --data <perf.script.txt> \
  [--sort-by inclusive|self] \
  [--top-n <N>] \
  [--pid <PID>] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--sort-by` | string | self | 排序方式: inclusive/self |
| `--top-n` | int | 20 | 显示热点数 |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |

**排序方式**:
| 方式 | 说明 |
|------|------|
| `inclusive` | 包含子调用时间，反映整体影响 |
| `self` | 仅自身执行时间，反映直接消耗 |

**输出字段**:
| 字段 | 说明 |
|------|------|
| `symbol` | 函数名 |
| `self_pct` | 自身消耗百分比 |
| `inclusive_pct` | 包含子调用百分比 |
| `core_sec` | core/s 值 |

---

### find-callers

热点函数溯源。

```bash
# 指定 target 模式
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --target <function> \
  [--min-ratio <pct>] \
  [--pid <PID>] \
  [--comm <name>]

# 自动模式
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --auto-target \
  [--auto-target-top-n <N>] \
  [--pid <PID>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--target` | string | - | 目标函数名（与 --auto-target 互斥） |
| `--auto-target` | flag | - | 自动追踪热点 |
| `--auto-target-top-n` | int | 3 | 自动追踪热点数 |
| `--min-ratio` | float | 5.0 | 最小占比阈值（%） |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |

**常用 target 函数**:
| 函数 | 用途 |
|------|------|
| `schedule` | 分析调度原因 |
| `nanosleep` | 分析主动休眠 |
| `pthread_mutex_lock` | 分析锁竞争 |
| `epoll_wait` | 分析 IO 等待 |
| `futex_wait` | 分析用户态锁 |

---

### cluster-paths

调用路径聚类，识别共同前缀模式。

```bash
python3 scripts/perf_expert.py cluster-paths \
  --data <perf.script.txt> \
  [--min-depth <N>] \
  [--min-samples <N>] \
  [--top-n <N>] \
  [--pid <PID>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--min-depth` | int | 3 | 最小调用深度 |
| `--min-samples` | int | 5 | 最小样本数 |
| `--top-n` | int | 10 | 显示路径数 |
| `--pid` | int | - | 过滤指定进程 |

---

## 语义聚类工具

### cluster-symbols

按专家规则语义聚类。

```bash
python3 scripts/perf_expert.py cluster-symbols \
  --data <perf.script.txt> \
  [--no-include-experts] \
  [--custom-rules <json>] \
  [--pid <PID>] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--no-include-experts` | flag | - | 禁用内置专家规则 |
| `--custom-rules` | json | - | 自定义规则 |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |

**内置规则分类**:
| 类别 | 匹配模式 | 含义 |
|------|---------|------|
| `EVENT_IRQ_OFF` | IRQ off, spin_unlock | 长临界区 |
| `EVENT_SCHEDULER` | schedule, yield | 调度器活动 |
| `EVENT_MEM_RECLAIM` | reclaim, TLB, page | 内存回收 |
| `EVENT_LOCK_CONTENTION` | mutex, spinlock, futex | 锁竞争 |
| `EVENT_SYNC_PRIMITIVE` | pthread_cond, barrier | 同步原语 |

**自定义规则**:
```bash
# 字符串格式
--custom-rules '{"MY_SCHEDULING": "schedule|nanosleep|epoll_wait"}'

# 列表格式
--custom-rules '{"MY_SCHEDULING": ["schedule", "nanosleep", "epoll_wait"]}'

# 领域特定规则
--custom-rules '{
  "RPC": "grpc|protobuf|thrift",
  "DB": "rocksdb|leveldb|sqlite",
  "ML": "tensorflow|torch|cudnn"
}'
```

---

### cluster-comm

按进程名聚类分析进程组行为。

```bash
python3 scripts/perf_expert.py cluster-comm \
  --data <perf.script.txt> \
  [--top-n <N>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 20 | 显示进程组数 |

---

## 领域定位工具

### count-process-variety

检测进程风暴/短生命周期进程。

```bash
python3 scripts/perf_expert.py count-process-variety \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--storm-pid-threshold <N>] \
  [--storm-ratio-threshold <ratio>] \
  [--storm-cpu-threshold <core/s>] \
  [--pid <PID>] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 20 | 显示进程名数 |
| `--storm-pid-threshold` | int | 50 | PID 数量阈值 |
| `--storm-ratio-threshold` | float | 2.0 | samples/PID 阈值 |
| `--storm-cpu-threshold` | float | 0.5 | 单 PID CPU 阈值 |

**检测模式**:
| 模式 | 条件 |
|------|------|
| `PROCESS_STORM` | samples_per_pid ≤ 阈值 且 short_lived_ratio > 50% |
| `LONG_RUNNING` | 单进程主导 |

---

## 可视化工具

### generate-flamegraph

生成 FlameGraph 格式。

```bash
python3 scripts/perf_expert.py generate-flamegraph \
  --data <perf.script.txt> \
  [--output <path>] \
  [--pid <PID>] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--output` | string | - | 输出文件路径（默认 stdout） |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |

**输出格式**: 符合 FlameGraph 标准的折叠栈格式

---

### generate-callgraph

生成调用图（DOT/JSON 格式）。

```bash
python3 scripts/perf_expert.py generate-callgraph \
  --data <perf.script.txt> \
  [--output <path>] \
  [--format dot|json] \
  [--target <function>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--output` | string | - | 输出文件路径 |
| `--format` | string | dot | 输出格式: dot/json |
| `--target` | string | - | 从指定函数开始生成 |

---

## Live Document 命令

### doc init

初始化诊断文档。

```bash
python3 scripts/perf_expert.py doc init --data <perf.data>
```

**作用**: 创建 `.perf-doc.json` 用于问题状态追踪

---

### doc add

添加问题记录。

```bash
python3 scripts/perf_expert.py doc add \
  --id <ISS-XXX> \
  --desc "问题描述" \
  [--risk "风险等级"] \
  [--hint "建议操作"]
```

---

### doc complete

标记问题完成。

```bash
python3 scripts/perf_expert.py doc complete \
  --id <ISS-XXX> \
  --result "分析结果"
```

---

### doc list

列出所有问题。

```bash
python3 scripts/perf_expert.py doc list [--format text|json]
```

---

### doc finalize

最终审计（生成报告前必须执行）。

```bash
python3 scripts/perf_expert.py doc finalize
```

---

### doc export

导出报告。

```bash
python3 scripts/perf_expert.py doc export \
  [--format markdown|json] \
  [--output <path>]
```

---

## 通用参数

所有命令支持:

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--data <path>` | string | perf script 文件路径（必填） | `--data perf.txt` |
| `--cpu-id <ID>` | int | 仅分析指定 CPU | `--cpu-id 0` |
| `--pid <PID>` | int | 仅分析指定进程 | `--pid 1234` |
| `--comm <name>` | string | 按进程名过滤（逗号分隔多值） | `--comm nginx,php-fpm` |
| `--comm-regex <pattern>` | string | 按进程名正则匹配 | `--comm-regex 'java.*'` |
| `--start-time <ts>` | float | 起始时间戳（含） | `--start-time 1000.5` |
| `--end-time <ts>` | float | 结束时间戳（含） | `--end-time 1010.0` |

---

## 参考文档

- 📗 **典型分析模式**: [workflow-patterns.md](./workflow-patterns.md) - 5 种场景的完整分析路径
- 📘 **核心流程详解**: [workflow-core.md](./workflow-core.md) - 7 Phase 分析流程
- 📕 **启发式规则手册**: [heuristics.md](./heuristics.md) - 五大认知闭包、诊断规则
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
