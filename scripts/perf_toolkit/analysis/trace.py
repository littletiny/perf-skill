#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trace Attribution - Bottom-up attribution for specific bottleneck functions

使用 SymbolStack 和规范化后的符号名进行调用链分析。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_core_sec
from ..core.output_builder import OutputBuilder


def cmd_trace_attribution(engine, args):
    """[Skill] Bottom-up attribution for specific bottleneck functions"""
    
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
    
    # Trace attribution
    target = args.target
    attribution = defaultdict(float)
    target_core_sec = 0.0
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        normalized_names = stack.get_normalized_names()
        
        if target in normalized_names:
            target_core_sec += core_per_sec
            idx = normalized_names.index(target)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += core_per_sec
    
    # Build results
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    for stack, core_sec in attribution.items():
        ratio_in_target = (core_sec / target_core_sec) * 100 if target_core_sec > 0 else 0
        if ratio_in_target < min_ratio:
            continue
        results.append({
            "caller_stack": list(stack),
            "ratio_of_target_pct": f"{ratio_in_target:.2f}%",
            "core_sec": format_core_sec(core_sec)
        })
    
    results.sort(key=lambda x: float(x['ratio_of_target_pct'].rstrip('%')), reverse=True)
    
    # Add risk if target has low activity
    if target_core_sec < 0.01:
        builder.add_risk(
            "warning",
            f"目标函数 '{target}' 几乎无 CPU 活动",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '目标函数 {target} 几乎无 CPU 活动' --risk 'warning' --hint '检查目标函数名称是否正确'",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    
    # Build and output
    result = builder.build(
        data_type="attributions",
        data=results,
        summary={
            "target": target,
            "target_core_sec": format_core_sec(target_core_sec)
        }
    )
    
    builder.print_json(result)


def cmd_find_callers_auto(engine, args):
    """[Skill] Auto-trace top N hotspot functions"""
    
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
    
    # Get total for ratio calculation
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    
    # Find top hotspots
    self_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            leaf_name = stack.get_normalized_names()[0]
            self_core_sec[leaf_name] += core_per_sec
    
    auto_target_top_n = getattr(args, 'auto_target_top_n', 5)
    top_hotspots = sorted(self_core_sec.items(), key=lambda x: -x[1])[:auto_target_top_n]
    
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
        
        sorted_attr = sorted(attribution.items(), key=lambda x: -x[1])[:5]
        
        attr_results = []
        for stack, core_sec in sorted_attr:
            ratio_in_target = (core_sec / target_total_core_sec) * 100 if target_total_core_sec > 0 else 0
            attr_results.append({
                "caller_stack": list(stack),
                "ratio_of_target_pct": f"{ratio_in_target:.2f}%",
                "core_sec": format_core_sec(core_sec)
            })
        
        target_ratio = (target_total_core_sec / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
        results.append({
            "target": target,
            "target_ratio_pct": f"{target_ratio:.2f}%",
            "attributions": attr_results
        })
    
    # Build and output
    result = builder.build(
        data_type="traces",
        data=results,
        summary={
            "hotspots_traced": len(results)
        }
    )
    
    builder.print_json(result)
