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
from .config_loader import get_analysis_thresholds


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
    # 获取阈值配置
    thresholds = get_analysis_thresholds()
    
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
        if duration < thresholds.reliability_min_duration:
            return (
                "CRITICAL",
                f"No CPU utilization data and duration too short ({duration:.1f}s < {thresholds.reliability_min_duration}s), cannot assess data quality. "
                f"Please verify perf script output format.",
                metrics
            )
        return (
            "WARNING",
            f"No CPU utilization data, analysis will estimate based on record count. CPU utilization may be inaccurate.",
            metrics
        )

    # === CRITICAL: Very short duration (< 2s) ===
    # Data coverage too short to capture complete behavior patterns
    if duration < thresholds.reliability_short_duration:
        if avg_cpu_utilization < thresholds.reliability_low_cpu_threshold:
            return (
                "CRITICAL",
                f"Duration too short ({duration:.1f}s < {thresholds.reliability_short_duration}s) and CPU utilization extremely low ({avg_cpu_utilization:.2f}% < {thresholds.reliability_low_cpu_threshold}%), "
                f"target has minimal activity, cannot draw valid conclusions.",
                metrics
            )
        else:
            return (
                "WARNING",
                f"Duration short ({duration:.1f}s < {thresholds.reliability_short_duration}s), though CPU utilization is acceptable. "
                f"Long-period behavior patterns may be missed.",
                metrics
            )

    # === CRITICAL: Very low CPU utilization (< 3%) ===
    # Low CPU activity means data may not be representative
    # 3% is the absolute threshold for extremely low CPU usage
    if avg_cpu_utilization < 3.0:
        return (
            "CRITICAL",
            f"CPU utilization extremely low ({avg_cpu_utilization:.2f}% < 3%), target has minimal activity in {duration:.1f}s, "
            f"cannot draw valid conclusions.",
            metrics
        )

    # === WARNING: Short duration (2-5s) ===
    if duration < thresholds.reliability_medium_duration:
        if avg_cpu_utilization < thresholds.reliability_medium_cpu_threshold:
            return (
                "WARNING",
                f"Duration short ({duration:.1f}s < {thresholds.reliability_medium_duration}s) and CPU utilization low ({avg_cpu_utilization:.1f}% < {thresholds.reliability_medium_cpu_threshold}%). "
                f"Short activities may be missed, observed percentage error may be > ±25%.",
                metrics
            )
        else:
            return (
                "ACCEPTABLE",
                f"Duration short ({duration:.1f}s < {thresholds.reliability_medium_duration}s), but CPU utilization acceptable ({avg_cpu_utilization:.1f}%). "
                f"Suitable for rough trend analysis, percentage error approximately ±15-20%.",
                metrics
            )

    # === WARNING: Low CPU utilization (3-10%) ===
    if avg_cpu_utilization < thresholds.reliability_medium_cpu_threshold:
        return (
            "WARNING",
            f"CPU utilization low ({avg_cpu_utilization:.1f}% < {thresholds.reliability_medium_cpu_threshold}%). "
            f"Short activities may be missed, observed percentage error may be > ±20%.",
            metrics
        )

    # === ACCEPTABLE: Moderate CPU utilization (10-30%) ===
    if avg_cpu_utilization < thresholds.reliability_high_cpu_threshold:
        return (
            "ACCEPTABLE",
            f"CPU utilization moderate ({avg_cpu_utilization:.1f}%). "
            f"Suitable for rough trend analysis, percentage error approximately ±10-15%.",
            metrics
        )

    # === GOOD: Good CPU utilization (30-60%) ===
    # 60% is the upper limit for GOOD classification
    if avg_cpu_utilization < 60.0:
        return (
            "GOOD",
            f"CPU utilization good ({avg_cpu_utilization:.1f}%). "
            f"Conclusions are reliable, percentage error approximately ±5-10%.",
            metrics
        )

    # === EXCELLENT: High CPU utilization (> 60%) ===
    if avg_cpu_utilization >= 60.0:
        if duration < thresholds.reliability_long_duration:
            return (
                "GOOD",
                f"CPU utilization high ({avg_cpu_utilization:.1f}%), but duration moderate ({duration:.1f}s < {thresholds.reliability_long_duration}s). "
                f"Conclusions are reliable, percentage error approximately ±5%.",
                metrics
            )
        else:
            return (
                "EXCELLENT",
                f"CPU utilization high ({avg_cpu_utilization:.1f}%) with sufficient duration ({duration:.1f}s). "
                f"Statistical conclusions highly reliable, percentage error < ±3%.",
                metrics
            )

    # Default fallback (should not reach here)
    return (
        "ACCEPTABLE",
        f"CPU utilization ({avg_cpu_utilization:.1f}%), duration ({duration:.1f}s).",
        metrics
    )


def format_percentage_with_ci(count, total):
    """Format percentage with 95% confidence interval"""
    if total == 0:
        return "0.00% (N/A)"

    p = count / total
    ci_low, ci_high = calculate_wilson_score_interval(count, total)

    return f"{p*100:.2f}% (95% CI: {ci_low*100:.1f}%-{ci_high*100:.1f}%)"


# Backward compatibility alias
assess_sample_reliability = assess_data_quality
