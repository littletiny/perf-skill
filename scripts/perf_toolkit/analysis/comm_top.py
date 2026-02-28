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

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


def cmd_get_comm_top(engine, args):
    """[Skill] Get top N comm groups by aggregated CPU utilization
    
    This tool is specifically designed to identify scenarios where:
    - Many processes with the same name (comm) collectively consume high CPU
    - Individual processes have low CPU usage
    - Typical in: worker pools, connection handlers, micro-services, etc.
    """
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
                "cpu_id": getattr(args, 'cpu_id', None),
                "pid": getattr(args, 'pid', None),
                "comm": getattr(args, 'comm', None),
                "comm_regex": getattr(args, 'comm_regex', None),
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    # Calculate duration and data quality
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Aggregate by comm - 使用 core/s 作为主要指标
    # comm_stats[comm] = {
    #   'pids': {pid: {'core_sec': X, 'kernel_core_sec': X, 'user_core_sec': X}},
    #   'total_core_sec': X,
    #   'kernel_core_sec': X,
    #   'user_core_sec': X
    # }
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
        
        # Update per-pid stats
        comm_stats[comm]['pids'][pid]['core_sec'] += core_val
        
        # Update comm-level stats
        comm_stats[comm]['total_core_sec'] += core_val
        
        # User/kernel breakdown
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['user_core_sec'] += core_val
    
    # Calculate aggregated statistics
    total_unique_pids = sum(len(stats['pids']) for stats in comm_stats.values())
    results = []
    
    for comm, stats in comm_stats.items():
        pids_data = stats['pids']
        pid_count = len(pids_data)
        total_core_sec = stats['total_core_sec']
        
        # Aggregate CPU utilization (total across all processes)
        if duration > 0:
            aggregate_cpu_util = (total_core_sec / duration) * 100
        else:
            aggregate_cpu_util = 0
        
        # Per-process averages
        avg_cpu_per_process = aggregate_cpu_util / pid_count if pid_count > 0 else 0
        avg_core_sec_per_process = total_core_sec / pid_count if pid_count > 0 else 0
        
        # Process count percentage
        process_count_pct = (pid_count / total_unique_pids * 100) if total_unique_pids > 0 else 0
        
        # User/kernel ratio for this comm group (based on core/s)
        if total_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100
            user_ratio = (stats['user_core_sec'] / total_core_sec) * 100
        else:
            kernel_ratio = user_ratio = 0
        
        # Per-process user/kernel averages
        total_pid_kernel = sum(p['kernel_core_sec'] for p in pids_data.values())
        total_pid_user = sum(p['user_core_sec'] for p in pids_data.values())
        avg_kernel_per_process = total_pid_kernel / pid_count if pid_count > 0 else 0
        avg_user_per_process = total_pid_user / pid_count if pid_count > 0 else 0
        
        # Density index: aggregate CPU / process count
        # High value = each process contributes significantly
        # Low value = many processes with tiny contribution
        density_index = aggregate_cpu_util / pid_count if pid_count > 0 else 0
        
        # Calculate min/max per-process core/s for variance analysis
        pid_core_sec = [p['core_sec'] for p in pids_data.values()]
        min_core_sec_per_pid = min(pid_core_sec) if pid_core_sec else 0
        max_core_sec_per_pid = max(pid_core_sec) if pid_core_sec else 0
        
        # Check if this looks like a "many small processes" pattern
        # Criteria: high aggregate CPU, low per-process average, high process count
        is_many_small_pattern = (
            aggregate_cpu_util > 10 and  # Aggregate > 10%
            avg_cpu_per_process < 1 and   # Per process < 1%
            pid_count >= 5                # At least 5 processes
        )
        
        results.append({
            'comm': comm,
            'pid_count': pid_count,
            'process_count_pct': round(process_count_pct, 2),
            'aggregate_cpu_utilization_pct': round(aggregate_cpu_util, 2),
            'total_core_sec': round(total_core_sec, 4),
            'avg_cpu_per_process_pct': round(avg_cpu_per_process, 2),
            'avg_core_sec_per_process': round(avg_core_sec_per_process, 4),
            'density_index': round(density_index, 4),
            'kernel_ratio_pct': round(kernel_ratio, 2),
            'user_ratio_pct': round(user_ratio, 2),
            'avg_kernel_core_sec_per_process': round(avg_kernel_per_process, 4),
            'avg_user_core_sec_per_process': round(avg_user_per_process, 4),
            'min_core_sec_per_pid': round(min_core_sec_per_pid, 4),
            'max_core_sec_per_pid': round(max_core_sec_per_pid, 4),
            'is_many_small_pattern': is_many_small_pattern
        })
    
    # Sort by aggregate CPU utilization descending (default)
    # Or by density index if --sort-by-density is specified
    if getattr(args, 'sort_by_density', False):
        results.sort(key=lambda x: x['density_index'], reverse=True)
    else:
        results.sort(key=lambda x: x['aggregate_cpu_utilization_pct'], reverse=True)
    
    # Apply top-n limit
    top_n = getattr(args, 'top_n', 10)
    top_results = results[:top_n]
    
    # Identify patterns
    patterns = []
    
    # Check for "many small processes" pattern in top results
    many_small_comms = [r for r in top_results if r['is_many_small_pattern']]
    if many_small_comms:
        patterns.append({
            'type': 'MANY_SMALL_PROCESSES',
            'description': '大量小进程集体消耗资源模式',
            'affected_comms': [r['comm'] for r in many_small_comms],
            'suggestion': '检查 worker pool 配置、连接池大小、或请求分发策略。考虑减少进程数或合并任务。'
        })
    
    # Check for high variance in core/s per process (uneven load distribution)
    high_variance_comms = []
    for r in top_results:
        if r['pid_count'] >= 3 and r['max_core_sec_per_pid'] > r['min_core_sec_per_pid'] * 10:
            high_variance_comms.append(r['comm'])
    if high_variance_comms:
        patterns.append({
            'type': 'UNEVEN_LOAD_DISTRIBUTION',
            'description': '同类型进程间负载分布不均',
            'affected_comms': high_variance_comms,
            'suggestion': '检查负载均衡策略，部分进程过载而其他进程空闲。'
        })
    
    # Check for extreme density (single process dominating)
    low_density_comms = [r for r in top_results if r['density_index'] < 0.5 and r['pid_count'] >= 10]
    if low_density_comms:
        patterns.append({
            'type': 'EXTREME_PROCESS_PROLIFERATION',
            'description': '进程数量极多但单进程贡献极低',
            'affected_comms': [r['comm'] for r in low_density_comms],
            'suggestion': '可能存在进程泄漏或过度分片，建议审查进程创建逻辑。'
        })
    
    # Calculate summary
    total_aggregate_cpu = sum(r['aggregate_cpu_utilization_pct'] for r in results)
    total_processes = sum(r['pid_count'] for r in results)
    
    output = {
        'time_range': {
            'start': samples[0]['ts'],
            'end': samples[-1]['ts'],
            'duration_sec': round(duration, 2)
        },
        'filters': {
            'cpu_id': getattr(args, 'cpu_id', None),
            'pid': getattr(args, 'pid', None),
            'comm': getattr(args, 'comm', None),
            'comm_regex': getattr(args, 'comm_regex', None),
            'start_time': getattr(args, 'start_time', None),
            'end_time': getattr(args, 'end_time', None)
        },
        'data_quality': {
            'level': quality_level,
            'warning': warning_msg,
            'metrics': metrics
        },
        'summary': {
            'total_comm_groups': len(results),
            'shown_comm_groups': len(top_results),
            'total_unique_pids': total_unique_pids,
            'total_aggregate_cpu_utilization_pct': round(total_aggregate_cpu, 2),
            'patterns_detected': len(patterns)
        },
        'patterns': patterns,
        'comm_groups': top_results
    }
    
    # Add interpretation hints
    output['_interpretation'] = {
        'density_index': '密度指数 = 总CPU利用率 / 进程数。值越小表示单进程贡献越低，可能存在过度分片。',
        'avg_cpu_per_process_pct': '单进程平均CPU利用率，用于识别是否单个进程过载。',
        'avg_core_sec_per_process': '单进程平均消耗的 core/s，直接反映 CPU 消耗。',
        'is_many_small_pattern': '标记符合"大量小进程集体高消耗"特征的进程组。'
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！comm 组 CPU 利用率排序完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，comm 组 CPU 利用率数据仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
