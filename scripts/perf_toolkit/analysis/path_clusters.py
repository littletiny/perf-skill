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
from ..core.format_utils import format_time_range, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


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
    
    # Data quality risk
    if quality_level == "CRITICAL":
        output.add_risk(
            "critical",
            "数据质量不足！调用路径聚类结果完全不可信",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！调用路径聚类结果完全不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
            patterns=["CRITICAL_DATA_QUALITY"]
        )
    
    result = output.build({
        "summary": {
            "total_clusters": len(clusters),
            "clustered_core_sec": format_core_sec(clustered_core_sec)
        },
        "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
        "clusters": [
            {
                "cluster_id": f"c_{i+1:03d}",
                "path_signature": c['path_signature'],
                "ratio_pct": c['ratio_pct'],
                "core_sec": format_core_sec(c['core_sec'])
            }
            for i, c in enumerate(top_clusters)
        ]
    })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
