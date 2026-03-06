#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CallChain Formatter - 统一的调用链格式化器

提供统一的调用链格式化功能，支持三种命令的不同输出风格：
- find-callers: bottom-up 风格，plain 样式
- cluster-paths: top-down 风格，plain 样式
- bottleneck-trace: top-down 风格，markdown 样式，带热点标记

新增功能：
- LayeredCallchainFormatter: 分层调用链格式化器（支持内核态/用户态分离展示）
- format_callchain_for_bottleneck: 便捷函数供 facade.py 使用
"""

from typing import List, Optional, Tuple

from config.defaults import CallChainFormat, StringConstants, OutputDefaults


# =============================================================================
# ExtractedCallchain DataClass - Mock 实现
# 当 analysis.callchain_extractor 模块不可用时使用
# =============================================================================

try:
    from ..analysis.callchain_extractor import ExtractedCallchain
except ImportError:
    from dataclasses import dataclass
    
    @dataclass(frozen=True)
    class ExtractedCallchain:
        """
        提取的调用链结果
        
        Attributes:
            target_symbol: 目标函数名
            kernel_path: 内核态调用路径（从内核对齐函数到系统调用入口）
            syscall_entry: 系统调用入口点（如 __x64_sys_nanosleep）
            user_entry_point: 用户态入口点（如 __GI___nanosleep）
            business_callers: 业务层调用链（从 user_entry_point 往上）
            raw_path: 完整原始路径（用于调试）
            extraction_strategy: 使用的提取策略
        """
        target_symbol: str
        kernel_path: List[str]
        syscall_entry: Optional[str]
        user_entry_point: Optional[str]
        business_callers: List[str]
        raw_path: List[str]
        extraction_strategy: str


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


# =============================================================================
# LayeredCallchainFormatter - 分层调用链格式化器
# =============================================================================

class LayeredCallchainFormatter:
    """
    分层调用链格式化器
    
    支持两种输出模式：
    1. compact: 紧凑模式（单行，业务调用优先）
    2. detailed: 详细模式（内核/用户态分离展示）
    
    用于格式化 ExtractedCallchain 类型的调用链数据，
    清晰展示内核态和用户态的调用层次。
    
    Attributes:
        mode: 输出模式，"compact" 或 "detailed"
        max_kernel_display: 内核路径最多显示的层数
    
    Example:
        >>> from dataclasses import dataclass
        >>> from typing import List, Optional
        >>> 
        >>> @dataclass
        ... class MockExtractedCallchain:
        ...     target_symbol: str
        ...     kernel_path: List[str]
        ...     syscall_entry: Optional[str]
        ...     user_entry_point: Optional[str]
        ...     business_callers: List[str]
        ...     raw_path: List[str]
        ...     extraction_strategy: str
        >>> 
        >>> extracted = MockExtractedCallchain(
        ...     target_symbol="finish_task_switch",
        ...     kernel_path=["__schedule", "schedule"],
        ...     syscall_entry=None,
        ...     user_entry_point=None,
        ...     business_callers=["FindInTableWithLock", "InsertWithProb"],
        ...     raw_path=[],
        ...     extraction_strategy="kernel_penetration"
        ... )
        >>> formatter = LayeredCallchainFormatter(mode="compact")
        >>> result = formatter.format(extracted, 5.50, 1)
        >>> print(result)
        #1 [5.50%] FindInTableWithLock <- InsertWithProb
    """
    
    def __init__(self, mode: str = "compact", max_kernel_display: int = 5):
        """
        初始化分层调用链格式化器
        
        Args:
            mode: 输出模式，"compact" 或 "detailed"，默认为 "compact"
            max_kernel_display: 内核路径最多显示的层数，默认为 5
        
        Raises:
            ValueError: 当 mode 不是 "compact" 或 "detailed" 时
        """
        if mode not in ("compact", "detailed"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'compact' or 'detailed'")
        
        self.mode = mode
        self.max_kernel_display = max_kernel_display
    
    def format(self, 
               extracted: ExtractedCallchain,
               weight_percent: float,
               index: int = 1) -> str:
        """
        格式化调用链
        
        根据初始化时指定的 mode，调用相应的格式化方法。
        
        Args:
            extracted: 提取的调用链数据 (ExtractedCallchain 类型)
            weight_percent: 占比百分比（如 5.50 表示 5.50%）
            index: 序号（如 1, 2, 3...），用于输出前缀
            
        Returns:
            格式化后的字符串
            
        Example:
            >>> formatter = LayeredCallchainFormatter(mode="compact")
            >>> result = formatter.format(extracted, 5.50, 1)
            >>> assert "#1" in result
            >>> assert "5.50%" in result
        """
        if self.mode == "compact":
            return self._format_compact(extracted, weight_percent, index)
        else:
            return self._format_detailed(extracted, weight_percent, index)
    
    def _format_compact(self, 
                        extracted: ExtractedCallchain, 
                        weight_percent: float, 
                        index: int) -> str:
        """
        紧凑格式（单行输出）
        
        格式：`#{index} [{weight:.2f}%] {path}`
        
        优先显示 business_callers（业务调用链），如果不存在则回退到 kernel_path。
        
        Args:
            extracted: 提取的调用链数据
            weight_percent: 占比百分比
            index: 序号
            
        Returns:
            单行格式化的调用链字符串
            
        Example:
            >>> # 有业务调用链时
            >>> result = formatter._format_compact(extracted_with_business, 5.50, 1)
            >>> "#1 [5.50%] FindInTableWithLock <- InsertWithProb"
            >>> 
            >>> # 无业务调用链时（回退到内核路径）
            >>> result = formatter._format_compact(extracted_no_business, 1.28, 2)
            >>> "#2 [1.28%] __schedule <- schedule"
        """
        business = extracted.business_callers
        if not business:
            # 没有找到用户态调用者，显示内核路径（限制层数）
            path = extracted.kernel_path[:self.max_kernel_display]
            path_str = " <- ".join(path) if path else "(no callers)"
        else:
            path_str = " <- ".join(business)
        
        return f"#{index} [{weight_percent:.2f}%] {path_str}"
    
    def _format_detailed(self, 
                         extracted: ExtractedCallchain, 
                         weight_percent: float, 
                         index: int) -> str:
        """
        详细格式（多行输出，内核/用户态分离）
        
        输出格式：
        - 第一行：主调用链（business_callers）
        - 第二行：内核路径（可选，缩进显示）
        - 第三行：系统调用入口（可选）
        
        使用缩进和标签清晰分层，便于理解跨态调用关系。
        
        Args:
            extracted: 提取的调用链数据
            weight_percent: 占比百分比
            index: 序号
            
        Returns:
            多行格式化的调用链字符串
            
        Example:
            >>> result = formatter._format_detailed(extracted, 5.50, 3)
            >>> print(result)
            #3 [5.50%] FindInTableWithLock <- InsertWithProb <- PushVecFid <- PushModel <- PushModels
               [kernel] __schedule <- schedule <- do_nanosleep <- hrtimer_nanosleep <- ...
               [syscall] __x64_sys_nanosleep
        """
        lines = []
        
        # 主调用链（业务层）
        business = extracted.business_callers
        if business:
            business_str = " <- ".join(business)
            lines.append(f"#{index} [{weight_percent:.2f}%] {business_str}")
        else:
            # 如果没有业务调用链，显示内核路径作为主路径
            kernel = extracted.kernel_path
            if kernel:
                kernel_str = " <- ".join(kernel[:self.max_kernel_display])
                lines.append(f"#{index} [{weight_percent:.2f}%] {kernel_str}")
            else:
                lines.append(f"#{index} [{weight_percent:.2f}%] (no callers)")
        
        # 内核路径（可选展示，缩进）
        kernel = extracted.kernel_path
        if kernel and business:
            kernel_display = kernel[:self.max_kernel_display]
            kernel_str = " <- ".join(kernel_display)
            if len(kernel) > self.max_kernel_display:
                kernel_str += " <- ..."
            lines.append(f"   [kernel] {kernel_str}")
        
        # 系统调用入口
        if extracted.syscall_entry:
            lines.append(f"   [syscall] {extracted.syscall_entry}")
        
        return "\n".join(lines)
    
    def format_collapsed(self, 
                         extractions: List[Tuple[ExtractedCallchain, float]],
                         top_n: int = 5) -> str:
        """
        格式化多个调用链的汇总视图
        
        用于 bottleneck 输出的 CALLCHAINS 部分，一次性格式化多个调用链，
        按权重排序后取 top_n。
        
        Args:
            extractions: (ExtractedCallchain, weight_percent) 元组列表
            top_n: 最多显示的调用链数量，默认为 5
            
        Returns:
            多个调用链格式化的汇总字符串，用换行连接
            
        Example:
            >>> extractions = [
            ...     (extracted1, 5.50),
            ...     (extracted2, 1.28),
            ... ]
            >>> result = formatter.format_collapsed(extractions, top_n=2)
            >>> assert "#1" in result
            >>> assert "#2" in result
        """
        lines = []
        
        # 按权重降序排序，取 top_n
        sorted_extractions = sorted(extractions, 
                                    key=lambda x: x[1], 
                                    reverse=True)[:top_n]
        
        for i, (extracted, weight) in enumerate(sorted_extractions, 1):
            lines.append(self.format(extracted, weight, i))
        
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
    
    这是 facade.py 当前调用路径的替代品。内部创建 CallchainExtractor
    和 LayeredCallchainFormatter，提取并格式化调用链。
    
    Args:
        stack: 完整的调用栈（函数名列表）
        target_idx: 目标函数在栈中的索引
        target_symbol: 目标函数名
        weight_percent: 占比百分比
        index: 序号，默认为 1
        
    Returns:
        格式化后的调用链字符串
        
    Example:
        >>> stack = [
        ...     "finish_task_switch",
        ...     "__schedule",
        ...     "schedule",
        ...     "FindInTableWithLock",
        ... ]
        >>> result = format_callchain_for_bottleneck(
        ...     stack, 0, "finish_task_switch", 5.50, 1
        ... )
        >>> assert "finish_task_switch" in stack
        >>> assert "#1" in result
        >>> assert "5.50%" in result
    """
    # 尝试导入 CallchainExtractor，如果不存在则使用简单提取逻辑
    try:
        from ..analysis.callchain_extractor import CallchainExtractor
        extractor = CallchainExtractor()
        extracted = extractor.extract(stack, target_idx, target_symbol)
    except ImportError:
        # 回退到简单提取逻辑
        from dataclasses import dataclass
        from typing import List, Optional
        
        @dataclass
        class SimpleExtractedCallchain:
            target_symbol: str
            kernel_path: List[str]
            syscall_entry: Optional[str]
            user_entry_point: Optional[str]
            business_callers: List[str]
            raw_path: List[str]
            extraction_strategy: str
        
        # 简单提取：从目标索引+1开始取最多10层
        caller_stack = stack[target_idx+1:target_idx+11] if target_idx + 1 < len(stack) else []
        extracted = SimpleExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=caller_stack,
            raw_path=stack,
            extraction_strategy="simple_fallback"
        )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    return formatter.format(extracted, weight_percent, index)
