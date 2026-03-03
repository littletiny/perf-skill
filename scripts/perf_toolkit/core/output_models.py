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
from enum import IntEnum

from .display_presets import get_display_preset


# =============================================================================
# Risk Level Enum
# =============================================================================

class RiskLevel(IntEnum):
    """Risk level enumeration with priority values
    
    Lower value = higher priority
    """
    CRITICAL = 0
    WARNING = 1
    INFO = 2
    NONE = 3
    
    @classmethod
    def from_string(cls, level: str) -> 'RiskLevel':
        """从字符串创建 RiskLevel"""
        mapping = {
            "critical": cls.CRITICAL,
            "warning": cls.WARNING,
            "info": cls.INFO,
            "none": cls.NONE,
        }
        return mapping.get(level.lower(), cls.INFO)
    
    def to_string(self) -> str:
        """转换为字符串"""
        return self.name.lower()


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
        return cls(
            template_type=preset.template_type,
            list_field=preset.list_field,
            header=preset.header,
            display_fields=preset.display_fields,
            index_format=preset.index_format,
            custom_renderer=preset.custom_renderer,
            empty_message=preset.empty_message,
            total_field=preset.total_field,
            shown_field=preset.shown_field
        )


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
# Composite Layer Output Models
# =============================================================================

@dataclass
class SysAuditSummary(BaseSummary):
    """系统审计摘要"""
    primary_suspect: str = ""
    secondary_count: int = 0
    mutation_detected: bool = False


@dataclass
class SysAuditOutput(BaseOutput):
    """sys-audit 输出结构"""
    diagnosis: Dict = field(default_factory=dict)
    details: Dict = field(default_factory=dict)

    def __init__(self, _risk: RiskInfo, diagnosis: Dict, details: Dict,
                 time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=None, time_range=time_range)
        self.diagnosis = diagnosis
        self.details = details
        self._template_config = TemplateConfig(
            template_type="custom",
            custom_renderer="sys_audit_renderer"
        )


@dataclass
class BottleneckTraceSummary(BaseSummary):
    """瓶颈追踪摘要"""
    target_comm: str = ""
    top_symbol: str = ""
    hotspot_count: int = 0


@dataclass
class BottleneckTraceOutput(BaseOutput):
    """bottleneck-trace 输出结构"""
    target_comm: str = ""
    bottleneck_analysis: Dict = field(default_factory=dict)
    hotspots: Dict = field(default_factory=dict)
    callers: Optional[Dict] = None

    def __init__(self, _risk: RiskInfo, target_comm: str,
                 bottleneck_analysis: Dict, hotspots: Dict,
                 callers: Optional[Dict] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=None, time_range=time_range)
        self.target_comm = target_comm
        self.bottleneck_analysis = bottleneck_analysis
        self.hotspots = hotspots
        self.callers = callers
        self._template_config = TemplateConfig(
            template_type="custom",
            custom_renderer="bottleneck_trace_renderer"
        )


@dataclass
class StormTraceSummary(BaseSummary):
    """进程风暴追踪摘要"""
    target_comm: str = ""
    spawn_rate: float = 0.0
    severity: str = "NONE"


@dataclass
class StormTraceOutput(BaseOutput):
    """storm-trace 输出结构"""
    target_comm: str = ""
    storm_analysis: Dict = field(default_factory=dict)
    lifecycle: Dict = field(default_factory=dict)
    callers: Optional[Dict] = None

    def __init__(self, _risk: RiskInfo, target_comm: str,
                 storm_analysis: Dict, lifecycle: Dict,
                 callers: Optional[Dict] = None, time_range: Optional[TimeRange] = None):
        super().__init__(_risk=_risk, summary=None, time_range=time_range)
        self.target_comm = target_comm
        self.storm_analysis = storm_analysis
        self.lifecycle = lifecycle
        self.callers = callers
        self._template_config = TemplateConfig(
            template_type="custom",
            custom_renderer="storm_trace_renderer"
        )


# =============================================================================
# Trace Module Data Models (Dict Refactor)
# =============================================================================

@dataclass
class TimelineRecord:
    """时间线记录 - trace.py begin_command"""
    seq: int
    type: str
    command: str
    timestamp: str
    findings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Issue:
    """Issue 记录 - trace.py add"""
    id: str
    desc: str
    level: str
    status: str
    created_at: str
    created_by_seq: Optional[int] = None
    resolved_at: Optional[str] = None
    resolved_by_seq: Optional[int] = None
    result: Optional[str] = None
    hint: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    reopen_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """解决结果记录 - trace.py complete"""
    result: str
    resolved_at: str
    resolved_by_seq: Optional[int] = None


@dataclass
class ReopenRecord:
    """重新打开记录 - trace.py reopen"""
    reopened_at: str
    reason: str
    previous_result: Optional[str] = None
    previous_resolved_at: Optional[str] = None
    previous_resolved_by_seq: Optional[int] = None
    previous_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TraceDocument:
    """Trace 文档根结构 - trace.py _create_new"""
    version: str
    created_at: str
    updated_at: str
    data_file: Optional[str] = None
    initial_command: str = ""
    timeline: List[TimelineRecord] = field(default_factory=list)
    issues: Dict[str, Issue] = field(default_factory=dict)


@dataclass
class TraceData:
    """Trace 数据根结构（用于 trace.py 内部操作）
    
    替代原有的裸 dict，提供类型安全
    """
    version: str = "2.0"
    data_file: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    issues: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    profiles_used: List[str] = field(default_factory=list)
    
    @classmethod
    def create_new(cls, data_file: Optional[str] = None) -> 'TraceData':
        """创建新的 TraceData 实例"""
        from datetime import datetime
        now = datetime.utcnow().isoformat() + "Z"
        return cls(
            version="2.0",
            data_file=data_file,
            created_at=now,
            updated_at=now,
            timeline=[],
            issues={},
            profiles_used=[data_file] if data_file else []
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict 用于 JSON 序列化"""
        return {
            "version": self.version,
            "data_file": self.data_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timeline": self.timeline,
            "issues": self.issues,
            "profiles_used": self.profiles_used
        }


# =============================================================================
# OutputBuilder Module Data Models (Dict Refactor)
# =============================================================================

@dataclass
class TraceSummary:
    """Trace 摘要统计 - output_builder.py get_trace_summary"""
    total_commands: int = 0
    open_issues: int = 0
    resolved_issues: int = 0
    can_finalize: bool = False


@dataclass
class ErrorData:
    """错误数据结构 - output_builder.py 错误处理"""
    error: str
    message: str
    recovery_hint: str = ""


@dataclass
class QualityMetrics:
    """质量指标 - output_builder.py 质量指标"""
    total_samples: int = 0
    time_range_seconds: float = 0.0
    cpu_count: int = 0


@dataclass
class IssueCategories:
    """Issue 分类统计 - output_builder.py _categorize_issues"""
    kernel_anomaly: int = 0
    lock_contention: int = 0
    process_storm: int = 0


# =============================================================================
# Trace Module Result Dataclasses (Dict Refactor)
# =============================================================================

@dataclass
class FinalizeResult:
    """Trace finalize 结果结构 - trace.py finalize"""
    status: str  # "ready" | "accepted" | "blocked"
    message: str
    resolved_count: Optional[int] = None
    open_count: Optional[int] = None
    open_issues: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict 用于 JSON 序列化"""
        result = {
            "status": self.status,
            "message": self.message,
        }
        if self.resolved_count is not None:
            result["resolved_count"] = self.resolved_count
        if self.open_count is not None:
            result["open_count"] = self.open_count
        if self.open_issues is not None:
            result["open_issues"] = self.open_issues
        return result


# =============================================================================
# Audit Module Dataclasses (Dict Refactor)
# =============================================================================

@dataclass
class CheckResult:
    """审计检查结果 - audit.py 检查项结果"""
    status: str  # "passed" | "warning" | "failed"
    message: str = ""


@dataclass
class IssueAuditResult:
    """单个 Issue 的审计结果 - audit.py _audit_issue"""
    issue_id: str
    desc: str
    status: str  # "passed" | "warning" | "failed"
    checks: Dict[str, CheckResult] = field(default_factory=dict)


@dataclass
class AuditSummary:
    """审计摘要统计 - audit.py 输出"""
    total: int = 0
    passed: int = 0
    warning: int = 0
    failed: int = 0


@dataclass
class AuditOutput:
    """审计输出结构 - audit.py 最终输出"""
    summary: AuditSummary
    results: List[IssueAuditResult]


# =============================================================================
# Reliability Module Data Models (Dict Refactor)
# =============================================================================

@dataclass
class DataQualityMetrics:
    """数据质量指标 - reliability.py assess_data_quality"""
    record_count: int = 0
    duration_sec: float = 0.0
    cpu_utilization_pct: float = 0.0
    utilization_source: str = "unknown"
    total_weight: Optional[float] = None
    avg_weight: Optional[float] = None


# =============================================================================
# Display Presets Module Data Models (Dict Refactor)
# =============================================================================

@dataclass
class DisplayPreset:
    """显示格式预设 - display_presets.py DISPLAY_PRESETS"""
    template_type: str
    list_field: Optional[str] = None
    header: Optional[str] = None
    display_fields: List[str] = field(default_factory=list)
    index_format: Optional[str] = None
    custom_renderer: Optional[str] = None
    empty_message: Optional[str] = None
    total_field: Optional[str] = None
    shown_field: Optional[str] = None


# =============================================================================
# CLI Layer Data Models (Dict Refactor - Task-4.1.x)
# =============================================================================

@dataclass
class ProfileConfig:
    """Profile 配置 - shecr_wrap.py cmd_init 使用
    
    Task-4.1.4, Task-4.1.5: 替代原有的 profile dict
    """
    name: str  # data_path as identifier
    data_file: str
    init_time: str
    script_path: str
    freq: Optional[str] = None
    risk_config: Optional[str] = None
    rules_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict 用于 JSON 序列化"""
        return {
            "init_time": self.init_time,
            "script_path": self.script_path,
            "freq": self.freq,
            "risk_config": self.risk_config,
            "rules_file": self.rules_file
        }


@dataclass
class EnvironmentConfig:
    """环境配置 - shecr_wrap.py load_env/migrate_old_env 使用
    
    Task-4.1.1, Task-4.1.2: 替代原有的 env dict
    """
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)
    default: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict 用于 JSON 序列化"""
        return {
            "profiles": {
                name: profile.to_dict()
                for name, profile in self.profiles.items()
            },
            "default": self.default
        }
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnvironmentConfig':
        """从 dict 创建 EnvironmentConfig"""
        profiles_data = data.get("profiles", {})
        profiles = {
            name: ProfileConfig(
                name=name,
                data_file=name,
                init_time=pdata.get("init_time", ""),
                script_path=pdata.get("script_path", ""),
                freq=pdata.get("freq"),
                risk_config=pdata.get("risk_config"),
                rules_file=pdata.get("rules_file")
            )
            for name, pdata in profiles_data.items()
        }
        return cls(
            profiles=profiles,
            default=data.get("default")
        )



@dataclass
class TraceConfig:
    """Trace 配置 - shecr_wrap.py init_global_trace 使用
    
    Task-4.1.3: 替代原有的 trace dict
    """
    version: str
    data_file: str
    created_at: str
    updated_at: str
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    issues: Dict[str, Any] = field(default_factory=dict)
    profiles_used: List[str] = field(default_factory=list)
    

    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict 用于 JSON 序列化"""
        return {
            "version": self.version,
            "data_file": self.data_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timeline": self.timeline,
            "issues": self.issues,
            "profiles_used": self.profiles_used
        }





    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceConfig':
        """从 dict 创建 TraceConfig"""
        return cls(
            version=data.get("version", "2.0"),
            data_file=data.get("data_file", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            timeline=data.get("timeline", []),
            issues=data.get("issues", {}),
            profiles_used=data.get("profiles_used", [])
        )

    @classmethod
    def create_new(cls, data_file: str) -> 'TraceConfig':
        """创建新的 TraceConfig 实例"""
        from datetime import datetime
        now = datetime.now().isoformat()
        return cls(
            version="2.0",
            data_file=data_file,
            created_at=now,
            updated_at=now,
            timeline=[],
            issues={},
            profiles_used=[data_file]
        )

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
