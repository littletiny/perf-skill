#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Symbol Processor and Kernel Awareness

测试覆盖：
1. SymbolRules 模式匹配 (hidden, collapse)
2. ProcessedStack 栈处理
3. KernelAwareness 内核函数识别
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from config.defaults import SymbolRules, ProcessedStack
from perf_toolkit.core.symbol import KernelAwareness


class TestSymbolRules(unittest.TestCase):
    """测试 SymbolRules 模式匹配"""
    
    def test_hidden_exact_match(self):
        """精确匹配 hidden"""
        rules = SymbolRules(hidden=["exact_symbol"])
        self.assertTrue(rules.is_hidden("exact_symbol"))
        self.assertFalse(rules.is_hidden("exact_symbol_2"))
    
    def test_hidden_wildcard(self):
        """通配符匹配 hidden"""
        rules = SymbolRules(hidden=["__clone*", "*thread*"])
        self.assertTrue(rules.is_hidden("__clone"))
        self.assertTrue(rules.is_hidden("__clone3"))
        self.assertTrue(rules.is_hidden("start_thread"))
        self.assertFalse(rules.is_hidden("main"))


class TestProcessedStack(unittest.TestCase):
    """测试 ProcessedStack 处理"""
    
    def test_remove_hidden(self):
        """移除 hidden 符号"""
        rules = SymbolRules(hidden=["__clone", "start_thread"])
        stack = ["main", "pthread_create", "start_thread", "__clone"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main", "pthread_create"])
        self.assertEqual(processed.hidden_count, 2)
    
    def test_collapse_group(self):
        """折叠符号组"""
        rules = SymbolRules(
            collapse_groups={
                "memory": {"symbols": ["malloc", "free"], "display": "[memory_ops]"}
            }
        )
        stack = ["start", "malloc", "free", "end"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["start", "[memory_ops]", "end"])
        self.assertEqual(processed.collapsed_count, 2)
    
    def test_normalize(self):
        """符号名规范化"""
        rules = SymbolRules()
        stack = ["ns1::ns2::Class1::method1", "plain_func"]
        processed = ProcessedStack.process(stack, rules, normalize=True)
        
        self.assertEqual(processed.processed_stack, ["Class1::method1", "plain_func"])


class TestKernelAwareness(unittest.TestCase):
    """测试 KernelAwareness 内核函数识别"""
    
    def test_is_kernel_with_suffix(self):
        """_[k] 后缀识别内核函数"""
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule_[k]"))
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
    
    def test_is_kernel_with_prefix(self):
        """前缀识别内核函数"""
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule"))
        self.assertTrue(KernelAwareness.is_kernel_function("__x64_sys_nanosleep"))
        self.assertFalse(KernelAwareness.is_kernel_function("main"))
    
    def test_should_penetrate_whitelist(self):
        """白名单穿透判断"""
        should_pen, reason = KernelAwareness.should_penetrate("finish_task_switch")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "in_whitelist")
    
    def test_should_penetrate_schedule_related(self):
        """调度相关函数穿透"""
        should_pen, reason = KernelAwareness.should_penetrate("io_schedule")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "schedule_related")
    
    def test_should_not_penetrate(self):
        """普通函数不穿透"""
        should_pen, reason = KernelAwareness.should_penetrate("FindInTableWithLock")
        self.assertFalse(should_pen)
        self.assertEqual(reason, "")
    
    def test_find_user_entry_point(self):
        """查找用户态入口点"""
        stack = ["finish_task_switch", "__schedule", "__GI___nanosleep", "main"]
        idx = KernelAwareness.find_user_entry_point(stack, 0)
        self.assertEqual(idx, 2)
        self.assertEqual(stack[idx], "__GI___nanosleep")


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_real_world_stack(self):
        """真实场景调用栈处理"""
        rules = SymbolRules(
            hidden=["__clone", "start_thread", "execute_native_thread_routine"],
        )
        stack = [
            "worker", "execute_native_thread_routine", "start_thread",
            "pthread_create", "main", "__libc_start_main"
        ]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["worker", "pthread_create", "main"])
        self.assertEqual(processed.hidden_count, 3)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestSymbolRules,
        TestProcessedStack,
        TestKernelAwareness,
        TestIntegration,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
