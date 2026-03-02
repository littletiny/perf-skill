# Perf Expert 工具命令参考

> 纯命令参考手册。分析策略和方法论请查阅 [workflow-patterns.md](./workflow-patterns.md) 和 [workflow-core.md](./workflow-core.md)。

---

## 快速使用

### 方式 1: wrap 脚本（推荐）

使用 `spear` wrap 脚本简化命令执行，自动注入 `--data` 参数：

```bash
# 1. 初始化（配置数据路径，只需一次）
scripts/spear init --data-path <perf.data> [--freq <hz>]

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
spear <subcommand> [options]
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

---

## 环境评估工具

### check-cpu-bottleneck

检查资源限制和单核饱和。

```bash
spear check-cpu-bottleneck \
  --data <perf.script.txt> \
  [--cpu-limit <limit>] \
  [--threshold <pct>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `--data` | string | perf script 文件路径（必填） |
| `--cpu-limit` | string | CPU limit（如 `0.5c` 表示 0.5 core） |
| `--threshold` | float | 单核饱和检测阈值（默认 80%） |

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
spear show-cpu-usage \
  --data <perf.script.txt> \
  [--cpu-id <ID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
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
spear detect-anomalies \
  --data <perf.script.txt> \
  [--window-size <sec>] \
  [--spike-threshold <ratio>] \
  [--min-utilization <ratio>] \
  [--cpu-id <ID>] \
  [--top-n <N>]
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
| `--window-size` | float | 1.0 | 滑动窗口大小（秒） |
| `--spike-threshold` | float | 0.5 | 变化倍数阈值 |
| `--min-utilization` | float | 0.3 | 最小利用率阈值 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--top-n` | int | 10 | 显示的异常数 |
| `--export-mode` | flag | - | 导出所有窗口数据 |
| `--export-samples` | flag | - | 包含详细样本数据 |
| `--detect-in-export` | flag | - | 导出模式也检测异常 |

---

### analyze-core-distribution

核心级负载分布与均衡性分析。

```bash
spear analyze-core-distribution \
  --data <perf.script.txt> \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--top-n <N>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--pid` | int | - | 仅分析指定进程 |
| `--comm` | string | - | 按进程名过滤 |
| `--comm-regex` | string | - | 按进程名正则匹配 |
| `--top-n` | int | 10 | 显示饱和核心数 |

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
spear get-process-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
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
spear get-comm-top \
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
spear get-hotspots \
  --data <perf.script.txt> \
  [--sort-by inclusive|self] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--sort-by` | string | inclusive | 排序方式: inclusive/self |
| `--top-n` | int | 10 | 显示热点数 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |
| `--comm-regex` | string | - | 按进程名正则匹配 |

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
spear find-callers \
  --data <perf.script.txt> \
  --target <function> \
  [--min-cpu <pct>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]

# 自动模式
spear find-callers \
  --data <perf.script.txt> \
  --auto-target \
  [--min-cpu <pct>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--target` | string | - | 目标函数名（与 --auto-target 互斥） |
| `--auto-target` | flag | - | 自动追踪热点 |
| `--top-n` | int | 10 | 显示结果数 |
| `--min-cpu` | float | 3.0 | 最小 CPU 利用率阈值（%） |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |
| `--comm-regex` | string | - | 按进程名正则匹配 |

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
spear cluster-paths \
  --data <perf.script.txt> \
  [--min-depth <N>] \
  [--min-samples <N>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--min-depth` | int | 2 | 最小调用深度 |
| `--min-samples` | int | 5 | 最小样本数 |
| `--top-n` | int | 10 | 显示路径数 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |
| `--comm-regex` | string | - | 按进程名正则匹配 |

---

## 语义聚类工具

### cluster-symbols

按专家规则语义聚类。

```bash
spear cluster-symbols \
  --data <perf.script.txt> \
  [--no-include-experts] \
  [--custom-rules <json>] \
  [--rules-file <path>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--no-include-experts` | flag | - | 禁用内置专家规则 |
| `--custom-rules` | json | - | 自定义规则（最高优先级） |
| `--rules-file` | path | - | 外部规则文件路径 |
| `--top-n` | int | 10 | 显示聚类数 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--pid` | int | - | 过滤指定进程 |
| `--comm` | string | - | 过滤指定进程名 |
| `--comm-regex` | string | - | 按进程名正则匹配 |

**规则优先级**（从高到低）：
1. `--custom-rules` 命令行参数
2. `--rules-file` 外部文件规则
3. 内置专家规则（默认启用）

**内置规则分类**:
| 类别 | 匹配模式 | 含义 |
|------|---------|------|
| `EVENT_IRQ_OFF` | IRQ off, spin_unlock | 长临界区 |
| `EVENT_SCHEDULER` | schedule, yield | 调度器活动 |
| `EVENT_MEM_RECLAIM` | reclaim, TLB, page | 内存回收 |
| `EVENT_LOCK_CONTENTION` | mutex, spinlock, futex | 锁竞争 |
| `EVENT_SYNC_PRIMITIVE` | pthread_cond, barrier | 同步原语 |

**外部规则文件** (`--rules-file`):
```bash
# 使用外部规则文件（完全替代内置规则）
spear cluster-symbols --data perf.data --rules-file my_rules.json --no-include-experts

# 扩展内置规则（外部规则补充或覆盖）
spear cluster-symbols --data perf.data --rules-file extra_rules.json
```

规则文件格式（JSON）：
```json
{
  "EVENT_NETWORK": "sock_|tcp_|udp_|sk_",
  "EVENT_IO_WAIT": ["blk_", "scsi_", "nvme_"],
  "EVENT_CUSTOM": "my_pattern.*"
}
```

**自定义规则**（`--custom-rules`）：
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

**组合使用示例**：
```bash
# 内置规则 + 外部文件 + 命令行覆盖
spear cluster-symbols --data perf.data \
  --rules-file base_rules.json \
  --custom-rules '{"URGENT": "critical_.*"}'
```

---

### cluster-comm

按进程名聚类分析进程组行为。

```bash
spear cluster-comm \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 10 | 显示进程组数 |
| `--cpu-id` | int | - | 仅分析指定 CPU |

---

## 领域定位工具

### count-process-variety

检测进程风暴/短生命周期进程。

**适用场景**：发现 fork 炸弹、连接风暴、worker 进程频繁创建销毁等问题。

```bash
spear count-process-variety \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--storm-pid-threshold <N>] \
  [--storm-ratio-threshold <ratio>] \
  [--cpu-id <ID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 20 | 显示进程名数 |
| `--storm-pid-threshold` | int | 50 | PID 数量阈值，超过此值考虑为风暴 |
| `--storm-ratio-threshold` | float | 2.0 | samples/PID 阈值，低于此值说明进程生命周期短 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--comm` | string | - | 过滤指定进程名 |
| `--comm-regex` | string | - | 按进程名正则匹配 |

**注意**：本工具用于分析"进程多样性"，不支持 `--pid` 过滤（单个 PID 不存在"多样性"）。

**输出字段**:
| 字段 | 说明 |
|------|------|
| `comm` | 进程名 |
| `pids_per_min` | 每分钟进程数（去重后的 PID 速率） |
| `cpu_util` | CPU 利用率 |
| `behavior` | 行为模式: process_storm/normal |

**检测模式**:
| 模式 | 条件 | 说明 |
|------|------|------|
| `PROCESS_STORM` | PID 数≥10 且 samples_per_pid≤2 且短进程比例>50% | 大量短生命周期进程 |
| `LONG_RUNNING` | 单 PID 主导 | 长运行进程，非风暴场景 |

---

## Trace 命令

### trace init

初始化诊断追踪文档。

```bash
spear trace init --data <perf.data>
# 或
spear trace init --data <perf.data>
```

**作用**: 创建 `.spear.json` 用于诊断过程追踪

---

### trace add

添加问题记录（自动生成 ID）。

```bash
spear trace add \
  --desc "问题描述" \
  [--level critical|warning|info] \
  [--hint "建议操作"]
```

**输出**: `✓ 已添加问题: ISS-001`

---

### trace complete

标记问题完成。

```bash
spear trace complete \
  --id ISS-001 \
  --result "分析结果"
```

---

### trace issues

列出所有问题。

```bash
spear trace issues [--status open|resolved|all]
```

---

### trace finalize

最终审计（生成报告前必须执行）。

```bash
spear trace finalize [--accept-risk "理由"]
```

---

### trace export

导出报告。

```bash
spear trace export \
  [--format markdown|json] \
  [--output <path>]
```

---

### trace timeline

查看诊断时间线。

```bash
spear trace timeline [--format text|json]
```

---

## 通用参数

各命令支持的过滤参数如下：

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--data <path>` | string | perf script 文件路径（必填） | `--data perf.txt` |
| `--start-time <time>` | string | 起始时间（含） | `2024-01-15T10:30:00` |
| `--end-time <time>` | string | 结束时间（含） | `2024-01-15 10:30:00` |

**时间格式说明**:

`--start-time` 和 `--end-time` 支持多种格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| Unix 时间戳 | `1705312200` | 秒级时间戳（兼容旧版本） |
| ISO 8601 | `2024-01-15T10:30:00` | 标准 ISO 格式 |
| ISO 8601 带时区 | `2024-01-15T10:30:00+08:00` | 带时区信息 |
| 常用日期时间 | `2024-01-15 10:30:00` | 空格分隔 |
| 日期 | `2024-01-15` | 自动补全为 00:00:00 |

**其他通用参数**:

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--cpu-id <ID>` | int | 仅分析指定 CPU | `--cpu-id 0` |
| `--pid <PID>` | int | 仅分析指定进程 | `--pid 1234` |
| `--comm <name>` | string | 按进程名过滤（逗号分隔多值） | `--comm nginx,php-fpm` |
| `--comm-regex <pattern>` | string | 按进程名正则匹配 | `--comm-regex 'java.*'` |

**参数支持情况速查**:

| 工具 | `--cpu-id` | `--pid` | `--comm` | `--comm-regex` | `--start/end-time` |
|------|:----------:|:-------:|:--------:|:--------------:|:------------------:|
| `check-cpu-bottleneck` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `show-cpu-usage` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `detect-anomalies` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `analyze-core-distribution` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `get-process-top` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `get-comm-top` | ✅ | ❌ | ❌ | ✅ | ✅ |
| `get-hotspots` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `find-callers` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-paths` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-symbols` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-comm` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `count-process-variety` | ✅ | ❌ | ✅ | ✅ | ✅ |

---

## 参考文档

- 📗 **典型分析模式**: [workflow-patterns.md](./workflow-patterns.md) - 5 种场景的完整分析路径
- 📘 **核心流程详解**: [workflow-core.md](./workflow-core.md) - 7 Phase 分析流程
- 📕 **启发式规则手册**: [heuristics.md](./heuristics.md) - 五大认知闭包、诊断规则
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
