#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试 - LayeredCallchainFormatter（简化版）

测试核心功能：
1. Compact/Detailed 模式格式化
2. format_collapsed 多调用链格式化
3. 权重排序
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_compact_mode():
    """Compact 模式"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    callers = ["FindInTableWithLock", "InsertWithProb"]
    
    formatter = LayeredCallchainFormatter(mode="compact")
    result = formatter.format_callers(callers, 5.50, 1)
    
    assert "FindInTableWithLock" in result, f"应包含调用链: {result}"
    assert "5.50%" in result and "#1" in result, f"应包含权重和序号: {result}"
    print("✓ test_compact_mode passed")
    return True


def test_detailed_mode():
    """Detailed 模式"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    callers = ["FindInTableWithLock", "InsertWithProb"]
    
    formatter = LayeredCallchainFormatter(mode="detailed")
    result = formatter.format_callers(callers, 5.50, 1)
    
    assert "FindInTableWithLock" in result, f"应显示调用链: {result}"
    print("✓ test_detailed_mode passed")
    return True


def test_format_collapsed():
    """多调用链格式化"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    formatter = LayeredCallchainFormatter(mode="compact")
    
    # 新接口：(callers_list, weight_percent) 元组列表
    extractions = [
        (["c1", "c2"], 5.50),
        (["c3", "c4"], 1.28),
    ]
    result = formatter.format_collapsed(extractions, top_n=2)
    
    assert "#1" in result and "#2" in result, f"应包含序号: {result}"
    assert "5.50%" in result, f"应包含 5.50%: {result}"
    print("✓ test_format_collapsed passed")
    return True


def test_format_collapsed_sorting():
    """按权重排序"""
    from scripts.perf_toolkit.core.callchain_formatter import LayeredCallchainFormatter
    
    formatter = LayeredCallchainFormatter(mode="compact")
    
    extractions = [
        (["b2"], 2.0),
        (["b3"], 3.0),
        (["b1"], 1.0),
    ]
    
    result = formatter.format_collapsed(extractions, top_n=3)
    lines = result.split("\n")
    
    assert "3.00%" in lines[0], "第一行应是最高权重"
    assert "1.00%" in lines[2], "最后一行应是最低权重"
    print("✓ test_format_collapsed_sorting passed")
    return True


def test_format_callchain_for_bottleneck():
    """format_callchain_for_bottleneck 便捷函数"""
    from scripts.perf_toolkit.core.callchain_formatter import format_callchain_for_bottleneck
    
    stack = ["finish_task_switch", "__schedule", "FindInTableWithLock"]
    result = format_callchain_for_bottleneck(stack, 0, "finish_task_switch", 5.50, 1)
    
    assert "#1" in result and "5.50%" in result, f"应包含序号和权重: {result}"
    print("✓ test_format_callchain_for_bottleneck passed")
    return True


def test_backward_compatibility():
    """CallChainFormatter 向后兼容"""
    from scripts.perf_toolkit.core.callchain_formatter import CallChainFormatter, format_callchain
    
    path = ["func1", "func2", "func3"]
    
    result = CallChainFormatter.format(path, direction="top_down", style="plain")
    assert "func1" in result, f"应包含函数名: {result}"
    
    result2 = format_callchain(path, direction="bottom_up", style="plain")
    assert "func1" in result2, f"应包含 func1: {result2}"
    print("✓ test_backward_compatibility passed")
    return True


def run_all_tests():
    """运行所有测试"""
    tests = [
        test_compact_mode,
        test_detailed_mode,
        test_format_collapsed,
        test_format_collapsed_sorting,
        test_format_callchain_for_bottleneck,
        test_backward_compatibility,
    ]
    
    passed = failed = 0
    
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
