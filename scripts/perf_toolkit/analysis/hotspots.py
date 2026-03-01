#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, HotspotItem, HotspotSummary, HotspotsOutput, TimeRange
)


@command("get-hotspots")
def cmd_get_hotspots(builder, engine, args, samples):
    """[Skill] Extract macro hotspot paths or function rankings"""

    # 样本已由装饰器准备好：获取、空检查、质量评估

    # 使用 engine 统一接口获取符号级 CPU 利用率
    symbol_util = engine.get_symbol_cpu_util(samples)

    # Build results
    results = []
    top_kernel_hotspot = None
    top_kernel_ratio = 0

    for sym in symbol_util['inclusive'].keys():
        self_pct = symbol_util['self'].get(sym, 0)
        incl_pct = symbol_util['inclusive'][sym]

        # Track kernel hotspots for risk
        if sym.endswith('_[k]') and incl_pct > top_kernel_ratio:
            top_kernel_ratio = incl_pct
            top_kernel_hotspot = sym

        results.append(HotspotItem.from_stats(sym, self_pct, incl_pct))

    # Sort by self ratio (descending)
    results.sort(key=lambda x: float(x.self.rstrip('%')), reverse=True)
    top_items = results[:args.top_n]

    # Build RiskInfo
    if top_kernel_ratio > 30:
        risk = create_risk_info(
            level="warning",
            message=f"热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%",
            live_doc_hint=f"[必须] 添加到 Trace: spear trace add --desc '热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%' --hint 'find-callers --target {top_kernel_hotspot}'",
            patterns=["HIGH_KERNEL_HOTSPOT"]
        )
    else:
        risk = create_risk_info(level="none")

    # Build time range
    time_range = None
    if samples:
        time_range = TimeRange.from_timestamps(
            samples[0].get('ts'),
            samples[-1].get('ts') if len(samples) > 0 else None
        )

    # Build summary with truncation info
    summary = HotspotSummary(
        total_hotspots=len(results),
        shown_hotspots=len(top_items)
    )

    # Build output
    output = HotspotsOutput(
        _risk=risk,
        hotspots=top_items,
        summary=summary,
        time_range=time_range
    )

    return output  # 装饰器会自动调用 print_output
