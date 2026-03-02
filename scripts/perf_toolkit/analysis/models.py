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
    
    def to_dict(self) -> dict:
        """转换为 dict（供 Facade 聚合使用）"""
        return {
            "level": self.level,
            "message": self.message,
            "hint": self.hint,
            "patterns": self.patterns,
            "pending_targets": self.pending_targets,
            "action_required": self.action_required
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Risk':
        """从 dict 创建 Risk"""
        return cls(
            level=d.get("level", "none"),
            message=d.get("message", ""),
            hint=d.get("hint", ""),
            patterns=d.get("patterns", []),
            pending_targets=d.get("pending_targets", [])
        )


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
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "symbol": self.symbol,
            "self_pct": self.self_pct,
            "inclusive_pct": self.inclusive_pct,
            "is_kernel": self.is_kernel
        }


@dataclass
class CoreStat:
    """核心统计数据结构 - CoreDistAnalyzer 内部使用"""
    cpu_id: int
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "cpu_id": self.cpu_id,
            "total_cpu": self.total_cpu,
            "kernel_cpu": self.kernel_cpu,
            "user_cpu": self.user_cpu
        }


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
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "type": self.type,
            "cpu_id": self.cpu_id,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "prev_util": self.prev_util,
            "curr_util": self.curr_util,
            "next_util": self.next_util,
            "z_score": self.z_score
        }


@dataclass
class PathCluster:
    """路径聚类数据结构 - PathClustersAnalyzer 内部使用"""
    cluster_id: str
    path_signature: str
    depth: int
    weight: float
    cpu_util: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "cluster_id": self.cluster_id,
            "path_signature": self.path_signature,
            "depth": self.depth,
            "weight": self.weight,
            "cpu_util": self.cpu_util
        }


@dataclass
class SymbolCluster:
    """符号聚类数据结构 - SymbolClustersAnalyzer 内部使用"""
    group: str
    ratio: float
    weight: float
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "group": self.group,
            "ratio": self.ratio,
            "weight": self.weight
        }


@dataclass
class ProcessVariety:
    """进程多样性数据结构 - ProcessVarietyAnalyzer 内部使用"""
    comm: str
    pids_per_min: int
    cpu_util: float
    behavior: str                     # "normal" | "process_storm"
    pid_count: int = 0
    samples_per_pid: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为 dict"""
        return {
            "comm": self.comm,
            "pids_per_min": self.pids_per_min,
            "cpu_util": self.cpu_util,
            "behavior": self.behavior,
            "pid_count": self.pid_count,
            "samples_per_pid": self.samples_per_pid
        }


@dataclass
class AnalysisResult:
    """
    统一分析结果结构
    
    所有 Analyzer 返回的标准结构，供 Facade 聚合使用。
    """
    result: dict = field(default_factory=dict)
    risks: List[Risk] = field(default_factory=list)
    metrics: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """转换为 dict（供 Facade 使用）"""
        return {
            "result": self.result,
            "risks": [r.to_dict() for r in self.risks],
            "metrics": self.metrics
        }
