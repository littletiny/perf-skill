#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""
Process Variety Analysis - Count process variety to detect short-lived process storms

检测进程风暴/短生命周期进程。

注意：数据已按 1 秒聚合，样本数量无参考价值。
检测基于：
1. PID 数量（进程数）
2. CPU 利用率分布（core/s per PID）
3. 单秒出现频率（出现该进程的不同秒数）
"""

from collections import defaultdict
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import RiskInfo, ProcessVarietyItem, ProcessVarietySummary, ProcessVarietyOutput, TimeRange


def cmd_count_process_variety(engine, args):
    """[Skill] Count process variety - detect short-lived process storms"""
    
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
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Aggregate comm-pid stats
    comm_pid_stats = defaultdict(lambda: defaultdict(lambda: {
        'core_sec': 0.0,
        'seconds': set(),
    }))
    
    for s in samples:
        comm = s['comm']
        pid = s['pid']
        ts = s['ts']
        weight = engine.get_sample_weight(s)
        
        comm_pid_stats[comm][pid]['core_sec'] += weight
        second_key = int(ts)
        comm_pid_stats[comm][pid]['seconds'].add(second_key)
    
    # 使用 engine 统一接口获取 duration
    duration = engine.get_duration(samples)
    
    # Analyze variety
    variety_results = []
    storm_comms = []
    
    STORM_PID_THRESHOLD = args.storm_pid_threshold
    STORM_CPU_THRESHOLD = getattr(args, 'storm_cpu_threshold', 0.5)
    STORM_RATIO_THRESHOLD = getattr(args, 'storm_ratio_threshold', 2.0)
    
    for comm, pid_dict in sorted(comm_pid_stats.items(), key=lambda x: -len(x[1])):
        pid_count = len(pid_dict)
        total_comm_core_sec = sum(stats['core_sec'] for stats in pid_dict.values())
        cpu_per_pid = total_comm_core_sec / pid_count if pid_count > 0 else 0
        
        single_second_pids = sum(1 for stats in pid_dict.values() if len(stats['seconds']) == 1)
        short_lived_ratio = single_second_pids / pid_count if pid_count > 0 else 0
        
        total_samples_for_comm = sum(len(stats['seconds']) for stats in pid_dict.values())
        samples_per_pid = total_samples_for_comm / pid_count if pid_count > 0 else 0
        
        behavior = "normal"
        
        # Process storm detection (need at least 10 pids to be considered a storm)
        if pid_count >= 10:
            if samples_per_pid <= STORM_RATIO_THRESHOLD and short_lived_ratio > 0.5:
                behavior = "process_storm"
                storm_comms.append(comm)
            elif cpu_per_pid <= STORM_CPU_THRESHOLD and short_lived_ratio > 0.5:
                behavior = "process_storm"
                storm_comms.append(comm)
        
        # Skip normal behavior and small pids (< 10)
        if behavior == "normal" or pid_count < 10:
            continue
        
        # Calculate cpu_util percentage
        cpu_util = (total_comm_core_sec / duration * 100) if duration > 0 else 0
        
        # Create V2 data item
        variety_results.append(ProcessVarietyItem(
            comm=comm,
            unique_pids=pid_count,
            cpu_util=f"{cpu_util:.2f}%",
            behavior=behavior
        ))
    
    # Create risk info
    if storm_comms:
        risk = create_risk_info(
            level="critical",
            message=f"检测到 {len(storm_comms)} 个进程风暴（短生命周期进程）",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '检测到 {len(storm_comms)} 个进程风暴（短生命周期进程）' --risk 'critical' --hint '对每个进程名运行 cluster-comm --comm <comm> 进行详细分析'",
            patterns=["PROCESS_STORM"],
            pending_targets=storm_comms
        )
    else:
        risk = create_risk_info(level="none")
    
    # Build output
    top_n = getattr(args, 'top_n', 20)
    top_results = variety_results[:top_n]
    
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    # Build summary with truncation info
    summary = ProcessVarietySummary(
        total_processes=len(variety_results),
        storm_detected=len(storm_comms) > 0,
        storm_count=len(storm_comms)
    )
    
    output = ProcessVarietyOutput(
        _risk=risk,
        process_variety=top_results,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
