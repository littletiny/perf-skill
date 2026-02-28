#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

使用 SymbolStack 和规范化后的符号名进行路径聚类。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


class PathCluster:
    """Trie-based path clustering for stack samples"""
    
    def __init__(self, min_depth=2, min_core_sec=0.01):
        """
        Args:
            min_depth: Minimum path depth to form a cluster
            min_core_sec: Minimum core/s to form a cluster
        """
        self.min_depth = min_depth
        self.min_core_sec = min_core_sec
        self.trie = {'_core_sec': 0.0, '_samples': []}
    
    def add_sample(self, stack, core_per_sec=0):
        """
        Add a stack sample to the trie.
        
        Args:
            stack: SymbolStack object (leaf-first order, reverse for root-first)
            core_per_sec: CPU utilization for this sample
        """
        if not stack:
            return
        
        node = self.trie
        # Traverse from root to leaf (reverse the stack)
        # 使用规范化后的符号名
        for func in reversed(stack.get_normalized_names()):
            if func not in node:
                node[func] = {'_core_sec': 0.0, '_samples': []}
            node = node[func]
            node['_core_sec'] += core_per_sec
            # Store the normalized names list and core/s for leaf analysis
            node['_samples'].append((stack.get_normalized_names(), core_per_sec))
    
    def extract_clusters(self, node=None, path=None, clusters=None):
        """Extract clusters that meet the criteria"""
        if node is None:
            node = self.trie
        if path is None:
            path = []
        if clusters is None:
            clusters = []
        
        # Check if current node qualifies as a cluster
        if len(path) >= self.min_depth and node['_core_sec'] >= self.min_core_sec:
            # Collect leaf distribution (weighted by core/s)
            leaf_core_sec = defaultdict(float)
            for stack_names, core_sec in node['_samples']:
                if stack_names:
                    leaf_core_sec[stack_names[0]] += core_sec
            
            # Collect representative sub-paths (most common full stacks)
            stack_core_sec = defaultdict(float)
            for stack_names, core_sec in node['_samples']:
                stack_key = '→'.join(reversed(stack_names))
                stack_core_sec[stack_key] += core_sec
            
            top_stacks = sorted(stack_core_sec.items(), key=lambda x: -x[1])[:5]
            
            clusters.append({
                'path_signature': '→'.join(path),
                'depth': len(path),
                'core_sec': node['_core_sec'],
                'leaves': dict(sorted(leaf_core_sec.items(), key=lambda x: -x[1])[:10]),
                'representative_stacks': [{'stack': s, 'core_sec': round(c, 4)} for s, c in top_stacks]
            })
            
            # Don't recurse deeper - we've captured this cluster
            return clusters
        
        # Recurse into children
        for key, child in node.items():
            if not key.startswith('_'):
                self.extract_clusters(child, path + [key], clusters)
        
        return clusters


def cmd_cluster_paths(engine, args):
    """[Skill] Cluster samples by common call path prefixes using Trie"""
    # Get filtered samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        print(json.dumps({
            "error": "No samples found",
            "filters": {
                'cpu_id': getattr(args, 'cpu_id', None),
                'pid': getattr(args, 'pid', None),
                'comm': getattr(args, 'comm', None),
                'start_time': getattr(args, 'start_time', None),
                'end_time': getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    # Calculate duration and data quality
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Build trie and extract clusters
    # 将 min_samples 参数转换为 min_core_sec (默认 0.01 core/s)
    min_core_sec = getattr(args, 'min_samples', 5) * 0.001  # 简单映射
    cluster_builder = PathCluster(min_depth=args.min_depth, min_core_sec=min_core_sec)
    
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            cluster_builder.add_sample(stack, core_per_sec)
    
    clusters = cluster_builder.extract_clusters()
    
    # Calculate ratios and sort (基于 core/s)
    for c in clusters:
        c['ratio_pct'] = round((c['core_sec'] / total_core_per_sec * 100), 2) if total_core_per_sec > 0 else 0
        # Calculate leaf distribution percentages (weighted by core/s)
        leaf_total = sum(c['leaves'].values())
        c['leaf_ratios'] = {
            leaf: f"{(core_sec / leaf_total * 100):.1f}%"
            for leaf, core_sec in sorted(c['leaves'].items(), key=lambda x: -x[1])
        } if leaf_total > 0 else {}
    
    # Sort by core/s descending
    clusters.sort(key=lambda x: -x['core_sec'])
    
    # Apply top-n limit
    top_clusters = clusters[:args.top_n]
    
    # Calculate unclustered ratio
    clustered_core_sec = sum(c['core_sec'] for c in clusters)
    unclustered_ratio = ((total_core_per_sec - clustered_core_sec) / total_core_per_sec * 100) if total_core_per_sec > 0 else 0
    
    output = {
        'time_range': {
            'start': samples[0]['ts'],
            'end': samples[-1]['ts'],
            'duration_sec': round(duration, 2)
        },
        'filters': {
            'cpu_id': getattr(args, 'cpu_id', None),
            'pid': getattr(args, 'pid', None),
            'comm': getattr(args, 'comm', None),
            'comm_regex': getattr(args, 'comm_regex', None),
            'start_time': getattr(args, 'start_time', None),
            'end_time': getattr(args, 'end_time', None)
        },
        'data_quality': {
            'level': quality_level,
            'warning': warning_msg,
            'metrics': metrics
        },
        'cluster_config': {
            'min_depth': args.min_depth,
            'min_core_sec': min_core_sec
        },
        'summary': {
            'record_count': record_count,
            'total_core_seconds': round(total_core_per_sec, 4),
            'total_clusters': len(clusters),
            'shown_clusters': len(top_clusters),
            'clustered_core_sec': round(clustered_core_sec, 4),
            'clustered_ratio_pct': round((clustered_core_sec / total_core_per_sec * 100), 2) if total_core_per_sec > 0 else 0,
            'unclustered_ratio_pct': round(unclustered_ratio, 2)
        },
        'clusters': [
            {
                'cluster_id': f"c_{i+1:03d}",
                'path_signature': c['path_signature'],
                'depth': c['depth'],
                'core_sec': round(c['core_sec'], 4),
                'ratio_pct': c['ratio_pct'],
                'leaf_ratios': c['leaf_ratios'],
                'representative_stacks': c['representative_stacks']
            }
            for i, c in enumerate(top_clusters)
        ]
    }
    
    if quality_level == "CRITICAL":
        output["_WARNING"] = "数据质量不足！调用路径聚类结果完全不可信。"
    elif quality_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "数据质量中等，路径聚类结果仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent= 2, ensure_ascii=False))
