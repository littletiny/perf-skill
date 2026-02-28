#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlameGraph Generation - Generate FlameGraph format data for visualization

使用 SymbolStack 和规范化后的符号名生成火焰图数据
"""

import json
from collections import defaultdict


def cmd_generate_flamegraph(engine, args):
    """[Skill] Generate FlameGraph format data for visualization"""
    # Get filtered samples by CPU, PID and comm
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
    
    # Count stack traces
    stack_counts = defaultdict(int)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            # FlameGraph format: func1;func2;func3 count
            # Reverse stack (root first for FlameGraph)
            # 使用规范化后的符号名
            stack_str = ';'.join(reversed(stack.get_normalized_names()))
            stack_counts[stack_str] += 1
    
    # Get actual time range from samples
    time_range = {
        "start": samples[0]['ts'] if samples else None,
        "end": samples[-1]['ts'] if samples else None
    }
    
    # Generate output
    if args.format == 'folded':
        # Standard folded stack format
        lines = []
        for stack, count in sorted(stack_counts.items(), key=lambda x: -x[1]):
            lines.append(f"{stack} {count}")
        output = '\n'.join(lines)
        
        result = {
            "format": "folded",
            "total_samples": len(samples),
            "unique_stacks": len(stack_counts),
            "cpu_id": args.cpu_id,
            "time_range": time_range,
            "data": output,
            "usage": "Paste into https://www.speedscope.app/ or use with flamegraph.pl"
        }
    else:
        # JSON format with structured data
        stacks = []
        for stack_str, count in sorted(stack_counts.items(), key=lambda x: -x[1])[:args.top_n]:
            funcs = stack_str.split(';')
            stacks.append({
                "stack": funcs,
                "count": count,
                "percentage": f"{(count/len(samples))*100:.2f}%"
            })
        
        result = {
            "format": "json",
            "total_samples": len(samples),
            "unique_stacks": len(stack_counts),
            "cpu_id": args.cpu_id,
            "time_range": time_range,
            "top_stacks": stacks
        }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
