#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottleneck-trace 命令实现

从 composite/bottleneck_trace.py 迁移而来
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import BottleneckTraceOutput
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator
from perf_toolkit.composite.models import (
    ProcessGroup, BottleneckAnalysis,
    HotspotItem, HotspotData, HotspotsDetails, CallerInfo, CallerData, CallersDetails,
    HotspotsReport, CallersReport
)
from perf_toolkit.composite.bottleneck_trace import (
    _find_bottleneck_comm,
    _analyze_bottleneck,
    _hotspots_to_dataclass,
    _callers_to_dataclass,
    _convert_comm_group,
    _convert_hotspots_result,
    _convert_callers_result,
)

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("bottleneck-trace")
def cmd_bottleneck_trace(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> BottleneckTraceOutput:
    """
    [Composite] 瓶颈追踪命令
    
    自动识别CPU瓶颈进程并进行深度分析
    如未指定--comm，自动识别最主要的瓶颈进程。
    
    Args:
        --comm: 指定目标进程（可选，未指定时自动识别）
    """
    target_comm = getattr(args, 'comm', None)
    top_n = getattr(args, 'top_n', 10)
    
    facade = AnalysisFacade(engine)
    
    # ========== Phase 1: 识别瓶颈 ==========
    
    if not target_comm:
        # 自动识别瓶颈进程
        target_comm = _find_bottleneck_comm(facade, samples)
        if not target_comm:
            # 未发现瓶颈
            risk = RiskInfo(
                level="info",
                message="未检测到明显瓶颈进程",
                hint="尝试运行 sys-audit 进行全面分析"
            )
            
            output = BottleneckTraceOutput(
                _risk=risk,
                target_comm="",
                bottleneck_analysis={},
                hotspots={},
                callers=None,
                time_range=TimeRange.from_timestamps(
                    samples[0].ts if hasattr(samples[0], 'ts') else samples[0].get('ts') if samples else None,
                    samples[-1].ts if hasattr(samples[-1], 'ts') else samples[-1].get('ts') if len(samples) > 1 else None
                )
            )
            return output
    
    # ========== Phase 2: 瓶颈分析 ==========
    
    bottleneck_analysis = _analyze_bottleneck(facade, samples, target_comm)
    
    # ========== Phase 3: 热点分析 ==========
    
    hotspots_result = facade.analyze_hotspots(samples, comm=target_comm, top_n=top_n)
    hotspots = _convert_hotspots_result(hotspots_result)

    # ========== Phase 4: 调用链溯源 ==========

    callers: Optional[CallersReport] = None
    if hotspots.top_symbol:
        callers_result = facade.analyze_callers(samples, target_symbol=hotspots.top_symbol, comm=target_comm)
        callers = _convert_callers_result(callers_result)
    
    # ========== Phase 5: Risk聚合与输出 ==========
    
    aggregator = RiskAggregator()
    aggregator.add_risks(bottleneck_analysis.risks)
    aggregator.add_risks(hotspots.risks)
    if callers:
        aggregator.add_risks(callers.risks)
    
    aggregated = aggregator.aggregate()
    
    # 记录到Trace（只记录一次）
    if aggregated.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated.level,
            f"[{target_comm}] {aggregated.message}",
            aggregated.hint
        )
    
    risk = RiskInfo(
        level=aggregated.level,
        message=aggregated.message,
        hint=aggregated.hint,
        patterns=aggregated.patterns,
        pending_targets=aggregated.pending_targets
    )
    
    # 构建输出
    time_range = TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if len(samples) > 1 else None
    )
    
    output = BottleneckTraceOutput(
        _risk=risk,
        target_comm=target_comm,
        bottleneck_analysis=bottleneck_analysis,
        hotspots=_hotspots_to_dataclass(hotspots),
        callers=_callers_to_dataclass(callers) if callers else None,
        time_range=time_range
    )
    
    return output
