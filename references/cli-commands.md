# CLI Commands Reference

> perf-hunter 命令行工具完整参考手册。包含所有子命令的详细参数说明和使用示例。
> 
> 分析策略和方法论请查阅 [methodology.md](./methodology.md)。

---

## 目录

- [命令概览](#命令概览)
- [Analysis Commands](#analysis-commands)
- [Composite Commands](#composite-commands)
- [Trace Commands](#trace-commands)
- [通用参数参考](#通用参数参考)
- [命令注册架构](#命令注册架构)

---

## 命令概览

### 命令分类统计

| 类别 | 数量 | 位置 |
|------|------|------|
| Analysis Commands | 6 | `scripts/perf_toolkit/cli/commands/analysis/` |
| Composite Commands | 2 | `scripts/perf_toolkit/cli/commands/composite/` |
| Trace Commands | 9 | `scripts/perf_toolkit/cli/commands/trace/` |

### 快速命令索引

| 命令 | 类别 | 用途 |
|------|------|------|
| `get-hotspots` | Analysis | 热点函数识别 |
| `find-callers` | Analysis | 热点函数溯源 |
| `detect-anomalies` | Analysis | 时序异常检测 |
| `cluster-paths` | Analysis | 调用路径聚类 |
| `analyze-core-distribution` | Analysis | 核心负载分布分析 |
| `get-comm-top` | Analysis | 进程组资源分析 |
| `sys-audit` | Composite | 系统全景扫描 |
| `bottleneck-trace` | Composite | 瓶颈深度追踪 |
| `trace` | Trace | 问题追踪管理 |

---

## Analysis Commands

> 位置：`scripts/perf_toolkit/cli/commands/analysis/`

### get-hotspots

热点函数识别。按 self/inclusive 时间提取热点函数排名。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/hotspots.py`
- 函数：`cmd_get_hotspots`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--sort-by` | - | self | 排序方式：`inclusive` 或 `self` |
| `--top-n`, `--limit` | - | 10 | 显示热点数量 |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--pid` | - | - | 按进程 ID 过滤 |
| `--comm` | - | - | 按进程名过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本（ISO 8601） |
| `--end-time` | - | - | 过滤此时间之前的样本（ISO 8601） |

**示例**

```bash
# 基础使用
shecr get-hotspots --data perf.data.txt

# 按 inclusive 排序，显示前20个
shecr get-hotspots --data perf.data.txt --sort-by inclusive --top-n 20

# 分析特定进程
shecr get-hotspots --data perf.data.txt --comm myapp --pid 1234
```

---

### find-callers

Bottom-up 热点函数溯源。追踪特定函数的调用者链。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/callers.py`
- 函数：`cmd_trace_attribution`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--target` | - | - | 目标函数名（与 `--auto-target` 二选一） |
| `--auto-target` | - | False | 自动追踪 Top N 热点函数 |
| `--top-n`, `--limit` | - | 10 | 返回结果数量 |
| `--min-ratio` | - | 0.5 | 最小占比阈值（%） |
| `--max-depth` | - | 0 | 最大调用链深度（0=无限制） |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--pid` | - | - | 按进程 ID 过滤 |
| `--comm` | - | - | 按进程名过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 追踪特定函数的调用者
shecr find-callers --data perf.data.txt --target pthread_mutex_lock

# 自动追踪热点（类似 perf top）
shecr find-callers --data perf.data.txt --auto-target --top-n 5

# 限制调用链深度
shecr find-callers --data perf.data.txt --target main --max-depth 10
```

---

### detect-anomalies

时序异常检测。识别 CPU 利用率突变点。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/anomalies.py`
- 函数：`cmd_detect_anomalies`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--window-size` | - | 1.0 | 滑动窗口大小（秒） |
| `--spike-threshold` | - | 0.5 | 突变检测阈值（倍数） |
| `--min-utilization` | - | 0.3 | 最小利用率阈值 |
| `--top-n`, `--limit` | - | 10 | 显示异常数量 |
| `--cpu-id` | - | - | 分析特定 CPU |
| `--pid` | - | - | 按进程 ID 过滤 |
| `--comm` | - | - | 按进程名过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--export-mode` | - | False | 导出所有窗口数据 |
| `--export-samples` | - | False | 包含详细样本数据 |
| `--detect-in-export` | - | False | 在导出模式下检测异常 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 基础异常检测
shecr detect-anomalies --data perf.data.txt

# 自定义窗口和阈值
shecr detect-anomalies --data perf.data.txt --window-size 2.0 --spike-threshold 0.8

# 分析特定 CPU 的异常
shecr detect-anomalies --data perf.data.txt --cpu-id 0
```

---

### cluster-paths

调用路径聚类。按共同调用路径前缀对样本进行聚类。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/path_clusters.py`
- 函数：`cmd_cluster_paths`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--min-depth` | - | 2 | 最小共同前缀深度 |
| `--min-samples` | - | 5 | 形成聚类的最小样本数 |
| `--top-n`, `--limit` | - | 10 | 显示聚类数量 |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--pid` | - | - | 按进程 ID 过滤 |
| `--comm` | - | - | 按进程名过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 基础聚类
shecr cluster-paths --data perf.data.txt

# 调整聚类参数
shecr cluster-paths --data perf.data.txt --min-depth 3 --min-samples 10
```

---

### analyze-core-distribution

核心负载分布分析。检测单核饱和、负载不均衡。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/core_dist.py`
- 函数：`cmd_analyze_core_distribution`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--top-n`, `--limit` | - | 10 | 显示高负载核心数量 |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--pid` | - | - | 按进程 ID 过滤 |
| `--comm` | - | - | 按进程名过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 分析核心负载分布
shecr analyze-core-distribution --data perf.data.txt

# 分析特定进程的核心分布
shecr analyze-core-distribution --data perf.data.txt --comm myapp
```

---

### get-comm-top

进程组资源分析。识别离群进程，计算 CV/Monopoly 指标。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/analysis/comm_top.py`
- 函数：`cmd_get_comm_top`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--top-n`, `--limit` | - | 10 | 显示进程组数量 |
| `--sort-by-density` | - | False | 按密度指数排序 |
| `--include-metrics` | - | False | 包含增强指标（CV/Monopoly/SpawnRate/ImpactScore） |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--comm-regex` | - | - | 按进程名正则过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 基础进程组分析
shecr get-comm-top --data perf.data.txt

# 包含增强指标
shecr get-comm-top --data perf.data.txt --include-metrics
```

---

## Composite Commands

> 位置：`scripts/perf_toolkit/cli/commands/composite/`

### sys-audit

系统全景扫描。自动编排多个分析工具，生成综合诊断报告。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/composite/sys_audit.py`
- 函数：`cmd_sys_audit`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--top-n`, `--limit` | - | 20 | 显示进程组数量 |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 系统全景扫描
shecr sys-audit --data perf.data.txt

# 显示更多进程
shecr sys-audit --data perf.data.txt --top-n 30
```

---

### bottleneck-trace

瓶颈深度追踪。通过多维度聚合分析（Bottom-Up + Top-Down 双视角），定位 CPU 瓶颈根因。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/composite/bottleneck_trace.py`
- 函数：`cmd_bottleneck_trace`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf script 输出文件路径 |
| `--freq` | - | 19 | 采样频率（Hz） |
| `--comm` | - | - | 目标进程名（可选，未指定时自动识别） |
| `--pid` | - | - | 目标进程 PID（可选） |
| `--top-n`, `--limit` | - | 3 | 双向视图中显示路径数（其余聚合） |
| `--cpu-id` | - | - | 按 CPU ID 过滤 |
| `--start-time` | - | - | 过滤此时间之后的样本 |
| `--end-time` | - | - | 过滤此时间之前的样本 |

**示例**

```bash
# 自动识别并追踪瓶颈
shecr bottleneck-trace --data perf.data.txt

# 追踪指定进程
shecr bottleneck-trace --data perf.data.txt --comm myapp

# 通过 PID 追踪
shecr bottleneck-trace --data perf.data.txt --pid 1234
```

---

## Trace Commands

> 位置：`scripts/perf_toolkit/cli/commands/trace/`

Trace 命令用于问题追踪：记录诊断过程中的发现和结论。

### trace init

初始化诊断文档。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/init.py`
- 函数：`cmd_doc_init`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--data` | ✅ | - | perf 数据文件路径 |
| `--path` | - | .shecr.json | 文档存储路径 |

**示例**

```bash
shecr trace init --data perf.data
```

---

### trace add

手动添加 issue。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/add.py`
- 函数：`cmd_doc_add`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--desc` | ✅ | - | 问题描述 |
| `--level` | - | warning | 级别：`critical` / `warning` / `info` |
| `--risk` | - | - | 不处理的风险 |
| `--hint` | - | - | 建议操作 |

**示例**

```bash
shecr trace add --desc "CPU异常高" --level critical --hint "执行热点分析"
```

---

### trace timeline

查看诊断时间线。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/timeline.py`
- 函数：`cmd_doc_timeline`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--format` | - | text | 格式：`text` / `json` |
| `--risk-config` | - | - | Risk 显示配置文件路径 |
| `--risk-style` | - | - | Risk 样式：`default` / `ci` / `compact` |

**示例**

```bash
shecr trace timeline
shecr trace timeline --format json
```

---

### trace issues

查看 issues 列表。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/issues.py`
- 函数：`cmd_doc_issues`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--status` | - | all | 状态过滤：`open` / `resolved` / `all` |
| `--risk-config` | - | - | Risk 显示配置文件路径 |
| `--risk-style` | - | - | Risk 样式：`default` / `ci` / `compact` |

**示例**

```bash
shecr trace issues
shecr trace issues --status open
```

---

### trace complete

标记 issue 为已完成。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/complete.py`
- 函数：`cmd_doc_complete`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--id` | ✅ | - | Issue 标识符 |
| `--result` | ✅ | - | 分析结果 |

**示例**

```bash
shecr trace complete --id ISS-001 --result "根因：锁竞争，建议优化"
```

---

### trace reopen

重新打开已解决的 issue。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/reopen.py`
- 函数：`cmd_doc_reopen`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--id` | - | - | Issue 标识符（与 `--all` 二选一） |
| `--all` | - | False | 重新打开所有已解决的 issues |
| `--reason` | - | - | 重新打开原因 |

**示例**

```bash
# 重新打开单个 issue
shecr trace reopen --id ISS-001 --reason "发现新问题"

# 重新打开所有
shecr trace reopen --all
```

---

### trace finalize

最终审计，确认是否可以生成报告。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/finalize.py`
- 函数：`cmd_doc_finalize`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--accept-risk` | - | - | 接受剩余风险的原因 |
| `--format` | - | text | 格式：`text` / `json` |
| `--risk-config` | - | - | Risk 显示配置文件路径 |
| `--risk-style` | - | - | Risk 样式：`default` / `ci` / `compact` |

**示例**

```bash
# 检查是否可结束诊断
shecr trace finalize

# 接受风险并结束
shecr trace finalize --accept-risk "已评估，风险可接受"
```

---

### trace export

导出报告为其他格式。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/export.py`
- 函数：`cmd_doc_export`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--format` | - | markdown | 格式：`markdown` / `json` |
| `--output` | - | stdout | 输出文件路径 |

**示例**

```bash
# 导出为 Markdown
shecr trace export --format markdown --output report.md

# 导出为 JSON
shecr trace export --format json --output report.json
```

---

### trace audit

审计 resolved issues 的分析质量。

**源码信息**
- 文件：`scripts/perf_toolkit/cli/commands/trace/audit.py`
- 函数：`cmd_doc_audit`

**参数列表**

| 参数名 | 必需 | 默认值 | 说明 |
|--------|:----:|--------|------|
| `--phase` | - | all | 审计阶段：`all` / `structural` / `timeline` / `depth` |
| `--format` | - | text | 格式：`text` / `json` |
| `--output` | - | - | 输出文件路径 |
| `--no-fail` | - | False | 失败时不以错误码退出 |
| `--risk-config` | - | - | Risk 显示配置文件路径 |
| `--risk-style` | - | - | Risk 样式：`default` / `ci` / `compact` |

**示例**

```bash
# 完整审计
shecr trace audit

# 仅结构检查
shecr trace audit --phase structural

# 导出审计报告
shecr trace audit --format json --output audit.json
```

---

## 通用参数参考

### 数据过滤参数

以下参数在多个命令中通用，用于过滤 perf 样本数据：

| 参数名 | 适用命令 | 说明 |
|--------|----------|------|
| `--data` | 所有 Analysis/Composite | perf script 输出文件路径 |
| `--freq` | 所有 Analysis/Composite | 采样频率（Hz） |
| `--cpu-id` | 除 `bottleneck-trace` 外大部分 | 按 CPU ID 过滤 |
| `--pid` | `get-hotspots`, `find-callers`, `cluster-paths`, `analyze-core-distribution`, `bottleneck-trace` | 按进程 ID 过滤 |
| `--comm` | `get-hotspots`, `find-callers`, `detect-anomalies`, `cluster-paths`, `analyze-core-distribution`, `bottleneck-trace` | 按进程名过滤 |
| `--comm-regex` | 大部分 Analysis | 按进程名正则过滤 |
| `--start-time` | 大部分 | 按起始时间过滤（ISO 8601） |
| `--end-time` | 大部分 | 按结束时间过滤（ISO 8601） |

### 输出控制参数

| 参数名 | 适用命令 | 说明 |
|--------|----------|------|
| `--top-n`, `--limit` | 大部分 | 显示结果数量 |
| `--format` | Trace 命令 | 输出格式：`text` / `json` |
| `--output` | `trace export`, `trace audit` | 输出文件路径 |
| `--risk-config` | Trace 命令 | Risk 显示配置文件 |
| `--risk-style` | Trace 命令 | Risk 样式：`default` / `ci` / `compact` |

### 参数矩阵

| 命令 | `--cpu-id` | `--pid` | `--comm` | `--comm-regex` | `--start-time` | `--end-time` |
|------|:----------:|:-------:|:--------:|:--------------:|:--------------:|:------------:|
| `get-hotspots` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `find-callers` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `detect-anomalies` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-paths` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `analyze-core-distribution` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `get-comm-top` | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `sys-audit` | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `bottleneck-trace` | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

---

## 命令注册架构

### 主解析器

**文件**：`scripts/perf_toolkit/cli/main.py`

主解析器负责注册所有子命令并路由到对应处理函数：

```python
def create_parser() -> argparse.ArgumentParser:
    # 注册 Analysis 命令（6个）
    from .commands.analysis import register_commands as register_analysis_commands
    register_analysis_commands(subparsers)
    
    # 注册 Composite 命令（2个）
    from .commands.composite import register_commands as register_composite_commands
    register_composite_commands(subparsers)
    
    # 注册 Trace 命令（9个子命令）
    register_trace_commands(subparsers)
```

### Analysis 命令注册

**文件**：`scripts/perf_toolkit/cli/commands/analysis/__init__.py`

```python
COMMAND_MAP = {
    'get-hotspots': 'perf_toolkit.cli.commands.analysis.hotspots',
    'find-callers': 'perf_toolkit.cli.commands.analysis.callers',
    'detect-anomalies': 'perf_toolkit.cli.commands.analysis.anomalies',
    'cluster-paths': 'perf_toolkit.cli.commands.analysis.path_clusters',
    'analyze-core-distribution': 'perf_toolkit.cli.commands.analysis.core_dist',
    'get-comm-top': 'perf_toolkit.cli.commands.analysis.comm_top',
}
```

### Composite 命令注册

**文件**：`scripts/perf_toolkit/cli/commands/composite/__init__.py`

```python
COMMAND_MAP = {
    'sys-audit': 'perf_toolkit.cli.commands.composite.sys_audit',
    'bottleneck-trace': 'perf_toolkit.cli.commands.composite.bottleneck_trace',
}
```

### Trace 命令注册

**文件**：`scripts/perf_toolkit/cli/main.py` -> `register_trace_commands()`

```python
def register_trace_commands(subparsers):
    trace_parser = subparsers.add_parser('trace', help='Tracing commands')
    trace_sub = trace_parser.add_subparsers(dest='trace_cmd')
    
    # 注册 9 个子命令
    register_init_parser(trace_sub)
    register_add_parser(trace_sub)
    register_timeline_parser(trace_sub)
    register_issues_parser(trace_sub)
    register_complete_parser(trace_sub)
    register_reopen_parser(trace_sub)
    register_finalize_parser(trace_sub)
    register_export_parser(trace_sub)
    register_audit_parser(trace_sub)
```

---

## 相关文档

- **分析方法论**: [methodology.md](./methodology.md) - 三层架构驱动的完整方法论
- **工具速查**: [tools.md](./tools.md) - 命令速查和典型场景
- **数据格式**: [data-format.md](./data-format.md) - 输入数据格式规范
