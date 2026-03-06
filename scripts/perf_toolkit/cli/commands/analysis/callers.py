#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find-callers 命令实现

从 analysis/trace.py 迁移而来
V2: 集成 Symbol Processing，自动应用 hidden/merge/collapse/normalize 规则
"""

from typing import List, Dict, Any, Optional, Set, TYPE_CHECKING, Union
from collections import defaultdict
import warnings

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.config_loader import get_analysis_thresholds
from perf_toolkit.core.output_models import (
    RiskInfo, AttributionItem, AttributionSummary, AttributionsOutput,
    TraceItem, TracesSummary, TracesOutput, TimeRange
)

if TYPE_CHECKING:
    from perf_toolkit.core.output_builder import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace

# Symbol rules 缓存（延迟加载）
_symbol_rules = None

def _get_symbol_rules():
    """获取 symbol rules（延迟加载）"""
    global _symbol_rules
    if _symbol_rules is None:
        from config.defaults import get_symbol_rules
        _symbol_rules = get_symbol_rules()
    return _symbol_rules


def _trace_single_target(
    target: str,
    samples: List[Dict[str, Any]],
    engine: 'PerfExpertEngine',
    total_weight: float,
    duration: float,
    min_ratio: float,
    top_n: int,
    max_depth: int,
    weight_basis: Optional[float] = None
) -> Optional[TraceItem]:
    """
    追踪单个目标的调用者
    
    Args:
        target: 目标函数名
        samples: 样本数据
        engine: PerfExpertEngine 实例
        total_weight: 总权重
        duration: 时间跨度
        min_ratio: 最小占比阈值
        top_n: 返回前 N 个调用者
        max_depth: 最大调用链深度
        weight_basis: 计算比例的分母，默认为 total_weight。用于聚合符号场景下排除聚合权重
        
    Returns:
        TraceItem 或 None（如果目标无调用者）
    """
    # 收集所有样本中的唯一函数名，用于符号匹配
    all_normalized_names: Set[str] = set()
    for s in samples:
        if s.stack:
            all_normalized_names.update(s.stack.get_normalized_names())

    # 查找匹配的符号
    matched_symbol = _find_matching_symbol(target, all_normalized_names)
    
    if matched_symbol is None:
        return None

    # Trace attribution
    attribution = defaultdict(float)
    target_weight = 0.0
    
    # 获取 symbol rules 用于处理调用者栈
    symbol_rules = _get_symbol_rules()

    for s in samples:
        if not s.stack:
            continue

        weight = engine.get_sample_weight(s)
        normalized_names = s.stack.get_normalized_names()

        # 查找所有匹配的函数位置
        indices = [i for i, name in enumerate(normalized_names) if name == matched_symbol]
        if indices:
            target_weight += weight
            for idx in indices:
                # 提取完整的调用链（从 target 的调用者开始）
                if max_depth > 0:
                    caller_stack = normalized_names[idx+1:idx+1+max_depth]
                else:
                    caller_stack = normalized_names[idx+1:]
                
                # 应用 symbol processing（hidden/merge/collapse/normalize）
                if caller_stack:
                    processed = symbol_rules.process_stack(caller_stack)
                    caller_stack = processed.processed_stack
                
                if caller_stack:
                    attribution[tuple(caller_stack)] += weight

    # Build attribution items
    results = []
    # 使用指定的 weight_basis 或默认的 total_weight
    basis = weight_basis if weight_basis is not None else total_weight
    
    for stack, weight_val in attribution.items():
        ratio_total = (weight_val / basis) * 100 if basis > 0 else 0
        if ratio_total < min_ratio:
            continue
        results.append(AttributionItem(
            caller_stack=list(stack),
            ratio_of_target_pct=f"{ratio_total:.2f}%",
            cpu_util="0.00%"
        ))

    if not results:
        return None

    results.sort(key=lambda x: float(x.ratio_of_target_pct.rstrip('%')), reverse=True)
    results = results[:top_n]

    target_ratio_pct = (target_weight / total_weight * 100) if total_weight > 0 else 0
    
    return TraceItem(
        target=matched_symbol,
        target_ratio_pct=f"{target_ratio_pct:.2f}%",
        attributions=results
    )


@command("find-callers")
def cmd_trace_attribution(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> Union[AttributionsOutput, TracesOutput]:
    """[Skill] Bottom-up attribution for specific bottleneck functions"""

    # 使用 engine 统一接口获取总量
    total_weight, _ = engine.get_total_core_per_sec(samples)
    duration = engine.get_duration(samples)

    # 处理 auto-target: 获取热点函数作为目标
    target = args.target
    is_auto_target = getattr(args, 'auto_target', False)
    
    if is_auto_target and target is None:
        from perf_toolkit.analysis.facade import get_facade
        facade = get_facade(engine)
        
        # 获取 top N 热点（按 self 排序）
        top_n_hotspots = getattr(args, 'top_n', 10)
        hotspots_result = facade.analyze_hotspots(samples, top_n=top_n_hotspots, sort_by='self')
        
        if not hotspots_result.hotspots:
            return TracesOutput(
                _risk=RiskInfo(
                    level="warning",
                    message="未找到热点函数，无法自动选择目标",
                    hint="[必须] 手动指定目标: --target <symbol> 或检查输入数据",
                    patterns=["NO_HOTSPOTS_FOUND"]
                ),
                traces=[],
                summary=TracesSummary(hotspots_traced=0)
            )
        
        # 获取参数
        min_ratio = getattr(args, 'min_ratio', 0.5)
        # auto-target 模式下默认使用 max_depth=5，避免完整调用链过长导致权重分散
        max_depth = getattr(args, 'max_depth', 0) or 5
        
        # 检测聚合符号（unknown_func[module]）占比
        thresholds = get_analysis_thresholds()
        aggregated_symbols = [h for h in hotspots_result.hotspots if h.symbol.startswith('unknown_func[')]
        aggregated_ratio = sum(h.self_pct for h in aggregated_symbols)
        
        # 计算有效总权重：当聚合符号占比过高时，扣除聚合符号权重
        # 这样非聚合符号的调用者比例会被放大，更容易被看到
        if aggregated_ratio > thresholds.aggregated_ratio_threshold:
            aggregated_weight = sum(h.self_pct / 100.0 * total_weight for h in aggregated_symbols)
            effective_total_weight = total_weight - aggregated_weight
        else:
            effective_total_weight = total_weight
        
        # 过滤掉聚合符号，只追踪可分析的非聚合符号
        traceable_hotspots = [h for h in hotspots_result.hotspots if not h.symbol.startswith('unknown_func[')]
        
        # 为每个可追踪的热点追踪调用者
        traces = []
        for hotspot in traceable_hotspots:
            trace_item = _trace_single_target(
                target=hotspot.symbol,
                samples=samples,
                engine=engine,
                total_weight=total_weight,
                duration=duration,
                min_ratio=min_ratio,
                top_n=5,  # 每个热点显示前5个调用者
                max_depth=max_depth,
                weight_basis=effective_total_weight
            )
            if trace_item:
                traces.append(trace_item)
        
        # 确定 risk level
        if not traces:
            risk = RiskInfo(
                level="warning",
                message="热点函数均无调用者（可能都位于调用链根部）",
                hint="尝试降低 --min-ratio 阈值，或使用 get-hotspots 查看热点详情",
                patterns=["NO_CALLERS_FOUND"]
            )
        else:
            risk = RiskInfo(level="none")
        
        return TracesOutput(
            _risk=risk,
            traces=traces,
            summary=TracesSummary(hotspots_traced=len(traces))
        )
    
    # 检查 target 是否已指定
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

    # 查找匹配的符号
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
    
    # 获取 symbol rules 用于处理调用者栈
    symbol_rules = _get_symbol_rules()

    for s in samples:
        if not s.stack:
            continue

        weight = engine.get_sample_weight(s)
        normalized_names = s.stack.get_normalized_names()

        # 查找所有匹配的函数位置
        indices = [i for i, name in enumerate(normalized_names) if name == matched_symbol]
        if indices:
            target_weight += weight
            for idx in indices:
                # 提取完整的调用链（从 target 的调用者开始）
                if max_depth > 0:
                    caller_stack = normalized_names[idx+1:idx+1+max_depth]
                else:
                    caller_stack = normalized_names[idx+1:]
                
                # 应用 symbol processing（hidden/merge/collapse/normalize）
                if caller_stack:
                    processed = symbol_rules.process_stack(caller_stack)
                    caller_stack = processed.processed_stack
                
                if caller_stack:
                    attribution[tuple(caller_stack)] += weight

    # Build results
    results = []
    min_ratio = getattr(args, 'min_ratio', 0.5)
    
    # 检测聚合符号占比，如果过高则调整权重计算
    thresholds = get_analysis_thresholds()
    aggregated_weight = 0.0
    for s in samples:
        if s.stack and len(s.stack) > 0:
            first_sym = s.stack.get_normalized_names()[0]
            if first_sym.startswith('unknown_func['):
                aggregated_weight += engine.get_sample_weight(s)
    
    aggregated_ratio = (aggregated_weight / total_weight * 100) if total_weight > 0 else 0
    if aggregated_ratio > thresholds.aggregated_ratio_threshold:
        effective_total_weight = total_weight - aggregated_weight
    else:
        effective_total_weight = total_weight
    
    for stack, weight_val in attribution.items():
        ratio_total = (weight_val / effective_total_weight) * 100 if effective_total_weight > 0 else 0
        if ratio_total < min_ratio:
            continue
        results.append(AttributionItem(
            caller_stack=list(stack),
            ratio_of_target_pct=f"{ratio_total:.2f}%",
            cpu_util="0.00%"
        ))

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
    elif not attribution:
        # 区分是 auto-target 还是手动指定
        is_auto = getattr(args, 'auto_target', False)
        if is_auto:
            hint_msg = f"该热点函数位于调用链根部（entry point）。建议手动指定其他热点：--target <function>，或使用更低的 --min-ratio 阈值"
        else:
            hint_msg = f"该函数位于调用链根部，通常是用户态程序入口或中断处理起点。建议分析其被谁调度：get-hotspots --comm {getattr(args, 'comm', '<comm>')} 查看整体热点分布"
        risk = RiskInfo(
            level="warning",
            message=f"目标函数 '{target}' 是调用链起点，无调用者",
            hint=hint_msg,
            patterns=["TARGET_IS_CALL_CHAIN_ROOT"]
        )
    elif not results and attribution:
        # 有调用者数据但被 min_ratio 过滤掉了
        is_auto = getattr(args, 'auto_target', False)
        if is_auto:
            hint_msg = f"该热点函数的调用者占比低于 --min-ratio={min_ratio}% 阈值。建议降低阈值：--min-ratio 0.1，或手动指定其他热点：--target <function>"
        else:
            hint_msg = f"目标函数的调用者占比低于 --min-ratio={min_ratio}% 阈值。建议降低阈值：--min-ratio 0.1"
        risk = RiskInfo(
            level="warning",
            message=f"目标函数 '{target}' 的调用者占比过低",
            hint=hint_msg,
            patterns=["CALLERS_BELOW_THRESHOLD"]
        )
    else:
        risk = RiskInfo(level="none")

    target_cpu_util = (target_weight / duration * 100) if duration > 0 else 0
    display_target = matched_symbol if matched_symbol != target else target
    
    summary = AttributionSummary(
        target=display_target,
        target_cpu_util=f"{target_cpu_util:.2f}%",
        total_attributions=len(attribution),
        shown_attributions=len(results)
    )

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
    best_match = min(partial_matches, key=len)
    
    warnings.warn(
        f"目标 '{target}' 匹配到多个函数，选择最精确的匹配: '{best_match}'. "
        f"其他匹配: {', '.join(m for m in partial_matches if m != best_match)}",
        UserWarning
    )
    
    return best_match
