#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Callchain Extractor - 智能调用链提取器

改进点：
1. 保留关键点：栈顶、栈底、热点
2. 非连续采样：让用户看清调用轨迹
3. 可配置总长度：max_display_length

Usage:
    extractor = SmartCallchainExtractor(samples, max_display_length=10)
    result = extractor.extract(stack, target_idx, target_symbol)
    
    # result.key_points - 保留的关键点列表
    # result.trajectory - 调用轨迹（带采样点）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Tuple
from collections import defaultdict

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import get_symbol_rules, SymbolRules, ProcessedStack


@dataclass
class KeyPoint:
    """关键点信息"""
    symbol: str
    idx: int  # 在原始栈中的索引
    type: str  # "target" | "entry" | "hotspot" | "anchor" | "sample"
    
    def __str__(self) -> str:
        if self.type == "hotspot":
            return f"[{self.symbol}]"
        return self.symbol


@dataclass
class SmartCallchain:
    """
    智能提取的调用链结果
    
    Attributes:
        target_symbol: 目标函数名
        display_chain: 用于展示的完整调用链
        key_points: 保留的关键点列表
        trajectory: 调用轨迹（关键点串联）
        hotspot_chain: 热点函数串联路径
        folded_count: 被折叠跳过的函数数
        penetration_depth: 穿透深度
        max_length: 配置的最大长度
    """
    target_symbol: str
    display_chain: str
    key_points: List[KeyPoint]
    trajectory: str  # 示例: "Target <- caller1 <- .. <- [Hotspot] <- .. <- entry_point"
    hotspot_chain: List[str]
    folded_count: int
    penetration_depth: int
    max_length: int
    
    def to_compact_string(self) -> str:
        """紧凑格式：只显示关键点"""
        return self.trajectory.replace(" <- ", "→")
    
    def to_detailed_string(self) -> str:
        """详细格式：含折叠信息"""
        lines = [f"轨迹: {self.trajectory}"]
        if self.folded_count > 0:
            lines.append(f"   [跳过了 {self.folded_count} 个中间函数，保留 {len(self.key_points)} 个关键点]")
        if len(self.hotspot_chain) > 1:
            lines.append(f"   [热点链: {' -> '.join(self.hotspot_chain)}]")
        return "\n".join(lines)


class SmartCallchainExtractor:
    """
    智能调用链提取器
    
    核心改进：
    1. 保留关键点（栈顶、栈底、热点）
    2. 非连续采样：在中间层按间隔保留采样点
    3. 可配置总长度限制
    
    关键点选择策略：
    - 必留：栈顶（距离目标最近）、栈底（入口点）
    - 必留：所有热点函数
    - 采样：中间层按间隔保留（让用户看清走向）
    - 折叠：其他冷函数跳过
    """
    
    # 默认参数
    DEFAULT_TOP_N = 20
    DEFAULT_MIN_RATIO = 0.005  # 0.5%
    DEFAULT_MAX_DEPTH = 30  # 最大穿透深度
    DEFAULT_MAX_DISPLAY_LENGTH = 12  # 默认显示的关键点数量
    DEFAULT_SAMPLE_INTERVAL = 3  # 采样间隔：每3层保留一个
    
    def __init__(self, 
                 samples,
                 max_display_length: int = DEFAULT_MAX_DISPLAY_LENGTH,
                 sample_interval: int = DEFAULT_SAMPLE_INTERVAL,
                 top_n: int = DEFAULT_TOP_N,
                 min_ratio: float = DEFAULT_MIN_RATIO,
                 max_depth: int = DEFAULT_MAX_DEPTH,
                 get_sample_weight_func=None,
                 symbol_rules: Optional[SymbolRules] = None):
        """
        初始化提取器
        
        Args:
            samples: 样本数据列表
            max_display_length: 最大显示的关键点数量（控制总长度）
            sample_interval: 采样间隔（每N层保留一个中间点）
            top_n: 取 Top N 作为热点
            min_ratio: 最小占比阈值
            max_depth: 最大穿透深度
            get_sample_weight_func: 获取样本权重的函数
            symbol_rules: 符号处理规则，默认从配置文件加载
        """
        self.max_display_length = max_display_length
        self.sample_interval = sample_interval
        self.top_n = top_n
        self.min_ratio = min_ratio
        self.max_depth = max_depth
        self.get_sample_weight = get_sample_weight_func or self._default_weight_func
        self.symbol_rules = symbol_rules or get_symbol_rules()
        
        # 学习热点函数
        self.hotspots = self._learn_hotspots(samples)
    
    @staticmethod
    def _default_weight_func(sample) -> float:
        """默认权重函数"""
        if hasattr(sample, 'weight'):
            return float(sample.weight)
        if hasattr(sample, 'cpu_util'):
            return float(sample.cpu_util)
        if hasattr(sample, 'core_per_sec'):
            return float(sample.core_per_sec)
        return 1.0
    
    def _learn_hotspots(self, samples) -> Set[str]:
        """从样本中学习热点函数（基于 self-weight）"""
        if not samples:
            return set()
        
        symbol_weights = defaultdict(float)
        
        for sample in samples:
            weight = self.get_sample_weight(sample)
            if weight <= 0:
                continue
            
            stack = sample.stack if hasattr(sample, 'stack') else None
            if stack:
                if hasattr(stack, 'get_normalized_names'):
                    symbols = stack.get_normalized_names()
                elif hasattr(stack, 'symbols'):
                    symbols = stack.symbols
                else:
                    symbols = list(stack)
            else:
                symbols = [sample.symbol] if hasattr(sample, 'symbol') else []
            
            # Self weight: 只有栈顶获得权重
            if symbols:
                top_symbol = symbols[0]
                if top_symbol:
                    symbol_weights[top_symbol] += weight
        
        if not symbol_weights:
            return set()
        
        sorted_symbols = sorted(symbol_weights.items(), key=lambda x: x[1], reverse=True)
        total = sum(symbol_weights.values())
        hotspots = set()
        
        # Top N
        for sym, weight in sorted_symbols[:self.top_n]:
            hotspots.add(sym)
        
        # 占比 > min_ratio
        for sym, weight in sorted_symbols:
            if total > 0 and weight / total >= self.min_ratio:
                hotspots.add(sym)
        
        return hotspots
    
    def is_hotspot(self, symbol: str) -> bool:
        return symbol in self.hotspots
    
    def extract(self, 
                stack: List[str], 
                target_idx: int, 
                target_symbol: str) -> SmartCallchain:
        """
        智能提取调用链
        
        算法：
        1. 使用 ProcessedStack 处理调用栈（应用 hidden/merge/collapse 规则）
        2. 收集所有关键点（栈顶、栈底、热点）
        3. 在中间区域按间隔采样
        4. 控制总长度不超过 max_display_length
        5. 生成轨迹字符串
        
        Args:
            stack: 完整调用栈
            target_idx: 目标函数索引
            target_symbol: 目标函数名
            
        Returns:
            SmartCallchain
        """
        if not stack or target_idx < 0 or target_idx >= len(stack):
            return self._empty_result(target_symbol)
        
        # 获取调用者区域（target 之后的栈）
        caller_start = target_idx + 1
        caller_end = min(caller_start + self.max_depth, len(stack))
        raw_callers = stack[caller_start:caller_end]
        
        # 使用 ProcessedStack 处理调用栈（应用所有 symbol 规则）
        processed = self.symbol_rules.process_stack(raw_callers)
        callers = processed.processed_stack
        
        if not callers:
            return SmartCallchain(
                target_symbol=target_symbol,
                display_chain="(no callers)",
                key_points=[KeyPoint(target_symbol, target_idx, "target")],
                trajectory=target_symbol,
                hotspot_chain=[target_symbol],
                folded_count=0,
                penetration_depth=0,
                max_length=self.max_display_length
            )
        
        # 阶段1：收集所有候选关键点（用 dict 去重，idx 为 key）
        candidates_map: Dict[int, KeyPoint] = {}
        
        # 1. 栈顶（距离目标最近的调用者）- 必留
        candidates_map[caller_start] = KeyPoint(callers[0], caller_start, "entry")
        
        # 2. 栈底（最底层的入口）- 使用有意义的锚点（跳过运行时函数）
        if len(callers) > 1:
            # 从栈底向上找有意义的锚点
            meaningful_idx_in_callers = self.symbol_rules.find_meaningful_anchor(callers)
            anchor_idx = caller_start + meaningful_idx_in_callers
            if anchor_idx != caller_start:
                candidates_map[anchor_idx] = KeyPoint(
                    callers[meaningful_idx_in_callers], anchor_idx, "anchor"
                )
        
        # 3. 热点函数 - 必留
        for i, sym in enumerate(callers):
            if self.is_hotspot(sym):
                idx = caller_start + i
                candidates_map[idx] = KeyPoint(sym, idx, "hotspot")
        
        # 4. 热点周围高密度采样 + 普通采样
        if len(callers) > 4:
            # 找到所有热点索引
            hotspot_indices = set()
            for i, sym in enumerate(callers):
                if self.is_hotspot(sym):
                    hotspot_indices.add(i)
            
            # 热点周围3层内密集采样
            for hotspot_idx in hotspot_indices:
                for offset in range(-3, 4):  # 热点前后各3层
                    i = hotspot_idx + offset
                    if 0 <= i < len(callers) and i not in hotspot_indices:
                        idx = caller_start + i
                        if idx not in candidates_map:
                            candidates_map[idx] = KeyPoint(callers[i], idx, "sample")
            
            # 热点之间补充采样：确保两个热点之间最多间隔2个采样点
            sorted_hotspots = sorted(hotspot_indices)
            for i in range(len(sorted_hotspots) - 1):
                gap = sorted_hotspots[i + 1] - sorted_hotspots[i]
                if gap > 5:  # 如果两个热点之间超过5层
                    # 在中间位置补充采样点
                    mid = (sorted_hotspots[i] + sorted_hotspots[i + 1]) // 2
                    for offset in [-1, 0, 1]:
                        sample_idx = mid + offset
                        if 0 <= sample_idx < len(callers) and sample_idx not in hotspot_indices:
                            idx = caller_start + sample_idx
                            if idx not in candidates_map:
                                candidates_map[idx] = KeyPoint(callers[sample_idx], idx, "sample")
            
            # 普通间隔采样（非热点区域）
            for i in range(self.sample_interval, len(callers) - 1, self.sample_interval):
                # 跳过热点附近已采样的（3层范围内）
                near_hotspot = any(abs(i - hi) <= 3 for hi in hotspot_indices)
                if not near_hotspot:
                    idx = caller_start + i
                    if idx not in candidates_map:
                        candidates_map[idx] = KeyPoint(callers[i], idx, "sample")
        
        candidates = list(candidates_map.values())
        
        # 阶段2：排序并限制数量
        candidates.sort(key=lambda kp: kp.idx)
        
        # 确保包含栈顶和栈底
        key_points = self._select_key_points(candidates, caller_start, caller_end - 1)
        
        # 阶段3：构建轨迹
        # target 符号也需要规范化（只保留 classname::method），如果是热点则加 [] 标记
        target_display = self.symbol_rules.normalize_symbol(target_symbol)
        if self.is_hotspot(target_symbol):
            target_display = f"[{target_display}]"
        trajectory_parts = [target_display]
        prev_idx = target_idx
        folded_count = 0
        hotspot_chain = [target_symbol]
        
        for kp in key_points:
            gap = kp.idx - prev_idx - 1
            if gap > 0:
                trajectory_parts.append("..")
                folded_count += gap
            
            # 热点用 [] 标记（symbol 已经通过 process_stack 规范化过了）
            display_symbol = kp.symbol  # 已经规范化
            if kp.type == "hotspot":
                display_name = f"[{display_symbol}]"
                hotspot_chain.append(kp.symbol)
            else:
                display_name = display_symbol
            
            trajectory_parts.append(display_name)
            prev_idx = kp.idx
        
        trajectory = " <- ".join(trajectory_parts)
        display_chain = trajectory
        
        return SmartCallchain(
            target_symbol=target_symbol,
            display_chain=display_chain,
            key_points=key_points,
            trajectory=trajectory,
            hotspot_chain=hotspot_chain,
            folded_count=folded_count,
            penetration_depth=len(callers),
            max_length=self.max_display_length
        )
    
    def _select_key_points(self, 
                          candidates: List[KeyPoint], 
                          stack_top_idx: int,
                          stack_bottom_idx: int) -> List[KeyPoint]:
        """
        选择关键点，优先保证调用链的清晰度
        
        策略变化：
        - 不再严格限制 key_points 数量，而是尽量展示清晰的调用路径
        - 优先保留热点之间的采样点，让用户看清调用链
        
        优先级：
        1. 栈顶（entry）- 必留
        2. 栈底（anchor）- 必留  
        3. 热点函数（hotspot）- 必留
        4. 热点之间的采样点 - 优先保留（看清调用路径）
        5. 其他采样点 - 填充剩余空间
        """
        # 分类
        entry = None
        anchor = None
        hotspots = []
        samples = []
        
        for kp in candidates:
            if kp.type == "entry":
                entry = kp
            elif kp.type == "anchor":
                anchor = kp
            elif kp.type == "hotspot":
                hotspots.append(kp)
            else:
                samples.append(kp)
        
        # 放宽限制：允许最多 max_display_length - 2 个关键点
        # 因为轨迹格式是交替的：Target <- kp1 <- .. <- kp2 ...
        max_key_points = max(1, self.max_display_length - 2)
        
        # 必选：栈顶和栈底
        selected = []
        if entry:
            selected.append(entry)
        if anchor and (not entry or anchor.idx != entry.idx):
            selected.append(anchor)
        
        # 所有热点必留
        for h in hotspots:
            if not any(kp.idx == h.idx for kp in selected):
                selected.append(h)
        
        # 找出热点之间的空隙，优先填充
        selected.sort(key=lambda kp: kp.idx)
        hotspot_and_ends = [kp for kp in selected if kp.type in ("entry", "anchor", "hotspot")]
        
        # 在热点/端点之间补充采样点
        if len(hotspot_and_ends) >= 2:
            for i in range(len(hotspot_and_ends) - 1):
                gap_start = hotspot_and_ends[i].idx
                gap_end = hotspot_and_ends[i + 1].idx
                gap_size = gap_end - gap_start
                
                # 如果空隙较大，补充1-2个采样点
                if gap_size > 4:
                    # 找中间位置的采样点
                    mid = (gap_start + gap_end) // 2
                    for s in samples:
                        if abs(s.idx - mid) <= 1 and not any(kp.idx == s.idx for kp in selected):
                            if len(selected) < max_key_points:
                                selected.append(s)
                                break
        
        # 如果还有空间，均匀添加其他采样点
        remaining = max_key_points - len(selected)
        if remaining > 0 and samples:
            samples.sort(key=lambda kp: kp.idx)
            # 找出还没被选中的采样点
            unused_samples = [s for s in samples if not any(kp.idx == s.idx for kp in selected)]
            step = max(1, len(unused_samples) // (remaining + 1))
            for i in range(step, len(unused_samples), step):
                if len(selected) >= max_key_points:
                    break
                selected.append(unused_samples[i])
        
        # 按索引排序
        selected.sort(key=lambda kp: kp.idx)
        return selected
    
    def _empty_result(self, target_symbol: str) -> SmartCallchain:
        """返回空结果"""
        return SmartCallchain(
            target_symbol=target_symbol,
            display_chain="(no callers)",
            key_points=[KeyPoint(target_symbol, 0, "target")],
            trajectory=target_symbol,
            hotspot_chain=[target_symbol],
            folded_count=0,
            penetration_depth=0,
            max_length=self.max_display_length
        )
    
    def get_hotspots_summary(self) -> str:
        """获取热点学习结果的摘要"""
        return f"Learned {len(self.hotspots)} hotspots: {', '.join(list(self.hotspots)[:10])}"


# =============================================================================
# 便捷函数
# =============================================================================

def extract_smart_callchain(samples,
                               stack: List[str],
                               target_idx: int,
                               target_symbol: str,
                               max_display_length: int = 8,
                               **kwargs) -> SmartCallchain:
    """
    便捷函数：一步完成提取器创建和调用链提取
    
    Args:
        samples: 样本数据（用于学习热点）
        stack: 调用栈
        target_idx: 目标函数索引
        target_symbol: 目标函数名
        max_display_length: 最大显示长度
        **kwargs: 其他参数
        
    Returns:
        SmartCallchain
    """
    extractor = SmartCallchainExtractor(samples, max_display_length=max_display_length, **kwargs)
    return extractor.extract(stack, target_idx, target_symbol)


def format_callchain_for_display(chain: SmartCallchain, 
                                    weight_percent: float,
                                    index: int = 1,
                                    mode: str = "compact") -> str:
    """
    格式化调用链用于显示
    
    Args:
        chain: SmartCallchain
        weight_percent: 占比
        index: 序号
        mode: "compact" | "detailed"
        
    Returns:
        格式化字符串
    """
    if mode == "compact":
        compact = chain.to_compact_string()
        return f"#{index} [{weight_percent:.2f}%] {compact}"
    else:
        detailed = chain.to_detailed_string()
        lines = detailed.split("\n")
        lines[0] = f"#{index} [{weight_percent:.2f}%] {lines[0]}"
        return "\n".join(lines)


