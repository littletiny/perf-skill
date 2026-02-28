#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU Bottleneck Detection - Check for resource throttling and single-core saturation

检测资源限制和单核饱和。

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_percent
from ..core.risk_mixin import RiskAwareOutput


def parse_cpu_quota(value):
    """Parse CPU quota string like '0.1c', '2c', '0.5' to float cores"""
    if value is None:
        return 0.0
    value = str(value).strip()
    if value.endswith('c'):
        value = value[:-1]
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid CPU quota format: '{value}'. Expected format like '0.1c', '2c', or '0.5'")


def cmd_check_bottleneck(engine, args):
    """[Skill] Determine resource throttling and single-core saturation"""
    # Get filtered samples based on time range, PID and comm
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
        result = output.add_risk(
            "warning",
            "指定时间范围内未找到样本",
            "检查时间范围或移除过滤条件"
        ).build({
            "error": "No samples found in the specified time range",
            "time_range": format_time_range(
                getattr(args, 'start_time', None),
                getattr(args, 'end_time', None)
            ),
            "available_range": engine.get_time_range()
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    # Calculate duration from filtered samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    
    # Assess data quality
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Calculate per-CPU utilization using core/s values
    cpu_core_per_sec = defaultdict(float)
    for s in samples:
        if s.get('core_per_sec'):
            cpu_core_per_sec[s['cpu']] += s['core_per_sec']
    
    # Find the busiest CPU
    max_cpu_id = max(cpu_core_per_sec, key=cpu_core_per_sec.get) if cpu_core_per_sec else 0
    max_cpu_core_sec = cpu_core_per_sec.get(max_cpu_id, 0)
    
    # Calculate max core usage: average core/s on that CPU per second
    if duration > 0:
        max_core_usage = max_cpu_core_sec / duration
    else:
        max_core_usage = 0
    
    # Parse CPU limit
    cpu_limit = getattr(args, 'cpu_limit', 0) or 0
    
    # Determine verdict based on CPU utilization percentage
    verdict = "HEALTHY"
    if cpu_limit > 0 and max_core_usage > (cpu_limit * 0.9):
        verdict = "CPU_LIMIT_SATURATION"
        output.add_risk(
            "critical",
            f"CPU 限制接近饱和: {format_percent(max_core_usage * 100)}",
            "检查 cgroup CPU 限制或扩容",
            patterns=["CPU_LIMIT_SATURATION"]
        )
    elif max_core_usage > 0.9:
        verdict = "SINGLE_CORE_SATURATION"
        output.add_risk(
            "warning",
            "单核满载，可能存在串行化瓶颈",
            f"执行: analyze-core-distribution --pid {getattr(args, 'pid', '<pid>')}",
            patterns=["SINGLE_CORE_SATURATION"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！所有结论都不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "verdict": verdict,
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "record_count": record_count,
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "max_core_load": {
            "cpu_id": max_cpu_id,
            "load": format_percent(max_core_usage * 100)
        },
        "limit_info": {
            "cpu_limit_cores": cpu_limit,
            "cpu_limit_detected": cpu_limit > 0
        }
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
