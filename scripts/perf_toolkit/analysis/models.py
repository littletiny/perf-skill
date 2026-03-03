#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Models - Analysis 层数据模型

用于 Analysis 层内部数据传递，供 Facade 层聚合使用。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Risk:
    """
    风险数据结构
    
    用于在 Analyzer 之间传递风险信息，供 Composite 层聚合。
    """
    level: str                          # "critical" | "warning" | "info" | "none"
    message: str = ""                   # 风险描述
    hint: str = ""                      # 建议操作
    patterns: List[str] = field(default_factory=list)  # 检测到的模式标签
    pending_targets: List[str] = field(default_factory=list)  # 待处理目标列表
    action_required: bool = field(init=False)  # 是否需要立即处理
    
    def __post_init__(self):
        self.action_required = self.level in ["critical", "warning"]


@dataclass
class CommGroup:
    """进程组数据结构 - CommTopAnalyzer 内部使用"""
    comm: str
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
    pid_count: int
    pids: List[int] = field(default_factory=list)
    cv: float = 0.0                     # 变异系数
    monopoly: float = 0.0               # 核心独占率
    spawn_rate: float = 0.0             # 产生速率
    diagnosis: str = "HEALTHY"          # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float = 0.0           # 危害指数
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "comm": self.comm,
            "total_cpu": self.total_cpu,
            "kernel_cpu": self.kernel_cpu,
            "user_cpu": self.user_cpu,
            "pid_count": self.pid_count,
            "pids": self.pids,
            "cv": self.cv,
            "monopoly": self.monopoly,
            "spawn_rate": self.spawn_rate,
            "diagnosis": self.diagnosis,
            "impact_score": self.impact_score
        }


@dataclass
class Hotspot:
    """热点函数数据结构 - HotspotsAnalyzer 内部使用"""
    symbol: str
    self_pct: float
    inclusive_pct: float
    is_kernel: bool = False


@dataclass
class CoreStat:
    """核心统计数据结构 - CoreDistAnalyzer 内部使用"""
    cpu_id: int
    total_cpu: float
    kernel_cpu: float
    user_cpu: float


@dataclass
class Anomaly:
    """异常数据结构 - AnomaliesAnalyzer 内部使用"""
    type: str                           # "SPIKE" | "DROP"
    cpu_id: int
    time_range_start: str
    time_range_end: str
    prev_util: float
    curr_util: float
    next_util: float
    z_score: float
    
    @property
    def change_magnitude(self) -> float:
        """变化幅度（用于排序）"""
        return abs(self.curr_util - self.prev_util)


@dataclass
class PathCluster:
    """路径聚类数据结构 - PathClustersAnalyzer 内部使用"""
    cluster_id: str
    path_signature: str
    depth: int
    weight: float
    cpu_util: float = 0.0


@dataclass
class SymbolCluster:
    """符号聚类数据结构 - SymbolClustersAnalyzer 内部使用"""
    group: str
    ratio: float
    weight: float


@dataclass
class ProcessVariety:
    """进程多样性数据结构 - ProcessVarietyAnalyzer 内部使用"""
    comm: str
    pids_per_min: int
    cpu_util: float
    behavior: str                     # "normal" | "process_storm"
    pid_count: int = 0
    samples_per_pid: float = 0.0


@dataclass
class AnalysisResult:
    """
    统一分析结果结构
    
    所有 Analyzer 返回的标准结构，供 Facade 聚合使用。
    """
    result: dict = field(default_factory=dict)
    risks: List[Risk] = field(default_factory=list)
    metrics: Optional[dict] = None


# =============================================================================
# Analyzer Result Dataclasses
# =============================================================================

@dataclass
class AnomaliesResult:
    """异常检测结果"""
    anomalies: List[Anomaly]
    mutation_detected: bool
    spike_count: int
    drop_count: int
    risks: List[Risk] = field(default_factory=list)


@dataclass 
class StormGroupDetail:
    """风暴组详情 - StormAnalysisResult 子结构"""
    comm: str
    spawn_rate: float
    pid_count: int
    total_cpu: float
    severity: str
    top_creators: List[dict] = field(default_factory=list)
    short_lived_count: int = 0
    leaked_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "comm": self.comm,
            "spawn_rate": self.spawn_rate,
            "pid_count": self.pid_count,
            "total_cpu": self.total_cpu,
            "severity": self.severity,
            "top_creators": self.top_creators,
            "short_lived_count": self.short_lived_count,
            "leaked_count": self.leaked_count
        }


@dataclass
class StormAnalysisResult:
    """进程风暴分析结果"""
    storm_groups: List[StormGroupDetail]
    total_storm_comms: int
    max_spawn_rate: float
    
    def to_dict(self) -> dict:
        return {
            "storm_groups": [g.to_dict() for g in self.storm_groups],
            "total_storm_comms": self.total_storm_comms,
            "max_spawn_rate": self.max_spawn_rate
        }


@dataclass
class CommTopResult:
    """进程组分析结果"""
    groups: List[CommGroup]
    folded_count: int
    total_groups: int
    risks: List[Risk] = field(default_factory=list)
    storm_analysis: Optional[StormAnalysisResult] = None
    metrics: Optional[dict] = None


@dataclass
class CoreDistributionResult:
    """核心分布分析结果"""
    cores: List[CoreStat]
    imbalance_level: str
    saturated_cores: List[CoreStat]
    total_cores: int
    risks: List[Risk] = field(default_factory=list)


@dataclass
class HotspotsResult:
    """热点函数分析结果"""
    hotspots: List[Hotspot]
    kernel_ratio: float
    user_ratio: float
    sort_by: str
    risks: List[Risk] = field(default_factory=list)


@dataclass
class PathClustersResult:
    """路径聚类分析结果"""
    clusters: List[PathCluster]
    total_clusters: int
    shown_clusters: int
    total_weight: float
    clustered_weight: float
    risks: List[Risk] = field(default_factory=list)


@dataclass
class CallerAttribution:
    """调用归因详情 - CallersResult 子结构"""
    symbol: str
    call_count: int
    call_ratio: float
    total_weight: float


@dataclass
class CallersResult:
    """调用链溯源结果"""
    target: str
    callers: List[CallerAttribution]
    total_weight: float
    risks: List[Risk] = field(default_factory=list)


# =============================================================================
# Engine Protocol Return Types
# =============================================================================

@dataclass
class SpawnEvent:
    """进程创建事件"""
    pid: int
    comm: str
    ts: float
    stack: Optional[List[str]] = None


@dataclass
class ExitEvent:
    """进程退出事件"""
    pid: int
    comm: str
    ts: float


@dataclass
class LifecycleStats:
    """生命周期统计"""
    total_spawned: int = 0
    total_exited: int = 0
    short_lived_count: int = 0
    avg_lifetime_sec: float = 0.0


@dataclass
class LifecycleInfo:
    """进程生命周期信息"""
    spawn_events: List[SpawnEvent]
    exit_events: List[ExitEvent]
    spawn_rate: float
    lifecycle_stats: LifecycleStats


@dataclass
class CallerInfo:
    """调用者信息"""
    symbol: str
    call_count: int
    total_weight: float
    call_ratio: float


@dataclass
class CallGraphInfo:
    """调用图信息"""
    callers: List[CallerInfo]
    call_graph: dict
    hot_paths: List[str]
