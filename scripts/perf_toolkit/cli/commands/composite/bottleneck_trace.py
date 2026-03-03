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


def _find_bottleneck_comm(facade, samples) -> Optional[str]:
    """
    自动识别瓶颈进程
    
    策略：通过CommTop获取按危害指数排序的进程组，
    找出第一个BOTTLENECK诊断的进程。
    """
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    # 使用CommTopAnalyzer获取带metrics的结果
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=20, include_metrics=True)
    
    # 从result中提取all_groups
    metrics = result.metrics
    all_groups_data = metrics.all_groups if metrics else []

    all_groups = [
        ProcessGroup(
            comm=g.comm,
            total_cpu=g.total_cpu,
            diagnosis=g.diagnosis,
            monopoly=g.monopoly
        )
        for g in all_groups_data
    ]
    
    # 找第一个BOTTLENECK
    for group in all_groups:
        if group.diagnosis == "BOTTLENECK":
            return group.comm
    
    # 如果没有明确的BOTTLENECK，返回危害指数最高的
    if all_groups:
        return all_groups[0].comm
    
    return None


def _analyze_bottleneck(facade, samples, comm: str) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征"""
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    # 找到目标comm
    metrics = result.metrics
    target_group: Optional[ProcessGroup] = None

    for g in (metrics.all_groups if metrics else []):
        if g.comm == comm:
            target_group = ProcessGroup(
                comm=g.comm,
                total_cpu=g.total_cpu,
                kernel_cpu=g.kernel_cpu,
                pid_count=g.pid_count,
                cv=g.cv,
                monopoly=g.monopoly,
                diagnosis=g.diagnosis,
                impact_score=g.impact_score
            )
            break
    
    if not target_group:
        return BottleneckAnalysis(
            found=False,
            comm=comm,
            risks=[RiskInfo(
                level="warning",
                message=f"未找到进程 {comm}",
                hint="get-comm-top",
                patterns=["COMM_NOT_FOUND"]
            )]
        )

    # 计算内核占比
    kernel_ratio = target_group.kernel_ratio

    # 生成risks
    risks: list[RiskInfo] = []

    if target_group.monopoly > 0.8:
        risks.append(RiskInfo(
            level="critical",
            message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
            hint=f"get-hotspots --comm {comm}",
            patterns=["SINGLE_CORE_SATURATION"],
            pending_targets=[comm],
            source="bottleneck_trace"
        ))

    if kernel_ratio > 50:
        risks.append(RiskInfo(
            level="warning",
            message=f"{comm} 高内核态 ({kernel_ratio:.1f}%)",
            hint=f"cluster-paths --comm {comm}",
            patterns=["HIGH_KERNEL"],
            pending_targets=[comm],
            source="bottleneck_trace"
        ))
    
    return BottleneckAnalysis(
        found=True,
        comm=comm,
        total_cpu=target_group.total_cpu,
        kernel_ratio=kernel_ratio,
        pid_count=target_group.pid_count,
        cv=target_group.cv,
        monopoly=target_group.monopoly,
        diagnosis=target_group.diagnosis,
        impact_score=target_group.impact_score,
        risks=risks
    )


def _hotspots_to_dataclass(h: HotspotsReport) -> HotspotsDetails:
    """转换HotspotsReport为HotspotsDetails dataclass"""
    hotspots = [
        HotspotData(
            symbol=hs.symbol,
            cpu_percent=hs.cpu_percent,
            resource_tag=hs.resource_tag
        )
        for hs in h.hotspots[:5]
    ]
    
    return HotspotsDetails(
        hotspots=hotspots,
        top_symbol=h.top_symbol,
        total_hotspots=h.total_hotspots,
        risks=h.risks
    )


def _callers_to_dataclass(c: CallersReport) -> CallersDetails:
    """转换CallersReport为CallersDetails dataclass"""
    callers = [
        CallerData(symbol=caller.symbol, call_ratio=caller.call_ratio)
        for caller in c.callers[:3]
    ]
    
    return CallersDetails(
        target=c.target,
        callers=callers,
        risks=c.risks
    )



# =============================================================================
# Conversion Helpers - 显式字段映射（替代已删除的 from_analysis_* 方法）
# =============================================================================

def _convert_hotspots_result(result) -> HotspotsReport:
    """从 Analysis 层的 HotspotsResult 转换为 Composite 层的 HotspotsReport"""
    def infer_tag(symbol: str) -> str:
        """推断资源标签"""
        symbol_lower = symbol.lower()
        if any(k in symbol_lower for k in ['lock', 'mutex', 'spin', 'rwsem']):
            return "LOCK"
        if any(k in symbol_lower for k in ['syscall', 'sys_']):
            return "SYSCALL"
        if any(k in symbol_lower for k in ['schedule', 'switch']):
            return "SCHED"
        if any(k in symbol_lower for k in ['malloc', 'free', 'reclaim']):
            return "MEMORY"
        if any(k in symbol_lower for k in ['read', 'write', 'send', 'recv']):
            return "IO"
        return "COMPUTE"

    hotspots = [
        HotspotItem(
            symbol=h.symbol,
            cpu_percent=h.self_pct,
            inclusive_percent=h.inclusive_pct,
            call_count=getattr(h, 'call_count', 0),
            resource_tag=infer_tag(h.symbol)
        )
        for h in result.hotspots
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="hotspots"
        )
        for r in result.risks
    ]

    top = result.hotspots[0].symbol if result.hotspots else None

    return HotspotsReport(
        hotspots=hotspots,
        top_symbol=top,
        total_hotspots=len(result.hotspots),
        kernel_ratio=result.kernel_ratio,
        user_ratio=result.user_ratio,
        risks=risks
    )


def _convert_callers_result(result) -> CallersReport:
    """从 Analysis 层的 CallersResult 转换为 Composite 层的 CallersReport"""
    callers = [
        CallerInfo(
            symbol=c.symbol,
            call_count=c.call_count,
            call_ratio=c.call_ratio,
            total_weight=c.total_weight
        )
        for c in result.callers
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="callers"
        )
        for r in result.risks
    ]

    hot_paths = [c.symbol for c in callers[:3]]

    return CallersReport(
        target=result.target,
        callers=callers,
        hot_paths=hot_paths,
        risks=risks
    )
