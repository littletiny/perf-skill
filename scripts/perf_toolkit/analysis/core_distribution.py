#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization and thread states

分析各 CPU 核心的负载分布，识别负载不均衡、线程休眠模式等问题。

注意：数据已按 1 秒聚合，样本数量仅作为记录数参考，分析基于 core/s 值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality
from ..core.format_utils import format_time_range, format_percent
from ..core.risk_mixin import RiskAwareOutput


def cmd_analyze_core_distribution(engine, args):
    """[Skill] Analyze CPU core utilization distribution for a process"""
    
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
            "检查过滤条件"
        ).build({
            "error": "No samples found",
            "filters": {
                "pid": getattr(args, 'pid', None),
                "cpu_id": getattr(args, 'cpu_id', None)
            }
        })
        return print(json.dumps(result, indent=2, ensure_ascii=False))
    
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    core_stats = defaultdict(lambda: {
        'record_count': 0,
        'total_core_per_sec': 0.0,
    })
    comm_core_sec = defaultdict(float)  # 统计各 comm 的 CPU 使用，用于提示
    
    for s in samples:
        cpu_id = s.get('cpu')
        core_per_sec = s.get('core_per_sec', 0)
        comm = s.get('comm', '')
        
        if cpu_id is None:
            continue
        
        core_stats[cpu_id]['record_count'] += 1
        core_stats[cpu_id]['total_core_per_sec'] += core_per_sec
        if comm:
            comm_core_sec[comm] += core_per_sec
    
    active_cores = len(core_stats)
    
    core_list = []
    for cpu_id, stats in sorted(core_stats.items(), key=lambda x: x[1]['total_core_per_sec'], reverse=True):
        utilization = (stats['total_core_per_sec'] / duration * 100) if duration > 0 else 0
        
        state = "normal"
        if utilization > 90:
            state = "saturated"
        elif utilization < 5:
            state = "idle"
        
        core_list.append({
            "cpu_id": cpu_id,
            "utilization": format_percent(utilization),
            "state": state
        })
    
    # Identify imbalance
    if core_list:
        max_util = float(core_list[0]['utilization'].rstrip('%'))
        min_util = float(core_list[-1]['utilization'].rstrip('%'))
        avg_util = sum(float(c['utilization'].rstrip('%')) for c in core_list) / len(core_list)
        
        imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
        
        if imbalance_ratio > 10 and max_util > 50:
            imbalance_level = "CRITICAL"
        elif imbalance_ratio > 5:
            imbalance_level = "HIGH"
        elif imbalance_ratio > 2:
            imbalance_level = "MEDIUM"
        else:
            imbalance_level = "LOW"
        
        saturated_cores = [c for c in core_list if c['state'] == "saturated"]
        
        # 确定 hint 中使用的目标进程：优先用户使用 --comm 指定的，否则取 CPU 最高的
        user_comm = getattr(args, 'comm', None)
        top_comm = max(comm_core_sec, key=comm_core_sec.get) if comm_core_sec else None
        target_comm = user_comm or top_comm or '<comm>'
        
        # Add risk for critical imbalance
        if imbalance_level == "CRITICAL":
            output.add_risk(
                "critical",
                "负载严重不均衡: 单核满载，其他核心空闲",
                f"检查锁竞争: cluster-symbols --comm {target_comm}",
                patterns=["SINGLE_CORE_SATURATION"]
            )
        elif len(saturated_cores) == 1 and len(core_list) > 1:
            output.add_risk(
                "warning",
                f"单核满载 (CPU {saturated_cores[0]['cpu_id']})",
                f"检查锁竞争或CPU亲和性: cluster-symbols --comm {target_comm}",
                patterns=["SINGLE_CORE_SATURATION"]
            )
    else:
        imbalance_level = "UNKNOWN"
        max_util = min_util = avg_util = 0
        saturated_cores = []
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！分布分析结果不可信",
            "使用更长的采样时间重新采集数据",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "imbalance_level": imbalance_level,
            "max_utilization": format_percent(max_util),
            "min_utilization": format_percent(min_util),
            "saturated_cores": len(saturated_cores)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "cores": core_list
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
