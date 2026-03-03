#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CallChain Formatter - 统一的调用链格式化器

提供统一的调用链格式化功能，支持三种命令的不同输出风格：
- find-callers: bottom-up 风格，plain 样式
- cluster-paths: top-down 风格，plain 样式
- bottleneck-trace: top-down 风格，markdown 样式，带热点标记
"""

from typing import List, Optional

from config.defaults import CallChainFormat, StringConstants, OutputDefaults


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
            if hotspot:
                return CallChainFormatter._format_hotspot(hotspot, style, use_hotspot_marker)
            return OutputDefaults.NA
        
        # 选择分隔符
        separator = (CallChainFormat.SEPARATOR_TOP_DOWN 
                    if direction == "top_down" 
                    else CallChainFormat.SEPARATOR_BOTTOM_UP)
        
        # 格式化路径节点
        if style == "markdown":
            nodes = [f"{CallChainFormat.CODE_MARKER}{n}{CallChainFormat.CODE_MARKER}" 
                    for n in path]
        else:
            nodes = list(path)
        
        # 添加热点
        if hotspot:
            if use_hotspot_marker:
                hotspot_str = CallChainFormatter._format_hotspot(hotspot, style, True)
            else:
                hotspot_str = (f"{CallChainFormat.CODE_MARKER}{hotspot}{CallChainFormat.CODE_MARKER}"
                             if style == "markdown" else hotspot)
            
            # 热点是否已在路径中
            if path[-1] != hotspot:
                if direction == "top_down":
                    nodes.append(hotspot_str)
                else:
                    nodes.insert(0, hotspot_str)
        
        # 连接路径
        path_str = separator.join(nodes)
        
        # 添加比例
        if ratio is not None:
            return CallChainFormat.TEMPLATE_WITH_RATIO.format(
                ratio=f"{ratio:.2f}%",
                path=path_str
            )
        
        return path_str
    
    @staticmethod
    def _format_hotspot(hotspot: str, style: str, use_marker: bool) -> str:
        """格式化热点标记"""
        if not use_marker:
            if style == "markdown":
                return f"{CallChainFormat.CODE_MARKER}{hotspot}{CallChainFormat.CODE_MARKER}"
            return hotspot
        
        return (f"{CallChainFormat.HOTSPOT_PREFIX}{hotspot}{CallChainFormat.HOTSPOT_SUFFIX}")
    
    @staticmethod
    def parse(path_str: str, separator: Optional[str] = None) -> List[str]:
        """
        解析调用链字符串为列表
        
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


# 便捷函数
def format_callchain(
    path: List[str],
    hotspot: Optional[str] = None,
    direction: str = "top_down",
    style: str = "markdown",
    ratio: Optional[float] = None
) -> str:
    """便捷的 callchain 格式化函数"""
    return CallChainFormatter.format(path, hotspot, direction, style, ratio)
