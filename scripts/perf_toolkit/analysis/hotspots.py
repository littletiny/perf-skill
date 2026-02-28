#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

使用 Symbol.normalized_name 作为符号标识，保留原始 kernel/user 信息
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability, format_percentage_with_ci


def cmd_get_hotspots(engine, args):
    """[Skill] Extract macro hotspot paths or function rankings"""
    # Get filtered samples by time range, CPU, PID and comm
    filtered = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not filtered:
        return print(json.dumps({
            "error": "No samples found",
            "filters": {
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None),
                "cpu_id": getattr(args, 'cpu_id', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))

    # Calculate duration from filtered samples
    duration = filtered[-1]['ts'] - filtered[0]['ts'] if len(filtered) > 1 else 0
    total = len(filtered)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(filtered)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total, duration, total_core_per_sec=total_core_per_sec
    )

    self_counts = defaultdict(int)
    incl_counts = defaultdict(int)

    for s in filtered:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        # 使用规范化后的符号名进行统计
        # SymbolStack.get_normalized_names() 返回规范化后的名称列表
        normalized_names = stack.get_normalized_names()
        
        # Self count: 栈顶函数 (leaf)
        self_counts[normalized_names[0]] += 1
        
        # Inclusive count: 栈中所有唯一函数
        for sym in set(normalized_names):
            incl_counts[sym] += 1
    
    results = []
    for sym, count in incl_counts.items():
        self_ci = format_percentage_with_ci(self_counts[sym], total)
        incl_ci = format_percentage_with_ci(count, total)
        results.append({
            "symbol": sym,
            "self_ratio": f"{(self_counts[sym]/total)*100:.2f}%",
            "self_ratio_with_ci": self_ci,
            "inclusive_ratio": f"{(count/total)*100:.2f}%",
            "inclusive_ratio_with_ci": incl_ci,
            "raw_count": count
        })
    
    key = "inclusive_ratio" if args.sort_by == "inclusive" else "self_ratio"
    results.sort(key=lambda x: float(x[key].replace('%', '')), reverse=True)
    
    output = {
        "time_range": {
            "start": filtered[0]['ts'],
            "end": filtered[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            "start_time": getattr(args, 'start_time', None),
            "end_time": getattr(args, 'end_time', None),
            "cpu_id": getattr(args, 'cpu_id', None)
        },
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics,
            "sample_count": total
        },
        "hotspots": results[:args.top_n]
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！热点函数排序和百分比完全不可信。"
    elif reliability_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "置信区间较宽，百分比数值仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
