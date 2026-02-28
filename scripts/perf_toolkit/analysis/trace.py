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
from ..core.format_utils import format_time_range, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


def cmd_trace_attribution(engine, args):
    """[Skill] Bottom-up attribution for specific bottleneck functions"""
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
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
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
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

    results = []
    for stack, core_sec in attribution.items():
        ratio_in_target = (core_sec / target_core_sec) * 100 if target_core_sec > 0 else 0
        if ratio_in_target < args.min_ratio:
            continue
        results.append({
            "caller_stack": list(stack),
            "ratio_of_target_pct": f"{ratio_in_target:.2f}%",
            "core_sec": format_core_sec(core_sec)
        })
    results.sort(key=lambda x: float(x['ratio_of_target_pct'].rstrip('%')), reverse=True)
    
    # Add risk if target has low activity
    if target_core_sec < 0.01:
        output.add_risk(
            "warning",
            f"目标函数 '{target}' 几乎无 CPU 活动",
            "检查目标函数名称是否正确",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！归因分析不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "target": target,
        "target_core_sec": format_core_sec(target_core_sec),
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "attributions": results
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_find_callers_auto(engine, args):
    """[Skill] Auto-trace top N hotspot functions"""
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
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
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)

    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    self_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            leaf_name = stack.get_normalized_names()[0]
            self_core_sec[leaf_name] += core_per_sec
    
    top_hotspots = sorted(self_core_sec.items(), key=lambda x: -x[1])[:args.auto_target_top_n]
    
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
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！自动溯源结果完全不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "hotspots_traced": len(results)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "traces": results
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
