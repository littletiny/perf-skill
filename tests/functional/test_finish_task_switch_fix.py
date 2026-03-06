#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 finish_task_switch 调用链截断问题修复

验证点：
1. finish_task_switch 的调用链能正确显示 FindInTableWithLock
2. 内核穿透模式正常工作
3. 不影响普通函数的调用链提取

Author: Developer D (Integration & Testing)
"""

import unittest
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DATA_FILE = Path(__file__).parent.parent / "data/new_format/ps.data"


class TestFinishTaskSwitchFix(unittest.TestCase):
    """测试 finish_task_switch 调用链修复"""
    
    @classmethod
    def setUpClass(cls):
        """加载测试数据"""
        try:
            from scripts.perf_toolkit.core.engine import PerfExpertEngine
            cls.engine = PerfExpertEngine()
            if DATA_FILE.exists():
                cls.samples = cls.engine.load_samples(str(DATA_FILE))
            else:
                cls.samples = []
                print(f"警告: 测试数据文件不存在: {DATA_FILE}")
        except Exception as e:
            print(f"加载引擎失败: {e}")
            cls.engine = None
            cls.samples = []
    
    def test_kernel_awareness_exists(self):
        """验证 KernelAwareness 类可用"""
        try:
            from scripts.perf_toolkit.core.symbol import KernelAwareness
            self.assertTrue(hasattr(KernelAwareness, 'is_kernel_function'))
            self.assertTrue(hasattr(KernelAwareness, 'should_penetrate'))
            self.assertTrue(hasattr(KernelAwareness, 'find_user_entry_point'))
        except ImportError as e:
            self.skipTest(f"KernelAwareness 未实现: {e}")
    
    def test_callchain_extractor_exists(self):
        """验证 CallchainExtractor 类可用"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor, ExtractedCallchain
            extractor = CallchainExtractor()
            self.assertTrue(callable(getattr(extractor, 'extract', None)))
            
            # 验证 ExtractedCallchain dataclass 有必要的字段
            # 使用 __dataclass_fields__ 检查 dataclass 字段
            if hasattr(ExtractedCallchain, '__dataclass_fields__'):
                fields = ExtractedCallchain.__dataclass_fields__
                self.assertIn('target_symbol', fields)
                self.assertIn('kernel_path', fields)
                self.assertIn('business_callers', fields)
                self.assertIn('extraction_strategy', fields)
            else:
                # 非 dataclass 情况，检查 annotations
                self.assertIn('target_symbol', ExtractedCallchain.__annotations__)
        except ImportError as e:
            self.skipTest(f"CallchainExtractor 未实现: {e}")
    
    def test_findintablewithlock_visible_with_mock(self):
        """使用 mock 数据验证 FindInTableWithLock 可见性"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
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
        
        extractor = CallchainExtractor()
        result = extractor.extract(test_stack, 0, "finish_task_switch_[k]")
        
        # 验证业务调用链包含 FindInTableWithLock
        self.assertIsNotNone(result.business_callers)
        self.assertTrue(
            any("FindInTableWithLock" in s for s in result.business_callers),
            f"FindInTableWithLock 应该在 business_callers 中，实际为: {result.business_callers}"
        )
        
        # 验证提取策略为穿透模式
        self.assertEqual(result.extraction_strategy, "kernel_penetration")
        
        # 验证内核路径被保留
        self.assertTrue(len(result.kernel_path) > 0)
        self.assertIn("__schedule_[k]", result.kernel_path)
        
        # 验证用户态入口点
        self.assertIsNotNone(result.user_entry_point)
        self.assertIn("__GI___nanosleep", result.user_entry_point)
    
    def test_kernel_path_preservation(self):
        """验证内核路径被正确保留"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
        # 构造测试栈
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
            "FindInTableWithLock",
            "InsertWithProb",
        ]
        
        extractor = CallchainExtractor()
        extracted = extractor.extract(test_stack, 0, "finish_task_switch_[k]")
        
        # 验证内核路径包含关键函数
        self.assertIn("__schedule_[k]", extracted.kernel_path)
        self.assertIn("do_nanosleep_[k]", extracted.kernel_path)
        
        # 验证系统调用入口
        self.assertEqual(extracted.syscall_entry, "__x64_sys_nanosleep_[k]")
        
        # 验证用户态入口点
        self.assertEqual(extracted.user_entry_point, "__GI___nanosleep")
        
        # 验证业务调用链
        self.assertIn("FindInTableWithLock", extracted.business_callers)
    
    def test_standard_extraction_for_user_functions(self):
        """验证用户态函数使用标准提取模式"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
        test_stack = [
            "AdamOptimizer::Optimize",
            "GradientDescent::Update",
            "Model::TrainStep",
            "Session::Run",
        ]
        
        extractor = CallchainExtractor()
        extracted = extractor.extract(test_stack, 0, "AdamOptimizer::Optimize")
        
        # 用户态函数应该使用标准模式
        self.assertEqual(extracted.extraction_strategy, "standard")
        
        # 验证 business_callers 包含调用链
        self.assertTrue(len(extracted.business_callers) > 0)
        self.assertIn("GradientDescent::Update", extracted.business_callers)
    
    def test_facade_integration(self):
        """验证 facade.analyze_callers 集成成功"""
        if not self.samples or not self.engine:
            self.skipTest("测试数据不可用")
        
        try:
            from scripts.perf_toolkit.analysis.facade import AnalysisFacade
        except ImportError:
            self.skipTest("AnalysisFacade 不可用")
        
        facade = AnalysisFacade(self.engine)
        
        # 测试是否能正常运行（不报错）
        try:
            result = facade.analyze_callers(
                self.samples,
                target_symbol="finish_task_switch",
                comm="parameter_serve",
                use_penetration=True
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.target, "finish_task_switch")
        except Exception as e:
            self.fail(f"facade.analyze_callers 执行失败: {e}")
    
    def test_facade_backward_compatibility(self):
        """验证关闭穿透模式时行为与之前一致"""
        if not self.samples or not self.engine:
            self.skipTest("测试数据不可用")
        
        try:
            from scripts.perf_toolkit.analysis.facade import AnalysisFacade
        except ImportError:
            self.skipTest("AnalysisFacade 不可用")
        
        facade = AnalysisFacade(self.engine)
        
        # 对普通用户态函数测试两种模式
        try:
            # 使用穿透模式
            result_with = facade.analyze_callers(
                self.samples, 
                target_symbol="AdamOptimizer::Optimize",
                use_penetration=True
            )
            
            # 不使用穿透模式
            result_without = facade.analyze_callers(
                self.samples, 
                target_symbol="AdamOptimizer::Optimize",
                use_penetration=False
            )
            
            # 对于用户态函数，两者结果应该一致（或兼容）
            self.assertEqual(result_with.target, result_without.target)
            
        except Exception as e:
            self.fail(f"向后兼容性测试失败: {e}")
    
    def test_facade_use_penetration_parameter(self):
        """验证 facade.analyze_callers 支持 use_penetration 参数"""
        if not self.samples or not self.engine:
            self.skipTest("测试数据不可用")
        
        try:
            from scripts.perf_toolkit.analysis.facade import AnalysisFacade
        except ImportError:
            self.skipTest("AnalysisFacade 不可用")
        
        facade = AnalysisFacade(self.engine)
        
        # 测试带 use_penetration 参数的调用
        try:
            result_with_pen = facade.analyze_callers(
                self.samples,
                target_symbol="finish_task_switch",
                comm="parameter_serve",
                use_penetration=True
            )
            
            result_without_pen = facade.analyze_callers(
                self.samples,
                target_symbol="finish_task_switch",
                comm="parameter_serve",
                use_penetration=False
            )
            
            # 两者都应该返回有效的 CallersResult
            self.assertIsNotNone(result_with_pen)
            self.assertIsNotNone(result_without_pen)
            
        except TypeError as e:
            if "use_penetration" in str(e):
                self.fail("facade.analyze_callers 不支持 use_penetration 参数")
            raise


class TestKernelAwarenessBasic(unittest.TestCase):
    """测试 KernelAwareness 基本功能"""
    
    def test_is_kernel_function_with_marker(self):
        """测试识别带 _[k] 标记的内核函数"""
        try:
            from scripts.perf_toolkit.core.symbol import KernelAwareness
        except ImportError:
            self.skipTest("KernelAwareness 未实现")
        
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule_[k]"))
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
        self.assertFalse(KernelAwareness.is_kernel_function("__GI___nanosleep"))
    
    def test_should_penetrate_whitelist(self):
        """测试白名单穿透判断"""
        try:
            from scripts.perf_toolkit.core.symbol import KernelAwareness
        except ImportError:
            self.skipTest("KernelAwareness 未实现")
        
        should, reason = KernelAwareness.should_penetrate("finish_task_switch")
        self.assertTrue(should)
        
        should, reason = KernelAwareness.should_penetrate("finish_task_switch_[k]")
        self.assertTrue(should)
        
        should, reason = KernelAwareness.should_penetrate("osq_lock_[k]")
        self.assertFalse(should)
    
    def test_find_user_entry_point(self):
        """测试查找用户态入口点"""
        try:
            from scripts.perf_toolkit.core.symbol import KernelAwareness
        except ImportError:
            self.skipTest("KernelAwareness 未实现")
        
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "__GI___nanosleep",
            "FindInTableWithLock",
        ]
        
        idx = KernelAwareness.find_user_entry_point(stack, 0)
        self.assertEqual(idx, 2)  # __GI___nanosleep 的索引
        self.assertEqual(stack[idx], "__GI___nanosleep")


class TestCallchainExtractorEdgeCases(unittest.TestCase):
    """测试 CallchainExtractor 边界情况"""
    
    def test_empty_stack(self):
        """测试空栈处理"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
        extractor = CallchainExtractor()
        result = extractor.extract([], 0, "finish_task_switch_[k]")
        
        self.assertEqual(result.extraction_strategy, "empty")
        self.assertEqual(result.business_callers, [])
        self.assertEqual(result.kernel_path, [])
    
    def test_invalid_index(self):
        """测试无效索引处理"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
        extractor = CallchainExtractor()
        stack = ["func1", "func2"]
        
        result = extractor.extract(stack, -1, "func1")
        self.assertEqual(result.extraction_strategy, "empty")
        
        result = extractor.extract(stack, 5, "func1")
        self.assertEqual(result.extraction_strategy, "empty")
    
    def test_no_user_space_found(self):
        """测试未找到用户态的情况"""
        try:
            from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        except ImportError:
            self.skipTest("CallchainExtractor 未实现")
        
        extractor = CallchainExtractor()
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "schedule_[k]",
        ]
        
        result = extractor.extract(stack, 0, "finish_task_switch_[k]")
        
        # 没有用户态，策略应该是 truncated
        self.assertEqual(result.extraction_strategy, "truncated")
        self.assertEqual(result.business_callers, [])
        self.assertTrue(len(result.kernel_path) > 0)


if __name__ == '__main__':
    unittest.main()
