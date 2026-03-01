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
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
from datetime import datetime


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
    clustered_core_sec: float = 0.0


@dataclass
class ProcessVarietySummary(BaseSummary):
    """进程多样性摘要"""
    total_processes: int = 0
    storm_detected: bool = False
    storm_count: int = 0


@dataclass
class CoreDistributionSummary(BaseSummary):
    """核心分布摘要"""
    imbalance_level: str = "UNKNOWN"  # "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"
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
    total_cpu_util: str  # "15.50%"
    kernel_cpu_util: str  # "3.20%"
    
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
    cpu: str  # "243.87%"
    kernel: str  # "94.7%"
    event: str = "normal"  # 事件描述
    
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
    self: str  # "15.23%"
    inclusive: str  # "45.67%"
    
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
    ratio_pct: str  # "79.84%"
    cpu_util: str   # "45.50%" (core_sec converted to cpu utilization)
    
    @classmethod
    def from_stats(cls, cluster: str, ratio: float, cpu_util: float) -> 'ClusterItem':
        """从统计数据创建 ClusterItem"""
        return cls(
            cluster=cluster,
            ratio_pct=f"{ratio:.2f}%",
            cpu_util=f"{cpu_util:.2f}%"
        )


@dataclass
class BottleneckData:
    """瓶颈检测数据"""
    verdict: str  # "HEALTHY", "CPU_LIMIT_SATURATION", "SINGLE_CORE_SATURATION"
    max_core_load: Dict[str, Any]  # {"cpu_id": int, "load": str}
    limit_info: Dict[str, Any]  # {"cpu_limit_cores": float, "cpu_limit_detected": bool}


@dataclass
class CPUUsageData:
    """CPU 使用率数据"""
    target: str
    cpu_utilization: Dict[str, str]  # {"total_pct": str, "user_pct": str, "kernel_pct": str}


@dataclass
class AnomalyItem:
    """异常检测数据项 - 用于 detect-anomalies"""
    type: str  # "SPIKE", "DROP"
    cpu_id: int
    time_range: str  # "start - end"
    utilization_change: str
    severity: str  # "high", "medium"


@dataclass
class WindowItem:
    """时间窗口数据项 - 用于 detect-anomalies --export-mode"""
    cpu_id: int
    start_time: str
    end_time: str
    utilization: str  # "45.50%"
    core_sec: float


@dataclass
class AttributionItem:
    """调用归因数据项 - 用于 find-callers"""
    caller_stack: List[str]
    ratio_of_target_pct: str  # "45.50%"
    cpu_util: str  # "12.50%" (converted from core_sec to cpu utilization)


@dataclass
class TraceItem:
    """追踪热点数据项 - 用于 find-callers --auto"""
    target: str
    target_ratio_pct: str  # "15.50%"
    attributions: List[AttributionItem] = field(default_factory=list)


@dataclass
class PathClusterItem:
    """路径聚类数据项 - 用于 cluster-paths"""
    cluster_id: str  # "c_001"
    path_signature: str  # "func1→func2→func3"
    ratio_pct: str  # "45.50%"
    cpu_util: str   # "23.50%" (core_sec converted to cpu utilization)


@dataclass
class ProcessVarietyItem:
    """进程多样性数据项 - 用于 count-process-variety"""
    comm: str
    unique_pids: int
    cpu_util: str  # "45.50%" (converted from total_core_sec)
    behavior: str  # "process_storm" (normal filtered out)


@dataclass
class CoreItem:
    """核心分布数据项 - 用于 analyze-core-distribution (仅 saturated 核心)"""
    cpu_id: int
    total_cpu_util: str  # "95.50%" (usr+sys)
    kernel_cpu_util: str  # "12.30%" (sys)


# =============================================================================
# Output Root Structures
# =============================================================================

@dataclass
class BaseOutput:
    """基础输出结构 - 所有输出的基类"""
    _risk: RiskInfo
    summary: Optional[BaseSummary] = None
    time_range: Optional[TimeRange] = None


@dataclass  
class ProcessTopOutput(BaseOutput):
    """get-process-top 输出结构"""
    processes: List[ProcessItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, processes: List[ProcessItem],
                 summary: ProcessSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.processes = processes


@dataclass
class CommTopOutput(BaseOutput):
    """get-comm-top 输出结构"""
    comm_groups: List[CommGroupItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, comm_groups: List[CommGroupItem],
                 summary: CommGroupSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.comm_groups = comm_groups


@dataclass
class ClusterCommOutput(BaseOutput):
    """cluster-comm 输出结构"""
    comm_groups: List[CommGroupItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, comm_groups: List[CommGroupItem],
                 summary: Optional[CommGroupSummary] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.comm_groups = comm_groups


@dataclass
class HotspotsOutput(BaseOutput):
    """get-hotspots 输出结构"""
    hotspots: List[HotspotItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, hotspots: List[HotspotItem],
                 summary: HotspotSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.hotspots = hotspots


@dataclass
class ClustersOutput(BaseOutput):
    """cluster-symbols 输出结构"""
    clusters: List[ClusterItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, clusters: List[ClusterItem],
                 summary: ClusterSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.clusters = clusters


@dataclass
class BottleneckOutput(BaseOutput):
    """check-cpu-bottleneck 输出结构"""
    data: BottleneckData = field(default_factory=dict)
    
    def __init__(self, _risk: RiskInfo, data: BottleneckData,
                 summary: BottleneckSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.data = data


@dataclass
class CPUUsageOutput(BaseOutput):
    """show-cpu-usage 输出结构"""
    data: CPUUsageData = field(default_factory=dict)
    
    def __init__(self, _risk: RiskInfo, data: CPUUsageData,
                 summary: CPUUsageSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.data = data


@dataclass
class AnomaliesOutput(BaseOutput):
    """detect-anomalies 输出结构"""
    anomalies: List[AnomalyItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, anomalies: List[AnomalyItem],
                 summary: AnomalySummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.anomalies = anomalies


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


@dataclass
class AttributionsOutput(BaseOutput):
    """find-callers 输出结构"""
    attributions: List[AttributionItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, attributions: List[AttributionItem],
                 summary: AttributionSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.attributions = attributions


@dataclass
class TracesOutput(BaseOutput):
    """find-callers --auto 输出结构"""
    traces: List[TraceItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, traces: List[TraceItem],
                 summary: TracesSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.traces = traces


@dataclass
class PathClustersOutput(BaseOutput):
    """cluster-paths 输出结构"""
    path_clusters: List[PathClusterItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, path_clusters: List[PathClusterItem],
                 summary: PathClusterSummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.path_clusters = path_clusters


@dataclass
class ProcessVarietyOutput(BaseOutput):
    """count-process-variety 输出结构"""
    process_variety: List[ProcessVarietyItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, process_variety: List[ProcessVarietyItem],
                 summary: ProcessVarietySummary, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.process_variety = process_variety


@dataclass
class CoreDistributionOutput(BaseOutput):
    """analyze-core-distribution 输出结构"""
    cores: List[CoreItem] = field(default_factory=list)
    
    def __init__(self, _risk: RiskInfo, cores: List[CoreItem],
                 summary: Optional[CoreDistributionSummary] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=summary, time_range=time_range)
        self.cores = cores


# =============================================================================
# Type Registry for Data Type Mapping
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
