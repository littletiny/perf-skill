#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for CallchainExtractor

Test coverage:
1. Kernel penetration mode extraction
2. Standard mode extraction (user-space functions)
3. Empty stack handling
4. Boundary conditions (invalid index, etc.)
5. Syscall entry recognition
6. User entry point identification

Usage:
    cd tests
    python3 unit/test_callchain_extractor.py
"""

import sys
import unittest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from perf_toolkit.analysis.callchain_extractor import (
    ExtractedCallchain,
    CallchainExtractor,
)
from perf_toolkit.core.symbol import KernelAwareness


class TestExtractedCallchain(unittest.TestCase):
    """Test ExtractedCallchain dataclass"""
    
    def test_dataclass_is_frozen(self):
        """Test that ExtractedCallchain is immutable (frozen)"""
        result = ExtractedCallchain(
            target_symbol="test",
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=["caller1"],
            raw_path=["test", "caller1"],
            extraction_strategy="standard"
        )
        
        # Attempting to modify should raise FrozenInstanceError
        with self.assertRaises(Exception):
            result.target_symbol = "modified"
    
    def test_dataclass_fields(self):
        """Test all required fields exist"""
        result = ExtractedCallchain(
            target_symbol="finish_task_switch_[k]",
            kernel_path=["__schedule_[k]"],
            syscall_entry="__x64_sys_nanosleep_[k]",
            user_entry_point="__GI___nanosleep",
            business_callers=["FindInTableWithLock", "InsertWithProb"],
            raw_path=["finish_task_switch_[k]", "__schedule_[k]", "FindInTableWithLock"],
            extraction_strategy="kernel_penetration"
        )
        
        self.assertEqual(result.target_symbol, "finish_task_switch_[k]")
        self.assertEqual(result.kernel_path, ["__schedule_[k]"])
        self.assertEqual(result.syscall_entry, "__x64_sys_nanosleep_[k]")
        self.assertEqual(result.user_entry_point, "__GI___nanosleep")
        self.assertEqual(result.business_callers, ["FindInTableWithLock", "InsertWithProb"])
        self.assertEqual(result.extraction_strategy, "kernel_penetration")


class TestKernelAwareness(unittest.TestCase):
    """Test KernelAwareness from core.symbol"""
    
    def test_is_kernel_function_with_k_suffix(self):
        """Test kernel detection with _[k] suffix"""
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule_[k]"))
        self.assertTrue(KernelAwareness.is_kernel_function("osq_lock_[k]"))
    
    def test_is_kernel_function_by_prefix(self):
        """Test kernel detection by known prefix"""
        # These should be detected as kernel by prefix matching
        self.assertTrue(KernelAwareness.is_kernel_function("__schedule"))
        self.assertTrue(KernelAwareness.is_kernel_function("schedule"))
        self.assertTrue(KernelAwareness.is_kernel_function("finish_task_switch"))
        self.assertTrue(KernelAwareness.is_kernel_function("__x64_sys_nanosleep"))
    
    def test_is_kernel_function_user_space(self):
        """Test user-space functions are not kernel"""
        self.assertFalse(KernelAwareness.is_kernel_function("FindInTableWithLock"))
        self.assertFalse(KernelAwareness.is_kernel_function("__GI___nanosleep"))
        self.assertFalse(KernelAwareness.is_kernel_function("AdamOptimizer::Optimize"))
    
    def test_should_penetrate_whitelist(self):
        """Test penetration detection for whitelisted functions"""
        should_pen, reason = KernelAwareness.should_penetrate("finish_task_switch")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "in_whitelist")
        
        should_pen, reason = KernelAwareness.should_penetrate("__schedule")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "in_whitelist")
    
    def test_should_penetrate_schedule_related(self):
        """Test penetration detection for schedule-related functions"""
        # Functions containing schedule keywords should be penetrated
        should_pen, reason = KernelAwareness.should_penetrate("some_schedule_function")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "schedule_related")
        
        should_pen, reason = KernelAwareness.should_penetrate("my_nanosleep_func")
        self.assertTrue(should_pen)
        self.assertEqual(reason, "schedule_related")
    
    def test_should_not_penetrate_regular(self):
        """Test penetration detection for non-special functions"""
        should_pen, reason = KernelAwareness.should_penetrate("osq_lock_[k]")
        self.assertFalse(should_pen)
        self.assertEqual(reason, "")
        
        should_pen, reason = KernelAwareness.should_penetrate("FindInTableWithLock")
        self.assertFalse(should_pen)
        self.assertEqual(reason, "")
    
    def test_find_user_entry_point(self):
        """Test finding user entry point in stack"""
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "__GI___nanosleep",
            "FindInTableWithLock",
        ]
        
        # Start from index 1 (after target)
        idx = KernelAwareness.find_user_entry_point(stack, 1)
        self.assertEqual(idx, 2)
        self.assertEqual(stack[idx], "__GI___nanosleep")
    
    def test_find_user_entry_point_not_found(self):
        """Test when no user entry point exists"""
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "schedule_[k]",
        ]
        
        idx = KernelAwareness.find_user_entry_point(stack, 1)
        self.assertIsNone(idx)


class TestCallchainExtractor(unittest.TestCase):
    """Test CallchainExtractor main functionality"""
    
    def setUp(self):
        """Setup extractor for each test"""
        self.extractor = CallchainExtractor()
    
    def test_kernel_penetration_mode(self):
        """
        Test 1: Kernel penetration mode extraction
        
        Verify that for finish_task_switch_[k], we can extract:
        - kernel_path containing kernel functions
        - user_entry_point being the first user-space function
        - business_callers containing business layer functions
        - syscall_entry being the system call entry
        """
        stack = [
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
            "PushVecFid",
        ]
        
        result = self.extractor.extract(stack, 0, "finish_task_switch_[k]")
        
        # Verify extraction strategy
        self.assertEqual(result.extraction_strategy, "kernel_penetration")
        
        # Verify kernel_path contains expected functions
        self.assertIn("__schedule_[k]", result.kernel_path)
        self.assertIn("schedule_[k]", result.kernel_path)
        self.assertIn("do_nanosleep_[k]", result.kernel_path)
        
        # Verify syscall entry is recognized
        self.assertEqual(result.syscall_entry, "__x64_sys_nanosleep_[k]")
        
        # Verify user entry point
        self.assertEqual(result.user_entry_point, "__GI___nanosleep")
        
        # Verify business callers
        self.assertIn("FindInTableWithLock", result.business_callers)
        self.assertIn("InsertWithProb", result.business_callers)
        self.assertIn("PushVecFid", result.business_callers)
        
        # Verify raw_path is preserved
        self.assertEqual(result.raw_path, stack)
    
    def test_standard_mode_user_space(self):
        """
        Test 2: Standard mode for user-space functions
        
        Verify that for user-space functions, standard extraction works:
        - extraction_strategy is "standard"
        - business_callers contains the callers
        - kernel_path is empty
        """
        stack2 = ["AdamOptimizer::Optimize", "Update", "PushVecFid", "PushModel"]
        result = self.extractor.extract(stack2, 0, "AdamOptimizer::Optimize")
        
        self.assertEqual(result.extraction_strategy, "standard")
        self.assertEqual(result.business_callers, ["Update", "PushVecFid", "PushModel"])
        self.assertEqual(result.kernel_path, [])
        self.assertIsNone(result.user_entry_point)
        self.assertIsNone(result.syscall_entry)
    
    def test_empty_stack(self):
        """
        Test 3: Empty stack handling
        
        Verify that empty stack returns empty strategy result.
        """
        result = self.extractor.extract([], 0, "test")
        self.assertEqual(result.extraction_strategy, "empty")
        self.assertEqual(result.business_callers, [])
        self.assertEqual(result.kernel_path, [])
    
    def test_invalid_target_index_negative(self):
        """Test handling of negative target index"""
        stack = ["func1", "func2"]
        result = self.extractor.extract(stack, -1, "test")
        self.assertEqual(result.extraction_strategy, "empty")
    
    def test_invalid_target_index_out_of_bounds(self):
        """Test handling of out-of-bounds target index"""
        stack = ["func1", "func2"]
        result = self.extractor.extract(stack, 5, "test")
        self.assertEqual(result.extraction_strategy, "empty")
    
    def test_truncated_strategy_no_user_space(self):
        """
        Test truncated strategy when no user-space function found
        
        If the stack only contains kernel functions (no user-space entry),
        the strategy should be "truncated".
        """
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "schedule_[k]",
        ]
        
        result = self.extractor.extract(stack, 0, "finish_task_switch_[k]")
        
        self.assertEqual(result.extraction_strategy, "truncated")
        self.assertIsNone(result.user_entry_point)
        self.assertEqual(result.business_callers, [])
        self.assertIn("__schedule_[k]", result.kernel_path)
    
    def test_custom_max_depth(self):
        """Test custom max_depth configuration"""
        extractor = CallchainExtractor(default_max_depth=2)
        
        stack = ["target", "c1", "c2", "c3", "c4"]
        result = extractor.extract(stack, 0, "target")
        
        self.assertEqual(len(result.business_callers), 2)
        self.assertEqual(result.business_callers, ["c1", "c2"])
    
    def test_penetration_max_depth_limit(self):
        """Test penetration max depth safety limit"""
        extractor = CallchainExtractor(
            default_max_depth=10,
            penetration_max_depth=3  # Very small limit
        )
        
        # Create a long stack with user-space at index 5
        # With penetration_max_depth=3, should stop after i=3
        # so user_func at i=5 should not be reached
        stack = [
            "finish_task_switch_[k]",  # 0: target
            "k1_[k]",                  # 1: kernel
            "k2_[k]",                  # 2: kernel
            "k3_[k]",                  # 3: kernel
            "k4_[k]",                  # 4: kernel (will be processed, i=4 > 3 triggers break after)
            "user_func",               # 5: user (should NOT be reached)
        ]
        
        result = extractor.extract(stack, 0, "finish_task_switch_[k]")
        
        # Should stop at penetration_max_depth
        # So user_func should not be reached
        self.assertEqual(result.extraction_strategy, "truncated")
    
    def test_syscall_entry_variants(self):
        """Test syscall entry recognition with different patterns"""
        # Test with __x64_sys_ pattern (this is a kernel prefix)
        # Use finish_task_switch_[k] as target because it's in whitelist
        stack = [
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "__x64_sys_read_[k]",
            "user_func",
        ]
        result = self.extractor.extract(stack, 0, "finish_task_switch_[k]")
        # __x64_sys_read_[k] should be detected as kernel and syscall entry
        self.assertEqual(result.syscall_entry, "__x64_sys_read_[k]")
        self.assertEqual(result.user_entry_point, "user_func")
    
    def test_non_whitelist_kernel_function(self):
        """Test kernel function not in whitelist uses standard mode"""
        stack = [
            "osq_lock_[k]",
            "mutex_lock_[k]",
            "some_user_func",
        ]
        
        result = self.extractor.extract(stack, 0, "osq_lock_[k]")
        
        # osq_lock is not in whitelist and doesn't match schedule keywords, 
        # so uses standard mode
        self.assertEqual(result.extraction_strategy, "standard")
    
    def test_target_at_middle_of_stack(self):
        """Test extraction when target is not at index 0"""
        stack = [
            "other_[k]",
            "finish_task_switch_[k]",
            "__schedule_[k]",
            "__GI___nanosleep",
            "business_func",
        ]
        
        result = self.extractor.extract(stack, 1, "finish_task_switch_[k]")
        
        self.assertEqual(result.extraction_strategy, "kernel_penetration")
        self.assertIn("__schedule_[k]", result.kernel_path)
        self.assertEqual(result.user_entry_point, "__GI___nanosleep")
        self.assertIn("business_func", result.business_callers)
    
    def test_kernel_without_k_suffix(self):
        """Test kernel function detection without _[k] suffix"""
        # finish_task_switch without _[k] should still be detected as kernel
        # because it matches the KERNEL_PREFIXES
        stack = [
            "finish_task_switch",  # No _[k] suffix but is a kernel prefix
            "__schedule",
            "user_func",
        ]
        
        result = self.extractor.extract(stack, 0, "finish_task_switch")
        
        # Should use penetration mode because finish_task_switch is in whitelist
        self.assertEqual(result.extraction_strategy, "kernel_penetration")
        self.assertIn("__schedule", result.kernel_path)


def run_tests():
    """Run all tests with detailed output"""
    print("=" * 70)
    print("CallchainExtractor Unit Test Suite")
    print("=" * 70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExtractedCallchain))
    suite.addTests(loader.loadTestsFromTestCase(TestKernelAwareness))
    suite.addTests(loader.loadTestsFromTestCase(TestCallchainExtractor))
    
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
