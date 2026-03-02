#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bottleneck Trace - 瓶颈追踪命令

自动识别CPU瓶颈进程并进行深度分析。

分析流程:
1. 识别瓶颈进程（通过Monopoly指标）
2. 热点函数分析
3. 调用链溯源
4. 生成诊断报告
"""

from typing import Optional

from ..core.command_decorator import command
from ..core.output_models import (
    RiskInfo, TimeRange, BottleneckTraceOutput
)
from ..analysis.facade import AnalysisFacade
from .risk_aggregator import RiskAggregator
from .models import (
    RiskItem, ProcessGroup, BottleneckAnalysis,
    HotspotsReport, CallersReport
)


@command("bottleneck-trace")
def cmd_bottleneck_trace(builder, engine, args, samples):
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
                    samples[0].get('ts') if samples else None,
                    samples[-1].get('ts') if len(samples) > 1 else None
                )
            )
            return output
    
    # ========== Phase 2: 瓶颈分析 ==========
    
    bottleneck_analysis = _analyze_bottleneck(facade, samples, target_comm)
    
    # ========== Phase 3: 热点分析 ==========
    
    hotspots_raw = facade.analyze_hotspots(samples, comm=target_comm, top_n=top_n)
    hotspots = HotspotsReport.from_dict(hotspots_raw)
    
    # ========== Phase 4: 调用链溯源 ==========
    
    callers: Optional[CallersReport] = None
    if hotspots.top_symbol:
        callers_raw = facade.analyze_callers(samples, target_symbol=hotspots.top_symbol, comm=target_comm)
        callers = CallersReport.from_dict(callers_raw)
    
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
        pending_targets=aggregated.pending_targets,
        action_required=aggregated.action_required
    )
    
    # 构建输出
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples else None,
        samples[-1].get('ts') if len(samples) > 1 else None
    )
    
    output = BottleneckTraceOutput(
        _risk=risk,
        target_comm=target_comm,
        bottleneck_analysis=_bottleneck_to_dict(bottleneck_analysis),
        hotspots=_hotspots_to_dict(hotspots),
        callers=_callers_to_dict(callers) if callers else None,
        time_range=time_range
    )
    
    return output


def _find_bottleneck_comm(facade: AnalysisFacade, samples) -> Optional[str]:
    """
    自动识别瓶颈进程
    
    策略：通过CommTop获取按危害指数排序的进程组，
    找出第一个BOTTLENECK诊断的进程。
    """
    from ..analysis.comm_top import CommTopAnalyzer
    
    # 使用CommTopAnalyzer获取带metrics的结果
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=20, include_metrics=True)
    
    # 从result中提取all_groups
    metrics = result.get("metrics", {})
    all_groups = [
        ProcessGroup(
            comm=g["comm"],
            total_cpu=g.get("total_cpu", 0.0),
            diagnosis=g.get("diagnosis", "HEALTHY"),
            monopoly=g.get("monopoly", 0.0)
        )
        for g in metrics.get("all_groups", [])
    ]
    
    # 找第一个BOTTLENECK
    for group in all_groups:
        if group.diagnosis == "BOTTLENECK":
            return group.comm
    
    # 如果没有明确的BOTTLENECK，返回危害指数最高的
    if all_groups:
        return all_groups[0].comm
    
    return None


def _analyze_bottleneck(facade: AnalysisFacade, samples, comm: str) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征"""
    from ..analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    # 找到目标comm
    metrics = result.get("metrics", {})
    target_group: Optional[ProcessGroup] = None
    
    for g in metrics.get("all_groups", []):
        if g["comm"] == comm:
            target_group = ProcessGroup(
                comm=g["comm"],
                total_cpu=g.get("total_cpu", 0.0),
                kernel_cpu=g.get("kernel_cpu", 0.0),
                pid_count=g.get("pid_count", g.get("count", 0)),
                cv=g.get("cv", 0.0),
                monopoly=g.get("monopoly", 0.0),
                diagnosis=g.get("diagnosis", "NORMAL"),
                impact_score=g.get("impact_score", 0.0)
            )
            break
    
    if not target_group:
        return BottleneckAnalysis(
            found=False,
            comm=comm,
            risks=[RiskItem(
                level="warning",
                message=f"未找到进程 {comm}",
                hint="get-comm-top",
                patterns=["COMM_NOT_FOUND"]
            )]
        )
    
    # 计算内核占比
    kernel_ratio = target_group.kernel_ratio
    
    # 生成risks
    risks: list[RiskItem] = []
    
    if target_group.monopoly > 0.8:
        risks.append(RiskItem(
            level="critical",
            message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
            hint=f"get-hotspots --comm {comm}",
            patterns=["SINGLE_CORE_SATURATION"],
            pending_targets=[comm]
        ))
    
    if kernel_ratio > 50:
        risks.append(RiskItem(
            level="warning",
            message=f"{comm} 高内核态 ({kernel_ratio:.1f}%)",
            hint=f"cluster-paths --comm {comm}",
            patterns=["HIGH_KERNEL"],
            pending_targets=[comm]
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


def _bottleneck_to_dict(b: BottleneckAnalysis) -> dict:
    """转换BottleneckAnalysis为dict"""
    return {
        "found": b.found,
        "comm": b.comm,
        "total_cpu": b.total_cpu,
        "kernel_ratio": b.kernel_ratio,
        "pid_count": b.pid_count,
        "cv": b.cv,
        "monopoly": b.monopoly,
        "diagnosis": b.diagnosis,
        "impact_score": b.impact_score,
        "risks": [r.to_dict() for r in b.risks]
    }


def _hotspots_to_dict(h: HotspotsReport) -> dict:
    """转换HotspotsReport为dict"""
    return {
        "hotspots": [
            {
                "symbol": hs.symbol,
                "cpu_percent": hs.cpu_percent,
                "resource_tag": hs.resource_tag
            }
            for hs in h.hotspots[:5]
        ],
        "top_symbol": h.top_symbol,
        "total_hotspots": h.total_hotspots,
        "risks": [r.to_dict() for r in h.risks]
    }


def _callers_to_dict(c: CallersReport) -> dict:
    """转换CallersReport为dict"""
    return {
        "target": c.target,
        "callers": [
            {"symbol": caller.symbol, "call_ratio": caller.call_ratio}
            for caller in c.callers[:3]
        ],
        "risks": [r.to_dict() for r in c.risks]
    }
