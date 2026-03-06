#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Symbol Processor - 符号处理器的单元测试

测试覆盖：
1. SymbolRules 类的模式匹配
2. ProcessedStack 的栈处理逻辑
3. hidden/merge_up/merge_down/collapse 规则
4. 通配符模式匹配
"""

import sys
import unittest
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import SymbolRules, ProcessedStack, StackOperation


class TestSymbolRulesPatternMatching(unittest.TestCase):
    """测试 SymbolRules 的模式匹配功能"""
    
    def test_exact_match(self):
        """测试精确匹配"""
        rules = SymbolRules(hidden=["exact_symbol"])
        self.assertTrue(rules.is_hidden("exact_symbol"))
        self.assertFalse(rules.is_hidden("exact_symbol_2"))
    
    def test_wildcard_star(self):
        """测试 * 通配符"""
        rules = SymbolRules(hidden=["__clone*"])
        self.assertTrue(rules.is_hidden("__clone"))
        self.assertTrue(rules.is_hidden("__clone3"))
        self.assertTrue(rules.is_hidden("__clone_internal"))
        self.assertFalse(rules.is_hidden("clone"))
    
    def test_wildcard_question(self):
        """测试 ? 通配符"""
        rules = SymbolRules(hidden=["symbol_?"])
        self.assertTrue(rules.is_hidden("symbol_a"))
        self.assertTrue(rules.is_hidden("symbol_1"))
        self.assertFalse(rules.is_hidden("symbol_ab"))
    
    def test_wildcard_sequence(self):
        """测试 [seq] 通配符"""
        rules = SymbolRules(hidden=["symbol_[abc]"])
        self.assertTrue(rules.is_hidden("symbol_a"))
        self.assertTrue(rules.is_hidden("symbol_b"))
        self.assertFalse(rules.is_hidden("symbol_d"))


class TestSymbolRulesMerge(unittest.TestCase):
    """测试 merge_up 和 merge_down 规则"""
    
    def test_should_merge_up(self):
        """测试向上合并检测"""
        rules = SymbolRules(merge_up=["__libc_start_main", "pthread_create*"])
        self.assertTrue(rules.should_merge_up("__libc_start_main"))
        self.assertTrue(rules.should_merge_up("pthread_create"))
        self.assertTrue(rules.should_merge_up("pthread_create_2_1"))
        self.assertFalse(rules.should_merge_up("main"))
    
    def test_should_merge_down(self):
        """测试向下合并检测"""
        rules = SymbolRules(merge_down=["syscall", "__x64_sys_*"])
        self.assertTrue(rules.should_merge_down("syscall"))
        self.assertTrue(rules.should_merge_down("__x64_sys_read"))
        self.assertTrue(rules.should_merge_down("__x64_sys_nanosleep"))
        self.assertFalse(rules.should_merge_down("read"))


class TestSymbolRulesCollapse(unittest.TestCase):
    """测试 collapse 组折叠功能"""
    
    def test_get_collapse_group(self):
        """测试获取折叠组"""
        rules = SymbolRules(
            collapse_groups={
                "memory": {
                    "symbols": ["malloc", "free"],
                    "display": "[memory_ops]"
                }
            }
        )
        self.assertEqual(rules.get_collapse_group("malloc"), "[memory_ops]")
        self.assertEqual(rules.get_collapse_group("free"), "[memory_ops]")
        self.assertIsNone(rules.get_collapse_group("calloc"))
    
    def test_collapse_wildcard(self):
        """测试折叠组通配符"""
        rules = SymbolRules(
            collapse_groups={
                "syscall": {
                    "symbols": ["__x64_sys_*"],
                    "display": "[syscall]"
                }
            }
        )
        self.assertEqual(rules.get_collapse_group("__x64_sys_read"), "[syscall]")
        self.assertEqual(rules.get_collapse_group("__x64_sys_write"), "[syscall]")


class TestProcessedStackHidden(unittest.TestCase):
    """测试 hidden 处理"""
    
    def test_remove_hidden_symbols(self):
        """测试移除 hidden 符号"""
        rules = SymbolRules(hidden=["__clone", "start_thread"])
        stack = ["main", "pthread_create", "start_thread", "__clone"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(len(processed.processed_stack), 2)
        self.assertEqual(processed.processed_stack, ["main", "pthread_create"])
        self.assertEqual(processed.hidden_count, 2)
    
    def test_hidden_with_wildcard(self):
        """测试带通配符的 hidden"""
        rules = SymbolRules(hidden=["*thread*"])
        stack = ["main", "start_thread", "worker_thread", "cleanup"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main", "cleanup"])
        self.assertEqual(processed.hidden_count, 2)


class TestProcessedStackMergeUp(unittest.TestCase):
    """测试 merge_up 处理"""
    
    def test_merge_up_with_caller(self):
        """测试向上合并到有调用者的情况"""
        rules = SymbolRules(merge_up=["__libc_start_main"])
        stack = ["main", "__libc_start_main"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main"])
        self.assertEqual(processed.merged_up_count, 1)
    
    def test_merge_up_no_caller(self):
        """测试向上合并但无调用者的情况（保留原位）"""
        rules = SymbolRules(merge_up=["__libc_start_main"])
        stack = ["__libc_start_main"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["__libc_start_main"])


class TestProcessedStackMergeDown(unittest.TestCase):
    """测试 merge_down 处理"""
    
    def test_merge_down_with_callee(self):
        """测试向下合并到有被调用者的情况"""
        rules = SymbolRules(merge_down=["syscall"])
        stack = ["main", "syscall", "read"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main", "read"])
        self.assertEqual(processed.merged_down_count, 1)
    
    def test_merge_down_chain(self):
        """测试连续的 merge_down 链"""
        rules = SymbolRules(merge_down=["syscall", "entry_SYSCALL_*"])
        stack = ["main", "syscall", "entry_SYSCALL_64", "read"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main", "read"])
        self.assertEqual(processed.merged_down_count, 2)


class TestProcessedStackCollapse(unittest.TestCase):
    """测试 collapse 处理"""
    
    def test_collapse_consecutive(self):
        """测试连续符号的折叠"""
        rules = SymbolRules(
            collapse_groups={
                "test": {
                    "symbols": ["a", "b", "c"],
                    "display": "[group]"
                }
            }
        )
        stack = ["start", "a", "b", "c", "end"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["start", "[group]", "end"])
        self.assertEqual(processed.collapsed_count, 3)
    
    def test_collapse_single(self):
        """测试单个符号的折叠"""
        rules = SymbolRules(
            collapse_groups={
                "test": {
                    "symbols": ["middle"],
                    "display": "[middle]"
                }
            }
        )
        stack = ["start", "middle", "end"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["start", "[middle]", "end"])
    
    def test_collapse_non_consecutive(self):
        """测试非连续符号的折叠（应产生多个折叠组）"""
        rules = SymbolRules(
            collapse_groups={
                "test": {
                    "symbols": ["a"],
                    "display": "[A]"
                }
            }
        )
        stack = ["a", "middle", "a"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["[A]", "middle", "[A]"])


class TestProcessedStackCombined(unittest.TestCase):
    """测试组合规则处理"""
    
    def test_all_rules_combined(self):
        """测试所有规则的组合效果"""
        rules = SymbolRules(
            hidden=["__clone"],
            merge_up=["__libc_start_main"],
            merge_down=["syscall"],
            collapse_groups={
                "memory": {
                    "symbols": ["malloc", "free"],
                    "display": "[mem]"
                }
            }
        )
        stack = [
            "main",
            "__libc_start_main",
            "malloc",
            "syscall",
            "read",
            "free",
            "__clone"
        ]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["main", "[mem]", "read", "[mem]"])
        self.assertEqual(processed.hidden_count, 1)
        self.assertEqual(processed.merged_up_count, 1)
        self.assertEqual(processed.merged_down_count, 1)
        self.assertEqual(processed.collapsed_count, 2)


class TestProcessedStackOperations(unittest.TestCase):
    """测试操作记录功能"""
    
    def test_operations_recorded(self):
        """测试操作被正确记录"""
        rules = SymbolRules(hidden=["hidden_sym"])
        stack = ["visible", "hidden_sym"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(len(processed.operations), 1)
        op = processed.operations[0]
        self.assertEqual(op.operation, "hidden")
        self.assertEqual(op.original_symbol, "hidden_sym")
        self.assertIsNone(op.new_symbol)
    
    def test_get_summary(self):
        """测试摘要生成功能"""
        rules = SymbolRules(hidden=["a"], merge_up=["b"])
        stack = ["main", "b", "a"]
        processed = ProcessedStack.process(stack, rules)
        
        summary = processed.get_summary()
        self.assertIn("1 hidden", summary)
        self.assertIn("1 merged_up", summary)
        self.assertIn("3 -> 1 symbols", summary)


class TestSymbolNormalization(unittest.TestCase):
    """测试符号名规范化功能"""
    
    def test_normalize_simple(self):
        """测试简单规范化"""
        self.assertEqual(
            SymbolRules.normalize_symbol("MyClass::method"),
            "MyClass::method"
        )
    
    def test_normalize_long_namespace(self):
        """测试长命名空间规范化"""
        self.assertEqual(
            SymbolRules.normalize_symbol("a::b::c::d::MyClass::method"),
            "c::d::MyClass::method"  # 最后两部分，包含类名和方法
        )
    
    def test_normalize_no_namespace(self):
        """测试无命名空间符号不变化"""
        self.assertEqual(
            SymbolRules.normalize_symbol("plain_function"),
            "plain_function"
        )
    
    def test_normalize_collapse_marker(self):
        """测试折叠组标记不变化"""
        self.assertEqual(
            SymbolRules.normalize_symbol("[syscall]"),
            "[syscall]"
        )
    
    def test_normalize_in_process_stack(self):
        """测试 process_stack 默认应用规范化"""
        rules = SymbolRules()
        stack = ["ns1::ns2::Class1::method1", "ns1::ns2::Class2::method2"]
        processed = ProcessedStack.process(stack, rules)
        
        # 默认启用 normalize
        self.assertEqual(processed.processed_stack, ["Class1::method1", "Class2::method2"])
    
    def test_normalize_disabled(self):
        """测试禁用规范化"""
        rules = SymbolRules()
        stack = ["ns1::ns2::Class1::method1", "ns1::ns2::Class2::method2"]
        processed = ProcessedStack.process(stack, rules, normalize=False)
        
        # 禁用 normalize，保持原始名称
        self.assertEqual(processed.processed_stack, ["ns1::ns2::Class1::method1", "ns1::ns2::Class2::method2"])


class TestRealWorldScenarios(unittest.TestCase):
    """测试真实场景"""
    
    def test_pthread_creation_path(self):
        """测试线程创建路径"""
        rules = SymbolRules(
            hidden=["__clone", "start_thread", "execute_native_thread_routine"],
            merge_up=["__libc_start_main", "pthread_create"]
        )
        stack = ["worker", "execute_native_thread_routine", "start_thread", 
                  "pthread_create", "main", "__libc_start_main"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["worker", "main"])
    
    def test_syscall_path(self):
        """测试系统调用路径"""
        rules = SymbolRules(
            merge_down=["syscall", "__x64_sys_*", "do_syscall_64", "entry_SYSCALL_*"],
            collapse_groups={
                "syscall": {
                    "symbols": ["__x64_sys_*"],
                    "display": "[syscall]"
                }
            }
        )
        stack = ["read_data", "syscall", "entry_SYSCALL_64", "do_syscall_64", 
                  "__x64_sys_read", "vfs_read"]
        processed = ProcessedStack.process(stack, rules)
        
        self.assertEqual(processed.processed_stack, ["read_data", "vfs_read"])
    
    def test_memory_allocation_path(self):
        """测试内存分配路径 - 连续的内存操作被折叠"""
        rules = SymbolRules(
            collapse_groups={
                "memory": {
                    "symbols": ["malloc", "free", "calloc"],
                    "display": "[memory_ops]"
                }
            }
        )
        # 场景：连续的内存操作被折叠为一个标记
        stack = ["process", "malloc", "free", "calloc", "use_data"]
        processed = ProcessedStack.process(stack, rules)
        
        # malloc, free, calloc 是连续的，被折叠为 [memory_ops]
        self.assertEqual(processed.processed_stack, ["process", "[memory_ops]", "use_data"])
    
    def test_cpp_long_namespace(self):
        """测试 C++ 长命名空间处理"""
        rules = SymbolRules(
            merge_down=["std::this_thread::__sleep_for"],
            hidden=["execute_native_thread_routine", "start_thread", "__clone"],
            merge_up=["__libc_start_main", "pthread_create"]
        )
        stack = [
            "MyApplication::Core::Engine::RenderSystem::GraphicsDevice::Present",
            "std::this_thread::__sleep_for",
            "std::this_thread::sleep_for",
            "main",
            "__libc_start_main"
        ]
        processed = ProcessedStack.process(stack, rules)
        
        # GraphicsDevice::Present (normalize 后的最后两部分: ClassName::method)
        # this_thread::sleep_for (normalize 后，__sleep_for 被 merge_down)
        # main
        self.assertEqual(processed.processed_stack, ["GraphicsDevice::Present", "this_thread::sleep_for", "main"])


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestSymbolRulesPatternMatching,
        TestSymbolRulesMerge,
        TestSymbolRulesCollapse,
        TestProcessedStackHidden,
        TestProcessedStackMergeUp,
        TestProcessedStackMergeDown,
        TestProcessedStackCollapse,
        TestProcessedStackCombined,
        TestProcessedStackOperations,
        TestRealWorldScenarios,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
