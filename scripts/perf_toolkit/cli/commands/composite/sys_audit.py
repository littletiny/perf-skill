#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sys-audit 命令实现

从 composite/sys_audit.py 迁移而来
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import SysAuditOutput
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator, AggregatedRisk
from perf_toolkit.composite.models import (
    ProcessGroup, DiagnosisReport,
    AnomaliesReport, CoreDistributionReport, CommTopReport,
    PrimarySuspectData, SecondaryLoadData, DiagnosisDetails,
    AnomaliesDetails, CoreDistDetails, CommTopDetails, SysAuditDetails
)

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("sys-audit")
def cmd_sys_audit(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> SysAuditOutput:
    """
    [Composite] 系统审计组合命令
    
    自动编排多个分析工具，生成综合诊断报告。
    通过Facade调用Analysis层，不触发子命令的Trace记录。
    """
    top_n = getattr(args, 'top_n', 20)
    
    # ========== Phase 1: 通过Facade执行各维度分析 ==========
    
    facade = AnalysisFacade(engine)
    
    # 1.1 异常检测
    anomalies_result = facade.detect_anomalies(samples, window_size=10, spike_threshold=0.5)
    anomalies = _convert_anomalies_result(anomalies_result)

    # 1.2 核心分布分析
    core_dist_result = facade.analyze_core_distribution(samples)
    core_dist = _convert_core_dist_result(core_dist_result)

    # 1.3 CommTop分析（增强版，通过include_metrics获取详细指标）
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    comm_top_analyzer = CommTopAnalyzer(engine)
    comm_top_result = comm_top_analyzer.analyze(samples, top_n=top_n, include_metrics=True)
    comm_top = _convert_comm_top_result(comm_top_result)
    
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
        aggregator.add_risk(RiskInfo(
            level="critical",
            message=f"主要性能瓶颈: {primary.comm}",
            hint=f"bottleneck-trace --comm {primary.comm}",
            patterns=["PRIMARY_SUSPECT"],
            pending_targets=[primary.comm],
            source="sys_audit"
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
        pending_targets=aggregated_risk.pending_targets
    )
    
    # ========== Phase 5: 构建输出 ==========
    
    time_range = TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if len(samples) > 1 else None
    )
    
    # 转换analysis结果为dataclass用于输出
    diagnosis_data = _diagnosis_to_dataclass(diagnosis)
    details_data = SysAuditDetails(
        anomalies=_anomalies_to_dataclass(anomalies),
        core_distribution=_core_dist_to_dataclass(core_dist),
        comm_top=_comm_top_to_dataclass(comm_top)
    )
    
    output = SysAuditOutput(
        _risk=risk,
        diagnosis=diagnosis_data,
        details=details_data,
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


def _diagnosis_to_dataclass(d: DiagnosisReport) -> DiagnosisDetails:
    """转换DiagnosisReport为DiagnosisDetails dataclass（用于输出）"""
    primary = None
    if d.primary_suspect:
        primary = PrimarySuspectData(
            comm=d.primary_suspect.comm,
            total_cpu=d.primary_suspect.total_cpu,
            diagnosis=d.primary_suspect.diagnosis,
            monopoly=d.primary_suspect.monopoly
        )
    
    secondary = [
        SecondaryLoadData(comm=g.comm, total_cpu=g.total_cpu, diagnosis=g.diagnosis)
        for g in d.secondary_loads
    ]
    
    return DiagnosisDetails(
        primary_suspect=primary,
        secondary_loads=secondary,
        background_count=d.background_count,
        mutation_detected=d.mutation_detected,
        mutation_time=d.mutation_time,
        saturated_cores=d.saturated_cores,
        root_cause_analysis=d.root_cause_analysis
    )


def _anomalies_to_dataclass(a: AnomaliesReport) -> AnomaliesDetails:
    """转换AnomaliesReport为AnomaliesDetails dataclass"""
    return AnomaliesDetails(
        anomalies_count=len(a.anomalies),
        mutation_detected=a.mutation_detected,
        risks=a.risks
    )


def _core_dist_to_dataclass(c: CoreDistributionReport) -> CoreDistDetails:
    """转换CoreDistributionReport为CoreDistDetails dataclass"""
    return CoreDistDetails(
        core_count=len(c.core_stats),
        saturated_cores=c.saturated_cores,
        imbalance_level=c.imbalance_level,
        risks=c.risks
    )


def _comm_top_to_dataclass(c: CommTopReport) -> CommTopDetails:
    """转换CommTopReport为CommTopDetails dataclass"""
    return CommTopDetails(
        groups_count=len(c.groups),
        folded_count=c.folded_count,
        total_groups=c.total_groups,
        risks=c.risks
    )



# =============================================================================
# Conversion Helpers - 显式字段映射（替代已删除的 from_analysis_* 方法）
# =============================================================================

def _convert_anomalies_result(result) -> AnomaliesReport:
    """从 Analysis 层的 AnomaliesResult 转换为 Composite 层的 AnomaliesReport"""
    from datetime import datetime
    from perf_toolkit.composite.models import AnomalyItem

    def _parse_timestamp(time_str: str) -> float:
        """将 ISO 8601 时间字符串转换为时间戳"""
        if isinstance(time_str, (int, float)):
            return float(time_str)
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt.timestamp()

    anomalies = [
        AnomalyItem(
            cpu_id=a.cpu_id,
            timestamp=_parse_timestamp(a.time_range_start),
            change_magnitude=abs(a.curr_util - a.prev_util),
            utilization=a.curr_util,
            anomaly_type=a.type,
            z_score=a.z_score
        )
        for a in result.anomalies
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="anomalies"
        )
        for r in result.risks
    ]

    return AnomaliesReport(
        anomalies=anomalies,
        mutation_detected=result.mutation_detected,
        spike_count=result.spike_count,
        drop_count=result.drop_count,
        risks=risks
    )


def _convert_core_dist_result(result) -> CoreDistributionReport:
    """从 Analysis 层的 CoreDistributionResult 转换为 Composite 层的 CoreDistributionReport"""
    from perf_toolkit.composite.models import CoreStat

    core_stats = [
        CoreStat(
            cpu_id=c.cpu_id,
            total_cpu=c.total_cpu,
            kernel_cpu=c.kernel_cpu,
            user_cpu=c.user_cpu
        )
        for c in result.cores
    ]

    # saturated_cores 可能是 CoreStat 对象列表，提取 cpu_id
    saturated = result.saturated_cores
    if saturated and hasattr(saturated[0], 'cpu_id'):
        saturated = [c.cpu_id for c in saturated]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="core_dist"
        )
        for r in result.risks
    ]

    return CoreDistributionReport(
        core_stats=core_stats,
        saturated_cores=saturated,
        imbalance_level=result.imbalance_level,
        risks=risks
    )


def _convert_comm_top_result(result) -> CommTopReport:
    """从 Analysis 层的 CommTopResult 转换为 Composite 层的 CommTopReport"""
    from perf_toolkit.composite.models import CommTopMetrics

    groups = [
        ProcessGroup(
            comm=g.comm,
            total_cpu=g.total_cpu,
            kernel_cpu=g.kernel_cpu,
            user_cpu=g.user_cpu,
            pid_count=g.pid_count,
            pids=list(g.pids) if hasattr(g, 'pids') else [],
            cv=g.cv,
            monopoly=g.monopoly,
            spawn_rate=g.spawn_rate,
            diagnosis=g.diagnosis,
            impact_score=g.impact_score
        )
        for g in result.groups
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="comm_top"
        )
        for r in result.risks
    ]

    # 转换 metrics（如果存在）
    metrics = None
    if result.metrics:
        metrics = CommTopMetrics(
            cv_map=getattr(result.metrics, 'cv_map', {}),
            monopoly_map=getattr(result.metrics, 'monopoly_map', {}),
            spawn_rate_map=getattr(result.metrics, 'spawn_rate_map', {}),
            impact_score_map=getattr(result.metrics, 'impact_score_map', {}),
            folded_groups=[],
            all_groups=groups
        )

    return CommTopReport(
        groups=groups,
        folded_count=result.folded_count,
        total_groups=result.total_groups,
        risks=risks,
        metrics=metrics
    )
