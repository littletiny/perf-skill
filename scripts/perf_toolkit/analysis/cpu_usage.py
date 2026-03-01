#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU Usage Analysis - Show CPU utilization for OS or specific PID (user/kernel/total)

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
- Kernel 函数在原始数据中带有 `_[k]` 后缀（如 `osq_lock_[k]`）
- Symbol 类在解析时保留这一信息
- 利用率计算基于准确的符号类型，而非启发式规则

注意：数据已按 1 秒聚合，样本数量仅作为记录数参考，分析基于 core/s 值。
"""

from ..core.format_utils import format_percent
from ..core.output_builder import OutputBuilder


def cmd_show_cpu_usage(engine, args):
    """[Skill] Show CPU utilization for OS or specific PID (user/kernel/total)"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality (no early return, just record)
    builder.assess_quality(samples)
    
    # Determine target description
    pid = getattr(args, 'pid', None)
    comm = getattr(args, 'comm', None)
    comm_regex = getattr(args, 'comm_regex', None)
    
    if pid:
        target_desc = f"PID {pid}"
    elif comm:
        target_desc = f"comm={comm}"
    elif comm_regex:
        target_desc = f"comm_regex={comm_regex}"
    else:
        target_desc = "System-wide"
    
    # Get CPU utilization
    util_stats = engine.get_cpu_utilization(samples)
    
    # Add risk for high kernel usage
    if util_stats['kernel_pct'] > 50:
        builder.add_risk(
            "warning",
            f"内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高' --risk 'warning' --hint '分析内核热点: cluster-symbols'",
            patterns=["HIGH_KERNEL_USAGE"]
        )
    
    # Build and output
    result = builder.build(
        data_type="generic",
        data={
            "target": target_desc,
            "cpu_utilization": {
                "total_pct": format_percent(util_stats['total_pct']),
                "user_pct": format_percent(util_stats['user_pct']),
                "kernel_pct": format_percent(util_stats['kernel_pct'])
            }
        }
    )
    
    builder.print_json(result)
