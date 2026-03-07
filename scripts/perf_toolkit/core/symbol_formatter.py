#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Formatter - 统一的符号格式化模块

为所有调用链相关命令提供一致的符号格式化风格：
- find-callers: bottom-up 风格
- cluster-paths: top-down 风格  
- bottleneck-analyze: 双向视图风格

格式规范 (AI友好 - 显式标记):
- 普通符号: sym (无特殊标记)
- 热点符号: **(hotspot:sym)**
- 聚合符号: (aggregate:name)
- 概念/折叠组: (concept:name)
- 聚合且热点: **(hotspot:aggregate:name)**
"""

from typing import List, Optional, Set
from dataclasses import dataclass


# =============================================================================
# Format Constants
# =============================================================================

class SymbolFormat:
    """符号格式常量"""
    # 热点标记
    HOTSPOT_PREFIX = "**(hotspot:"
    HOTSPOT_SUFFIX = ")**"
    
    # 聚合标记
    AGGREGATED_PREFIX = "(aggregate:"
    AGGREGATED_SUFFIX = ")"
    
    # 概念/折叠组标记
    CONCEPT_PREFIX = "(concept:"
    CONCEPT_SUFFIX = ")"
    
    # 聚合且热点 (复合标记)
    AGG_HOTSPOT_PREFIX = "**(hotspot:aggregate:"
    AGG_HOTSPOT_SUFFIX = ")**"
    
    # 分隔符
    SEP_TOP_DOWN = " → "      # 正向: 入口 → 热点
    SEP_BOTTOM_UP = " <- "    # 反向: 热点 <- 入口


# =============================================================================
# Symbol Formatter
# =============================================================================

class SymbolFormatter:
    """
    统一的符号格式化器
    
    所有调用链相关的符号格式化都通过此类完成，确保输出风格一致。
    """
    
    @staticmethod
    def format_symbol(symbol: str, is_hotspot: bool = False, is_aggregated: bool = False, is_concept: bool = False) -> str:
        """
        格式化单个符号
        
        Args:
            symbol: 符号名
            is_hotspot: 是否是热点符号
            is_aggregated: 是否是聚合符号
            is_concept: 是否是概念/折叠组
            
        Returns:
            格式化后的符号字符串
            
        Examples:
            >>> SymbolFormatter.format_symbol("func", False, False)
            'func'
            >>> SymbolFormatter.format_symbol("func", True, False)
            '**(hotspot:func)**'
            >>> SymbolFormatter.format_symbol("module", False, True)
            '(aggregate:module)'
            >>> SymbolFormatter.format_symbol("syscall", False, False, True)
            '(concept:syscall)'
            >>> SymbolFormatter.format_symbol("module", True, True)
            '**(hotspot:aggregate:module)**'
        """
        # 如果 symbol 本身已经是聚合格式，提取内部名称
        if symbol.startswith('(aggregate:') and symbol.endswith(')'):
            symbol = symbol[len('(aggregate:'):-1]
            is_aggregated = True
        
        if is_hotspot and is_aggregated:
            return f"{SymbolFormat.AGG_HOTSPOT_PREFIX}{symbol}{SymbolFormat.AGG_HOTSPOT_SUFFIX}"
        elif is_hotspot:
            return f"{SymbolFormat.HOTSPOT_PREFIX}{symbol}{SymbolFormat.HOTSPOT_SUFFIX}"
        elif is_concept:
            return f"{SymbolFormat.CONCEPT_PREFIX}{symbol}{SymbolFormat.CONCEPT_SUFFIX}"
        elif is_aggregated:
            return f"{SymbolFormat.AGGREGATED_PREFIX}{symbol}{SymbolFormat.AGGREGATED_SUFFIX}"
        else:
            return symbol
    
    @staticmethod
    def format_callchain(
        symbols: List[str],
        hotspots: Optional[Set[str]] = None,
        aggregated: Optional[Set[str]] = None,
        concepts: Optional[Set[str]] = None,
        direction: str = "bottom_up"
    ) -> str:
        """
        格式化调用链
        
        Args:
            symbols: 符号列表
            hotspots: 热点符号集合
            aggregated: 聚合符号集合
            concepts: 概念/折叠组集合
            direction: 方向 "bottom_up" (热点 <- 入口) 或 "top_down" (入口 → 热点)
            
        Returns:
            格式化后的调用链字符串
            
        Examples:
            >>> SymbolFormatter.format_callchain(["main", "func"], {"func"}, set())
            '**(hotspot:func)** <- main'
            >>> SymbolFormatter.format_callchain(["entry", "mod"], set(), {"mod"})
            'entry → (aggregate:mod)'
        """
        hotspots = hotspots or set()
        aggregated = aggregated or set()
        concepts = concepts or set()
        
        separator = SymbolFormat.SEP_BOTTOM_UP if direction == "bottom_up" else SymbolFormat.SEP_TOP_DOWN
        
        formatted_parts = []
        for sym in symbols:
            is_hot = sym in hotspots
            is_agg = sym in aggregated
            is_con = sym in concepts
            formatted_parts.append(SymbolFormatter.format_symbol(sym, is_hot, is_agg, is_con))
        
        return separator.join(formatted_parts)
    
    @staticmethod
    def parse_formatted_symbol(formatted: str) -> tuple:
        """
        解析格式化后的符号，返回 (原始符号, is_hotspot, is_aggregated, is_concept)
        
        Args:
            formatted: 格式化后的符号字符串
            
        Returns:
            (原始符号, 是否热点, 是否聚合, 是否概念)
            
        Examples:
            >>> SymbolFormatter.parse_formatted_symbol("**(hotspot:func)**")
            ('func', True, False, False)
            >>> SymbolFormatter.parse_formatted_symbol("(aggregate:module)")
            ('module', False, True, False)
            >>> SymbolFormatter.parse_formatted_symbol("**(hotspot:aggregate:mod)**")
            ('mod', True, True, False)
            >>> SymbolFormatter.parse_formatted_symbol("(concept:syscall)")
            ('syscall', False, False, True)
            >>> SymbolFormatter.parse_formatted_symbol("func")
            ('func', False, False, False)
        """
        # 聚合且热点: **(hotspot:aggregate:name)**
        if formatted.startswith(SymbolFormat.AGG_HOTSPOT_PREFIX) and formatted.endswith(SymbolFormat.AGG_HOTSPOT_SUFFIX):
            inner = formatted[len(SymbolFormat.AGG_HOTSPOT_PREFIX):-len(SymbolFormat.AGG_HOTSPOT_SUFFIX)]
            return (inner, True, True, False)
        
        # 热点: **(hotspot:name)**
        if formatted.startswith(SymbolFormat.HOTSPOT_PREFIX) and formatted.endswith(SymbolFormat.HOTSPOT_SUFFIX):
            inner = formatted[len(SymbolFormat.HOTSPOT_PREFIX):-len(SymbolFormat.HOTSPOT_SUFFIX)]
            # 检查是否是聚合热点 (hotspot:aggregate:name)
            if inner.startswith("aggregate:"):
                name = inner[len("aggregate:"):]
                return (name, True, True, False)
            return (inner, True, False, False)
        
        # 聚合: (aggregate:name)
        if formatted.startswith(SymbolFormat.AGGREGATED_PREFIX) and formatted.endswith(SymbolFormat.AGGREGATED_SUFFIX):
            inner = formatted[len(SymbolFormat.AGGREGATED_PREFIX):-len(SymbolFormat.AGGREGATED_SUFFIX)]
            return (inner, False, True, False)
        
        # 概念: (concept:name)
        if formatted.startswith(SymbolFormat.CONCEPT_PREFIX) and formatted.endswith(SymbolFormat.CONCEPT_SUFFIX):
            inner = formatted[len(SymbolFormat.CONCEPT_PREFIX):-len(SymbolFormat.CONCEPT_SUFFIX)]
            return (inner, False, False, True)
        
        # 普通符号
        return (formatted, False, False, False)


# =============================================================================
# Helper Functions
# =============================================================================

def format_sym(symbol: str, is_hotspot: bool = False, is_aggregated: bool = False, is_concept: bool = False) -> str:
    """便捷函数: 格式化单个符号"""
    return SymbolFormatter.format_symbol(symbol, is_hotspot, is_aggregated, is_concept)


def format_chain(
    symbols: List[str],
    hotspots: Optional[Set[str]] = None,
    aggregated: Optional[Set[str]] = None,
    concepts: Optional[Set[str]] = None,
    direction: str = "bottom_up"
) -> str:
    """便捷函数: 格式化调用链"""
    return SymbolFormatter.format_callchain(symbols, hotspots, aggregated, concepts, direction)


# =============================================================================
# Hotspot Detector (用于统一的热点检测)
# =============================================================================

@dataclass
class HotspotContext:
    """热点检测上下文"""
    hotspots: Set[str]
    aggregated: Set[str]
    
    @classmethod
    def from_samples(cls, samples, get_weight_func=None, top_n: int = 20, min_ratio: float = 0.005) -> 'HotspotContext':
        """
        从样本中学习热点
        
        Args:
            samples: 样本数据
            get_weight_func: 获取权重的函数
            top_n: Top N 热点
            min_ratio: 最小占比阈值
            
        Returns:
            HotspotContext
        """
        from collections import defaultdict
        
        symbol_weights = defaultdict(float)
        
        get_weight = get_weight_func or (lambda s: getattr(s, 'weight', 1.0))
        
        for sample in samples:
            weight = get_weight(sample)
            if weight <= 0:
                continue
            
            stack = getattr(sample, 'stack', None)
            if stack:
                if hasattr(stack, 'get_normalized_names'):
                    symbols = stack.get_normalized_names()
                elif hasattr(stack, 'symbols'):
                    symbols = stack.symbols
                else:
                    symbols = list(stack)
            else:
                symbols = [getattr(sample, 'symbol', '')] if hasattr(sample, 'symbol') else []
            
            # Self weight: 只有栈顶获得权重
            if symbols:
                top_symbol = symbols[0]
                if top_symbol:
                    symbol_weights[top_symbol] += weight
        
        if not symbol_weights:
            return cls(hotspots=set(), aggregated=set())
        
        sorted_symbols = sorted(symbol_weights.items(), key=lambda x: x[1], reverse=True)
        total = sum(symbol_weights.values())
        hotspots = set()
        
        # Top N
        for sym, weight in sorted_symbols[:top_n]:
            hotspots.add(sym)
        
        # 占比 > min_ratio
        for sym, weight in sorted_symbols:
            if total > 0 and weight / total >= min_ratio:
                hotspots.add(sym)
        
        # 检测聚合符号 (aggregate:name 格式)
        aggregated = set()
        for sym in hotspots:
            if sym.startswith('(aggregate:'):
                aggregated.add(sym)
        
        return cls(hotspots=hotspots, aggregated=aggregated)
    
    def is_hotspot(self, symbol: str) -> bool:
        """检查符号是否是热点"""
        return symbol in self.hotspots
    
    def is_aggregated(self, symbol: str) -> bool:
        """检查符号是否是聚合符号"""
        return symbol in self.aggregated
    
    def format(self, symbol: str) -> str:
        """格式化符号"""
        return SymbolFormatter.format_symbol(
            symbol,
            self.is_hotspot(symbol),
            self.is_aggregated(symbol)
        )


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    # 测试格式化
    print("=== Symbol Format Tests ===")
    
    test_cases = [
        ("func", False, False, False),
        ("func", True, False, False),
        ("module", False, True, False),
        ("module", True, True, False),
        ("syscall", False, False, True),
        ("syscall", True, False, True),
    ]
    
    for sym, is_hot, is_agg, is_con in test_cases:
        formatted = SymbolFormatter.format_symbol(sym, is_hot, is_agg, is_con)
        parsed = SymbolFormatter.parse_formatted_symbol(formatted)
        print(f"format({sym}, hot={is_hot}, agg={is_agg}, con={is_con}) = {formatted}")
        print(f"  parse({formatted}) = {parsed}")
        print()
    
    # 测试调用链格式化
    print("\n=== CallChain Format Tests ===")
    symbols = ["main", "worker", "hotfunc"]
    hotspots = {"hotfunc"}
    aggregated = set()
    
    chain = SymbolFormatter.format_callchain(symbols, hotspots, aggregated, None, "bottom_up")
    print(f"bottom_up: {chain}")
    
    chain = SymbolFormatter.format_callchain(symbols, hotspots, aggregated, None, "top_down")
    print(f"top_down: {chain}")
