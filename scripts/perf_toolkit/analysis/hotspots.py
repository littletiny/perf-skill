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
    record_count = len(filtered)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(filtered)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )

    # 使用 core/s 作为权重进行统计，而非样本数量
    self_core_sec = defaultdict(float)  # Self time: 栈顶函数
    incl_core_sec = defaultdict(float)  # Inclusive time: 栈中所有函数

    for s in filtered:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        
        # 使用规范化后的符号名进行统计
        normalized_names = stack.get_normalized_names()
        
        # Self time: 栈顶函数 (leaf) 的 core/s
        self_core_sec[normalized_names[0]] += core_per_sec
        
        # Inclusive time: 栈中所有唯一函数的 core/s
        # 注意：同一个函数在栈中多次出现只计算一次
        seen = set()
        for sym in normalized_names:
            if sym not in seen:
                incl_core_sec[sym] += core_per_sec
                seen.add(sym)
    
    # 计算总 core/s 用于百分比计算
    total_self_core_sec = sum(self_core_sec.values())
    total_incl_core_sec = sum(incl_core_sec.values())
    
    results = []
    for sym, core_sec in incl_core_sec.items():
        self_pct = (self_core_sec[sym] / total_self_core_sec * 100) if total_self_core_sec > 0 else 0
        incl_pct = (core_sec / total_incl_core_sec * 100) if total_incl_core_sec > 0 else 0
        results.append({
            "symbol": sym,
            "self_core_sec": round(self_core_sec[sym], 4),
            "self_ratio_pct": round(self_pct, 2),
            "inclusive_core_sec": round(core_sec, 4),
            "inclusive_ratio_pct": round(incl_pct, 2)
        })
    
    # 按指定方式排序
    key = "inclusive_ratio_pct" if args.sort_by == "inclusive" else "self_ratio_pct"
    results.sort(key=lambda x: x[key], reverse=True)
    
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
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "total_core_seconds": round(total_core_per_sec, 4),
        "hotspots": results[:args.top_n]
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！热点函数排序和百分比完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，百分比数值仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
