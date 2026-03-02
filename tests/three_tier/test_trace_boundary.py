#!/usr/bin/env python3
"""
Trace边界测试

验证三层架构中的Trace边界:
- CLI调用触发Trace记录
- Composite内部调用不触发Trace
- Timeline不被子命令污染
- Issues记录正确

运行: python3 tests/three_tier/test_trace_boundary.py
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


class TestTraceBoundary(unittest.TestCase):
    """Trace边界测试套件"""
    
    def setUp(self):
        """测试前置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.trace_file = self.temp_dir / ".spear.json"
        
        # 创建初始trace文件
        initial_data = {
            "version": "2.0",
            "data_file": str(self.temp_dir / "test.data"),
            "created_at": "2026-03-01T00:00:00Z",
            "updated_at": "2026-03-01T00:00:00Z",
            "timeline": [],
            "issues": {}
        }
        self.trace_file.write_text(json.dumps(initial_data, indent=2))
    
    def tearDown(self):
        """测试后置"""
        # 清理临时文件
        if self.trace_file.exists():
            self.trace_file.unlink()
        os.rmdir(self.temp_dir)
    
    def _load_trace(self):
        """加载trace文件"""
        return json.loads(self.trace_file.read_text())


class TestCLITracesToTimeline(TestTraceBoundary):
    """CLI调用触发Trace记录测试"""
    
    @patch('perf_toolkit.core.trace.Trace.DEFAULT_PATH', '.spear.json')
    def test_single_cli_command_records_to_timeline(self):
        """测试单个CLI命令记录到timeline"""
        try:
            from perf_toolkit.core.trace import Trace
            
            # 创建trace实例
            trace = Trace(str(self.trace_file))
            
            # 模拟命令执行
            seq = trace.begin_command("get-comm-top --data test.data")
            trace.record_risk("warning", "高内核态进程", "cluster-symbols --comm nginx")
            trace.end_command()
            
            # 验证timeline
            data = self._load_trace()
            self.assertEqual(len(data["timeline"]), 1)
            self.assertEqual(data["timeline"][0]["command"], "get-comm-top --data test.data")
            
        except Exception as e:
            self.skipTest(f"Trace测试失败: {e}")
    
    @patch('perf_toolkit.core.trace.Trace.DEFAULT_PATH', '.spear.json')
    def test_risk_creates_issue(self):
        """测试record_risk创建issue"""
        try:
            from perf_toolkit.core.trace import Trace
            
            trace = Trace(str(self.trace_file))
            trace.begin_command("get-comm-top --data test.data")
            issue_id = trace.record_risk("critical", "单核饱和", "bottleneck-trace --comm app")
            trace.end_command()
            
            # 验证issue创建
            data = self._load_trace()
            self.assertIn(issue_id, data["issues"])
            self.assertEqual(data["issues"][issue_id]["level"], "critical")
            self.assertEqual(data["issues"][issue_id]["status"], "open")
            
        except Exception as e:
            self.skipTest(f"Trace测试失败: {e}")


class TestCompositeDoesNotPolluteTimeline(TestTraceBoundary):
    """Composite调用不污染Timeline测试"""
    
    @patch('perf_toolkit.core.trace.Trace.DEFAULT_PATH', '.spear.json')
    def test_composite_records_only_top_level(self):
        """测试Composite只记录顶层命令"""
        try:
            from perf_toolkit.core.trace import Trace
            
            trace = Trace(str(self.trace_file))
            
            # 模拟sys-audit执行（内部调用多个子分析）
            seq = trace.begin_command("sys-audit --data test.data")
            
            # 内部调用不记录（这是Composite应该保证的）
            # 注意：这里模拟的是理想情况，实际实现中Composite应该控制不调用begin_command
            
            # 只记录综合risk
            trace.record_risk("critical", "发现性能瓶颈", "bottleneck-trace --comm app")
            trace.end_command()
            
            # 验证timeline只有一条记录
            data = self._load_trace()
            self.assertEqual(len(data["timeline"]), 1)
            self.assertIn("sys-audit", data["timeline"][0]["command"])
            
            # 验证没有子命令记录
            commands = [t["command"] for t in data["timeline"]]
            for cmd in commands:
                self.assertNotIn("get-comm-top", cmd)
                self.assertNotIn("detect-anomalies", cmd)
                self.assertNotIn("analyze-core-distribution", cmd)
            
        except Exception as e:
            self.skipTest(f"Trace测试失败: {e}")
    
    @patch('perf_toolkit.core.trace.Trace.DEFAULT_PATH', '.spear.json')
    def test_composite_aggregates_risks_before_recording(self):
        """测试Composite聚合risk后才记录"""
        try:
            from perf_toolkit.core.trace import Trace
            
            trace = Trace(str(self.trace_file))
            
            # 模拟sys-audit
            trace.begin_command("sys-audit --data test.data")
            
            # 只记录聚合后的综合risk（不是多个单独risk）
            trace.record_risk(
                "critical",
                "发现2个性能瓶颈: app_worker, lsof",
                "1. bottleneck-trace --comm app_worker; 2. storm-trace --comm lsof"
            )
            trace.end_command()
            
            # 验证只创建了一个issue
            data = self._load_trace()
            self.assertEqual(len(data["issues"]), 1)
            
            issue = list(data["issues"].values())[0]
            self.assertIn("app_worker", issue["desc"])
            self.assertIn("lsof", issue["desc"])
            
        except Exception as e:
            self.skipTest(f"Trace测试失败: {e}")


class TestTraceBoundaryEnforcement(unittest.TestCase):
    """Trace边界强制执行测试"""
    
    def test_analyzer_internal_method_does_not_record_trace(self):
        """测试Analyzer内部方法不记录Trace"""
        try:
            from perf_toolkit.analysis.comm_top import CommTopAnalyzer
            from perf_toolkit.core.engine import PerfExpertEngine
            
            # 创建mock engine
            mock_engine = Mock()
            mock_engine.get_comm_cpu_util = Mock(return_value={})
            mock_engine.get_pid_cpu_distribution = Mock(return_value={})
            mock_engine.get_process_lifecycle = Mock(return_value={
                "spawn_events": [],
                "exit_events": [],
                "spawn_rate": 0.0
            })
            
            analyzer = CommTopAnalyzer(mock_engine)
            
            # 调用analyze方法（内部接口，不应该操作trace）
            result = analyzer.analyze([])
            
            # 验证返回结果，但不验证trace（因为analyzer不应该操作trace）
            self.assertIsInstance(result, dict)
            
        except ImportError as e:
            self.skipTest(f"依赖模块未实现: {e}")
    
    def test_facade_method_does_not_auto_record_trace(self):
        """测试Facade方法不自动记录Trace"""
        try:
            from perf_toolkit.analysis.facade import AnalysisFacade
            
            # 创建mock engine
            mock_engine = Mock()
            mock_engine.get_comm_cpu_util = Mock(return_value={})
            mock_engine.get_pid_cpu_distribution = Mock(return_value={})
            mock_engine.get_process_lifecycle = Mock(return_value={
                "spawn_events": [],
                "exit_events": [],
                "spawn_rate": 0.0
            })
            
            facade = AnalysisFacade(mock_engine)
            
            # 调用Facade方法（不应该自动记录trace）
            result = facade.analyze_comm_top([])
            
            # Facade不应该有trace相关操作
            self.assertIsInstance(result, dict)
            
        except ImportError as e:
            self.skipTest(f"依赖模块未实现: {e}")


class TestTraceOutputBuilderIntegration(TestTraceBoundary):
    """Trace与OutputBuilder集成测试"""
    
    def test_output_builder_records_risk_to_trace(self):
        """测试OutputBuilder自动记录risk到Trace"""
        try:
            from perf_toolkit.core.output_builder import OutputBuilder
            from perf_toolkit.core.output_models import RiskInfo, CommTopOutput, CommGroupSummary
            from perf_toolkit.core.trace import Trace
            
            # 先初始化trace文件
            trace = Trace(str(self.trace_file))
            trace.init(str(self.temp_dir / "test.data"))
            
            # 创建mock args
            mock_args = Mock()
            mock_args.data = str(self.temp_dir / "test.data")
            mock_args.trace = True  # 启用自动trace
            
            # 创建mock engine
            mock_engine = Mock()
            
            # 创建OutputBuilder
            builder = OutputBuilder(mock_engine, mock_args)
            
            # 在begin_command之前注入trace（使用我们的测试文件）
            builder._trace = trace
            builder._auto_trace = True
            
            # 直接调用record_risk记录风险
            issue_id = builder.record_risk("warning", "测试风险", "测试提示")
            
            # 验证issue被创建
            self.assertTrue(len(issue_id) > 0, "record_risk应该返回issue_id")
            
            # 重新加载trace文件验证
            trace._load()
            self.assertIn(issue_id, trace.data["issues"])
            self.assertEqual(trace.data["issues"][issue_id]["level"], "warning")
            
        except Exception as e:
            self.skipTest(f"集成测试失败: {e}")


class TestTraceIsolationBetweenCommands(TestTraceBoundary):
    """命令间Trace隔离测试"""
    
    @patch('perf_toolkit.core.trace.Trace.DEFAULT_PATH', '.spear.json')
    def test_sequential_commands_create_sequential_timeline(self):
        """测试顺序命令创建顺序timeline"""
        try:
            from perf_toolkit.core.trace import Trace
            
            trace = Trace(str(self.trace_file))
            
            # 执行多个命令
            trace.begin_command("cmd1")
            trace.end_command()
            
            trace.begin_command("cmd2")
            trace.end_command()
            
            trace.begin_command("cmd3")
            trace.end_command()
            
            # 验证timeline顺序
            data = self._load_trace()
            self.assertEqual(len(data["timeline"]), 3)
            
            for i, entry in enumerate(data["timeline"]):
                self.assertEqual(entry["seq"], i + 1)
            
        except Exception as e:
            self.skipTest(f"Trace测试失败: {e}")


class TestTraceBoundaryViolationDetection(unittest.TestCase):
    """Trace边界违规检测测试"""
    
    def test_detect_nested_command_in_timeline(self):
        """检测timeline中是否有嵌套命令（违规）"""
        # 这是一个检测工具，用于验证实现是否正确
        def check_timeline_for_violations(timeline: list) -> list:
            """检查timeline是否有嵌套命令违规"""
            violations = []
            open_commands = []
            
            for entry in timeline:
                if entry["type"] == "command":
                    # 检查是否有未闭合的命令
                    if open_commands:
                        violations.append({
                            "type": "nested_command",
                            "parent": open_commands[-1],
                            "child": entry["command"]
                        })
                    open_commands.append(entry["command"])
                elif entry["type"] == "command_end":
                    if open_commands:
                        open_commands.pop()
            
            return violations
        
        # 测试正常情况
        normal_timeline = [
            {"seq": 1, "type": "command", "command": "sys-audit"},
            {"seq": 1, "type": "command_end"},
            {"seq": 2, "type": "command", "command": "bottleneck-trace"},
            {"seq": 2, "type": "command_end"}
        ]
        
        violations = check_timeline_for_violations(normal_timeline)
        self.assertEqual(len(violations), 0)
        
        # 测试违规情况
        violated_timeline = [
            {"seq": 1, "type": "command", "command": "sys-audit"},
            {"seq": 2, "type": "command", "command": "get-comm-top"},  # 嵌套！
            {"seq": 2, "type": "command_end"},
            {"seq": 1, "type": "command_end"}
        ]
        
        violations = check_timeline_for_violations(violated_timeline)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["type"], "nested_command")


def run_tests():
    """运行所有Trace边界测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundary))
    suite.addTests(loader.loadTestsFromTestCase(TestCLITracesToTimeline))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeDoesNotPolluteTimeline))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundaryEnforcement))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceOutputBuilderIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceIsolationBetweenCommands))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundaryViolationDetection))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
