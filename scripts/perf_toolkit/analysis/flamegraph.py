#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlameGraph Generation - Generate FlameGraph format data for visualization

使用 SymbolStack 和规范化后的符号名生成火焰图数据。
基于 core/s（CPU 利用率）而非记录数统计。

注意：数据已按 1 秒聚合，记录数量无参考价值。
"""

from collections import defaultdict
from ..core.format_utils import format_core_sec
from ..core.output_builder import OutputBuilder


def cmd_generate_flamegraph(engine, args):
    """[Skill] Generate FlameGraph format data for visualization"""
    
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
    
    # Aggregate stack core/s
    stack_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            stack_str = ';'.join(reversed(stack.get_normalized_names()))
            stack_core_sec[stack_str] += core_per_sec
    
    total_core_sec = sum(stack_core_sec.values())
    
    # Build output based on format
    if args.format == 'folded':
        lines = []
        for stack, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1]):
            lines.append(f"{stack} {core_sec:.4f}")
        data_output = '\n'.join(lines)
        
        result = builder.build_simple({
            "format": "folded",
            "total_core_seconds": format_core_sec(total_core_sec),
            "data": data_output
        })
    else:
        stacks = []
        top_n = getattr(args, 'top_n', 1000)
        for stack_str, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1])[:top_n]:
            funcs = stack_str.split(';')
            stacks.append({
                "stack": funcs,
                "core_sec": format_core_sec(core_sec)
            })
        
        result = builder.build_simple({
            "format": "json",
            "total_core_seconds": format_core_sec(total_core_sec),
            "stacks": stacks
        })
    
    builder.print_json(result)
