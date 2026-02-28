#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

使用 Symbol.normalized_name 作为符号标识，基于 core/s（CPU 利用率）进行统计，
而非样本数量（因为数据已按 1 秒聚合，样本数无意义）。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


def cmd_get_hotspots(engine, args):
    """[Skill] Extract macro hotspot paths or function rankings"""
    filtered = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not filtered:
        result = output.add_risk(
            "warning",
            "未找到样本数据",
            "检查过滤条件"
        ).build({
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(args, 'start_time', None),
                getattr(args, 'end_time', None)
            ),
            "available_range": engine.get_time_range()
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    duration = filtered[-1]['ts'] - filtered[0]['ts'] if len(filtered) > 1 else 0
    record_count = len(filtered)
    
    total_core_per_sec, _ = engine.get_total_core_per_sec(filtered)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )

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
    
    key = "inclusive_ratio_pct"
    results.sort(key=lambda x: float(x[key].rstrip('%')), reverse=True)
    
    # Add risk for high kernel hotspot
    if top_kernel_ratio > 30:
        output.add_risk(
            "warning",
            f"热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%",
            f"溯源调用: find-callers --target {top_kernel_hotspot}",
            patterns=["HIGH_KERNEL_HOTSPOT"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！热点函数排序和百分比完全不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "total_core_seconds": format_core_sec(total_core_per_sec)
        },
        "time_range": format_time_range(filtered[0]['ts'], filtered[-1]['ts']),
        "hotspots": results[:args.top_n]
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
