#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Clustering - Cluster samples by process name (comm) to analyze process group CPU usage

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


def cmd_cluster_comm(engine, args):
    """[Skill] Cluster samples by comm (process name) to analyze process group CPU usage"""
    # Get filtered samples by time range and CPU
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None)
    )
    
    if not samples:
        print(json.dumps({
            "error": "No samples found",
            "filters": {
                "cpu_id": getattr(args, 'cpu_id', None),
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    # Calculate duration from samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Aggregate by comm - 使用 core/s 作为主要指标
    comm_stats = defaultdict(lambda: {
        'record_count': 0,
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0,
        'total_core_sec': 0.0,
        'pids': set(),
        'unique_pids': 0
    })
    
    for s in samples:
        comm = s['comm']
        comm_stats[comm]['record_count'] += 1
        comm_stats[comm]['pids'].add(s['pid'])
        
        # Accumulate core/s values for accurate CPU utilization
        core_val = s.get('core_per_sec') or 0
        comm_stats[comm]['total_core_sec'] += core_val
        
        # 使用 SymbolStack.is_leaf_kernel 准确判断 user/kernel 模式
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
    
    # Calculate utilization and prepare results
    results = []
    
    for comm, stats in comm_stats.items():
        unique_pids = len(stats['pids'])
        total_core_sec = stats['total_core_sec']
        
        # Calculate CPU utilization using core/s values (accurate method)
        # Total core-seconds divided by duration gives average CPU utilization
        if duration > 0:
            cpu_util = (total_core_sec / duration) * 100
        else:
            cpu_util = 0
        
        # Calculate user/kernel ratio (based on core/s)
        if total_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100
            user_ratio = (stats['user_core_sec'] / total_core_sec) * 100
        else:
            kernel_ratio = user_ratio = 0
        
        results.append({
            'comm': comm,
            'unique_pids': unique_pids,
            'record_count': stats['record_count'],
            'core_sec': round(total_core_sec, 4),
            'cpu_utilization_pct': round(cpu_util, 2),
            'kernel_ratio_pct': round(kernel_ratio, 2),
            'user_ratio_pct': round(user_ratio, 2)
        })
    
    # Sort by CPU utilization descending
    results.sort(key=lambda x: x['cpu_utilization_pct'], reverse=True)
    
    # Apply top-n limit
    top_results = results[:args.top_n]
    
    # Calculate summary statistics
    total_comm_util = sum(r['cpu_utilization_pct'] for r in results)
    total_unique_pids = sum(r['unique_pids'] for r in results)
    
    output = {
        'time_range': {
            'start': samples[0]['ts'],
            'end': samples[-1]['ts'],
            'duration_sec': round(duration, 2)
        },
        'filters': {
            'cpu_id': getattr(args, 'cpu_id', None),
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
            'total_cpu_utilization_pct': round(total_comm_util, 2)
        },
        'comm_groups': top_results
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！进程组 CPU 利用率聚类结果完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，进程组 CPU 利用率数据仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
