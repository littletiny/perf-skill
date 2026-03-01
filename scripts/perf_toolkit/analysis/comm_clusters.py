#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Clustering - Cluster samples by process name (comm) to analyze process group CPU usage

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_percent
from ..core.output_builder import OutputBuilder


def cmd_cluster_comm(engine, args):
    """[Skill] Cluster samples by comm (process name) to analyze process group CPU usage"""
    
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
    
    # Aggregate comm stats
    comm_stats = defaultdict(lambda: {
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0,
        'total_core_sec': 0.0,
        'pids': set()
    })
    
    for s in samples:
        comm = s['comm']
        comm_stats[comm]['pids'].add(s['pid'])
        
        core_val = s.get('core_per_sec') or 0
        comm_stats[comm]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
    
    # Build results
    results = []
    for comm, stats in comm_stats.items():
        unique_pids = len(stats['pids'])
        total_core_sec = stats['total_core_sec']
        
        cpu_util = (total_core_sec / duration) * 100 if duration > 0 else 0
        kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100 if total_core_sec > 0 else 0
        
        results.append({
            'comm': comm,
            'unique_pids': unique_pids,
            'cpu_pct': format_percent(cpu_util),
            'kernel_pct': format_percent(kernel_ratio)
        })
    
    results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)
    top_results = results[:args.top_n]
    
    # Build and output
    result = builder.build(
        data_type="comm_groups",
        data=top_results,
        summary={
            "total_comm_groups": len(results)
        }
    )
    
    builder.print_json(result)
