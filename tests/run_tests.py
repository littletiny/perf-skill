#!/usr/bin/env python3
"""
统一测试入口 - 运行所有自动化测试

自动发现并运行 tests/ 下所有自动化测试（不包括 scenario/ 人工验证）

Usage:
    python3 tests/run_tests.py        # 运行所有测试
    python3 tests/run_tests.py -v     # 详细输出
    python3 tests/run_tests.py -f     # 失败时停止
    python3 tests/run_tests.py -l     # 只列出测试文件
"""

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path


# 测试文件列表（按依赖关系排序）
TEST_FILES = [
    # 单元测试
    "tests/unit/test_risk_display_config.py",
    "tests/unit/test_perfdata.py",
    # 功能测试
    "tests/functional/test_issue_overflow_warning.py",
    "tests/functional/test_trace_audit.py",
    # CLI 回归测试
    "tests/cli/test_shecr_wrap.py",
]


class Colors:
    """终端颜色"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class TestResult:
    """测试结果统计"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.time()

    def finish(self):
        self.end_time = time.time()

    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    def summary(self):
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        success = len(self.failed) == 0

        print()
        print("=" * 70)
        print(f"{Colors.BOLD}测试结果摘要{Colors.RESET}")
        print("=" * 70)

        if self.passed:
            print(f"{Colors.GREEN}✓ 通过: {len(self.passed)}{Colors.RESET}")
            for name in self.passed:
                print(f"    {Colors.GREEN}✓{Colors.RESET} {name}")

        if self.failed:
            print(f"{Colors.RED}✗ 失败: {len(self.failed)}{Colors.RESET}")
            for name, error in self.failed:
                print(f"    {Colors.RED}✗{Colors.RESET} {name}")
                if error:
                    print(f"      {Colors.RED}{error}{Colors.RESET}")

        if self.skipped:
            print(f"{Colors.YELLOW}⚠ 跳过: {len(self.skipped)}{Colors.RESET}")
            for name, reason in self.skipped:
                print(f"    {Colors.YELLOW}⚠{Colors.RESET} {name}")
                if reason:
                    print(f"      {Colors.YELLOW}{reason}{Colors.RESET}")

        print("-" * 70)
        print(f"总计: {total} 个测试套件")
        print(f"耗时: {self.duration():.2f} 秒")

        if success:
            print(f"{Colors.GREEN}{Colors.BOLD}全部通过 ✓{Colors.RESET}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}有失败的测试 ✗{Colors.RESET}")

        print("=" * 70)
        return success


def run_test(test_file, verbose=False):
    """运行单个测试文件"""
    test_path = Path(test_file)

    if not test_path.exists():
        return "skipped", f"文件不存在: {test_file}"

    cmd = [sys.executable, str(test_path)]
    if verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            return "passed", None
        else:
            # 提取错误信息（最后几行）
            output = result.stdout + result.stderr
            error_lines = output.strip().split('\n') if output else []
            error = error_lines[-1] if error_lines else "未知错误"
            return "failed", error

    except subprocess.TimeoutExpired:
        return "failed", "超时 (>120s)"
    except Exception as e:
        return "failed", str(e)


def list_tests():
    """列出所有测试文件"""
    print(f"{Colors.BOLD}测试文件列表:{Colors.RESET}")
    print()

    repo_root = Path(__file__).parent.parent

    for i, test_file in enumerate(TEST_FILES, 1):
        test_path = repo_root / test_file
        status = f"{Colors.GREEN}存在{Colors.RESET}" if test_path.exists() else f"{Colors.RED}缺失{Colors.RESET}"
        print(f"  {i}. {test_file} [{status}]")

    print()
    print(f"总计: {len(TEST_FILES)} 个测试套件")


def main():
    parser = argparse.ArgumentParser(
        description="统一测试入口 - 运行所有自动化测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 tests/run_tests.py        # 运行所有测试
    python3 tests/run_tests.py -v     # 详细输出
    python3 tests/run_tests.py -f     # 失败时停止
    python3 tests/run_tests.py -l     # 只列出测试文件
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="失败时停止")
    parser.add_argument("-l", "--list", action="store_true", help="只列出测试文件")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)

    if args.list:
        list_tests()
        return 0

    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}  perf-hunter 自动化测试套件{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"项目根目录: {repo_root}")
    print()

    result = TestResult()
    result.start()

    for test_file in TEST_FILES:
        test_name = Path(test_file).stem
        test_path = repo_root / test_file

        print(f"运行: {Colors.CYAN}{test_file}{Colors.RESET} ... ", end="", flush=True)

        if not test_path.exists():
            print(f"{Colors.YELLOW}跳过 (不存在){Colors.RESET}")
            result.skipped.append((test_name, "文件不存在"))
            continue

        status, error = run_test(test_file, verbose=args.verbose)

        if status == "passed":
            print(f"{Colors.GREEN}通过{Colors.RESET}")
            result.passed.append(test_name)
        elif status == "failed":
            print(f"{Colors.RED}失败{Colors.RESET}")
            result.failed.append((test_name, error))
            if args.fail_fast:
                break
        else:  # skipped
            print(f"{Colors.YELLOW}跳过{Colors.RESET}")
            result.skipped.append((test_name, error))

    result.finish()
    success = result.summary()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
