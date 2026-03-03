#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

V3 版本（三层架构）：
- 提取 PathClustersAnalyzer 纯逻辑类
- 支持调用路径聚类
- Task-2.6.1: 返回 PathClustersResult dataclass
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from collections import defaultdict
from .base import BaseAnalyzer
from .models import Risk, PathCluster, PathClustersResult


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
    """Trie-based path clustering for stack samples"""

    def __init__(self, min_depth: int = 2, min_weight: float = 0.01):
        self.min_depth = min_depth
        self.min_weight = min_weight
        self.root = PathClusterTrieNode()

    def add_sample(self, stack, weight=0):
        if not stack:
            return

        node = self.root
        for func in reversed(stack.get_normalized_names()):
            if func not in node.children:
                node.children[func] = PathClusterTrieNode()
            node = node.children[func]
            node.weight += weight
            node.samples.append((stack.get_normalized_names(), weight))

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
    """
    
    def analyze(self, samples: List[Dict],
                min_depth: int = 2,
                min_samples: int = 5,
                top_n: int = 10,
                comm: Optional[str] = None,
                pid: Optional[int] = None) -> PathClustersResult:
        """
        分析调用路径聚类
        
        Args:
            samples: 样本数据
            min_depth: 最小调用深度
            min_samples: 最小样本数
            top_n: 返回前 N 个聚类
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            
        Returns:
            PathClustersResult dataclass
        """
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
            filtered_samples = [s for s in filtered_samples if s.get('comm') == comm]
        if pid:
            filtered_samples = [s for s in filtered_samples if s.get('pid') == pid]
        
        # 2. 获取总量
        total_weight, _ = self._engine.get_total_core_per_sec(filtered_samples)
        duration = self._engine.get_duration(filtered_samples)
        
        # 3. 构建聚类
        min_weight = min_samples * 0.001
        cluster_builder = PathClusterTrie(min_depth=min_depth, min_weight=min_weight)
        
        for s in filtered_samples:
            stack = s.get('stack')
            if stack and len(stack) > 0:
                weight = self._engine.get_sample_weight(s)
                cluster_builder.add_sample(stack, weight)
        
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


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, PathClusterItem, PathClusterSummary, PathClustersOutput, TimeRange
)


@command("cluster-paths")
def cmd_cluster_paths(builder, engine, args, samples):
    """[Skill] Cluster samples by common call path prefixes using Trie"""
    
    # 1. 调用 Analyzer
    analyzer = PathClustersAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        min_depth=getattr(args, 'min_depth', 2),
        min_samples=getattr(args, 'min_samples', 5),
        top_n=getattr(args, 'top_n', 10),
        comm=getattr(args, 'comm', None),
        pid=getattr(args, 'pid', None)
    )
    
    # 2. 路径聚类通常不产生 risk
    risk = create_risk_info(level="none")
    
    # 3. 转换为 Output 模型
    duration = engine.get_duration(samples)
    total_weight = result.total_weight
    
    results = [
        PathClusterItem.from_raw(
            cluster_id=c.cluster_id,
            path_signature=c.path_signature,
            weight=c.weight,
            total_weight=total_weight,
            duration=duration
        )
        for c in result.clusters
    ]
    
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples else None,
        samples[-1].get('ts') if len(samples) > 1 else None
    )
    
    summary = PathClusterSummary(
        total_clusters=result.total_clusters,
        shown_clusters=result.shown_clusters,
        clustered_weight=result.clustered_weight
    )
    
    output = PathClustersOutput(
        _risk=risk,
        path_clusters=results,
        summary=summary,
        time_range=time_range
    )
    
    return output
