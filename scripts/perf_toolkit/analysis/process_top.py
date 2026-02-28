#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Top - Get top N processes by CPU utilization

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability


def cmd_get_process_top(engine, args):
    """[Skill] Get top N processes by CPU utilization"""
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
    total_samples = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    # Aggregate by (comm, pid) - collect both sample counts and core/s values
    process_stats = defaultdict(lambda: {
        'comm': '',
        'sample_count': 0,
        'kernel_samples': 0,
        'user_samples': 0,
        'kernel_core_per_sec': 0.0,
        'user_core_per_sec': 0.0,
        'total_core_per_sec': 0.0
    })
    
    for s in samples:
        key = (s['comm'], s['pid'])
        process_stats[key]['comm'] = s['comm']
        process_stats[key]['pid'] = s['pid']
        process_stats[key]['sample_count'] += 1
        
        core_val = s.get('core_per_sec') or 0
        process_stats[key]['total_core_per_sec'] += core_val
        
        # 使用 SymbolStack.is_leaf_kernel 准确判断 user/kernel 模式
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            process_stats[key]['kernel_samples'] += 1
            process_stats[key]['kernel_core_per_sec'] += core_val
        else:
            process_stats[key]['user_samples'] += 1
            process_stats[key]['user_core_per_sec'] += core_val
    
    # Calculate utilization and prepare results
    results = []
    
    for (comm, pid), stats in process_stats.items():
        sample_count = stats['sample_count']
        total_core = stats['total_core_per_sec']
        
        # Calculate CPU utilization directly from core/s
        # Process utilization = (total_core / duration) * 100
        if duration > 0:
            cpu_util = (total_core / duration) * 100
        else:
            cpu_util = 0
        
        # For user/kernel breakdown, use the sample-based ratio from this process
        if sample_count > 0:
            kernel_ratio = (stats['kernel_samples'] / sample_count) * 100
            user_ratio = (stats['user_samples'] / sample_count) * 100
        else:
            kernel_ratio = user_ratio = 0
        
        results.append({
            'comm': comm,
            'pid': pid,
            'sample_count': sample_count,
            'cpu_utilization_pct': round(cpu_util, 2),
            'sample_ratio_pct': round((sample_count / total_samples) * 100, 2) if total_samples > 0 else 0,
            'kernel_ratio_pct': round(kernel_ratio, 2),
            'user_ratio_pct': round(user_ratio, 2)
        })
    
    # Sort by CPU utilization descending
    results.sort(key=lambda x: x['cpu_utilization_pct'], reverse=True)
    
    # Apply top-n limit
    top_results = results[:args.top_n]
    
    # Calculate summary statistics
    total_proc_util = sum(r['cpu_utilization_pct'] for r in results)
    
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
        'reliability': {
            'level': reliability_level,
            'warning': warning_msg,
            'metrics': metrics
        },
        'summary': {
            'total_processes': len(results),
            'shown_processes': len(top_results),
            'total_cpu_utilization_pct': round(total_proc_util, 2)
        },
        'processes': top_results
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！进程 CPU 利用率排序完全不可信。"
    elif reliability_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "采样率偏低，进程 CPU 利用率数据仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
