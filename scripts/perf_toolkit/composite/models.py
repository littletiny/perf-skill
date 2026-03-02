#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Composite Layer Data Models

用 dataclass 替代 dict，提供类型安全和代码可维护性
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


# =============================================================================
# Risk Related Models
# =============================================================================

@dataclass
class RiskItem:
    """单个Risk条目"""
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False
    
    def __post_init__(self):
        if not self.action_required:
            self.action_required = self.level in ["critical", "warning"]
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'RiskItem':
        """从dict创建（兼容Analysis层返回的risk格式）"""
        return cls(
            level=d.get("level", "info"),
            message=d.get("message", ""),
            hint=d.get("hint", ""),
            patterns=d.get("patterns", []),
            pending_targets=d.get("pending_targets", []),
            action_required=d.get("action_required", False)
        )
    
    def to_dict(self) -> Dict:
        """转换为dict（用于需要序列化的场景）"""
        return {
            "level": self.level,
            "message": self.message,
            "hint": self.hint,
            "patterns": self.patterns,
            "pending_targets": self.pending_targets,
            "action_required": self.action_required
        }


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
    """进程组数据（CommTop分析结果）"""
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
        """内核态占比"""
        return (self.kernel_cpu / self.total_cpu * 100) if self.total_cpu > 0 else 0


# =============================================================================
# Analysis Result Models
# =============================================================================

@dataclass
class AnomalyItem:
    """单个异常点"""
    cpu_id: int
    timestamp: float
    change_magnitude: float
    utilization: float


@dataclass
class AnomaliesReport:
    """异常检测报告"""
    anomalies: List[AnomalyItem] = field(default_factory=list)
    mutation_detected: bool = False
    risks: List[RiskItem] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'AnomaliesReport':
        """从Facade返回的dict创建"""
        anomalies = [
            AnomalyItem(
                cpu_id=a.get("cpu_id", 0),
                timestamp=a.get("timestamp", 0.0),
                change_magnitude=a.get("change_magnitude", 0.0),
                utilization=a.get("utilization", 0.0)
            )
            for a in d.get("anomalies", [])
        ]
        risks = [RiskItem.from_dict(r) for r in d.get("risks", [])]
        return cls(
            anomalies=anomalies,
            mutation_detected=d.get("mutation_detected", False),
            risks=risks
        )


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
    risks: List[RiskItem] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'CoreDistributionReport':
        """从Facade返回的dict创建"""
        cores = d.get("cores", d.get("core_stats", []))
        core_stats = [
            CoreStat(
                cpu_id=c.get("cpu_id", c.get("core_id", 0)),
                total_cpu=c.get("total_cpu", c.get("total_cpu_util", 0.0)),
                kernel_cpu=c.get("kernel_cpu", c.get("kernel_cpu_util", 0.0)),
                user_cpu=c.get("user_cpu", c.get("user_cpu_util", 0.0))
            )
            for c in cores
        ]
        risks = [RiskItem.from_dict(r) for r in d.get("risks", [])]
        return cls(
            core_stats=core_stats,
            saturated_cores=d.get("saturated_cores", []),
            imbalance_level=d.get("imbalance_level", "NORMAL"),
            risks=risks
        )


@dataclass
class CommTopMetrics:
    """CommTop分析的中间指标"""
    cv_map: Dict[str, float] = field(default_factory=dict)
    monopoly_map: Dict[str, float] = field(default_factory=dict)
    spawn_rate_map: Dict[str, float] = field(default_factory=dict)
    impact_score_map: Dict[str, float] = field(default_factory=dict)
    folded_groups: List[ProcessGroup] = field(default_factory=list)
    all_groups: List[ProcessGroup] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'CommTopMetrics':
        """从Analyzer返回的metrics创建"""
        all_groups = [
            ProcessGroup(
                comm=g["comm"],
                total_cpu=g.get("total_cpu", 0.0),
                kernel_cpu=g.get("kernel_cpu", 0.0),
                user_cpu=g.get("user_cpu", 0.0),
                pid_count=g.get("pid_count", g.get("count", 0)),
                pids=g.get("pids", []),
                cv=g.get("cv", 0.0),
                monopoly=g.get("monopoly", 0.0),
                spawn_rate=g.get("spawn_rate", 0.0),
                diagnosis=g.get("diagnosis", "HEALTHY"),
                impact_score=g.get("impact_score", 0.0)
            )
            for g in d.get("all_groups", [])
        ]
        
        folded_groups = [
            ProcessGroup(
                comm=g["comm"],
                total_cpu=g.get("total_cpu", 0.0),
                diagnosis=g.get("diagnosis", "HEALTHY")
            )
            for g in d.get("folded_groups", [])
        ]
        
        return cls(
            cv_map=d.get("cv_map", {}),
            monopoly_map=d.get("monopoly_map", {}),
            spawn_rate_map=d.get("spawn_rate_map", {}),
            impact_score_map=d.get("impact_score_map", {}),
            folded_groups=folded_groups,
            all_groups=all_groups
        )


@dataclass
class CommTopReport:
    """CommTop分析报告"""
    groups: List[ProcessGroup] = field(default_factory=list)
    folded_count: int = 0
    total_groups: int = 0
    risks: List[RiskItem] = field(default_factory=list)
    metrics: Optional[CommTopMetrics] = None
    
    @classmethod
    def from_result(cls, result: Dict) -> 'CommTopReport':
        """从Analyzer返回的result创建"""
        result_data = result.get("result", result)
        groups = [
            ProcessGroup(
                comm=g["comm"],
                total_cpu=g.get("total_cpu", 0.0),
                kernel_cpu=g.get("kernel_cpu", 0.0),
                user_cpu=g.get("user_cpu", 0.0),
                pid_count=g.get("pid_count", g.get("count", 0)),
                pids=g.get("pids", []),
                cv=g.get("cv", 0.0),
                monopoly=g.get("monopoly", 0.0),
                spawn_rate=g.get("spawn_rate", 0.0),
                diagnosis=g.get("diagnosis", "HEALTHY"),
                impact_score=g.get("impact_score", 0.0)
            )
            for g in result_data.get("groups", [])
        ]
        
        risks = [RiskItem.from_dict(r) for r in result.get("risks", [])]
        
        metrics = None
        if "metrics" in result:
            metrics = CommTopMetrics.from_dict(result["metrics"])
        
        return cls(
            groups=groups,
            folded_count=result_data.get("folded_count", 0),
            total_groups=result_data.get("total_groups", len(groups)),
            risks=risks,
            metrics=metrics
        )


# =============================================================================
# Composite Diagnosis Models
# =============================================================================

@dataclass
class DiagnosisReport:
    """综合诊断报告（sys-audit输出）"""
    primary_suspect: Optional[ProcessGroup] = None
    secondary_loads: List[ProcessGroup] = field(default_factory=list)
    background_noise: List[ProcessGroup] = field(default_factory=list)
    background_count: int = 0
    mutation_detected: bool = False
    mutation_time: Optional[float] = None
    saturated_cores: List[int] = field(default_factory=list)
    root_cause_analysis: str = ""


# =============================================================================
# Bottleneck Trace Models
# =============================================================================

@dataclass
class HotspotItem:
    """热点函数项"""
    symbol: str
    cpu_percent: float
    inclusive_percent: float = 0.0
    call_count: int = 0
    resource_tag: str = "COMPUTE"  # LOCK/SYSCALL/SCHED/MEMORY/IO/COMPUTE


@dataclass
class CallerInfo:
    """调用者信息"""
    symbol: str
    call_count: int = 0
    call_ratio: float = 0.0


@dataclass
class HotspotsReport:
    """热点分析报告"""
    hotspots: List[HotspotItem] = field(default_factory=list)
    top_symbol: Optional[str] = None
    total_hotspots: int = 0
    kernel_ratio: float = 0.0
    user_ratio: float = 0.0
    risks: List[RiskItem] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'HotspotsReport':
        """从Facade返回的dict创建"""
        hotspots = [
            HotspotItem(
                symbol=h.get("symbol", ""),
                cpu_percent=h.get("cpu_percent", h.get("self_pct", 0.0)),
                inclusive_percent=h.get("inclusive_percent", h.get("inclusive_pct", 0.0)),
                call_count=h.get("call_count", h.get("count", 0)),
                resource_tag=h.get("resource_tag", "COMPUTE")
            )
            for h in d.get("hotspots", [])
        ]
        
        risks = [RiskItem.from_dict(r) for r in d.get("risks", [])]
        
        top = d.get("top_symbol")
        if not top and hotspots:
            top = hotspots[0].symbol
        
        return cls(
            hotspots=hotspots,
            top_symbol=top,
            total_hotspots=d.get("total_hotspots", len(hotspots)),
            kernel_ratio=d.get("kernel_ratio", 0.0),
            user_ratio=d.get("user_ratio", 0.0),
            risks=risks
        )


@dataclass
class CallersReport:
    """调用链分析报告"""
    target: str = ""
    callers: List[CallerInfo] = field(default_factory=list)
    hot_paths: List[str] = field(default_factory=list)
    risks: List[RiskItem] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'CallersReport':
        """从Facade返回的dict创建"""
        callers = [
            CallerInfo(
                symbol=c.get("symbol", ""),
                call_count=c.get("call_count", c.get("count", 0)),
                call_ratio=c.get("call_ratio", c.get("ratio", 0.0))
            )
            for c in d.get("callers", [])
        ]
        
        risks = [RiskItem.from_dict(r) for r in d.get("risks", [])]
        
        return cls(
            target=d.get("target", ""),
            callers=callers,
            hot_paths=d.get("hot_paths", []),
            risks=risks
        )


@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = "NORMAL"
    impact_score: float = 0.0
    risks: List[RiskItem] = field(default_factory=list)


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
    risks: List[RiskItem] = field(default_factory=list)


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
    risks: List[RiskItem] = field(default_factory=list)
