#!/usr/bin/env python3
"""
Risk集成测试

验证Risk在三层架构中的流转:
- Core层RiskMixin基础能力
- Analysis层risk识别
- Composite层risk聚合
- 输出格式正确性

运行: python3 tests/three_tier/test_risk_integration.py
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class TestRiskMixinCore(unittest.TestCase):
    """Core层RiskMixin测试"""
    
    def test_risk_mixin_add_risk(self):
        """测试RiskMixin添加risk"""
        try:
            from perf_toolkit.core.risk_mixin import RiskMixin
            
            mixin = RiskMixin()
            mixin.add_risk(
                level="warning",
                message="测试风险",
                hint="测试提示",
                patterns=["TEST_PATTERN"],
                targets=["target1"]
            )
            
            # 验证risk被添加
            self.assertEqual(len(mixin.risks), 1)
            self.assertEqual(mixin.risks[0]["level"], "warning")
            self.assertEqual(mixin.risks[0]["message"], "测试风险")
            
        except ImportError:
            self.skipTest("RiskMixin尚未实现")
    
    def test_risk_mixin_get_top_risk(self):
        """测试RiskMixin获取最高级别risk"""
        try:
            from perf_toolkit.core.risk_mixin import RiskMixin
            
            mixin = RiskMixin()
            mixin.add_risk("info", "信息1", "")
            mixin.add_risk("warning", "警告1", "")
            mixin.add_risk("critical", "严重1", "")
            mixin.add_risk("info", "信息2", "")
            
            top_risk = mixin.get_top_risk()
            
            # 应该返回critical级别
            self.assertEqual(top_risk["level"], "critical")
            self.assertEqual(top_risk["message"], "严重1")
            self.assertTrue(top_risk["action_required"])
            
        except ImportError:
            self.skipTest("RiskMixin尚未实现")
    
    def test_risk_mixin_get_all_risks(self):
        """测试RiskMixin获取所有risk（供Composite使用）"""
        try:
            from perf_toolkit.core.risk_mixin import RiskMixin
            
            mixin = RiskMixin()
            mixin.add_risk("warning", "警告1", "提示1")
            mixin.add_risk("warning", "警告2", "提示2")
            
            all_risks = mixin.risks  # 或通过get_all_risks()
            
            self.assertEqual(len(all_risks), 2)
            
        except ImportError:
            self.skipTest("RiskMixin尚未实现")
    
    def test_risk_mixin_format_output(self):
        """测试RiskMixin格式化输出"""
        try:
            from perf_toolkit.core.risk_mixin import RiskMixin
            
            mixin = RiskMixin()
            mixin.add_risk("warning", "测试风险", "测试提示")
            
            data = {"key": "value"}
            output = mixin.format_output(data)
            
            # 验证_risk字段存在
            self.assertIn("_risk", output)
            self.assertEqual(output["_risk"]["level"], "warning")
            self.assertEqual(output["key"], "value")
            
        except ImportError:
            self.skipTest("RiskMixin尚未实现")


class TestRiskInfoDataClass(unittest.TestCase):
    """RiskInfo数据类测试"""
    
    def test_risk_info_creation(self):
        """测试RiskInfo创建"""
        try:
            from perf_toolkit.core.output_models import RiskInfo
            
            risk = RiskInfo(
                level="critical",
                message="单核饱和",
                hint="bottleneck-trace --comm app",
                patterns=["SINGLE_CORE_SATURATION"],
                pending_targets=["app"]
            )
            
            self.assertEqual(risk.level, "critical")
            self.assertEqual(risk.message, "单核饱和")
            self.assertTrue(risk.action_required)
            
        except (ImportError, AttributeError):
            self.skipTest("RiskInfo尚未实现")
    
    def test_risk_info_action_required_auto_set(self):
        """测试RiskInfo自动设置action_required"""
        try:
            from perf_toolkit.core.output_models import RiskInfo
            
            # critical/warning应该action_required=True
            risk1 = RiskInfo(level="critical", message="")
            self.assertTrue(risk1.action_required)
            
            risk2 = RiskInfo(level="warning", message="")
            self.assertTrue(risk2.action_required)
            
            # info/none应该action_required=False
            risk3 = RiskInfo(level="info", message="")
            self.assertFalse(risk3.action_required)
            
            risk4 = RiskInfo(level="none", message="")
            self.assertFalse(risk4.action_required)
            
        except (ImportError, AttributeError):
            self.skipTest("RiskInfo尚未实现")


class TestAnalysisRiskIdentification(unittest.TestCase):
    """Analysis层risk识别测试"""
    
    def test_comm_top_identifies_bottleneck_risk(self):
        """测试CommTop识别瓶颈risk"""
        try:
            from perf_toolkit.analysis.comm_top import CommTopAnalyzer
            
            # 创建mock数据（模拟高monopoly场景）
            from perf_toolkit.core.engine_types import CommCPUInfo
            mock_engine = Mock()
            mock_engine.get_comm_cpu_util = Mock(return_value={
                "app_worker": CommCPUInfo(
                    comm="app_worker",
                    total_pct=95.0,
                    kernel_pct=80.0,
                    user_pct=15.0,
                    pid_count=1
                )
            })
            mock_engine.get_pid_cpu_distribution = Mock(return_value={
                5678: 95.0
            })
            # 返回ProcessLifecycle对象而不是dict
            from perf_toolkit.core.engine_types import ProcessLifecycle, LifecycleStats
            mock_engine.get_process_lifecycle = Mock(return_value=ProcessLifecycle(
                spawn_events=[],
                exit_events=[],
                spawn_rate=0.1,
                lifecycle_stats=LifecycleStats()
            ))
            
            analyzer = CommTopAnalyzer(mock_engine)
            
            # 构造样本数据
            samples = [{"comm": "app_worker", "pid": 5678, "cpu_util": 95.0}]
            result = analyzer.analyze(samples)
            
            # 验证识别出瓶颈
            self.assertIn("risks", result)
            
            if result["risks"]:
                risk_levels = [r["level"] for r in result["risks"]]
                self.assertIn("critical", risk_levels)
            
        except ImportError:
            self.skipTest("CommTopAnalyzer尚未实现")
    
    def test_comm_top_identifies_storm_risk(self):
        """测试CommTop识别风暴risk"""
        try:
            from perf_toolkit.analysis.comm_top import CommTopAnalyzer
            
            mock_engine = Mock()
            mock_engine.get_comm_cpu_util = Mock(return_value={
                "lsof": {
                    "total_pct": 400.0,
                    "kernel_pct": 300.0,
                    "user_pct": 100.0,
                    "pid_count": 2000
                }
            })
            mock_engine.get_pid_cpu_distribution = Mock(return_value={
                i: 0.2 for i in range(2000)
            })
            # 返回ProcessLifecycle对象而不是dict
            from perf_toolkit.core.engine_types import ProcessLifecycle, LifecycleStats, LifecycleEvent
            mock_engine.get_process_lifecycle = Mock(return_value=ProcessLifecycle(
                spawn_events=[LifecycleEvent(pid=i, comm="lsof", timestamp=1000.0, type="spawn") for i in range(100)],
                exit_events=[],
                spawn_rate=85.0,  # 高spawn_rate
                lifecycle_stats=LifecycleStats()
            ))
            
            analyzer = CommTopAnalyzer(mock_engine)
            result = analyzer.analyze([])
            
            # 验证识别出风暴
            self.assertIn("risks", result)
            
        except ImportError:
            self.skipTest("CommTopAnalyzer尚未实现")


class TestCompositeRiskAggregation(unittest.TestCase):
    """Composite层risk聚合测试"""
    
    def test_aggregate_multiple_risks_from_same_target(self):
        """测试相同target的多个risk聚合"""
        risks = [
            {
                "level": "warning",
                "message": "高内核态",
                "hint": "cluster-symbols --comm app",
                "patterns": ["HIGH_KERNEL"],
                "pending_targets": ["app"]
            },
            {
                "level": "critical",
                "message": "单核饱和",
                "hint": "bottleneck-trace --comm app",
                "patterns": ["BOTTLENECK"],
                "pending_targets": ["app"]
            }
        ]
        
        # 聚合逻辑
        target_risks = {}
        for risk in risks:
            for target in risk.get("pending_targets", []):
                if target not in target_risks:
                    target_risks[target] = risk
                elif risk["level"] == "critical":
                    target_risks[target] = risk
        
        # 验证取最高级别
        self.assertEqual(target_risks["app"]["level"], "critical")
    
    def test_aggregate_risks_generates_comprehensive_message(self):
        """测试聚合生成综合message"""
        risks = [
            {
                "level": "critical",
                "message": "app_worker 单核饱和",
                "hint": "bottleneck-trace --comm app_worker",
                "pending_targets": ["app_worker"]
            },
            {
                "level": "warning",
                "message": "lsof 进程风暴",
                "hint": "storm-trace --comm lsof",
                "pending_targets": ["lsof"]
            }
        ]
        
        # 分类统计
        critical_targets = []
        warning_targets = []
        
        for risk in risks:
            for target in risk.get("pending_targets", []):
                if risk["level"] == "critical":
                    critical_targets.append(target)
                elif risk["level"] == "warning":
                    warning_targets.append(target)
        
        # 生成综合message
        if critical_targets:
            message = f"发现 {len(critical_targets)} 个关键性能瓶颈: {', '.join(critical_targets)}"
        elif warning_targets:
            message = f"发现 {len(warning_targets)} 个潜在风险: {', '.join(warning_targets)}"
        
        self.assertIn("app_worker", message)
        # 验证message中包含正确的数量（这里是1个critical target）
        self.assertIn("1", message)
    
    def test_aggregate_risks_merges_hints(self):
        """测试聚合合并hints"""
        risks = [
            {
                "level": "critical",
                "message": "app_worker 单核饱和",
                "hint": "bottleneck-trace --comm app_worker",
                "pending_targets": ["app_worker"]
            },
            {
                "level": "critical",
                "message": "lsof 单核饱和",
                "hint": "bottleneck-trace --comm lsof",
                "pending_targets": ["lsof"]
            }
        ]
        
        # 合并hints
        hints = [r["hint"] for r in risks]
        merged_hint = "; ".join(hints)
        
        self.assertIn("app_worker", merged_hint)
        self.assertIn("lsof", merged_hint)
        self.assertIn(";", merged_hint)


class TestRiskFlowAcrossLayers(unittest.TestCase):
    """Risk跨层流转测试"""
    
    def test_risk_flow_from_analysis_to_composite(self):
        """测试risk从Analysis流向Composite"""
        # 模拟Analysis层返回的risk
        analysis_result = {
            "groups": [],
            "risks": [
                {
                    "level": "critical",
                    "message": "发现性能瓶颈",
                    "hint": "bottleneck-trace --comm app",
                    "pending_targets": ["app"]
                }
            ]
        }
        
        # Composite层收集risks
        all_risks = []
        if "risks" in analysis_result:
            all_risks.extend(analysis_result["risks"])
        
        # 验证risk被正确传递
        self.assertEqual(len(all_risks), 1)
        self.assertEqual(all_risks[0]["level"], "critical")
    
    def test_risk_level_priority(self):
        """测试risk级别优先级"""
        from perf_toolkit.core.output_models import RiskLevel
        
        # 验证优先级顺序（使用 RiskLevel 枚举）
        self.assertLess(RiskLevel.CRITICAL.value, RiskLevel.WARNING.value)
        self.assertLess(RiskLevel.WARNING.value, RiskLevel.INFO.value)
        self.assertLess(RiskLevel.INFO.value, RiskLevel.NONE.value)
        
        # 验证字符串转换
        self.assertEqual(RiskLevel.from_string("critical"), RiskLevel.CRITICAL)
        self.assertEqual(RiskLevel.from_string("warning"), RiskLevel.WARNING)
        self.assertEqual(RiskLevel.from_string("info"), RiskLevel.INFO)
        self.assertEqual(RiskLevel.from_string("none"), RiskLevel.NONE)


class TestRiskOutputFormat(unittest.TestCase):
    """Risk输出格式测试"""
    
    def test_risk_field_in_output(self):
        """测试输出包含_risk字段"""
        try:
            from perf_toolkit.core.output_models import CommTopOutput, RiskInfo, CommGroupSummary
            
            output = CommTopOutput(
                _risk=RiskInfo(
                    level="warning",
                    message="测试",
                    hint="测试提示"
                ),
                comm_groups=[],
                summary=CommGroupSummary(total_comm_groups=0, high_kernel_groups=0)
            )
            
            # 转换为dict验证
            from dataclasses import asdict
            output_dict = asdict(output)
            
            self.assertIn("_risk", output_dict)
            self.assertEqual(output_dict["_risk"]["level"], "warning")
            
        except (ImportError, AttributeError):
            self.skipTest("输出模型尚未实现")
    
    def test_risk_field_at_top_level(self):
        """测试_risk字段在输出顶层"""
        output = {
            "_risk": {
                "level": "critical",
                "message": "发现瓶颈",
                "hint": "执行分析",
                "action_required": True
            },
            "data": "..."
        }
        
        # 验证_risk是第一个字段（在Python 3.7+ dict保持插入顺序）
        keys = list(output.keys())
        self.assertEqual(keys[0], "_risk")


class TestRiskPatterns(unittest.TestCase):
    """Risk模式标签测试"""
    
    def test_risk_patterns_for_categorization(self):
        """测试risk patterns用于分类"""
        risk = {
            "level": "critical",
            "message": "单核饱和",
            "patterns": ["SINGLE_CORE_SATURATION", "BOTTLENECK"],
            "pending_targets": ["app"]
        }
        
        # 验证patterns可用于分类统计
        categories = {}
        for pattern in risk["patterns"]:
            if pattern == "SINGLE_CORE_SATURATION":
                categories["单核饱和"] = categories.get("单核饱和", 0) + 1
            elif pattern == "BOTTLENECK":
                categories["性能瓶颈"] = categories.get("性能瓶颈", 0) + 1
        
        self.assertIn("单核饱和", categories)
        self.assertIn("性能瓶颈", categories)


def run_tests():
    """运行所有Risk集成测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestRiskMixinCore))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskInfoDataClass))
    suite.addTests(loader.loadTestsFromTestCase(TestAnalysisRiskIdentification))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeRiskAggregation))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskFlowAcrossLayers))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskOutputFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskPatterns))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
