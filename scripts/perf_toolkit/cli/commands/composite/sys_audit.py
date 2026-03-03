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
from perf_toolkit.composite.sys_audit import (
    _synthesize_diagnosis,
    _build_root_cause,
    _diagnosis_to_dataclass,
    _anomalies_to_dataclass,
    _core_dist_to_dataclass,
    _comm_top_to_dataclass,
    _convert_anomalies_result,
    _convert_core_dist_result,
    _convert_comm_top_result,
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
