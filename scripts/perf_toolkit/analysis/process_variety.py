#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Variety Analysis - Count process variety to detect short-lived process storms

检测进程风暴/短生命周期进程。

注意：数据已按 1 秒聚合，样本数量无参考价值。
检测基于：
1. PID 数量（进程数）
2. CPU 利用率分布（core/s per PID）
3. 单秒出现频率（出现该进程的不同秒数）
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


def cmd_count_process_variety(engine, args):
    """
    [Skill] Count process variety - detect short-lived process storms
    
    Analyzes the diversity of PIDs per process name to detect:
    - Process storms (high PID count, low CPU per PID)
    - Short-lived processes (single second appearance per PID)
    - Normal long-running processes (few PIDs, sustained CPU)
    
    Note: Data is aggregated per second, sample counts are not meaningful.
    Analysis is based on CPU utilization (core/s) and time coverage.
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
                'cpu_id': getattr(args, 'cpu_id', None),
                'pid': getattr(args, 'pid', None),
                'comm': getattr(args, 'comm', None),
                'comm_regex': getattr(args, 'comm_regex', None),
                'start_time': getattr(args, 'start_time', None),
                'end_time': getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Count variety: comm -> {pid -> {'core_sec': x, 'seconds': set()}}
    comm_pid_stats = defaultdict(lambda: defaultdict(lambda: {
        'core_sec': 0.0,
        'seconds': set(),  # Track which seconds this PID appears in
        'first_ts': None,
        'last_ts': None
    }))
    
    for s in samples:
        comm = s['comm']
        pid = s['pid']
        ts = s['ts']
        core_per_sec = s.get('core_per_sec', 0)
        
        comm_pid_stats[comm][pid]['core_sec'] += core_per_sec
        # Round timestamp to nearest second for tracking
        second_key = int(ts)
        comm_pid_stats[comm][pid]['seconds'].add(second_key)
        
        if comm_pid_stats[comm][pid]['first_ts'] is None or ts < comm_pid_stats[comm][pid]['first_ts']:
            comm_pid_stats[comm][pid]['first_ts'] = ts
        if comm_pid_stats[comm][pid]['last_ts'] is None or ts > comm_pid_stats[comm][pid]['last_ts']:
            comm_pid_stats[comm][pid]['last_ts'] = ts
    
    # Analyze each comm
    variety_results = []
    behavior_alerts = []
    
    # Behavior detection thresholds
    STORM_PID_THRESHOLD = args.storm_pid_threshold
    STORM_CPU_THRESHOLD = getattr(args, 'storm_cpu_threshold', 0.5)  # Default 0.5 core/s per PID
    
    for comm, pid_dict in sorted(comm_pid_stats.items(), key=lambda x: -len(x[1])):
        pid_count = len(pid_dict)
        total_comm_core_sec = sum(stats['core_sec'] for stats in pid_dict.values())
        cpu_per_pid = total_comm_core_sec / pid_count if pid_count > 0 else 0
        
        # Detect lifecycle patterns
        single_second_pids = sum(1 for stats in pid_dict.values() if len(stats['seconds']) == 1)
        short_lived_ratio = single_second_pids / pid_count if pid_count > 0 else 0
        
        # Estimate process duration for multi-second PIDs
        durations = []
        for pid, stats in pid_dict.items():
            if stats['first_ts'] is not None and stats['last_ts'] is not None:
                durations.append(stats['last_ts'] - stats['first_ts'])
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Determine behavior pattern
        behavior = "normal"
        alert = None
        
        # Storm detection: many PIDs with low average CPU per PID
        if pid_count >= STORM_PID_THRESHOLD and cpu_per_pid <= STORM_CPU_THRESHOLD:
            behavior = "process_storm"
            alert = {
                "type": "BEHAVIOR_PROCESS_STORM",
                "severity": "HIGH",
                "description": f"检测到 {comm} 进程风暴：{pid_count} 个进程在 {duration:.2f}s 内活动，"
                              f"平均每个进程仅消耗 {cpu_per_pid:.3f} core/s",
                "indicators": ["高频进程创建", "可能的脚本循环或监控风暴"]
            }
            behavior_alerts.append(alert)
        elif short_lived_ratio > 0.8 and pid_count > 20:
            behavior = "short_lived_heavy"
            alert = {
                "type": "BEHAVIOR_SHORT_LIVED",
                "severity": "MEDIUM",
                "description": f"{comm} 单秒生命周期进程占比 {short_lived_ratio*100:.1f}%",
                "indicators": ["频繁进程创建销毁", "可能的批量脚本执行"]
            }
            behavior_alerts.append(alert)
        elif pid_count == 1 and cpu_per_pid > 10:
            behavior = "long_running"
        
        result = {
            "comm": comm,
            "unique_pids": pid_count,
            "total_core_sec": round(total_comm_core_sec, 4),
            "cpu_per_pid": round(cpu_per_pid, 4),
            "single_second_pids": single_second_pids,
            "short_lived_ratio": round(short_lived_ratio, 2),
            "avg_duration_sec": round(avg_duration, 3) if avg_duration > 0 else None,
            "behavior": behavior
        }
        
        if alert:
            result["alert"] = alert
        
        variety_results.append(result)
    
    # Summary statistics
    total_unique_pids = sum(len(pids) for pids in comm_pid_stats.values())
    storm_comms = [r for r in variety_results if r["behavior"] == "process_storm"]
    short_lived_comms = [r for r in variety_results if r["behavior"] == "short_lived_heavy"]
    
    output = {
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            'cpu_id': getattr(args, 'cpu_id', None),
            'pid': getattr(args, 'pid', None),
            'comm': getattr(args, 'comm', None),
            'comm_regex': getattr(args, 'comm_regex', None),
            'start_time': getattr(args, 'start_time', None),
            'end_time': getattr(args, 'end_time', None)
        },
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "summary": {
            "total_processes": len(comm_pid_stats),
            "total_unique_pids": total_unique_pids,
            "process_storm_detected": len(storm_comms) > 0,
            "storm_process_count": len(storm_comms),
            "short_lived_heavy_count": len(short_lived_comms)
        },
        "behavior_alerts": behavior_alerts,
        "process_variety": variety_results[:args.top_n]
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！进程多样性分析结果完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，进程生命周期分析结果仅供参考。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
