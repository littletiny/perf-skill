#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Quality Assessment Module

评估 perf script 数据的覆盖质量和可靠性。
核心原则：直接使用 CPU 利用率评估数据质量。
"""

import math
from typing import Tuple, Optional
from .output_models import DataQualityMetrics


def calculate_wilson_score_interval(successes, total, confidence=0.95):
    """
    Calculate Wilson score interval for binomial proportion.
    More accurate than normal approximation for small samples.

    Returns: (lower_bound, upper_bound) as proportions
    """
    if total == 0:
        return (0.0, 0.0)

    # Wilson score interval calculation
    z = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
    p = successes / total
    n = total

    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2*n)) / denominator
    half_width = z * ((p*(1-p)/n + z**2/(4*n**2)) ** 0.5) / denominator

    return (max(0, centre - half_width), min(1, centre + half_width))


def assess_data_quality(duration, cpu_id=None, total_weight=None, record_count=None) -> Tuple[str, str, DataQualityMetrics]:
    """
    Assess the quality and reliability of aggregated perf data.

    直接基于 CPU 利用率和数据覆盖时长评估数据质量。

    Args:
        duration: Duration in seconds
        cpu_id: Optional CPU ID for filtering
        total_weight: Sum of sample weights
        record_count: Number of aggregated records (for reference only)

    Returns: (quality_level, warning_message, DataQualityMetrics)
        quality_level: CRITICAL / WARNING / ACCEPTABLE / GOOD / EXCELLENT
    """
    if duration <= 0:
        duration = 1.0  # Avoid division by zero

    # Calculate average CPU utilization from sample weights
    if total_weight is not None:
        avg_cpu_utilization = (total_weight / duration) * 100
        utilization_source = "shecr"
    else:
        avg_cpu_utilization = 0.0
        utilization_source = "unknown"

    # 使用 DataQualityMetrics dataclass
    metrics = DataQualityMetrics(
        record_count=record_count or 0,
        duration_sec=round(duration, 2),
        cpu_utilization_pct=round(avg_cpu_utilization, 2),
        utilization_source=utilization_source,
    )

    if total_weight is not None:
        metrics.total_weight = round(total_weight, 4)
        metrics.avg_weight = round(total_weight / duration, 4)

    # =========================================================================
    # Data Quality Assessment based on CPU Utilization and Duration
    # =========================================================================

    # === CRITICAL: No CPU utilization data available ===
    if total_weight is None or utilization_source == "unknown":
        if duration < 1.0:
            return (
                "CRITICAL",
                f"无 CPU 利用率数据且数据覆盖时长过短 ({duration:.1f}s < 1s)，无法评估数据质量。"
                f"请确认 perf script 输出格式正确。",
                metrics
            )
        return (
            "WARNING",
            f"无 CPU 利用率数据，分析将基于记录数估算。CPU 利用率数据可能不准确。",
            metrics
        )

    # === CRITICAL: Very short duration (< 2s) ===
    # 数据覆盖时长太短，可能无法捕获完整行为模式
    if duration < 2.0:
        if avg_cpu_utilization < 5.0:
            return (
                "CRITICAL",
                f"数据覆盖时长过短 ({duration:.1f}s < 2s) 且 CPU 利用率极低 ({avg_cpu_utilization:.2f}% < 5%)，"
                f"目标几乎无活动，无法得出有效结论。",
                metrics
            )
        else:
            return (
                "WARNING",
                f"数据覆盖时长较短 ({duration:.1f}s < 2s)，尽管 CPU 利用率尚可。"
                f"可能遗漏长周期行为模式。",
                metrics
            )

    # === CRITICAL: Very low CPU utilization (< 3%) ===
    # Low CPU activity means data may not be representative
    if avg_cpu_utilization < 3.0:
        return (
            "CRITICAL",
            f"CPU 利用率极低 ({avg_cpu_utilization:.2f}% < 3%)，目标在 {duration:.1f}s 内几乎无活动，"
            f"无法得出有效结论。",
            metrics
        )

    # === WARNING: Short duration (2-5s) ===
    if duration < 5.0:
        if avg_cpu_utilization < 10.0:
            return (
                "WARNING",
                f"数据覆盖时长较短 ({duration:.1f}s < 5s) 且 CPU 利用率较低 ({avg_cpu_utilization:.1f}% < 10%)。"
                f"可能遗漏短时活动，观测百分比误差可能 > ±25%。",
                metrics
            )
        else:
            return (
                "ACCEPTABLE",
                f"数据覆盖时长较短 ({duration:.1f}s < 5s)，但 CPU 利用率尚可 ({avg_cpu_utilization:.1f}%)。"
                f"可用于粗略趋势分析，精确百分比误差约 ±15-20%。",
                metrics
            )

    # === WARNING: Low CPU utilization (3-10%) ===
    if avg_cpu_utilization < 10.0:
        return (
            "WARNING",
            f"CPU 利用率较低 ({avg_cpu_utilization:.1f}% < 10%)。"
            f"可能遗漏短时活动，观测百分比误差可能 > ±20%。",
            metrics
        )

    # === ACCEPTABLE: Moderate CPU utilization (10-30%) ===
    if avg_cpu_utilization < 30.0:
        return (
            "ACCEPTABLE",
            f"CPU 利用率中等 ({avg_cpu_utilization:.1f}%)。"
            f"可用于粗略趋势分析，精确百分比误差约 ±10-15%。",
            metrics
        )

    # === GOOD: Good CPU utilization (30-60%) ===
    if avg_cpu_utilization < 60.0:
        return (
            "GOOD",
            f"CPU 利用率良好 ({avg_cpu_utilization:.1f}%)。"
            f"结论可信，百分比误差约 ±5-10%。",
            metrics
        )

    # === EXCELLENT: High CPU utilization (> 60%) ===
    if avg_cpu_utilization >= 60.0:
        if duration < 10.0:
            return (
                "GOOD",
                f"CPU 利用率很高 ({avg_cpu_utilization:.1f}%)，但数据覆盖时长 ({duration:.1f}s < 10s) 中等。"
                f"结论可信，百分比误差约 ±5%。",
                metrics
            )
        else:
            return (
                "EXCELLENT",
                f"CPU 利用率很高 ({avg_cpu_utilization:.1f}%)，数据覆盖时长充足 ({duration:.1f}s)。"
                f"统计结论高度可信，百分比误差 < ±3%。",
                metrics
            )

    # Default fallback (should not reach here)
    return (
        "ACCEPTABLE",
        f"CPU 利用率 ({avg_cpu_utilization:.1f}%)，数据覆盖时长 ({duration:.1f}s)。",
        metrics
    )


def format_percentage_with_ci(count, total):
    """Format percentage with 95% confidence interval"""
    if total == 0:
        return "0.00% (N/A)"

    p = count / total
    ci_low, ci_high = calculate_wilson_score_interval(count, total)

    return f"{p*100:.2f}% (95% CI: {ci_low*100:.1f}%-{ci_high*100:.1f}%)"


# 向后兼容的别名
assess_sample_reliability = assess_data_quality
