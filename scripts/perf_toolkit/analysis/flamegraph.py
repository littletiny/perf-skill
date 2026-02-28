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
from ..core.format_utils import format_time_range, format_core_sec
from ..core.risk_mixin import RiskAwareOutput


def cmd_generate_flamegraph(engine, args):
    """[Skill] Generate FlameGraph format data for visualization"""
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
            "检查过滤条件"
        ).build({
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(args, 'start_time', None),
                getattr(args, 'end_time', None)
            )
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    stack_core_sec = defaultdict(float)
    for s in samples:
        stack = s.get('stack')
        if stack and len(stack) > 0:
            core_per_sec = s.get('core_per_sec', 0)
            stack_str = ';'.join(reversed(stack.get_normalized_names()))
            stack_core_sec[stack_str] += core_per_sec
    
    total_core_sec = sum(stack_core_sec.values())
    
    if args.format == 'folded':
        lines = []
        for stack, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1]):
            lines.append(f"{stack} {core_sec:.4f}")
        data_output = '\n'.join(lines)
        
        result = output.build({
            "format": "folded",
            "total_core_seconds": format_core_sec(total_core_sec),
            "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
            "data": data_output
        })
    else:
        stacks = []
        for stack_str, core_sec in sorted(stack_core_sec.items(), key=lambda x: -x[1])[:args.top_n]:
            funcs = stack_str.split(';')
            stacks.append({
                "stack": funcs,
                "core_sec": format_core_sec(core_sec)
            })
        
        result = output.build({
            "format": "json",
            "total_core_seconds": format_core_sec(total_core_sec),
            "time_range": format_time_range(samples[0]['ts'], samples[-1]['ts']),
            "stacks": stacks
        })
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
