#!/usr/bin/env python3
"""
Core层接口测试

验证PerfExpertEngine新增接口的正确性:
- get_process_lifecycle()
- get_pid_cpu_distribution()
- get_call_graph()
- 现有接口兼容性

运行: python3 tests/three_tier/test_core_interfaces.py
"""

import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from perf_toolkit.core.engine import PerfExpertEngine


class TestCoreInterfaces(unittest.TestCase):
    """Core层接口测试套件"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.test_data_path = PROJECT_ROOT / "tests" / "perfdata" / "new_format" / "case_test.data"
        
        # 如果测试数据不存在，创建一个临时模拟数据文件
        if not cls.test_data_path.exists():
            cls._temp_data_file = PROJECT_ROOT / "tests" / "temp_mock.data"
            cls._create_mock_data_file()
            cls.engine = PerfExpertEngine(str(cls._temp_data_file))
        else:
            cls.engine = PerfExpertEngine(str(cls.test_data_path))
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        # 清理临时文件
        if hasattr(cls, '_temp_data_file') and cls._temp_data_file.exists():
            cls._temp_data_file.unlink()
    
    @classmethod
    def _create_mock_data_file(cls):
        """创建模拟数据文件"""
        import json
        mock_data = {
            "version": "1.0",
            "samples": [
                {
                    "ts": 1705312200.0,
                    "cpu": 0,
                    "pid": 1234,
                    "comm": "test_process",
                    "stack": ["func_a", "func_b", "main"],
                    "cpu_util": 10.0
                },
                {
                    "ts": 1705312200.1,
                    "cpu": 0,
                    "pid": 1234,
                    "comm": "test_process",
                    "stack": ["func_a", "func_b", "main"],
                    "cpu_util": 15.0
                },
                {
                    "ts": 1705312200.2,
                    "cpu": 1,
                    "pid": 5678,
                    "comm": "test_process",
                    "stack": ["syscall_[k]", "func_c", "main"],
                    "cpu_util": 80.0
                }
            ]
        }
        cls._temp_data_file.write_text(json.dumps(mock_data))
    

    
    # ========== 基础接口测试 ==========
    
    def test_get_comm_cpu_util_interface(self):
        """测试get_comm_cpu_util接口可用性"""
        from perf_toolkit.core.engine_types import CommCPUInfo
        result = self.engine.get_comm_cpu_util(self.engine.samples)
        
        # 验证返回类型
        self.assertIsInstance(result, dict)
        
        # 验证数据结构（如果有数据）
        if result:
            for comm, info in result.items():
                self.assertIsInstance(comm, str)
                self.assertIsInstance(info, CommCPUInfo)
                self.assertTrue(hasattr(info, "total_pct"))
                self.assertTrue(hasattr(info, "kernel_pct"))
                self.assertTrue(hasattr(info, "pid_count"))
    
    def test_get_filtered_samples_interface(self):
        """测试get_filtered_samples接口"""
        # 测试无过滤
        all_samples = self.engine.get_filtered_samples()
        self.assertIsInstance(all_samples, list)
        
        # 测试按comm过滤
        if all_samples:
            test_comm = all_samples[0].get("comm")
            filtered = self.engine.get_filtered_samples(comm=test_comm)
            self.assertIsInstance(filtered, list)
            for s in filtered:
                self.assertEqual(s.get("comm"), test_comm)
    
    # ========== 新增接口测试 ==========
    
    def test_get_process_lifecycle_interface(self):
        """测试get_process_lifecycle接口"""
        from perf_toolkit.core.engine_types import ProcessLifecycle
        result = self.engine.get_process_lifecycle(self.engine.samples)
        
        # 验证返回类型是ProcessLifecycle对象
        self.assertIsInstance(result, ProcessLifecycle)
        
        # 验证必要字段
        self.assertTrue(hasattr(result, "spawn_events"))
        self.assertTrue(hasattr(result, "exit_events"))
        self.assertTrue(hasattr(result, "spawn_rate"))
        self.assertTrue(hasattr(result, "lifecycle_stats"))
        
        # 验证类型
        self.assertIsInstance(result.spawn_events, list)
        self.assertIsInstance(result.exit_events, list)
        self.assertIsInstance(result.spawn_rate, (int, float))
    
    def test_get_process_lifecycle_with_comm_filter(self):
        """测试get_process_lifecycle带comm过滤"""
        from perf_toolkit.core.engine_types import ProcessLifecycle
        if not self.engine.samples:
            return
            
        test_comm = self.engine.samples[0].get("comm")
        result = self.engine.get_process_lifecycle(
            self.engine.samples, 
            comm=test_comm
        )
        
        self.assertIsInstance(result, ProcessLifecycle)
        self.assertTrue(hasattr(result, "spawn_rate"))
    
    def test_get_pid_cpu_distribution_interface(self):
        """测试get_pid_cpu_distribution接口"""
        if not self.engine.samples:
            return
            
        test_comm = self.engine.samples[0].get("comm")
        result = self.engine.get_pid_cpu_distribution(
            self.engine.samples,
            test_comm
        )
        
        # 验证返回类型
        self.assertIsInstance(result, dict)
        
        # 验证键值类型
        for pid, cpu in result.items():
            self.assertIsInstance(pid, int)
            self.assertIsInstance(cpu, (int, float))
            self.assertGreaterEqual(cpu, 0)
    
    def test_get_pid_cpu_distribution_empty(self):
        """测试get_pid_cpu_distribution空数据"""
        result = self.engine.get_pid_cpu_distribution([], "nonexistent")
        self.assertEqual(result, {})
    
    def test_get_call_graph_interface(self):
        """测试get_call_graph接口"""
        from perf_toolkit.core.engine_types import CallGraph
        if not self.engine.samples:
            return
            
        result = self.engine.get_call_graph(
            self.engine.samples,
            target_symbol="func_a"
        )
        
        # 验证返回类型是CallGraph对象
        self.assertIsInstance(result, CallGraph)
        
        # 验证必要字段
        self.assertTrue(hasattr(result, "callers"))
        self.assertTrue(hasattr(result, "call_graph"))
        self.assertTrue(hasattr(result, "hot_paths"))
        
        # 验证类型
        self.assertIsInstance(result.callers, list)
        self.assertIsInstance(result.call_graph, dict)
        self.assertIsInstance(result.hot_paths, list)
    
    def test_get_call_graph_with_comm_filter(self):
        """测试get_call_graph带comm过滤"""
        from perf_toolkit.core.engine_types import CallGraph
        if not self.engine.samples:
            return
            
        test_comm = self.engine.samples[0].get("comm")
        result = self.engine.get_call_graph(
            self.engine.samples,
            target_symbol="main",
            comm=test_comm
        )
        
        self.assertIsInstance(result, CallGraph)
        self.assertTrue(hasattr(result, "callers"))


class TestCoreDataAccessControl(unittest.TestCase):
    """Core层数据访问控制测试"""
    
    def test_engine_is_single_source_of_truth(self):
        """验证Engine是数据的唯一来源"""
        # 创建一个临时文件用于初始化Engine
        import tempfile
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.data', delete=False) as f:
            json.dump({"version": "1.0", "samples": []}, f)
            temp_path = f.name
        
        try:
            engine = PerfExpertEngine(temp_path)
            
            # Analysis层应该只能通过Engine接口获取数据
            # 这个测试验证Engine提供的接口完整性
            required_methods = [
                'get_comm_cpu_util',
                'get_core_cpu_util',
                'get_filtered_samples',
                'get_process_lifecycle',
                'get_pid_cpu_distribution',
                'get_call_graph',
                'get_time_range'
            ]
            
            for method in required_methods:
                self.assertTrue(
                    hasattr(engine, method),
                    f"Engine缺少必要接口: {method}"
                )
        finally:
            import os
            os.unlink(temp_path)


class TestCoreCVAndMonopoly(unittest.TestCase):
    """Core层CV和Monopoly计算工具函数测试"""
    
    def test_calculate_cv_uniform_distribution(self):
        """测试均匀分布的CV计算（应该接近0）"""
        from perf_toolkit.analysis.comm_top import CommTopAnalyzer
        
        analyzer = CommTopAnalyzer(None)
        # 均匀分布: 所有值相同
        pid_dist = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
        cv = analyzer._calculate_cv(pid_dist)
        
        self.assertAlmostEqual(cv, 0.0, places=2)
    
    def test_calculate_cv_high_variance(self):
        """测试高方差分布的CV计算"""
        from perf_toolkit.analysis.comm_top import CommTopAnalyzer
        
        analyzer = CommTopAnalyzer(None)
        # 高方差分布: 一个值很大，其他很小
        pid_dist = {1: 90.0, 2: 1.0, 3: 1.0, 4: 1.0}
        cv = analyzer._calculate_cv(pid_dist)
        
        # CV应该大于1（表示高度不均匀）
        self.assertGreater(cv, 1.0)
    
    def test_calculate_monopoly_single_pid(self):
        """测试单PID的Monopoly（应该为1.0）"""
        from perf_toolkit.analysis.comm_top import CommTopAnalyzer
        
        analyzer = CommTopAnalyzer(None)
        pid_dist = {1: 100.0}
        monopoly = analyzer._calculate_monopoly(pid_dist)
        
        self.assertAlmostEqual(monopoly, 1.0, places=2)
    
    def test_calculate_monopoly_uniform(self):
        """测试均匀分布的Monopoly"""
        from perf_toolkit.analysis.comm_top import CommTopAnalyzer
        
        analyzer = CommTopAnalyzer(None)
        # 4个PID平均分配
        pid_dist = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}
        monopoly = analyzer._calculate_monopoly(pid_dist)
        
        # Monopoly应该为0.25
        self.assertAlmostEqual(monopoly, 0.25, places=2)


def run_tests():
    """运行所有Core层测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestCoreInterfaces))
    suite.addTests(loader.loadTestsFromTestCase(TestCoreDataAccessControl))
    suite.addTests(loader.loadTestsFromTestCase(TestCoreCVAndMonopoly))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
