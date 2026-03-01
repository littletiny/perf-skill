#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Clustering - Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

import os
import re
import json as json_mod
from collections import defaultdict
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import RiskInfo, ClusterItem, ClusterSummary, ClustersOutput, TimeRange


# Module-level cache for loaded rules files
_rules_cache = {}


def get_default_rules_path():
    """Get the default rules file path relative to this module"""
    # This module is at: scripts/perf_toolkit/analysis/clusters.py
    # Default rules is at: config/default-rules.json
    module_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up 3 levels: analysis/ -> perf_toolkit/ -> scripts/ -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
    return os.path.join(project_root, 'config', 'default-rules.json')


def load_rules_from_file(file_path):
    """Load rules from external JSON file (with module-level cache)"""
    # Normalize path for consistent caching
    abs_path = os.path.abspath(file_path)
    
    # Return cached result if available
    if abs_path in _rules_cache:
        return _rules_cache[abs_path]
    
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Rules file not found: {file_path}")
    
    with open(abs_path, 'r') as f:
        data = json_mod.load(f)
        # Filter out underscore-prefixed metadata keys
        rules = {k: v for k, v in data.items() if not k.startswith('_')}
    
    # Cache the result with absolute path
    _rules_cache[abs_path] = rules
    return rules


def load_default_rules():
    """Load default expert rules from config file, fallback to hardcoded"""
    default_path = get_default_rules_path()
    if os.path.exists(default_path):
        return load_rules_from_file(default_path)
    
    # Fallback to hardcoded rules if file doesn't exist
    return {
        "EVENT_IRQ_OFF": r"irqoff|spin_unlock_irqrestore|ksoftirqd",
        "EVENT_SCHEDULER": r"sched_|pick_next_task|load_balance|idle_balance|dequeue_task|enqueue_task",
        "EVENT_MEM_RECLAIM": r"direct_reclaim|try_to_free_pages|tlb_flush|tlb_shootdown",
        "EVENT_LOCK_CONTENTION": r"spin_lock|mutex_lock|rwsem_down|queued_spin_lock",
        "EVENT_SYNC_PRIMITIVE": r"pthread_mutex|pthread_cond|pthread_sig|futex_wait|futex_wake"
    }


# Symbol-based event classification (for cluster-symbols)
# Loaded once at module import time
EXPERT_RULES = load_default_rules()


def prepare_rules(args):
    """Prepare rules: merge built-in, file, and CLI rules by priority"""
    rules = {}
    
    # 1. Built-in expert rules (default included)
    if args.include_experts and not args.no_include_experts:
        rules = EXPERT_RULES.copy()
    
    # 2. External file rules (if specified)
    if getattr(args, 'rules_file', None):
        file_rules = load_rules_from_file(args.rules_file)
        rules.update(file_rules)
    
    # 3. CLI custom rules (highest priority)
    if args.custom_rules:
        rules.update(json_mod.loads(args.custom_rules))
    
    return rules


def cmd_apply_cluster(engine, args):
    """[Skill] Execute expert rule clustering or custom rule clustering"""
    
    builder = OutputBuilder(engine, args)
    
    # Trace v2.0 - 自动记录命令开始
    builder.begin_command("cluster-symbols")
    
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
    rules = prepare_rules(args)
    
    # Cluster samples using CPU utilization weights
    total_weight, _ = engine.get_total_core_per_sec(samples)
    cluster_weight = defaultdict(float)
    lock_func_weight = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack:
            continue
        
        weight = engine.get_sample_weight(s)
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
                        lock_func_weight[sym] += weight
        for g in matched_groups:
            cluster_weight[g] += weight
    
    # Build results
    results = []
    lock_contention_ratio = 0
    
    for group, weight in cluster_weight.items():
        ratio = (weight / total_weight * 100) if total_weight > 0 else 0
        if group == "EVENT_LOCK_CONTENTION":
            lock_contention_ratio = ratio
        results.append(ClusterItem.from_stats(group, ratio))
    
    results.sort(key=lambda x: float(x.pct_of_total.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    results = results[:top_n]
    
    # Find top lock function for hint
    top_lock_func = max(lock_func_weight, key=lock_func_weight.get) if lock_func_weight else "pthread_mutex_lock"
    
    # Build risk info based on lock contention ratio
    if lock_contention_ratio > 50:
        risk = create_risk_info(
            level="critical",
            message=f"锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈",
            hint=f"[必须] 添加到 Trace: spear trace add --desc '锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈' --hint 'find-callers --target {top_lock_func}'",
            patterns=["HIGH_LOCK_CONTENTION"]
        )
    elif lock_contention_ratio > 20:
        risk = create_risk_info(
            level="warning",
            message=f"锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈",
            hint="[必须] 添加到 Trace: spear trace add --desc '锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈' --hint 'find-callers --target pthread_mutex_lock'",
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
    
    # Build summary with truncation info
    summary = ClusterSummary(
        clusters_found=len(cluster_weight),
        shown_clusters=len(results)
    )
    
    # Build output
    output = ClustersOutput(
        _risk=risk,
        symbol_clusters=results,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
