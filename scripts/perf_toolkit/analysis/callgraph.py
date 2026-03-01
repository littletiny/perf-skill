#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Call Graph Generation - Generate Call Graph SVG/Graphviz DOT format

使用 SymbolStack 和规范化后的符号名生成调用图。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_core_sec
from ..core.output_builder import OutputBuilder


def cmd_generate_callgraph(engine, args):
    """[Skill] Generate Call Graph SVG/Graphviz DOT format"""
    
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
    
    # Build edge and node weights
    edge_weights = defaultdict(float)
    node_weights = defaultdict(float)
    
    for s in samples:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        normalized_names = stack.get_normalized_names()
        core_per_sec = s.get('core_per_sec', 0)
        
        node_weights[normalized_names[0]] += core_per_sec
        
        for i in range(len(normalized_names) - 1):
            caller = normalized_names[i + 1]
            callee = normalized_names[i]
            edge_weights[(caller, callee)] += core_per_sec
            node_weights[caller] += core_per_sec
    
    # Apply filters
    max_nodes = getattr(args, 'max_nodes', 50)
    min_edge_count = getattr(args, 'min_edge_count', 1)
    
    if max_nodes > 0:
        top_nodes = set(sorted(node_weights.keys(), key=lambda x: -node_weights[x])[:max_nodes])
        edge_weights = {k: v for k, v in edge_weights.items() if k[0] in top_nodes and k[1] in top_nodes}
    
    edge_weights = {k: v for k, v in edge_weights.items() if v >= min_edge_count * 0.001}
    
    total_core_sec = sum(node_weights.values())
    
    # Build output based on format
    if args.format == 'dot':
        dot_lines = ['digraph callgraph {', '  rankdir=TB;', '  node [shape=box, style=rounded];', '']
        
        max_weight = max(node_weights.values()) if node_weights else 1
        for node in set(node for edge in edge_weights for node in edge):
            weight = node_weights[node]
            intensity = weight / max_weight
            color = f"{int(255 * (1 - intensity * 0.5)):02x}{int(255 * (1 - intensity)):02x}99"
            label = f"{node}\\n({weight:.4f})"
            dot_lines.append(f'  "{node}" [label="{label}", fillcolor="#{color}", style="filled"];')
        
        dot_lines.append('')
        
        max_edge_weight = max(edge_weights.values()) if edge_weights else 1
        for (caller, callee), weight in edge_weights.items():
            penwidth = max(1, min(10, weight / max_edge_weight * 5))
            dot_lines.append(f'  "{caller}" -> "{callee}" [label="{weight:.4f}", penwidth={penwidth}];')
        
        dot_lines.append('}')
        
        result = builder.build_simple({
            "format": "graphviz-dot",
            "total_core_seconds": format_core_sec(total_core_sec),
            "nodes": len(set(node for edge in edge_weights for node in edge)),
            "edges": len(edge_weights),
            "data": '\n'.join(dot_lines)
        })
    else:
        result = builder.build_simple({
            "format": "json",
            "total_core_seconds": format_core_sec(total_core_sec),
            "nodes": {k: format_core_sec(v) for k, v in node_weights.items()},
            "edges": [{"caller": k[0], "callee": k[1], "core_sec": format_core_sec(v)} for k, v in edge_weights.items()]
        })
    
    builder.print_json(result)
