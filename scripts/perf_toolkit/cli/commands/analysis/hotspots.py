#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get-hotspots 命令实现

从 analysis/hotspots.py 迁移而来
"""

from perf_toolkit.cli.decorators import command
from perf_toolkit.cli.builders import create_risk_info
from perf_toolkit.core.output_models import (
    RiskInfo, RiskLevel, HotspotItem, HotspotSummary, HotspotsOutput, TimeRange
)
from perf_toolkit.analysis.hotspots import HotspotsAnalyzer


@command("get-hotspots")
def cmd_get_hotspots(builder, engine, args, samples):
    """[Skill] Extract hotspot function rankings by self/inclusive time"""
    
    # 1. 调用 Analyzer
    analyzer = HotspotsAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        comm=getattr(args, 'comm', None),
        pid=getattr(args, 'pid', None),
        top_n=getattr(args, 'top_n', 10),
        sort_by=getattr(args, 'sort_by', 'self')
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
    hotspots = [
        HotspotItem.from_stats(
            symbol=h.symbol,
            self_pct=h.self_pct,
            inclusive_pct=h.inclusive_pct
        )
        for h in result.hotspots
    ]
    
    risk_output = create_risk_info(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else create_risk_info(level="none")
    
    output = HotspotsOutput(
        _risk=risk_output,
        hotspots=hotspots,
        summary=HotspotSummary(
            total_hotspots=len(result.hotspots),
            shown_hotspots=len(hotspots)
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None,
            samples[-1].ts if len(samples) > 1 else None
        )
    )
    
    return output
