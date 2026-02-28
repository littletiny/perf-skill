#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Call Graph Generation - Generate Call Graph SVG/Graphviz DOT format

使用 SymbolStack 和规范化后的符号名生成调用图。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

import json
from collections import defaultdict


def cmd_generate_callgraph(engine, args):
    """[Skill] Generate Call Graph SVG/Graphviz DOT format"""
    # Get filtered samples by time range, CPU, PID and comm
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        cpu_id=getattr(args, 'cpu_id', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        print(json.dumps({"error": "No samples found"}, indent=2))
        return
    
    # Build call graph edges (caller -> callee)
    # 使用 core/s 作为权重进行统计，而非记录数
    edge_weights = defaultdict(float)
    node_weights = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        # 获取规范化后的符号名列表
        normalized_names = stack.get_normalized_names()
        
        # 使用 core/s 作为权重
        core_per_sec = s.get('core_per_sec', 0)
        
        # Leaf node (where CPU was executing)
        node_weights[normalized_names[0]] += core_per_sec
        
        # Build edges (caller -> callee)
        # stack is leaf-first: [leaf, caller_of_leaf, ..., root]
        # So caller is at i+1, callee is at i
        for i in range(len(normalized_names) - 1):
            caller = normalized_names[i + 1]
            callee = normalized_names[i]
            edge_weights[(caller, callee)] += core_per_sec
            node_weights[caller] += core_per_sec
    
    # Filter to top nodes if specified
    if args.max_nodes > 0:
        top_nodes = set(sorted(node_weights.keys(), key=lambda x: -node_weights[x])[:args.max_nodes])
        # Filter edges to only include top nodes
        edge_weights = {k: v for k, v in edge_weights.items() if k[0] in top_nodes and k[1] in top_nodes}
    
    # Filter edges by min weight (using min_edge_count as threshold for core/s)
    edge_weights = {k: v for k, v in edge_weights.items() if v >= args.min_edge_count * 0.001}
    
    if args.format == 'dot':
        # Generate Graphviz DOT format
        dot_lines = ['digraph callgraph {', '  rankdir=TB;', '  node [shape=box, style=rounded];', '']
        
        # Add nodes with color based on weight (core/s)
        max_weight = max(node_weights.values()) if node_weights else 1
        for node in set(node for edge in edge_weights for node in edge):
            weight = node_weights[node]
            intensity = weight / max_weight
            # Color from light yellow to red
            color = f"{int(255 * (1 - intensity * 0.5)):02x}{int(255 * (1 - intensity)):02x}99"
            label = f"{node}\\n({weight:.4f})"
            dot_lines.append(f'  "{node}" [label="{label}", fillcolor="#{color}", style="filled"];')
        
        dot_lines.append('')
        
        # Add edges with thickness based on weight
        max_edge_weight = max(edge_weights.values()) if edge_weights else 1
        for (caller, callee), weight in edge_weights.items():
            penwidth = max(1, min(10, weight / max_edge_weight * 5))
            dot_lines.append(f'  "{caller}" -> "{callee}" [label="{weight:.4f}", penwidth={penwidth}];')
        
        dot_lines.append('}')
        
        result = {
            "format": "graphviz-dot",
            "total_records": len(samples),
            "total_core_seconds": round(sum(node_weights.values()), 4),
            "nodes": len(set(node for edge in edge_weights for node in edge)),
            "edges": len(edge_weights),
            "usage": "Save to file and run: dot -Tsvg callgraph.dot -o callgraph.svg",
            "data": '\n'.join(dot_lines)
        }
    else:
        # JSON format
        result = {
            "format": "json",
            "total_records": len(samples),
            "total_core_seconds": round(sum(node_weights.values()), 4),
            "nodes": {k: round(v, 4) for k, v in node_weights.items()},
            "edges": [{"caller": k[0], "callee": k[1], "core_sec": round(v, 4)} for k, v in edge_weights.items()]
        }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
