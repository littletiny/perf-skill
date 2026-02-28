#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization and thread states

分析各 CPU 核心的负载分布，识别负载不均衡、线程休眠模式等问题。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability, format_percentage_with_ci


def cmd_analyze_core_distribution(engine, args):
    """[Skill] Analyze CPU core utilization distribution for a process"""
    
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
        return print(json.dumps({
            "error": "No samples found",
            "filters": {
                "pid": getattr(args, 'pid', None),
                "cpu_id": getattr(args, 'cpu_id', None)
            }
        }, indent=2))
    
    # Calculate duration
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    total_samples = len(samples)
    
    # Get total core/s
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    # Analyze per-core distribution
    core_stats = defaultdict(lambda: {
        'sample_count': 0,
        'total_core_per_sec': 0.0,
        'symbols': defaultdict(float),
        'states': defaultdict(int)  # active, sleeping, etc.
    })
    
    sleep_indicators = ['nanosleep', 'epoll_wait', 'futex_wait', 'schedule', 
                        'finish_task_switch', 'do_nanosleep', 'hrtimer_nanosleep']
    
    for s in samples:
        cpu_id = s.get('cpu')
        core_per_sec = s.get('core_per_sec', 0)
        
        if cpu_id is None:
            continue
        
        core_stats[cpu_id]['sample_count'] += 1
        core_stats[cpu_id]['total_core_per_sec'] += core_per_sec
        
        # Analyze stack symbols
        stack = s.get('stack')
        if stack:
            normalized_names = stack.get_normalized_names()
            
            # Check for sleep indicators
            is_sleeping = any(indicator in ' '.join(normalized_names) 
                            for indicator in sleep_indicators)
            
            if is_sleeping:
                core_stats[cpu_id]['states']['sleeping'] += 1
            else:
                core_stats[cpu_id]['states']['active'] += 1
            
            # Track top symbols for this core
            for sym in normalized_names[:3]:  # Top 3 symbols
                core_stats[cpu_id]['symbols'][sym] += core_per_sec
    
    # Calculate distribution metrics
    active_cores = len(core_stats)
    total_core_capacity = active_cores * duration if duration > 0 else 1
    
    # Sort cores by utilization
    core_list = []
    for cpu_id, stats in sorted(core_stats.items(), key=lambda x: x[1]['total_core_per_sec'], reverse=True):
        utilization = (stats['total_core_per_sec'] / duration * 100) if duration > 0 else 0
        sample_ratio = (stats['sample_count'] / total_samples * 100) if total_samples > 0 else 0
        
        # Get top symbols for this core
        top_symbols = sorted(stats['symbols'].items(), 
                           key=lambda x: x[1], reverse=True)[:3]
        
        core_list.append({
            "cpu_id": cpu_id,
            "utilization_pct": round(utilization, 2),
            "sample_count": stats['sample_count'],
            "sample_ratio_pct": round(sample_ratio, 2),
            "core_seconds": round(stats['total_core_per_sec'], 4),
            "states": dict(stats['states']),
            "top_symbols": [{"symbol": s, "core_sec": round(c, 4)} for s, c in top_symbols]
        })
    
    # Identify imbalance
    if core_list:
        max_util = core_list[0]['utilization_pct']
        min_util = core_list[-1]['utilization_pct']
        avg_util = sum(c['utilization_pct'] for c in core_list) / len(core_list)
        
        imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
        
        # Classification
        if imbalance_ratio > 10 and max_util > 50:
            imbalance_level = "CRITICAL"
            imbalance_desc = "单核满载，其他核心几乎空闲"
        elif imbalance_ratio > 5:
            imbalance_level = "HIGH"
            imbalance_desc = "负载严重不均衡"
        elif imbalance_ratio > 2:
            imbalance_level = "MEDIUM"
            imbalance_desc = "负载不均衡"
        else:
            imbalance_level = "LOW"
            imbalance_desc = "负载相对均衡"
    else:
        imbalance_level = "UNKNOWN"
        imbalance_desc = "无法计算"
        imbalance_ratio = 0
        max_util = min_util = avg_util = 0
    
    # Detect patterns
    patterns = []
    
    # Check for single-core saturation
    saturated_cores = [c for c in core_list if c['utilization_pct'] > 80]
    if len(saturated_cores) == 1 and len(core_list) > 1:
        patterns.append({
            "type": "SINGLE_CORE_SATURATION",
            "description": f"核心 {saturated_cores[0]['cpu_id']} 满载，其他 {len(core_list)-1} 个核心利用率低",
            "suggestion": "检查锁竞争、CPU亲和性绑定或应用层主动休眠"
        })
    
    # Check for sleeping threads
    cores_with_sleep = [c for c in core_list 
                       if c['states'].get('sleeping', 0) > c['states'].get('active', 0)]
    if len(cores_with_sleep) > len(core_list) * 0.5:
        patterns.append({
            "type": "MAJORITY_SLEEPING",
            "description": f"{len(cores_with_sleep)}/{len(core_list)} 个核心线程主要处于休眠状态",
            "suggestion": "检查应用层是否使用nanosleep/epoll_wait进行主动退避"
        })
    
    # Check for wide distribution but low utilization
    if len(core_list) > 10 and avg_util < 10:
        patterns.append({
            "type": "WIDE_DISTRIBUTION_LOW_UTIL",
            "description": f"分布在 {len(core_list)} 个核心，但平均利用率仅 {avg_util:.1f}%",
            "suggestion": "线程数充足但实际工作少，检查是否有全局锁或调度问题"
        })
    
    output = {
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            "pid": getattr(args, 'pid', None),
            "comm": getattr(args, 'comm', None)
        },
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "summary": {
            "total_cores_with_activity": active_cores,
            "total_samples": total_samples,
            "max_utilization_pct": round(max_util, 2),
            "min_utilization_pct": round(min_util, 2),
            "avg_utilization_pct": round(avg_util, 2),
            "imbalance_level": imbalance_level,
            "imbalance_description": imbalance_desc,
            "imbalance_ratio": round(imbalance_ratio, 2)
        },
        "cores": core_list,
        "patterns": patterns
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！分布分析结果不可信。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
