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

import json
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_percent
from ..core.risk_mixin import RiskAwareOutput


def cmd_show_cpu_usage(engine, args):
    """[Skill] Show CPU utilization for OS or specific PID (user/kernel/total)"""
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
        result = output.add_risk(
            "warning",
            "未找到样本数据",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '未找到样本数据' --risk 'warning' --hint '检查过滤条件'"
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
    
    util_stats = engine.get_cpu_utilization(samples)
    total_core_per_sec = util_stats['total_core_seconds']
    
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Add risk for high kernel usage
    if util_stats['kernel_pct'] > 50:
        output.add_risk(
            "warning",
            f"内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高' --risk 'warning' --hint '分析内核热点: cluster-symbols'",
            patterns=["HIGH_KERNEL_USAGE"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！CPU 利用率数据完全不可信",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！CPU 利用率数据完全不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "target": target_desc,
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "cpu_utilization": {
            "total_pct": format_percent(util_stats['total_pct']),
            "user_pct": format_percent(util_stats['user_pct']),
            "kernel_pct": format_percent(util_stats['kernel_pct'])
        }
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
