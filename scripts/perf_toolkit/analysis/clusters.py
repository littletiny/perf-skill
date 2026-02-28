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
from ..core.format_utils import format_time_range, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


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
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '未找到样本数据' --risk 'warning' --hint '检查过滤条件'"
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
    
    rules = {}
    if args.include_experts and not args.no_include_experts:
        rules = EXPERT_RULES.copy()
    if args.custom_rules:
        rules.update(json.loads(args.custom_rules))
    
    cluster_core_sec = defaultdict(float)
    lock_func_core_sec = defaultdict(float)  # 记录各锁函数的 core_sec 用于溯源
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = s.get('core_per_sec', 0)
        normalized_names = stack.get_normalized_names()
        
        matched_groups = set()
        for sym in normalized_names:
            for group, pattern in rules.items():
                if isinstance(pattern, list):
                    pattern_str = '|'.join(pattern)
                else:
                    pattern_str = pattern
                if re.search(pattern_str, sym):
                    matched_groups.add(group)
                    # 记录锁函数用于后续溯源
                    if group == "EVENT_LOCK_CONTENTION":
                        lock_func_core_sec[sym] += core_per_sec
        for g in matched_groups:
            cluster_core_sec[g] += core_per_sec
    
    results = []
    lock_contention_ratio = 0
    
    for group, core_sec in cluster_core_sec.items():
        ratio = (core_sec / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
        if group == "EVENT_LOCK_CONTENTION":
            lock_contention_ratio = ratio
        results.append({
            "cluster": group,
            "ratio_pct": f"{ratio:.2f}%",
            "core_sec": format_core_sec(core_sec)
        })
    results.sort(key=lambda x: float(x['ratio_pct'].rstrip('%')), reverse=True)
    
    # 找出最频繁的锁函数用于溯源提示
    top_lock_func = max(lock_func_core_sec, key=lock_func_core_sec.get) if lock_func_core_sec else "pthread_mutex_lock"
    
    # Add risk for high lock contention
    if lock_contention_ratio > 50:
        output.add_risk(
            "critical",
            f"锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈' --risk 'critical' --hint 'find-callers --target {top_lock_func}'",
            patterns=["HIGH_LOCK_CONTENTION"]
        )
    elif lock_contention_ratio > 20:
        output.add_risk(
            "warning",
            f"锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈' --risk 'warning' --hint 'find-callers --target pthread_mutex_lock'",
            patterns=["LOCK_CONTENTION"]
        )
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！聚类结果完全不可信",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！聚类结果完全不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "total_core_seconds": format_core_sec(total_core_per_sec)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "clusters": results
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
