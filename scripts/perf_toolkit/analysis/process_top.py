#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Top - Get top N processes by CPU utilization

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_percent
from ..core.output_builder import OutputBuilder


def cmd_get_process_top(engine, args):
    """[Skill] Get top N processes by CPU utilization"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Calculate duration
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Aggregate process stats
    process_stats = defaultdict(lambda: {
        'comm': '',
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0,
        'total_core_sec': 0.0
    })
    
    for s in samples:
        key = (s['comm'], s['pid'])
        process_stats[key]['comm'] = s['comm']
        process_stats[key]['pid'] = s['pid']
        
        core_val = s.get('core_per_sec') or 0
        process_stats[key]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            process_stats[key]['kernel_core_sec'] += core_val
        else:
            process_stats[key]['user_core_sec'] += core_val
    
    # Build results
    results = []
    
    for (comm, pid), stats in process_stats.items():
        proc_core_sec = stats['total_core_sec']
        
        cpu_util = (proc_core_sec / duration) * 100 if duration > 0 else 0
        kernel_ratio = (stats['kernel_core_sec'] / proc_core_sec) * 100 if proc_core_sec > 0 else 0
        
        results.append({
            'comm': comm,
            'pid': pid,
            'cpu_pct': format_percent(cpu_util),
            'kernel_pct': format_percent(kernel_ratio)
        })
    
    results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)
    top_results = results[:args.top_n]
    
    # Build and output
    result = builder.build(
        data_type="processes",
        data=top_results,
        summary={
            "total_processes": len(results),
            "shown_processes": len(top_results)
        }
    )
    
    builder.print_json(result)
