#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerfExpert Core Module

核心组件：
- engine: PerfExpertEngine 主引擎
- symbol: Symbol 和 SymbolStack 数据结构
- reliability: 样本可靠性评估
- format_utils: 时间格式化和输出规范工具
- risk_mixin: 标准化风险提示
- output_builder: 统一输出构建器 (V1)
- output_models: 统一数据模型定义 (V2)
- output_adapter: JSON 转换器 (V2)
- output_builder_v2: V2 输出构建器
"""

from .engine import PerfExpertEngine
from .symbol import Symbol, SymbolStack
from .reliability import assess_sample_reliability, format_percentage_with_ci
from .format_utils import (
    format_timestamp, format_time_range, format_duration,
    format_percent, format_core_sec, safe_time_range
)
from .risk_mixin import RiskMixin, RiskAwareOutput
from .live_doc import LiveDoc
from .output_builder import OutputBuilder, AnalysisExecutor

# V2 Output System - Unified Data Models
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
from .output_builder_v2 import OutputBuilderV2, create_risk_info

__all__ = [
    # Core V1
    'PerfExpertEngine',
    'Symbol',
    'SymbolStack',
    'assess_sample_reliability',
    'format_percentage_with_ci',
    'format_timestamp',
    'format_time_range',
    'format_duration',
    'format_percent',
    'format_core_sec',
    'safe_time_range',
    'RiskMixin',
    'RiskAwareOutput',
    'LiveDoc',
    'OutputBuilder',
    'AnalysisExecutor',
    # V2 Output System - Models
    'RiskInfo', 'TimeRange', 'BaseSummary', 'BaseOutput',
    'ProcessItem', 'CommGroupItem', 'HotspotItem', 'ClusterItem',
    'ProcessSummary', 'CommGroupSummary', 'HotspotSummary', 'ClusterSummary',
    'ProcessTopOutput', 'CommTopOutput', 'HotspotsOutput', 'ClustersOutput',
    'ClusterCommOutput',
    # V2 Output System - Utils
    'OUTPUT_TYPE_MAP', 'get_output_classes',
    'OutputAdapter', 'CompactOutputAdapter', 'to_json_output', 'print_json_output',
    'OutputBuilderV2', 'create_risk_info',
]
