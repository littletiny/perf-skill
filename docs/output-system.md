# Output System 快速参考

## 概述

Output System 提供了统一的数据结构来管理所有分析工具的输出：

1. **代码复用**: 统一数据结构定义（`output_models.py`）
2. **类型安全**: 使用 `@dataclass` 提供类型检查
3. **格式统一**: 通过 adapter 转换，便于扩展
4. **渲染分离**: 显示格式通过 `display_presets.py` 集中管理

## 文件结构

```
scripts/perf_toolkit/core/
├── output_models.py       # 数据模型定义（ dataclass ）
├── output_adapter.py      # JSON 转换器
├── text_output_adapter.py # 文本输出转换器
├── output_builder.py      # 输出构建器
├── display_presets.py     # 显示配置预设
├── risk_mixin.py          # 风险信息标准化
├── format_utils.py        # 时间/格式工具
└── __init__.py            # 导出模块

docs/
├── output-format-spec.md  # 输出格式规范（详细文档）
└── output-system.md       # 本文件（快速参考）
```

## 统一的数据结构

### RiskInfo - 风险信息

所有输出的第一个字段，遵循统一规范：

```python
from perf_toolkit.core import RiskInfo

risk = RiskInfo(
    level="warning",              # "critical" | "warning" | "info" | "none"
    message="发现性能瓶颈",        # 简短描述
    hint="执行: bottleneck-trace --comm xxx",  # 建议操作
    patterns=["BOTTLENECK"],      # 检测到的模式
    pending_targets=["xxx"],      # 待处理目标
    action_required=True          # 是否需要处理（level为critical/warning时自动为true）
)
```

### TimeRange - 时间范围

```python
from perf_toolkit.core import TimeRange

# 从时间戳创建（自动转换为 ISO 8601 格式）
time_range = TimeRange.from_timestamps(start_ts, end_ts)
# 输出: {"start_time": "2026-03-02T10:00:00", "end_time": "2026-03-02T10:30:00", "duration": 1800}
```

### 数据项创建

#### ProcessItem（进程数据）

```python
from perf_toolkit.core import ProcessItem

item = ProcessItem.from_cpu_util("nginx", 12345, 45.5, 12.3)
# 输出: {"comm": "nginx", "pid": 12345, "total_cpu_util": "45.50%", "kernel_cpu_util": "12.30%"}
```

#### CommGroupItem（进程组数据）

```python
from perf_toolkit.core import CommGroupItem

item = CommGroupItem.from_stats(
    comm="worker",
    pid_count=100,
    aggregate_cpu=150.0,
    kernel_ratio=60.0,
    event_desc="HIGH_KERNEL: 60%"
)
# 输出: {"comm": "worker", "pids": 100, "cpu": "150.00%", "kernel": "60.00%", "event": "HIGH_KERNEL: 60%"}
```

#### HotspotItem（热点函数）

```python
from perf_toolkit.core import HotspotItem

item = HotspotItem.from_stats("func_name_[k]", 15.23, 45.67)
# 输出: {"symbol": "func_name_[k]", "self": "15.23%", "inclusive": "45.67%"}
```

#### PathClusterItem（路径聚类）

```python
from perf_toolkit.core import PathClusterItem

item = PathClusterItem.from_raw(
    cluster_id="c_001",
    path_signature="main→worker_loop→process_request",
    weight=45.67,
    total_weight=100.0,
    duration=1800
)
# 存储原始权重，百分比由模板计算
```

#### AnomalyItem（异常检测）

```python
from perf_toolkit.core import AnomalyItem

item = AnomalyItem.from_raw(
    type="SPIKE",
    cpu_id=5,
    start="2026-03-02T10:15:00",
    end="2026-03-02T10:16:00",
    prev=0.1,
    curr=0.85,
    next=0.15,
    z_score=2.8
)
```

### 输出构建

#### get-comm-top 输出示例

```python
from perf_toolkit.core import (
    RiskInfo, CommGroupItem, CommGroupSummary, 
    CommTopOutput, TimeRange, create_risk_info
)

# 创建数据项
groups = [
    CommGroupItem.from_stats("worker", 100, 150.0, 60.0, "HIGH_KERNEL"),
    CommGroupItem.from_stats("nginx", 4, 45.5, 12.3, "normal"),
]

# 创建输出
output = CommTopOutput(
    _risk=create_risk_info(level="warning"),
    comm_groups=groups,
    summary=CommGroupSummary(total_comm_groups=5, high_kernel_groups=1),
    time_range=TimeRange.from_timestamps(start_ts, end_ts)
)
```

#### analyze-core-distribution 输出示例

```python
from perf_toolkit.core import (
    RiskInfo, CoreItem, CoreDistributionOutput, 
    CoreDistributionSummary, TimeRange
)

cores = [
    CoreItem(cpu_id=5, total_cpu_util="95.20%", kernel_cpu_util="55.30%"),
    CoreItem(cpu_id=0, total_cpu_util="25.10%", kernel_cpu_util="10.50%"),
]

output = CoreDistributionOutput(
    _risk=RiskInfo(
        level="warning",
        message="单核满载 (CPU 5)",
        hint="使用 sys-audit 分析负载分布",
        patterns=["SINGLE_CORE_SATURATION"],
        pending_targets=["cpu_5"],
        action_required=True
    ),
    cores=cores,
    summary=CoreDistributionSummary(
        imbalance_level="CRITICAL",
        max_utilization="95.20%",
        min_utilization="2.10%",
        saturated_cores=1
    ),
    time_range=TimeRange.from_timestamps(start_ts, end_ts)
)
```

## 快速开始

### 1. 导入所需模块

```python
from perf_toolkit.core import (
    OutputBuilder, create_risk_info,
    CommGroupItem, CommGroupSummary, CommTopOutput, TimeRange
)
```

### 2. 创建输出构建器

```python
builder = OutputBuilder(engine, args)
```

### 3. 创建数据项

```python
items = []
for group_data in groups_data:
    items.append(CommGroupItem.from_stats(
        comm=group_data["comm"],
        pid_count=group_data["pid_count"],
        aggregate_cpu=group_data["total_cpu"],
        kernel_ratio=group_data["kernel_ratio"],
        event_desc=group_data["event"]
    ))
```

### 4. 构建输出

```python
output = CommTopOutput(
    _risk=create_risk_info(level="none"),
    comm_groups=items,
    summary=CommGroupSummary(total_comm_groups=10, shown_processes=5),
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

item_cls, summary_cls, output_cls = get_output_classes('hotspots')
# 返回: (HotspotItem, HotspotSummary, HotspotsOutput)
```

## 数据结构概览

| 数据类型 | Item 类 | Summary 类 | Output 类 |
|---------|---------|-----------|-----------|
| processes | ProcessItem | ProcessSummary | ProcessTopOutput |
| comm_groups | CommGroupItem | CommGroupSummary | CommTopOutput |
| hotspots | HotspotItem | HotspotSummary | HotspotsOutput |
| symbol_clusters | ClusterItem | ClusterSummary | ClustersOutput |
| anomalies | AnomalyItem | AnomalySummary | AnomaliesOutput |
| path_clusters | PathClusterItem | PathClusterSummary | PathClustersOutput |
| attributions | AttributionItem | AttributionSummary | AttributionsOutput |
| cores | CoreItem | CoreDistributionSummary | CoreDistributionOutput |

## 显示预设配置

显示格式统一在 `display_presets.py` 中配置：

```python
# display_presets.py 示例
DISPLAY_PRESETS = {
    "comm_groups": {
        "template_type": "simple_list",
        "list_field": "comm_groups",
        "header": "Top Comm Groups",
        "display_fields": ["comm", "pids", "cpu", "kernel", "event"],
        "index_format": "{idx}. ",
        "empty_message": "No comm groups found",
        "total_field": "total_comm_groups",
        "shown_field": None,
    },
    "hotspots": {
        "template_type": "simple_list",
        "list_field": "hotspots",
        "header": "Hotspot Functions",
        "display_fields": ["symbol", "self", "inclusive"],
    },
    # ...
}
```

## 三层架构中的使用

### Core 层（output_models.py）

定义数据结构，不包含业务逻辑：

```python
@dataclass
class CommGroupItem:
    comm: str
    pids: int
    cpu: str
    kernel: str
    event: str = "normal"
```

### Analysis 层（如 comm_top.py）

构建输出对象：

```python
from ..core.output_models import CommTopOutput, CommGroupItem, CommGroupSummary

output = CommTopOutput(
    _risk=risk_info,
    comm_groups=groups,
    summary=CommGroupSummary(...),
    time_range=TimeRange.from_timestamps(...)
)
return output
```

### Composite 层（如 sys_audit.py）

组合多个 Analysis 结果：

```python
from ..core.output_models import SysAuditOutput

output = SysAuditOutput(
    _risk=aggregated_risk,
    diagnosis=diagnosis_dict,
    details=details_dict,
    time_range=time_range
)
return output
```

## 更多信息

- 输出格式规范: `docs/output-format-spec.md`
- 三层架构设计: `docs/design-three-tier-architecture.md`
