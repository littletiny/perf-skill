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

__all__ = [
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
    'AnalysisExecutor'
]
