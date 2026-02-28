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


def cmd_show_cpu_usage(engine, args):
    """[Skill] Show CPU utilization for OS or specific PID (user/kernel/total)"""
    # Get filtered samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        print(json.dumps({
            "error": "No samples found",
            "filters": {
                "pid": getattr(args, 'pid', None),
                "comm": getattr(args, 'comm', None),
                "comm_regex": getattr(args, 'comm_regex', None),
                "cpu_id": getattr(args, 'cpu_id', None),
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    # Calculate duration from samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
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
    
    # Get accurate CPU utilization breakdown using the new method
    # This uses Symbol.is_kernel for accurate user/kernel classification
    util_stats = engine.get_cpu_utilization(samples)
    total_core_per_sec = util_stats['total_core_seconds']
    
    # Assess data quality (no sample_count parameter needed)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    result = {
        "target": target_desc,
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            "pid": pid,
            "comm": comm,
            "comm_regex": comm_regex,
            "cpu_id": getattr(args, 'cpu_id', None),
            "start_time": getattr(args, 'start_time', None),
            "end_time": getattr(args, 'end_time', None)
        },
        "data_coverage": {
            "record_count": record_count,
            "user_records": util_stats['user_records'],
            "kernel_records": util_stats['kernel_records']
        },
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "cpu_utilization": {
            "total_pct": util_stats['total_pct'],
            "user_pct": util_stats['user_pct'],
            "kernel_pct": util_stats['kernel_pct'],
            "breakdown": {
                "user_core_seconds": util_stats['user_core_seconds'],
                "kernel_core_seconds": util_stats['kernel_core_seconds'],
                "total_core_seconds": util_stats['total_core_seconds'],
                "user_records": util_stats['user_records'],
                "kernel_records": util_stats['kernel_records'],
                "total_records": record_count
            }
        }
    }
    
    if quality_level == "CRITICAL":
        result["_WARNING"] = "数据质量不足！CPU 利用率数据完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        result["_NOTICE"] = "数据质量中等，利用率数据仅供参考，关注相对比例而非精确值。"
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
