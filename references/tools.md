# Perf Expert 工具命令参考

> 纯命令参考手册。分析策略和方法论请查阅 [methodology.md](./methodology.md) 和 [workflow-patterns.md](./workflow-patterns.md)。
>
> **版本更新**: 工具集已精简（12个 → 6个核心 + 3个组合），详见 [design-three-tier-architecture.md](../docs/design-three-tier-architecture.md)

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

### 核心分析工具（6个）

| 工具 | 层级 | 用途 | 典型场景 |
|------|------|------|---------|
| `analyze-core-distribution` | 系统级 | 核心级负载分析、单核饱和检测 | 负载不均衡检查 |
| `detect-anomalies` | 时间级 | 时序异常定位 | 突发问题分析 |
| `get-comm-top` | 实体级 | 进程组资源识别 + 离群检测 + 风暴检测 | 大量小进程场景、单进程瓶颈 |
| `get-hotspots` | 函数级 | 热点函数排名 | 代码级优化 |
| `find-callers` | 关系级 | 热点函数溯源 | 调用链分析 |
| `cluster-paths` | 模式级 | 调用路径聚类 | 业务逻辑定位 |

### 组合诊断工具（3个）

| 工具 | 链式触发 | 用途 | 典型场景 |
|------|----------|------|---------|
| `sys-audit` | anomalies → core-dist → comm-top | 系统全景扫描 | 快速定位真瓶颈 |
| `bottleneck-trace` | comm-top → hotspots → cluster-paths | 瓶颈深度追踪 | 单点性能问题 |

### 已合并/删除的工具

| 原工具 | 合并到 | 说明 |
|--------|--------|------|
| `check-cpu-bottleneck` | `analyze-core-distribution` | 单核饱和检测已整合 |
| `show-cpu-usage` | `analyze-core-distribution` | CPU利用率展示已整合 |
| `get-process-top` | `get-comm-top` | 通过CV/Monopoly实现单进程定位 |
| `cluster-comm` | `get-comm-top` | 进程组聚类已整合 |
| `count-process-variety` | `get-comm-top` | 作为Spawn Rate指标 |
| `cluster-symbols` | `cluster-paths` | 语义聚类已整合 |

---

## 系统级工具

### analyze-core-distribution

核心级负载分布分析（整合原 `check-cpu-bottleneck` 能力）。

检测单核饱和、中断不均、负载分布情况。

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
| `--cpu-limit` | string | - | CPU limit检测（如 `0.5c`） |
| `--threshold` | float | 80% | 单核饱和检测阈值 |

**输出字段**:
| 字段 | 说明 |
|------|------|
| `imbalance_level` | 不均衡等级: LOW/MEDIUM/HIGH/CRITICAL |
| `max_utilization_pct` | 最高核心利用率 |
| `min_utilization_pct` | 最低核心利用率 |
| `saturated_cores` | 饱和核心列表 |
| `patterns` | 检测到的模式数组 |

**检测模式**:
| 模式 | 说明 |
|------|------|
| `SINGLE_CORE_SATURATION` | 单核满载，其他核心空闲 |
| `WIDE_DISTRIBUTION_LOW_UTIL` | 广泛分布但利用率低 |
| `IRQ_IMBALANCE` | 中断分布不均 |

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

### get-comm-top

进程组资源分析（增强版 - 三合一工具）。

整合原 `get-process-top` + `cluster-comm` + `count-process-variety` 能力：
- **聚合视图**: 按进程名分组统计
- **离群检测**: CV变异系数识别异常PID
- **风暴检测**: Spawn Rate检测短生命周期进程
- **自动降噪**: 折叠高Count低CPU的背景组

```bash
spear get-comm-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--show-all] \
  [--comm <name>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 10 | 显示进程组数（已过滤噪音） |
| `--show-all` | flag | - | 显示所有组（包括被折叠的背景组） |
| `--comm` | string | - | 过滤指定进程名 |
| `--cv-threshold` | float | 1.0 | CV异常阈值 |
| `--monopoly-threshold` | float | 0.8 | 核心独占率阈值 |
| `--spawn-threshold` | float | 10.0 | 进程风暴阈值（个/秒） |

**输出字段**:
| 字段 | 说明 |
|------|------|
| `comm` | 进程名 |
| `total_cpu` | 聚合 CPU 利用率 |
| `count` | 进程数量 |
| `cv` | 变异系数（组内离散程度） |
| `monopoly` | 核心独占率（0-1） |
| `spawn_rate` | 进程产生速率（个/秒） |
| `impact_score` | 危害指数（排序依据） |
| `diagnosis` | 诊断标签: HEALTHY/UNBALANCED/BOTTLENECK/STORM |
| `outlier_pid` | 离群PID（CV异常时） |

**诊断标签说明**:
| 标签 | 条件 | 含义 |
|------|------|------|
| `HEALTHY` | CV低 + Monopoly低 | 负载均衡，正常 |
| `UNBALANCED` | CV高 | 组内进程负载不均，存在离群 |
| `BOTTLENECK` | Monopoly高 | 单点瓶颈，独占核心 |
| `STORM` | Spawn Rate高 | 短生命周期进程风暴 |

**自动降噪逻辑**:
以下组会被自动折叠（除非使用 `--show-all`）：
- Count > 100 且 Total_CPU < 5%
- CV < 0.1 且 Monopoly < 0.1（分布均匀无离群）

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
  [--min-ratio <pct>] \
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
  [--min-ratio <pct>] \
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
| `--min-ratio` | float | 0.5 | 最小占比阈值（%），低于此值的调用者被隐藏 |
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

## 组合诊断工具

### sys-audit

系统审计 - 自动扫描全景并识别真瓶颈（解决"亮眼数字掩盖真问题"）。

**链式触发**: `detect-anomalies` → `analyze-core-distribution` → `get-comm-top`

**核心能力**:
- 自动降噪：折叠高Count低CPU的背景进程
- 危害排序：按Impact Score排序，非单纯CPU%
- A/B分离：区分"背景负载(A)"和"真瓶颈(B)"

```bash
spear sys-audit \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--show-all] \
  [--start-time <ts>] \
  [--end-time <ts>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--top-n` | int | 10 | 显示关键进程组数 |
| `--show-all` | flag | - | 显示所有组（包括折叠的背景组） |

**输出结构**:
```
[系统审计报告]
1. 异常发现
   系统CPU在10:05突变+80%，Core #7单核饱和

2. 关键进程（按Impact Score排序）
   COMM           CPU%   Count   Monopoly   Diagnosis
   app_worker     12%    10      0.92!!     BOTTLENECK  ← 真凶
   lsof           400%   2000    0.05       HIGH_VOLUME ← 背景

3. 背景噪音（已折叠）
   24个组 | 总CPU: 15% | 状态: Quiet

4. 建议操作
   [CRITICAL] app_worker独占Core #7，建议执行: bottleneck-trace --comm app_worker
```

---

### bottleneck-trace

瓶颈追踪 - 深度分析被识别出的瓶颈进程。

**链式触发**: `get-comm-top` → `get-hotspots` → `cluster-paths`

**适用场景**: `sys-audit`发现高Monopoly进程，或手动指定目标进程

```bash
spear bottleneck-trace \
  --data <perf.script.txt> \
  [--comm <name>] \
  [--pid <PID>] \
  [--auto-detect] \
  [--top-n <N>]
```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--comm` | string | - | 目标进程名（与--auto-detect互斥） |
| `--pid` | int | - | 目标PID |
| `--auto-detect` | flag | - | 自动检测系统中的瓶颈进程 |
| `--top-n` | int | 10 | 显示热点数 |

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

### trace audit

**事后独立审计**：验证已完成诊断的 issues 分析质量。

审计员（Tech Lead / QA / 架构师）在诊断完成后独立运行，用于质量检查和团队学习。**不阻塞诊断流程**，发现问题不 reopen，而是反馈给工程师改进。

**审计检查项**：
- 结构完整性：result 非空、非敷衍（如 "ok", "done"）
- Timeline 关联：有分析命令支撑，无 analysis gap
- 分析深度：包含因果推导或文档引用

```bash
# 完整审计（诊断完成后运行）
spear trace audit

# 指定审计阶段
spear trace audit --phase structural  # 只检查结构
spear trace audit --phase timeline    # 只检查 timeline 关联
spear trace audit --phase depth       # 只检查分析深度

# JSON 输出（便于集成到质量平台）
spear trace audit --format json --output audit-report.json
```

**使用场景**：
```bash
# 场景 1: 定期质量审计
cd /path/to/completed/diagnosis
spear trace audit

# 场景 2: Code Review 时检查
# Reviewer 查看诊断质量
spear trace audit --format json | jq '.summary'

# 场景 3: 事后复盘
# 问题复现时检查历史诊断是否充分
spear trace audit --phase depth
```

**参考文档**：`docs/audit-process.md` - 完整审计流程指南

---

### trace finalize

结束诊断，准备生成报告。

检查是否还有 open issues。如有，可选择继续分析或接受风险后结束。**与 audit 完全独立**，不依赖审计结果。

```bash
# 结束诊断（所有 issues 已解决）
spear trace finalize

# 如有未处理 issues，但决定接受风险
spear trace finalize --accept-risk "与当前问题无关，可后续处理"
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
| `analyze-core-distribution` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `detect-anomalies` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `get-comm-top` | ✅ | ❌ | ✅ | ✅ | ✅ |
| `get-hotspots` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `find-callers` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-paths` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `sys-audit` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `bottleneck-trace` | ✅ | ✅ | ✅ | ❌ | ✅ |

**已删除工具的替代方案**:

| 原工具 | 替代方案 | 示例 |
|--------|----------|------|
| `check-cpu-bottleneck` | `analyze-core-distribution` | `spear analyze-core-distribution --cpu-limit 0.5c` |
| `get-process-top` | `get-comm-top`（增强版） | `spear get-comm-top`（自动显示离群PID） |
| `count-process-variety` | `get-comm-top` | `spear get-comm-top`（查看Spawn Rate列） |
| `cluster-symbols` | `cluster-paths` | `spear cluster-paths` |

---

## 参考文档

- 📗 **分析方法论**: [methodology.md](./methodology.md) - 三层架构驱动的完整方法论
- 📘 **典型分析模式**: [workflow-patterns.md](./workflow-patterns.md) - 5 种场景的速查路径
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
