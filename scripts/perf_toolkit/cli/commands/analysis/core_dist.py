#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze-core-distribution 命令实现

从 analysis/core_distribution.py 迁移而来
"""

from typing import List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.output_models import RiskInfo, RiskLevel, CoreItem, CoreDistributionOutput, TimeRange
from perf_toolkit.analysis.core_distribution import CoreDistAnalyzer

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("analyze-core-distribution")
def cmd_analyze_core_distribution(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> CoreDistributionOutput:
    """[Skill] Analyze CPU core utilization distribution"""
    
    # 1. 调用 Analyzer
    analyzer = CoreDistAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        top_n=getattr(args, 'top_n', 10)
    )
    
    # 2. 记录 risks 到 Trace
    for risk in result.risks:
        builder.record_risk(
            risk.level,
            risk.message,
            risk.hint
        )
    
    # 3. 取最高级别 risk
    top_risk = None
    if result.risks:
        top_risk = min(result.risks, key=lambda r: RiskLevel.from_string(r.level).value)
    
    # 4. 转换为 Output 模型
    cores = [
        CoreItem(
            cpu_id=c.cpu_id,
            total_cpu_util=f"{c.total_cpu:.2f}%",
            kernel_cpu_util=f"{c.kernel_cpu:.2f}%"
        )
        for c in result.cores
    ]
    
    risk_output = RiskInfo(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else RiskInfo(level="none")
    
    output = CoreDistributionOutput(
        _risk=risk_output,
        cores=cores,
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None,
            samples[-1].ts if len(samples) > 1 else None
        )
    )
    
    return output
