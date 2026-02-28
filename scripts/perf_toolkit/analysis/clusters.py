#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Clustering - Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)

使用 Symbol.normalized_name 进行规则匹配，保留 kernel/user 信息
"""

import json
import re
from collections import defaultdict
from ..core.reliability import assess_sample_reliability, format_percentage_with_ci


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
    total_samples = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    rules = {}
    if args.include_experts and not args.no_include_experts:
        rules = EXPERT_RULES.copy()
    if args.custom_rules:
        rules.update(json.loads(args.custom_rules))
    
    cluster_hits = defaultdict(int)
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
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
            cluster_hits[g] += 1

    results = []
    for group, count in cluster_hits.items():
        ratio_with_ci = format_percentage_with_ci(count, total_samples)
        ref = "Custom" if group not in EXPERT_RULES else group.split('_')[0]
        results.append({
            "cluster": group,
            "ratio": f"{(count/total_samples)*100:.2f}%",
            "ratio_with_ci": ratio_with_ci,
            "reference": ref,
            "sample_count": count
        })
    results.sort(key=lambda x: float(x['ratio'].replace('%', '')), reverse=True)
    
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
        "reliability": {
            "level": reliability_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "clusters": results
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！聚类结果完全不可信。"
    
    print(json.dumps(output, indent=2, ensure_ascii=False))
