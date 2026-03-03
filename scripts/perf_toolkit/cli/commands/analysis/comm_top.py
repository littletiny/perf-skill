#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get-comm-top 命令实现

从 analysis/comm_top.py 迁移而来
"""

from typing import List, Dict, Any, TYPE_CHECKING

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.output_models import (
    RiskInfo, RiskLevel, CommGroupItem, CommGroupSummary, CommTopOutput, TimeRange
)
from perf_toolkit.analysis.comm_top import CommTopAnalyzer

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("get-comm-top")
def cmd_get_comm_top(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> CommTopOutput:
    """[Skill] Get top N comm groups by aggregated CPU utilization"""
    
    # 1. 调用 Analyzer
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(
        samples, 
        top_n=getattr(args, 'top_n', 10),
        include_metrics=False
    )
    
    # 2. 记录所有 risks 到 Trace
    for risk in result.risks:
        builder.record_risk(
            risk.level,
            risk.message,
            risk.hint
        )
    
    # 3. 取最高级别 risk 放入 _risk 字段
    top_risk = None
    if result.risks:
        top_risk = min(result.risks, key=lambda r: RiskLevel.from_string(r.level).value)
    
    # 4. 转换为 Output 模型
    groups = []
    for g in result.groups:
        kernel_ratio = (g.kernel_cpu / g.total_cpu * 100) if g.total_cpu > 0 else 0
        
        # 构建 event 描述
        if g.diagnosis == "BOTTLENECK":
            event = f"BOTTLENECK(M={g.monopoly:.2f})"
        elif g.diagnosis == "STORM":
            event = f"STORM({g.spawn_rate:.1f}/s)"
        elif g.diagnosis == "UNBALANCED":
            event = f"UNBALANCED(CV={g.cv:.2f})"
        else:
            event = "normal"
        
        groups.append(CommGroupItem.from_stats(
            comm=g.comm,
            pid_count=g.pid_count,
            aggregate_cpu=g.total_cpu,
            kernel_ratio=kernel_ratio,
            event_desc=event
        ))
    
    risk_output = RiskInfo(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else RiskInfo(level="none")
    
    output = CommTopOutput(
        _risk=risk_output,
        comm_groups=groups,
        summary=CommGroupSummary(
            total_comm_groups=result.total_groups,
            high_kernel_groups=len([r for r in result.risks if "HIGH_KERNEL" in str(r.patterns)])
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None,
            samples[-1].ts if len(samples) > 1 else None
        )
    )
    
    return output
