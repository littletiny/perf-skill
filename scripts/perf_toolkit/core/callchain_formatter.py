#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CallChain Formatter - 统一的调用链格式化器

提供统一的调用链格式化功能，支持三种命令的不同输出风格：
- find-callers: bottom-up 风格，plain 样式
- cluster-paths: top-down 风格，plain 样式
- bottleneck-trace: top-down 风格，markdown 样式，带热点标记

新增功能：
- LayeredCallchainFormatter: 分层调用链格式化器（简化版）
- format_callchain_for_bottleneck: 便捷函数供 facade.py 使用
"""

from typing import List, Optional, Tuple

from config.defaults import CallChainFormat, StringConstants, OutputDefaults


# =============================================================================
# CallChainFormatter - 原有统一的调用链格式化器
# =============================================================================

class CallChainFormatter:
    """统一的 CallChain 格式化器"""
    
    @staticmethod
    def format(
        path: List[str],
        hotspot: Optional[str] = None,
        direction: str = "top_down",  # "top_down" | "bottom_up"
        style: str = "markdown",      # "markdown" | "plain"
        ratio: Optional[float] = None,
        use_hotspot_marker: bool = True
    ) -> str:
        """
        格式化调用链
        
        Args:
            path: 调用路径 (函数名列表)
            hotspot: 热点函数名 (可选)
            direction: 方向 "top_down" (入口->热点) 或 "bottom_up" (热点<-入口)
            style: 样式 "markdown" (带`标记) 或 "plain" (纯文本)
            ratio: 占比百分比 (可选)
            use_hotspot_marker: 是否使用 **[hotspot]** 标记
            
        Returns:
            格式化后的字符串
        """
        if not path:
            return OutputDefaults.NO_DATA
        
        # 根据方向确定分隔符
        if direction == "bottom_up":
            separator = CallChainFormat.SEPARATOR_BOTTOM_UP
        else:
            separator = CallChainFormat.SEPARATOR_TOP_DOWN
        
        # 格式化每个函数名
        formatted_parts = []
        for i, func in enumerate(path):
            # 检查是否是热点
            is_hotspot = hotspot and func == hotspot
            
            if is_hotspot and use_hotspot_marker:
                part = f"{CallChainFormat.HOTSPOT_PREFIX}{func}{CallChainFormat.HOTSPOT_SUFFIX}"
            elif style == "markdown":
                part = f"{CallChainFormat.CODE_MARKER}{func}{CallChainFormat.CODE_MARKER}"
            else:
                part = func
            
            formatted_parts.append(part)
        
        # 连接路径
        path_str = separator.join(formatted_parts)
        
        # 添加比例
        if ratio is not None:
            return CallChainFormat.TEMPLATE_WITH_RATIO.format(
                ratio=f"{ratio:.2f}%",
                path=path_str
            )
        
        return path_str
    
    @staticmethod
    def parse_path(path_str: str, separator: Optional[str] = None) -> List[str]:
        """
        解析调用链字符串为函数名列表
        
        Args:
            path_str: 调用链字符串
            separator: 分隔符 (默认自动检测)
            
        Returns:
            函数名列表
        """
        if not path_str or path_str == OutputDefaults.NA:
            return []
        
        # 自动检测分隔符
        if separator is None:
            if CallChainFormat.SEPARATOR_TOP_DOWN in path_str:
                separator = CallChainFormat.SEPARATOR_TOP_DOWN
            elif CallChainFormat.SEPARATOR_BOTTOM_UP in path_str:
                separator = CallChainFormat.SEPARATOR_BOTTOM_UP
            else:
                # 尝试直接分割
                return [path_str]
        
        parts = path_str.split(separator)
        
        # 去除代码标记
        cleaned = []
        for part in parts:
            part = part.strip()
            if part.startswith(CallChainFormat.CODE_MARKER) and part.endswith(CallChainFormat.CODE_MARKER):
                part = part[1:-1]
            # 去除热点标记 **[...]**
            if part.startswith(CallChainFormat.HOTSPOT_PREFIX) and part.endswith(CallChainFormat.HOTSPOT_SUFFIX):
                part = part[len(CallChainFormat.HOTSPOT_PREFIX):-len(CallChainFormat.HOTSPOT_SUFFIX)]
            cleaned.append(part)
        
        return cleaned


# =============================================================================
# LayeredCallchainFormatter - 分层调用链格式化器（简化版）
# =============================================================================

class LayeredCallchainFormatter:
    """
    分层调用链格式化器（简化版）
    
    支持两种输出模式：
    1. compact: 紧凑模式（单行）- 默认
    2. detailed: 详细模式（多行）- 可选
    
    Attributes:
        mode: 输出模式，"compact" 或 "detailed"
        max_display: 最多显示的层数
    """
    
    def __init__(self, mode: str = "compact", max_display: int = 5):
        """
        初始化分层调用链格式化器
        
        Args:
            mode: 输出模式，"compact" 或 "detailed"，默认为 "compact"
            max_display: 最多显示的层数，默认为 5
        """
        if mode not in ("compact", "detailed"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'compact' or 'detailed'")
        
        self.mode = mode
        self.max_display = max_display
    
    def format_callers(self, 
                       callers: List[str],
                       weight_percent: float,
                       index: int = 1) -> str:
        """
        格式化调用链
        
        Args:
            callers: 调用者列表
            weight_percent: 占比百分比
            index: 序号
            
        Returns:
            格式化后的字符串
        """
        if self.mode == "compact":
            return self._format_compact(callers, weight_percent, index)
        else:
            return self._format_detailed(callers, weight_percent, index)
    
    def _format_compact(self, 
                        callers: List[str], 
                        weight_percent: float, 
                        index: int) -> str:
        """紧凑格式（单行输出）"""
        if not callers:
            return f"#{index} [{weight_percent:.2f}%] (no callers)"
        
        display_callers = callers[:self.max_display]
        path_str = " <- ".join(display_callers)
        if len(callers) > self.max_display:
            path_str += " <- ..."
        
        return f"#{index} [{weight_percent:.2f}%] {path_str}"
    
    def _format_detailed(self, 
                         callers: List[str], 
                         weight_percent: float, 
                         index: int) -> str:
        """详细格式（多行输出）"""
        return self._format_compact(callers, weight_percent, index)
    
    def format_collapsed(self, 
                         extractions: List[Tuple[List[str], float]],
                         top_n: int = 5) -> str:
        """
        格式化多个调用链的汇总视图
        
        Args:
            extractions: (callers_list, weight_percent) 元组列表
            top_n: 最多显示的调用链数量
            
        Returns:
            多个调用链格式化的汇总字符串
        """
        lines = []
        sorted_extractions = sorted(extractions, key=lambda x: x[1], reverse=True)[:top_n]
        
        for i, (callers, weight) in enumerate(sorted_extractions, 1):
            lines.append(self.format_callers(callers, weight, i))
        
        return "\n".join(lines)


# =============================================================================
# 便捷函数
# =============================================================================

def format_callchain(
    path: List[str],
    hotspot: Optional[str] = None,
    direction: str = "top_down",
    style: str = "markdown",
    ratio: Optional[float] = None
) -> str:
    """便捷的 callchain 格式化函数"""
    return CallChainFormatter.format(path, hotspot, direction, style, ratio)


def format_callchain_for_bottleneck(
    stack: List[str],
    target_idx: int,
    target_symbol: str,
    weight_percent: float,
    index: int = 1
) -> str:
    """
    供 bottleneck 输出使用的便捷格式化函数
    """
    # 简化实现：直接格式化调用链
    callers = stack[target_idx+1:target_idx+6] if target_idx + 1 < len(stack) else []
    
    if not callers:
        return f"#{index} {target_symbol} [{weight_percent:.2f}%] (no callers)"
    
    path_str = " <- ".join(callers)
    return f"#{index} {target_symbol} [{weight_percent:.2f}%] <- {path_str}"
