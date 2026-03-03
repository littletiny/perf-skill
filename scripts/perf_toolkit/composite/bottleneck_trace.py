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

注意：CLI 命令已迁移到 cli/commands/composite/bottleneck_trace.py
本文件保留辅助函数供 CLI 命令使用
"""

from typing import Optional

from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator
from perf_toolkit.composite.models import (
    RiskItem, ProcessGroup, BottleneckAnalysis,
    HotspotsReport, CallersReport,
    HotspotData, HotspotsDetails, CallerData, CallersDetails
)


# 以下辅助函数保留供 cli/commands/composite/bottleneck_trace.py 使用

def _find_bottleneck_comm(facade: AnalysisFacade, samples) -> Optional[str]:
    """
    自动识别瓶颈进程
    
    策略：通过CommTop获取按危害指数排序的进程组，
    找出第一个BOTTLENECK诊断的进程。
    """
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    # 使用CommTopAnalyzer获取带metrics的结果
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=20, include_metrics=True)
    
    # 从result中提取all_groups（处理 CommTopResult dataclass）
    metrics = result.metrics if hasattr(result, 'metrics') else result.get("metrics", {})
    # 处理 metrics 可能是 dict 或 dataclass 的情况
    if hasattr(metrics, 'all_groups'):
        all_groups_data = metrics.all_groups
    elif isinstance(metrics, dict):
        all_groups_data = metrics.get("all_groups", [])
    else:
        all_groups_data = []
    
    all_groups = [
        ProcessGroup(
            comm=g["comm"] if isinstance(g, dict) else getattr(g, 'comm', ''),
            total_cpu=g.get("total_cpu", 0.0) if isinstance(g, dict) else getattr(g, 'total_cpu', 0.0),
            diagnosis=g.get("diagnosis", "HEALTHY") if isinstance(g, dict) else getattr(g, 'diagnosis', 'HEALTHY'),
            monopoly=g.get("monopoly", 0.0) if isinstance(g, dict) else getattr(g, 'monopoly', 0.0)
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


def _analyze_bottleneck(facade: AnalysisFacade, samples, comm: str) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征"""
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    # 找到目标comm（处理 CommTopResult dataclass）
    metrics = result.metrics if hasattr(result, 'metrics') else result.get("metrics", {})
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
