#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

Specialized for identifying "many small processes consuming resources collectively" scenarios:
- High aggregate CPU usage across many processes with same comm
- Low individual process CPU usage
- Useful for detecting worker pool issues, connection storms, etc.

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

from collections import defaultdict
from ..core.format_utils import format_percent, format_core_sec
from ..core.output_builder import OutputBuilder


def cmd_get_comm_top(engine, args):
    """[Skill] Get top N comm groups by aggregated CPU utilization"""
    
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
    filters = {
        "cpu_id": getattr(args, 'cpu_id', None),
        "pid": getattr(args, 'pid', None),
        "comm": getattr(args, 'comm', None),
        "comm_regex": getattr(args, 'comm_regex', None),
        "start_time": getattr(args, 'start_time', None),
        "end_time": getattr(args, 'end_time', None)
    }
    if builder.check_empty_samples(samples, filters=filters):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Calculate duration
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Aggregate by comm
    comm_stats = defaultdict(lambda: {
        'pids': defaultdict(lambda: {'core_sec': 0.0, 'kernel_core_sec': 0.0, 'user_core_sec': 0.0}),
        'total_core_sec': 0.0,
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0
    })
    
    for s in samples:
        comm = s['comm']
        pid = s['pid']
        core_val = s.get('core_per_sec') or 0
        
        comm_stats[comm]['pids'][pid]['core_sec'] += core_val
        comm_stats[comm]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['user_core_sec'] += core_val
    
    # Calculate aggregated statistics
    total_unique_pids = sum(len(stats['pids']) for stats in comm_stats.values())
    high_kernel_groups = []
    results = []
    
    for comm, stats in comm_stats.items():
        pids_data = stats['pids']
        pid_count = len(pids_data)
        total_core_sec = stats['total_core_sec']
        
        aggregate_cpu_util = (total_core_sec / duration) * 100 if duration > 0 else 0
        avg_cpu_per_process = aggregate_cpu_util / pid_count if pid_count > 0 else 0
        density_index = aggregate_cpu_util / pid_count if pid_count > 0 else 0
        
        if total_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100
        else:
            kernel_ratio = 0
        
        # Track high kernel groups for risk
        if kernel_ratio > 50 and aggregate_cpu_util > 5:
            high_kernel_groups.append(comm)
        
        results.append({
            'comm': comm,
            'pid_count': pid_count,
            'cpu_pct': format_percent(aggregate_cpu_util),
            'kernel_pct': format_percent(kernel_ratio),
            'total_core_sec': format_core_sec(total_core_sec),
            'avg_cpu_per_process_pct': format_percent(avg_cpu_per_process),
            'density_index': round(density_index, 4)
        })
    
    # Sort by CPU utilization descending
    results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    top_results = results[:top_n]
    
    # Add risk for high kernel groups
    if len(high_kernel_groups) > 0:
        risk_level = "warning" if len(high_kernel_groups) <= 2 else "critical"
        cluster_commands = [f"cluster-symbols --comm {comm}" for comm in high_kernel_groups]
        builder.add_risk(
            risk_level,
            f"发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%)未分析",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%): {', '.join(high_kernel_groups)}' --risk '{risk_level}' --hint '必须对每个进程运行: {'; '.join(cluster_commands)}'",
            patterns=["MULTI_HIGH_KERNEL"],
            targets=high_kernel_groups
        )
    
    # Build and output
    result = builder.build(
        data_type="comm_groups",
        data=top_results,
        summary={
            "total_comm_groups": len(results),
            "high_kernel_groups": len(high_kernel_groups)
        }
    )
    
    builder.print_json(result)
