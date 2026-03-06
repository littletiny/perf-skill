#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

V3 版本（三层架构）：
- 提取 PathClustersAnalyzer 纯逻辑类
- 支持调用路径聚类
- Task-2.6.1: 返回 PathClustersResult dataclass
- V4: 集成 Symbol Processing，自动应用 hidden/merge/collapse/normalize 规则
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from collections import defaultdict
from .base import BaseAnalyzer
from ..core.engine_types import Sample
from ..core.models import RiskInfo
from .models import PathCluster, PathClustersResult


# =============================================================================
# Internal Data Structures
# =============================================================================

@dataclass
class PathClusterTrieNode:
    """Trie 节点 - 路径聚类中间结构"""
    weight: float = 0.0
    samples: List[tuple] = None
    children: Dict[str, 'PathClusterTrieNode'] = None
    
    def __post_init__(self):
        if self.samples is None:
            self.samples = []
        if self.children is None:
            self.children = {}


class PathClusterTrie:
    """Trie-based path clustering for stack samples with symbol processing"""

    def __init__(self, min_depth: int = 2, min_weight: float = 0.01, symbol_rules=None):
        self.min_depth = min_depth
        self.min_weight = min_weight
        self.root = PathClusterTrieNode()
        self.symbol_rules = symbol_rules

    def add_sample(self, stack, weight=0):
        if not stack:
            return
        
        # 获取调用栈符号列表
        names = stack.get_normalized_names()
        
        # 应用 symbol processing（hidden/merge/collapse/normalize）
        if self.symbol_rules:
            processed = self.symbol_rules.process_stack(names)
            names = processed.processed_stack
        
        if not names:
            return

        node = self.root
        for func in reversed(names):
            if func not in node.children:
                node.children[func] = PathClusterTrieNode()
            node = node.children[func]
            node.weight += weight
            node.samples.append((names, weight))

    def extract_clusters(self, node=None, path=None, clusters=None) -> List[PathCluster]:
        if node is None:
            node = self.root
        if path is None:
            path = []
        if clusters is None:
            clusters: List[PathCluster] = []

        if len(path) >= self.min_depth and node.weight >= self.min_weight:
            clusters.append(PathCluster(
                cluster_id="",  # 稍后分配
                path_signature='→'.join(path),
                depth=len(path),
                weight=node.weight
            ))
            return clusters

        for key, child in node.children.items():
            self.extract_clusters(child, path + [key], clusters)

        return clusters


# =============================================================================
# PathClustersAnalyzer
# =============================================================================

class PathClustersAnalyzer(BaseAnalyzer):
    """
    路径聚类分析器
    
    使用 Trie 对调用路径进行聚类，识别共同前缀模式。
    自动应用 symbol processing（hidden/merge/collapse/normalize）。
    """
    
    def __init__(self, engine):
        super().__init__(engine)
        # 延迟加载 symbol rules
        self._symbol_rules = None
    
    @property
    def symbol_rules(self):
        """获取 symbol rules（延迟加载）"""
        if self._symbol_rules is None:
            from config.defaults import get_symbol_rules
            self._symbol_rules = get_symbol_rules()
        return self._symbol_rules
    
    def analyze(self, samples: List[Sample],
                min_depth: Optional[int] = None,
                min_samples: Optional[int] = None,
                top_n: int = 10,
                comm: Optional[str] = None,
                pid: Optional[int] = None) -> PathClustersResult:
        """
        分析调用路径聚类
        
        Args:
            samples: 样本数据
            min_depth: 最小调用深度（默认从配置文件读取）
            min_samples: 最小样本数（默认从配置文件读取）
            top_n: 返回前 N 个聚类
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            
        Returns:
            PathClustersResult dataclass
        """
        # 从配置文件读取默认值
        clustering_config = self.symbol_rules.clustering
        if min_depth is None:
            min_depth = clustering_config.get('min_depth', 2)
        if min_samples is None:
            min_samples = clustering_config.get('min_samples', 5)
        if not samples:
            return PathClustersResult(
                clusters=[],
                total_clusters=0,
                shown_clusters=0,
                total_weight=0.0,
                clustered_weight=0.0,
                risks=[]
            )
        
        # 1. 过滤样本
        filtered_samples = samples
        if comm:
            filtered_samples = [s for s in filtered_samples if s.comm == comm]
        if pid:
            filtered_samples = [s for s in filtered_samples if s.pid == pid]
        
        # 2. 获取总量
        total_weight, _ = self._engine.get_total_core_per_sec(filtered_samples)
        duration = self._engine.get_duration(filtered_samples)
        
        # 3. 构建聚类（应用 symbol processing）
        min_weight = min_samples * 0.001
        cluster_builder = PathClusterTrie(
            min_depth=min_depth, 
            min_weight=min_weight,
            symbol_rules=self.symbol_rules
        )
        
        for s in filtered_samples:
            if s.stack and len(s.stack) > 0:
                weight = self._engine.get_sample_weight(s)
                cluster_builder.add_sample(s.stack, weight)
        
        clusters = cluster_builder.extract_clusters()
        
        # 4. 分配 cluster_id 和计算 CPU 利用率
        clusters_data: List[PathCluster] = []
        for i, c in enumerate(clusters):
            c.cluster_id = f"c_{i+1:03d}"
            c.cpu_util = (c.weight / duration * 100) if duration > 0 else 0.0
            clusters_data.append(c)
        
        clusters_data.sort(key=lambda x: -x.weight)
        top_clusters = clusters_data[:top_n]
        
        clustered_weight = sum(c.weight for c in top_clusters)
        
        return PathClustersResult(
            clusters=top_clusters,
            total_clusters=len(clusters),
            shown_clusters=len(top_clusters),
            total_weight=total_weight,
            clustered_weight=clustered_weight,
            risks=[]  # 路径聚类通常不产生 risk
        )
