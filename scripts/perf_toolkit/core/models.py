#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Unified Models - 统一数据模型

为三层架构提供统一的数据模型定义，消除重复定义。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


# =============================================================================
# Risk Model - 统一风险信息结构（全项目唯一 Risk 类）
# =============================================================================

@dataclass
class RiskInfo:
    """
    统一风险信息结构 - 所有输出的第一个字段
    
    遵循 output-format-spec.md 规范，风险置顶原则。
    替代原有的 Risk、RiskItem 等多个重复定义。
    
    Attributes:
        level: 风险等级 ("critical" | "warning" | "info" | "none")
        message: 风险描述信息
        hint: 建议操作或提示
        patterns: 匹配的 attention flags 列表 (X0, X1, X2, XA)
        pending_targets: 待处理目标列表
        source: 来源标识（如 "comm_top", "anomalies"）
    """
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    source: str = ""  # 来源分析器

    def __post_init__(self):
        """验证 level 并自动计算 action_required"""
        valid_levels = ["critical", "warning", "info", "none"]
        if self.level not in valid_levels:
            self.level = "info"

    @property
    def action_required(self) -> bool:
        """是否需要立即行动（自动计算）"""
        return self.level in ["critical", "warning"]

    @classmethod
    def from_risk_list(cls, risks: List['RiskInfo']) -> 'RiskInfo':
        """
        从风险列表中选择最高优先级的风险
        
        Args:
            risks: RiskInfo 列表
            
        Returns:
            最高优先级的 RiskInfo，如果列表为空返回 level="none"
        """
        if not risks:
            return cls(level="none")
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        return min(risks, key=lambda r: priority.get(r.level, 2))


# =============================================================================
# Time Range Model
# =============================================================================

@dataclass(frozen=True)
class TimeRange:
    """
    时间范围结构 - ISO 8601 格式
    
    Attributes:
        start_time: 开始时间（ISO 8601 格式字符串）
        end_time: 结束时间（ISO 8601 格式字符串）
        duration: 持续时间（秒）
    """
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: float = 0.0

    @classmethod
    def from_timestamps(cls, start_ts: Optional[float], end_ts: Optional[float]) -> 'TimeRange':
        """
        从时间戳创建 TimeRange
        
        Args:
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            
        Returns:
            TimeRange 实例
        """
        if start_ts is None or end_ts is None:
            return cls()
        return cls(
            start_time=datetime.fromtimestamp(start_ts).isoformat() if start_ts else None,
            end_time=datetime.fromtimestamp(end_ts).isoformat() if end_ts else None,
            duration=round(end_ts - start_ts, 2)
        )


# =============================================================================
# Summary Models
# =============================================================================

@dataclass
class Summary:
    """
    统一摘要基类
    
    所有具体的摘要结构都继承此类。
    """
    pass


@dataclass
class ProcessSummary(Summary):
    """进程统计摘要"""
    total_processes: int = 0
    shown_processes: int = 0


@dataclass
class CommGroupSummary(Summary):
    """进程组统计摘要"""
    total_comm_groups: int = 0
    high_kernel_groups: int = 0


@dataclass
class HotspotSummary(Summary):
    """热点函数摘要"""
    total_hotspots: int = 0
    shown_hotspots: int = 0


@dataclass
class ClusterSummary(Summary):
    """聚类摘要"""
    clusters_found: int = 0
    shown_clusters: int = 0


@dataclass
class AnomalySummary(Summary):
    """异常检测摘要"""
    total_anomalies: int = 0
    spike_count: int = 0
    drop_count: int = 0


