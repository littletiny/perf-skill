#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Call Graph Generation - Generate Call Graph SVG/Graphviz DOT format

使用 SymbolStack 和规范化后的符号名生成调用图
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
    edge_counts = defaultdict(int)
    node_counts = defaultdict(int)
    
    for s in samples:
        stack = s.get('stack')
        if not stack or len(stack) == 0:
            continue
        
        # 获取规范化后的符号名列表
        normalized_names = stack.get_normalized_names()
        
        # Leaf node (where CPU was executing)
        node_counts[normalized_names[0]] += 1
        
        # Build edges (caller -> callee)
        # stack is leaf-first: [leaf, caller_of_leaf, ..., root]
        # So caller is at i+1, callee is at i
        for i in range(len(normalized_names) - 1):
            caller = normalized_names[i + 1]
            callee = normalized_names[i]
            edge_counts[(caller, callee)] += 1
            node_counts[caller] += 1
    
    # Filter to top nodes if specified
    if args.max_nodes > 0:
        top_nodes = set(sorted(node_counts.keys(), key=lambda x: -node_counts[x])[:args.max_nodes])
        # Filter edges to only include top nodes
        edge_counts = {k: v for k, v in edge_counts.items() if k[0] in top_nodes and k[1] in top_nodes}
    
    # Filter edges by min count
    edge_counts = {k: v for k, v in edge_counts.items() if v >= args.min_edge_count}
    
    if args.format == 'dot':
        # Generate Graphviz DOT format
        dot_lines = ['digraph callgraph {', '  rankdir=TB;', '  node [shape=box, style=rounded];', '']
        
        # Add nodes with color based on frequency
        max_count = max(node_counts.values()) if node_counts else 1
        for node in set(node for edge in edge_counts for node in edge):
            count = node_counts[node]
            intensity = count / max_count
            # Color from light yellow to red
            color = f"{int(255 * (1 - intensity * 0.5)):02x}{int(255 * (1 - intensity)):02x}99"
            label = f"{node}\\n({count})"
            dot_lines.append(f'  "{node}" [label="{label}", fillcolor="#{color}", style="filled"];')
        
        dot_lines.append('')
        
        # Add edges with thickness based on count
        max_edge = max(edge_counts.values()) if edge_counts else 1
        for (caller, callee), count in edge_counts.items():
            penwidth = max(1, min(10, count / max_edge * 5))
            dot_lines.append(f'  "{caller}" -> "{callee}" [label="{count}", penwidth={penwidth}];')
        
        dot_lines.append('}')
        
        result = {
            "format": "graphviz-dot",
            "total_samples": len(samples),
            "nodes": len(set(node for edge in edge_counts for node in edge)),
            "edges": len(edge_counts),
            "usage": "Save to file and run: dot -Tsvg callgraph.dot -o callgraph.svg",
            "data": '\n'.join(dot_lines)
        }
    else:
        # JSON format
        result = {
            "format": "json",
            "total_samples": len(samples),
            "nodes": {k: v for k, v in node_counts.items()},
            "edges": [{"caller": k[0], "callee": k[1], "count": v} for k, v in edge_counts.items()]
        }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
