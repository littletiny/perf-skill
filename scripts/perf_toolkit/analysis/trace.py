#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trace Attribution - Bottom-up attribution for specific bottleneck functions

使用 SymbolStack 和规范化后的符号名进行调用链分析
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability, format_percentage_with_ci


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
    total_samples = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    target = args.target
    attribution = defaultdict(int)
    target_samples = 0

    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        # 获取规范化后的符号名列表
        normalized_names = stack.get_normalized_names()
        
        if target in normalized_names:
            target_samples += 1
            idx = normalized_names.index(target)
            # Extract parent stack calling target (take 5 levels up)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += 1

    results = []
    for stack, count in attribution.items():
        ratio_in_target = (count / target_samples) * 100 if target_samples > 0 else 0
        if ratio_in_target < args.min_ratio:
            continue
        ratio_with_ci = format_percentage_with_ci(count, target_samples) if target_samples > 0 else "N/A"
        results.append({
            "caller_stack": list(stack),
            "ratio_of_target": f"{ratio_in_target:.2f}%",
            "ratio_with_ci": ratio_with_ci,
            "sample_count": count
        })
    results.sort(key=lambda x: float(x['ratio_of_target'].replace('%', '')), reverse=True)
    
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
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics,
            "target_samples": target_samples,
            "target": args.target
        },
        "attributions": results
    }
    
    if target_samples < 5:
        output["_WARNING"] = f"目标函数 '{args.target}' 仅出现 {target_samples} 次，归因分析完全不可信。"
    elif reliability_level == "CRITICAL":
        output["_WARNING"] = "总体样本数过少，归因分析不可信。"
    
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
    total_samples = len(samples)

    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    # Count self samples (leaf functions) to find hotspots
    self_counts = defaultdict(int)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            # 使用规范化后的栈顶符号名
            leaf_name = stack.get_normalized_names()[0]
            self_counts[leaf_name] += 1
    
    # Get top N hotspots (excluding kernel internals if requested)
    top_hotspots = sorted(self_counts.items(), key=lambda x: -x[1])[:args.auto_target_top_n]
    
    # Trace each hotspot
    results = []
    for target, target_count in top_hotspots:
        attribution = defaultdict(int)
        
        for s in samples:
            stack = s.get('stack')
            if not stack:
                continue
            
            normalized_names = stack.get_normalized_names()
            if target in normalized_names:
                idx = normalized_names.index(target)
                caller_stack = normalized_names[idx+1:idx+6]
                if caller_stack:
                    attribution[tuple(caller_stack)] += 1
        
        # Sort attributions
        sorted_attr = sorted(attribution.items(), key=lambda x: -x[1])[:5]  # Top 5 callers
        
        attr_results = []
        for stack, count in sorted_attr:
            ratio_in_target = (count / target_count) * 100 if target_count > 0 else 0
            attr_results.append({
                "caller_stack": list(stack),
                "ratio_of_target": f"{ratio_in_target:.2f}%",
                "sample_count": count
            })
        
        results.append({
            "target": target,
            "target_samples": target_count,
            "target_ratio": f"{(target_count / total_samples * 100):.2f}%",
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
        "reliability": {
            "level": reliability_level,
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
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！自动溯源结果完全不可信。"
    elif reliability_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "采样率偏低，溯源结果仅供参考。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
