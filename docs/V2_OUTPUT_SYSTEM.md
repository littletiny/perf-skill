# V2 Output System 快速参考

## 概述

V2 Output System 提供了统一的数据结构来管理所有分析工具的输出，解决了以下问题：

1. **代码重复**: 统一数据结构定义，避免重复
2. **类型不安全**: 使用 `@dataclass` 提供类型安全
3. **JSON 直接输出**: 通过 adapter 转换，便于扩展
4. **统一管理**: 输出格式规范易于维护

## 文件结构

```
scripts/perf_toolkit/core/
├── output_models.py       # 数据模型定义
├── output_adapter.py      # JSON 转换器
├── output_builder_v2.py   # 输出构建器
├── README_V2.md          # 详细文档
└── __init__.py           # 导出 V2 模块

docs/
├── V2_OUTPUT_SYSTEM.md   # 本文件（快速参考）
└── CHANGES.md            # 变更记录
```

## 统一的数据结构

### processes (get-process-top)

```python
from perf_toolkit.core import ProcessItem, ProcessSummary, ProcessTopOutput

# 创建数据项
item = ProcessItem.from_stats("nginx", 12345, 45.5, 12.3)
# 输出: {"comm": "nginx", "pid": 12345, "cpu_pct": "45.50%", "kernel_pct": "12.30%"}

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
    OutputBuilderV2, create_risk_info,
    ProcessItem, ProcessSummary, ProcessTopOutput, TimeRange
)
```

### 2. 创建输出构建器

```python
builder = OutputBuilderV2(engine, args)
```

### 3. 创建数据项

```python
items = []
for sample in samples:
    # 处理逻辑...
    items.append(ProcessItem.from_stats(comm, pid, cpu_util, kernel_ratio))
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

## 与 V1 的兼容性

- V2 系统的 JSON 输出与 V1 完全兼容
- 所有字段名称和类型保持一致
- 可以逐个模块迁移，V1 和 V2 可以共存

## 更多信息

- 详细文档: `scripts/perf_toolkit/core/README_V2.md`
- 修改记录: `docs/CHANGES.md`
- 输出格式规范: `docs/output-format-spec.md`
