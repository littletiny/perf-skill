#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Composite Layer Data Models

用 dataclass 替代 dict，提供类型安全和代码可维护性
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..core.models import RiskInfo


@dataclass
class TargetDetail:
    """目标详情（用于Composite展示）"""
    target: str
    level: str
    message: str
    hint: str


# =============================================================================
# Process Group Models
# =============================================================================

@dataclass
class ProcessGroup:
    """
    进程组数据（从 CommGroup 转换）
    
    包含 CV/Monopoly/SpawnRate 等增强指标，用于解决"A掩盖B"问题。
    """
    comm: str
    total_cpu: float = 0.0
    kernel_cpu: float = 0.0
    user_cpu: float = 0.0
    pid_count: int = 0
    pids: List[int] = field(default_factory=list)
    cv: float = 0.0              # 变异系数
    monopoly: float = 0.0        # 独占率
    spawn_rate: float = 0.0      # 产生速率
    diagnosis: str = "HEALTHY"   # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float = 0.0    # 危害指数

    @property
    def kernel_ratio(self) -> float:
        """内核态占比 (%)"""
        return (self.kernel_cpu / self.total_cpu * 100) if self.total_cpu > 0 else 0


# =============================================================================
# Analysis Result Models
# =============================================================================

@dataclass
class AnomalyItem:
    """
    异常点数据（从 Anomaly 转换）
    
    用于时间序列异常检测结果的内部表示。
    """
    cpu_id: int
    timestamp: float
    change_magnitude: float
    utilization: float
    anomaly_type: str = "SPIKE"  # SPIKE | DROP
    z_score: float = 0.0


@dataclass
class AnomaliesReport:
    """
    异常检测报告（Composite 层）
    """
    anomalies: List[AnomalyItem] = field(default_factory=list)
    mutation_detected: bool = False
    spike_count: int = 0
    drop_count: int = 0
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CoreStat:
    """单个核心统计"""
    cpu_id: int
    total_cpu: float = 0.0
    kernel_cpu: float = 0.0
    user_cpu: float = 0.0


@dataclass
class CoreDistributionReport:
    """核心分布报告"""
    core_stats: List[CoreStat] = field(default_factory=list)
    saturated_cores: List[int] = field(default_factory=list)
    imbalance_level: str = "NORMAL"  # NORMAL/MODERATE/SEVERE
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CommTopMetrics:
    """CommTop分析的中间指标"""
    cv_map: Dict[str, float] = field(default_factory=dict)
    monopoly_map: Dict[str, float] = field(default_factory=dict)
    spawn_rate_map: Dict[str, float] = field(default_factory=dict)
    impact_score_map: Dict[str, float] = field(default_factory=dict)
    folded_groups: List[ProcessGroup] = field(default_factory=list)
    all_groups: List[ProcessGroup] = field(default_factory=list)


@dataclass
class CommTopReport:
    """
    CommTop分析报告（Composite 层）
    """
    groups: List[ProcessGroup] = field(default_factory=list)
    folded_count: int = 0
    total_groups: int = 0
    risks: List[RiskInfo] = field(default_factory=list)
    metrics: Optional[CommTopMetrics] = None


# =============================================================================
# Composite Diagnosis Models
# =============================================================================

@dataclass
class DiagnosisReport:
    """
    综合诊断报告（sys-audit输出）
    
    整合 anomalies、core_distribution、comm_top 三个分析器的结果，
    解决"A（高Count亮眼数字）掩盖B（真瓶颈）"问题。
    """
    primary_suspect: Optional[ProcessGroup] = None
    secondary_loads: List[ProcessGroup] = field(default_factory=list)
    background_noise: List[ProcessGroup] = field(default_factory=list)
    background_count: int = 0
    mutation_detected: bool = False
    mutation_time: Optional[float] = None
    saturated_cores: List[int] = field(default_factory=list)
    imbalance_level: str = "NORMAL"  # NORMAL/MODERATE/SEVERE
    root_cause_analysis: str = ""
    recommendations: List[str] = field(default_factory=list)
    risks: List[RiskInfo] = field(default_factory=list)


# =============================================================================
# Bottleneck Trace Models
# =============================================================================

@dataclass
class HotspotItem:
    """热点函数数据（用于瓶颈追踪中的热点分析结果）"""
    symbol: str
    cpu_percent: float
    inclusive_percent: float = 0.0
    call_count: int = 0
    resource_tag: str = "COMPUTE"  # LOCK/SYSCALL/SCHED/MEMORY/IO/COMPUTE


@dataclass
class CallerInfo:
    """调用者信息（用于调用链溯源分析）"""
    symbol: str
    call_count: int = 0
    call_ratio: float = 0.0
    total_weight: float = 0.0


@dataclass
class HotspotsReport:
    """热点分析报告（Composite 层）"""
    hotspots: List[HotspotItem] = field(default_factory=list)
    top_symbol: Optional[str] = None
    total_hotspots: int = 0
    kernel_ratio: float = 0.0
    user_ratio: float = 0.0
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CallersReport:
    """调用链溯源报告（Composite 层）"""
    target: str = ""
    callers: List[CallerInfo] = field(default_factory=list)
    hot_paths: List[str] = field(default_factory=list)
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class BottleneckAnalysis:
    """
    瓶颈分析结果
    
    bottleneck-trace 命令的核心输出。
    """
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = "NORMAL"
    impact_score: float = 0.0
    risks: List[RiskInfo] = field(default_factory=list)


# =============================================================================
# SysAudit Output Models
# =============================================================================

@dataclass
class PrimarySuspectData:
    """主要嫌疑进程数据"""
    comm: str
    total_cpu: float
    diagnosis: str
    monopoly: float


@dataclass
class SecondaryLoadData:
    """次要负载数据"""
    comm: str
    total_cpu: float
    diagnosis: str


@dataclass
class DiagnosisDetails:
    """诊断详情（SysAuditOutput.diagnosis 字段）"""
    primary_suspect: Optional[PrimarySuspectData] = None
    secondary_loads: List[SecondaryLoadData] = field(default_factory=list)
    background_count: int = 0
    mutation_detected: bool = False
    mutation_time: Optional[float] = None
    saturated_cores: List[int] = field(default_factory=list)
    root_cause_analysis: str = ""


@dataclass
class AnomaliesDetails:
    """异常详情（SysAuditOutput.details.anomalies）"""
    anomalies_count: int = 0
    mutation_detected: bool = False
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CoreDistDetails:
    """核心分布详情（SysAuditOutput.details.core_distribution）"""
    core_count: int = 0
    saturated_cores: List[int] = field(default_factory=list)
    imbalance_level: str = "NORMAL"
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CommTopDetails:
    """CommTop详情（SysAuditOutput.details.comm_top）"""
    groups_count: int = 0
    folded_count: int = 0
    total_groups: int = 0
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class SysAuditDetails:
    """SysAudit 综合详情（SysAuditOutput.details 字段）"""
    anomalies: AnomaliesDetails = field(default_factory=AnomaliesDetails)
    core_distribution: CoreDistDetails = field(default_factory=CoreDistDetails)
    comm_top: CommTopDetails = field(default_factory=CommTopDetails)


# =============================================================================
# BottleneckTrace Output Models (replacing dict)
# =============================================================================

@dataclass
class HotspotData:
    """热点数据项"""
    symbol: str
    cpu_percent: float
    resource_tag: str


@dataclass
class HotspotsDetails:
    """热点详情（BottleneckTraceOutput.hotspots）"""
    hotspots: List[HotspotData] = field(default_factory=list)
    top_symbol: Optional[str] = None
    total_hotspots: int = 0
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class CallerData:
    """调用者数据项"""
    symbol: str
    call_ratio: float


@dataclass
class CallersDetails:
    """调用者详情（BottleneckTraceOutput.callers）"""
    target: str = ""
    callers: List[CallerData] = field(default_factory=list)
    risks: List[RiskInfo] = field(default_factory=list)


# =============================================================================
# Storm Trace Models
# =============================================================================

@dataclass
class LifecycleEvent:
    """生命周期事件"""
    timestamp: float
    pid: int
    event_type: str  # SPAWN/EXIT
    stack: List[str] = field(default_factory=list)


@dataclass
class CreatorInfo:
    """进程创建者信息"""
    symbol: str
    count: int = 0


@dataclass
class LifecycleReport:
    """生命周期分析报告"""
    spawn_events_count: int = 0
    exit_events_count: int = 0
    spawn_rate: float = 0.0
    top_creators: List[CreatorInfo] = field(default_factory=list)
    short_lived_count: int = 0
    leaked_count: int = 0
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class StormAnalysis:
    """风暴分析结果"""
    found: bool = False
    comm: str = ""
    spawn_rate: float = 0.0
    pid_count: int = 0
    total_cpu: float = 0.0
    severity: str = "NONE"  # LOW/MEDIUM/HIGH/CRITICAL
    diagnosis: str = "NORMAL"
    risks: List[RiskInfo] = field(default_factory=list)
