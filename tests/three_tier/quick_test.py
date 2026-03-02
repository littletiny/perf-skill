#!/usr/bin/env python3
"""
三层架构快速测试脚本

简化版测试入口，只运行关键测试并显示结果摘要。
适合开发过程中快速验证。

使用方法:
    python3 tests/three_tier/quick_test.py
    
输出:
    ✅ 通过: 45
    ⚠️  跳过: 25 
    ❌ 失败: 0
"""

import unittest
import sys
from pathlib import Path
from io import StringIO

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "three_tier"))


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header():
    """打印标题"""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}  三层架构快速测试{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")


def print_summary(passed, skipped, failed, errors):
    """打印结果摘要"""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}  测试结果{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    
    print(f"\n  {Colors.GREEN}✅ 通过: {passed}{Colors.RESET}")
    
    if skipped > 0:
        print(f"  {Colors.YELLOW}⚠️  跳过: {skipped} (依赖未实现模块){Colors.RESET}")
    else:
        print(f"  ⚠️  跳过: {skipped}")
    
    if failed > 0:
        print(f"  {Colors.RED}❌ 失败: {failed}{Colors.RESET}")
    else:
        print(f"  ❌ 失败: {failed}")
    
    if errors > 0:
        print(f"  {Colors.RED}💥 错误: {errors}{Colors.RESET}")
    
    # 总体状态
    print(f"\n{Colors.BOLD}{'-' * 60}{Colors.RESET}")
    if failed == 0 and errors == 0:
        if skipped == 0:
            print(f"  {Colors.GREEN}✅ 状态: 所有测试通过{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}⚠️  状态: 部分测试通过（有跳过）{Colors.RESET}")
        print(f"\n  可以开始集成测试")
    else:
        print(f"  {Colors.RED}❌ 状态: 存在失败/错误{Colors.RESET}")
        print(f"\n  请检查失败用例")
    
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")


def run_test_suites():
    """运行测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 尝试导入并添加测试
    test_modules = [
        ('test_core_interfaces', 'Core层接口'),
        ('test_facade_interfaces', 'Facade接口'),
        ('test_composite_commands', 'Composite命令'),
        ('test_trace_boundary', 'Trace边界'),
        ('test_risk_integration', 'Risk集成'),
        ('test_three_tier_e2e', '端到端'),
    ]
    
    loaded_modules = []
    
    for module_name, display_name in test_modules:
        try:
            module = __import__(module_name)
            # 获取模块中的所有测试类
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    suite.addTests(loader.loadTestsFromTestCase(obj))
            loaded_modules.append(display_name)
        except ImportError as e:
            # 模块未实现，跳过
            pass
    
    if not loaded_modules:
        print(f"{Colors.YELLOW}警告: 未找到可运行的测试模块{Colors.RESET}")
        print("请先实现基础模块:\n")
        print("  1. perf_toolkit/core/engine.py")
        print("  2. perf_toolkit/core/risk_mixin.py")
        return 0, 0, 0, 0
    
    print(f"  加载模块: {', '.join(loaded_modules)}\n")
    
    # 运行测试
    runner = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=1,  # 简洁输出
        descriptions=False
    )
    
    # 捕获结果
    result = runner.run(suite)
    
    # 统计
    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    skipped = len(result.skipped)
    failed = len(result.failures)
    errors = len(result.errors)
    
    return passed, skipped, failed, errors


def main():
    """主函数"""
    print_header()
    
    try:
        passed, skipped, failed, errors = run_test_suites()
        print_summary(passed, skipped, failed, errors)
        
        # 返回状态码
        if failed > 0 or errors > 0:
            return 1
        return 0
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}测试被用户中断{Colors.RESET}\n")
        return 130
    except Exception as e:
        print(f"\n{Colors.RED}测试运行出错: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
