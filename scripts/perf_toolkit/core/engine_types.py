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
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime


# =============================================================================
# CPU Utilization Types
# =============================================================================

@dataclass
class UserKernelStats:
    """用户态/内核态 CPU 统计"""
    user_core_sec: float = 0.0
    kernel_core_sec: float = 0.0
    total_core_sec: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass
class CPUUtilization:
    """CPU 利用率（整体）"""
    total_pct: float = 0.0
    user_pct: float = 0.0
    kernel_pct: float = 0.0
    total_core_seconds: float = 0.0
    user_core_seconds: float = 0.0
    kernel_core_seconds: float = 0.0
    duration: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass
class ProcessCPUInfo:
    """进程 CPU 信息"""
    comm: str
    pid: str
    total_pct: float
    user_pct: float
    kernel_pct: float


@dataclass
class CommCPUInfo:
    """进程组 CPU 信息"""
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    pid_count: int
    pids: Set[str] = field(default_factory=set)


@dataclass
class CoreCPUInfo:
    """核心级 CPU 信息"""
    cpu_id: int
    total_pct: float
    kernel_pct: float
    user_pct: float = 0.0


@dataclass
class SymbolCPUInfo:
    """符号级 CPU 信息"""
    self_pct: Dict[str, float] = field(default_factory=dict)
    inclusive_pct: Dict[str, float] = field(default_factory=dict)
    core_sec: Dict[str, float] = field(default_factory=dict)
    self_core_sec: Dict[str, float] = field(default_factory=dict)
    total_core_sec: float = 0.0


# =============================================================================
# Process Lifecycle Types
# =============================================================================

@dataclass
class LifecycleEvent:
    """生命周期事件"""
    pid: str
    comm: str
    timestamp: float
    type: str  # "spawn" | "exit"


@dataclass
class LifecycleStats:
    """生命周期统计"""
    total_unique_pids: int = 0
    duration_sec: float = 0.0
    avg_lifetime_sec: float = 0.0


@dataclass
class ProcessLifecycle:
    """进程生命周期信息"""
    spawn_events: List[LifecycleEvent] = field(default_factory=list)
    exit_events: List[LifecycleEvent] = field(default_factory=list)
    spawn_rate: float = 0.0
    lifecycle_stats: LifecycleStats = field(default_factory=LifecycleStats)


# =============================================================================
# Call Graph Types
# =============================================================================

@dataclass
class CallerInfo:
    """调用者信息"""
    symbol: str
    call_count: int
    total_weight: float


@dataclass
class CallEdge:
    """调用边信息"""
    callee: str
    count: int
    weight: float


@dataclass
class CallGraph:
    """调用图"""
    callers: List[CallerInfo] = field(default_factory=list)
    call_graph: Dict[str, List[CallEdge]] = field(default_factory=dict)
    hot_paths: List[str] = field(default_factory=list)


# =============================================================================
# Sample Types
# =============================================================================

@dataclass
class Sample:
    """单个样本数据（替代裸 dict）"""
    comm: str
    pid: str
    cpu: int
    ts: float
    core_per_sec: Optional[float]
    # stack 保持为 SymbolStack 对象，不在这里定义


# =============================================================================
# Helper Functions
# =============================================================================

def to_dict(obj) -> Dict:
    """将 dataclass 转换为 dict（用于需要 JSON 序列化的场景）"""
    from dataclasses import asdict, is_dataclass
    
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
