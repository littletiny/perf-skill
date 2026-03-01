#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

使用 Symbol.normalized_name 作为符号标识，基于 core/s（CPU 利用率）进行统计，
而非样本数量（因为数据已按 1 秒聚合，样本数无意义）。

V2 版本：使用统一数据模型
"""

from collections import defaultdict

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, HotspotItem, HotspotSummary, HotspotsOutput, TimeRange
)


def cmd_get_hotspots(engine, args):
    """[Skill] Extract macro hotspot paths or function rankings"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Calculate self and inclusive core/s
    self_core_sec = defaultdict(float)
    incl_core_sec = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        core_per_sec = engine.get_sample_weight(s)
        normalized_names = stack.get_normalized_names()
        
        self_core_sec[normalized_names[0]] += core_per_sec
        
        seen = set()
        for sym in normalized_names:
            if sym not in seen:
                incl_core_sec[sym] += core_per_sec
                seen.add(sym)
    
    # Use the same total for both self and inclusive percentages
    # total_self_core_sec is the total sample time (sum of all stack tops)
    total_core_sec = sum(self_core_sec.values())
    
    # Build results
    results = []
    top_kernel_hotspot = None
    top_kernel_ratio = 0
    
    for sym, core_sec in incl_core_sec.items():
        # Use the same total for both percentages to ensure inclusive >= self
        self_pct = (self_core_sec[sym] / total_core_sec * 100) if total_core_sec > 0 else 0
        incl_pct = (core_sec / total_core_sec * 100) if total_core_sec > 0 else 0
        
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
            live_doc_hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%' --risk 'warning' --hint 'find-callers --target {top_kernel_hotspot}'",
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
    
    builder.print_output(output)
