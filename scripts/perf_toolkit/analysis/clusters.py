#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Clustering - Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)

使用 Symbol.normalized_name 进行规则匹配，基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。

V2 版本：使用统一数据模型
"""

import re
import json as json_mod
from collections import defaultdict
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import RiskInfo, ClusterItem, ClustersOutput, TimeRange


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
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality
    builder.assess_quality(samples)
    
    # Prepare rules
    rules = {}
    if args.include_experts and not args.no_include_experts:
        rules = EXPERT_RULES.copy()
    if args.custom_rules:
        rules.update(json_mod.loads(args.custom_rules))
    
    # Cluster samples
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    cluster_core_sec = defaultdict(float)
    lock_func_core_sec = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        core_per_sec = engine.get_sample_weight(s)
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
                    if group == "EVENT_LOCK_CONTENTION":
                        lock_func_core_sec[sym] += core_per_sec
        for g in matched_groups:
            cluster_core_sec[g] += core_per_sec
    
    # Calculate duration for cpu_util conversion
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    
    # Build results
    results = []
    lock_contention_ratio = 0
    
    for group, core_sec in cluster_core_sec.items():
        ratio = (core_sec / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
        cpu_util = (core_sec / duration * 100) if duration > 0 else 0
        if group == "EVENT_LOCK_CONTENTION":
            lock_contention_ratio = ratio
        results.append(ClusterItem.from_stats(group, ratio, cpu_util))
    
    results.sort(key=lambda x: float(x.ratio_pct.rstrip('%')), reverse=True)
    
    # Find top lock function for hint
    top_lock_func = max(lock_func_core_sec, key=lock_func_core_sec.get) if lock_func_core_sec else "pthread_mutex_lock"
    
    # Build risk info based on lock contention ratio
    if lock_contention_ratio > 50:
        risk = create_risk_info(
            level="critical",
            message=f"锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈' --risk 'critical' --hint 'find-callers --target {top_lock_func}'",
            patterns=["HIGH_LOCK_CONTENTION"]
        )
    elif lock_contention_ratio > 20:
        risk = create_risk_info(
            level="warning",
            message=f"锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈",
            hint="[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈' --risk 'warning' --hint 'find-callers --target pthread_mutex_lock'",
            patterns=["LOCK_CONTENTION"]
        )
    else:
        risk = create_risk_info(level="none")
    
    # Build time range
    time_range = None
    if samples:
        time_range = TimeRange.from_timestamps(
            samples[0].get('ts'),
            samples[-1].get('ts') if len(samples) > 0 else None
        )
    
    # Build output (no summary for cleaner output)
    output = ClustersOutput(
        _risk=risk,
        clusters=results,
        time_range=time_range
    )
    
    builder.print_output(output)
