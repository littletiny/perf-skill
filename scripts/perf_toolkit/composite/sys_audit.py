#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sys Audit - 系统审计组合命令

Composite层命令，通过Facade编排多个analysis工具：
1. detect-anomalies → 发现突变时刻
2. analyze-core-distribution → 分析核心分布  
3. analyze-comm-top → 分析进程组（增强版，含CV/Monopoly/SpawnRate）

然后综合分析结果，解决"A掩盖B"问题。
"""

from typing import Optional

from ..core.command_decorator import command
from ..core.output_models import (
    RiskInfo, TimeRange, SysAuditOutput
)
from ..analysis.facade import AnalysisFacade
from .risk_aggregator import RiskAggregator, AggregatedRisk
from .models import (
    RiskItem, ProcessGroup, DiagnosisReport,
    AnomaliesReport, CoreDistributionReport, CommTopReport
)


@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """
    [Composite] 系统审计组合命令
    
    自动编排多个分析工具，生成综合诊断报告。
    通过Facade调用Analysis层，不触发子命令的Trace记录。
    """
    top_n = getattr(args, 'top_n', 20)
    
    # ========== Phase 1: 通过Facade执行各维度分析 ==========
    
    facade = AnalysisFacade(engine)
    
    # 1.1 异常检测
    anomalies_raw = facade.detect_anomalies(samples, window_size=10, spike_threshold=0.5)
    anomalies = AnomaliesReport.from_dict(anomalies_raw)
    
    # 1.2 核心分布分析
    core_dist_raw = facade.analyze_core_distribution(samples)
    core_dist = CoreDistributionReport.from_dict(core_dist_raw)
    
    # 1.3 CommTop分析（增强版，通过include_metrics获取详细指标）
    from ..analysis.comm_top import CommTopAnalyzer
    comm_top_analyzer = CommTopAnalyzer(engine)
    comm_top_result_raw = comm_top_analyzer.analyze(samples, top_n=top_n, include_metrics=True)
    comm_top = CommTopReport.from_result(comm_top_result_raw)
    
    # ========== Phase 2: 收集Risks ==========
    
    aggregator = RiskAggregator()
    aggregator.add_risks(anomalies.risks)
    aggregator.add_risks(core_dist.risks)
    aggregator.add_risks(comm_top.risks)
    
    # ========== Phase 3: 综合分析 ==========
    
    diagnosis = _synthesize_diagnosis(anomalies, core_dist, comm_top)
    
    # 如果综合分析发现了额外风险，添加到aggregator
    if diagnosis.primary_suspect:
        primary = diagnosis.primary_suspect
        aggregator.add_risk(RiskItem(
            level="critical",
            message=f"主要性能瓶颈: {primary.comm}",
            hint=f"bottleneck-trace --comm {primary.comm}",
            patterns=["PRIMARY_SUSPECT"],
            pending_targets=[primary.comm]
        ))
    
    # ========== Phase 4: 生成聚合Risk ==========
    
    aggregated_risk = aggregator.aggregate()
    
    # 记录到Trace（只记录聚合后的，不记录子分析）
    if aggregated_risk.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated_risk.level,
            aggregated_risk.message,
            aggregated_risk.hint
        )
    
    risk = RiskInfo(
        level=aggregated_risk.level,
        message=aggregated_risk.message,
        hint=aggregated_risk.hint,
        patterns=aggregated_risk.patterns,
        pending_targets=aggregated_risk.pending_targets,
        action_required=aggregated_risk.action_required
    )
    
    # ========== Phase 5: 构建输出 ==========
    
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples else None,
        samples[-1].get('ts') if len(samples) > 1 else None
    )
    
    # 转换diagnosis为dict用于输出
    diagnosis_dict = _diagnosis_to_dict(diagnosis)
    details_dict = {
        "anomalies": _anomalies_to_dict(anomalies),
        "core_distribution": _core_dist_to_dict(core_dist),
        "comm_top": _comm_top_to_dict(comm_top)
    }
    
    output = SysAuditOutput(
        _risk=risk,
        diagnosis=diagnosis_dict,
        details=details_dict,
        time_range=time_range
    )
    
    return output


def _synthesize_diagnosis(anomalies: AnomaliesReport, 
                          core_dist: CoreDistributionReport,
                          comm_top: CommTopReport) -> DiagnosisReport:
    """
    综合分析结果，识别真正的瓶颈
    
    核心逻辑（解决A掩盖B问题）:
    1. 识别突变时刻
    2. 分析核心饱和情况
    3. 按危害指数（而非绝对CPU）排序进程组
    4. 区分Primary/Secondary/Background
    """
    # 1. 检查是否有突变
    mutation_time = None
    if anomalies.mutation_detected and anomalies.anomalies:
        mutation_time = anomalies.anomalies[0].timestamp
    
    # 2. 分析核心饱和情况
    saturated_cores = core_dist.saturated_cores
    
    # 3. 获取进程组（已按危害指数排序）
    groups = comm_top.groups
    
    # 获取所有组（包括被折叠的）用于完整分析
    all_groups = comm_top.metrics.all_groups if comm_top.metrics else groups
    
    # 4. 分类：Primary / Secondary / Background
    primary: Optional[ProcessGroup] = None
    secondary: list[ProcessGroup] = []
    background: list[ProcessGroup] = []
    
    for g in all_groups:
        diagnosis = g.diagnosis
        total_cpu = g.total_cpu
        
        if diagnosis == "BOTTLENECK":
            if primary is None:
                primary = g
            else:
                secondary.append(g)
        elif total_cpu > 10 or diagnosis in ["STORM", "UNBALANCED"]:
            secondary.append(g)
        else:
            background.append(g)
    
    # 构建根因分析
    root_cause = _build_root_cause(primary, secondary, anomalies, core_dist)
    
    return DiagnosisReport(
        primary_suspect=primary,
        secondary_loads=secondary[:3],
        background_noise=background[:5],
        background_count=len(background),
        mutation_detected=anomalies.mutation_detected,
        mutation_time=mutation_time,
        saturated_cores=saturated_cores,
        root_cause_analysis=root_cause
    )


def _build_root_cause(primary: Optional[ProcessGroup], 
                      secondary: list[ProcessGroup],
                      anomalies: AnomaliesReport,
                      core_dist: CoreDistributionReport) -> str:
    """构建根因分析描述"""
    parts: list[str] = []
    
    if primary:
        parts.append(f"主要瓶颈: {primary.comm} ({primary.diagnosis})")
    
    if anomalies.mutation_detected:
        parts.append("检测到性能突变")
    
    if core_dist.saturated_cores:
        cores_str = ', '.join(map(str, core_dist.saturated_cores[:3]))
        parts.append(f"核心饱和: CPU {cores_str}")
    
    if secondary:
        comms = ', '.join(s.comm for s in secondary[:2])
        parts.append(f"次要负载: {comms}")
    
    return "; ".join(parts) if parts else "未检测到明显瓶颈"


def _diagnosis_to_dict(d: DiagnosisReport) -> dict:
    """转换DiagnosisReport为dict（用于输出）"""
    return {
        "primary_suspect": {
            "comm": d.primary_suspect.comm,
            "total_cpu": d.primary_suspect.total_cpu,
            "diagnosis": d.primary_suspect.diagnosis,
            "monopoly": d.primary_suspect.monopoly
        } if d.primary_suspect else None,
        "secondary_loads": [
            {"comm": g.comm, "total_cpu": g.total_cpu, "diagnosis": g.diagnosis}
            for g in d.secondary_loads
        ],
        "background_count": d.background_count,
        "mutation_detected": d.mutation_detected,
        "mutation_time": d.mutation_time,
        "saturated_cores": d.saturated_cores,
        "root_cause_analysis": d.root_cause_analysis
    }


def _anomalies_to_dict(a: AnomaliesReport) -> dict:
    """转换AnomaliesReport为dict"""
    return {
        "anomalies_count": len(a.anomalies),
        "mutation_detected": a.mutation_detected,
        "risks": [r.to_dict() for r in a.risks]
    }


def _core_dist_to_dict(c: CoreDistributionReport) -> dict:
    """转换CoreDistributionReport为dict"""
    return {
        "core_count": len(c.core_stats),
        "saturated_cores": c.saturated_cores,
        "imbalance_level": c.imbalance_level,
        "risks": [r.to_dict() for r in c.risks]
    }


def _comm_top_to_dict(c: CommTopReport) -> dict:
    """转换CommTopReport为dict"""
    return {
        "groups_count": len(c.groups),
        "folded_count": c.folded_count,
        "total_groups": c.total_groups,
        "risks": [r.to_dict() for r in c.risks]
    }
