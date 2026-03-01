#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Top - Get top N processes by CPU utilization

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, ProcessItem, ProcessSummary, ProcessTopOutput, TimeRange
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
    
    # 使用 engine 统一接口获取进程级 CPU 利用率
    proc_util = engine.get_process_cpu_util(samples)
    
    # Build ProcessItem list
    items = [
        ProcessItem.from_cpu_util(
            info['comm'], 
            info['pid'], 
            info['total_pct'], 
            info['kernel_pct']
        )
        for info in proc_util.values()
    ]
    
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
    
    # Build summary with truncation info
    summary = ProcessSummary(
        total_processes=len(items),
        shown_processes=len(top_items)
    )
    
    # Build output
    output = ProcessTopOutput(
        _risk=risk,
        processes=top_items,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
