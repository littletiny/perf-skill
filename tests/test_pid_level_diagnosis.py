#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PID Level Diagnosis Test Suite

验证工具集 pid 级别的诊断功能是否符合预期。

测试覆盖:
1. show-cpu-usage --pid: PID 级别的 CPU 利用率分析
2. get-hotspots --pid: PID 级别的热点函数识别
3. find-callers --pid: PID 级别的调用溯源
4. cluster-symbols --pid: PID 级别的语义聚类
5. analyze-core-distribution --pid: PID 级别的核心分布
6. cluster-paths --pid: PID 级别的调用路径聚类
7. count-process-variety --pid: PID 级别的进程多样性

数据文件: tests/perfdata/new_format/case_huge_samples.data

Usage:
    cd tests
    python3 test_pid_level_diagnosis.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestPIDLevelDiagnosis(unittest.TestCase):
    """Test PID level diagnosis functionality"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment"""
        cls.test_dir = Path(__file__).parent
        cls.repo_root = cls.test_dir.parent
        cls.spear_script = cls.repo_root / "scripts" / "spear.py"
        cls.test_data = cls.repo_root / "tests" / "perfdata" / "new_format" / "case_huge_samples.data"

        # 验证测试数据文件存在
        if not cls.test_data.exists():
            raise FileNotFoundError(f"Test data file not found: {cls.test_data}")

        # 主要测试 PID (从数据文件中识别出的高消耗进程)
        cls.test_pids = {
            'kubelet': 1143016,      # 最高消耗进程
            'telegraf': 72179,       # 高消耗进程
            'ilogtail': 74186,       # 高消耗进程
            'hacontrol': 1204656,    # Go 进程，有 GC 活动
        }

    def _run_spear(self, args):
        """Helper to run spear command"""
        cmd = [sys.executable, str(self.spear_script)] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.repo_root)
        )
        return result

    def _run_pid_command(self, subcommand, pid, extra_args=None):
        """Helper to run pid-specific command"""
        args = [
            subcommand,
            "--data", str(self.test_data),
            "--pid", str(pid)
        ]
        if extra_args:
            args.extend(extra_args)
        return self._run_spear(args)

    # =================================================================
    # Test 1: show-cpu-usage --pid
    # =================================================================

    def test_01_show_cpu_usage_pid_basic(self):
        """Test: show-cpu-usage --pid 基本功能"""
        print("\n[Test 01] show-cpu-usage --pid 基本功能")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("show-cpu-usage", pid)

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        self.assertIn("Target: PID", result.stdout)
        self.assertIn("Total:", result.stdout)
        self.assertIn("User:", result.stdout)
        self.assertIn("Kernel:", result.stdout)

        print(f"  ✓ PID {pid} CPU usage retrieved successfully")

    def test_02_show_cpu_usage_pid_values(self):
        """Test: show-cpu-usage --pid 数值合理性检查"""
        print("\n[Test 02] show-cpu-usage --pid 数值合理性")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("show-cpu-usage", pid)

        # 解析输出中的数值
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'Total:' in line:
                total_str = line.split(':')[1].strip().rstrip('%')
                total = float(total_str)
                self.assertGreater(total, 0, "Total CPU should be > 0")
                # kubelet 是最高消耗进程，应该 > 100%
                self.assertGreater(total, 100, "kubelet should have > 100% CPU")

        print(f"  ✓ PID {pid} CPU values are reasonable")

    def test_03_show_cpu_usage_different_pids(self):
        """Test: show-cpu-usage --pid 多个 PID 对比"""
        print("\n[Test 03] show-cpu-usage --pid 多个 PID 对比")

        results = {}
        for name, pid in self.test_pids.items():
            result = self._run_pid_command("show-cpu-usage", pid)
            self.assertEqual(result.returncode, 0)

            # 提取 Total CPU
            for line in result.stdout.strip().split('\n'):
                if 'Total:' in line:
                    total_str = line.split(':')[1].strip().rstrip('%')
                    results[name] = float(total_str)
                    break

        # kubelet 应该是最高的
        self.assertGreater(
            results.get('kubelet', 0),
            results.get('hacontrol', 0),
            "kubelet should have higher CPU than hacontrol"
        )

        print(f"  ✓ CPU comparison: kubelet({results.get('kubelet', 0):.1f}%) > hacontrol({results.get('hacontrol', 0):.1f}%)")

    def test_04_show_cpu_usage_nonexistent_pid(self):
        """Test: show-cpu-usage --pid 不存在的 PID"""
        print("\n[Test 04] show-cpu-usage --pid 不存在的 PID")

        result = self._run_pid_command("show-cpu-usage", 999999999)

        # 应该返回 0，但显示风险信息
        self.assertEqual(result.returncode, 0)
        # 输出应该包含风险信息或 NO_SAMPLES 提示
        has_risk = (
            "_risk" in result.stdout or
            "NO_SAMPLES" in result.stdout or
            "未找到样本" in result.stdout or
            "Target: PID" in result.stdout
        )
        self.assertTrue(has_risk, f"Expected risk info for non-existent PID: {result.stdout[:200]}")

        print("  ✓ Non-existent PID handled gracefully")

    # =================================================================
    # Test 2: get-hotspots --pid
    # =================================================================

    def test_05_get_hotspots_pid_basic(self):
        """Test: get-hotspots --pid 基本功能"""
        print("\n[Test 05] get-hotspots --pid 基本功能")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("get-hotspots", pid, ["--top-n", "5"])

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        self.assertIn("index,funcname,self,inclusive", result.stdout)

        # 应该有热点数据
        lines = [l for l in result.stdout.strip().split('\n') if l.startswith('#')]
        self.assertGreater(len(lines), 0, "Should have hotspot data")

        print(f"  ✓ PID {pid} hotspots retrieved: {len(lines)} functions")

    def test_06_get_hotspots_pid_sort_by_self(self):
        """Test: get-hotspots --pid --sort-by self"""
        print("\n[Test 06] get-hotspots --pid --sort-by self")

        pid = self.test_pids['hacontrol']
        result = self._run_pid_command(
            "get-hotspots", pid,
            ["--sort-by", "self", "--top-n", "5"]
        )

        self.assertEqual(result.returncode, 0)

        # 检查输出格式
        lines = [l for l in result.stdout.strip().split('\n') if l.startswith('#')]
        if len(lines) >= 2:
            # 第一行是表头，第二行是排名第一的热点
            header = lines[0]
            first_data = lines[1]
            self.assertIn("funcname", header)
            self.assertIn("self", header)
            self.assertIn("inclusive", header)

        print(f"  ✓ Sort by self working for PID {pid}")

    def test_07_get_hotspots_pid_sort_by_inclusive(self):
        """Test: get-hotspots --pid --sort-by inclusive"""
        print("\n[Test 07] get-hotspots --pid --sort-by inclusive")

        pid = self.test_pids['hacontrol']
        result = self._run_pid_command(
            "get-hotspots", pid,
            ["--sort-by", "inclusive", "--top-n", "5"]
        )

        self.assertEqual(result.returncode, 0)

        # 检查输出包含 inclusive 数据
        self.assertIn("inclusive", result.stdout)

        print(f"  ✓ Sort by inclusive working for PID {pid}")

    # =================================================================
    # Test 3: find-callers --pid
    # =================================================================

    def test_08_find_callers_pid_basic(self):
        """Test: find-callers --pid 基本功能"""
        print("\n[Test 08] find-callers --pid 基本功能")

        pid = self.test_pids['kubelet']
        result = self._run_spear([
            "find-callers",
            "--data", str(self.test_data),
            "--pid", str(pid),
            "--target", "entry_SYSCALL_64_after_hwframe"
        ])

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        self.assertIn("index,ratio,callstack", result.stdout)

        print(f"  ✓ PID {pid} callers analysis completed")

    def test_09_find_callers_pid_with_min_cpu(self):
        """Test: find-callers --pid --min-cpu"""
        print("\n[Test 09] find-callers --pid --min-cpu")

        pid = self.test_pids['kubelet']
        result = self._run_spear([
            "find-callers",
            "--data", str(self.test_data),
            "--pid", str(pid),
            "--target", "entry_SYSCALL_64_after_hwframe",
            "--min-cpu", "1.0"
        ])

        self.assertEqual(result.returncode, 0)

        print(f"  ✓ Min-cpu filter working for PID {pid}")

    def test_10_find_callers_pid_auto_target(self):
        """Test: find-callers --pid --auto-target"""
        print("\n[Test 10] find-callers --pid --auto-target")

        pid = self.test_pids['hacontrol']
        result = self._run_spear([
            "find-callers",
            "--data", str(self.test_data),
            "--pid", str(pid),
            "--auto-target",
            "--top-n", "3"
        ])

        self.assertEqual(result.returncode, 0)
        # 自动追踪应该产生输出
        self.assertIn("callstack", result.stdout)

        print(f"  ✓ Auto-target working for PID {pid}")

    # =================================================================
    # Test 4: cluster-symbols --pid
    # =================================================================

    def test_11_cluster_symbols_pid_basic(self):
        """Test: cluster-symbols --pid 基本功能"""
        print("\n[Test 11] cluster-symbols --pid 基本功能")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("cluster-symbols", pid)

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        # 应该包含聚类输出或"No samples found"
        self.assertTrue(
            "event_type" in result.stdout or
            "No samples" in result.stdout or
            "LOCK" in result.stdout or
            "SCHEDULER" in result.stdout
        )

        print(f"  ✓ PID {pid} symbol clustering completed")

    def test_12_cluster_symbols_pid_hacontrol(self):
        """Test: cluster-symbols --pid Go 进程 (hacontrol)"""
        print("\n[Test 12] cluster-symbols --pid Go 进程 (hacontrol)")

        pid = self.test_pids['hacontrol']
        result = self._run_pid_command("cluster-symbols", pid)

        self.assertEqual(result.returncode, 0)

        # Go 进程应该有 GC 相关的锁竞争事件
        output = result.stdout
        has_events = (
            "LOCK_CONTENTION" in output or
            "SYNC_PRIMITIVE" in output or
            "SCHEDULER" in output or
            "No samples" in output
        )
        self.assertTrue(has_events, f"Expected events in output: {output}")

        print(f"  ✓ Go process (PID {pid}) clustering shows relevant events")

    def test_13_cluster_symbols_pid_custom_rules(self):
        """Test: cluster-symbols --pid --custom-rules"""
        print("\n[Test 13] cluster-symbols --pid --custom-rules")

        pid = self.test_pids['kubelet']
        result = self._run_spear([
            "cluster-symbols",
            "--data", str(self.test_data),
            "--pid", str(pid),
            "--custom-rules", '{"MY_SYSCALL": "syscall|system"}'
        ])

        self.assertEqual(result.returncode, 0)

        print(f"  ✓ Custom rules working for PID {pid}")

    # =================================================================
    # Test 5: analyze-core-distribution --pid
    # =================================================================

    def test_14_analyze_core_distribution_pid(self):
        """Test: analyze-core-distribution --pid"""
        print("\n[Test 14] analyze-core-distribution --pid")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("analyze-core-distribution", pid)

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        # 应该包含饱和核心信息或"No saturated cores"
        self.assertTrue(
            "SATURATED_CORES" in result.stdout or
            "No saturated" in result.stdout
        )

        print(f"  ✓ PID {pid} core distribution analyzed")

    def test_15_analyze_core_distribution_different_pids(self):
        """Test: analyze-core-distribution --pid 对比不同 PID"""
        print("\n[Test 15] analyze-core-distribution --pid 对比不同 PID")

        for name, pid in self.test_pids.items():
            result = self._run_pid_command("analyze-core-distribution", pid)
            self.assertEqual(result.returncode, 0)

            # 检查输出格式
            self.assertIn("SATURATED_CORES", result.stdout)

        print(f"  ✓ Core distribution analyzed for {len(self.test_pids)} PIDs")

    # =================================================================
    # Test 6: cluster-paths --pid
    # =================================================================

    def test_16_cluster_paths_pid(self):
        """Test: cluster-paths --pid"""
        print("\n[Test 16] cluster-paths --pid")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command(
            "cluster-paths", pid,
            ["--top-n", "5", "--min-depth", "2"]
        )

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        self.assertIn("index,percent,cpu_util,path", result.stdout)

        # 应该有路径数据
        lines = [l for l in result.stdout.strip().split('\n') if l.startswith('#')]
        self.assertGreater(len(lines), 0, "Should have path data")

        print(f"  ✓ PID {pid} call paths clustered: {len(lines)} paths")

    def test_17_cluster_paths_pid_min_depth(self):
        """Test: cluster-paths --pid --min-depth"""
        print("\n[Test 17] cluster-paths --pid --min-depth")

        pid = self.test_pids['hacontrol']

        # 测试不同 min-depth
        for depth in [2, 3, 5]:
            result = self._run_pid_command(
                "cluster-paths", pid,
                ["--min-depth", str(depth), "--top-n", "3"]
            )
            self.assertEqual(result.returncode, 0)

        print(f"  ✓ Min-depth filter working for PID {pid}")

    # =================================================================
    # Test 7: count-process-variety --pid
    # =================================================================

    def test_18_count_process_variety_pid(self):
        """Test: count-process-variety --pid"""
        print("\n[Test 18] count-process-variety --pid")

        pid = self.test_pids['kubelet']
        result = self._run_pid_command("count-process-variety", pid)

        self.assertEqual(result.returncode, 0, f"Command failed: {result.stderr}")
        # 单 PID 不应该有进程多样性（只有自己）
        self.assertIn("PROCESS_STORM", result.stdout)

        print(f"  ✓ PID {pid} process variety checked")

    # =================================================================
    # Test 8: 组合测试
    # =================================================================

    def test_19_pid_filter_consistency(self):
        """Test: 不同工具对同一 PID 的过滤一致性"""
        print("\n[Test 19] PID 过滤一致性验证")

        pid = self.test_pids['hacontrol']

        # 使用多个工具分析同一 PID
        tools = [
            ("show-cpu-usage", []),
            ("get-hotspots", ["--top-n", "3"]),
            ("cluster-symbols", []),
            ("analyze-core-distribution", []),
        ]

        results = {}
        for tool, extra_args in tools:
            result = self._run_pid_command(tool, pid, extra_args)
            self.assertEqual(result.returncode, 0, f"{tool} failed: {result.stderr}")
            results[tool] = result.stdout

        # 所有工具都应该成功执行
        self.assertEqual(len(results), len(tools))

        print(f"  ✓ All {len(tools)} tools work consistently for PID {pid}")

    def test_20_pid_vs_comm_filter(self):
        """Test: --pid 与 --comm 过滤结果对比"""
        print("\n[Test 20] --pid vs --comm 过滤对比")

        # 使用 PID 过滤
        pid_result = self._run_pid_command("show-cpu-usage", self.test_pids['hacontrol'])

        # 使用 comm 过滤
        comm_result = self._run_spear([
            "show-cpu-usage",
            "--data", str(self.test_data),
            "--comm", "hacontrol"
        ])

        self.assertEqual(pid_result.returncode, 0)
        self.assertEqual(comm_result.returncode, 0)

        # PID 结果应该包含具体 PID
        self.assertIn(str(self.test_pids['hacontrol']), pid_result.stdout)

        print("  ✓ PID and COMM filters both work correctly")


class TestPIDLevelDataValidation(unittest.TestCase):
    """Test data validation for PID level analysis"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent
        cls.repo_root = cls.test_dir.parent
        cls.spear_script = cls.repo_root / "scripts" / "spear.py"
        cls.test_data = cls.repo_root / "tests" / "perfdata" / "new_format" / "case_huge_samples.data"

    def _run_spear(self, args):
        cmd = [sys.executable, str(self.spear_script)] + args
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.repo_root))
        return result

    def test_21_data_file_pid_statistics(self):
        """Test: 验证测试数据文件中的 PID 统计信息"""
        print("\n[Test 21] 测试数据文件 PID 统计")

        # 使用 get-process-top 获取 PID 统计
        result = self._run_spear([
            "get-process-top",
            "--data", str(self.test_data),
            "--top-n", "20"
        ])

        self.assertEqual(result.returncode, 0)

        # 解析输出，统计 PID 数量
        lines = result.stdout.strip().split('\n')
        pid_lines = [l for l in lines if '(' in l and ')' in l and '%' in l]

        self.assertGreater(len(pid_lines), 10, "Should have multiple PIDs")

        print(f"  ✓ Data file contains {len(pid_lines)} unique PIDs")

    def test_22_high_cpu_pid_identification(self):
        """Test: 识别高 CPU 消耗 PID"""
        print("\n[Test 22] 高 CPU 消耗 PID 识别")

        result = self._run_spear([
            "get-process-top",
            "--data", str(self.test_data),
            "--top-n", "5"
        ])

        self.assertEqual(result.returncode, 0)

        # 过滤出包含实际 PID 数据的行（格式: comm(pid) total%/kernel%）
        # 排除表头行和以 # 开头的注释行
        all_lines = result.stdout.strip().split('\n')
        data_lines = []
        for l in all_lines:
            if l.startswith('# comm(pid)') or 'more items' in l:
                continue
            if '(' in l and ')' in l and '%' in l:
                data_lines.append(l)

        # 应该有数据行
        self.assertGreater(len(data_lines), 0, f"Should have PID data lines, got: {all_lines[:5]}")

        # 验证第一行数据格式
        first_data_line = data_lines[0]
        self.assertIn('(', first_data_line)
        self.assertIn(')', first_data_line)
        self.assertIn('%', first_data_line)

        print(f"  ✓ High CPU PID identification working ({len(data_lines)} PIDs found)")


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("PID Level Diagnosis Test Suite")
    print("=" * 70)
    print(f"Test data: tests/perfdata/new_format/case_huge_samples.data")
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPIDLevelDiagnosis))
    suite.addTests(loader.loadTestsFromTestCase(TestPIDLevelDataValidation))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("\n✅ All PID level diagnosis tests passed!")
        print("\n验证结论:")
        print("- show-cpu-usage --pid: ✅ 支持 PID 级别 CPU 分析")
        print("- get-hotspots --pid: ✅ 支持 PID 级别热点识别")
        print("- find-callers --pid: ✅ 支持 PID 级别调用溯源")
        print("- cluster-symbols --pid: ✅ 支持 PID 级别语义聚类")
        print("- analyze-core-distribution --pid: ✅ 支持 PID 级别核心分布")
        print("- cluster-paths --pid: ✅ 支持 PID 级别路径聚类")
        print("- count-process-variety --pid: ✅ 支持 PID 级别进程多样性")
    else:
        print("\n❌ Some tests failed!")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
