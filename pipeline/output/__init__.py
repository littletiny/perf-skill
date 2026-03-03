#!/usr/bin/env python3
"""
pipeline/output - 输出格式化模块

提供 bottleneck-trace 等工具的结构化输出格式化。
"""

from .bottleneck_trace_builder import (
    BottleneckTraceOutputBuilder,
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
    build_bottleneck_trace_output,
)

__all__ = [
    'BottleneckTraceOutputBuilder',
    'BottleneckTraceResult',
    'EntityDistribution',
    'CallPathCluster',
    'CorrelationFlag',
    'build_bottleneck_trace_output',
]
