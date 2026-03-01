#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Data Structure - Structured representation of perf symbols with kernel/user awareness

原始 perf script 数据中，kernel 函数带有 `_[k]` 后缀，例如：
  - `osq_lock_[k]` - kernel 函数
  - `__mutex_lock.isra.7_[k]` - kernel 函数（带编译器优化后缀）
  - `runtime.getempty` - user 函数（无 _[k] 后缀）

Symbol 类在解析时保留这一信息，提供准确的 kernel/user 区分。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Symbol:
    """
    Structured symbol representation with kernel/user awareness.

    Attributes:
        raw_name: 原始符号名（如 `osq_lock_[k]` 或 `__mutex_lock.isra.7_[k]`）
        normalized_name: 规范化后的符号名（移除 _[k] 和编译器优化后缀）
        is_kernel: 是否为内核函数（基于原始名称的 _[k] 后缀判断）
        module: 所属模块（如 `[kernel.kallsyms]` 或 `containerd`）
    """
    raw_name: str
    normalized_name: str
    is_kernel: bool
    module: Optional[str] = None

    @classmethod
    def parse(cls, sym: str, module: Optional[str] = None) -> "Symbol":
        """
        从原始符号字符串创建 Symbol 对象。

        识别 kernel 符号的两种方法：
        1. 符号名以 `_[k]` 结尾（如 `osq_lock_[k]`）
        2. 所属 module 是 `[kernel.kallsyms]` 或包含 `kernel.kallsyms`

        Args:
            sym: 原始符号名（可能带有 _[k] 后缀）
            module: 所属模块名

        Returns:
            Symbol 对象，包含准确的 kernel/user 信息
        """
        if not sym:
            return cls(raw_name="", normalized_name="", is_kernel=False, module=module)

        raw_name = sym

        # 判断是否为 kernel 符号：
        # 1. 检查 _[k] 后缀
        # 2. 检查 module 是否为 kernel.kallsyms
        is_kernel = sym.endswith('_[k]')
        if not is_kernel and module:
            is_kernel = 'kernel.kallsyms' in module

        # 规范化名称：先移除 _[k] 后缀，再移除编译器优化后缀
        normalized = cls._normalize_kernel_symbol(sym)

        return cls(
            raw_name=raw_name,
            normalized_name=normalized,
            is_kernel=is_kernel,
            module=module
        )

    @staticmethod
    def _normalize_kernel_symbol(sym: str) -> str:
        """
        Normalize kernel symbol names by removing compiler optimizations and kernel markers.

        Rules:
        1. symbol_[k] -> symbol (remove kernel marker)
        2. symbol.isra.7_[k] -> symbol (remove .isra.N and kernel marker)
        3. symbol.isra.7 -> symbol (remove .isra.N)
        4. symbol.part.N -> symbol (remove .part.N)
        5. symbol.constprop.N -> symbol (remove .constprop.N)

        These suffixes are added by GCC/Clang compiler optimizations:
        - .isra.N: Interprocedural Scalar Replacement of Aggregates
        - .part.N: Function partial inlining
        - .constprop.N: Constant propagation
        """
        if not sym:
            return sym

        # Remove kernel marker _[k] suffix first
        if sym.endswith('_[k]'):
            sym = sym[:-4]

        # Remove compiler optimization suffixes
        # Match patterns like .isra.7, .part.3, .constprop.5
        for pattern in ['.isra.', '.part.', '.constprop.']:
            if pattern in sym:
                # Split at the first occurrence of the pattern
                sym = sym.split(pattern)[0]
                break

        return sym

    @staticmethod
    def _strip_offset(sym_with_offset: str) -> str:
        """Remove +0x... offset from symbol name"""
        if '+' in sym_with_offset:
            return sym_with_offset.split('+')[0]
        return sym_with_offset

    def __str__(self) -> str:
        return self.normalized_name

    def __repr__(self) -> str:
        return f"Symbol({self.normalized_name!r}, is_kernel={self.is_kernel})"

    def __hash__(self) -> int:
        return hash((self.normalized_name, self.is_kernel))

    def __eq__(self, other) -> bool:
        if isinstance(other, Symbol):
            return self.normalized_name == other.normalized_name and self.is_kernel == other.is_kernel
        return self.normalized_name == str(other)


class SymbolStack:
    """
    Represents a call stack as a list of Symbol objects.
    Provides convenient access to kernel/user information.
    """

    def __init__(self, symbols: list[Symbol] = None):
        self.symbols: list[Symbol] = symbols or []

    def __iter__(self):
        return iter(self.symbols)

    def __len__(self) -> int:
        return len(self.symbols)

    def __getitem__(self, index) -> Symbol:
        return self.symbols[index]

    @property
    def leaf(self) -> Optional[Symbol]:
        """获取栈顶符号（leaf function）"""
        return self.symbols[0] if self.symbols else None

    @property
    def root(self) -> Optional[Symbol]:
        """获取栈底符号（root function）"""
        return self.symbols[-1] if self.symbols else None

    @property
    def has_kernel(self) -> bool:
        """栈中是否包含 kernel 函数"""
        return any(s.is_kernel for s in self.symbols)

    @property
    def has_user(self) -> bool:
        """栈中是否包含 user 函数"""
        return any(not s.is_kernel for s in self.symbols)

    @property
    def is_leaf_kernel(self) -> bool:
        """栈顶函数是否为 kernel 函数"""
        leaf = self.leaf
        return leaf.is_kernel if leaf else False

    def get_normalized_names(self) -> list[str]:
        """获取规范化后的符号名列表"""
        return [s.normalized_name for s in self.symbols]

    def append(self, symbol: Symbol):
        """添加符号到栈"""
        self.symbols.append(symbol)

    def __repr__(self) -> str:
        return f"SymbolStack({self.get_normalized_names()!r})"
