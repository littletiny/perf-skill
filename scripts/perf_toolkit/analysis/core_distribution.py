#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization and thread states

V2 版本：使用统一数据模型

分析各 CPU 核心的负载分布，识别负载不均衡、线程休眠模式等问题。

注意：数据已按 1 秒聚合，样本数量仅作为记录数参考，分析基于 core/s 值。
"""

from collections import defaultdict
from ..core.format_utils import format_percent
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import RiskInfo, CoreItem, CoreDistributionSummary, CoreDistributionOutput, TimeRange


def cmd_analyze_core_distribution(engine, args):
    """[Skill] Analyze CPU core utilization distribution for a process"""
    
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
    if builder.check_empty_samples(samples, filters={
        "pid": getattr(args, 'pid', None),
        "cpu_id": getattr(args, 'cpu_id', None)
    }):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Calculate duration
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Aggregate core stats
    core_stats = defaultdict(lambda: {
        'record_count': 0,
        'total_core_per_sec': 0.0,
    })
    comm_core_sec = defaultdict(float)
    
    for s in samples:
        cpu_id = s.get('cpu')
        core_per_sec = engine.get_sample_weight(s)
        comm = s.get('comm', '')
        
        if cpu_id is None:
            continue
        
        core_stats[cpu_id]['record_count'] += 1
        core_stats[cpu_id]['total_core_per_sec'] += core_per_sec
        if comm:
            comm_core_sec[comm] += core_per_sec
    
    # Build core list
    core_list = []
    for cpu_id, stats in sorted(core_stats.items(), key=lambda x: x[1]['total_core_per_sec'], reverse=True):
        utilization = (stats['total_core_per_sec'] / duration * 100) if duration > 0 else 0
        
        state = "normal"
        if utilization > 90:
            state = "saturated"
        elif utilization < 5:
            state = "idle"
        
        core_list.append(CoreItem(
            cpu_id=cpu_id,
            utilization=format_percent(utilization),
            state=state
        ))
    
    # Identify imbalance
    if core_list:
        max_util = float(core_list[0].utilization.rstrip('%'))
        min_util = float(core_list[-1].utilization.rstrip('%'))
        avg_util = sum(float(c.utilization.rstrip('%')) for c in core_list) / len(core_list)
        
        imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
        
        if imbalance_ratio > 10 and max_util > 50:
            imbalance_level = "CRITICAL"
        elif imbalance_ratio > 5:
            imbalance_level = "HIGH"
        elif imbalance_ratio > 2:
            imbalance_level = "MEDIUM"
        else:
            imbalance_level = "LOW"
        
        saturated_cores = [c for c in core_list if c.state == "saturated"]
        
        # Determine target comm for hint
        user_comm = getattr(args, 'comm', None)
        top_comm = max(comm_core_sec, key=comm_core_sec.get) if comm_core_sec else None
        target_comm = user_comm or top_comm or '<comm>'
        
        # Determine risk level
        if imbalance_level == "CRITICAL":
            risk_level = "critical"
            risk_info = create_risk_info(
                level="critical",
                message="负载严重不均衡: 单核满载，其他核心空闲",
                hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '负载严重不均衡: 单核满载，其他核心空闲' --risk 'critical' --hint 'cluster-symbols --comm {target_comm}'",
                patterns=["SINGLE_CORE_SATURATION"]
            )
        elif len(saturated_cores) == 1 and len(core_list) > 1:
            risk_level = "warning"
            risk_info = create_risk_info(
                level="warning",
                message=f"单核满载 (CPU {saturated_cores[0].cpu_id})",
                hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '单核满载 (CPU {saturated_cores[0].cpu_id})' --risk 'warning' --hint 'cluster-symbols --comm {target_comm}'",
                patterns=["SINGLE_CORE_SATURATION"]
            )
        else:
            risk_level = "none"
            risk_info = None
    else:
        imbalance_level = "UNKNOWN"
        max_util = min_util = avg_util = 0
        saturated_cores = []
        risk_level = "none"
        risk_info = None
    
    # Build summary
    summary = CoreDistributionSummary(
        imbalance_level=imbalance_level,
        max_utilization=format_percent(max_util),
        min_utilization=format_percent(min_util),
        saturated_cores=len(saturated_cores)
    )
    
    # Create time range
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    # Build output
    output = CoreDistributionOutput(
        _risk=risk_info,
        cores=core_list,
        summary=summary,
        time_range=time_range
    )
    
    # Print output
    builder.print_output(output)
