#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Clustering - Cluster samples by process name (comm) to analyze process group CPU usage

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。

V2 版本：使用统一数据模型，与 comm_top 共享数据结构
"""

from collections import defaultdict

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, CommGroupItem, CommGroupSummary, ClusterCommOutput, TimeRange
)


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
        
        core_val = engine.get_sample_weight(s)
        comm_stats[comm]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
    
    # Build results using unified data model (same as comm_top)
    items = []
    for comm, stats in comm_stats.items():
        unique_pids = len(stats['pids'])
        total_core_sec = stats['total_core_sec']
        
        cpu_util = (total_core_sec / duration) * 100 if duration > 0 else 0
        kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100 if total_core_sec > 0 else 0
        
        # cluster-comm uses same CommGroupItem as comm_top
        # but with different semantics in 'pids' field (unique_pids vs pid_count)
        items.append(CommGroupItem(
            comm=comm,
            pids=unique_pids,  # In cluster-comm, this means unique_pids
            cpu=f"{cpu_util:.2f}%",
            kernel=f"{kernel_ratio:.2f}%",
            event="normal"  # cluster-comm doesn't track events
        ))
    
    items.sort(key=lambda x: float(x.cpu.rstrip('%')), reverse=True)
    top_items = items[:args.top_n]
    
    # Build RiskInfo (no specific risk for cluster-comm)
    risk = create_risk_info(level="none")
    
    # Build summary using CommGroupSummary (shared with comm_top)
    summary = CommGroupSummary(
        total_comm_groups=len(items),
        high_kernel_groups=0  # cluster-comm doesn't track this
    )
    
    # Build time range
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts'),
        samples[-1].get('ts') if len(samples) > 0 else None
    )
    
    # Build output using ClusterCommOutput (comm_groups data type)
    output = ClusterCommOutput(
        _risk=risk,
        comm_groups=top_items,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
