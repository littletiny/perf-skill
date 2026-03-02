#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output Models - Unified data structures for all analysis tool outputs

遵循 output-format-spec.md 规范：
- 所有数据结构在此统一定义
- 不直接使用 JSON，通过 adapter 转换为 JSON 输出
- 扁平优先，嵌套不超过 3 层
- 风险置顶，包含 _risk 字段
- 时间字符串化，使用 ISO 8601 格式

显示格式配置统一在 display_presets.py 中管理
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
from datetime import datetime

from .display_presets import get_display_preset


# =============================================================================
# Template Configuration
# =============================================================================

@dataclass
class TemplateConfig:
    """文本输出模板配置

    支持的模板类型:
    - simple_list: 带序号的简单列表, #index field1 field2 ...
    - key_value: 无序号键值对, key value1 value2 ...
    - table: 多字段表格
    - nested: 嵌套结构,有父项和子项
    - custom: 完全自定义格式

    截断提示配置:
    - total_field: summary 中总数字段名 (如 "total_hotspots")
    - shown_field: summary 中显示数字段名 (如 "shown_hotspots")
    - 两者都不为 None 时，会显示 "... N more items" 提示
    """
    template_type: str
    list_field: Optional[str] = None
    header: Optional[str] = None
    display_fields: List[str] = field(default_factory=list)
    index_format: Optional[str] = None
    custom_renderer: Optional[str] = None
    empty_message: Optional[str] = None
    # 截断提示配置
    total_field: Optional[str] = None
    shown_field: Optional[str] = None

    @classmethod
    def from_preset(cls, preset_name: str) -> 'TemplateConfig':
        """从 display_presets 加载配置"""
        preset = get_display_preset(preset_name)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_name}")
        return cls(**preset)


# =============================================================================
# Risk Data Structures
# =============================================================================

@dataclass
class RiskInfo:
    """风险信息结构 - 所有输出的第一个字段"""
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False

    def __post_init__(self):
        # Validate level
        valid_levels = ["critical", "warning", "info", "none"]
        if self.level not in valid_levels:
            self.level = "info"
        # Auto-calculate action_required
        self.action_required = self.level in ["critical", "warning"]


# =============================================================================
# Time Range Structure
# =============================================================================

@dataclass
class TimeRange:
    """时间范围结构 - ISO 8601 格式"""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: float = 0.0  # seconds

    @classmethod
    def from_timestamps(cls, start_ts: Optional[float], end_ts: Optional[float]) -> 'TimeRange':
        """从时间戳创建 TimeRange"""
        if start_ts is None or end_ts is None:
            return cls()
        return cls(
            start_time=datetime.fromtimestamp(start_ts).isoformat() if start_ts else None,
            end_time=datetime.fromtimestamp(end_ts).isoformat() if end_ts else None,
            duration=round(end_ts - start_ts, 2)
        )


# =============================================================================
# Summary Structures
# =============================================================================

@dataclass
class BaseSummary:
    """基础摘要结构"""
    pass


@dataclass
class ProcessSummary(BaseSummary):
    """进程统计摘要"""
    total_processes: int = 0
    shown_processes: int = 0


@dataclass
class CommGroupSummary(BaseSummary):
    """进程组统计摘要"""
    total_comm_groups: int = 0
    high_kernel_groups: int = 0


@dataclass
class HotspotSummary(BaseSummary):
    """热点函数摘要"""
    total_hotspots: int = 0
    shown_hotspots: int = 0


@dataclass
class ClusterSummary(BaseSummary):
    """聚类摘要"""
    clusters_found: int = 0
    shown_clusters: int = 0


@dataclass
class BottleneckSummary(BaseSummary):
    """瓶颈检测摘要"""
    pass


@dataclass
class CPUUsageSummary(BaseSummary):
    """CPU 使用率摘要"""
    pass


@dataclass
class AnomalySummary(BaseSummary):
    """异常检测摘要"""
    total_anomalies: int = 0
    spike_count: int = 0
    drop_count: int = 0


@dataclass
class WindowSummary(BaseSummary):
    """时间窗口摘要"""
    mode: str = "export"
    window_size_sec: int = 0
    export_samples: bool = False
    cpu_count: int = 0
    total_windows: int = 0


@dataclass
class AttributionSummary(BaseSummary):
    """调用归因摘要"""
    target: str = ""
    target_cpu_util: str = "0.00%"
    total_attributions: int = 0
    shown_attributions: int = 0


@dataclass
class TracesSummary(BaseSummary):
    """追踪热点摘要"""
    hotspots_traced: int = 0


@dataclass
class PathClusterSummary(BaseSummary):
    """路径聚类摘要"""
    total_clusters: int = 0
    shown_clusters: int = 0
    clustered_weight: float = 0.0


@dataclass
class ProcessVarietySummary(BaseSummary):
    """进程多样性摘要"""
    total_processes: int = 0
    storm_detected: bool = False
    storm_count: int = 0


@dataclass
class CoreDistributionSummary(BaseSummary):
    """核心分布摘要"""
    imbalance_level: str = "UNKNOWN"
    max_utilization: str = "0%"
    min_utilization: str = "0%"
    saturated_cores: int = 0


# =============================================================================
# Data Item Structures
# =============================================================================

@dataclass
class ProcessItem:
    """进程数据项 - 用于 get-process-top"""
    comm: str
    pid: int
    total_cpu_util: str
    kernel_cpu_util: str

    @classmethod
    def from_cpu_util(cls, comm: str, pid: int, total_cpu_util: float,
                      kernel_cpu_util: float) -> 'ProcessItem':
        """从 CPU utilization % 创建 ProcessItem"""
        return cls(
            comm=comm,
            pid=pid,
            total_cpu_util=f"{total_cpu_util:.2f}%",
            kernel_cpu_util=f"{kernel_cpu_util:.2f}%"
        )


@dataclass
class CommGroupItem:
    """进程组数据项 - 用于 get-comm-top 和 cluster-comm"""
    comm: str
    pids: int
    cpu: str
    kernel: str
    event: str = "normal"

    @classmethod
    def from_stats(cls, comm: str, pid_count: int, aggregate_cpu: float,
                   kernel_ratio: float, event_desc: str = "normal") -> 'CommGroupItem':
        """从统计数据创建 CommGroupItem"""
        return cls(
            comm=comm,
            pids=pid_count,
            cpu=f"{aggregate_cpu:.2f}%",
            kernel=f"{kernel_ratio:.2f}%",
            event=event_desc
        )


@dataclass
class HotspotItem:
    """热点函数数据项 - 用于 get-hotspots"""
    symbol: str
    self: str
    inclusive: str

    @classmethod
    def from_stats(cls, symbol: str, self_pct: float, inclusive_pct: float) -> 'HotspotItem':
        """从统计数据创建 HotspotItem"""
        return cls(
            symbol=symbol,
            self=f"{self_pct:.2f}%",
            inclusive=f"{inclusive_pct:.2f}%"
        )


@dataclass
class ClusterItem:
    """聚类数据项 - 用于 cluster-symbols"""
    cluster: str
    pct_of_total: str

    @classmethod
    def from_stats(cls, cluster: str, ratio: float) -> 'ClusterItem':
        """从统计数据创建 ClusterItem"""
        return cls(
            cluster=cluster,
            pct_of_total=f"{ratio:.2f}%"
        )


@dataclass
class CoreLoadInfo:
    """核心负载信息"""
    cpu_id: int
    load: str


@dataclass
class LimitInfo:
    """CPU 限制信息"""
    cpu_limit_cores: float
    cpu_limit_detected: bool


@dataclass
class BottleneckData:
    """瓶颈检测数据"""
    verdict: str
    events: List[str]
    high_cpu_cores: List[int]
    high_sys_cores: List[int]
    threshold: int
    max_core_load: CoreLoadInfo
    limit_info: LimitInfo


@dataclass
class CPUUtilizationBreakdown:
    """CPU 利用率分解"""
    total_pct: str
    user_pct: str
    kernel_pct: str


@dataclass
class CPUUsageData:
    """CPU 使用率数据"""
    target: str
    cpu_utilization: CPUUtilizationBreakdown


@dataclass
class AnomalyItem:
    """异常检测数据项 - 用于 detect-anomalies

    存储原始数据，格式由模板根据 preset 配置处理
    """
    type: str
    cpu_id: int
    time_range_start: str
    time_range_end: str
    prev_util: float
    curr_util: float
    next_util: float
    severity: str

    @classmethod
    def from_raw(cls, type: str, cpu_id: int, start: str, end: str,
                 prev: float, curr: float, next: float, z_score: float) -> 'AnomalyItem':
        """从原始数据创建 AnomalyItem"""
        severity = "high" if z_score > 2.5 else "medium"
        return cls(
            type=type,
            cpu_id=cpu_id,
            time_range_start=start,
            time_range_end=end,
            prev_util=prev,
            curr_util=curr,
            next_util=next,
            severity=severity
        )


@dataclass
class WindowItem:
    """时间窗口数据项 - 用于 detect-anomalies --export-mode"""
    cpu_id: int
    start_time: str
    end_time: str
    utilization: str
    weight: float


@dataclass
class AttributionItem:
    """调用归因数据项 - 用于 find-callers"""
    caller_stack: List[str]
    ratio_of_target_pct: str
    cpu_util: str


@dataclass
class TraceItem:
    """追踪热点数据项 - 用于 find-callers --auto"""
    target: str
    target_ratio_pct: str
    attributions: List[AttributionItem] = field(default_factory=list)


@dataclass
class PathClusterItem:
    """路径聚类数据项 - 用于 cluster-paths

    存储原始权重，百分比由模板根据 preset 配置计算和格式化
    """
    cluster_id: str
    path_signature: str
    weight: float
    total_weight: float
    duration: float

    @classmethod
    def from_raw(cls, cluster_id: str, path_signature: str, weight: float,
                 total_weight: float, duration: float) -> 'PathClusterItem':
        """从原始数据创建 PathClusterItem"""
        return cls(
            cluster_id=cluster_id,
            path_signature=path_signature,
            weight=weight,
            total_weight=total_weight,
            duration=duration
        )


@dataclass
class ProcessVarietyItem:
    """进程多样性数据项 - 用于 count-process-variety"""
    comm: str
    pids_per_min: int
    cpu_util: str
    behavior: str


@dataclass
class CoreItem:
    """核心分布数据项 - 用于 analyze-core-distribution"""
    cpu_id: int
    total_cpu_util: str
    kernel_cpu_util: str


# =============================================================================
# Output Root Structures
# =============================================================================

@dataclass
class BaseOutput:
    """基础输出结构 - 所有输出的基类"""
    _risk: RiskInfo
    summary: Optional[BaseSummary] = None
    time_range: Optional[TimeRange] = None
    _template_config: Optional[TemplateConfig] = None


@dataclass
class ProcessTopOutput(BaseOutput):
    """get-process-top 输出结构"""
    processes: List[ProcessItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, processes: List[ProcessItem],
                 summary: ProcessSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.processes = processes
        self._template_config = TemplateConfig.from_preset("processes")


@dataclass
class CommTopOutput(BaseOutput):
    """get-comm-top 输出结构"""
    comm_groups: List[CommGroupItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, comm_groups: List[CommGroupItem],
                 summary: CommGroupSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.comm_groups = comm_groups
        self._template_config = TemplateConfig.from_preset("comm_groups")


@dataclass
class ClusterCommOutput(BaseOutput):
    """cluster-comm 输出结构"""
    comm_groups: List[CommGroupItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, comm_groups: List[CommGroupItem],
                 summary: Optional[CommGroupSummary] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.comm_groups = comm_groups
        self._template_config = TemplateConfig.from_preset("comm_groups")


@dataclass
class HotspotsOutput(BaseOutput):
    """get-hotspots 输出结构"""
    hotspots: List[HotspotItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, hotspots: List[HotspotItem],
                 summary: HotspotSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.hotspots = hotspots
        self._template_config = TemplateConfig.from_preset("hotspots")


@dataclass
class ClustersOutput(BaseOutput):
    """cluster-symbols 输出结构"""
    symbol_clusters: List[ClusterItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, symbol_clusters: List[ClusterItem],
                 summary: ClusterSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.symbol_clusters = symbol_clusters
        self._template_config = TemplateConfig.from_preset("symbol_clusters")


@dataclass
class BottleneckOutput(BaseOutput):
    """check-cpu-bottleneck 输出结构"""
    data: BottleneckData = field(default_factory=dict)

    def __init__(self, _risk: RiskInfo, data: BottleneckData,
                 summary: BottleneckSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.data = data
        self._template_config = TemplateConfig.from_preset("bottleneck")


@dataclass
class CPUUsageOutput(BaseOutput):
    """show-cpu-usage 输出结构"""
    data: CPUUsageData = field(default_factory=dict)

    def __init__(self, _risk: RiskInfo, data: CPUUsageData,
                 summary: CPUUsageSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.data = data
        self._template_config = TemplateConfig.from_preset("cpu_usage")


@dataclass
class AnomaliesOutput(BaseOutput):
    """detect-anomalies 输出结构"""
    anomalies: List[AnomalyItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, anomalies: List[AnomalyItem],
                 summary: AnomalySummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.anomalies = anomalies
        self._template_config = TemplateConfig.from_preset("anomalies")


@dataclass
class WindowsOutput(BaseOutput):
    """detect-anomalies --export-mode 输出结构"""
    windows: List[WindowItem] = field(default_factory=list)
    statistics: Dict[str, str] = field(default_factory=dict)

    def __init__(self, _risk: RiskInfo, windows: List[WindowItem],
                 summary: WindowSummary, time_range: Optional[TimeRange] = None,
                 statistics: Dict[str, str] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.windows = windows
        self.statistics = statistics or {}
        self._template_config = TemplateConfig.from_preset("windows")


@dataclass
class AttributionsOutput(BaseOutput):
    """find-callers 输出结构"""
    attributions: List[AttributionItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, attributions: List[AttributionItem],
                 summary: AttributionSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.attributions = attributions
        self._template_config = TemplateConfig.from_preset("attributions")


@dataclass
class TracesOutput(BaseOutput):
    """find-callers --auto 输出结构"""
    traces: List[TraceItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, traces: List[TraceItem],
                 summary: TracesSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.traces = traces
        self._template_config = TemplateConfig.from_preset("traces")


@dataclass
class PathClustersOutput(BaseOutput):
    """cluster-paths 输出结构"""
    path_clusters: List[PathClusterItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, path_clusters: List[PathClusterItem],
                 summary: PathClusterSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.path_clusters = path_clusters
        self._template_config = TemplateConfig.from_preset("path_clusters")


@dataclass
class ProcessVarietyOutput(BaseOutput):
    """count-process-variety 输出结构"""
    process_variety: List[ProcessVarietyItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, process_variety: List[ProcessVarietyItem],
                 summary: ProcessVarietySummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.process_variety = process_variety
        self._template_config = TemplateConfig.from_preset("process_variety")


@dataclass
class CoreDistributionOutput(BaseOutput):
    """analyze-core-distribution 输出结构"""
    cores: List[CoreItem] = field(default_factory=list)

    def __init__(self, _risk: RiskInfo, cores: List[CoreItem],
                 summary: Optional[CoreDistributionSummary] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.cores = cores
        self._template_config = TemplateConfig.from_preset("cores")


# =============================================================================
# Type Registry
# =============================================================================

OUTPUT_TYPE_MAP = {
    "processes": (ProcessItem, ProcessSummary, ProcessTopOutput),
    "comm_groups": (CommGroupItem, CommGroupSummary, CommTopOutput),
    "clusters": (ClusterItem, ClusterSummary, ClustersOutput),
    "hotspots": (HotspotItem, HotspotSummary, HotspotsOutput),
    "bottleneck": (BottleneckData, BottleneckSummary, BottleneckOutput),
    "cpu_usage": (CPUUsageData, CPUUsageSummary, CPUUsageOutput),
    "anomalies": (AnomalyItem, AnomalySummary, AnomaliesOutput),
    "windows": (WindowItem, WindowSummary, WindowsOutput),
    "attributions": (AttributionItem, AttributionSummary, AttributionsOutput),
    "traces": (TraceItem, TracesSummary, TracesOutput),
    "path_clusters": (PathClusterItem, PathClusterSummary, PathClustersOutput),
    "process_variety": (ProcessVarietyItem, ProcessVarietySummary, ProcessVarietyOutput),
    "cores": (CoreItem, CoreDistributionSummary, CoreDistributionOutput),
}


def get_output_classes(data_type: str):
    """Get output classes for a data type"""
    return OUTPUT_TYPE_MAP.get(data_type, (None, None, None))
