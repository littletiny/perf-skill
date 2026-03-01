#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine

使用 SymbolStack 和规范化后的符号名进行路径聚类。
"""

from collections import defaultdict
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import RiskInfo, PathClusterItem, PathClusterSummary, PathClustersOutput, TimeRange


class PathCluster:
    """Trie-based path clustering for stack samples"""
    
    def __init__(self, min_depth=2, min_weight=0.01):
        self.min_depth = min_depth
        self.min_weight = min_weight
        self.trie = {'_weight': 0.0, '_samples': []}
    
    def add_sample(self, stack, weight=0):
        if not stack:
            return
        
        node = self.trie
        for func in reversed(stack.get_normalized_names()):
            if func not in node:
                node[func] = {'_weight': 0.0, '_samples': []}
            node = node[func]
            node['_weight'] += weight
            node['_samples'].append((stack.get_normalized_names(), weight))
    
    def extract_clusters(self, node=None, path=None, clusters=None):
        if node is None:
            node = self.trie
        if path is None:
            path = []
        if clusters is None:
            clusters = []
        
        if len(path) >= self.min_depth and node['_weight'] >= self.min_weight:
            leaf_weight = defaultdict(float)
            for stack_names, weight in node['_samples']:
                if stack_names:
                    leaf_weight[stack_names[0]] += weight
            
            clusters.append({
                'path_signature': '→'.join(path),
                'depth': len(path),
                'weight': node['_weight'],
                'leaves': dict(sorted(leaf_weight.items(), key=lambda x: -x[1])[:5])
            })
            return clusters
        
        for key, child in node.items():
            if not key.startswith('_'):
                self.extract_clusters(child, path + [key], clusters)
        
        return clusters


def cmd_cluster_paths(engine, args):
    """[Skill] Cluster samples by common call path prefixes using Trie"""
    
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
    
    # 使用 engine 统一接口获取总量和 duration
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)
    
    # Build clusters
    min_weight = getattr(args, 'min_samples', 5) * 0.001
    cluster_builder = PathCluster(min_depth=args.min_depth, min_weight=min_weight)
    
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            weight = engine.get_sample_weight(s)
        cluster_builder.add_sample(stack, weight)
    
    clusters = cluster_builder.extract_clusters()
    
    clusters.sort(key=lambda x: -x['weight'])
    top_clusters = clusters[:args.top_n]
    
    # Build output using V2 data models
    risk = create_risk_info("none", None, None)
    
    results = [
        PathClusterItem.from_raw(
            cluster_id=f"c_{i+1:03d}",
            path_signature=c['path_signature'],
            weight=c['weight'],
            total_weight=total_weight,
            duration=duration
        )
        for i, c in enumerate(top_clusters)
    ]
    
    # 计算 clustered_weight
    clustered_weight = sum(c['weight'] for c in top_clusters)
    
    time_range = TimeRange.from_timestamps(samples[0]['ts'], samples[-1]['ts'])
    
    # Build summary with truncation info
    summary = PathClusterSummary(
        total_clusters=len(clusters),
        shown_clusters=len(results),
        clustered_weight=clustered_weight
    )
    
    output = PathClustersOutput(
        _risk=risk,
        path_clusters=results,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)
