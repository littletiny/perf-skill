#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Variety Analysis - Count process variety to detect short-lived process storms
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability


def cmd_count_process_variety(engine, args):
    """
    [Skill] Count process variety - detect short-lived process storms
    
    Analyzes the diversity of PIDs per process name to detect:
    - Process storms (high PID count, low samples per PID)
    - Short-lived processes (single sample per PID)
    - Normal long-running processes (few PIDs, many samples per PID)
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
    total_samples = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    # Count variety: comm -> {pid -> sample_count}
    comm_pid_samples = defaultdict(lambda: defaultdict(int))
    comm_timestamps = defaultdict(lambda: defaultdict(list))
    
    for s in samples:
        comm = s['comm']
        pid = s['pid']
        ts = s['ts']
        comm_pid_samples[comm][pid] += 1
        comm_timestamps[comm][pid].append(ts)
    
    # Analyze each comm
    variety_results = []
    behavior_alerts = []
    
    # Behavior detection thresholds
    STORM_PID_THRESHOLD = args.storm_pid_threshold
    STORM_RATIO_THRESHOLD = args.storm_ratio_threshold
    
    for comm, pid_dict in sorted(comm_pid_samples.items(), key=lambda x: -len(x[1])):
        pid_count = len(pid_dict)
        total_comm_samples = sum(pid_dict.values())
        samples_per_pid = total_comm_samples / pid_count if pid_count > 0 else 0
        
        # Detect lifecycle patterns
        single_sample_pids = sum(1 for c in pid_dict.values() if c == 1)
        short_lived_ratio = single_sample_pids / pid_count if pid_count > 0 else 0
        
        # Estimate process duration for multi-sample PIDs
        durations = []
        for pid, ts_list in comm_timestamps[comm].items():
            if len(ts_list) > 1:
                durations.append(max(ts_list) - min(ts_list))
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Determine behavior pattern
        behavior = "normal"
        alert = None
        
        if pid_count >= STORM_PID_THRESHOLD and samples_per_pid <= STORM_RATIO_THRESHOLD:
            behavior = "process_storm"
            alert = {
                "type": "BEHAVIOR_PROCESS_STORM",
                "severity": "HIGH",
                "description": f"检测到 {comm} 进程风暴：{pid_count} 个进程在 {duration:.2f}s 内启动，平均每个进程仅 {samples_per_pid:.1f} 个样本",
                "indicators": ["高频进程创建", "可能的脚本循环或监控风暴"]
            }
            behavior_alerts.append(alert)
        elif short_lived_ratio > 0.8 and pid_count > 20:
            behavior = "short_lived_heavy"
            alert = {
                "type": "BEHAVIOR_SHORT_LIVED",
                "severity": "MEDIUM",
                "description": f"{comm} 短生命周期进程占比 {short_lived_ratio*100:.1f}%",
                "indicators": ["频繁进程创建销毁", "可能的批量脚本执行"]
            }
            behavior_alerts.append(alert)
        elif pid_count == 1 and samples_per_pid > 100:
            behavior = "long_running"
        
        result = {
            "comm": comm,
            "unique_pids": pid_count,
            "total_samples": total_comm_samples,
            "samples_per_pid": round(samples_per_pid, 2),
            "single_sample_pids": single_sample_pids,
            "short_lived_ratio": round(short_lived_ratio, 2),
            "avg_duration_sec": round(avg_duration, 3) if avg_duration > 0 else None,
            "behavior": behavior
        }
        
        if alert:
            result["alert"] = alert
        
        variety_results.append(result)
    
    # Summary statistics
    total_unique_pids = sum(len(pids) for pids in comm_pid_samples.values())
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
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "summary": {
            "total_processes": len(comm_pid_samples),
            "total_unique_pids": total_unique_pids,
            "process_storm_detected": len(storm_comms) > 0,
            "storm_process_count": len(storm_comms),
            "short_lived_heavy_count": len(short_lived_comms)
        },
        "behavior_alerts": behavior_alerts,
        "process_variety": variety_results[:args.top_n]
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！进程多样性分析结果完全不可信。"
    elif reliability_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "采样率偏低，进程生命周期分析结果仅供参考。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
