#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlameGraph Generation - Generate FlameGraph format data for visualization

使用 SymbolStack 和规范化后的符号名生成火焰图数据。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
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
    
    # 使用 core/s 作为权重统计堆栈
    stack_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            # FlameGraph format: func1;func2;func3 core_sec
            # Reverse stack (root first for FlameGraph)
            # 使用规范化后的符号名
            stack_str = ';'.join(reversed(stack.get_normalized_names()))
            stack_core_sec[stack_str] += core_per_sec
    
    # Get actual time range from samples
    time_range = {
        "start": samples[0]['ts'] if samples else None,
        "end": samples[-1]['ts'] if samples else None
    }
    
    # Calculate total core/s
    total_core_sec = sum(stack_core_sec.values())
    
    # Generate output
    if args.format == 'folded':
        # Standard folded stack format (使用 core/s 替代 count)
        lines = []
        for stack, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1]):
            lines.append(f"{stack} {core_sec:.4f}")
        output = '\n'.join(lines)
        
        result = {
            "format": "folded",
            "record_count": len(samples),
            "total_core_seconds": round(total_core_sec, 4),
            "unique_stacks": len(stack_core_sec),
            "cpu_id": args.cpu_id,
            "time_range": time_range,
            "data": output,
            "usage": "Paste into https://www.speedscope.app/ or use with flamegraph.pl"
        }
    else:
        # JSON format with structured data
        stacks = []
        for stack_str, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1])[:args.top_n]:
            funcs = stack_str.split(';')
            percentage = (core_sec / total_core_sec * 100) if total_core_sec > 0 else 0
            stacks.append({
                "stack": funcs,
                "core_sec": round(core_sec, 4),
                "percentage_pct": round(percentage, 2)
            })
        
        result = {
            "format": "json",
            "record_count": len(samples),
            "total_core_seconds": round(total_core_sec, 4),
            "unique_stacks": len(stack_core_sec),
            "cpu_id": args.cpu_id,
            "time_range": time_range,
            "top_stacks": stacks
        }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
