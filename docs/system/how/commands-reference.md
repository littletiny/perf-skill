# Perf Hunter 命令手册（三层架构版）

基于 Core-Analysis-Composite 三层架构的命令说明

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Composite (组合层)                                     │
│  职责: 编排多个 Analysis 工具，生成综合诊断报告                    │
│  Trace: 仅记录顶层命令，内部调用不记录                             │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Analysis (分析层)                                      │
│  职责: 实现具体诊断逻辑，通过 Facade 提供双接口                    │
│  CLI接口: 记录 Trace，供用户直接调用                              │
│  内部接口: 供 Composite 调用，不记录 Trace                        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Core (核心层)                                          │
│  职责: 数据解析、Trace 记录、基础输出能力                          │
│  约束: 所有数据解析在此完成，上层禁止直接访问原始数据               │
└─────────────────────────────────────────────────────────────────┘
```

**设计原则**:
- 向下依赖: 每层只能调用直接下层的接口
- 接口封装: 下层能力通过 Facade 模式暴露
- Trace 边界: Composite 层统一记录，Analysis 内部调用不记录
- 数据流动: Core → Analysis → Composite（单向）

---

## Layer 1: Core 层（数据层）

Core 层提供数据解析和管理能力，不直接暴露给用户，通过 Engine 接口供上层调用。

### Core Engine 接口

| 接口 | 用途 | 返回类型 |
|------|------|----------|
| `load_data(path)` | 加载 perf 数据文件 | bool |
| `get_filtered_samples(...)` | 获取过滤后的样本 | List[Dict] |
| `get_time_range()` | 获取数据时间范围 | Tuple[float, float] |
| `get_comm_cpu_util(samples)` | 进程组级 CPU 利用率 | Dict[str, Dict] |
| `get_pid_cpu_util(samples)` | 进程级 CPU 利用率 | Dict[int, Dict] |
| `get_core_cpu_util(samples)` | 核心级 CPU 利用率 | Dict[int, Dict] |
| `get_symbol_hotspots(...)` | 符号热点数据 | Dict[str, Dict] |
| `get_process_lifecycle(...)` | 进程生命周期信息 | Dict |
| `get_call_graph(...)` | 指定符号的调用图 | Dict |

### 数据结构说明

**CPU 利用率数据结构**:
```python
{
    "comm_name": {
        "total_pct": float,      # 总 CPU%
        "kernel_pct": float,     # 内核态 CPU%
        "user_pct": float,       # 用户态 CPU%
        "pid_count": int,        # 进程数
        "pids": List[int]        # PID 列表
    }
}
```

---

## 环境管理命令

环境命令用于管理数据文件配置和当前会话状态。

### init

初始化配置，添加并切换到新的数据文件。

```bash
shecr init --data-path <perf.data> [--script-path <path>] [--freq <hz>] [--risk-config <path>] [--rules-file <path>]
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `--data-path` | string | **必需**，perf 数据文件路径 |
| `--script-path` | string | shecr.py 脚本路径 |
| `--freq` | string | 采样频率（Hz）|
| `--risk-config` | string | Risk 显示配置文件 |
| `--rules-file` | string | 专家规则文件 |

**输出示例**:
```
✓ 数据文件已添加: /path/to/perf.data
✓ Trace 文档已创建: .shecr.trace.json

=== shecr (perf-hunter) 环境配置 ===

配置文件: /path/to/.shecr.json
Trace 文件: /path/to/.shecr.trace.json

已配置 1 个数据文件:

▶ /path/to/perf.data

▶ 当前默认数据文件

提示: 使用 'shecr use <path>' 切换默认数据文件
```

---

### use

切换默认数据文件。

```bash
shecr use <data_path|index>
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data_path` | string/int | 数据文件路径或索引（从 1 开始）|

**使用示例**:
```bash
# 通过路径切换
shecr use /path/to/perf.data

# 通过索引切换
shecr use 1
```

**输出示例**:
```
✓ 已切换到: /path/to/perf.data
  初始化时间: 2026-03-04T10:30:00
  采样频率: 99Hz
```

---

### list

列出所有已配置的数据文件。

```bash
shecr list
```

**输出示例**:
```
=== 已配置的数据文件 ===

▶ [1] /path/to/perf.data [✓]
       Freq: 99Hz

  [2] /another/path/data.txt [ ]

图例: ▶ 当前默认  ✓ 已在 trace 中使用

提示: 使用 'shecr use <path|index>' 切换默认数据文件
```

---

### status

显示当前配置和 trace 状态。

```bash
shecr status
```

**输出示例**:
```
=== shecr (perf-hunter) 环境配置 ===

配置文件: /path/to/.shecr.json
Trace 文件: /path/to/.shecr.trace.json

Timeline: 5 条命令记录
Issues: 2 个 (1 个待处理)
涉及数据文件: 1 个

已配置 2 个数据文件:

▶ /path/to/perf.data
    Freq: 99Hz

  /another/path/data.txt
    Freq: 99Hz

▶ 当前默认数据文件

提示: 使用 'shecr use <path>' 切换默认数据文件
```

---

## Layer 2: Analysis 层（分析层）

Analysis 层实现具体诊断逻辑，通过 **Facade 模式** 提供双接口：

- **CLI 接口**: 用户直接调用，触发 Trace 记录
- **内部接口**: Composite 层调用，不触发 Trace

### Analysis Facade 接口

| 方法 | 对应 CLI 命令 | 用途 |
|------|--------------|------|
| `analyze_comm_top()` | `get-comm-top` | 进程组 CPU 分析 |
| `analyze_hotspots()` | `get-hotspots` | 热点函数分析 |
| `analyze_core_distribution()` | `analyze-core-distribution` | 核心级负载分布 |
| `detect_anomalies()` | `detect-anomalies` | 时序异常检测 |
| `analyze_callers()` | `find-callers` | 调用链溯源 |
| `cluster_paths()` | `cluster-paths` | 调用路径聚类 |

### CLI 命令详解

#### 进程分析工具

##### get-comm-top

识别高消耗进程组。

```bash
shecr get-comm-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--sort-by-density] \
  [--cpu-id <ID>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**输出字段**:
| 字段 | 说明 |
|------|------|
| `comm` | 进程名 |
| `pid_count` | 进程数量 |
| `aggregate_cpu_pct` | 聚合 CPU 利用率 |
| `kernel_pct` | 平均内核态占比 |
| `density_index` | 密度指数（总CPU/进程数）|

---

#### 热点分析工具

##### get-hotspots

识别热点函数。

```bash
shecr get-hotspots \
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

##### find-callers

热点函数溯源。

```bash
# 指定 target 模式
shecr find-callers \
  --data <perf.script.txt> \
  --target <function> \
  [--min-ratio <pct>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**常用 target 函数**:
| 函数 | 用途 |
|------|------|
| `schedule` | 分析调度原因 |
| `nanosleep` | 分析主动休眠 |
| `pthread_mutex_lock` | 分析锁竞争 |
| `epoll_wait` | 分析 IO 等待 |
| `futex_wait` | 分析用户态锁 |

---

#### 环境评估工具

##### detect-anomalies

时序异常检测与窗口定位。

```bash
shecr detect-anomalies \
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
| `--window-size` | float | 1.0 | 滑动窗口大小（秒）|
| `--spike-threshold` | float | 0.5 | 变化倍数阈值 |
| `--min-utilization` | float | 0.3 | 最小利用率阈值 |
| `--cpu-id` | int | - | 仅分析指定 CPU |
| `--top-n` | int | 10 | 显示的异常数 |

---

##### analyze-core-distribution

核心级负载分布与均衡性分析。

```bash
shecr analyze-core-distribution \
  --data <perf.script.txt> \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--top-n <N>] \
  [--start-time <ts>] \
  [--end-time <ts>]
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

##### cluster-paths

调用路径聚类，识别共同前缀模式。

```bash
shecr cluster-paths \
  --data <perf.script.txt> \
  [--min-depth <N>] \
  [--min-samples <N>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--min-depth` | int | 2 | 最小调用深度 |
| `--min-samples` | int | 5 | 最小样本数 |
| `--top-n` | int | 10 | 显示路径数 |

---

## Layer 3: Composite 层（组合层）

Composite 层通过编排多个 Analysis 工具，生成综合诊断报告。内部调用 Analysis Facade 时不触发 Trace 记录，仅顶层命令被记录到 timeline。

### 组合命令列表

| 命令 | 用途 | 编排工具 |
|------|------|----------|
| `sys-audit` | 系统全面审计 | detect-anomalies + analyze-core-distribution + get-comm-top |
| `bottleneck-analyze` | 瓶颈分析 | get-comm-top + get-hotspots + find-callers |

---

### sys-audit

系统审计组合命令，解决"A 掩盖 B"问题。

```bash
shecr sys-audit \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**编排逻辑**:
1. `detect-anomalies` → 发现突变时刻
2. `analyze-core-distribution` → 分析核心分布
3. `get-comm-top` → 分析进程组
4. 综合分析，生成诊断报告

**诊断报告结构**:
```python
{
    "primary_suspect": {       # 主要嫌疑人
        "comm": str,
        "impact_score": float,
        "diagnosis": str       # BOTTLENECK/STORM/UNBALANCED
    },
    "secondary_loads": [...],  # 次要负载
    "background_noise": [...], # 背景噪音
    "root_cause_chain": str,   # 根因链描述
    "recommendations": [...]   # 操作建议
}
```

**输出示例**:
```json
{
    "_risk": {
        "level": "critical",
        "message": "发现主要性能瓶颈: netstat",
        "hint": "执行 bottleneck-analyze --comm netstat 深入分析"
    },
    "diagnosis": {
        "primary_suspect": {
            "comm": "netstat",
            "total_cpu": 12.5,
            "impact_score": 75.3
        },
        "root_cause_chain": "单进程垄断 CPU 资源，疑似串行化处理"
    }
}
```

---

### bottleneck-analyze

瓶颈追踪分析，深度定位性能瓶颈。

```bash
shecr bottleneck-analyze \
  --data <perf.script.txt> \
  [--comm <name>] \
  [--top-n <N>] \
  [--cpu-id <ID>] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**编排逻辑**:
1. `get-comm-top` → 识别瓶颈进程
2. `get-hotspots --comm <target>` → 分析热点函数
3. `find-callers --target <hotspot>` → 热点溯源

**使用场景**:
```bash
# 场景 1: 已知瓶颈进程
shecr bottleneck-analyze --comm netstat

# 场景 2: 自动检测瓶颈（不指定 --comm）
shecr bottleneck-analyze --data <perf.script.txt>
```

---

## Trace 命令

Trace 系统用于记录诊断过程，所有 Analysis CLI 命令自动记录到 timeline。

### trace init

初始化诊断追踪文档。

```bash
shecr trace init --data <perf.data>
```

---

### trace add

添加问题记录（自动生成 ID）。

```bash
shecr trace add \
  --desc "问题描述" \
  [--level critical|warning|info] \
  [--risk "不处理的风险"] \
  [--hint "建议操作"]
```

**输出**: `✓ 已添加问题: ISS-001`

---

### trace complete

标记问题完成。

```bash
shecr trace complete \
  --id ISS-001 \
  --result "分析结果"
```

---

### trace reopen

重新打开已解决的问题。

```bash
shecr trace reopen \
  --id ISS-001 \
  [--reason "重新打开原因"]

# 重新打开所有已解决的问题
shecr trace reopen --all
```

---

### trace issues

列出所有问题。

```bash
shecr trace issues [--status open|resolved|all]
```

---

### trace audit

事后独立审计，验证诊断质量。

```bash
# 完整审计
shecr trace audit

# 指定阶段
shecr trace audit --phase structural
shecr trace audit --phase timeline
shecr trace audit --phase depth

# JSON 输出
shecr trace audit --format json --output audit-report.json
```

---

### trace finalize

结束诊断。

```bash
shecr trace finalize
shecr trace finalize --accept-risk "与当前问题无关"
```

---

### trace export

导出报告。

```bash
shecr trace export \
  [--format markdown|json] \
  [--output <path>]
```

---

### trace timeline

查看诊断时间线。

```bash
shecr trace timeline [--format text|json]
```

---

## 通用参数

### 过滤参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--data <path>` | string | perf script 文件路径 | `--data perf.txt` |
| `--start-time <time>` | string | 起始时间（含） | `2024-01-15T10:30:00` |
| `--end-time <time>` | string | 结束时间（含） | `2024-01-15 10:30:00` |
| `--cpu-id <ID>` | int | 仅分析指定 CPU | `--cpu-id 0` |
| `--pid <PID>` | int | 仅分析指定进程 | `--pid 1234` |
| `--comm <name>` | string | 按进程名过滤 | `--comm nginx,php-fpm` |
| `--comm-regex <pattern>` | string | 按进程名正则匹配 | `--comm-regex 'java.*'` |

### 时间格式

| 格式 | 示例 | 说明 |
|------|------|------|
| Unix 时间戳 | `1705312200` | 秒级时间戳 |
| ISO 8601 | `2024-01-15T10:30:00` | 标准 ISO 格式 |
| ISO 8601 带时区 | `2024-01-15T10:30:00+08:00` | 带时区信息 |
| 常用日期时间 | `2024-01-15 10:30:00` | 空格分隔 |
| 日期 | `2024-01-15` | 自动补全为 00:00:00 |

---

## 参数支持速查表

| 工具 | `--data` | `--cpu-id` | `--pid` | `--comm` | `--comm-regex` | `--start/end-time` |
|------|:--------:|:----------:|:-------:|:--------:|:--------------:|:------------------:|
| `init` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `use` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `list` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `status` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `get-comm-top` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `get-hotspots` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `find-callers` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `detect-anomalies` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `analyze-core-distribution` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-paths` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `sys-audit` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `bottleneck-analyze` | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |

---

## 三层架构数据流

### CLI 调用（记录 Trace）

```
用户: shecr get-comm-top --data xxx.data

┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│ CLI 层  │────▶│ @command     │────▶│ CLI Wrapper │────▶│ Analyzer │
└─────────┘     │ (记录 Trace) │     └──────┬──────┘     └────┬─────┘
                └──────────────┘            │                 │
                                            ▼                 ▼
                                      ┌──────────┐     ┌──────────┐
                                      │ Output   │◀────│ Core     │
                                      │ Builder  │     │ Engine   │
                                      └──────────┘     └──────────┘

Trace 记录:
- timeline[0]: command="get-comm-top --data xxx.data"
```

### Composite 调用（不记录子 Trace）

```
用户: shecr sys-audit --data xxx.data

┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│ CLI 层  │────▶│ @command     │────▶│ cmd_sys_    │────▶│ Analysis    │
└─────────┘     │ (记录 Trace) │     │ audit       │     │ Facade      │
                └──────────────┘     └──────┬──────┘     │ (internal)  │
                                            │            └──────┬──────┘
                                            │    ┌──────────────┼───────────┐
                                            │    ▼              ▼           ▼
                                            │ ┌────────┐   ┌────────┐   ┌────────┐
                                            │ │ detect │   │analyze │   │get-comm│
                                            │ │anomalies   │core-dist   │-top    │
                                            │ └───┬────┘   └───┬────┘   └───┬────┘
                                            │     │            │            │
                                            │     └────────────┴─────┬──────┘
                                            │                        ▼
                                            │                   ┌──────────┐
                                            │                   │ Core     │
                                            │                   │ Engine   │
                                            │                   └──────────┘
                                            ▼
                                      ┌──────────┐
                                      │ Output   │
                                      │ Builder  │
                                      └──────────┘

Trace 记录:
- timeline[0]: command="sys-audit --data xxx.data"（仅顶层）
- 子调用 detect-anomalies/analyze-core-distribution/get-comm-top 不记录
```

---

## 快速使用指南

### 初始化（推荐）

```bash
# 1. 初始化（配置数据路径，只需一次）
shecr init --data-path <perf.data> [--freq <hz>]

# 2. 后续命令大幅简化
shecr get-hotspots --comm myapp
shecr find-callers --target pthread_mutex_lock
```

### 典型分析路径

```bash
# 1. 系统审计（推荐）
shecr sys-audit

# 2. 如发现瓶颈，深度追踪
shecr bottleneck-analyze --comm <target>

# 3. 查看诊断记录
shecr trace timeline
shecr trace issues
```

---

## 参考文档

- 📗 **三层架构设计**: `design-three-tier-architecture.md` - 架构详细说明
- 📘 **分析模式**: `references/workflow-patterns.md` - 5 种典型场景分析路径
- 📙 **核心流程**: `references/workflow.md` - 7 Phase 分析流程
- 📕 **分析方法论**: `references/methodology.md` - 三层架构驱动的完整方法论
- 📋 **文档模板**: `references/templates.md` - 诊断报告格式
