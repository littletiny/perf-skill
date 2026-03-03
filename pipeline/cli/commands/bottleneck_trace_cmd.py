#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottleneck-trace CLI 命令实现

命令: shecr bottleneck-trace

参数：
    --auto-detect          # 自动检测瓶颈进程
    --comm COMM            # 分析指定进程
    --pid PID              # 分析指定 PID
    --start-time TIME      # 开始时间（ISO 8601）
    --end-time TIME        # 结束时间
    --hotspots-limit N     # 热点分析数量（默认 20）
    --callers-limit N      # 调用链数量（默认 10）
    --max-depth N          # 最大调用深度（默认 5）
    --verbose              # 详细输出

职责：
1. 解析参数
2. 加载 samples 数据
3. 调用 BottleneckTracer.trace()
4. 使用 BottleneckTraceOutputBuilder 格式化输出
5. 打印结果

不使用 regex，错误处理简单（let it crash）。
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.bottleneck_tracer import BottleneckTraceAdapter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from output.bottleneck_trace_builder import (
    BottleneckTraceOutputBuilder,
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
)

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


# =============================================================================
# CLI 命令
# =============================================================================

@command("bottleneck-trace")
def cmd_bottleneck_trace(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> str:
    """
    [Composite] 瓶颈深度追踪命令
    
    自动识别CPU瓶颈进程并进行深度分析，生成四段式报告：
    - [ENTITY_DISTRIBUTION_MATRIX]: 实体分布矩阵
    - [CONVERGENCE_TRACE]: 收敛追踪（调用路径聚类）
    - [CORRELATION_FLAGS]: 关联标志
    - [DATA_SUMMARY]: 数据摘要
    
    Args:
        --data: 数据文件路径（必需）
        --comm: 指定目标进程（可选，未指定时自动识别）
        --pid: 指定目标 PID（可选）
        --start-time: 开始时间过滤（ISO 8601）
        --end-time: 结束时间过滤（ISO 8601）
        --hotspots-limit: 热点分析数量（默认 20）
        --callers-limit: 调用链数量（默认 10）
        --max-depth: 最大调用深度（默认 5）
        --verbose: 详细输出
    """
    # 解析参数
    target_comm = getattr(args, 'comm', None)
    hotspots_limit = getattr(args, 'hotspots_limit', 20)
    callers_limit = getattr(args, 'callers_limit', 10)
    max_depth = getattr(args, 'max_depth', 5)
    verbose = getattr(args, 'verbose', False)
    
    facade = AnalysisFacade(engine)
    adapter = BottleneckTraceAdapter(facade)
    
    # 执行瓶颈追踪分析，直接获取 BottleneckTraceResult
    result = adapter.trace(samples, target_comm=target_comm)
    
    # 从结果中提取信息用于风险记录
    actual_comm = result.entity_distribution[0].comm if result.entity_distribution else (target_comm or "unknown")
    risk_level = result._risk.level
    risk_message = result._risk.message
    
    # 使用 BottleneckTraceOutputBuilder 格式化输出
    output_builder = BottleneckTraceOutputBuilder(result)
    output_text = output_builder.build()
    
    # 打印结果
    print(output_text)
    
    # 记录风险到 Trace
    if risk_level in ["critical", "warning"]:
        builder.record_risk(risk_level, risk_message, result._risk.hint)
    
    return output_text


# =============================================================================
# 命令注册辅助函数
# =============================================================================

def register_bottleneck_trace_command(subparsers):
    """
    注册 bottleneck-trace 命令参数
    
    Args:
        subparsers: argparse subparsers 对象
    """
    parser = subparsers.add_parser(
        'bottleneck-trace',
        help="[Composite] Bottleneck trace - deep analysis of CPU bottlenecks with four-section output"
    )
    
    # 必需参数
    parser.add_argument("--data", required=True, help="Path to perf script output file")
    
    # 目标选择参数
    parser.add_argument("--auto-detect", action="store_true",
                        help="Auto detect bottleneck process")
    parser.add_argument("--comm", type=str,
                        help="Target process name to analyze")
    parser.add_argument("--pid", type=int,
                        help="Target PID to analyze")
    
    # 时间范围参数
    parser.add_argument("--start-time", type=str,
                        help="Start time filter (ISO 8601 format)")
    parser.add_argument("--end-time", type=str,
                        help="End time filter (ISO 8601 format)")
    
    # 分析控制参数
    parser.add_argument("--hotspots-limit", type=int, default=20,
                        help="Number of hotspots to analyze (default: 20)")
    parser.add_argument("--callers-limit", type=int, default=10,
                        help="Number of call chains to analyze (default: 10)")
    parser.add_argument("--max-depth", type=int, default=5,
                        help="Maximum call chain depth (default: 5)")
    
    # 输出控制参数
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    
    # 采样频率
    parser.add_argument("--freq", type=int, default=19, metavar="HZ",
                        help="Sampling frequency in Hz (default: 19)")
