#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine

Trace Attribution - Bottom-up attribution for specific bottleneck functions

使用 SymbolStack 和规范化后的符号名进行调用链分析。
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
    
    # 使用 engine 统一接口获取总量
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)
    
    # Trace attribution
    target = args.target
    attribution = defaultdict(float)
    target_weight = 0.0
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        weight = engine.get_sample_weight(s)
        normalized_names = stack.get_normalized_names()
        
        if target in normalized_names:
            target_weight += weight
            idx = normalized_names.index(target)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += weight
    
    # Build results - show ratio relative to total samples (not just target)
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    for stack, weight_val in attribution.items():
        # Calculate ratio relative to total samples
        ratio_total = (weight_val / total_weight) * 100 if total_weight > 0 else 0
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
    if target_weight < 0.01:
        risk = create_risk_info(
            level="warning",
            message=f"目标函数 '{target}' 几乎无 CPU 活动",
            hint=f"[必须] 添加到 Trace: spear trace add --desc '目标函数 {target} 几乎无 CPU 活动' --hint '检查目标函数名称是否正确'",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    else:
        risk = RiskInfo(level="none")
    
    # Create summary with truncation info
    target_cpu_util = (target_weight / duration * 100) if duration > 0 else 0
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
    
    # 使用 engine 统一接口获取总量和 duration
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)
    
    # 使用 engine 统一接口获取符号级利用率
    symbol_util = engine.get_symbol_cpu_util(samples)
    
    # Apply min-cpu threshold filter
    min_cpu = getattr(args, 'min_cpu', 3.0)
    filtered_hotspots = []
    hidden_hotspots = []
    for name, self_pct in symbol_util['self'].items():
        if self_pct >= min_cpu:
            filtered_hotspots.append((name, self_pct))
        else:
            hidden_hotspots.append((name, self_pct))
    
    # Print threshold filter info if any hotspots were hidden
    if hidden_hotspots:
        hidden_total_ratio = sum(h[1] for h in hidden_hotspots)
        print(f"# ... {len(hidden_hotspots)} hotspots below {min_cpu}% threshold (total: {hidden_total_ratio:.2f}%)")
        print()
    
    top_n = getattr(args, 'top_n', 10)
    top_hotspots = sorted(filtered_hotspots, key=lambda x: -x[1])[:top_n]
    
    # Trace each hotspot
    results = []
    for target, target_cpu_util in top_hotspots:
        attribution = defaultdict(float)
        target_total_weight = 0.0
        
        for s in samples:
            stack = s.get('stack')
            if not stack:
                continue
            
            weight = engine.get_sample_weight(s)
            normalized_names = stack.get_normalized_names()
            # Only count when target is at stack top (self time)
            if normalized_names and normalized_names[0] == target:
                target_total_weight += weight
                if len(normalized_names) > 1:
                    caller_stack = normalized_names[1:6]
                    attribution[tuple(caller_stack)] += weight
        
        sorted_attr = sorted(attribution.items(), key=lambda x: -x[1])[:5]
        
        attr_results = []
        for stack, weight_val in sorted_attr:
            ratio_in_target = (weight_val / target_total_weight) * 100 if target_total_weight > 0 else 0
            stack_cpu_util = (weight_val / duration * 100) if duration > 0 else 0
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
