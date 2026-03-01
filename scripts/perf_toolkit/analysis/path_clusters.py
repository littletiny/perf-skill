#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

V2 版本：使用统一数据模型

使用 SymbolStack 和规范化后的符号名进行路径聚类。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_core_sec
from ..core.output_builder_v2 import OutputBuilderV2, create_risk_info
from ..core.output_models import RiskInfo, PathClusterItem, PathClusterSummary, PathClustersOutput, TimeRange


class PathCluster:
    """Trie-based path clustering for stack samples"""
    
    def __init__(self, min_depth=2, min_core_sec=0.01):
        self.min_depth = min_depth
        self.min_core_sec = min_core_sec
        self.trie = {'_core_sec': 0.0, '_samples': []}
    
    def add_sample(self, stack, core_per_sec=0):
        if not stack:
            return
        
        node = self.trie
        for func in reversed(stack.get_normalized_names()):
            if func not in node:
                node[func] = {'_core_sec': 0.0, '_samples': []}
            node = node[func]
            node['_core_sec'] += core_per_sec
            node['_samples'].append((stack.get_normalized_names(), core_per_sec))
    
    def extract_clusters(self, node=None, path=None, clusters=None):
        if node is None:
            node = self.trie
        if path is None:
            path = []
        if clusters is None:
            clusters = []
        
        if len(path) >= self.min_depth and node['_core_sec'] >= self.min_core_sec:
            leaf_core_sec = defaultdict(float)
            for stack_names, core_sec in node['_samples']:
                if stack_names:
                    leaf_core_sec[stack_names[0]] += core_sec
            
            clusters.append({
                'path_signature': '→'.join(path),
                'depth': len(path),
                'core_sec': node['_core_sec'],
                'leaves': dict(sorted(leaf_core_sec.items(), key=lambda x: -x[1])[:5])
            })
            return clusters
        
        for key, child in node.items():
            if not key.startswith('_'):
                self.extract_clusters(child, path + [key], clusters)
        
        return clusters


def cmd_cluster_paths(engine, args):
    """[Skill] Cluster samples by common call path prefixes using Trie"""
    
    builder = OutputBuilderV2(engine, args)
    
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
    
    # Get total for ratio calculation
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    
    # Build clusters
    min_core_sec = getattr(args, 'min_samples', 5) * 0.001
    cluster_builder = PathCluster(min_depth=args.min_depth, min_core_sec=min_core_sec)
    
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            cluster_builder.add_sample(stack, core_per_sec)
    
    clusters = cluster_builder.extract_clusters()
    
    for c in clusters:
        c['ratio_pct'] = f"{(c['core_sec'] / total_core_per_sec * 100):.2f}%" if total_core_per_sec > 0 else "0.00%"
    
    clusters.sort(key=lambda x: -x['core_sec'])
    top_clusters = clusters[:args.top_n]
    
    clustered_core_sec = sum(c['core_sec'] for c in clusters)
    
    # Build output using V2 data models
    risk = create_risk_info("none", None, None)
    
    results = [
        PathClusterItem(
            cluster_id=f"c_{i+1:03d}",
            path_signature=c['path_signature'],
            ratio_pct=c['ratio_pct'],
            core_sec=format_core_sec(c['core_sec'])
        )
        for i, c in enumerate(top_clusters)
    ]
    
    summary = PathClusterSummary(
        total_clusters=len(clusters),
        clustered_core_sec=format_core_sec(clustered_core_sec)
    )
    
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    output = PathClustersOutput(
        _risk=risk,
        clusters=results,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
