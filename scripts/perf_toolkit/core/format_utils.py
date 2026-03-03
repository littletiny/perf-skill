#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Format Utilities - Time formatting and helper functions for standardized output

遵循 output-format-spec.md 规范：
- 时间字符串化: ISO 8601 格式
- 百分比使用字符串带 % 符号
- 权重值保留数字，4位小数
"""

from datetime import datetime
from typing import Optional, List

from .output_models import TimeRange


def format_timestamp(ts: float) -> str:
    """Convert timestamp to ISO 8601 string (local time)"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat()


def format_time_range(start_ts: float, end_ts: float) -> TimeRange:
    """Format time range with readable string and duration"""
    if start_ts is None or end_ts is None:
        return TimeRange()
    return TimeRange(
        start_time=format_timestamp(start_ts),
        end_time=format_timestamp(end_ts),
        duration=round(end_ts - start_ts, 2)
    )


def format_duration(seconds: float) -> str:
    """Format duration to human readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def format_percent(value: float) -> str:
    """Format value as percentage string with % symbol"""
    return f"{value:.2f}%"


def format_weight(value: float) -> float:
    """Format weight value to 4 decimal places"""
    return round(value, 4)


def safe_time_range(samples: list) -> TimeRange:
    """
    Safely extract and format time range from samples list.

    Args:
        samples: List of sample dicts with 'ts' field

    Returns:
        TimeRange dataclass
    """
    if not samples:
        return TimeRange()

    start_ts = samples[0].get('ts')
    end_ts = samples[-1].get('ts')

    return format_time_range(start_ts, end_ts)
