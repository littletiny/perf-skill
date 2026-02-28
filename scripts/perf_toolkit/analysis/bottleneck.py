#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU Bottleneck Detection - Check for resource throttling and single-core saturation
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability


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
    
    if not samples:
        print(json.dumps({
            "error": "No samples found in the specified time range",
            "time_range": {
                "start": getattr(args, 'start_time', None),
                "end": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2, ensure_ascii=False))
        return
    
    # Calculate duration from filtered samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    actual_total = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, core_count = engine.get_total_core_per_sec(samples)
    
    # Assess sample reliability (without hz parameter)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        actual_total, duration, total_core_per_sec=total_core_per_sec
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
    # Total core-seconds divided by duration gives average CPU utilization
    if duration > 0:
        max_core_usage = max_cpu_core_sec / duration
    else:
        max_core_usage = 0
    
    # Parse CPU limit
    cpu_limit = getattr(args, 'cpu_limit', 0) or 0
    
    # Determine verdict based on CPU utilization percentage
    # max_core_usage is already a ratio (e.g., 0.63 = 63%)
    verdict = "HEALTHY"
    if cpu_limit > 0 and max_core_usage > (cpu_limit * 0.9):
        verdict = "CPU_LIMIT_SATURATION (near CPU limit)"
    elif max_core_usage > 0.9:
        verdict = "SINGLE_CORE_SATURATION (one CPU core at max capacity)"
    
    result = {
        "verdict": verdict,
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "total_samples": actual_total,
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "max_core_load": {
            "cpu_id": max_cpu_id,
            "load": f"{max_core_usage*100:.2f}%"
        },
        "limit_info": {
            "cpu_limit_cores": cpu_limit,
            "cpu_limit_detected": cpu_limit > 0
        }
    }
    
    # Add explicit warning for CRITICAL reliability
    if reliability_level == "CRITICAL":
        result["_WARNING"] = "数据可信度极低！所有结论（包括 CPU 利用率）都不可信。请使用更长的采样时间重新采集数据。"
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
