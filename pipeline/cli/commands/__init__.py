#!/usr/bin/env python3
"""
pipeline/cli/commands - CLI 命令模块

提供 bottleneck-trace 等复合诊断命令的 CLI 实现。
"""

from .bottleneck_trace_cmd import (
    cmd_bottleneck_trace,
    register_bottleneck_trace_command,
)

__all__ = [
    'cmd_bottleneck_trace',
    'register_bottleneck_trace_command',
]
