#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization and thread states

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine

分析各 CPU 核心的负载分布，识别负载不均衡、线程休眠模式等问题。
"""

from collections import defaultdict
from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import RiskInfo, CoreItem, CoreDistributionOutput, TimeRange


@command("analyze-core-distribution")
def cmd_analyze_core_distribution(builder, engine, args, samples):
    """[Skill] Analyze CPU core utilization distribution for a process"""
    
    # 使用 engine 统一接口获取核心级 CPU 利用率
    core_util = engine.get_core_cpu_util(samples)
    
    # Build core list with filtering (only show saturated cores > 90%)
    core_list = []
    for cpu_id, info in sorted(core_util.items(), key=lambda x: x[1]['total_pct'], reverse=True):
        if info['total_pct'] > 90:
            core_list.append(CoreItem(
                cpu_id=cpu_id,
                total_cpu_util=f"{info['total_pct']:.2f}%",
                kernel_cpu_util=f"{info['kernel_pct']:.2f}%"
            ))
    
    # Apply top_n limit
    top_n = getattr(args, 'top_n', 10)
    core_list = core_list[:top_n]
    
    # Aggregate comm CPU utilization for hint generation
    comm_weight = defaultdict(float)
    for s in samples:
        comm = s.get('comm', '')
        if comm:
            weight = engine.get_sample_weight(s)
            comm_weight[comm] += weight
    
    # Identify imbalance
    if core_list:
        max_util = float(core_list[0].total_cpu_util.rstrip('%'))
        min_util = float(core_list[-1].total_cpu_util.rstrip('%'))
        avg_util = sum(float(c.total_cpu_util.rstrip('%')) for c in core_list) / len(core_list)
        
        imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
        
        if imbalance_ratio > 10 and max_util > 50:
            imbalance_level = "CRITICAL"
        elif imbalance_ratio > 5:
            imbalance_level = "HIGH"
        elif imbalance_ratio > 2:
            imbalance_level = "MEDIUM"
        else:
            imbalance_level = "LOW"
        
        # All cores in core_list are saturated (already filtered above)
        saturated_cores = core_list
        
        # Determine target comm for hint
        user_comm = getattr(args, 'comm', None)
        top_comm = max(comm_weight, key=comm_weight.get) if comm_weight else None
        target_comm = user_comm or top_comm or '<comm>'
        
        # Determine risk level
        if imbalance_level == "CRITICAL":
            risk_info = create_risk_info(
                level="critical",
                message="负载严重不均衡: 单核满载，其他核心空闲",
                hint=f"[必须] 添加到 Trace: spear trace add --desc '负载严重不均衡: 单核满载，其他核心空闲' --hint 'cluster-symbols --comm {target_comm}'",
                patterns=["SINGLE_CORE_SATURATION"]
            )
        elif len(saturated_cores) == 1 and len(core_list) > 1:
            risk_info = create_risk_info(
                level="warning",
                message=f"单核满载 (CPU {saturated_cores[0].cpu_id})",
                hint=f"[必须] 添加到 Trace: spear trace add --desc '单核满载 (CPU {saturated_cores[0].cpu_id})' --hint 'cluster-symbols --comm {target_comm}'",
                patterns=["SINGLE_CORE_SATURATION"]
            )
        else:
            risk_info = None
    else:
        imbalance_level = "UNKNOWN"
        saturated_cores = []
        risk_info = None
    
    # Create time range
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    # Build output (no summary for cleaner output)
    output = CoreDistributionOutput(
        _risk=risk_info,
        cores=core_list,
        time_range=time_range
    )
    
    return output
