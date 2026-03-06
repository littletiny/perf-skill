#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试：SmartCallchainExtractor

测试改进点：
1. 保留栈顶、栈底
2. 非连续采样
3. 可配置 max_display_length
4. 轨迹清晰度
"""

import unittest
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from perf_toolkit.analysis.smart_callchain import (
    SmartCallchainExtractor, SmartCallchain, KeyPoint,
    extract_smart_callchain, format_callchain_for_display
)


# =============================================================================
# Mock 数据
# =============================================================================

@dataclass
class MockStack:
    symbols: List[str]
    def get_normalized_names(self):
        return self.symbols


@dataclass
class MockSample:
    symbols: List[str]
    weight: float = 1.0
    @property
    def stack(self):
        return MockStack(self.symbols)


# =============================================================================
# 测试用例
# =============================================================================

class TestKeyPointPreservation(unittest.TestCase):
    """测试关键点保留"""
    
    def test_preserve_stack_top(self):
        """保留栈顶（距离目标最近的调用者）"""
        samples = [MockSample(["Target", "Caller1", "Caller2", "Caller3"], weight=1)]
        extractor = SmartCallchainExtractor(samples, max_display_length=5)
        
        stack = ["Target", "Caller1", "Caller2", "Caller3", "EntryPoint"]
        result = extractor.extract(stack, 0, "Target")
        
        # 栈顶 Caller1 应该被保留
        self.assertIn("Caller1", result.trajectory)
    
    def test_preserve_stack_bottom(self):
        """保留栈底（最底层的入口）"""
        samples = [MockSample(["Target", "A", "B", "C"], weight=1)]
        extractor = SmartCallchainExtractor(samples, max_display_length=5)
        
        stack = ["Target", "Caller1", "Caller2", "Caller3", "EntryPoint"]
        result = extractor.extract(stack, 0, "Target")
        
        # 栈底 EntryPoint 应该被保留
        self.assertIn("EntryPoint", result.trajectory)
    
    def test_preserve_hotspots(self):
        """保留热点函数"""
        samples = [
            MockSample(["Target"], weight=10),
            MockSample(["HotFunc"], weight=8),
        ]
        # 使用更大的 max_length 确保能显示热点
        extractor = SmartCallchainExtractor(samples, max_display_length=10)
        
        stack = ["Target", "A", "HotFunc", "C", "D"]
        result = extractor.extract(stack, 0, "Target")
        
        # 热点 HotFunc 应该被保留（用 [] 标记）
        self.assertIn("HotFunc", result.trajectory)


class TestSamplingStrategy(unittest.TestCase):
    """测试采样策略"""
    
    def test_interval_sampling(self):
        """间隔采样"""
        samples = [MockSample(["Target"], weight=10)]
        extractor = SmartCallchainExtractor(
            samples, 
            max_display_length=10,
            sample_interval=3
        )
        
        # 构造一个长栈
        stack = ["Target"] + [f"L{i}" for i in range(20)]
        result = extractor.extract(stack, 0, "Target")
        
        # 应该保留部分采样点
        key_point_count = len(result.key_points)
        self.assertGreater(key_point_count, 2)  # 至少保留栈顶和栈底
        self.assertLessEqual(key_point_count + 1, 10)  # +1 for target
    
    def test_max_length_limit(self):
        """最大长度限制"""
        samples = [MockSample(["Target"], weight=10)]
        
        for max_len in [5, 8, 12]:
            extractor = SmartCallchainExtractor(samples, max_display_length=max_len)
            stack = ["Target"] + [f"L{i}" for i in range(30)]
            result = extractor.extract(stack, 0, "Target")
            
            # 关键点数量 + target 应该 <= max_length
            total_display = len(result.key_points) + 1
            self.assertLessEqual(total_display, max_len,
                f"max_length={max_len} but got {total_display} points")


class TestTrajectoryClarity(unittest.TestCase):
    """测试轨迹清晰度"""
    
    def test_trajectory_format(self):
        """轨迹格式"""
        samples = [MockSample(["Target", "A", "B", "C", "D"], weight=1)]
        extractor = SmartCallchainExtractor(samples, max_display_length=5)
        
        stack = ["Target", "Caller1", "X", "Y", "Entry"]
        result = extractor.extract(stack, 0, "Target")
        
        # 轨迹应该包含 .. 表示折叠
        self.assertIn("..", result.trajectory)
        # 轨迹应该用 <- 连接
        self.assertIn("<-", result.trajectory)
    
    def test_clear_calling_trace(self):
        """清晰的调用轨迹"""
        samples = [
            MockSample(["finish_task_switch"], weight=100),
            MockSample(["FindInTableWithLock"], weight=50),
        ]
        extractor = SmartCallchainExtractor(samples, max_display_length=8)
        
        # 模拟真实调用链
        stack = [
            "finish_task_switch",
            "__schedule",      # 栈顶
            "schedule",
            "do_nanosleep",
            "FindInTableWithLock",  # 热点
            "InsertWithProb",
            "PushVecFid",
            "PushModel",
            "EntryPoint",      # 栈底
        ]
        result = extractor.extract(stack, 0, "finish_task_switch")
        
        print(f"\n[轨迹测试] {result.trajectory}")
        
        # 应该保留：栈顶、热点、栈底
        self.assertIn("__schedule", result.trajectory)
        self.assertIn("FindInTableWithLock", result.trajectory)
        self.assertIn("EntryPoint", result.trajectory)
        
        # 应该有折叠
        self.assertIn("..", result.trajectory)


class TestRealWorldScenario(unittest.TestCase):
    """真实场景测试"""
    
    def test_finish_task_switch_v2(self):
        """finish_task_switch 穿透测试"""
        # 构造热点
        samples = []
        for _ in range(10):
            samples.append(MockSample(["finish_task_switch"], weight=10))
        for _ in range(5):
            samples.append(MockSample(["FindInTableWithLock"], weight=8))
        
        extractor = SmartCallchainExtractor(
            samples, 
            max_display_length=8,
            sample_interval=3
        )
        
        # 模拟真实调用链
        stack = [
            "finish_task_switch",     # idx 0, target
            "__schedule",             # idx 1, 栈顶
            "schedule",
            "do_nanosleep",
            "hrtimer_nanosleep",
            "__x64_sys_nanosleep",
            "do_syscall_64",
            "entry_SYSCALL_64",
            "__GI___nanosleep",
            "FindInTableWithLock",    # 热点
            "InsertWithProb",
            "PushVecFid",
            "PushModel",
            "EntryPoint",             # idx 14, 栈底
        ]
        
        result = extractor.extract(stack, 0, "finish_task_switch")
        
        print(f"\n[真实场景] 轨迹: {result.trajectory}")
        print(f"  关键点: {[kp.symbol for kp in result.key_points]}")
        print(f"  热点链: {' -> '.join(result.hotspot_chain)}")
        
        # 验证关键点保留
        self.assertIn("__schedule", result.trajectory, "应保留栈顶")
        self.assertIn("FindInTableWithLock", result.trajectory, "应保留热点")
        self.assertIn("EntryPoint", result.trajectory, "应保留栈底")
        
        # 验证长度限制
        self.assertLessEqual(len(result.key_points) + 1, 8)
    
    def test_configurable_length(self):
        """可配置长度"""
        samples = [MockSample(["Target"], weight=10)]
        
        stack = ["Target"] + [f"Layer{i}" for i in range(20)]
        
        for length in [5, 10, 15]:
            extractor = SmartCallchainExtractor(samples, max_display_length=length)
            result = extractor.extract(stack, 0, "Target")
            
            # 验证 max_length 被保存
            self.assertEqual(result.max_length, length)
            
            # 验证关键点数量在合理范围内（允许稍微超过以看清调用链）
            # 策略：优先保证调用链清晰度，最多保留 max_length - 2 个关键点
            self.assertLessEqual(len(result.key_points), max(1, length - 2),
                f"max_length={length} but got {len(result.key_points)} key_points")


class TestFormatting(unittest.TestCase):
    """测试格式化输出"""
    
    def test_compact_format(self):
        """紧凑格式"""
        chain = SmartCallchain(
            target_symbol="Target",
            display_chain="Target <- A <- .. <- [Hot] <- .. <- Entry",
            key_points=[],
            trajectory="Target <- A <- .. <- [Hot] <- .. <- Entry",
            hotspot_chain=["Target", "Hot"],
            folded_count=5,
            penetration_depth=10,
            max_length=8
        )
        
        compact = chain.to_compact_string()
        self.assertEqual(compact, "Target→A→..→[Hot]→..→Entry")
    
    def test_format_for_display(self):
        """显示格式化"""
        chain = SmartCallchain(
            target_symbol="Target",
            display_chain="Target <- A <- B",
            key_points=[KeyPoint("A", 1, "entry"), KeyPoint("B", 2, "anchor")],
            trajectory="Target <- A <- B",
            hotspot_chain=["Target"],
            folded_count=0,
            penetration_depth=2,
            max_length=8
        )
        
        formatted = format_callchain_for_display(chain, 5.50, 1, mode="compact")
        self.assertIn("#1", formatted)
        self.assertIn("5.50%", formatted)
        self.assertIn("Target", formatted)


if __name__ == '__main__':
    unittest.main(verbosity=2)
