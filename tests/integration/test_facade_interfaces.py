#!/usr/bin/env python3
"""
Analysis Facade接口测试

验证AnalysisFacade对外暴露的接口:
- 接口可用性
- 返回数据格式
- 延迟加载机制
- 错误处理

运行: python3 tests/three_tier/test_facade_interfaces.py
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from perf_toolkit.core.engine import PerfExpertEngine
from perf_toolkit.core.engine_types import (
    ProcessLifecycle, LifecycleStats, CommCPUInfo, CoreCPUInfo, SymbolCPUInfo
)
from perf_toolkit.core.symbol import Symbol, SymbolStack


class MockEngine:
    """模拟Engine，用于隔离测试"""
    
    def __init__(self):
        # 使用SymbolStack而不是普通list
        self.samples = [
            {
                "ts": 1705312200.0,
                "cpu": 0,
                "pid": 1234,
                "comm": "nginx",
                "stack": SymbolStack([
                    Symbol.parse("epoll_wait"),
                    Symbol.parse("worker"),
                    Symbol.parse("main")
                ]),
                "cpu_util": 10.0
            },
            {
                "ts": 1705312200.1,
                "cpu": 0,
                "pid": 1235,
                "comm": "nginx",
                "stack": SymbolStack([
                    Symbol.parse("epoll_wait"),
                    Symbol.parse("worker"),
                    Symbol.parse("main")
                ]),
                "cpu_util": 12.0
            },
            {
                "ts": 1705312200.2,
                "cpu": 1,
                "pid": 5678,
                "comm": "python-worker",
                "stack": SymbolStack([
                    Symbol.parse("spinlock_[k]"),
                    Symbol.parse("worker"),
                    Symbol.parse("main")
                ]),
                "cpu_util": 95.0
            }
        ]
    
    def get_comm_cpu_util(self, samples):
        # 返回CommCPUInfo对象而不是dict
        return {
            "nginx": CommCPUInfo(
                comm="nginx",
                total_pct=22.0,
                kernel_pct=2.0,
                user_pct=20.0,
                pid_count=2
            ),
            "python-worker": CommCPUInfo(
                comm="python-worker",
                total_pct=95.0,
                kernel_pct=80.0,
                user_pct=15.0,
                pid_count=1
            )
        }
    
    def get_core_cpu_util(self, samples):
        # 返回CoreCPUInfo对象
        return {
            0: CoreCPUInfo(cpu_id=0, total_pct=50.0, kernel_pct=10.0, user_pct=40.0),
            1: CoreCPUInfo(cpu_id=1, total_pct=100.0, kernel_pct=80.0, user_pct=20.0)
        }
    
    def get_symbol_cpu_util(self, samples, comm=None, pid=None):
        # 返回SymbolCPUInfo对象
        return SymbolCPUInfo(
            self_pct={"spinlock_[k]": 80.0, "worker": 15.0},
            inclusive_pct={"spinlock_[k]": 80.0, "worker": 95.0},
            total_core_sec=100.0
        )
    
    def get_duration(self, samples=None):
        # 返回时间范围
        if not samples:
            return 0.0
        ts_list = [s.get("ts", 0) for s in samples]
        return max(ts_list) - min(ts_list) if ts_list else 0.0
    
    def get_sample_weight(self, sample):
        # 返回样本权重
        return sample.get("cpu_util", 1.0)
    
    def get_total_core_per_sec(self, samples):
        # 返回总核心秒数和样本数
        return (100.0, len(samples) if samples else 0)
    
    def get_pid_cpu_distribution(self, samples, comm):
        if comm == "nginx":
            return {1234: 10.0, 1235: 12.0}
        elif comm == "python-worker":
            return {5678: 95.0}
        return {}
    
    def get_process_lifecycle(self, samples, comm=None):
        # 返回ProcessLifecycle对象而不是dict
        return ProcessLifecycle(
            spawn_events=[],
            exit_events=[],
            spawn_rate=0.1,
            lifecycle_stats=LifecycleStats()
        )
    
    def get_filtered_samples(self, **kwargs):
        return self.samples


class TestFacadeInterface(unittest.TestCase):
    """Facade接口测试套件"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.mock_engine = MockEngine()
    
    def test_facade_initialization(self):
        """测试Facade初始化"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            self.assertIsNotNone(facade)
            self.assertIs(facade._engine, self.mock_engine)
        except ImportError:
            # Facade可能还未实现
            self.skipTest("AnalysisFacade尚未实现")
    
    def test_facade_lazy_loading(self):
        """测试Facade延迟加载机制"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            # 初始时_analyzers应该为空
            self.assertEqual(len(facade._analyzers), 0)
            
            # 访问某个analyzer后应该被缓存
            # 注意：这里依赖于具体实现
            analyzer = facade._get_analyzer("comm_top")
            self.assertIsNotNone(analyzer)
            
            # 再次访问应该返回缓存的实例
            analyzer2 = facade._get_analyzer("comm_top")
            self.assertIs(analyzer, analyzer2)
            
        except ImportError:
            self.skipTest("AnalysisFacade尚未实现")
    
    def test_analyze_comm_top_interface(self):
        """测试analyze_comm_top接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.analyze_comm_top(self.mock_engine.samples, top_n=10)
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据facade实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
            # 验证result结构
            result_data = result.get("result", {})
            if result_data.get("groups"):
                group = result_data["groups"][0]
                self.assertIn("comm", group)
                
        except ImportError:
            self.skipTest("AnalysisFacade或CommTopAnalyzer尚未实现")
    
    def test_analyze_comm_top_default_top_n(self):
        """测试analyze_comm_top默认top_n参数"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            # 不提供top_n参数
            result = facade.analyze_comm_top(self.mock_engine.samples)
            
            self.assertIsInstance(result, dict)
            self.assertIn("result", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade尚未实现")
    
    def test_analyze_hotspots_interface(self):
        """测试analyze_hotspots接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.analyze_hotspots(
                self.mock_engine.samples,
                comm="nginx",
                top_n=20
            )
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade或HotspotsAnalyzer尚未实现")
    
    def test_analyze_core_distribution_interface(self):
        """测试analyze_core_distribution接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.analyze_core_distribution(self.mock_engine.samples)
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade或CoreDistAnalyzer尚未实现")
    
    def test_detect_anomalies_interface(self):
        """测试detect_anomalies接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.detect_anomalies(
                self.mock_engine.samples,
                window_size=1.0,
                spike_threshold=0.5
            )
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade或AnomaliesAnalyzer尚未实现")
    
    def test_cluster_symbols_interface(self):
        """测试cluster_symbols接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.cluster_symbols(
                self.mock_engine.samples,
                top_n=10,
                comm="nginx"
            )
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade或SymbolClustersAnalyzer尚未实现")
    
    def test_cluster_paths_interface(self):
        """测试cluster_paths接口"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(self.mock_engine)
            
            result = facade.cluster_paths(
                self.mock_engine.samples,
                comm="nginx"
            )
            
            # 验证返回类型
            self.assertIsInstance(result, dict)
            
            # 验证必要字段（根据实际返回结构）
            self.assertIn("result", result)
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("AnalysisFacade或PathClusterAnalyzer尚未实现")


class TestFacadeErrorHandling(unittest.TestCase):
    """Facade错误处理测试"""
    
    def test_facade_with_empty_samples(self):
        """测试Facade处理空样本"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(MockEngine())
            
            result = facade.analyze_comm_top([])
            
            # 应该返回空结果但不抛出异常
            self.assertIsInstance(result, dict)
            # 检查结果结构 - result键下可能有groups
            result_data = result.get("result", {})
            self.assertEqual(result_data.get("groups", []), [])
            
        except ImportError:
            self.skipTest("AnalysisFacade尚未实现")
    
    def test_facade_with_none_samples(self):
        """测试Facade处理None样本"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            facade = AnalysisFacade(MockEngine())
            
            # 应该抛出异常或返回空结果
            try:
                result = facade.analyze_comm_top(None)
                # 如果不抛出异常，应该返回空结果
                self.assertIsInstance(result, dict)
            except (TypeError, AttributeError):
                # 抛出异常也是可接受的
                pass
                
        except ImportError:
            self.skipTest("AnalysisFacade尚未实现")


class TestFacadeInterfaceContract(unittest.TestCase):
    """Facade接口契约测试
    
    验证Facade接口的输入输出契约
    """
    
    def test_all_facade_methods_exist(self):
        """验证Facade暴露的所有方法"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            
            required_methods = [
                'analyze_comm_top',
                'analyze_hotspots',
                'analyze_core_distribution',
                'detect_anomalies',
                'cluster_paths',
                'cluster_symbols'
            ]
            
            for method in required_methods:
                self.assertTrue(
                    hasattr(AnalysisFacade, method),
                    f"AnalysisFacade缺少方法: {method}"
                )
                
        except ImportError:
            self.skipTest("AnalysisFacade尚未实现")


def run_tests():
    """运行所有Facade接口测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeInterface))
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeInterfaceContract))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
