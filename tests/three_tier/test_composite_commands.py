#!/usr/bin/env python3
"""
Composite命令测试

验证组合命令的功能:
- sys-audit: 系统审计流程
- bottleneck-trace: 瓶颈追踪流程
- storm-trace: 风暴溯源流程

运行: python3 tests/three_tier/test_composite_commands.py
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class MockAnalyzer:
    """模拟Analyzer返回值"""
    
    @staticmethod
    def mock_comm_top_result():
        """模拟CommTop分析结果"""
        return {
            "groups": [
                {
                    "comm": "app_worker",
                    "total_cpu": 12.0,
                    "count": 10,
                    "cv": 0.15,
                    "monopoly": 0.92,
                    "spawn_rate": 0.1,
                    "diagnosis": "BOTTLENECK"
                },
                {
                    "comm": "lsof",
                    "total_cpu": 400.0,
                    "count": 2000,
                    "cv": 0.02,
                    "monopoly": 0.01,
                    "spawn_rate": 85.0,
                    "diagnosis": "STORM"
                }
            ],
            "cv_analysis": {"app_worker": 0.15, "lsof": 0.02},
            "monopoly_scores": {"app_worker": 0.92, "lsof": 0.01},
            "spawn_rates": {"app_worker": 0.1, "lsof": 85.0},
            "recommendations": [
                {
                    "level": "critical",
                    "message": "app_worker 单核饱和",
                    "hint": "bottleneck-trace --comm app_worker"
                }
            ],
            "risks": [
                {
                    "level": "critical",
                    "message": "app_worker 单核饱和 (Monopoly=0.92)",
                    "hint": "bottleneck-trace --comm app_worker",
                    "patterns": ["SINGLE_CORE_SATURATION"],
                    "pending_targets": ["app_worker"]
                }
            ]
        }
    
    @staticmethod
    def mock_core_dist_result():
        """模拟Core分布分析结果"""
        return {
            "core_stats": [
                {"core_id": 0, "total_cpu": 50.0, "user_cpu": 40.0, "kernel_cpu": 10.0},
                {"core_id": 1, "total_cpu": 100.0, "user_cpu": 20.0, "kernel_cpu": 80.0},
                {"core_id": 2, "total_cpu": 30.0, "user_cpu": 25.0, "kernel_cpu": 5.0}
            ],
            "imbalance_score": 0.65,
            "saturated_cores": [1],
            "risks": []
        }
    
    @staticmethod
    def mock_anomalies_result():
        """模拟异常检测结果"""
        return {
            "anomalies": [
                {"timestamp": 1705312200.0, "cpu_spike": 80.0, "deviation": 3.5}
            ],
            "baseline": 45.0,
            "mutation_detected": True,
            "risks": [
                {
                    "level": "warning",
                    "message": "CPU突变 detected",
                    "hint": "sys-audit查看详情",
                    "patterns": ["CPU_MUTATION"],
                    "pending_targets": ["system"]
                }
            ]
        }
    
    @staticmethod
    def mock_hotspots_result():
        """模拟热点分析结果"""
        return {
            "hotspots": [
                {"symbol": "spinlock_[k]", "cpu_percent": 65.0, "resource_tag": "LOCK_CONTENTION"},
                {"symbol": "worker_loop", "cpu_percent": 20.0, "resource_tag": "USER_CODE"}
            ],
            "kernel_ratio": 80.0,
            "user_ratio": 20.0,
            "risks": [
                {
                    "level": "critical",
                    "message": "高内核态占比 (80%)",
                    "hint": "find-callers --target spinlock_[k]",
                    "patterns": ["HIGH_KERNEL_RATIO"],
                    "pending_targets": ["app_worker"]
                }
            ]
        }


class TestCompositeCommands(unittest.TestCase):
    """Composite命令测试套件"""
    
    def setUp(self):
        """测试前置"""
        self.temp_dir = tempfile.mkdtemp()
        self.trace_file = Path(self.temp_dir) / ".spear.json"
    
    def tearDown(self):
        """测试后置"""
        # 清理临时文件
        if self.trace_file.exists():
            self.trace_file.unlink()
        os.rmdir(self.temp_dir)


class TestSysAuditComposite(unittest.TestCase):
    """sys-audit组合命令测试"""
    
    def test_sys_audit_command_exists(self):
        """测试sys-audit命令存在"""
        try:
            from perf_toolkit.composite.sys_audit import cmd_sys_audit
            self.assertTrue(callable(cmd_sys_audit))
        except ImportError:
            self.skipTest("sys-audit尚未实现")
    
    def test_sys_audit_aggregation_logic(self):
        """测试sys-audit的Risk聚合逻辑"""
        # 模拟_aggregate_risks函数
        try:
            from perf_toolkit.composite.sys_audit import _aggregate_risks
            
            # 测试数据：混合risk
            risks = [
                {
                    "level": "critical",
                    "message": "app_worker 单核饱和",
                    "hint": "bottleneck-trace --comm app_worker",
                    "pending_targets": ["app_worker"]
                },
                {
                    "level": "warning",
                    "message": "CPU突变 detected",
                    "hint": "sys-audit查看详情",
                    "pending_targets": ["system"]
                }
            ]
            
            result = _aggregate_risks(risks)
            
            # 验证聚合结果
            self.assertEqual(result["level"], "critical")  # 最高级别
            self.assertIn("app_worker", result["message"])
            self.assertIn("bottleneck-trace", result["hint"])
            
        except ImportError:
            self.skipTest("sys-audit或_aggregate_risks尚未实现")
    
    def test_sys_audit_synthesize_logic(self):
        """测试sys-audit的综合分析逻辑"""
        try:
            from perf_toolkit.composite.sys_audit import _synthesize
            
            # 模拟输入
            anomalies = MockAnalyzer.mock_anomalies_result()
            core_dist = MockAnalyzer.mock_core_dist_result()
            comm_top = MockAnalyzer.mock_comm_top_result()
            
            result = _synthesize(anomalies, core_dist, comm_top)
            
            # 验证输出结构
            self.assertIn("primary_suspect", result)
            self.assertIn("secondary_loads", result)
            self.assertIn("background_noise", result)
            
            # 验证主要嫌疑人识别（应该识别出app_worker，而非lsof）
            if result["primary_suspect"]:
                self.assertEqual(result["primary_suspect"]["comm"], "app_worker")
                self.assertGreater(result["primary_suspect"]["monopoly"], 0.8)
            
        except ImportError:
            self.skipTest("sys-audit或_synthesize尚未实现")


class TestBottleneckTraceComposite(unittest.TestCase):
    """bottleneck-trace组合命令测试"""
    
    def test_bottleneck_trace_command_exists(self):
        """测试bottleneck-trace命令存在"""
        try:
            from perf_toolkit.composite.bottleneck_trace import cmd_bottleneck_trace
            self.assertTrue(callable(cmd_bottleneck_trace))
        except ImportError:
            self.skipTest("bottleneck-trace尚未实现")
    
    def test_bottleneck_detection_logic(self):
        """测试瓶颈检测逻辑"""
        try:
            from perf_toolkit.composite.bottleneck_trace import _find_bottleneck
            
            # 模拟CommTop结果
            comm_top = {
                "groups": [
                    {"comm": "nginx", "total_cpu": 150.0, "monopoly": 0.1, "diagnosis": "HEALTHY"},
                    {"comm": "app_worker", "total_cpu": 98.0, "monopoly": 0.95, "diagnosis": "BOTTLENECK"}
                ]
            }
            
            bottleneck = _find_bottleneck(comm_top)
            
            # 应该识别出monopoly最高的app_worker
            self.assertIsNotNone(bottleneck)
            self.assertEqual(bottleneck["comm"], "app_worker")
            self.assertGreater(bottleneck["monopoly"], 0.9)
            
        except ImportError:
            self.skipTest("bottleneck-trace或_find_bottleneck尚未实现")


class TestStormTraceComposite(unittest.TestCase):
    """storm-trace组合命令测试"""
    
    def test_storm_trace_command_exists(self):
        """测试storm-trace命令存在"""
        try:
            from perf_toolkit.composite.storm_trace import cmd_storm_trace
            self.assertTrue(callable(cmd_storm_trace))
        except ImportError:
            self.skipTest("storm-trace尚未实现")
    
    def test_storm_detection_logic(self):
        """测试风暴检测逻辑"""
        try:
            from perf_toolkit.composite.storm_trace import _detect_storm
            
            # 模拟CommTop结果（包含高spawn_rate）
            comm_top = {
                "groups": [
                    {
                        "comm": "lsof",
                        "total_cpu": 400.0,
                        "spawn_rate": 85.0,
                        "diagnosis": "STORM"
                    }
                ]
            }
            
            storm_info = _detect_storm(comm_top)
            
            # 应该识别出风暴
            self.assertIsNotNone(storm_info)
            self.assertEqual(storm_info["comm"], "lsof")
            self.assertGreater(storm_info["spawn_rate"], 10)
            
        except ImportError:
            self.skipTest("storm-trace或_detect_storm尚未实现")


class TestCompositeRiskAggregation(unittest.TestCase):
    """Composite Risk聚合算法测试"""
    
    def test_aggregate_empty_risks(self):
        """测试空risk列表聚合"""
        try:
            from perf_toolkit.composite.sys_audit import _aggregate_risks
            
            result = _aggregate_risks([])
            
            self.assertEqual(result["level"], "none")
            
        except ImportError:
            self.skipTest("_aggregate_risks尚未实现")
    
    def test_aggregate_single_risk(self):
        """测试单条risk聚合"""
        try:
            from perf_toolkit.composite.sys_audit import _aggregate_risks
            
            risks = [{
                "level": "warning",
                "message": "测试风险",
                "hint": "测试提示",
                "pending_targets": ["test"]
            }]
            
            result = _aggregate_risks(risks)
            
            self.assertEqual(result["level"], "warning")
            self.assertEqual(result["message"], "测试风险")
            
        except ImportError:
            self.skipTest("_aggregate_risks尚未实现")
    
    def test_aggregate_duplicate_targets(self):
        """测试相同target的risk去重"""
        try:
            from perf_toolkit.composite.sys_audit import _aggregate_risks
            
            risks = [
                {
                    "level": "warning",
                    "message": "风险1",
                    "hint": "提示1",
                    "pending_targets": ["target1"]
                },
                {
                    "level": "critical",
                    "message": "风险2",
                    "hint": "提示2",
                    "pending_targets": ["target1"]  # 相同target
                }
            ]
            
            result = _aggregate_risks(risks)
            
            # 应该取最高级别
            self.assertEqual(result["level"], "critical")
            # 应该包含target1
            self.assertIn("target1", result["pending_targets"])
            
        except ImportError:
            self.skipTest("_aggregate_risks尚未实现")


class TestCompositeOutputFormat(unittest.TestCase):
    """Composite输出格式测试"""
    
    def test_composite_output_structure(self):
        """测试Composite输出结构"""
        # 验证SysAuditOutput模型存在
        try:
            from perf_toolkit.core.output_models import SysAuditOutput, RiskInfo
            
            # 创建一个实例来验证字段
            output = SysAuditOutput(
                _risk=RiskInfo(level="info", message="test"),
                diagnosis={},
                details={}
            )
            
            # 验证必要字段
            self.assertTrue(hasattr(output, '_risk'))
            self.assertTrue(hasattr(output, 'diagnosis'))
            
        except (ImportError, AttributeError, TypeError):
            self.skipTest("SysAuditOutput模型尚未实现")


def run_tests():
    """运行所有Composite命令测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeCommands))
    suite.addTests(loader.loadTestsFromTestCase(TestSysAuditComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestBottleneckTraceComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestStormTraceComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeRiskAggregation))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeOutputFormat))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
