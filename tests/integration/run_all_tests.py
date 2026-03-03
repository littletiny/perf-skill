#!/usr/bin/env python3
"""
三层架构集成测试统一入口

运行所有 Core-Analysis-Composite 三层架构集成测试:
- Core层接口测试
- Facade接口测试
- Composite命令测试
- Trace边界测试
- Risk集成测试
- 端到端测试

使用方法:
    python3 tests/integration/run_all_tests.py
    python3 tests/integration/run_all_tests.py -v  # 详细输出
    python3 tests/integration/run_all_tests.py -f  # 失败时停止
"""

import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "integration"))

# 导入所有测试模块
try:
    from test_core_interfaces import TestCoreInterfaces, TestCoreDataAccessControl, TestCoreCVAndMonopoly
    from test_facade_interfaces import TestFacadeInterface, TestFacadeErrorHandling, TestFacadeInterfaceContract
    from test_composite_commands import (
        TestCompositeCommands, TestSysAuditComposite, TestBottleneckTraceComposite,
        TestStormTraceComposite, TestCompositeRiskAggregation, TestCompositeOutputFormat
    )
    from test_trace_boundary import (
        TestTraceBoundary, TestCLITracesToTimeline, TestCompositeDoesNotPolluteTimeline,
        TestTraceBoundaryEnforcement, TestTraceOutputBuilderIntegration,
        TestTraceIsolationBetweenCommands, TestTraceBoundaryViolationDetection
    )
    from test_risk_integration import (
        TestRiskMixinCore, TestRiskInfoDataClass, TestAnalysisRiskIdentification,
        TestCompositeRiskAggregation, TestRiskFlowAcrossLayers, TestRiskOutputFormat, TestRiskPatterns
    )
    from test_three_tier_e2e import (
        TestThreeTierE2E, TestE2ESysAuditCommand, TestE2EDataFlow,
        TestE2ERiskFlow, TestE2ETraceBoundary, TestE2EIntegration, TestE2EErrorHandling
    )
    ALL_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"警告: 部分测试模块未找到: {e}")
    ALL_MODULES_AVAILABLE = False


def create_test_suite():
    """创建测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Core层测试
    suite.addTests(loader.loadTestsFromTestCase(TestCoreInterfaces))
    suite.addTests(loader.loadTestsFromTestCase(TestCoreDataAccessControl))
    suite.addTests(loader.loadTestsFromTestCase(TestCoreCVAndMonopoly))
    
    # Facade接口测试
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeInterface))
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestFacadeInterfaceContract))
    
    # Composite命令测试
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeCommands))
    suite.addTests(loader.loadTestsFromTestCase(TestSysAuditComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestBottleneckTraceComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestStormTraceComposite))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeRiskAggregation))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeOutputFormat))
    
    # Trace边界测试
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundary))
    suite.addTests(loader.loadTestsFromTestCase(TestCLITracesToTimeline))
    suite.addTests(loader.loadTestsFromTestCase(TestCompositeDoesNotPolluteTimeline))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundaryEnforcement))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceOutputBuilderIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceIsolationBetweenCommands))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceBoundaryViolationDetection))
    
    # Risk集成测试
    suite.addTests(loader.loadTestsFromTestCase(TestRiskMixinCore))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskInfoDataClass))
    suite.addTests(loader.loadTestsFromTestCase(TestAnalysisRiskIdentification))
    # 注意：TestCompositeRiskAggregation 在Risk和Composite测试中都存在，避免重复
    # suite.addTests(loader.loadTestsFromTestCase(TestCompositeRiskAggregation))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskFlowAcrossLayers))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskOutputFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskPatterns))
    
    # 端到端测试
    suite.addTests(loader.loadTestsFromTestCase(TestThreeTierE2E))
    suite.addTests(loader.loadTestsFromTestCase(TestE2ESysAuditCommand))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EDataFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestE2ERiskFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestE2ETraceBoundary))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EErrorHandling))
    
    return suite


def run_tests(verbosity=1, failfast=False):
    """运行所有测试"""
    suite = create_test_suite()
    
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def print_summary():
    """打印测试摘要"""
    print("\n" + "=" * 70)
    print("三层架构测试套件")
    print("=" * 70)
    print("\n测试分类:")
    print("  1. Core层接口测试      - 验证Engine新接口")
    print("  2. Facade接口测试      - 验证Analysis Facade")
    print("  3. Composite命令测试   - 验证组合诊断命令")
    print("  4. Trace边界测试       - 验证Trace不被污染")
    print("  5. Risk集成测试        - 验证Risk流转与聚合")
    print("  6. 端到端测试          - 验证完整诊断流程")
    print("\n" + "=" * 70)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="三层架构集成测试套件")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--failfast", action="store_true", help="失败时停止")
    parser.add_argument("-s", "--summary", action="store_true", help="只显示摘要")
    args = parser.parse_args()
    
    if args.summary:
        print_summary()
        return 0
    
    verbosity = 2 if args.verbose else 1
    
    print_summary()
    print("\n开始运行测试...\n")
    
    success = run_tests(verbosity=verbosity, failfast=args.failfast)
    
    print("\n" + "=" * 70)
    if success:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败")
    print("=" * 70 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
