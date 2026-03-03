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
        """从Facade返回的dict或AnomaliesResult dataclass创建"""
        # 处理 dataclass 输入（AnomaliesResult 有 anomalies 属性）
        if hasattr(d, 'anomalies') and not isinstance(d, dict):
            risks = [RiskItem.from_dict(r) if isinstance(r, dict) else r for r in (getattr(d, 'risks', None) or [])]
            anomalies_data = d.anomalies
            
            anomalies = [
                AnomalyItem(
                    cpu_id=getattr(a, 'cpu_id', getattr(a, 'type', 0)),
                    timestamp=getattr(a, 'timestamp', 0.0),
                    change_magnitude=getattr(a, 'change_magnitude', 0.0),
                    utilization=getattr(a, 'utilization', getattr(a, 'curr_util', 0.0))
                )
                for a in anomalies_data
            ]
            mutation = getattr(d, 'mutation_detected', False)
            return cls(
                anomalies=anomalies,
                mutation_detected=mutation,
                risks=risks
            )
        
        # 处理 dict 输入（原始方式）
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
        """从Facade返回的dict或CoreDistributionResult dataclass创建"""
        # 处理 dataclass 输入（CoreDistributionResult 有 cores 属性）
        if hasattr(d, 'cores') and not isinstance(d, dict):
            risks = [RiskItem.from_dict(r) if isinstance(r, dict) else r for r in (getattr(d, 'risks', None) or [])]
            cores_data = d.cores
            
            core_stats = [
                CoreStat(
                    cpu_id=getattr(c, 'cpu_id', getattr(c, 'core_id', 0)),
                    total_cpu=getattr(c, 'total_cpu', getattr(c, 'total_cpu_util', 0.0)),
                    kernel_cpu=getattr(c, 'kernel_cpu', getattr(c, 'kernel_cpu_util', 0.0)),
                    user_cpu=getattr(c, 'user_cpu', getattr(c, 'user_cpu_util', 0.0))
                )
                for c in cores_data
            ]
            
            saturated = getattr(d, 'saturated_cores', [])
            # saturated_cores 可能是 CoreStat 对象列表，提取 cpu_id
            if saturated and hasattr(saturated[0], 'cpu_id'):
                saturated = [getattr(c, 'cpu_id', 0) for c in saturated]
            
            imbalance = getattr(d, 'imbalance_level', 'NORMAL')
            
            return cls(
                core_stats=core_stats,
                saturated_cores=saturated,
                imbalance_level=imbalance,
                risks=risks
            )
        
        # 处理 dict 输入
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
    def from_dict(cls, d) -> 'CommTopMetrics':
        """从Analyzer返回的metrics创建（支持 dict 或包含 dataclass 的结构）"""
        # all_groups 中的元素可能是 dict 或 CommGroup dataclass
        all_groups_raw = d.get("all_groups", []) if isinstance(d, dict) else getattr(d, 'all_groups', [])
        
        all_groups = []
        for g in all_groups_raw:
            if isinstance(g, dict):
                all_groups.append(ProcessGroup(
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
                ))
            else:
                # 处理 CommGroup dataclass
                all_groups.append(ProcessGroup(
                    comm=g.comm,
                    total_cpu=getattr(g, 'total_cpu', 0.0),
                    kernel_cpu=getattr(g, 'kernel_cpu', 0.0),
                    user_cpu=getattr(g, 'user_cpu', 0.0),
                    pid_count=getattr(g, 'pid_count', 0),
                    pids=getattr(g, 'pids', []),
                    cv=getattr(g, 'cv', 0.0),
                    monopoly=getattr(g, 'monopoly', 0.0),
                    spawn_rate=getattr(g, 'spawn_rate', 0.0),
                    diagnosis=getattr(g, 'diagnosis', 'HEALTHY'),
                    impact_score=getattr(g, 'impact_score', 0.0)
                ))
        
        folded_groups_raw = d.get("folded_groups", []) if isinstance(d, dict) else getattr(d, 'folded_groups', [])
        folded_groups = []
        for g in folded_groups_raw:
            if isinstance(g, dict):
                folded_groups.append(ProcessGroup(
                    comm=g["comm"],
                    total_cpu=g.get("total_cpu", 0.0),
                    diagnosis=g.get("diagnosis", "HEALTHY")
                ))
            else:
                # 处理 CommGroup dataclass
                folded_groups.append(ProcessGroup(
                    comm=g.comm,
                    total_cpu=getattr(g, 'total_cpu', 0.0),
                    diagnosis=getattr(g, 'diagnosis', 'HEALTHY')
                ))
        
        if isinstance(d, dict):
            return cls(
                cv_map=d.get("cv_map", {}),
                monopoly_map=d.get("monopoly_map", {}),
                spawn_rate_map=d.get("spawn_rate_map", {}),
                impact_score_map=d.get("impact_score_map", {}),
                folded_groups=folded_groups,
                all_groups=all_groups
            )
        else:
            return cls(
                cv_map=getattr(d, 'cv_map', {}),
                monopoly_map=getattr(d, 'monopoly_map', {}),
                spawn_rate_map=getattr(d, 'spawn_rate_map', {}),
                impact_score_map=getattr(d, 'impact_score_map', {}),
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
    def from_result(cls, result) -> 'CommTopReport':
        """从Analyzer返回的result创建（支持 dict 或 CommTopResult dataclass）"""
        # 处理 dataclass 输入（CommTopResult）
        if hasattr(result, 'groups') and not isinstance(result, dict):
            # 直接处理 CommTopResult dataclass
            groups_data = result.groups
            risks_data = getattr(result, 'risks', [])
            
            groups = [
                ProcessGroup(
                    comm=g.comm,
                    total_cpu=getattr(g, 'total_cpu', 0.0),
                    kernel_cpu=getattr(g, 'kernel_cpu', 0.0),
                    user_cpu=getattr(g, 'user_cpu', 0.0),
                    pid_count=getattr(g, 'pid_count', 0),
                    pids=getattr(g, 'pids', []),
                    cv=getattr(g, 'cv', 0.0),
                    monopoly=getattr(g, 'monopoly', 0.0),
                    spawn_rate=getattr(g, 'spawn_rate', 0.0),
                    diagnosis=getattr(g, 'diagnosis', 'HEALTHY'),
                    impact_score=getattr(g, 'impact_score', 0.0)
                )
                for g in groups_data
            ]
            
            risks = [RiskItem.from_dict(r) if isinstance(r, dict) else r for r in risks_data]
            
            metrics = None
            metrics_data = getattr(result, 'metrics', None)
            if metrics_data:
                # metrics 是 dict，使用 from_dict 转换
                metrics = CommTopMetrics.from_dict(metrics_data)
            
            return cls(
                groups=groups,
                folded_count=getattr(result, 'folded_count', 0),
                total_groups=getattr(result, 'total_groups', len(groups)),
                risks=risks,
                metrics=metrics
            )
        
        # 处理 dict 输入（旧方式，保持兼容）
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
        """从Facade返回的dict或HotspotsResult dataclass创建"""
        # 处理 dataclass 输入（HotspotsResult 有 hotspots 属性）
        if hasattr(d, 'hotspots') and not isinstance(d, dict):
            risks = [RiskItem.from_dict(r) if isinstance(r, dict) else r for r in (getattr(d, 'risks', None) or [])]
            hotspots_data = d.hotspots
            
            hotspots = [
                HotspotItem(
                    symbol=getattr(h, 'symbol', ""),
                    cpu_percent=getattr(h, 'cpu_percent', getattr(h, 'self_pct', 0.0)),
                    inclusive_percent=getattr(h, 'inclusive_percent', getattr(h, 'inclusive_pct', 0.0)),
                    call_count=getattr(h, 'call_count', getattr(h, 'count', 0)),
                    resource_tag=getattr(h, 'resource_tag', "COMPUTE")
                )
                for h in hotspots_data
            ]
            
            top = getattr(d, 'top_symbol', None)
            if not top and hotspots:
                top = hotspots[0].symbol
            
            total = getattr(d, 'total_hotspots', len(hotspots))
            kernel = getattr(d, 'kernel_ratio', 0.0)
            user = getattr(d, 'user_ratio', 0.0)
            
            return cls(
                hotspots=hotspots,
                top_symbol=top,
                total_hotspots=total,
                kernel_ratio=kernel,
                user_ratio=user,
                risks=risks
            )
        
        # 处理 dict 输入
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
        # 处理 dataclass 输入（当 d 已经是 CallersReport 或类似结构时）
        if hasattr(d, 'target'):
            callers_data = getattr(d, 'callers', [])
            risks = [RiskItem.from_dict(r) if isinstance(r, dict) else r for r in getattr(d, 'risks', [])]
            
            callers = [
                CallerInfo(
                    symbol=getattr(c, 'symbol', ""),
                    call_count=getattr(c, 'call_count', getattr(c, 'count', 0)),
                    call_ratio=getattr(c, 'call_ratio', getattr(c, 'ratio', 0.0))
                )
                for c in callers_data
            ]
            
            return cls(
                target=getattr(d, 'target', ""),
                callers=callers,
                hot_paths=getattr(d, 'hot_paths', []),
                risks=risks
            )
        
        # 处理 dict 输入
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
# SysAudit Output Models (replacing dict)
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
    risks: List[RiskItem] = field(default_factory=list)


@dataclass
class CoreDistDetails:
    """核心分布详情（SysAuditOutput.details.core_distribution）"""
    core_count: int = 0
    saturated_cores: List[int] = field(default_factory=list)
    imbalance_level: str = "NORMAL"
    risks: List[RiskItem] = field(default_factory=list)


@dataclass
class CommTopDetails:
    """CommTop详情（SysAuditOutput.details.comm_top）"""
    groups_count: int = 0
    folded_count: int = 0
    total_groups: int = 0
    risks: List[RiskItem] = field(default_factory=list)


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
    risks: List[RiskItem] = field(default_factory=list)


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
