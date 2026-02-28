#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sample Reliability Assessment Module

评估 perf script 采样数据的统计可靠性。
核心原则：直接利用 CPU 利用率 (core/s) 评估置信度，无需采样频率参数。
"""

import math


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


def assess_sample_reliability(sample_count, duration, cpu_id=None, cpu_samples=None, total_core_per_sec=None):
    """
    Assess the statistical reliability of sampling data.
    
    核心变化：废除 hz 参数，直接使用 CPU 利用率评估置信度。
    CPU 利用率直接从 perf script 的 core/s 字段计算得出。
    
    Args:
        sample_count: Number of samples (样本数)
        duration: Duration in seconds (采样持续时间)
        cpu_id: Optional CPU ID for filtering
        cpu_samples: Optional dict of samples per CPU
        total_core_per_sec: Sum of core/s values from perf (total CPU core-seconds consumed)
    
    Returns: (reliability_level, warning_message, metrics_dict)
        reliability_level: CRITICAL / WARNING / ACCEPTABLE / GOOD / EXCELLENT
    """
    if duration <= 0:
        duration = 1.0  # Avoid division by zero
    
    # Calculate CPU utilization from core/s values
    # core/s represents CPU core-seconds per second = CPU utilization (as ratio)
    # Formula: avg CPU utilization % = (total core-seconds / duration) * 100
    if total_core_per_sec is not None and sample_count > 0:
        avg_cpu_utilization = (total_core_per_sec / duration) * 100
        utilization_source = "core/s"
    else:
        # Fallback: if no core/s data, use sample density as rough estimate
        # This should rarely happen with modern perf script output
        avg_cpu_utilization = 0.0
        utilization_source = "unknown"
    
    # Calculate samples per second for reference
    samples_per_sec = sample_count / duration
    
    metrics = {
        "sample_count": sample_count,
        "samples_per_sec": round(samples_per_sec, 2),
        "cpu_utilization_pct": round(avg_cpu_utilization, 2),
        "utilization_source": utilization_source,
        "duration_sec": round(duration, 2),
    }
    
    if total_core_per_sec is not None:
        metrics["total_core_seconds"] = round(total_core_per_sec, 4)
        metrics["avg_core_per_sec"] = round(total_core_per_sec / duration, 4)
    
    # =========================================================================
    # Reliability Assessment based on CPU Utilization and Sample Count
    # =========================================================================
    
    # === CRITICAL: No core/s data available ===
    if total_core_per_sec is None or utilization_source == "unknown":
        if sample_count < 10:
            return (
                "CRITICAL",
                f"无 core/s 数据且样本数过少 ({sample_count} < 10)，无法评估数据可靠性。"
                f"请确认 perf script 输出包含 core/s 字段。",
                metrics
            )
        return (
            "WARNING",
            f"无 core/s 数据，使用样本数估算。CPU 利用率数据可能不准确。",
            metrics
        )
    
    # === CRITICAL: Very low CPU utilization (< 3%) ===
    # Low CPU activity means samples are sparse and may not be representative
    if avg_cpu_utilization < 3.0:
        if sample_count < 50:
            return (
                "CRITICAL",
                f"CPU利用率极低 ({avg_cpu_utilization:.2f}% < 3%)，样本稀疏且不具有代表性。"
                f"目标在{duration:.1f}秒内几乎无活动，无法得出有效结论。",
                metrics
            )
        else:
            return (
                "WARNING",
                f"CPU利用率较低 ({avg_cpu_utilization:.2f}% < 3%)，尽管样本数尚可 ({sample_count})。"
                f"可能主要采集到的是背景噪音。",
                metrics
            )
    
    # === CRITICAL: Too few total samples ===
    if sample_count < 10:
        return (
            "CRITICAL",
            f"样本数过少 ({sample_count} < 10)，统计结论完全不可信。"
            f"需要至少 100+ 样本才能给出可靠结论。",
            metrics
        )
    
    # === WARNING: Low CPU utilization (3-10%) ===
    if avg_cpu_utilization < 10.0:
        if sample_count < 30:
            return (
                "WARNING",
                f"CPU利用率较低 ({avg_cpu_utilization:.1f}% < 10%) 且样本数较少 ({sample_count})。"
                f"可能遗漏短时活动，观测百分比误差可能 > ±25%。",
                metrics
            )
        else:
            return (
                "ACCEPTABLE",
                f"CPU利用率较低 ({avg_cpu_utilization:.1f}% < 10%)，但样本数尚可 ({sample_count})。"
                f"可用于粗略趋势分析，精确百分比误差约 ±15-20%。",
                metrics
            )
    
    # === WARNING: Low sample count despite good CPU utilization ===
    if sample_count < 30:
        return (
            "WARNING",
            f"样本数较少 ({sample_count} < 30)，尽管CPU利用率尚可 ({avg_cpu_utilization:.1f}%)。"
            f"置信区间较宽，观测百分比可能与真实值偏差 ±20% 以上。",
            metrics
        )
    
    # === ACCEPTABLE: Moderate CPU utilization (10-30%) ===
    if avg_cpu_utilization < 30.0:
        if sample_count < 100:
            return (
                "ACCEPTABLE",
                f"CPU利用率中等 ({avg_cpu_utilization:.1f}%)，样本数 ({sample_count}) 尚可。"
                f"可用于粗略趋势分析，精确百分比误差约 ±10-15%。",
                metrics
            )
        else:
            return (
                "GOOD",
                f"CPU利用率中等 ({avg_cpu_utilization:.1f}%)，样本数充足 ({sample_count})。"
                f"结论可信，百分比误差约 ±5-10%。",
                metrics
            )
    
    # === GOOD: Good CPU utilization (30-60%) ===
    if avg_cpu_utilization < 60.0:
        if sample_count < 100:
            return (
                "ACCEPTABLE",
                f"CPU利用率良好 ({avg_cpu_utilization:.1f}%)，但样本数 ({sample_count}) 偏少。"
                f"结论基本可信，百分比误差约 ±10%。",
                metrics
            )
        else:
            return (
                "GOOD",
                f"CPU利用率良好 ({avg_cpu_utilization:.1f}%)，样本数充足 ({sample_count})。"
                f"结论可信，百分比误差约 ±5-10%。",
                metrics
            )
    
    # === EXCELLENT: High CPU utilization (> 60%) ===
    if avg_cpu_utilization >= 60.0:
        if sample_count < 50:
            return (
                "ACCEPTABLE",
                f"CPU利用率很高 ({avg_cpu_utilization:.1f}%)，但样本数 ({sample_count}) 偏少。"
                f"结论基本可信，百分比误差约 ±10%。",
                metrics
            )
        elif sample_count < 200:
            return (
                "GOOD",
                f"CPU利用率很高 ({avg_cpu_utilization:.1f}%)，样本数 ({sample_count}) 充足。"
                f"结论可信，百分比误差约 ±5%。",
                metrics
            )
        else:
            return (
                "EXCELLENT",
                f"CPU利用率很高 ({avg_cpu_utilization:.1f}%)，样本数优秀 ({sample_count})。"
                f"统计结论高度可信，百分比误差 < ±3%。",
                metrics
            )
    
    # Default fallback (should not reach here)
    return (
        "ACCEPTABLE",
        f"样本数 ({sample_count})，CPU利用率 ({avg_cpu_utilization:.1f}%)。",
        metrics
    )


def format_percentage_with_ci(count, total):
    """Format percentage with 95% confidence interval"""
    if total == 0:
        return "0.00% (N/A)"
    
    p = count / total
    ci_low, ci_high = calculate_wilson_score_interval(count, total)
    
    return f"{p*100:.2f}% (95% CI: {ci_low*100:.1f}%-{ci_high*100:.1f}%)"
