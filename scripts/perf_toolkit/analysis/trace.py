#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trace Attribution - Bottom-up attribution for specific bottleneck functions

使用 SymbolStack 和规范化后的符号名进行调用链分析。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


def cmd_trace_attribution(engine, args):
    """[Skill] Bottom-up attribution for specific bottleneck functions"""
    # Get filtered samples by time range, CPU, PID and comm
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
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
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    target = args.target
    attribution = defaultdict(float)  # 使用 core/s 作为权重
    target_core_sec = 0.0

    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        
        # 获取规范化后的符号名列表
        normalized_names = stack.get_normalized_names()
        
        if target in normalized_names:
            target_core_sec += core_per_sec
            idx = normalized_names.index(target)
            # Extract parent stack calling target (take 5 levels up)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += core_per_sec

    results = []
    for stack, core_sec in attribution.items():
        ratio_in_target = (core_sec / target_core_sec) * 100 if target_core_sec > 0 else 0
        if ratio_in_target < args.min_ratio:
            continue
        results.append({
            "caller_stack": list(stack),
            "ratio_of_target_pct": round(ratio_in_target, 2),
            "core_sec": round(core_sec, 4)
        })
    results.sort(key=lambda x: x['ratio_of_target_pct'], reverse=True)
    
    output = {
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
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
            "metrics": metrics,
            "target_core_sec": round(target_core_sec, 4),
            "target": args.target
        },
        "attributions": results
    }
    
    if target_core_sec < 0.01:  # 小于 0.01 core/s 视为几乎无活动
        output["_WARNING"] = f"目标函数 '{args.target}' 几乎无 CPU 活动 ({target_core_sec:.4f} core/s)，归因分析不可信。"
    elif quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足，归因分析不可信。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_find_callers_auto(engine, args):
    """[Skill] Auto-trace top N hotspot functions"""
    # Get filtered samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        print(json.dumps({
            "error": "No samples found",
            "filters": {
                'cpu_id': getattr(args, 'cpu_id', None),
                'pid': getattr(args, 'pid', None),
                'comm': getattr(args, 'comm', None),
                'start_time': getattr(args, 'start_time', None),
                'end_time': getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)

    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Count self core/s (leaf functions) to find hotspots - 使用 core/s 而非计数
    self_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            # 使用规范化后的栈顶符号名
            leaf_name = stack.get_normalized_names()[0]
            self_core_sec[leaf_name] += core_per_sec
    
    # Get top N hotspots (excluding kernel internals if requested)
    top_hotspots = sorted(self_core_sec.items(), key=lambda x: -x[1])[:args.auto_target_top_n]
    
    # Trace each hotspot
    results = []
    for target, target_total_core_sec in top_hotspots:
        attribution = defaultdict(float)
        
        for s in samples:
            stack = s.get('stack')
            if not stack:
                continue
            
            core_per_sec = s.get('core_per_sec', 0)
            normalized_names = stack.get_normalized_names()
            if target in normalized_names:
                idx = normalized_names.index(target)
                caller_stack = normalized_names[idx+1:idx+6]
                if caller_stack:
                    attribution[tuple(caller_stack)] += core_per_sec
        
        # Sort attributions
        sorted_attr = sorted(attribution.items(), key=lambda x: -x[1])[:5]  # Top 5 callers
        
        attr_results = []
        for stack, core_sec in sorted_attr:
            ratio_in_target = (core_sec / target_total_core_sec) * 100 if target_total_core_sec > 0 else 0
            attr_results.append({
                "caller_stack": list(stack),
                "ratio_of_target_pct": round(ratio_in_target, 2),
                "core_sec": round(core_sec, 4)
            })
        
        target_ratio = (target_total_core_sec / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
        results.append({
            "target": target,
            "target_core_sec": round(target_total_core_sec, 4),
            "target_ratio_pct": round(target_ratio, 2),
            "attributions": attr_results
        })
    
    output = {
        "mode": "auto-target",
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            'cpu_id': getattr(args, 'cpu_id', None),
            'pid': getattr(args, 'pid', None),
            'comm': getattr(args, 'comm', None),
            'start_time': getattr(args, 'start_time', None),
            'end_time': getattr(args, 'end_time', None)
        },
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "auto_config": {
            "top_n": args.auto_target_top_n,
            "min_ratio": args.min_ratio
        },
        "hotspots_traced": len(results),
        "traces": results
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！自动溯源结果完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，溯源结果仅供参考。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
