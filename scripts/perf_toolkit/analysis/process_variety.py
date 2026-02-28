#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Variety Analysis - Count process variety to detect short-lived process storms

检测进程风暴/短生命周期进程。

注意：数据已按 1 秒聚合，样本数量无参考价值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range
from ..core.risk_mixin import RiskAwareOutput


def cmd_count_process_variety(engine, args):
    """[Skill] Count process variety - detect short-lived process storms"""
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
        result = output.add_risk(
            "warning",
            "未找到样本数据",
            "检查过滤条件"
        ).build({
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(args, 'start_time', None),
                getattr(args, 'end_time', None)
            ),
            "available_range": engine.get_time_range()
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    comm_pid_stats = defaultdict(lambda: defaultdict(lambda: {
        'core_sec': 0.0,
        'seconds': set()
    }))
    
    for s in samples:
        comm = s['comm']
        pid = s['pid']
        ts = s['ts']
        core_per_sec = s.get('core_per_sec', 0)
        
        comm_pid_stats[comm][pid]['core_sec'] += core_per_sec
        second_key = int(ts)
        comm_pid_stats[comm][pid]['seconds'].add(second_key)
    
    variety_results = []
    storm_detected = False
    
    STORM_PID_THRESHOLD = args.storm_pid_threshold
    STORM_CPU_THRESHOLD = getattr(args, 'storm_cpu_threshold', 0.5)
    
    for comm, pid_dict in sorted(comm_pid_stats.items(), key=lambda x: -len(x[1])):
        pid_count = len(pid_dict)
        total_comm_core_sec = sum(stats['core_sec'] for stats in pid_dict.values())
        cpu_per_pid = total_comm_core_sec / pid_count if pid_count > 0 else 0
        
        single_second_pids = sum(1 for stats in pid_dict.values() if len(stats['seconds']) == 1)
        short_lived_ratio = single_second_pids / pid_count if pid_count > 0 else 0
        
        # Determine behavior pattern
        behavior = "normal"
        
        if pid_count >= STORM_PID_THRESHOLD and cpu_per_pid <= STORM_CPU_THRESHOLD:
            behavior = "process_storm"
            storm_detected = True
        elif short_lived_ratio > 0.8 and pid_count > 20:
            behavior = "short_lived_heavy"
            storm_detected = True
        
        variety_results.append({
            "comm": comm,
            "unique_pids": pid_count,
            "total_core_sec": round(total_comm_core_sec, 4),
            "cpu_per_pid": round(cpu_per_pid, 4),
            "short_lived_ratio": round(short_lived_ratio, 2),
            "behavior": behavior
        })
    
    # Add risk for process storm
    if storm_detected:
        output.add_risk(
            "critical",
            "检测到进程风暴！大量短生命周期进程",
            "检查脚本循环或监控风暴源",
            patterns=["PROCESS_STORM"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！进程多样性分析结果完全不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "total_processes": len(comm_pid_stats),
            "storm_detected": storm_detected
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "process_variety": variety_results[:args.top_n]
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
