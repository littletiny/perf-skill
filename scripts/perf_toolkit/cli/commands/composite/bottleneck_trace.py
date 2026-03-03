#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottleneck-trace 命令实现

从 composite/bottleneck_trace.py 迁移而来
使用 V2 强类型输出模型（无裸 Dict）
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from config.defaults import (
    DiagnosisType, AttentionFlag, RiskPattern,
    Thresholds, CompositeDefaults
)

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import (
    BottleneckTraceOutput, BottleneckProfile,
    HotspotOutputItem, HotspotsOutputData,
    CallerOutputItem, CallChainAnalysis, ConvergencePath,
    RootCauseAnalysis
)
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator
from perf_toolkit.composite.models import (
    BottleneckAnalysis, HotspotsReport, CallersReport
)
from perf_toolkit.composite.bottleneck_trace import (
    _find_bottleneck_comm,
    _analyze_bottleneck,
    _convert_hotspots_result,
    _convert_callers_result,
)

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


def _convert_to_hotspots_output(hotspots_report: HotspotsReport) -> HotspotsOutputData:
    """转换 HotspotsReport 为 HotspotsOutputData（强类型）"""
    items = [
        HotspotOutputItem(
            symbol=hs.symbol,
            self_pct=hs.cpu_percent / 100.0,  # 转换为小数
            inclusive_pct=hs.inclusive_percent / 100.0,
            resource_tag=hs.resource_tag,
            attention_flag=AttentionFlag.X0 if hs.resource_tag == "LOCK" and i == 0 else ""
        )
        for i, hs in enumerate(hotspots_report.hotspots[:5])
    ]
    
    return HotspotsOutputData(
        top_symbol=hotspots_report.top_symbol,
        total_hotspots=hotspots_report.total_hotspots,
        kernel_ratio=hotspots_report.kernel_ratio / 100.0,
        user_ratio=hotspots_report.user_ratio / 100.0,
        items=items
    )


def _convert_to_call_chain_analysis(
    callers_report: CallersReport,
    target_comm: str
) -> CallChainAnalysis:
    """转换 CallersReport 为 CallChainAnalysis（强类型）"""
    top_callers = [
        CallerOutputItem(
            symbol=caller.symbol,
            call_ratio=caller.call_ratio / 100.0,
            call_stack=caller.symbol.split(" <- ") if " <- " in caller.symbol else [caller.symbol]
        )
        for caller in callers_report.callers[:3]
    ]
    
    # 构建聚合路径描述
    convergence = None
    if top_callers:
        path_desc = f"[User_Logic:{target_comm}]"
        if top_callers[0].call_stack:
            path_desc += " → " + " → ".join(top_callers[0].call_stack[:3])
        convergence = ConvergencePath(
            description=path_desc,
            impact=f"热点函数 {callers_report.target} 的调用来源"
        )
    
    return CallChainAnalysis(
        target=callers_report.target,
        convergence_path=convergence,
        top_callers=top_callers
    )


def _build_root_cause(
    bottleneck: BottleneckAnalysis,
    target_comm: str
) -> Optional[RootCauseAnalysis]:
    """构建根因分析"""
    if not bottleneck.found:
        return None
    
    # 根据诊断类型构建根因描述
    if bottleneck.diagnosis == DiagnosisType.BOTTLENECK:
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 单核瓶颈",
            evidence=f"Monopoly={bottleneck.monopoly:.2f}, 单进程独占 CPU",
            mechanism="单进程无法利用多核，导致串行化执行",
            victim="业务请求处理延迟增加"
        )
    elif bottleneck.diagnosis == DiagnosisType.STORM:
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 进程风暴",
            evidence=f"高频率进程创建，资源消耗在进程管理上",
            mechanism="频繁创建/销毁进程导致系统开销增加",
            victim="正常业务进程被资源竞争影响"
        )
    elif bottleneck.diagnosis == DiagnosisType.UNBALANCED:
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 负载不均衡",
            evidence=f"CV={bottleneck.cv:.2f}, PID 间负载差异大",
            mechanism="部分 PID 过载，其他 PID 空闲",
            victim="整体吞吐量受限"
        )
    
    return None


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
            
            return BottleneckTraceOutput(
                _risk=risk,
                target_comm="",
                bottleneck_profile=BottleneckProfile(found=False),
                hotspots=HotspotsOutputData(),
                time_range=TimeRange.from_timestamps(
                    samples[0].ts if hasattr(samples[0], 'ts') else samples[0].get('ts') if samples else None,
                    samples[-1].ts if hasattr(samples[-1], 'ts') else samples[-1].get('ts') if len(samples) > 1 else None
                )
            )
    
    # ========== Phase 2: 瓶颈分析 ==========
    
    bottleneck_analysis = _analyze_bottleneck(facade, samples, target_comm)
    
    # 转换为 BottleneckProfile
    bottleneck_profile = BottleneckProfile(
        found=bottleneck_analysis.found,
        comm=bottleneck_analysis.comm,
        total_cpu=bottleneck_analysis.total_cpu,
        kernel_ratio=bottleneck_analysis.kernel_ratio,
        pid_count=bottleneck_analysis.pid_count,
        cv=bottleneck_analysis.cv,
        monopoly=bottleneck_analysis.monopoly,
        diagnosis=bottleneck_analysis.diagnosis,
        impact_score=bottleneck_analysis.impact_score
    )
    
    # ========== Phase 3: 热点分析 ==========
    
    hotspots_result = facade.analyze_hotspots(samples, comm=target_comm, top_n=top_n)
    hotspots_report = _convert_hotspots_result(hotspots_result)
    hotspots_output = _convert_to_hotspots_output(hotspots_report)

    # ========== Phase 4: 调用链溯源 ==========

    call_chain: Optional[CallChainAnalysis] = None
    if hotspots_report.top_symbol:
        callers_result = facade.analyze_callers(samples, target_symbol=hotspots_report.top_symbol, comm=target_comm)
        callers_report = _convert_callers_result(callers_result)
        call_chain = _convert_to_call_chain_analysis(callers_report, target_comm)
    
    # ========== Phase 5: Risk聚合与输出 ==========
    
    aggregator = RiskAggregator()
    aggregator.add_risks(bottleneck_analysis.risks)
    aggregator.add_risks(hotspots_report.risks)
    if call_chain:
        # 添加调用链相关的 risk（从 callers_report 获取）
        pass
    
    aggregated = aggregator.aggregate()
    
    # 记录到Trace（只记录一次）
    if aggregated.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated.level,
            f"[{target_comm}] {aggregated.message}",
            aggregated.hint
        )
    
    # 构建 RiskInfo，嵌入 SHECR Attention Flags
    attention_flag = (
        AttentionFlag.X0 if bottleneck_analysis.monopoly > Thresholds.MONOPOLY_HIGH 
        else AttentionFlag.X1 if bottleneck_analysis.cv > Thresholds.CV_UNBALANCED 
        else ""
    )
    risk = RiskInfo(
        level=aggregated.level,
        message=f"{attention_flag} {aggregated.message}" if attention_flag else aggregated.message,
        hint=f"<XA> {aggregated.hint}" if aggregated.hint else "",
        patterns=aggregated.patterns,
        pending_targets=aggregated.pending_targets
    )
    
    # 构建根因分析
    root_cause = _build_root_cause(bottleneck_analysis, target_comm)
    
    # 构建建议
    recommendations = []
    if bottleneck_analysis.monopoly > Thresholds.MONOPOLY_HIGH:
        recommendations.append(f"{AttentionFlag.XA} 执行 find-callers --target {hotspots_report.top_symbol} 溯源热点")
    if bottleneck_analysis.kernel_ratio > Thresholds.KERNEL_RATIO_HIGH:
        recommendations.append(f"{AttentionFlag.XA} 执行 cluster-paths --comm {target_comm} 分析内核调用")
    recommendations.append(f"{AttentionFlag.XA} 执行 sys-audit 查看系统全局状态")
    
    # 构建输出（强类型，无裸 Dict）
    time_range = TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if len(samples) > 1 else None
    )
    
    output = BottleneckTraceOutput(
        _risk=risk,
        target_comm=target_comm,
        bottleneck_profile=bottleneck_profile,
        hotspots=hotspots_output,
        call_chain=call_chain,
        root_cause=root_cause,
        recommendations=recommendations,
        time_range=time_range
    )
    
    return output
