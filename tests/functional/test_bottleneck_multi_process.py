#!/usr/bin/env python3
"""
测试: bottleneck-analyze 多 BOTTLENECK 进程识别

验证点:
1. _find_all_bottleneck_comms 能找到所有 BOTTLENECK 进程
2. sys-audit 的 recommendations 包含所有 BOTTLENECK 的追踪建议
3. bottleneck-analyze 的 risk hint 提示其他待追踪的瓶颈
"""

import sys
import os
import unittest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from config.defaults import DiagnosisType
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.core.engine import PerfExpertEngine
from perf_toolkit.composite.bottleneck_analyze import _find_all_bottleneck_comms


class TestBottleneckMultiProcess(unittest.TestCase):
    """测试多 BOTTLENECK 进程识别功能"""

    @classmethod
    def setUpClass(cls):
        """加载测试数据"""
        cls.data_dir = Path(__file__).parent.parent / "data" / "new_format"
        cls.data_file = cls.data_dir / "case_huge_samples.data"
        
        if not cls.data_file.exists():
            raise FileNotFoundError(f"测试数据不存在: {cls.data_file}")
        
        # 加载样本数据
        from perf_toolkit.core.engine import PerfExpertEngine
        cls.engine = PerfExpertEngine(str(cls.data_file))
        cls.samples = cls.engine.get_filtered_samples()
        cls.facade = AnalysisFacade(cls.engine)

    def test_find_all_bottleneck_comms(self):
        """测试 _find_all_bottleneck_comms 能找到所有 BOTTLENECK"""
        bottlenecks = _find_all_bottleneck_comms(self.facade, self.samples)
        
        # 验证找到了多个 bottleneck
        self.assertGreaterEqual(len(bottlenecks), 4, 
            f"应该找到至少4个 BOTTLENECK，实际找到 {len(bottlenecks)}: {bottlenecks}")
        
        # 验证包含预期的进程
        expected_comms = {'netstat', 'python3', 'containerd-shim', 'kubelet'}
        found_set = set(bottlenecks)
        
        for comm in expected_comms:
            self.assertIn(comm, found_set, 
                f"预期进程 {comm} 应该在 BOTTLENECK 列表中")
        
        print(f"✓ 找到 {len(bottlenecks)} 个 BOTTLENECK: {bottlenecks}")

    def test_sys_audit_recommendations_include_all_bottlenecks(self):
        """测试 sys-audit 的 recommendations 包含所有 BOTTLENECK 的追踪建议"""
        from perf_toolkit.cli.commands.composite.sys_audit import cmd_sys_audit
        from argparse import Namespace
        
        # 创建 mock args (@command 装饰器会自动创建 builder 和 samples)
        args = Namespace(top_n=20, data=self.data_file)
        
        # 执行 sys-audit (装饰后只接受 engine 和 args)
        output = cmd_sys_audit(self.engine, args)
        
        # 获取 recommendations
        recommendations = output.recommendations
        self.assertIsNotNone(recommendations, "recommendations 不应为 None")
        
        # 查找所有包含 "bottleneck-analyze" 的推荐
        trace_recommendations = [r for r in recommendations if 'bottleneck-analyze' in r]
        
        # 验证至少有为 netstat 的推荐
        netstat_recs = [r for r in trace_recommendations if 'netstat' in r]
        self.assertGreaterEqual(len(netstat_recs), 1, "应该有为 netstat 的追踪推荐")
        
        # 获取所有 bottleneck 进程名
        all_bottlenecks = _find_all_bottleneck_comms(self.facade, self.samples)
        
        # 验证每个 bottleneck 都有对应的推荐
        for comm in all_bottlenecks:
            comm_recs = [r for r in trace_recommendations if comm in r]
            self.assertGreaterEqual(len(comm_recs), 1,
                f"进程 {comm} 应该有对应的 bottleneck-analyze 推荐")
        
        print(f"✓ sys-audit 生成了 {len(trace_recommendations)} 个追踪推荐")
        for rec in trace_recommendations:
            print(f"  - {rec}")

    def test_sys_audit_pending_targets_include_all_bottlenecks(self):
        """测试 sys-audit 的 risk pending_targets 包含所有 BOTTLENECK"""
        from perf_toolkit.cli.commands.composite.sys_audit import cmd_sys_audit
        from argparse import Namespace
        
        args = Namespace(top_n=20, data=self.data_file)
        
        output = cmd_sys_audit(self.engine, args)
        
        # 获取 risk 信息
        risk = output._risk
        self.assertIsNotNone(risk, "risk 不应为 None")
        
        pending_targets = risk.pending_targets
        self.assertIsNotNone(pending_targets, "pending_targets 不应为 None")
        
        # 获取所有 bottleneck
        all_bottlenecks = _find_all_bottleneck_comms(self.facade, self.samples)
        
        # 验证所有 bottleneck 都在 pending_targets 中
        for comm in all_bottlenecks:
            self.assertIn(comm, pending_targets,
                f"进程 {comm} 应该在 pending_targets 中")
        
        print(f"✓ pending_targets 包含 {len(pending_targets)} 个目标: {pending_targets}")

    def test_bottleneck_analyze_shows_other_bottlenecks(self):
        """测试 bottleneck-analyze 自动追踪所有检测到的瓶颈"""
        from perf_toolkit.cli.commands.composite.bottleneck_analyze import cmd_bottleneck_analyze
        from argparse import Namespace
        
        # 不带 --comm，自动识别所有 bottleneck (@command 装饰器会自动处理)
        args = Namespace(comm=None, pid=None, top_n=10, data=self.data_file)
        
        output = cmd_bottleneck_analyze(self.engine, args)
        
        # 获取 risk
        risk = output._risk
        self.assertIsNotNone(risk, "risk 不应为 None")
        
        # 验证 pending_targets 包含所有 bottleneck
        all_bottlenecks = _find_all_bottleneck_comms(self.facade, self.samples)
        
        # 验证 pending_targets 包含所有 bottleneck
        for comm in all_bottlenecks:
            self.assertIn(comm, risk.pending_targets,
                f"进程 {comm} 应该在 pending_targets 中")
        
        # 验证 entity_distribution 包含所有 bottleneck 的数据
        entity_comms = [e.comm for e in output.entity_distribution]
        for comm in all_bottlenecks:
            self.assertIn(comm, entity_comms,
                f"进程 {comm} 应该在 entity_distribution 中")
        
        # 验证 risk message 报告了所有 bottleneck
        self.assertIn(str(len(all_bottlenecks)), risk.message,
            f"Risk message 应该包含瓶颈数量 {len(all_bottlenecks)}")
        
        print(f"✓ bottleneck-analyze 自动追踪了 {len(all_bottlenecks)} 个瓶颈")
        print(f"  - 所有瓶颈: {all_bottlenecks}")
        print(f"  - Entity count: {len(output.entity_distribution)}")
        print(f"  - Risk message: {risk.message}")
        print(f"  - Hint: {risk.hint}")

    def test_bottleneck_analyze_creates_issues_for_all_bottlenecks(self):
        """测试 bottleneck-analyze 为所有 bottleneck 创建一个聚合 issue"""
        from perf_toolkit.cli.commands.composite.bottleneck_analyze import cmd_bottleneck_analyze
        from perf_toolkit.core.trace import Trace
        from argparse import Namespace
        import os
        import tempfile
        
        # 使用临时目录避免干扰现有 trace 文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 切换到临时目录
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                # 初始化新的 trace
                trace = Trace()
                trace.init(str(self.data_file))
                
                # 执行 bottleneck-analyze
                args = Namespace(comm=None, pid=None, top_n=10, data=self.data_file)
                output = cmd_bottleneck_analyze(self.engine, args)
                
                # 重新加载 trace 查看创建的 issues
                trace = Trace()
                open_issues = trace.get_open_issues()
                
                # 获取所有 bottleneck
                all_bottlenecks = _find_all_bottleneck_comms(self.facade, self.samples)
                
                # 现在只创建一个聚合的 issue
                self.assertGreaterEqual(len(open_issues), 1,
                    f"应该至少创建 1 个 issue，实际 {len(open_issues)} 个")
                
                # 验证聚合 issue 的描述中包含所有 bottleneck
                issue_descs = [issue.get('desc', '') for issue in open_issues]
                main_issue_desc = issue_descs[0] if issue_descs else ""
                
                # 验证第一个 issue 包含瓶颈数量信息
                self.assertIn(str(len(all_bottlenecks)), main_issue_desc,
                    f"Issue 描述应该包含瓶颈数量 {len(all_bottlenecks)}")
                
                # 验证每个 bottleneck 都在某个 issue 的描述中
                for comm in all_bottlenecks[:3]:  # 检查前3个（描述可能被截断）
                    found = any(comm in desc for desc in issue_descs)
                    self.assertTrue(found, f"bottleneck {comm} 应该在某个 issue 描述中")
                
                print(f"✓ 为 {len(all_bottlenecks)} 个 bottleneck 创建了聚合 issue")
                for issue in open_issues:
                    print(f"  - {issue.get('id')}: {issue.get('desc', '')[:80]}...")
                    
            finally:
                os.chdir(original_cwd)


class TestBottleneckTraceIntegration(unittest.TestCase):
    """集成测试: 完整的 bottleneck-analyze 流程"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.data_dir = Path(__file__).parent.parent / "data" / "new_format"
        cls.data_file = cls.data_dir / "case_huge_samples.data"
        
        if not cls.data_file.exists():
            raise FileNotFoundError(f"测试数据不存在: {cls.data_file}")

    def test_bottleneck_analyze_with_specific_comm(self):
        """测试指定 comm 时只分析该进程"""
        from perf_toolkit.cli.commands.composite.bottleneck_analyze import cmd_bottleneck_analyze
        from perf_toolkit.core.engine import PerfExpertEngine
        from argparse import Namespace
        
        engine = PerfExpertEngine(str(self.data_file))
        
        args = Namespace(comm='python3', pid=None, top_n=10, data=self.data_file)
        
        output = cmd_bottleneck_analyze(engine, args)
        
        # 验证分析了指定的进程
        risk = output._risk
        self.assertIsNotNone(risk)
        self.assertIn('python3', risk.message, "应该分析 python3 进程")


if __name__ == '__main__':
    # 设置 verbosity
    unittest.main(verbosity=2)
