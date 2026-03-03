#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect-anomalies 命令实现

从 analysis/anomalies.py 迁移而来
"""

from typing import List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.output_models import (
    RiskInfo, RiskLevel, AnomalyItem, AnomalySummary, AnomaliesOutput, TimeRange
)
from perf_toolkit.analysis.anomalies import AnomaliesAnalyzer

if TYPE_CHECKING:
    from perf_toolkit.core.output_builder import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("detect-anomalies")
def cmd_detect_anomalies(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> AnomaliesOutput:
    """[Skill] Detect CPU utilization anomalies"""
    
    # 1. 调用 Analyzer
    analyzer = AnomaliesAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        window_size=getattr(args, 'window_size', 1.0),
        spike_threshold=getattr(args, 'spike_threshold', 0.5),
        min_utilization=getattr(args, 'min_utilization', 0.3),
        cpu_id=getattr(args, 'cpu_id', None),
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
    anomaly_items = [
        AnomalyItem(
            type=a.type,
            cpu_id=a.cpu_id,
            time_range_start=a.time_range_start,
            time_range_end=a.time_range_end,
            prev_util=a.prev_util,
            curr_util=a.curr_util,
            next_util=a.next_util,
            severity="high" if a.z_score > 2.5 else "medium"
        )
        for a in result.anomalies
    ]
    
    risk_output = RiskInfo(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else RiskInfo(level="none")
    
    output = AnomaliesOutput(
        _risk=risk_output,
        anomalies=anomaly_items,
        summary=AnomalySummary(
            total_anomalies=result.spike_count + result.drop_count,
            spike_count=result.spike_count,
            drop_count=result.drop_count
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None,
            samples[-1].ts if len(samples) > 1 else None
        )
    )
    
    return output
