#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Clustering - Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)

V3 版本（三层架构）：
- 提取 SymbolClustersAnalyzer 纯逻辑类
- 支持专家规则和自定义规则
"""

import os
import re
import json as json_mod
from collections import defaultdict
from typing import Dict, List, Any, Optional
from .base import BaseAnalyzer
from .models import Risk, SymbolCluster


# =============================================================================
# Rule Loading Functions (Module-level)
# =============================================================================

_rules_cache = {}


def get_default_rules_path():
    """Get the default rules file path relative to this module"""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
    return os.path.join(project_root, 'config', 'default-rules.json')


def load_rules_from_file(file_path):
    """Load rules from external JSON file (with module-level cache)"""
    abs_path = os.path.abspath(file_path)
    
    if abs_path in _rules_cache:
        return _rules_cache[abs_path]
    
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Rules file not found: {file_path}")
    
    with open(abs_path, 'r') as f:
        data = json_mod.load(f)
        rules = {k: v for k, v in data.items() if not k.startswith('_')}
    
    _rules_cache[abs_path] = rules
    return rules


def load_default_rules():
    """Load default expert rules from config file, fallback to hardcoded"""
    default_path = get_default_rules_path()
    if os.path.exists(default_path):
        return load_rules_from_file(default_path)
    
    # Fallback to hardcoded rules
    return {
        "EVENT_IRQ_OFF": r"irqoff|spin_unlock_irqrestore|ksoftirqd",
        "EVENT_SCHEDULER": r"sched_|pick_next_task|load_balance|idle_balance|dequeue_task|enqueue_task",
        "EVENT_MEM_RECLAIM": r"direct_reclaim|try_to_free_pages|tlb_flush|tlb_shootdown",
        "EVENT_LOCK_CONTENTION": r"spin_lock|mutex_lock|rwsem_down|queued_spin_lock",
        "EVENT_SYNC_PRIMITIVE": r"pthread_mutex|pthread_cond|pthread_sig|futex_wait|futex_wake"
    }


# Module-level default rules
DEFAULT_EXPERT_RULES = load_default_rules()

# Backward compatibility exports (for tests)
EXPERT_RULES = DEFAULT_EXPERT_RULES


def prepare_rules(args=None,
                  include_experts: bool = True,
                  no_include_experts: bool = False,
                  rules_file: Optional[str] = None,
                  custom_rules: Optional[str] = None) -> Dict[str, str]:
    """
    模块级规则准备函数（向后兼容）
    
    支持两种调用方式：
    1. prepare_rules(args) - 接受 argparse.Namespace 对象（测试兼容）
    2. prepare_rules(include_experts=..., ...) - 接受关键字参数
    
    实例方法已移至 SymbolClustersAnalyzer.prepare_rules()
    """
    # 如果传入 args 对象，从中提取参数
    if args is not None:
        include_experts = getattr(args, 'include_experts', True)
        no_include_experts = getattr(args, 'no_include_experts', False)
        rules_file = getattr(args, 'rules_file', None)
        custom_rules = getattr(args, 'custom_rules', None)
    
    rules = {}
    
    # 1. 内置专家规则
    if include_experts and not no_include_experts:
        rules = DEFAULT_EXPERT_RULES.copy()
    
    # 2. 外部文件规则
    if rules_file:
        file_rules = load_rules_from_file(rules_file)
        rules.update(file_rules)
    
    # 3. 命令行自定义规则（最高优先级）
    if custom_rules:
        # 尝试解析为 JSON
        if custom_rules.strip().startswith('{'):
            try:
                json_rules = json_mod.loads(custom_rules)
                rules.update(json_rules)
            except json_mod.JSONDecodeError:
                pass
        else:
            # name:pattern 格式
            for rule_def in custom_rules.split(','):
                if ':' in rule_def:
                    name, pattern = rule_def.split(':', 1)
                    rules[name.strip()] = pattern.strip()
    
    return rules


# =============================================================================
# SymbolClustersAnalyzer
# =============================================================================

class SymbolClustersAnalyzer(BaseAnalyzer):
    """
    符号聚类分析器
    
    使用专家规则对符号进行语义聚类。
    """
    
    # Risk 阈值
    LOCK_CONTENTION_CRITICAL = 50.0  # 严重锁竞争阈值
    LOCK_CONTENTION_WARNING = 20.0   # 轻度锁竞争阈值
    
    def __init__(self, engine):
        super().__init__(engine)
        self.rules = {}
    
    def prepare_rules(self, include_experts: bool = True,
                      no_include_experts: bool = False,
                      rules_file: Optional[str] = None,
                      custom_rules: Optional[str] = None) -> Dict[str, str]:
        """
        准备规则：按优先级合并内置规则、文件规则和命令行规则
        
        优先级（从高到低）：
        1. 命令行自定义规则
        2. 外部文件规则
        3. 内置专家规则
        """
        rules = {}
        
        # 1. 内置专家规则
        if include_experts and not no_include_experts:
            rules = DEFAULT_EXPERT_RULES.copy()
        
        # 2. 外部文件规则
        if rules_file:
            file_rules = load_rules_from_file(rules_file)
            rules.update(file_rules)
        
        # 3. 命令行自定义规则（最高优先级）
        if custom_rules:
            rules.update(json_mod.loads(custom_rules))
        
        self.rules = rules
        return rules
    
    def analyze(self, samples: List[Dict],
                top_n: int = 10,
                include_experts: bool = True,
                no_include_experts: bool = False,
                rules_file: Optional[str] = None,
                custom_rules: Optional[str] = None,
                comm: Optional[str] = None,
                pid: Optional[int] = None) -> Dict[str, Any]:
        """
        执行符号聚类分析
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个聚类
            include_experts: 是否包含内置专家规则
            no_include_experts: 是否禁用内置规则
            rules_file: 外部规则文件路径
            custom_rules: 命令行自定义规则（JSON 字符串）
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            
        Returns:
            {
                "result": {"clusters": [...], "lock_contention_ratio": float},
                "risks": [...]
            }
        """
        if not samples:
            return {
                "result": {"clusters": [], "lock_contention_ratio": 0.0},
                "risks": []
            }
        
        # 1. 准备规则
        rules = self.prepare_rules(include_experts, no_include_experts, 
                                   rules_file, custom_rules)
        
        # 2. 过滤样本
        filtered_samples = samples
        if comm:
            filtered_samples = [s for s in filtered_samples if s.get('comm') == comm]
        if pid:
            filtered_samples = [s for s in filtered_samples if s.get('pid') == pid]
        
        # 3. 聚类分析
        total_weight, _ = self._engine.get_total_core_per_sec(filtered_samples)
        cluster_weight = defaultdict(float)
        lock_func_weight = defaultdict(float)
        
        for s in filtered_samples:
            stack = s.get('stack')
            if not stack:
                continue
            
            weight = self._engine.get_sample_weight(s)
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
        
        # 4. 构建聚类结果
        clusters: List[SymbolCluster] = []
        lock_contention_ratio = 0.0
        
        for group, weight in cluster_weight.items():
            ratio = (weight / total_weight * 100) if total_weight > 0 else 0
            if group == "EVENT_LOCK_CONTENTION":
                lock_contention_ratio = ratio
            
            clusters.append(SymbolCluster(
                group=group,
                ratio=ratio,
                weight=weight
            ))
        
        clusters.sort(key=lambda x: x.ratio, reverse=True)
        
        # 5. 识别 risk
        risks: List[Risk] = []
        top_lock_func = max(lock_func_weight, key=lock_func_weight.get) if lock_func_weight else "pthread_mutex_lock"
        
        if lock_contention_ratio > self.LOCK_CONTENTION_CRITICAL:
            risks.append(self._create_risk(
                level="critical",
                message=f"锁竞争占比 {lock_contention_ratio:.2f}%，系统严重瓶颈",
                hint=f"find-callers --target {top_lock_func}",
                patterns=["HIGH_LOCK_CONTENTION"],
                pending_targets=[top_lock_func]
            ))
        elif lock_contention_ratio > self.LOCK_CONTENTION_WARNING:
            risks.append(self._create_risk(
                level="warning",
                message=f"锁竞争占比 {lock_contention_ratio:.2f}%，可能存在瓶颈",
                hint=f"find-callers --target {top_lock_func}",
                patterns=["LOCK_CONTENTION"],
                pending_targets=[top_lock_func]
            ))
        
        return {
            "result": {
                "clusters": [c.to_dict() for c in clusters[:top_n]],
                "lock_contention_ratio": lock_contention_ratio,
                "clusters_found": len(cluster_weight),
                "shown_clusters": min(len(clusters), top_n)
            },
            "risks": [r.to_dict() for r in risks]
        }


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import RiskInfo, ClusterItem, ClusterSummary, ClustersOutput, TimeRange


@command("cluster-symbols")
def cmd_cluster_symbols(builder, engine, args, samples):
    """[Skill] Execute expert rule clustering or custom rule clustering"""
    
    # 1. 调用 Analyzer
    analyzer = SymbolClustersAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        top_n=getattr(args, 'top_n', 10),
        include_experts=getattr(args, 'include_experts', True),
        no_include_experts=getattr(args, 'no_include_experts', False),
        rules_file=getattr(args, 'rules_file', None),
        custom_rules=getattr(args, 'custom_rules', None),
        comm=getattr(args, 'comm', None),
        pid=getattr(args, 'pid', None)
    )
    
    # 2. 记录 risks 到 Trace
    for risk_dict in result["risks"]:
        builder.record_risk(
            risk_dict["level"],
            risk_dict["message"],
            risk_dict["hint"]
        )
    
    # 3. 取最高级别 risk
    top_risk = None
    if result["risks"]:
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top_risk = min(result["risks"], key=lambda r: priority.get(r["level"], 3))
    
    # 4. 转换为 Output 模型
    results = [
        ClusterItem.from_stats(c["group"], c["ratio"])
        for c in result["result"]["clusters"]
    ]
    
    risk_output = create_risk_info(**top_risk) if top_risk else create_risk_info(level="none")
    
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples else None,
        samples[-1].get('ts') if len(samples) > 1 else None
    )
    
    summary = ClusterSummary(
        clusters_found=result["result"]["clusters_found"],
        shown_clusters=result["result"]["shown_clusters"]
    )
    
    output = ClustersOutput(
        _risk=risk_output,
        symbol_clusters=results,
        summary=summary,
        time_range=time_range
    )
    
    return output
