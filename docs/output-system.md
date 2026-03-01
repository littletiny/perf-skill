# Output System 快速参考

## 概述

Output System 提供了统一的数据结构来管理所有分析工具的输出：

1. **代码复用**: 统一数据结构定义
2. **类型安全**: 使用 `@dataclass` 提供类型检查
3. **格式统一**: 通过 adapter 转换，便于扩展
4. **易于维护**: 输出格式规范集中管理

## 文件结构

```
scripts/perf_toolkit/core/
├── output_models.py       # 数据模型定义
├── output_adapter.py      # JSON 转换器
├── output_builder.py      # 输出构建器
├── risk_mixin.py         # 风险信息管理
├── trace.py              # Trace 支持
└── __init__.py           # 导出模块

docs/
├── output-system.md      # 本文件（快速参考）
└── CHANGES.md            # 变更记录
```

## 统一的数据结构

### processes (get-process-top)

```python
from perf_toolkit.core import ProcessItem, ProcessSummary, ProcessTopOutput

# 创建数据项
item = ProcessItem.from_cpu_util("nginx", 12345, 45.5, 12.3)
# 输出: {"comm": "nginx", "pid": 12345, "total_cpu_util": "45.50%", "kernel_cpu_util": "12.30%"}

# 创建输出
output = ProcessTopOutput(
    _risk=risk,
    processes=[item],
    summary=ProcessSummary(total_processes=10, shown_processes=1),
    time_range=time_range
)
```

### comm_groups (get-comm-top / cluster-comm)

```python
from perf_toolkit.core import CommGroupItem, CommGroupSummary, CommTopOutput, ClusterCommOutput

# 创建数据项（两个工具共享相同的 CommGroupItem）
item = CommGroupItem.from_stats("worker", 100, 150.0, 60.0, "HIGH_KERNEL: 60%")
# 输出: {"comm": "worker", "pids": 100, "cpu": "150.00%", "kernel": "60.00%", "event": "HIGH_KERNEL: 60%"}

# get-comm-top 使用 CommTopOutput
comm_output = CommTopOutput(
    _risk=risk,
    comm_groups=[item],
    summary=CommGroupSummary(total_comm_groups=5, high_kernel_groups=1),
    time_range=time_range
)

# cluster-comm 使用 ClusterCommOutput（相同的数据结构）
cluster_output = ClusterCommOutput(
    _risk=risk,
    comm_groups=[item],  # 相同的 CommGroupItem
    summary=CommGroupSummary(total_comm_groups=5, high_kernel_groups=0),
    time_range=time_range
)
```

## 快速开始

### 1. 导入所需模块

```python
from perf_toolkit.core import (
    OutputBuilder, create_risk_info,
    ProcessItem, ProcessSummary, ProcessTopOutput, TimeRange
)
```

### 2. 创建输出构建器

```python
builder = OutputBuilder(engine, args)
```

### 3. 创建数据项

```python
items = []
for sample in samples:
    # 处理逻辑...
    items.append(ProcessItem.from_cpu_util(comm, pid, cpu_util, kernel_ratio))
```

### 4. 构建输出

```python
output = ProcessTopOutput(
    _risk=create_risk_info(level="none"),
    processes=items,
    summary=ProcessSummary(total_processes=10, shown_processes=5),
    time_range=TimeRange.from_timestamps(start_ts, end_ts)
)
```

### 5. 打印输出

```python
builder.print_output(output)
```

## 类型注册表

```python
from perf_toolkit.core import OUTPUT_TYPE_MAP, get_output_classes

# 获取数据类型对应的类
item_cls, summary_cls, output_cls = get_output_classes('processes')
# 返回: (ProcessItem, ProcessSummary, ProcessTopOutput)

item_cls, summary_cls, output_cls = get_output_classes('comm_groups')
# 返回: (CommGroupItem, CommGroupSummary, CommTopOutput)
```

## 数据结构概览

所有分析工具使用统一的数据模型：
- **RiskInfo**: 风险提示信息
- **TimeRange**: 时间范围
- **Data Items**: 具体数据项（ProcessItem, HotspotItem 等）
- **Summary**: 统计摘要
- **Output**: 根输出结构

## 更多信息

- 修改记录: `docs/CHANGES.md`
- 输出格式规范: `docs/output-format-spec.md`
