#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze-core-distribution 命令实现

使用共享的 CoreDistributionBuilder 构建输出，
确保与 sys-audit 中的核心分布展示格式一致。
"""

from typing import List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import RiskLevel, CoreDistributionOutput
from perf_toolkit.core.core_distribution_builder import (
    build_core_distribution_for_command
)
from perf_toolkit.analysis.core_distribution import CoreDistAnalyzer

if TYPE_CHECKING:
    from perf_toolkit.core.output_builder import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("analyze-core-distribution")
def cmd_analyze_core_distribution(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> CoreDistributionOutput:
    """
    [Skill] Analyze CPU core utilization distribution
    
    使用共享的 CoreDistributionBuilder 构建输出，
    确保与 sys-audit 中的核心分布展示格式一致。
    """
    
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
    
    risk_output = RiskInfo(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else RiskInfo(level="none")
    
    # 4. 使用共享构建器构建输出（确保与 sys-audit 格式一致）
    output = build_core_distribution_for_command(result, risk_output)
    
    # 5. 添加时间范围
    output.time_range = TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if len(samples) > 1 else None
    )
    
    return output
