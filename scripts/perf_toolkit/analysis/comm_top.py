#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

Specialized for identifying "many small processes consuming resources collectively" scenarios:
- High aggregate CPU usage across many processes with same comm
- Low individual process CPU usage
- Useful for detecting worker pool issues, connection storms, etc.

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, CommGroupItem, CommGroupSummary, CommTopOutput, TimeRange
)


@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """[Skill] Get top N comm groups by aggregated CPU utilization"""

    # 使用 engine 统一接口获取 comm 级 CPU 利用率
    comm_util = engine.get_comm_cpu_util(samples)

    # Calculate aggregated statistics
    total_unique_pids = sum(info['pid_count'] for info in comm_util.values())
    high_kernel_groups = []
    results = []

    for comm, info in comm_util.items():
        pid_count = info['pid_count']
        aggregate_cpu_util = info['total_pct']
        avg_cpu_per_process = aggregate_cpu_util / pid_count if pid_count > 0 else 0

        # 计算 kernel 占比
        if info['total_pct'] > 0:
            kernel_ratio = (info['kernel_pct'] / info['total_pct']) * 100
        else:
            kernel_ratio = 0

        # Track high kernel groups for risk
        if kernel_ratio > 50 and aggregate_cpu_util > 5:
            high_kernel_groups.append(comm)

        # Build event description (skip normal events)
        if aggregate_cpu_util > 10 and avg_cpu_per_process < 1 and pid_count >= 5:
            event = f"MANY_SMALL_PROCESSES({pid_count}p/{avg_cpu_per_process:.2f}%)"
        elif kernel_ratio > 50:
            event = f"HIGH_KERNEL_RATIO({kernel_ratio:.1f}%)"
        else:
            event = "normal"
            continue  # Skip normal events

        results.append(CommGroupItem.from_stats(
            comm=comm,
            pid_count=pid_count,
            aggregate_cpu=aggregate_cpu_util,
            kernel_ratio=kernel_ratio,
            event_desc=event
        ))

    # Sort by CPU utilization descending
    results.sort(key=lambda x: float(x.cpu.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    top_results = results[:top_n]

    # Build RiskInfo + Trace 自动记录
    if len(high_kernel_groups) > 0:
        risk_level = "warning" if len(high_kernel_groups) <= 2 else "critical"
        cluster_commands = [f"cluster-symbols --comm {comm}" for comm in high_kernel_groups]

        # Trace v2.0 - 自动记录每个高内核态风险
        for comm in high_kernel_groups:
            # 找到对应的 kernel_ratio
            for item in top_results:
                if item.comm == comm:
                    kernel_val = item.kernel.rstrip('%')
                    builder.record_risk(
                        level=risk_level,
                        desc=f"{comm} 高内核态 {kernel_val}%",
                        hint=f"cluster-symbols --comm {comm}"
                    )
                    break

        risk = create_risk_info(
            level=risk_level,
            message=f"发现 {len(high_kernel_groups)} 个高内核态进程组(kernel%>50%)未分析",
            hint=f"必须对每个进程运行: {'; '.join(cluster_commands)}",
            patterns=["MULTI_HIGH_KERNEL"],
            pending_targets=high_kernel_groups
        )
    else:
        risk = create_risk_info(level="none")

    # Build time range
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts'),
        samples[-1].get('ts') if len(samples) > 0 else None
    )

    # Build summary with truncation info
    summary = CommGroupSummary(
        total_comm_groups=len(results),
        high_kernel_groups=len(high_kernel_groups)
    )

    # Build output
    output = CommTopOutput(
        _risk=risk,
        comm_groups=top_results,
        summary=summary,
        time_range=time_range
    )

    return output
