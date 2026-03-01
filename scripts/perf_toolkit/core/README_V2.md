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
├── output_builder.py      # 输出构建器
└── README_V2.md          # 本文档
```

## 核心数据模型

### 基础类

```python
# 风险信息 - 所有输出的第一个字段
@dataclass
class RiskInfo:
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False

# 时间范围 - ISO 8601 格式
@dataclass
class TimeRange:
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: float = 0.0  # seconds
```

### 数据项类

```python
# 进程数据项 - get-process-top
@dataclass
class ProcessItem:
    comm: str
    pid: int
    cpu_pct: str  # "45.5%"
    kernel_pct: str  # "12.3%"
    
    @classmethod
    def from_stats(cls, comm: str, pid: int, cpu_util: float, kernel_ratio: float) -> 'ProcessItem':
        return cls(
            comm=comm, pid=pid,
            cpu_pct=f"{cpu_util:.2f}%",
            kernel_pct=f"{kernel_ratio:.2f}%"
        )

# 进程组数据项 - get-comm-top / cluster-comm (共享)
@dataclass
class CommGroupItem:
    comm: str
    pids: int
    cpu: str  # "243.87%"
    kernel: str  # "94.7%"
    event: str = "normal"
    
    @classmethod
    def from_stats(cls, comm: str, pid_count: int, aggregate_cpu: float,
                   kernel_ratio: float, event_desc: str = "normal") -> 'CommGroupItem':
        return cls(
            comm=comm, pids=pid_count,
            cpu=f"{aggregate_cpu:.2f}%",
            kernel=f"{kernel_ratio:.2f}%",
            event=event_desc
        )

# 热点函数数据项 - get-hotspots
@dataclass
class HotspotItem:
    symbol: str
    self: str  # "15.23%"
    inclusive: str  # "45.67%"
    
    @classmethod
    def from_stats(cls, symbol: str, self_pct: float, inclusive_pct: float) -> 'HotspotItem':
        return cls(
            symbol=symbol,
            self=f"{self_pct:.2f}%",
            inclusive=f"{inclusive_pct:.2f}%"
        )

# 聚类数据项 - cluster-symbols
@dataclass
class ClusterItem:
    cluster: str
    ratio_pct: str  # "79.84%"
    core_sec: float  # 98.7654
    
    @classmethod
    def from_stats(cls, cluster: str, ratio: float, core_sec: float) -> 'ClusterItem':
        return cls(
            cluster=cluster,
            ratio_pct=f"{ratio:.2f}%",
            core_sec=round(core_sec, 4)
        )
```

### 摘要类

```python
@dataclass
class ProcessSummary:
    total_processes: int = 0
    shown_processes: int = 0

@dataclass
class CommGroupSummary:
    total_comm_groups: int = 0
    high_kernel_groups: int = 0

@dataclass
class HotspotSummary:
    total_hotspots: int = 0

@dataclass
class ClusterSummary:
    clusters_found: int = 0
    total_core_seconds: float = 0.0
```

### 输出根类

```python
@dataclass
class BaseOutput:
    _risk: RiskInfo
    summary: Optional[BaseSummary] = None
    time_range: Optional[TimeRange] = None

@dataclass
class ProcessTopOutput(BaseOutput):
    processes: List[ProcessItem] = field(default_factory=list)

@dataclass
class CommTopOutput(BaseOutput):
    comm_groups: List[CommGroupItem] = field(default_factory=list)

@dataclass
class ClusterCommOutput(BaseOutput):
    comm_groups: List[CommGroupItem] = field(default_factory=list)

@dataclass
class HotspotsOutput(BaseOutput):
    hotspots: List[HotspotItem] = field(default_factory=list)

@dataclass
class ClustersOutput(BaseOutput):
    clusters: List[ClusterItem] = field(default_factory=list)
```

## 使用示例

### 基本用法

```python
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    ProcessItem, ProcessSummary, ProcessTopOutput, TimeRange
)

def cmd_my_tool(engine, args):
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(...)
    if builder.check_empty_samples(samples):
        return
    
    builder.assess_quality(samples)
    
    # Process data and create items
    items = []
    for sample in samples:
        # ... process logic ...
        items.append(ProcessItem.from_stats(comm, pid, cpu_util, kernel_ratio))
    
    # Sort and limit
    items.sort(key=lambda x: float(x.cpu_pct.rstrip('%')), reverse=True)
    top_items = items[:args.top_n]
    
    # Build output
    risk = create_risk_info(level="none")
    summary = ProcessSummary(total_processes=len(items), shown_processes=len(top_items))
    time_range = TimeRange.from_timestamps(start_ts, end_ts)
    
    output = ProcessTopOutput(
        _risk=risk,
        processes=top_items,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
```

### 共享数据结构

`processes` 和 `comm_groups` 现在使用统一的数据结构：

```python
# process_top.py
from ..core.output_models import ProcessItem, ProcessSummary, ProcessTopOutput

# comm_top.py 和 comm_clusters.py
from ..core.output_models import CommGroupItem, CommGroupSummary, CommTopOutput, ClusterCommOutput

# 两者共享相同的数据项定义，但使用不同的输出结构
```

## 迁移检查清单

迁移现有模块到 V2 系统时：

- [ ] 导入 `OutputBuilder` 和 `create_risk_info`
- [ ] 导入对应的数据模型类（Item, Summary, Output）
- [ ] 使用 `ProcessItem.from_stats()` 等类方法创建数据项
- [ ] 使用 `create_risk_info()` 创建风险信息
- [ ] 使用 `builder.print_output(output)` 输出结果
- [ ] 测试输出 JSON 格式与之前一致

## 注意事项

1. **兼容性**: V2 系统的 JSON 输出与 V1 完全兼容，工具使用方无需修改
2. **渐进迁移**: 可以逐个模块迁移，V1 和 V2 可以共存
3. **类型检查**: 使用 mypy 等工具可以获得类型检查支持
4. **性能**: dataclass 的性能开销极小，可以忽略不计
