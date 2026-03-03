#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Models - Analysis 层数据模型

用于 Analysis 层内部数据传递，供 Facade 层聚合使用。

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import DiagnosisType

from ..core.models import RiskInfo


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
    diagnosis: str = DiagnosisType.HEALTHY          # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float = 0.0           # 危害指数


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
    risks: List[RiskInfo] = field(default_factory=list)
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
    risks: List[RiskInfo] = field(default_factory=list)


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


@dataclass
class StormAnalysisResult:
    """进程风暴分析结果"""
    storm_groups: List[StormGroupDetail]
    total_storm_comms: int
    max_spawn_rate: float


@dataclass
class CommTopResult:
    """进程组分析结果"""
    groups: List[CommGroup]
    folded_count: int
    total_groups: int
    risks: List[RiskInfo] = field(default_factory=list)
    storm_analysis: Optional[StormAnalysisResult] = None
    metrics: Optional[dict] = None


@dataclass
class CoreDistributionResult:
    """核心分布分析结果"""
    cores: List[CoreStat]
    imbalance_level: str
    saturated_cores: List[CoreStat]
    total_cores: int
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class HotspotsResult:
    """热点函数分析结果"""
    hotspots: List[Hotspot]
    kernel_ratio: float
    user_ratio: float
    sort_by: str
    risks: List[RiskInfo] = field(default_factory=list)


@dataclass
class PathClustersResult:
    """路径聚类分析结果"""
    clusters: List[PathCluster]
    total_clusters: int
    shown_clusters: int
    total_weight: float
    clustered_weight: float
    risks: List[RiskInfo] = field(default_factory=list)


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
    risks: List[RiskInfo] = field(default_factory=list)


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
