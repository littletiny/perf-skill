#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Top - Get top N processes by CPU utilization

使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_percent
from ..core.risk_mixin import RiskAwareOutput


def cmd_get_process_top(engine, args):
    """[Skill] Get top N processes by CPU utilization"""
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None)
    )
    
    output = RiskAwareOutput()
    
    if not samples:
        result = output.add_risk(
            "warning",
            "未找到样本数据",
            "检查过滤条件"
        ).build({
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(args, 'start_time', None),
                getattr(args, 'end_time', None)
            ),
            "available_range": engine.get_time_range()
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    process_stats = defaultdict(lambda: {
        'comm': '',
        'kernel_core_sec': 0.0,
        'user_core_sec': 0.0,
        'total_core_sec': 0.0
    })
    
    for s in samples:
        key = (s['comm'], s['pid'])
        process_stats[key]['comm'] = s['comm']
        process_stats[key]['pid'] = s['pid']
        
        core_val = s.get('core_per_sec') or 0
        process_stats[key]['total_core_sec'] += core_val
        
        stack = s.get('stack')
        if stack and stack.is_leaf_kernel:
            process_stats[key]['kernel_core_sec'] += core_val
        else:
            process_stats[key]['user_core_sec'] += core_val
    
    results = []
    high_kernel_processes = []
    
    for (comm, pid), stats in process_stats.items():
        proc_core_sec = stats['total_core_sec']
        
        if duration > 0:
            cpu_util = (proc_core_sec / duration) * 100
        else:
            cpu_util = 0
        
        if proc_core_sec > 0:
            kernel_ratio = (stats['kernel_core_sec'] / proc_core_sec) * 100
        else:
            kernel_ratio = 0
        
        # Track high kernel processes for risk
        if kernel_ratio > 80 and cpu_util > 5:
            high_kernel_processes.append(f"{comm}({pid})")
        
        results.append({
            'comm': comm,
            'pid': pid,
            'cpu_pct': format_percent(cpu_util),
            'kernel_pct': format_percent(kernel_ratio)
        })
    
    results.sort(key=lambda x: float(x['cpu_pct'].rstrip('%')), reverse=True)
    top_results = results[:args.top_n]
    
    # Add risk for high kernel processes
    if len(high_kernel_processes) > 0:
        output.add_risk(
            "warning" if len(high_kernel_processes) <= 2 else "critical",
            f"发现 {len(high_kernel_processes)} 个高内核态进程",
            f"分析热点: cluster-symbols --comm {results[0]['comm']}",
            patterns=["HIGH_KERNEL_PROCESSES"],
            targets=high_kernel_processes[:3]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！进程 CPU 利用率排序完全不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "total_processes": len(results),
            "shown_processes": len(top_results)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "processes": top_results
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
