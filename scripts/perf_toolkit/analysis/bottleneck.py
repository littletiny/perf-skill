#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU Bottleneck Detection - Check for resource throttling and single-core saturation
V2 版本：使用统一数据模型

检测资源限制和单核饱和。

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

from collections import defaultdict
from ..core.format_utils import format_percent
from ..core.output_builder_v2 import OutputBuilderV2, create_risk_info
from ..core.output_models import RiskInfo, BottleneckData, BottleneckSummary, BottleneckOutput, TimeRange


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
    
    builder = OutputBuilderV2(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Calculate per-CPU utilization using core/s values
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    cpu_core_per_sec = defaultdict(float)
    
    for s in samples:
        if s.get('core_per_sec'):
            cpu_core_per_sec[s['cpu']] += s['core_per_sec']
    
    # Find the busiest CPU
    max_cpu_id = max(cpu_core_per_sec, key=cpu_core_per_sec.get) if cpu_core_per_sec else 0
    max_cpu_core_sec = cpu_core_per_sec.get(max_cpu_id, 0)
    
    # Calculate max core usage: average core/s on that CPU per second
    max_core_usage = max_cpu_core_sec / duration if duration > 0 else 0
    
    # Parse CPU limit
    cpu_limit = getattr(args, 'cpu_limit', 0) or 0
    
    # Determine verdict based on CPU utilization percentage
    verdict = "HEALTHY"
    risk = None
    
    if cpu_limit > 0 and max_core_usage > (cpu_limit * 0.9):
        verdict = "CPU_LIMIT_SATURATION"
        risk = create_risk_info(
            level="critical",
            message=f"CPU 限制接近饱和: {format_percent(max_core_usage * 100)}",
            hint=f"检查 cgroup CPU 限制或扩容",
            doc_hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc 'CPU 限制接近饱和: {format_percent(max_core_usage * 100)}' --risk 'critical' --hint '检查 cgroup CPU 限制或扩容'",
            patterns=["CPU_LIMIT_SATURATION"]
        )
    elif max_core_usage > 0.9:
        verdict = "SINGLE_CORE_SATURATION"
        # Build hint: use pid if available, otherwise suggest getting process top
        pid = getattr(args, 'pid', None)
        if pid:
            hint = f"analyze-core-distribution --pid {pid}"
        else:
            hint = "先定位高 CPU 进程: get-process-top --top-n 5，然后分析具体进程"
        risk = create_risk_info(
            level="warning",
            message="单核满载，可能存在串行化瓶颈",
            hint=hint,
            doc_hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '单核满载，可能存在串行化瓶颈' --risk 'warning' --hint '{hint}'",
            patterns=["SINGLE_CORE_SATURATION"]
        )
    
    # Create data model
    data = BottleneckData(
        verdict=verdict,
        max_core_load={
            "cpu_id": max_cpu_id,
            "load": format_percent(max_core_usage * 100)
        },
        limit_info={
            "cpu_limit_cores": cpu_limit,
            "cpu_limit_detected": cpu_limit > 0
        }
    )
    
    summary = BottleneckSummary()
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    output = BottleneckOutput(
        _risk=risk,
        data=data,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
