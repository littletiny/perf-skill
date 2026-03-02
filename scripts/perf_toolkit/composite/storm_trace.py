#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Storm Trace - 进程风暴追踪命令

自动识别进程风暴（高SpawnRate）并进行深度分析。

分析流程:
1. 识别风暴进程（通过SpawnRate指标）
2. 分析进程生命周期
3. 溯源风暴来源（调用链分析）
4. 生成诊断报告
"""

from typing import Optional
from collections import defaultdict

from ..core.command_decorator import command
from ..core.output_models import (
    RiskInfo, TimeRange, StormTraceOutput
)
from ..analysis.facade import AnalysisFacade
from .risk_aggregator import RiskAggregator
from .models import (
    RiskItem, ProcessGroup, StormAnalysis,
    LifecycleReport, CreatorInfo, CallersReport
)


@command("storm-trace")
def cmd_storm_trace(builder, engine, args, samples):
    """
    [Composite] 进程风暴追踪命令
    
    自动识别进程风暴并进行深度分析。
    如未指定--comm，自动识别最主要的风暴进程。
    
    Args:
        --comm: 指定目标进程（可选）
    """
    target_comm = getattr(args, 'comm', None)
    
    facade = AnalysisFacade(engine)
    
    # ========== Phase 1: 识别风暴进程 ==========
    
    if not target_comm:
        target_comm = _find_storm_comm(facade, samples)
        if not target_comm:
            risk = RiskInfo(
                level="info",
                message="未检测到进程风暴",
                hint="尝试运行 sys-audit 进行全面分析"
            )
            
            output = StormTraceOutput(
                _risk=risk,
                target_comm="",
                storm_analysis={},
                lifecycle={},
                callers=None,
                time_range=TimeRange.from_timestamps(
                    samples[0].get('ts') if samples else None,
                    samples[-1].get('ts') if len(samples) > 1 else None
                )
            )
            return output
    
    # ========== Phase 2: 风暴分析 ==========
    
    storm_analysis = _analyze_storm(facade, samples, target_comm)
    
    # ========== Phase 3: 生命周期分析 ==========
    
    lifecycle = _analyze_lifecycle(facade, samples, target_comm)
    
    # ========== Phase 4: 溯源分析 ==========
    
    callers: Optional[CallersReport] = None
    # 对高频创建的函数进行溯源
    if lifecycle.top_creators:
        callers_raw = facade.analyze_callers(
            samples, 
            target_symbol=lifecycle.top_creators[0].symbol, 
            comm=target_comm
        )
        callers = CallersReport.from_dict(callers_raw)
    
    # ========== Phase 5: Risk聚合与输出 ==========
    
    aggregator = RiskAggregator()
    aggregator.add_risks(storm_analysis.risks)
    aggregator.add_risks(lifecycle.risks)
    if callers:
        aggregator.add_risks(callers.risks)
    
    aggregated = aggregator.aggregate()
    
    # 记录到Trace
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
    
    output = StormTraceOutput(
        _risk=risk,
        target_comm=target_comm,
        storm_analysis=_storm_to_dict(storm_analysis),
        lifecycle=_lifecycle_to_dict(lifecycle),
        callers=_callers_to_dict(callers) if callers else None,
        time_range=time_range
    )
    
    return output


def _find_storm_comm(facade: AnalysisFacade, samples) -> Optional[str]:
    """
    自动识别风暴进程
    
    策略：找出SpawnRate最高的STORM诊断进程
    """
    from ..analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    metrics = result.get("metrics", {})
    
    # 找所有STORM诊断的进程，按SpawnRate排序
    storm_groups: list[tuple[str, float]] = []
    for g in metrics.get("all_groups", []):
        if g.get("diagnosis") == "STORM":
            storm_groups.append((g["comm"], g.get("spawn_rate", 0.0)))
    
    storm_groups.sort(key=lambda x: x[1], reverse=True)
    
    if storm_groups:
        return storm_groups[0][0]
    
    return None


def _analyze_storm(facade: AnalysisFacade, samples, comm: str) -> StormAnalysis:
    """分析进程风暴特征"""
    from ..analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    metrics = result.get("metrics", {})
    
    # 找到目标comm
    target_group: Optional[ProcessGroup] = None
    for g in metrics.get("all_groups", []):
        if g["comm"] == comm:
            target_group = ProcessGroup(
                comm=g["comm"],
                total_cpu=g.get("total_cpu", 0.0),
                pid_count=g.get("pid_count", g.get("count", 0)),
                spawn_rate=g.get("spawn_rate", 0.0),
                diagnosis=g.get("diagnosis", "NORMAL")
            )
            break
    
    if not target_group:
        return StormAnalysis(
            found=False,
            comm=comm,
            risks=[RiskItem(
                level="warning",
                message=f"未找到进程 {comm}",
                hint="get-comm-top",
                patterns=["COMM_NOT_FOUND"]
            )]
        )
    
    spawn_rate = target_group.spawn_rate
    pid_count = target_group.pid_count
    total_cpu = target_group.total_cpu
    
    # 评估风暴严重程度
    severity = "LOW"
    if spawn_rate > 100:
        severity = "CRITICAL"
    elif spawn_rate > 50:
        severity = "HIGH"
    elif spawn_rate > 20:
        severity = "MEDIUM"
    
    # 生成risks
    risks: list[RiskItem] = []
    if spawn_rate > 50:
        risks.append(RiskItem(
            level="critical",
            message=f"{comm} 严重进程风暴 ({spawn_rate:.1f}/s, {pid_count} PIDs)",
            hint=f"检查 {comm} 的进程创建逻辑，可能存在泄漏",
            patterns=["PROCESS_STORM"],
            pending_targets=[comm]
        ))
    elif spawn_rate > 10:
        risks.append(RiskItem(
            level="warning",
            message=f"{comm} 进程风暴 ({spawn_rate:.1f}/s, {pid_count} PIDs)",
            hint=f"cluster-paths --comm {comm}",
            patterns=["PROCESS_STORM"],
            pending_targets=[comm]
        ))
    
    return StormAnalysis(
        found=True,
        comm=comm,
        spawn_rate=spawn_rate,
        pid_count=pid_count,
        total_cpu=total_cpu,
        severity=severity,
        diagnosis=target_group.diagnosis,
        risks=risks
    )


def _analyze_lifecycle(facade: AnalysisFacade, samples, comm: str) -> LifecycleReport:
    """分析进程生命周期"""
    # 获取生命周期信息
    lifecycle_raw = facade._engine.get_process_lifecycle(samples, comm)
    
    spawn_events = lifecycle_raw.get("spawn_events", [])
    exit_events = lifecycle_raw.get("exit_events", [])
    spawn_rate = lifecycle_raw.get("spawn_rate", 0.0)
    
    # 分析创建热点（哪些函数在创建进程）
    creator_symbols: dict[str, int] = defaultdict(int)
    for event in spawn_events:
        stack = event.get("stack", [])
        if stack:
            creator_symbols[stack[0]] += 1
    
    # 排序创建者
    top_creators = [
        CreatorInfo(symbol=s, count=c)
        for s, c in sorted(creator_symbols.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # 分析生命周期特征
    lifecycle_stats = lifecycle_raw.get("lifecycle_stats", {})
    short_lived = lifecycle_stats.get("short_lived_count", 0)
    leaked = len(spawn_events) - len(exit_events)
    if leaked < 0:
        leaked = 0
    
    # 生成risks
    risks: list[RiskItem] = []
    
    if short_lived > 10:
        risks.append(RiskItem(
            level="warning",
            message=f"检测到 {short_lived} 个短生命周期进程",
            hint="可能存在频繁的创建/销毁循环",
            patterns=["SHORT_LIVED_PROCESSES"]
        ))
    
    if leaked > 10:
        risks.append(RiskItem(
            level="critical",
            message=f"疑似进程泄漏: {leaked} 个进程未正常退出",
            hint="检查进程退出逻辑和资源释放",
            patterns=["PROCESS_LEAK"]
        ))
    
    return LifecycleReport(
        spawn_events_count=len(spawn_events),
        exit_events_count=len(exit_events),
        spawn_rate=spawn_rate,
        top_creators=top_creators,
        short_lived_count=short_lived,
        leaked_count=leaked,
        risks=risks
    )


def _storm_to_dict(s: StormAnalysis) -> dict:
    """转换StormAnalysis为dict"""
    return {
        "found": s.found,
        "comm": s.comm,
        "spawn_rate": s.spawn_rate,
        "pid_count": s.pid_count,
        "total_cpu": s.total_cpu,
        "severity": s.severity,
        "diagnosis": s.diagnosis,
        "risks": [r.to_dict() for r in s.risks]
    }


def _lifecycle_to_dict(l: LifecycleReport) -> dict:
    """转换LifecycleReport为dict"""
    return {
        "spawn_events_count": l.spawn_events_count,
        "exit_events_count": l.exit_events_count,
        "spawn_rate": l.spawn_rate,
        "top_creators": [{"symbol": c.symbol, "count": c.count} for c in l.top_creators],
        "short_lived_count": l.short_lived_count,
        "leaked_count": l.leaked_count,
        "risks": [r.to_dict() for r in l.risks]
    }


def _callers_to_dict(c: CallersReport) -> dict:
    """转换CallersReport为dict"""
    return {
        "target": c.target,
        "callers": [{"symbol": caller.symbol} for caller in c.callers[:3]],
        "risks": [r.to_dict() for r in c.risks]
    }
