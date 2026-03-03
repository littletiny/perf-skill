#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerfExpert Core Module

核心组件：
- engine: PerfExpertEngine 主引擎
- symbol: Symbol 和 SymbolStack 数据结构
- reliability: 样本可靠性评估
- format_utils: 时间格式化和输出规范工具
- output_models: 统一数据模型定义
- output_adapter: JSON 转换器
- output_builder: 输出构建器
"""

from .engine import PerfExpertEngine
from .symbol import Symbol, SymbolStack
from .engine_types import (
    UserKernelStats, CPUUtilization, ProcessCPUInfo, CommCPUInfo,
    CoreCPUInfo, SymbolCPUInfo, ProcessLifecycle, LifecycleEvent,
    LifecycleStats, CallerInfo, CallEdge, CallGraph
)
from .reliability import assess_sample_reliability, format_percentage_with_ci
from .format_utils import (
    format_timestamp, format_time_range, format_duration,
    format_percent, format_weight, safe_time_range
)
from .risk_config import RiskDisplayConfig, get_risk_config, clear_risk_config_cache
from .trace import Trace

# Output System - Unified Data Models
from .output_models import (
    # Risk & Base
    RiskInfo, TimeRange, BaseSummary, BaseOutput,
    # Items
    ProcessItem, CommGroupItem, HotspotItem, ClusterItem,
    # Summaries
    ProcessSummary, CommGroupSummary, HotspotSummary, ClusterSummary,
    # Outputs
    ProcessTopOutput, CommTopOutput, HotspotsOutput, ClustersOutput,
    ClusterCommOutput,
    # Registry
    OUTPUT_TYPE_MAP, get_output_classes,
)
from .output_adapter import (
    OutputAdapter, CompactOutputAdapter,
    to_json_output, print_json_output,
)
from .output_builder import OutputBuilder
from .command_decorator import command

__all__ = [
    # Core Engine
    'PerfExpertEngine',
    'Symbol',
    'SymbolStack',
    # Engine Types
    'UserKernelStats', 'CPUUtilization', 'ProcessCPUInfo', 'CommCPUInfo',
    'CoreCPUInfo', 'SymbolCPUInfo', 'ProcessLifecycle', 'LifecycleEvent',
    'LifecycleStats', 'CallerInfo', 'CallEdge', 'CallGraph',
    'assess_sample_reliability',
    'format_percentage_with_ci',
    'format_timestamp',
    'format_time_range',
    'format_duration',
    'format_percent',
    'format_weight',
    'safe_time_range',
    'RiskDisplayConfig',
    'get_risk_config',
    'clear_risk_config_cache',
    'Trace',
    # Output System - Models
    'RiskInfo', 'TimeRange', 'BaseSummary', 'BaseOutput',
    'ProcessItem', 'CommGroupItem', 'HotspotItem', 'ClusterItem',
    'ProcessSummary', 'CommGroupSummary', 'HotspotSummary', 'ClusterSummary',
    'ProcessTopOutput', 'CommTopOutput', 'HotspotsOutput', 'ClustersOutput',
    'ClusterCommOutput',
    # Output System - Utils
    'OUTPUT_TYPE_MAP', 'get_output_classes',
    'OutputAdapter', 'CompactOutputAdapter', 'to_json_output', 'print_json_output',
    'OutputBuilder',    'command',
]
