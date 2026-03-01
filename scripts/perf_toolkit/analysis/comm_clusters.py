#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Clustering - Cluster samples by process name (comm) to analyze process group CPU usage

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。

V2 版本：使用统一数据模型，与 comm_top 共享数据结构，CPU 利用率计算收拢到 engine
"""

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, CommGroupItem, ClusterCommOutput, TimeRange
)


def cmd_cluster_comm(engine, args):
    """[Skill] Cluster samples by comm (process name) to analyze process group CPU usage"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # 使用 engine 统一接口获取 comm 级 CPU 利用率
    comm_util = engine.get_comm_cpu_util(samples)
    
    # Build results using unified data model (same as comm_top)
    items = []
    for comm, info in comm_util.items():
        unique_pids = info['pid_count']
        cpu_util = info['total_pct']
        
        # 计算 kernel 占比
        if info['total_pct'] > 0:
            kernel_ratio = (info['kernel_pct'] / info['total_pct']) * 100
        else:
            kernel_ratio = 0
        
        # Determine event (skip normal events in output)
        if kernel_ratio > 50:
            event = f"<HIGH_KERNEL_RATIO:{kernel_ratio:.1f}%>"
        elif cpu_util > 10 and unique_pids >= 5:
            avg_cpu = cpu_util / unique_pids
            if avg_cpu < 1:
                event = f"<MANY_SMALL_PROCESSES:{unique_pids}p/{avg_cpu:.2f}%>"
            else:
                event = "normal"
        else:
            event = "normal"
        
        # Skip normal events
        if event == "normal":
            continue
        
        # cluster-comm uses same CommGroupItem as comm_top
        # but with different semantics in 'pids' field (unique_pids vs pid_count)
        items.append(CommGroupItem(
            comm=comm,
            pids=unique_pids,  # In cluster-comm, this means unique_pids
            cpu=f"{cpu_util:.2f}%",
            kernel=f"{kernel_ratio:.2f}%",
            event=event
        ))
    
    items.sort(key=lambda x: float(x.cpu.rstrip('%')), reverse=True)
    top_items = items[:args.top_n]
    
    # Build RiskInfo (no specific risk for cluster-comm)
    risk = create_risk_info(level="none")
    
    # Build time range
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts'),
        samples[-1].get('ts') if len(samples) > 0 else None
    )
    
    # Build output using ClusterCommOutput (comm_groups data type, no summary)
    output = ClusterCommOutput(
        _risk=risk,
        comm_groups=top_items,
        time_range=time_range
    )
    
    builder.print_output(output)
