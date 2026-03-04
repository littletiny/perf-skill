#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find-callers 命令实现

从 analysis/trace.py 迁移而来
"""

from typing import List, Dict, Any, Optional, Set, TYPE_CHECKING
from collections import defaultdict
import warnings

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.output_models import (
    RiskInfo, AttributionItem, AttributionSummary, AttributionsOutput, TimeRange
)

if TYPE_CHECKING:
    from perf_toolkit.core.output_builder import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


@command("find-callers")
def cmd_trace_attribution(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> AttributionsOutput:
    """[Skill] Bottom-up attribution for specific bottleneck functions"""

    # 使用 engine 统一接口获取总量
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)

    # 处理 auto-target: 获取热点函数作为目标
    target = args.target
    if getattr(args, 'auto_target', False) and target is None:
        from perf_toolkit.analysis.facade import get_facade
        facade = get_facade(engine)
        hotspots_result = facade.analyze_hotspots(samples, top_n=1)
        if hotspots_result.hotspots:
            auto_target_symbol = hotspots_result.hotspots[0].symbol
            if auto_target_symbol:
                target = auto_target_symbol
            else:
                # 热点函数 symbol 无效
                return AttributionsOutput(
                    _risk=RiskInfo(
                        level="warning",
                        message="自动选择的热点函数无效",
                        hint="[必须] 手动指定目标: --target <symbol>",
                        patterns=["INVALID_AUTO_TARGET"]
                    ),
                    attributions=[],
                    summary=AttributionSummary(
                        target=None,
                        target_cpu_util="0.00%",
                        total_attributions=0,
                        shown_attributions=0
                    )
                )
        else:
            # 无热点数据时返回空结果
            return AttributionsOutput(
                _risk=RiskInfo(
                    level="warning",
                    message="未找到热点函数，无法自动选择目标",
                    hint="[必须] 手动指定目标: --target <symbol> 或检查输入数据",
                    patterns=["NO_HOTSPOTS_FOUND"]
                ),
                attributions=[],
                summary=AttributionSummary(
                    target=None,
                    target_cpu_util="0.00%",
                    total_attributions=0,
                    shown_attributions=0
                )
            )
    
    # 检查 target 是否已指定（通过 --target 或 --auto-target）
    if target is None:
        return AttributionsOutput(
            _risk=RiskInfo(
                level="warning",
                message="未指定目标函数",
                hint="[必须] 使用 --target <symbol> 指定目标函数，或使用 --auto-target 自动选择热点函数",
                patterns=["NO_TARGET_SPECIFIED"]
            ),
            attributions=[],
            summary=AttributionSummary(
                target=None,
                target_cpu_util="0.00%",
                total_attributions=0,
                shown_attributions=0
            )
        )

    # Trace attribution
    attribution = defaultdict(float)
    target_weight = 0.0

    # 收集所有样本中的唯一函数名，用于符号匹配
    all_normalized_names: Set[str] = set()
    for s in samples:
        if s.stack:
            all_normalized_names.update(s.stack.get_normalized_names())

    # 查找匹配的符号（全局匹配，不依赖单个样本）
    matched_symbol = _find_matching_symbol(target, all_normalized_names)
    
    # 无匹配时返回警告
    if matched_symbol is None:
        return AttributionsOutput(
            _risk=RiskInfo(
                level="warning",
                message=f"未找到匹配函数 '{target}'",
                hint=f"[必须] 检查函数名拼写，或查看可用函数: get-hotspots --show-all",
                patterns=["NO_MATCHING_SYMBOL"]
            ),
            attributions=[],
            summary=AttributionSummary(
                target=target,
                target_cpu_util="0.00%",
                total_attributions=0,
                shown_attributions=0
            )
        )

    # 获取最大调用链深度限制（默认0表示无限制）
    max_depth = getattr(args, 'max_depth', 0)

    for s in samples:
        if not s.stack:
            continue

        weight = engine.get_sample_weight(s)
        normalized_names = s.stack.get_normalized_names()

        # 查找所有匹配的函数位置
        # 处理同一调用链中 target 多次出现的情况，每条路径都独立统计
        indices = [i for i, name in enumerate(normalized_names) if name == matched_symbol]
        if indices:
            target_weight += weight
            for idx in indices:
                # 提取完整的调用链（从 target 的调用者开始）
                if max_depth > 0:
                    caller_stack = normalized_names[idx+1:idx+1+max_depth]
                else:
                    caller_stack = normalized_names[idx+1:]
                if caller_stack:
                    attribution[tuple(caller_stack)] += weight

    # Build results - show ratio relative to total samples (not just target)
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    for stack, weight_val in attribution.items():
        # Calculate ratio relative to total samples
        ratio_total = (weight_val / total_weight) * 100 if total_weight > 0 else 0
        if ratio_total < min_ratio:
            continue
        results.append(AttributionItem(
            caller_stack=list(stack),
            ratio_of_target_pct=f"{ratio_total:.2f}%",
            cpu_util="0.00%"
        ))

    # 检测调用分叉（多个不同的调用路径）
    fork_detected = len(attribution) > 1

    results.sort(key=lambda x: float(x.ratio_of_target_pct.rstrip('%')), reverse=True)
    top_n = getattr(args, 'top_n', 10)
    results = results[:top_n]

    # Determine risk level
    risk = None
    if target_weight < 0.01:
        risk = RiskInfo(
            level="warning",
            message=f"目标函数 '{target}' 几乎无 CPU 活动",
            hint=f"[必须] 添加到 Trace: shecr trace add --desc '目标函数 {target} 几乎无 CPU 活动' --hint '检查目标函数名称是否正确'",
            patterns=["LOW_TARGET_ACTIVITY"]
        )
    else:
        risk = RiskInfo(level="none")

    # Create summary with truncation info
    target_cpu_util = (target_weight / duration * 100) if duration > 0 else 0
    
    # 如果匹配到了不同名称，显示匹配信息
    display_target = matched_symbol if matched_symbol != target else target
    
    summary = AttributionSummary(
        target=display_target,
        target_cpu_util=f"{target_cpu_util:.2f}%",
        total_attributions=len(attribution),
        shown_attributions=len(results)
    )

    # Build and output
    output = AttributionsOutput(
        _risk=risk,
        attributions=results,
        summary=summary
    )

    return output


def _find_matching_symbol(target: str, normalized_names: Set[str]) -> Optional[str]:
    """
    查找匹配的符号。
    
    匹配策略：
    1. 先尝试精确匹配
    2. 如果无精确匹配，尝试部分匹配（函数名包含target）
    3. 如果多个函数名都匹配，选择最短的（最精确的）那个，并记录 warning
    
    Args:
        target: 用户输入的目标函数名（可能是部分名称）
        normalized_names: 所有可用的规范化函数名集合
        
    Returns:
        匹配到的完整函数名，如果没有匹配则返回 None
    """
    # 1. 先尝试精确匹配
    if target in normalized_names:
        return target
    
    # 2. 尝试部分匹配（函数名包含target）
    partial_matches = [name for name in normalized_names if target in name]
    
    if not partial_matches:
        return None
    
    if len(partial_matches) == 1:
        return partial_matches[0]
    
    # 3. 多个匹配时，选择最短的（最精确的）
    # 例如："AdamOptimizer::Optimize" 匹配到多个时，
    # "parameter_server::optimizer::AdamOptimizer::Optimize" 比 
    # "parameter_server::optimizer::AdamOptimizer::OptimizeInternal" 更精确（更短）
    best_match = min(partial_matches, key=len)
    
    warnings.warn(
        f"目标 '{target}' 匹配到多个函数，选择最精确的匹配: '{best_match}'. "
        f"其他匹配: {', '.join(m for m in partial_matches if m != best_match)}",
        UserWarning
    )
    
    return best_match
