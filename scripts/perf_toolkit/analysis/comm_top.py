#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

Specialized for identifying "many small processes consuming resources collectively" scenarios:
- High aggregate CPU usage across many processes with same comm
- Low individual process CPU usage
- Useful for detecting worker pool issues, connection storms, etc.

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。

V2 版本：使用统一数据模型
"""

from collections import defaultdict

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, CommGroupItem, CommTopOutput, TimeRange
)


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
        core_val = engine.get_sample_weight(s)
        
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
        
        if total_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100
        else:
            kernel_ratio = 0
        
        # Track high kernel groups for risk
        if kernel_ratio > 50 and aggregate_cpu_util > 5:
            high_kernel_groups.append(comm)
        
        # Build event description (skip normal events)
        if aggregate_cpu_util > 10 and avg_cpu_per_process < 1 and pid_count >= 5:
            event = f"MANY_SMALL_PROCESSES: {pid_count}个进程，每个仅消耗{avg_cpu_per_process:.2f}% CPU"
        elif kernel_ratio > 50:
            event = f"HIGH_KERNEL: 内核态占比 {kernel_ratio:.1f}%"
        else:
            event = "normal"
            continue  # Skip normal events
        
        results.append(CommGroupItem.from_stats(
            comm=comm,
            pid_count=pid_count,
            aggregate_cpu=aggregate_cpu_util,
            kernel_ratio=kernel_ratio,
            event_desc=event
        ))
    
    # Sort by CPU utilization descending
    results.sort(key=lambda x: float(x.cpu.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    top_results = results[:top_n]
    
    # Build RiskInfo
    if len(high_kernel_groups) > 0:
        risk_level = "warning" if len(high_kernel_groups) <= 2 else "critical"
        cluster_commands = [f"cluster-symbols --comm {comm}" for comm in high_kernel_groups]
        risk = create_risk_info(
            level=risk_level,
            message=f"发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%)未分析",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%): {', '.join(high_kernel_groups)}' --risk '{risk_level}' --hint '必须对每个进程运行: {'; '.join(cluster_commands)}'",
            patterns=["MULTI_HIGH_KERNEL"],
            pending_targets=high_kernel_groups
        )
    else:
        risk = create_risk_info(level="none")
    
    # Build time range
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts'),
        samples[-1].get('ts') if len(samples) > 0 else None
    )
    
    # Build output (no summary for cleaner output)
    output = CommTopOutput(
        _risk=risk,
        comm_groups=top_results,
        time_range=time_range
    )
    
    builder.print_output(output)
