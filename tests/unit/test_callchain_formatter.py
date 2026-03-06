#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试 - LayeredCallchainFormatter

测试分层调用链格式化器的各种功能，包括：
1. Compact 模式格式化
2. Detailed 模式格式化
3. format_collapsed 多调用链格式化
4. format_callchain_for_bottleneck 便捷函数
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dataclasses import dataclass
from typing import List, Optional


# =============================================================================
# Mock ExtractedCallchain 数据类
# =============================================================================

@dataclass(frozen=True)
class MockExtractedCallchain:
    """Mock ExtractedCallchain 用于测试"""
    target_symbol: str
    kernel_path: List[str]
    syscall_entry: Optional[str]
    user_entry_point: Optional[str]
    business_callers: List[str]
    raw_path: List[str]
    extraction_strategy: str


# =============================================================================
# 测试用例
# =============================================================================

def test_compact_mode_with_business_callers():
    """测试1: Compact 模式有业务调用链"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["__schedule", "schedule", "do_nanosleep"],
        syscall_entry="__x64_sys_nanosleep",
        user_entry_point="__GI___nanosleep",
        business_callers=["FindInTableWithLock", "InsertWithProb"],
        raw_path=[],
        extraction_strategy="kernel_penetration"
    )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    result = formatter.format(extracted, 5.50, 1)
    
    assert "FindInTableWithLock" in result, f"业务调用链应包含 FindInTableWithLock，实际: {result}"
    assert "5.50%" in result, f"应包含权重百分比 5.50%，实际: {result}"
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    assert " <- " in result, f"应使用 <- 作为分隔符，实际: {result}"
    
    print("✓ test_compact_mode_with_business_callers passed")
    return True


def test_compact_mode_without_business_callers():
    """测试2: Compact 模式无业务调用链（回退到内核路径）"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["__schedule", "schedule"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=[],
        raw_path=[],
        extraction_strategy="truncated"
    )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    result = formatter.format(extracted, 1.28, 2)
    
    assert "__schedule" in result, f"应显示内核路径 __schedule，实际: {result}"
    assert "#2" in result, f"应包含序号 #2，实际: {result}"
    assert "1.28%" in result, f"应包含权重百分比 1.28%，实际: {result}"
    
    print("✓ test_compact_mode_without_business_callers passed")
    return True


def test_detailed_mode():
    """测试3: Detailed 模式（分层展示内核/用户态）"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["__schedule", "schedule", "do_nanosleep", "hrtimer_nanosleep"],
        syscall_entry="__x64_sys_nanosleep",
        user_entry_point="__GI___nanosleep",
        business_callers=["FindInTableWithLock", "InsertWithProb", "PushVecFid", "PushModel", "PushModels"],
        raw_path=[],
        extraction_strategy="kernel_penetration"
    )
    
    formatter_detailed = LayeredCallchainFormatter(mode="detailed")
    result = formatter_detailed.format(extracted, 5.50, 3)
    
    # 检查主调用链
    assert "FindInTableWithLock" in result, f"应显示业务调用链 FindInTableWithLock，实际: {result}"
    assert "#3" in result, f"应包含序号 #3，实际: {result}"
    
    # 检查分层标签
    assert "[kernel]" in result, f"应包含 [kernel] 标签，实际: {result}"
    assert "[syscall]" in result, f"应包含 [syscall] 标签，实际: {result}"
    
    # 检查内核路径内容
    assert "__schedule" in result, f"应显示内核路径 __schedule，实际: {result}"
    assert "__x64_sys_nanosleep" in result, f"应显示系统调用入口，实际: {result}"
    
    print("✓ test_detailed_mode passed")
    return True


def test_format_collapsed():
    """测试4: format_collapsed 多调用链格式化"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted1 = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["__schedule", "schedule", "do_nanosleep"],
        syscall_entry="__x64_sys_nanosleep",
        user_entry_point="__GI___nanosleep",
        business_callers=["FindInTableWithLock", "InsertWithProb"],
        raw_path=[],
        extraction_strategy="kernel_penetration"
    )
    
    extracted2 = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["__schedule", "schedule"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=[],
        raw_path=[],
        extraction_strategy="truncated"
    )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    extractions = [
        (extracted1, 5.50),
        (extracted2, 1.28),
    ]
    result = formatter.format_collapsed(extractions, top_n=2)
    
    # 检查是否包含两个调用链的序号
    assert "#1" in result, f"应包含 #1，实际: {result}"
    assert "#2" in result, f"应包含 #2，实际: {result}"
    
    # 检查权重百分比
    assert "5.50%" in result, f"应包含 5.50%，实际: {result}"
    assert "1.28%" in result, f"应包含 1.28%，实际: {result}"
    
    print("✓ test_format_collapsed passed")
    return True


def test_format_collapsed_sorting():
    """测试5: format_collapsed 按权重排序"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted1 = MockExtractedCallchain(
        target_symbol="symbol1",
        kernel_path=["kernel1"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=["business1"],
        raw_path=[],
        extraction_strategy="standard"
    )
    
    extracted2 = MockExtractedCallchain(
        target_symbol="symbol2",
        kernel_path=["kernel2"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=["business2"],
        raw_path=[],
        extraction_strategy="standard"
    )
    
    extracted3 = MockExtractedCallchain(
        target_symbol="symbol3",
        kernel_path=["kernel3"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=["business3"],
        raw_path=[],
        extraction_strategy="standard"
    )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    
    # 故意不按权重顺序传入
    extractions = [
        (extracted2, 2.0),  # 中间权重
        (extracted3, 3.0),  # 最高权重
        (extracted1, 1.0),  # 最低权重
    ]
    
    result = formatter.format_collapsed(extractions, top_n=3)
    
    # 检查排序是否正确（应该按 3.0, 2.0, 1.0 排序）
    lines = result.split("\n")
    assert len(lines) == 3, f"应有3行，实际: {len(lines)}"
    
    # 第一行应该是权重最高的 (3.0%)
    assert "3.00%" in lines[0], f"第一行应包含 3.00%，实际: {lines[0]}"
    assert "business3" in lines[0], f"第一行应包含 business3，实际: {lines[0]}"
    
    # 第二行应该是权重中间的 (2.0%)
    assert "2.00%" in lines[1], f"第二行应包含 2.00%，实际: {lines[1]}"
    assert "business2" in lines[1], f"第二行应包含 business2，实际: {lines[1]}"
    
    # 第三行应该是权重最低的 (1.0%)
    assert "1.00%" in lines[2], f"第三行应包含 1.00%，实际: {lines[2]}"
    assert "business1" in lines[2], f"第三行应包含 business1，实际: {lines[2]}"
    
    print("✓ test_format_collapsed_sorting passed")
    return True


def test_compact_mode_no_callers():
    """测试6: Compact 模式无任何调用者"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="some_function",
        kernel_path=[],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=[],
        raw_path=[],
        extraction_strategy="empty"
    )
    
    formatter = LayeredCallchainFormatter(mode="compact")
    result = formatter.format(extracted, 0.5, 1)
    
    assert "(no callers)" in result, f"应显示 (no callers)，实际: {result}"
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    assert "0.50%" in result, f"应包含权重百分比，实际: {result}"
    
    print("✓ test_compact_mode_no_callers passed")
    return True


def test_detailed_mode_no_kernel_path():
    """测试7: Detailed 模式无内核路径"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="user_function",
        kernel_path=[],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=["caller1", "caller2"],
        raw_path=[],
        extraction_strategy="standard"
    )
    
    formatter = LayeredCallchainFormatter(mode="detailed")
    result = formatter.format(extracted, 3.33, 1)
    
    # 检查主调用链
    assert "caller1" in result, f"应显示业务调用链 caller1，实际: {result}"
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    
    # 不应显示 kernel 和 syscall 标签（因为没有数据）
    assert "[kernel]" not in result, f"不应包含 [kernel] 标签，实际: {result}"
    assert "[syscall]" not in result, f"不应包含 [syscall] 标签，实际: {result}"
    
    print("✓ test_detailed_mode_no_kernel_path passed")
    return True


def test_max_kernel_display_limit():
    """测试8: 内核路径显示层数限制"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    # 创建一个有很多层内核路径的调用链
    extracted = MockExtractedCallchain(
        target_symbol="finish_task_switch",
        kernel_path=["k1", "k2", "k3", "k4", "k5", "k6", "k7"],  # 7层内核路径
        syscall_entry="__x64_sys_test",
        user_entry_point="__GI___test",
        business_callers=["business1"],
        raw_path=[],
        extraction_strategy="kernel_penetration"
    )
    
    # 使用 max_kernel_display=3
    formatter = LayeredCallchainFormatter(mode="detailed", max_kernel_display=3)
    result = formatter.format(extracted, 10.0, 1)
    
    # 检查是否只显示了前3层
    assert "[kernel] k1 <- k2 <- k3" in result, f"应显示前3层内核路径，实际: {result}"
    assert "..." in result, f"应显示 ... 表示截断，实际: {result}"
    
    # 检查第4层不应该出现
    assert "k4" not in result, f"不应显示第4层内核路径 k4，实际: {result}"
    
    print("✓ test_max_kernel_display_limit passed")
    return True


def test_invalid_mode():
    """测试9: 无效的模式应该抛出 ValueError"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    try:
        LayeredCallchainFormatter(mode="invalid_mode")
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "Invalid mode" in str(e), f"错误信息应包含 'Invalid mode'，实际: {e}"
    
    print("✓ test_invalid_mode passed")
    return True


def test_format_callchain_for_bottleneck():
    """测试10: format_callchain_for_bottleneck 便捷函数"""
    from scripts.perf_toolkit.core.callchain_formatter import format_callchain_for_bottleneck
    
    stack = [
        "finish_task_switch",
        "__schedule",
        "schedule",
        "FindInTableWithLock",
        "InsertWithProb",
        "PushVecFid",
    ]
    
    result = format_callchain_for_bottleneck(
        stack, 0, "finish_task_switch", 5.50, 1
    )
    
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    assert "5.50%" in result, f"应包含权重百分比 5.50%，实际: {result}"
    assert " <- " in result, f"应使用 <- 作为分隔符，实际: {result}"
    
    print("✓ test_format_callchain_for_bottleneck passed")
    return True


def test_format_callchain_for_bottleneck_empty_stack():
    """测试11: format_callchain_for_bottleneck 空栈处理"""
    from scripts.perf_toolkit.core.callchain_formatter import format_callchain_for_bottleneck
    
    result = format_callchain_for_bottleneck(
        [], 0, "some_symbol", 1.0, 1
    )
    
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    assert "1.00%" in result, f"应包含权重百分比，实际: {result}"
    
    print("✓ test_format_callchain_for_bottleneck_empty_stack passed")
    return True


def test_format_callchain_for_bottleneck_target_at_end():
    """测试12: format_callchain_for_bottleneck 目标在栈末尾"""
    from scripts.perf_toolkit.core.callchain_formatter import format_callchain_for_bottleneck
    
    stack = ["symbol1", "symbol2", "target_symbol"]
    
    result = format_callchain_for_bottleneck(
        stack, 2, "target_symbol", 2.5, 1
    )
    
    assert "#1" in result, f"应包含序号 #1，实际: {result}"
    assert "2.50%" in result, f"应包含权重百分比，实际: {result}"
    
    print("✓ test_format_callchain_for_bottleneck_target_at_end passed")
    return True


def test_callchain_formatter_backward_compatibility():
    """测试13: 原有的 CallChainFormatter 保持向后兼容"""
    from scripts.perf_toolkit.core.callchain_formatter import CallChainFormatter, format_callchain
    
    path = ["func1", "func2", "func3"]
    
    # 测试原有的 format 方法
    result = CallChainFormatter.format(path, direction="top_down", style="plain")
    assert "func1" in result, f"应包含 func1，实际: {result}"
    assert "func2" in result, f"应包含 func2，实际: {result}"
    assert "func3" in result, f"应包含 func3，实际: {result}"
    
    # 测试便捷函数
    result2 = format_callchain(path, direction="bottom_up", style="plain")
    assert "func1" in result2, f"应包含 func1，实际: {result2}"
    
    print("✓ test_callchain_formatter_backward_compatibility passed")
    return True


def test_detailed_mode_only_kernel():
    """测试14: Detailed 模式只有内核路径没有业务调用链"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    extracted = MockExtractedCallchain(
        target_symbol="kernel_only",
        kernel_path=["k1", "k2", "k3"],
        syscall_entry=None,
        user_entry_point=None,
        business_callers=[],
        raw_path=[],
        extraction_strategy="kernel_only"
    )
    
    formatter = LayeredCallchainFormatter(mode="detailed")
    result = formatter.format(extracted, 4.44, 5)
    
    # 检查是否显示内核路径作为主路径
    assert "#5" in result, f"应包含序号 #5，实际: {result}"
    assert "k1" in result, f"应显示内核路径 k1，实际: {result}"
    assert "4.44%" in result, f"应包含权重百分比，实际: {result}"
    
    # 因为没有业务调用链，kernel 标签不应该出现（直接作为主路径显示）
    assert "[kernel]" not in result, f"不应包含 [kernel] 标签（因为内核路径就是主路径），实际: {result}"
    
    print("✓ test_detailed_mode_only_kernel passed")
    return True


# =============================================================================
# 测试运行器
# =============================================================================

def run_all_tests():
    """运行所有测试"""
    tests = [
        test_compact_mode_with_business_callers,
        test_compact_mode_without_business_callers,
        test_detailed_mode,
        test_format_collapsed,
        test_format_collapsed_sorting,
        test_compact_mode_no_callers,
        test_detailed_mode_no_kernel_path,
        test_max_kernel_display_limit,
        test_invalid_mode,
        test_format_callchain_for_bottleneck,
        test_format_callchain_for_bottleneck_empty_stack,
        test_format_callchain_for_bottleneck_target_at_end,
        test_callchain_formatter_backward_compatibility,
        test_detailed_mode_only_kernel,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 60)
    print("Running LayeredCallchainFormatter Tests")
    print("=" * 60)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} failed: {e}")
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
