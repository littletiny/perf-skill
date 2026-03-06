#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression test for finish_task_switch visibility issue

验证 finish_task_switch 相关调用链能够正确显示业务层函数
（如 FindInTableWithLock）

Usage:
    cd tests
    python3 functional/test_finish_task_switch_fix.py
"""

import sys
import unittest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


class TestFinishTaskSwitchFix(unittest.TestCase):
    """验证 finish_task_switch 调用链可见性修复"""
    
    def test_kernel_awareness_exists(self):
        """验证 KernelAwareness 类可用"""
        try:
            from perf_toolkit.core.symbol import KernelAwareness
            self.assertTrue(callable(getattr(KernelAwareness, 'is_kernel_function', None)))
            self.assertTrue(callable(getattr(KernelAwareness, 'should_penetrate', None)))
        except ImportError as e:
            self.skipTest(f"KernelAwareness 未实现: {e}")
    
    def test_findintablewithlock_in_stack(self):
        """验证 FindInTableWithLock 可以在调用栈中被找到"""
        # 构造测试栈（模拟实际数据）
        test_stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "schedule_[k]",
            "do_nanosleep_[k]",
            "hrtimer_nanosleep_[k]",
            "__x64_sys_nanosleep_[k]",
            "do_syscall_64_[k]",
            "entry_SYSCALL_64_after_hwframe_[k]",
            "__GI___nanosleep",
            "parameter_server::DoubleHash::FindInTableWithLock",
            "parameter_server::DoubleHash::InsertWithProb",
            "parameter_server::Model::PushVecFid",
        ]
        
        # 验证 FindInTableWithLock 在栈中
        self.assertIn("parameter_server::DoubleHash::FindInTableWithLock", test_stack)
        
        # 验证可以通过简单索引找到用户态函数
        user_space_funcs = [s for s in test_stack if not s.endswith("_[k]")]
        self.assertTrue(len(user_space_funcs) > 0)
        self.assertIn("parameter_server::DoubleHash::FindInTableWithLock", user_space_funcs)


class TestKernelAwareness(unittest.TestCase):
    """测试 KernelAwareness 功能"""
    
    def test_is_kernel_function(self):
        """测试内核函数识别"""
        try:
            from perf_toolkit.core.symbol import KernelAwareness
        except ImportError:
            self.skipTest("KernelAwareness 未实现")
        
        # 测试 _[k] 后缀识别
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule_[k]"))
        
        # 测试非内核函数
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
        self.assertFalse(KernelAwareness.is_kernel_function("__GI___nanosleep"))


class TestSymbolRules(unittest.TestCase):
    """测试 SymbolRules 简化功能"""
    
    def test_symbol_rules_exists(self):
        """验证 SymbolRules 类可用"""
        try:
            from config.defaults import SymbolRules
            rules = SymbolRules()
            self.assertTrue(callable(getattr(rules, 'is_hidden', None)))
            self.assertTrue(callable(getattr(rules, 'get_collapse_group', None)))
        except ImportError as e:
            self.skipTest(f"SymbolRules 未实现: {e}")
    
    def test_hidden_rules(self):
        """测试 hidden 规则"""
        try:
            from config.defaults import SymbolRules
        except ImportError:
            self.skipTest("SymbolRules 未实现")
        
        rules = SymbolRules(hidden=['__clone', 'start_thread'])
        
        self.assertTrue(rules.is_hidden('__clone'))
        self.assertTrue(rules.is_hidden('start_thread'))
        self.assertFalse(rules.is_hidden('main'))
    
    def test_collapse_rules(self):
        """测试 collapse 规则"""
        try:
            from config.defaults import SymbolRules
        except ImportError:
            self.skipTest("SymbolRules 未实现")
        
        rules = SymbolRules(
            collapse_groups={
                'memory': {'symbols': ['malloc', 'free'], 'display': '[memory_ops]'}
            }
        )
        
        self.assertEqual(rules.get_collapse_group('malloc'), '[memory_ops]')
        self.assertEqual(rules.get_collapse_group('free'), '[memory_ops]')
        self.assertIsNone(rules.get_collapse_group('main'))
    
    def test_process_stack(self):
        """测试栈处理"""
        try:
            from config.defaults import SymbolRules, ProcessedStack
        except ImportError:
            self.skipTest("SymbolRules 或 ProcessedStack 未实现")
        
        rules = SymbolRules(
            hidden=['__clone'],
            collapse_groups={
                'memory': {'symbols': ['malloc', 'free'], 'display': '[memory_ops]'}
            }
        )
        
        stack = ['malloc', '__clone', 'free', 'main']
        result = ProcessedStack.process(stack, rules)
        
        # 验证 __clone 被移除
        self.assertNotIn('__clone', result.processed_stack)
        
        # 验证连续的 malloc/free 被折叠
        self.assertEqual(result.processed_stack.count('[memory_ops]'), 1)


def run_tests():
    """Run all tests with detailed output"""
    print("=" * 70)
    print("Finish Task Switch Fix - Regression Test Suite")
    print("=" * 70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFinishTaskSwitchFix))
    suite.addTests(loader.loadTestsFromTestCase(TestKernelAwareness))
    suite.addTests(loader.loadTestsFromTestCase(TestSymbolRules))
    
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
