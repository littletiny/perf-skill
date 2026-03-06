#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Kernel Awareness

测试 KernelAwareness 类的核心功能:
1. is_kernel_function - 内核函数识别
2. should_penetrate - 穿透策略判断
3. find_user_entry_point - 用户态入口点查找

Usage:
    cd tests
    python3 test_kernel_awareness.py
"""

import sys
import unittest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from perf_toolkit.core.symbol import KernelAwareness


class TestKernelAwareness(unittest.TestCase):
    """Test KernelAwareness functionality"""
    
    def test_01_is_kernel_function_with_k_suffix(self):
        """Test: 名称以 _[k] 结尾的是内核函数"""
        print("\n[Test 01] Kernel function detection with _[k] suffix")
        
        # 带 _[k] 后缀的内核函数
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("osq_lock_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("__mutex_lock.isra.7_[k]"))
        
        # 不带 _[k] 后缀的用户函数
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
        self.assertFalse(KernelAwareness.is_kernel_function("InsertWithProb"))
        
        print("  ✓ _[k] suffix detection works")
    
    def test_02_is_kernel_function_with_module(self):
        """Test: module 包含 kernel.kallsyms 的是内核函数"""
        print("\n[Test 02] Kernel function detection with module")
        
        # module 包含 kernel.kallsyms
        self.assertTrue(KernelAwareness.is_kernel_function(
            "finish_task_switch", 
            module="[kernel.kallsyms]"
        ))
        self.assertTrue(KernelAwareness.is_kernel_function(
            "__schedule",
            module="[kernel.kallsyms]"
        ))
        
        # module 不包含 kernel.kallsyms
        self.assertFalse(KernelAwareness.is_kernel_function(
            "FindInTableWithLock",
            module="parameter_serve"
        ))
        
        print("  ✓ Module-based detection works")
    
    def test_03_is_kernel_function_with_prefix(self):
        """Test: 名称匹配已知内核前缀"""
        print("\n[Test 03] Kernel function detection with prefix")
        
        # 调度相关前缀
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule"))
        self.assertTrue(KernelAwareness.is_kernel_function("schedule"))
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch"))
        
        # 系统调用前缀
        self.assertTrue(KernelAwareness.is_kernel_function("__x64_sys_nanosleep"))
        self.assertTrue(KernelAwareness.is_kernel_function("do_syscall_64"))
        self.assertTrue(KernelAwareness.is_kernel_function("entry_SYSCALL_64_after_hwframe"))
        
        # 锁相关前缀
        self.assertTrue(KernelAwareness.is_kernel_function("_raw_spin_lock"))
        self.assertTrue(KernelAwareness.is_kernel_function("mutex_lock"))
        
        # 用户函数
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
        self.assertFalse(KernelAwareness.is_kernel_function("main"))
        self.assertFalse(KernelAwareness.is_kernel_function("PushModel"))
        
        print("  ✓ Prefix-based detection works")
    
    def test_04_is_kernel_function_edge_cases(self):
        """Test: 边界情况"""
        print("\n[Test 04] Edge cases for is_kernel_function")
        
        # 空字符串
        self.assertFalse(KernelAwareness.is_kernel_function(""))
        
        # None 会被 str() 处理，这里测试空字符串即可
        
        print("  ✓ Edge cases handled")
    
    def test_05_should_penetrate_whitelist(self):
        """Test: 白名单中的函数需要穿透"""
        print("\n[Test 05] Penetration whitelist")
        
        # 白名单中的函数
        result, reason = KernelAwareness.should_penetrate("finish_task_switch")
        self.assertTrue(result)
        self.assertEqual(reason, "in_whitelist")
        
        result, reason = KernelAwareness.should_penetrate("__schedule")
        self.assertTrue(result)
        self.assertEqual(reason, "in_whitelist")
        
        result, reason = KernelAwareness.should_penetrate("schedule")
        self.assertTrue(result)
        self.assertEqual(reason, "in_whitelist")
        
        print("  ✓ Whitelist penetration works")
    
    def test_06_should_penetrate_schedule_related(self):
        """Test: 调度相关函数需要穿透"""
        print("\n[Test 06] Schedule-related penetration")
        
        # 调度相关但不在白名单中的函数（注意：do_nanosleep, hrtimer_nanosleep 等在白名单中）
        result, reason = KernelAwareness.should_penetrate("native_safe_halt")
        self.assertTrue(result)
        # native_safe_halt 在白名单中，所以返回 in_whitelist
        self.assertEqual(reason, "in_whitelist")
        
        # 不在白名单但调度相关的函数
        result, reason = KernelAwareness.should_penetrate("sleep_on_page")
        self.assertTrue(result)
        self.assertEqual(reason, "schedule_related")
        
        result, reason = KernelAwareness.should_penetrate("io_schedule")
        self.assertTrue(result)
        self.assertEqual(reason, "schedule_related")
        
        result, reason = KernelAwareness.should_penetrate("switch_to")
        self.assertTrue(result)
        self.assertEqual(reason, "schedule_related")
        
        print("  ✓ Schedule-related detection works")
    
    def test_07_should_not_penetrate(self):
        """Test: 普通函数不需要穿透"""
        print("\n[Test 07] No penetration for normal functions")
        
        # 普通用户函数
        result, reason = KernelAwareness.should_penetrate("FindInTableWithLock")
        self.assertFalse(result)
        self.assertEqual(reason, "")
        
        result, reason = KernelAwareness.should_penetrate("InsertWithProb")
        self.assertFalse(result)
        self.assertEqual(reason, "")
        
        result, reason = KernelAwareness.should_penetrate("PushModel")
        self.assertFalse(result)
        self.assertEqual(reason, "")
        
        print("  ✓ Normal function non-penetration works")
    
    def test_08_find_user_entry_point(self):
        """Test: 查找用户态入口点"""
        print("\n[Test 08] Find user entry point")
        
        # 标准调用栈
        stack = [
            "finish_task_switch",
            "__schedule",
            "schedule",
            "do_nanosleep",
            "hrtimer_nanosleep",
            "__x64_sys_nanosleep",
            "do_syscall_64",
            "entry_SYSCALL_64_after_hwframe",
            "__GI___nanosleep",
            "FindInTableWithLock",
            "InsertWithProb",
        ]
        
        # 从 finish_task_switch (索引 0) 开始查找
        idx = KernelAwareness.find_user_entry_point(stack, 0)
        self.assertEqual(idx, 8)  # __GI___nanosleep 的索引
        self.assertEqual(stack[idx], "__GI___nanosleep")
        
        print("  ✓ User entry point found correctly")
    
    def test_09_find_user_entry_point_different_start(self):
        """Test: 从不同起始位置查找用户态入口点"""
        print("\n[Test 09] Find user entry point from different start")
        
        stack = [
            "finish_task_switch",
            "__schedule",
            "__GI___nanosleep",
            "FindInTableWithLock",
            "InsertWithProb",
        ]
        
        # 从 __schedule (索引 1) 开始查找
        idx = KernelAwareness.find_user_entry_point(stack, 1)
        self.assertEqual(idx, 2)  # __GI___nanosleep 的索引
        
        # 从 __GI___nanosleep (索引 2) 开始查找
        idx = KernelAwareness.find_user_entry_point(stack, 2)
        self.assertEqual(idx, 3)  # FindInTableWithLock 的索引
        
        print("  ✓ Different start positions work")
    
    def test_10_find_user_entry_point_not_found(self):
        """Test: 找不到用户态入口点"""
        print("\n[Test 10] User entry point not found")
        
        # 全是内核函数的栈
        stack = [
            "finish_task_switch",
            "__schedule",
            "schedule",
        ]
        
        idx = KernelAwareness.find_user_entry_point(stack, 0)
        self.assertIsNone(idx)
        
        print("  ✓ Returns None when user entry not found")
    
    def test_11_find_user_entry_point_edge_cases(self):
        """Test: 边界情况"""
        print("\n[Test 11] Edge cases for find_user_entry_point")
        
        # 空栈
        idx = KernelAwareness.find_user_entry_point([], 0)
        self.assertIsNone(idx)
        
        # 无效的起始索引
        stack = ["finish_task_switch", "__schedule"]
        idx = KernelAwareness.find_user_entry_point(stack, -1)
        self.assertIsNone(idx)
        
        idx = KernelAwareness.find_user_entry_point(stack, 10)
        self.assertIsNone(idx)
        
        # 起始索引在栈末尾
        stack = ["finish_task_switch", "FindInTableWithLock"]
        idx = KernelAwareness.find_user_entry_point(stack, 1)
        self.assertIsNone(idx)
        
        print("  ✓ Edge cases handled")
    
    def test_12_integration_example(self):
        """Test: 集成示例 - 完整调用链分析"""
        print("\n[Test 12] Integration example")
        
        # 实际场景调用栈
        stack = [
            "finish_task_switch",
            "__schedule",
            "__GI___nanosleep",
            "FindInTableWithLock",
            "InsertWithProb",
            "PushVecFid",
            "PushModel",
        ]
        
        # 1. 判断是否为内核函数
        self.assertTrue(KernelAwareness.is_kernel_function(stack[0]))
        
        # 2. 判断是否需要穿透
        should_pen, reason = KernelAwareness.should_penetrate(stack[0])
        self.assertTrue(should_pen)
        self.assertEqual(reason, "in_whitelist")
        
        # 3. 查找用户态入口点
        user_idx = KernelAwareness.find_user_entry_point(stack, 0)
        self.assertEqual(user_idx, 2)  # __GI___nanosleep
        
        # 4. 提取业务调用链
        business_callers = stack[user_idx+1:]  # FindInTableWithLock, InsertWithProb, ...
        self.assertEqual(business_callers[0], "FindInTableWithLock")
        
        print("  ✓ Integration example passes")


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("Kernel Awareness Test Suite")
    print("=" * 70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestKernelAwareness))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
