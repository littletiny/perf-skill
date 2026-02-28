#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

Specialized for identifying "many small processes consuming resources collectively" scenarios:
- High aggregate CPU usage across many processes with same comm
- Low individual process CPU usage
- Useful for detecting worker pool issues, connection storms, etc.

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_percent, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


def cmd_get_comm_top(engine, args):
    """[Skill] Get top N comm groups by aggregated CPU utilization"""
    # Get filtered samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )

    output = RiskAwareOutput()

    if not samples:
        result = output.add_risk(
            "warning",
            "未找到样本数据",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '未找到样本数据' --risk 'warning' --hint '检查过滤条件或数据文件'"
        ).build({
            "error": "No samples found",
            "filters": {
                "cpu_id": getattr(args, 'cpu_id', None),
                "pid": getattr(args, 'pid', None),
                "comm": getattr(args, 'comm', None),
                "comm_regex": getattr(args, 'comm_regex', None),
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        })
        print(json.dumps(result, indent=2))
        return

    # Calculate duration and data quality
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )

    # Aggregate by comm
    comm_stats = defaultdict(lambda: {
        'pids': defaultdict(lambda: {'core_sec': 0.0, 'kernel_core_sec': 0.0, 'user_core_sec': 0.0}),
        'total_core_sec': 0.0,
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0
    })

    for s in samples:
        comm = s['comm']
        pid = s['pid']
        core_val = s.get('core_per_sec') or 0

        comm_stats[comm]['pids'][pid]['core_sec'] += core_val
        comm_stats[comm]['total_core_sec'] += core_val

        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            comm_stats[comm]['kernel_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['kernel_core_sec'] += core_val
        else:
            comm_stats[comm]['user_core_sec'] += core_val
            comm_stats[comm]['pids'][pid]['user_core_sec'] += core_val

    # Calculate aggregated statistics
    total_unique_pids = sum(len(stats['pids']) for stats in comm_stats.values())
    high_kernel_groups = []
    results = []

    for comm, stats in comm_stats.items():
        pids_data = stats['pids']
        pid_count = len(pids_data)
        total_core_sec = stats['total_core_sec']

        if duration > 0:
            aggregate_cpu_util = (total_core_sec / duration) * 100
        else:
            aggregate_cpu_util = 0

        avg_cpu_per_process = aggregate_cpu_util / pid_count if pid_count > 0 else 0
        avg_core_sec_per_process = total_core_sec / pid_count if pid_count > 0 else 0
        process_count_pct = (pid_count / total_unique_pids * 100) if total_unique_pids > 0 else 0

        if total_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / total_core_sec) * 100
            user_ratio = (stats['user_core_sec'] / total_core_sec) * 100
        else:
            kernel_ratio = user_ratio = 0

        # Track high kernel groups for risk (kernel% > 50%)
        if kernel_ratio > 50 and aggregate_cpu_util > 5:
            high_kernel_groups.append(comm)

        density_index = aggregate_cpu_util / pid_count if pid_count > 0 else 0

        pid_core_sec = [p['core_sec'] for p in pids_data.values()]
        min_core_sec_per_pid = min(pid_core_sec) if pid_core_sec else 0
        max_core_sec_per_pid = max(pid_core_sec) if pid_core_sec else 0

        results.append({
            'comm': comm,
            'pid_count': pid_count,
            'cpu_pct': format_percent(aggregate_cpu_util),
            'kernel_pct': format_percent(kernel_ratio),
            'total_core_sec': format_core_sec(total_core_sec),
            'avg_cpu_per_process_pct': format_percent(avg_cpu_per_process),
            'density_index': round(density_index, 4)
        })

    # Sort by CPU utilization descending
    if getattr(args, 'sort_by_density', False):
        results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)
    else:
        results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)

    top_n = getattr(args, 'top_n', 10)
    top_results = results[:top_n]

    # Add risk for high kernel groups (kernel% > 50%)
    if len(high_kernel_groups) > 0:
        risk_level = "warning" if len(high_kernel_groups) <= 2 else "critical"
        # 构建必须对每个进程执行 cluster-symbols 的 hint
        cluster_commands = [f"cluster-symbols --comm {comm}" for comm in high_kernel_groups]
        output.add_risk(
            risk_level,
            f"发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%)未分析",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%): {', '.join(high_kernel_groups)}' --risk '{risk_level}' --hint '必须对每个进程运行: {'; '.join(cluster_commands)}'",
            patterns=["MULTI_HIGH_KERNEL"],
            targets=high_kernel_groups
        )

    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！comm 组分析结果不可信",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！comm 组分析结果不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
            patterns=["CRITICAL_DATA_QUALITY"]
        )

    result = output.build({
        "summary": {
            "total_comm_groups": len(results),
            "high_kernel_groups": len(high_kernel_groups)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "comm_groups": top_results
    })

    print(json.dumps(result, indent=2, ensure_ascii=False))
