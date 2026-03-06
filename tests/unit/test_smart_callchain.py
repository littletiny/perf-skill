#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试：SmartCallchainExtractor

测试核心功能：
1. 关键点保留（栈顶、栈底、热点）
2. 轨迹生成
3. 热点识别
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


class TestSmartCallchainExtractor(unittest.TestCase):
    """测试 SmartCallchainExtractor 核心功能"""
    
    def test_preserve_stack_top_and_bottom(self):
        """保留栈顶和栈底"""
        samples = [MockSample(["Target"], weight=1)]
        extractor = SmartCallchainExtractor(samples, max_display_length=5)
        
        stack = ["Target", "Caller1", "Middle", "CallerN", "EntryPoint"]
        result = extractor.extract(stack, 0, "Target")
        
        self.assertIn("Caller1", result.trajectory)  # 栈顶
        self.assertIn("EntryPoint", result.trajectory)  # 栈底
    
    def test_preserve_hotspots(self):
        """保留热点函数"""
        samples = [
            MockSample(["Target"], weight=10),
            MockSample(["HotFunc"], weight=8),
        ]
        extractor = SmartCallchainExtractor(samples, max_display_length=10)
        
        stack = ["Target", "A", "HotFunc", "C", "D"]
        result = extractor.extract(stack, 0, "Target")
        
        self.assertIn("HotFunc", result.trajectory)
    
    def test_trajectory_format(self):
        """轨迹格式检查"""
        samples = [MockSample(["Target", "A", "B", "C"], weight=1)]
        extractor = SmartCallchainExtractor(samples, max_display_length=5)
        
        stack = ["Target", "Caller1", "X", "Y", "Entry"]
        result = extractor.extract(stack, 0, "Target")
        
        self.assertIn("..", result.trajectory)  # 折叠标记
        self.assertIn("<-", result.trajectory)  # 连接符
    
    def test_max_length_limit(self):
        """最大长度限制"""
        samples = [MockSample(["Target"], weight=10)]
        
        for max_len in [5, 8]:
            extractor = SmartCallchainExtractor(samples, max_display_length=max_len)
            stack = ["Target"] + [f"L{i}" for i in range(30)]
            result = extractor.extract(stack, 0, "Target")
            
            total_display = len(result.key_points) + 1
            self.assertLessEqual(total_display, max_len,
                f"max_length={max_len} but got {total_display} points")


class TestRealWorldScenario(unittest.TestCase):
    """真实场景测试"""
    
    def test_finish_task_switch_scenario(self):
        """finish_task_switch 场景"""
        samples = []
        for _ in range(10):
            samples.append(MockSample(["finish_task_switch"], weight=10))
        for _ in range(5):
            samples.append(MockSample(["FindInTableWithLock"], weight=8))
        
        extractor = SmartCallchainExtractor(samples, max_display_length=8)
        
        stack = [
            "finish_task_switch", "__schedule", "schedule",
            "do_nanosleep", "hrtimer_nanosleep", "__x64_sys_nanosleep",
            "do_syscall_64", "entry_SYSCALL_64", "__GI___nanosleep",
            "FindInTableWithLock", "InsertWithProb", "EntryPoint"
        ]
        
        result = extractor.extract(stack, 0, "finish_task_switch")
        
        self.assertIn("__schedule", result.trajectory)
        self.assertIn("FindInTableWithLock", result.trajectory)
        self.assertIn("EntryPoint", result.trajectory)


class TestFormatting(unittest.TestCase):
    """测试格式化输出"""
    
    def test_compact_format(self):
        """紧凑格式"""
        chain = SmartCallchain(
            target_symbol="Target",
            display_chain="Target <- A <- .. <- Entry",
            key_points=[],
            trajectory="Target <- A <- .. <- Entry",
            hotspot_chain=["Target"],
            folded_count=5,
            penetration_depth=10,
            max_length=8
        )
        
        compact = chain.to_compact_string()
        self.assertEqual(compact, "Target→A→..→Entry")
    
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
