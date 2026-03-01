#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2 版本：使用统一数据模型

Trace Attribution - Bottom-up attribution for specific bottleneck functions

使用 SymbolStack 和规范化后的符号名进行调用链分析。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, AttributionItem, AttributionSummary, AttributionsOutput,
    TraceItem, TracesSummary, TracesOutput, TimeRange
)


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
    
    # Calculate duration for cpu_util conversion and get total
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    
    # Trace attribution
    target = args.target
    attribution = defaultdict(float)
    target_core_sec = 0.0
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = engine.get_sample_weight(s)
        normalized_names = stack.get_normalized_names()
        
        if target in normalized_names:
            target_core_sec += core_per_sec
            idx = normalized_names.index(target)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += core_per_sec
    
    # Build results - show ratio relative to total samples (not just target)
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    for stack, core_sec in attribution.items():
        # Calculate ratio relative to total samples
        ratio_total = (core_sec / total_core_per_sec) * 100 if total_core_per_sec > 0 else 0
        if ratio_total < min_ratio:
            continue
        results.append(AttributionItem(
            caller_stack=list(stack),
            ratio_of_target_pct=f"{ratio_total:.2f}%",
            cpu_util="0.00%"  # Not used in display
        ))
    
    results.sort(key=lambda x: float(x.ratio_of_target_pct.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    results = results[:top_n]
    
    # Determine risk level
    risk = None
    if target_core_sec < 0.01:
        risk = create_risk_info(
            level="warning",
            message=f"目标函数 '{target}' 几乎无 CPU 活动",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '目标函数 {target} 几乎无 CPU 活动' --risk 'warning' --hint '检查目标函数名称是否正确'",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    else:
        risk = RiskInfo(level="none")
    
    # Create summary with truncation info
    target_cpu_util = (target_core_sec / duration * 100) if duration > 0 else 0
    summary = AttributionSummary(
        target=target,
        target_cpu_util=f"{target_cpu_util:.2f}%",
        total_attributions=len(attribution),
        shown_attributions=len(results)
    )
    
    # Build and output
    output = AttributionsOutput(
        _risk=risk,
        attributions=results,
        summary=summary
    )
    
    builder.print_output(output)


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
    
    # Get total for ratio calculation and duration
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Find top hotspots
    self_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = engine.get_sample_weight(s)
            leaf_name = stack.get_normalized_names()[0]
            self_core_sec[leaf_name] += core_per_sec
    
    # Apply min-cpu threshold filter
    min_cpu = getattr(args, 'min_cpu', 3.0)
    filtered_hotspots = []
    hidden_hotspots = []
    for name, core_sec in sorted(self_core_sec.items(), key=lambda x: -x[1]):
        cpu_util = (core_sec / total_core_per_sec) * 100 if total_core_per_sec > 0 else 0
        if cpu_util >= min_cpu:
            filtered_hotspots.append((name, core_sec, cpu_util))
        else:
            hidden_hotspots.append((name, cpu_util))
    
    # Print threshold filter info if any hotspots were hidden
    if hidden_hotspots:
        hidden_total_ratio = sum(h[1] for h in hidden_hotspots)
        print(f"# ... {len(hidden_hotspots)} hotspots below {min_cpu}% threshold (total: {hidden_total_ratio:.2f}%)")
        print()
    
    top_n = getattr(args, 'top_n', 10)
    top_hotspots = filtered_hotspots[:top_n]
    
    # Trace each hotspot
    results = []
    for target, target_total_core_sec, target_cpu_util in top_hotspots:
        attribution = defaultdict(float)
        
        for s in samples:
            stack = s.get('stack')
            if not stack:
                continue
            
            core_per_sec = engine.get_sample_weight(s)
            normalized_names = stack.get_normalized_names()
            # Only count when target is at stack top (self time)
            if normalized_names and normalized_names[0] == target:
                if len(normalized_names) > 1:
                    caller_stack = normalized_names[1:6]
                    attribution[tuple(caller_stack)] += core_per_sec
        
        sorted_attr = sorted(attribution.items(), key=lambda x: -x[1])[:5]
        
        attr_results = []
        for stack, core_sec in sorted_attr:
            ratio_in_target = (core_sec / target_total_core_sec) * 100 if target_total_core_sec > 0 else 0
            stack_cpu_util = (core_sec / duration * 100) if duration > 0 else 0
            attr_results.append(AttributionItem(
                caller_stack=list(stack),
                ratio_of_target_pct=f"{ratio_in_target:.2f}%",
                cpu_util=f"{stack_cpu_util:.2f}%"
            ))
        
        results.append(TraceItem(
            target=target,
            target_ratio_pct=f"{target_cpu_util:.2f}%",
            attributions=attr_results
        ))
    
    # Create risk (always none for auto trace)
    risk = RiskInfo(level="none")
    
    # Create summary
    summary = TracesSummary(hotspots_traced=len(results))
    
    # Build and output
    output = TracesOutput(
        _risk=risk,
        traces=results,
        summary=summary
    )
    
    builder.print_output(output)
