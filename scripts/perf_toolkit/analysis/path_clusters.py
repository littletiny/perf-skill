#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Clustering - Cluster samples by common call path prefixes using Trie

使用 SymbolStack 和规范化后的符号名进行路径聚类
"""

import json
from collections import defaultdict
from ..core.reliability import assess_sample_reliability


class PathCluster:
    """Trie-based path clustering for stack samples"""
    
    def __init__(self, min_depth=2, min_samples=5):
        self.min_depth = min_depth
        self.min_samples = min_samples
        self.trie = {'_count': 0, '_samples': []}
    
    def add_sample(self, stack):
        """
        Add a stack sample to the trie.
        
        Args:
            stack: SymbolStack object (leaf-first order, reverse for root-first)
        """
        if not stack:
            return
        
        node = self.trie
        # Traverse from root to leaf (reverse the stack)
        # 使用规范化后的符号名
        for func in reversed(stack.get_normalized_names()):
            if func not in node:
                node[func] = {'_count': 0, '_samples': []}
            node = node[func]
            node['_count'] += 1
            # Store the normalized names list for leaf analysis
            node['_samples'].append(stack.get_normalized_names())
    
    def extract_clusters(self, node=None, path=None, clusters=None):
        """Extract clusters that meet the criteria"""
        if node is None:
            node = self.trie
        if path is None:
            path = []
        if clusters is None:
            clusters = []
        
        # Check if current node qualifies as a cluster
        if len(path) >= self.min_depth and node['_count'] >= self.min_samples:
            # Collect leaf distribution
            leaf_counts = defaultdict(int)
            for stack_names in node['_samples']:
                if stack_names:
                    leaf_counts[stack_names[0]] += 1
            
            # Collect representative sub-paths (most common full stacks)
            stack_counts = defaultdict(int)
            for stack_names in node['_samples']:
                stack_key = '→'.join(reversed(stack_names))
                stack_counts[stack_key] += 1
            
            top_stacks = sorted(stack_counts.items(), key=lambda x: -x[1])[:5]
            
            clusters.append({
                'path_signature': '→'.join(path),
                'depth': len(path),
                'sample_count': node['_count'],
                'leaves': dict(sorted(leaf_counts.items(), key=lambda x: -x[1])[:10]),
                'representative_stacks': [{'stack': s, 'count': c} for s, c in top_stacks]
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
    
    # Calculate duration and reliability
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    total_samples = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    reliability_level, warning_msg, metrics = assess_sample_reliability(
        total_samples, duration, total_core_per_sec=total_core_per_sec
    )
    
    # Build trie and extract clusters
    cluster_builder = PathCluster(min_depth=args.min_depth, min_samples=args.min_samples)
    
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            cluster_builder.add_sample(stack)
    
    clusters = cluster_builder.extract_clusters()
    
    # Calculate ratios and sort
    for c in clusters:
        c['ratio'] = f"{(c['sample_count'] / total_samples * 100):.2f}%"
        c['ratio_value'] = c['sample_count'] / total_samples * 100
        # Calculate leaf distribution percentages
        leaf_total = sum(c['leaves'].values())
        c['leaf_ratios'] = {
            leaf: f"{(count / leaf_total * 100):.1f}%"
            for leaf, count in sorted(c['leaves'].items(), key=lambda x: -x[1])
        }
    
    # Sort by sample count descending
    clusters.sort(key=lambda x: -x['sample_count'])
    
    # Apply top-n limit
    top_clusters = clusters[:args.top_n]
    
    # Calculate unclustered ratio
    clustered_samples = sum(c['sample_count'] for c in clusters)
    unclustered_ratio = (total_samples - clustered_samples) / total_samples * 100 if total_samples > 0 else 0
    
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
        'reliability': {
            'level': reliability_level,
            'warning': warning_msg,
            'metrics': metrics
        },
        'cluster_config': {
            'min_depth': args.min_depth,
            'min_samples': args.min_samples
        },
        'summary': {
            'total_samples': total_samples,
            'total_clusters': len(clusters),
            'shown_clusters': len(top_clusters),
            'clustered_samples': clustered_samples,
            'clustered_ratio': f"{(clustered_samples / total_samples * 100):.2f}%" if total_samples > 0 else "0%",
            'unclustered_ratio': f"{unclustered_ratio:.2f}%"
        },
        'clusters': [
            {
                'cluster_id': f"c_{i+1:03d}",
                'path_signature': c['path_signature'],
                'depth': c['depth'],
                'sample_count': c['sample_count'],
                'ratio': c['ratio'],
                'leaf_ratios': c['leaf_ratios'],
                'representative_stacks': c['representative_stacks']
            }
            for i, c in enumerate(top_clusters)
        ]
    }
    
    if reliability_level == "CRITICAL":
        output["_WARNING"] = "样本数过少！调用路径聚类结果完全不可信。"
    elif reliability_level in ["WARNING", "ACCEPTABLE"]:
        output["_NOTICE"] = "采样率偏低，路径聚类结果仅供参考，关注相对排序而非精确值。"
    
    print(json.dumps(output, indent= 2, ensure_ascii=False))
