#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
CPU Usage Analysis - Show CPU utilization for OS or specific PID (user/kernel/total)

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
- Kernel 函数在原始数据中带有 `_[k]` 后缀（如 `osq_lock_[k]`）
- Symbol 类在解析时保留这一信息
- 利用率计算基于准确的符号类型，而非启发式规则

新增功能：检测单核 sys 利用率高的核心（>70%）

注意：数据已按 1 秒聚合，样本数量仅作为记录数参考，分析基于 core/s 值。
"""

from ..core.format_utils import format_percent
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, CPUUsageData, CPUUsageSummary, CPUUsageOutput,
    CoreItem, TimeRange
)


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
    
    # 使用 engine 统一接口获取整体 CPU 利用率
    util_stats = engine.get_cpu_utilization(samples)
    
    # 使用 engine 统一接口获取核心级利用率，检测高 sys 核心
    core_util = engine.get_core_cpu_util(samples)
    high_sys_cores = []
    
    for cpu_id, info in sorted(core_util.items(), key=lambda x: x[1]['kernel_pct'], reverse=True):
        if info['kernel_pct'] > 70:
            high_sys_cores.append(CoreItem(
                cpu_id=cpu_id,
                total_cpu_util=f"{info['total_pct']:.2f}%",
                kernel_cpu_util=f"{info['kernel_pct']:.2f}%"
            ))
    
    # Build risk info
    if high_sys_cores:
        # High sys cores detected - critical risk
        core_list = ", ".join([f"CPU{c.cpu_id}({c.kernel_cpu_util})" for c in high_sys_cores[:3]])
        risk = create_risk_info(
            level="critical",
            message=f"检测到 {len(high_sys_cores)} 个核心 sys 利用率 >70%: {core_list}",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '检测到 {len(high_sys_cores)} 个核心 sys 利用率 >70%' --risk 'critical' --hint '分析内核热点: cluster-symbols'",
            patterns=["HIGH_SYS_CORES"]
        )
    elif util_stats['kernel_pct'] > 50:
        risk = create_risk_info(
            level="warning",
            message=f"内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '内核态 CPU 使用率 {util_stats['kernel_pct']:.2f}% 异常高' --risk 'warning' --hint '分析内核热点: cluster-symbols'",
            patterns=["HIGH_KERNEL_USAGE"]
        )
    else:
        risk = create_risk_info(level="none")
    
    # Build CPU usage data
    data = CPUUsageData(
        target=target_desc,
        cpu_utilization={
            "total_pct": format_percent(util_stats['total_pct']),
            "user_pct": format_percent(util_stats['user_pct']),
            "kernel_pct": format_percent(util_stats['kernel_pct'])
        }
    )
    
    # Build summary with high sys cores info
    summary = CPUUsageSummary()
    
    # Build output
    output = CPUUsageOutput(_risk=risk, data=data, summary=summary)
    
    # Print output
    builder.print_output(output)
    
    # Print high sys cores if any
    if high_sys_cores:
        print("\n# HIGH_SYS_CORES: cpu_id,(usr+sys)/sys")
        for i, core in enumerate(high_sys_cores, 1):
            print(f"#{i} CPU{core.cpu_id} {core.total_cpu_util}/{core.kernel_cpu_util}")
