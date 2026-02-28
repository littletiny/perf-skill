#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Clustering - Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)

使用 Symbol.normalized_name 进行规则匹配，基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
import re
from collections import defaultdict
from ..core.reliability import assess_data_quality


# Symbol-based event classification (for cluster-symbols)
EXPERT_RULES = {
    "EVENT_IRQ_OFF": r"irqoff|spin_unlock_irqrestore|ksoftirqd",
    "EVENT_SCHEDULER": r"sched_|pick_next_task|load_balance|idle_balance|dequeue_task|enqueue_task",
    "EVENT_MEM_RECLAIM": r"direct_reclaim|try_to_free_pages|tlb_flush|tlb_shootdown",
    "EVENT_LOCK_CONTENTION": r"spin_lock|mutex_lock|rwsem_down|queued_spin_lock",
    "EVENT_SYNC_PRIMITIVE": r"pthread_mutex|pthread_cond|pthread_sig|futex_wait|futex_wake"
}


def cmd_apply_cluster(engine, args):
    """[Skill] Execute expert rule clustering or custom rule clustering"""
    # Get filtered samples by time range, CPU, PID and comm
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        return print(json.dumps({
            "error": "No samples found",
            "filters": {
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None),
                "cpu_id": getattr(args, 'cpu_id', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
    
    # Calculate duration from filtered samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    rules = {}
    if args.include_experts and not args.no_include_experts:
        rules = EXPERT_RULES.copy()
    if args.custom_rules:
        rules.update(json.loads(args.custom_rules))
    
    # 使用 core/s 作为权重进行聚类统计
    cluster_core_sec = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        
        # 使用规范化后的符号名进行匹配
        normalized_names = stack.get_normalized_names()
        
        matched_groups = set()
        for sym in normalized_names:
            for group, pattern in rules.items():
                # 支持 pattern 为列表或字符串
                if isinstance(pattern, list):
                    # 列表转换为正则表达式
                    pattern_str = '|'.join(pattern)
                else:
                    pattern_str = pattern
                if re.search(pattern_str, sym):
                    matched_groups.add(group)
        for g in matched_groups:
            cluster_core_sec[g] += core_per_sec

    # 计算百分比
    results = []
    for group, core_sec in cluster_core_sec.items():
        ratio = (core_sec / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
        ref = "Custom" if group not in EXPERT_RULES else group.split('_')[0]
        results.append({
            "cluster": group,
            "ratio_pct": round(ratio, 2),
            "core_sec": round(core_sec, 4),
            "reference": ref
        })
    results.sort(key=lambda x: x['ratio_pct'], reverse=True)
    
    output = {
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            "start_time": getattr(args, 'start_time', None),
            "end_time": getattr(args, 'end_time', None),
            "cpu_id": getattr(args, 'cpu_id', None)
        },
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "total_core_seconds": round(total_core_per_sec, 4),
        "clusters": results
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！聚类结果完全不可信。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
