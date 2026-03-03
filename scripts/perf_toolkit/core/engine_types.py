#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine Data Types - Structured data classes for Engine return values

替代裸 dict，提供：
- 明确的字段定义（IDE 友好）
- 类型检查支持
- 文档自描述
- 避免拼写错误

设计原则：
- 内部处理使用 dataclass
- 仅在边界处转换为 dict（如果需要）
- 字段命名直接，不使用缩写
- 不可变类型使用 frozen=True
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class RiskLevel(Enum):
    """风险等级枚举
    
    对应 SHECR 方法论中的 attention flags:
    - CRITICAL: X0 - 关键问题，必须解决
    - WARNING: X1 - 警告，需要关注
    - INFO: X2 - 信息提示
    - NONE: 无风险
    """
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


class DataQualityLevel(Enum):
    """数据质量等级"""
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# =============================================================================
# CPU Utilization Types
# =============================================================================

@dataclass(frozen=True)
class UserKernelStats:
    """用户态/内核态 CPU 统计
    
    Attributes:
        user_core_sec: 用户态核心秒数
        kernel_core_sec: 内核态核心秒数
        total_core_sec: 总核心秒数
        user_records: 用户态样本数
        kernel_records: 内核态样本数
    """
    user_core_sec: float = 0.0
    kernel_core_sec: float = 0.0
    total_core_sec: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass(frozen=True)
class CPUUtilization:
    """CPU 利用率（整体统计）
    
    Attributes:
        total_pct: 总利用率百分比 (0-100)
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        total_core_seconds: 总核心秒数
        user_core_seconds: 用户态核心秒数
        kernel_core_seconds: 内核态核心秒数
        duration: 采样持续时间（秒）
        user_records: 用户态样本数
        kernel_records: 内核态样本数
    """
    total_pct: float = 0.0
    user_pct: float = 0.0
    kernel_pct: float = 0.0
    total_core_seconds: float = 0.0
    user_core_seconds: float = 0.0
    kernel_core_seconds: float = 0.0
    duration: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass(frozen=True)
class ProcessCPUInfo:
    """进程级 CPU 信息
    
    Attributes:
        comm: 进程名
        pid: 进程 ID
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
    """
    comm: str
    pid: str
    total_pct: float
    user_pct: float
    kernel_pct: float


@dataclass(frozen=True)
class PidCPUInfo:
    """PID 级 CPU 信息（按 PID 聚合，合并相同 PID 的不同 comm）
    
    Attributes:
        pid: 进程 ID
        comm: 进程名（使用出现次数最多的 comm）
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        sample_count: 样本数
    """
    pid: int
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    sample_count: int = 0


@dataclass(frozen=True)
class CommCPUInfo:
    """进程组（comm）级 CPU 信息
    
    Attributes:
        comm: 进程组名
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        pid_count: 包含的 PID 数量
        pids: PID 集合
    """
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    pid_count: int
    pids: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CoreCPUInfo:
    """核心级 CPU 信息
    
    Attributes:
        cpu_id: CPU 核心 ID
        total_pct: 总利用率百分比
        kernel_pct: 内核态利用率百分比
        user_pct: 用户态利用率百分比
    """
    cpu_id: int
    total_pct: float
    kernel_pct: float
    user_pct: float = 0.0


@dataclass
class SymbolCPUInfo:
    """符号级 CPU 信息
    
    Attributes:
        self_pct: 各符号的自耗时百分比
        inclusive_pct: 各符号的包含耗时百分比
        core_sec: 各符号的核心秒数
        self_core_sec: 各符号的自耗时核心秒数
        total_core_sec: 总核心秒数
    """
    self_pct: Dict[str, float] = field(default_factory=dict)
    inclusive_pct: Dict[str, float] = field(default_factory=dict)
    core_sec: Dict[str, float] = field(default_factory=dict)
    self_core_sec: Dict[str, float] = field(default_factory=dict)
    total_core_sec: float = 0.0


# =============================================================================
# Process Lifecycle Types
# =============================================================================

@dataclass(frozen=True)
class LifecycleEvent:
    """进程生命周期事件
    
    Attributes:
        pid: 进程 ID
        comm: 进程名
        timestamp: 事件发生时间戳
        type: 事件类型 ("spawn" | "exit")
        stack: 首次出现时的调用栈（可选，仅 spawn 事件有）
    """
    pid: str
    comm: str
    timestamp: float
    type: str  # "spawn" | "exit"
    stack: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class LifecycleStats:
    """生命周期统计
    
    Attributes:
        total_unique_pids: 唯一 PID 总数
        duration_sec: 观察持续时间
        avg_lifetime_sec: 平均生命周期（秒）
    """
    total_unique_pids: int = 0
    duration_sec: float = 0.0
    avg_lifetime_sec: float = 0.0


@dataclass
class ProcessLifecycle:
    """进程生命周期信息
    
    用于计算 Spawn Rate（进程产生速率），检测短生命周期风暴。
    
    Attributes:
        spawn_events: 进程创建事件列表
        exit_events: 进程退出事件列表
        spawn_rate: 进程产生速率（每秒）
        lifecycle_stats: 生命周期统计
    """
    spawn_events: List[LifecycleEvent] = field(default_factory=list)
    exit_events: List[LifecycleEvent] = field(default_factory=list)
    spawn_rate: float = 0.0
    lifecycle_stats: LifecycleStats = field(default_factory=LifecycleStats)


# =============================================================================
# Call Graph Types
# =============================================================================

@dataclass(frozen=True)
class CallerInfo:
    """调用者信息
    
    Attributes:
        symbol: 调用者符号名
        call_count: 调用次数
        total_weight: 总权重
        call_ratio: 调用比例
    """
    symbol: str
    call_count: int
    total_weight: float
    call_ratio: float = 0.0


@dataclass(frozen=True)
class CallEdge:
    """调用边信息
    
    Attributes:
        callee: 被调用者符号
        count: 调用次数
        weight: 权重
    """
    callee: str
    count: int
    weight: float


@dataclass
class CallGraph:
    """调用图
    
    Attributes:
        callers: 调用者列表
        call_graph: 调用图结构（调用者 -> 被调用者列表）
        hot_paths: 热点调用路径
    """
    callers: List[CallerInfo] = field(default_factory=list)
    call_graph: Dict[str, List[CallEdge]] = field(default_factory=dict)
    hot_paths: List[str] = field(default_factory=list)


# =============================================================================
# Sample Types
# =============================================================================

@dataclass(frozen=True)
class Sample:
    """单个样本数据（替代裸 dict）
    
    这是 Core Layer 的基础数据单元，所有分析都基于此结构。
    
    Attributes:
        comm: 进程名
        pid: 进程 ID
        cpu: CPU 核心 ID
        ts: 时间戳（Unix timestamp）
        core_per_sec: 每秒核心数（可选，用于预计算数据）
        stack: 调用栈（SymbolStack 对象，可选）
    """
    comm: str
    pid: str
    cpu: int
    ts: float
    core_per_sec: Optional[float] = None
    stack: Optional[Any] = None  # SymbolStack 对象，延迟导入避免循环依赖


@dataclass(frozen=True)
class FilterCriteria:
    """样本过滤条件
    
    Attributes:
        start_time: 开始时间戳
        end_time: 结束时间戳
        cpu_id: CPU ID 过滤
        pid: PID 过滤
        comm: 进程名过滤（精确匹配）
        comm_regex: 进程名过滤（正则匹配）
    """
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    cpu_id: Optional[int] = None
    pid: Optional[int] = None
    comm: Optional[str] = None
    comm_regex: Optional[str] = None


# =============================================================================
# Quality Metrics Types
# =============================================================================

@dataclass(frozen=True)
class QualityMetrics:
    """数据质量指标
    
    Attributes:
        total_samples: 总样本数
        time_range_seconds: 时间范围（秒）
        cpu_count: CPU 核心数
        level: 质量等级
        warning: 质量警告信息
    """
    total_samples: int = 0
    time_range_seconds: float = 0.0
    cpu_count: int = 0
    level: str = "unknown"
    warning: str = ""


@dataclass(frozen=True)
class DataQualityMetrics:
    """详细数据质量指标
    
    Attributes:
        record_count: 记录数
        duration_sec: 持续时间（秒）
        cpu_utilization_pct: CPU 利用率百分比
        utilization_source: 利用率来源
        total_weight: 总权重
        avg_weight: 平均权重
    """
    record_count: int = 0
    duration_sec: float = 0.0
    cpu_utilization_pct: float = 0.0
    utilization_source: str = "unknown"
    total_weight: Optional[float] = None
    avg_weight: Optional[float] = None


# =============================================================================
# Risk and Time Types - 已迁移至 core.models
# =============================================================================
# Note: RiskInfo 和 TimeRange 现已定义在 core.models 中，
# 请从 core.models 导入以避免循环依赖
# from .models import RiskInfo, TimeRange
