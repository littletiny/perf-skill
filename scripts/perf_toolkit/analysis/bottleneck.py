#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU Bottleneck Detection - Check for resource throttling and single-core saturation
V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine

检测内容：
1. CPU 限制饱和 (cgroup CPU limit) - cpu_limit > 0 且使用率 > 90%
2. 单核满载 (single core saturation) - 任意核心 total > threshold (默认 80%)
3. 单核 sys 过高 (high sys usage) - 任意核心 sys > threshold + 10% (默认 90%)
4. 多核高负载 (high cores) - >=3 个核心 total > threshold

优先级: CPU_LIMIT > HIGH_SYS_CORES > SINGLE_CORE_SATURATION > HIGH_CORES > HEALTHY
"""

from ..core.command_decorator import command
from ..core.format_utils import format_percent
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, BottleneckData, BottleneckSummary, BottleneckOutput, TimeRange,
    CoreLoadInfo, LimitInfo
)


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


@command("check-cpu-bottleneck")
def cmd_check_bottleneck(builder, engine, args, samples):
    """[Skill] Determine resource throttling and single-core saturation"""

    # 使用 engine 统一接口获取核心级 CPU 利用率
    core_util = engine.get_core_cpu_util(samples)

    # 检测各类瓶颈
    cpu_limit = getattr(args, 'cpu_limit', 0) or 0

    # 获取阈值参数 (默认 80%)
    threshold = getattr(args, 'threshold', 80)
    sys_threshold = threshold + 10  # sys 阈值比 total 高 10%

    # 收集高负载核心
    high_cpu_cores = []  # total > threshold
    high_sys_cores = []  # sys > sys_threshold
    max_cpu_id = None
    max_usage_pct = 0

    for cpu_id, info in core_util.items():
        total_pct = info.total_pct
        sys_pct = info.kernel_pct

        # 记录最高负载核心
        if total_pct > max_usage_pct:
            max_usage_pct = total_pct
            max_cpu_id = cpu_id

        # 检测单核高负载 (>threshold)
        if total_pct > threshold:
            high_cpu_cores.append(cpu_id)

        # 检测单核 sys 高 (>sys_threshold)
        if sys_pct > sys_threshold:
            high_sys_cores.append(cpu_id)

    # 排序
    high_cpu_cores.sort()
    high_sys_cores.sort()

    # 收集所有检测到的 events
    events = []
    risk = None

    # Event 1: CPU 限制饱和 (最高优先级)
    if cpu_limit > 0 and max_usage_pct / 100 > (cpu_limit * 0.9):
        events.append("CPU_LIMIT_SATURATION")
        risk = create_risk_info(
            level="critical",
            message=f"CPU 限制接近饱和: {format_percent(max_usage_pct)}",
            hint=f"检查 cgroup CPU 限制或扩容",
            patterns=["CPU_LIMIT_SATURATION"]
        )

    # Event 2: 单核 sys 过高
    if high_sys_cores:
        events.append("HIGH_SYS_CORES")
        if risk is None:
            core_list_str = ",".join(map(str, high_sys_cores))
            risk = create_risk_info(
                level="critical",
                message=f"检测到 {len(high_sys_cores)} 个核心 sys 利用率 >{sys_threshold}%: {core_list_str}",
                hint="[必须] 分析内核热点: cluster-symbols",
                patterns=["HIGH_SYS_CORES"]
            )

    # Event 3: 单核满载 (至少1个核心高负载)
    if high_cpu_cores:
        events.append("SINGLE_CORE_SATURATION")
        if risk is None:
            core_list_str = ",".join(map(str, high_cpu_cores))
            pid = getattr(args, 'pid', None)
            if pid:
                hint = f"analyze-core-distribution --pid {pid}"
            else:
                hint = "先定位高 CPU 进程: get-process-top --top-n 5，然后分析具体进程"
            risk = create_risk_info(
                level="warning",
                message=f"单核利用率>{threshold}% (CPU {core_list_str})，可能存在串行化瓶颈",
                hint=hint,
                patterns=["SINGLE_CORE_SATURATION"]
            )

    # Event 4: 多核高负载 (>=3 个核心高负载，区别于单核满载)
    if len(high_cpu_cores) >= 3:
        events.append("HIGH_CORES")
        # 不覆盖 risk，因为 HIGH_CORES 是信息性的，优先级低于 SINGLE_CORE_SATURATION
        if risk is None:
            core_list_str = ",".join(map(str, high_cpu_cores))
            risk = create_risk_info(
                level="info",
                message=f"多核高负载 ({len(high_cpu_cores)} 个核心 >{threshold}%): {core_list_str}",
                hint="检查整体负载情况",
                patterns=["HIGH_CORES"]
            )

    # 确定主要 verdict (按优先级)
    if "CPU_LIMIT_SATURATION" in events:
        verdict = "CPU_LIMIT_SATURATION"
    elif "HIGH_SYS_CORES" in events:
        verdict = "HIGH_SYS_CORES"
    elif "SINGLE_CORE_SATURATION" in events:
        verdict = "SINGLE_CORE_SATURATION"
    elif "HIGH_CORES" in events:
        verdict = "HIGH_CORES"
    else:
        verdict = "HEALTHY"
        events.append("HEALTHY")

    # 无风险时创建空 risk
    if risk is None:
        risk = create_risk_info(level="none")

    # Create data model
    data = BottleneckData(
        verdict=verdict,
        events=events,
        high_cpu_cores=high_cpu_cores,
        high_sys_cores=high_sys_cores,
        threshold=threshold,
        max_core_load=CoreLoadInfo(
            cpu_id=max_cpu_id if max_cpu_id is not None else 0,
            load=format_percent(max_usage_pct)
        ),
        limit_info=LimitInfo(
            cpu_limit_cores=cpu_limit,
            cpu_limit_detected=cpu_limit > 0
        )
    )

    summary = BottleneckSummary()
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])

    output = BottleneckOutput(
        _risk=risk,
        data=data,
        summary=summary,
        time_range=time_range
    )

    return output
