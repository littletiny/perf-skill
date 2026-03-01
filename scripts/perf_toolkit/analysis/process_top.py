#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Top - Get top N processes by CPU utilization

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。

V2 版本：使用统一数据模型
"""

from collections import defaultdict

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, ProcessItem, ProcessTopOutput, TimeRange
)


def cmd_get_process_top(engine, args):
    """[Skill] Get top N processes by CPU utilization"""
    
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
    
    # Calculate duration
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Aggregate process stats
    process_stats = defaultdict(lambda: {
        'comm': '',
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0,
        'total_core_sec': 0.0
    })
    
    for s in samples:
        key = (s['comm'], s['pid'])
        process_stats[key]['comm'] = s['comm']
        process_stats[key]['pid'] = s['pid']
        
        core_val = engine.get_sample_weight(s)
        process_stats[key]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            process_stats[key]['kernel_core_sec'] += core_val
        else:
            process_stats[key]['user_core_sec'] += core_val
    
    # Build ProcessItem list
    # 计算 CPU utilization % (usr+sys)/sys 格式
    items = []
    for (comm, pid), stats in process_stats.items():
        total_cpu_util = (stats['total_core_sec'] / duration * 100) if duration > 0 else 0
        kernel_cpu_util = (stats['kernel_core_sec'] / duration * 100) if duration > 0 else 0
        
        items.append(ProcessItem.from_cpu_util(comm, pid, total_cpu_util, kernel_cpu_util))
    
    items.sort(key=lambda x: float(x.total_cpu_util.rstrip('%')), reverse=True)
    top_items = items[:args.top_n]
    
    # Build RiskInfo (no specific risk for process top)
    risk = create_risk_info(level="none")
    
    # Build time range
    time_range = None
    if samples:
        time_range = TimeRange.from_timestamps(
            samples[0].get('ts'),
            samples[-1].get('ts') if len(samples) > 0 else None
        )
    
    # Build output (no summary for cleaner output)
    output = ProcessTopOutput(
        _risk=risk,
        processes=top_items,
        time_range=time_range
    )
    
    builder.print_output(output)
