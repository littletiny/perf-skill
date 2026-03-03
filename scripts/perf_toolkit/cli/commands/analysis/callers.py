#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find-callers 命令实现

从 analysis/trace.py 迁移而来
"""

from collections import defaultdict
from perf_toolkit.cli.decorators import command
from perf_toolkit.core.output_models import (
    RiskInfo, AttributionItem, AttributionSummary, AttributionsOutput, TimeRange
)


@command("find-callers")
def cmd_trace_attribution(builder, engine, args, samples):
    """[Skill] Bottom-up attribution for specific bottleneck functions"""

    # 使用 engine 统一接口获取总量
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)

    # Trace attribution
    target = args.target
    attribution = defaultdict(float)
    target_weight = 0.0

    for s in samples:
        if not s.stack:
            continue

        weight = engine.get_sample_weight(s)
        normalized_names = s.stack.get_normalized_names()

        if target in normalized_names:
            target_weight += weight
            idx = normalized_names.index(target)
            caller_stack = normalized_names[idx+1:idx+6]
            if caller_stack:
                attribution[tuple(caller_stack)] += weight

    # Build results - show ratio relative to total samples (not just target)
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    for stack, weight_val in attribution.items():
        # Calculate ratio relative to total samples
        ratio_total = (weight_val / total_weight) * 100 if total_weight > 0 else 0
        if ratio_total < min_ratio:
            continue
        results.append(AttributionItem(
            caller_stack=list(stack),
            ratio_of_target_pct=f"{ratio_total:.2f}%",
            cpu_util="0.00%"
        ))

    results.sort(key=lambda x: float(x.ratio_of_target_pct.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    results = results[:top_n]

    # Determine risk level
    risk = None
    if target_weight < 0.01:
        risk = RiskInfo(
            level="warning",
            message=f"目标函数 '{target}' 几乎无 CPU 活动",
            hint=f"[必须] 添加到 Trace: shecr trace add --desc '目标函数 {target} 几乎无 CPU 活动' --hint '检查目标函数名称是否正确'",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    else:
        risk = RiskInfo(level="none")

    # Create summary with truncation info
    target_cpu_util = (target_weight / duration * 100) if duration > 0 else 0
    summary = AttributionSummary(
        target=target,
        target_cpu_util=f"{target_cpu_util:.2f}%",
        total_attributions=len(attribution),
        shown_attributions=len(results)
    )

    # Build and output
    output = AttributionsOutput(
        _risk=risk,
        attributions=results,
        summary=summary
    )

    return output
