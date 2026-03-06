#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Callchain Extractor - Intelligent call chain extraction with cross-state penetration support

This module provides smart call chain extraction capabilities, supporting:
1. Standard extraction for user-space functions
2. Kernel penetration mode for kernel alignment functions that need to trace into user-space

Usage:
    extractor = CallchainExtractor()
    result = extractor.extract(stack, target_idx, target_symbol)
    
    # result.kernel_path - kernel-space call path
    # result.business_callers - business layer call chain
    # result.user_entry_point - user-space entry point (e.g., __GI___nanosleep)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

# Try to import KernelAwareness from core.symbol, use mock if not available
try:
    from ..core.symbol import KernelAwareness
except ImportError:
    # Mock implementation for development phase
    class KernelAwareness:
        """Mock kernel awareness for development phase."""
        
        # Whitelist of kernel functions that need penetration analysis
        PENETRATION_TARGETS: set = {
            'finish_task_switch',
            '__schedule',
            'schedule',
            'switch_mm_irqs_off',
            'native_safe_halt',
            'do_nanosleep',
            'hrtimer_nanosleep',
        }
        
        @staticmethod
        def is_kernel_function(symbol_name: str, module: Optional[str] = None) -> bool:
            """
            Determine if a symbol is a kernel function.
            
            Rules:
            1. Name ends with _[k]
            2. Name starts with __ and is relatively short (heuristic for kernel internals)
            
            Args:
                symbol_name: The symbol name to check
                module: Optional module information
                
            Returns:
                True if the symbol is a kernel function
            """
            if not symbol_name:
                return False
            # Check for kernel marker _[k] suffix
            if symbol_name.endswith('_[k]'):
                return True
            # Some kernel functions start with __ (heuristic: kernel internal functions)
            # This is a simplified heuristic for the mock
            if symbol_name.startswith('__') and len(symbol_name) < 20:
                return True
            return False
        
        @staticmethod
        def should_penetrate(symbol_name: str) -> Tuple[bool, str]:
            """
            Determine if we need to penetrate into user-space for this symbol.
            
            Args:
                symbol_name: The target symbol name
                
            Returns:
                Tuple of (should_penetration, reason)
                - should_penetration: True if we should trace into user-space
                - reason: "in_whitelist" if in whitelist, empty string otherwise
            """
            # Remove _[k] suffix for comparison
            clean_name = symbol_name
            if symbol_name.endswith('_[k]'):
                clean_name = symbol_name[:-4]
            
            if clean_name in KernelAwareness.PENETRATION_TARGETS:
                return (True, "in_whitelist")
            return (False, "not_in_whitelist")
        
        @staticmethod
        def find_user_entry_point(stack: List[str], start_idx: int) -> Optional[int]:
            """
            Find the index of the first user-space function in the stack.
            
            Starting from start_idx, traverse the stack to find the first
            non-kernel function (user-space entry point).
            
            Args:
                stack: The complete call stack
                start_idx: Starting index for search
                
            Returns:
                Index of the first user-space function, or None if not found
            """
            for i in range(start_idx, len(stack)):
                if not KernelAwareness.is_kernel_function(stack[i]):
                    return i
            return None


@dataclass(frozen=True)
class ExtractedCallchain:
    """
    Extracted call chain result.
    
    This dataclass represents the result of call chain extraction,
    separating kernel-space and user-space paths for clear analysis.
    
    Attributes:
        target_symbol: The target function name being analyzed
        kernel_path: Kernel-space call path (from kernel alignment function to syscall entry)
        syscall_entry: System call entry point (e.g., __x64_sys_nanosleep)
        user_entry_point: User-space entry point (e.g., __GI___nanosleep)
        business_callers: Business layer call chain (starting from user_entry_point)
        raw_path: Complete raw path for debugging
        extraction_strategy: Strategy used for extraction
            - "standard": Normal extraction for user-space functions
            - "kernel_penetration": Cross-state extraction for kernel functions
            - "truncated": Extraction stopped before finding user-space
            - "empty": Empty result due to invalid input
    """
    target_symbol: str
    kernel_path: List[str]
    syscall_entry: Optional[str]
    user_entry_point: Optional[str]
    business_callers: List[str]
    raw_path: List[str]
    extraction_strategy: str  # "standard" | "kernel_penetration" | "truncated" | "empty"


class CallchainExtractor:
    """
    Intelligent call chain extractor.
    
    Automatically selects extraction strategy based on target function type:
    1. User-space functions: Standard extraction with fixed depth
    2. Kernel alignment functions: Penetration mode extending to user-space business functions
    
    Example:
        >>> extractor = CallchainExtractor()
        >>> stack = ["finish_task_switch_[k]", "__schedule_[k]", "...", "FindInTableWithLock"]
        >>> result = extractor.extract(stack, 0, "finish_task_switch_[k]")
        >>> result.extraction_strategy
        "kernel_penetration"
        >>> result.kernel_path
        ["__schedule_[k]", "..."]
        >>> result.business_callers
        ["FindInTableWithLock", "..."]
    """
    
    def __init__(self, 
                 default_max_depth: int = 10,
                 penetration_max_depth: int = 15,
                 min_kernel_layers: int = 3):
        """
        Initialize the call chain extractor.
        
        Args:
            default_max_depth: Maximum depth for standard extraction (default: 10)
            penetration_max_depth: Maximum depth for kernel penetration mode (default: 15)
            min_kernel_layers: Minimum kernel layers to preserve (default: 3)
        """
        self.default_max_depth = default_max_depth
        self.penetration_max_depth = penetration_max_depth
        self.min_kernel_layers = min_kernel_layers
    
    def extract(self,
                stack: List[str],
                target_idx: int,
                target_symbol: str) -> ExtractedCallchain:
        """
        Extract call chain from stack.
        
        Algorithm:
        1. Validate input (empty stack or out-of-bounds index)
        2. Determine target function type (kernel/user-space, needs penetration)
        3. Use standard extraction for normal functions
        4. Use penetration mode for kernel alignment functions
        
        Args:
            stack: Complete call stack (list of symbol names)
            target_idx: Index of target function in stack
            target_symbol: Name of target function
            
        Returns:
            ExtractedCallchain with extraction results
        """
        # Boundary check: empty stack or invalid index
        if not stack or target_idx < 0 or target_idx >= len(stack):
            return self._empty_result(target_symbol)
        
        # Determine function type and strategy
        is_kernel = KernelAwareness.is_kernel_function(target_symbol)
        should_pen, reason = KernelAwareness.should_penetrate(target_symbol)
        
        if is_kernel and should_pen:
            return self._extract_with_penetration(
                stack, target_idx, target_symbol
            )
        else:
            return self._extract_standard(
                stack, target_idx, target_symbol
            )
    
    def _extract_standard(self, stack: List[str], target_idx: int, target_symbol: str) -> ExtractedCallchain:
        """
        Standard extraction mode for user-space functions.
        
        Extracts callers starting from target_idx+1 up to default_max_depth.
        
        Args:
            stack: Complete call stack
            target_idx: Index of target function
            target_symbol: Name of target function
            
        Returns:
            ExtractedCallchain with standard extraction results
        """
        callers = stack[target_idx + 1:target_idx + 1 + self.default_max_depth]
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=callers,
            raw_path=list(stack),  # Create a copy to avoid reference issues
            extraction_strategy="standard"
        )
    
    def _extract_with_penetration(self, stack: List[str], target_idx: int, target_symbol: str) -> ExtractedCallchain:
        """
        Kernel penetration extraction mode.
        
        Key logic:
        1. Traverse upward, identifying kernel/user-space boundary
        2. Preserve kernel path (for display)
        3. Extract user-space business call chain
        
        Syscall entry heuristic:
        - Name contains 'sys_' (e.g., sys_nanosleep)
        - Name starts with '__x64_sys_' (e.g., __x64_sys_nanosleep)
        
        Args:
            stack: Complete call stack
            target_idx: Index of target function
            target_symbol: Name of target function
            
        Returns:
            ExtractedCallchain with penetration extraction results
        """
        kernel_path: List[str] = []
        business_callers: List[str] = []
        syscall_entry: Optional[str] = None
        user_entry_point: Optional[str] = None
        
        found_user = False
        kernel_layer_count = 0
        
        # Traverse stack from target_idx+1 to end
        for i in range(target_idx + 1, len(stack)):
            symbol = stack[i]
            is_sym_kernel = KernelAwareness.is_kernel_function(symbol)
            
            if is_sym_kernel and not found_user:
                # Still in kernel space
                kernel_path.append(symbol)
                kernel_layer_count += 1
                
                # Identify syscall entry (heuristic)
                # Pattern 1: contains 'sys_' (e.g., sys_read_[k])
                # Pattern 2: starts with '__x64_sys_' (e.g., __x64_sys_write_[k])
                # Note: use case-insensitive check for 'sys_'
                if 'sys_' in symbol.lower() or symbol.startswith('__x64_'):
                    syscall_entry = symbol
            else:
                # Found user-space function
                if not found_user:
                    found_user = True
                    user_entry_point = symbol
                
                # Collect business callers (up to default_max_depth)
                if len(business_callers) < self.default_max_depth:
                    business_callers.append(symbol)
            
            # Termination condition 1: Found user-space and collected enough business layers
            if found_user and len(business_callers) >= self.default_max_depth:
                break
            
            # Termination condition 2: Safety limit on total traversal depth
            if i - target_idx > self.penetration_max_depth:
                break
        
        # Determine extraction strategy based on results
        if found_user:
            strategy = "kernel_penetration"
        else:
            strategy = "truncated"
        
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=kernel_path,
            syscall_entry=syscall_entry,
            user_entry_point=user_entry_point,
            business_callers=business_callers,
            raw_path=list(stack),
            extraction_strategy=strategy
        )
    
    def _empty_result(self, target_symbol: str) -> ExtractedCallchain:
        """
        Return empty result for invalid input.
        
        Args:
            target_symbol: Name of target function
            
        Returns:
            ExtractedCallchain with empty results and "empty" strategy
        """
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=[],
            raw_path=[],
            extraction_strategy="empty"
        )
