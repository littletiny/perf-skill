#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

使用 Symbol.normalized_name 作为符号标识，基于 core/s（CPU 利用率）进行统计，
而非样本数量（因为数据已按 1 秒聚合，样本数无意义）。
"""

from collections import defaultdict
from ..core.format_utils import format_core_sec
from ..core.output_builder import OutputBuilder


def cmd_get_hotspots(engine, args):
    """[Skill] Extract macro hotspot paths or function rankings"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    filtered = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(filtered):
        return
    
    # Assess quality
    builder.assess_quality(filtered)
    
    # Calculate self and inclusive core/s
    self_core_sec = defaultdict(float)
    incl_core_sec = defaultdict(float)
    
    for s in filtered:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        normalized_names = stack.get_normalized_names()
        
        self_core_sec[normalized_names[0]] += core_per_sec
        
        seen = set()
        for sym in normalized_names:
            if sym not in seen:
                incl_core_sec[sym] += core_per_sec
                seen.add(sym)
    
    total_self_core_sec = sum(self_core_sec.values())
    total_incl_core_sec = sum(incl_core_sec.values())
    
    # Build results
    results = []
    top_kernel_hotspot = None
    top_kernel_ratio = 0
    
    for sym, core_sec in incl_core_sec.items():
        self_pct = (self_core_sec[sym] / total_self_core_sec * 100) if total_self_core_sec > 0 else 0
        incl_pct = (core_sec / total_incl_core_sec * 100) if total_incl_core_sec > 0 else 0
        
        # Track kernel hotspots for risk
        if sym.endswith('_[k]') and incl_pct > top_kernel_ratio:
            top_kernel_ratio = incl_pct
            top_kernel_hotspot = sym
        
        results.append({
            "symbol": sym,
            "self_ratio_pct": f"{self_pct:.2f}%",
            "inclusive_ratio_pct": f"{incl_pct:.2f}%",
            "core_sec": format_core_sec(core_sec)
        })
    
    # Sort by inclusive ratio
    key = "inclusive_ratio_pct"
    results.sort(key=lambda x: float(x[key].rstrip('%')), reverse=True)
    
    # Add risk for high kernel hotspot
    if top_kernel_ratio > 30:
        builder.add_risk(
            "warning",
            f"热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%' --risk 'warning' --hint 'find-callers --target {top_kernel_hotspot}'",
            patterns=["HIGH_KERNEL_HOTSPOT"]
        )
    
    # Build and output
    result = builder.build(
        data_type="hotspots",
        data=results[:args.top_n],
        summary={
            "total_hotspots": len(results)
        }
    )
    
    builder.print_json(result)
