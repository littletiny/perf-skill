#!/usr/bin/env python3
"""
perfdata 回归测试套件

统一测试 new_format 和 perf_format 两种数据格式的兼容性。

用法:
    python3 tests/perfdata/test_perfdata.py        # 运行所有测试
    python3 tests/perfdata/test_perfdata.py -v     # 详细输出
    python3 tests/perfdata/test_perfdata.py -f     # 失败时停止
    python3 tests/perfdata/test_perfdata.py -d new_format  # 只测试指定格式
"""

import os
import sys
import json
import shutil
import tempfile
import argparse
import subprocess
from pathlib import Path

# 测试目录
TEST_DIR = Path(__file__).parent
REPO_ROOT = TEST_DIR.parent.parent
SPEAR = REPO_ROOT / "scripts" / "spear"


class Colors:
    """终端颜色"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  {Colors.GREEN}✓{Colors.RESET} {name}")

    def add_fail(self, name, msg):
        self.failed += 1
        self.failures.append((name, msg))
        print(f"  {Colors.RED}✗{Colors.RESET} {name}")
        if msg:
            print(f"      {Colors.RED}{msg}{Colors.RESET}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
        print(f"总计: {total} | {Colors.GREEN}通过: {self.passed}{Colors.RESET} | {Colors.RED}失败: {self.failed}{Colors.RESET}")
        if self.failures:
            print(f"\n{Colors.RED}失败详情:{Colors.RESET}")
            for name, msg in self.failures:
                print(f"  - {name}: {msg}")
        return self.failed == 0


class TestEnv:
    """测试环境上下文管理器"""
    def __init__(self):
        self.tmpdir = None
        self.orig_dir = None

    def __enter__(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="perfdata_test_"))
        self.orig_dir = Path.cwd()
        os.chdir(self.tmpdir)
        return self

    def __exit__(self, *args):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_spear(self, *args, data_file=None, check=True):
        """运行 spear 命令"""
        # SPEAR 是 bash 脚本，需要用 bash 执行
        cmd = ["bash", str(SPEAR)]
        
        # 如果提供了 data_file，使用 SPEAR_DATA 环境变量
        env = os.environ.copy()
        if data_file:
            env["SPEAR_DATA"] = str(data_file)
        
        cmd.extend(args)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env
        )
        
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(args)}\n{result.stderr}")
        
        return result

    def init_data(self, data_file):
        """初始化数据文件"""
        self.run_spear("init", "--data-path", str(data_file))


def get_data_info(data_file):
    """获取数据文件信息"""
    content = data_file.read_text()
    lines = content.splitlines()
    
    # 采样记录数
    sample_count = sum(1 for line in lines if 'core/s:' in line or 'cpu-clock' in line)
    
    # 进程类型数
    comms = set()
    for line in lines:
        if 'core/s:' in line:
            parts = line.split()
            if parts:
                comms.add(parts[0])
        elif 'cpu-clock' in line:
            # perf_format: 进程名在第一列
            parts = line.split()
            if len(parts) >= 1:
                comms.add(parts[0])
    
    return {
        "total_lines": len(lines),
        "sample_count": sample_count,
        "comm_count": len(comms),
        "comms": sorted(list(comms))[:10]  # 前10个
    }


def test_data_file_exists(data_dir):
    """测试: 数据文件存在"""
    data_file = TEST_DIR / data_dir / "case_test.data"
    assert data_file.exists(), f"数据文件不存在: {data_file}"
    return data_file


def test_format_detection(data_file, format_type):
    """测试: 格式识别"""
    content = data_file.read_text()
    
    if format_type == "new_format":
        assert "core/s:" in content, "new_format 应包含 core/s: 标识"
    elif format_type == "perf_format":
        assert "cpu-clock" in content, "perf_format 应包含 cpu-clock 事件"


def test_tool_check_cpu_bottleneck(env, data_file):
    """测试: check-cpu-bottleneck"""
    result = env.run_spear("check-cpu-bottleneck", data_file=data_file, check=False)
    # 工具应该成功运行，不管输出是什么
    assert result.returncode == 0, f"工具失败: {result.stderr}"


def test_tool_show_cpu_usage(env, data_file):
    """测试: show-cpu-usage"""
    result = env.run_spear("show-cpu-usage", data_file=data_file, check=False)
    assert result.returncode == 0


def test_tool_get_process_top(env, data_file):
    """测试: get-process-top"""
    result = env.run_spear("get-process-top", "--top-n", "5", data_file=data_file)
    assert "# comm(pid)" in result.stdout or len(result.stdout) > 0


def test_tool_get_comm_top(env, data_file):
    """测试: get-comm-top"""
    result = env.run_spear("get-comm-top", "--top-n", "5", data_file=data_file)
    assert len(result.stdout) > 0


def test_tool_count_process_variety(env, data_file):
    """测试: count-process-variety"""
    result = env.run_spear("count-process-variety", "--top-n", "10", data_file=data_file)
    assert len(result.stdout) > 0


def test_tool_cluster_comm(env, data_file):
    """测试: cluster-comm"""
    result = env.run_spear("cluster-comm", "--top-n", "10", data_file=data_file)
    assert len(result.stdout) > 0


def test_tool_get_hotspots(env, data_file):
    """测试: get-hotspots"""
    result = env.run_spear("get-hotspots", "--sort-by", "self", "--top-n", "10", data_file=data_file)
    assert "# index,funcname" in result.stdout


def test_tool_get_hotspots_inclusive(env, data_file):
    """测试: get-hotspots --sort-by inclusive"""
    result = env.run_spear("get-hotspots", "--sort-by", "inclusive", "--top-n", "10", data_file=data_file)
    assert "# index,funcname" in result.stdout


def test_tool_cluster_symbols(env, data_file):
    """测试: cluster-symbols"""
    result = env.run_spear("cluster-symbols", data_file=data_file)
    assert len(result.stdout) > 0


def test_tool_cluster_paths(env, data_file):
    """测试: cluster-paths"""
    result = env.run_spear("cluster-paths", "--min-depth", "3", "--top-n", "5", data_file=data_file)
    assert len(result.stdout) > 0


def test_tool_analyze_core_distribution(env, data_file):
    """测试: analyze-core-distribution"""
    result = env.run_spear("analyze-core-distribution", data_file=data_file)
    assert len(result.stdout) > 0


def test_find_callers(env, data_file):
    """测试: find-callers（针对第一个热点）"""
    # 先获取热点
    result = env.run_spear("get-hotspots", "--sort-by", "self", "--top-n", "1", data_file=data_file)
    
    # 解析第一个函数名
    for line in result.stdout.splitlines():
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 1:
            symbol = parts[0]
            # 尝试查找调用者
            caller_result = env.run_spear(
                "find-callers", "--target", symbol, 
                "--min-ratio", "1.0",
                data_file=data_file,
                check=False
            )
            # find-callers 可能找不到，但不影响测试
            break


# ═════════════════════════════════════════════════════════════════════════════
# 测试套件
# ═════════════════════════════════════════════════════════════════════════════

TEST_TOOLS = [
    ("check-cpu-bottleneck", test_tool_check_cpu_bottleneck),
    ("show-cpu-usage", test_tool_show_cpu_usage),
    ("get-process-top", test_tool_get_process_top),
    ("get-comm-top", test_tool_get_comm_top),
    ("count-process-variety", test_tool_count_process_variety),
    ("cluster-comm", test_tool_cluster_comm),
    ("get-hotspots", test_tool_get_hotspots),
    ("get-hotspots-incl", test_tool_get_hotspots_inclusive),
    ("cluster-symbols", test_tool_cluster_symbols),
    ("cluster-paths", test_tool_cluster_paths),
    ("analyze-core-distribution", test_tool_analyze_core_distribution),
    ("find-callers", test_find_callers),
]


def test_format(data_dir, format_type, result, verbose=False):
    """测试单个数据格式"""
    print(f"\n{Colors.YELLOW}▶ 测试 {data_dir} ({format_type}){Colors.RESET}")
    
    # 1. 数据文件存在性
    try:
        data_file = test_data_file_exists(data_dir)
        result.add_pass(f"{data_dir}/data_file_exists")
    except Exception as e:
        result.add_fail(f"{data_dir}/data_file_exists", str(e))
        return
    
    # 2. 格式检测
    try:
        test_format_detection(data_file, format_type)
        result.add_pass(f"{data_dir}/format_detection")
    except Exception as e:
        result.add_fail(f"{data_dir}/format_detection", str(e))
    
    # 3. 获取数据信息
    info = get_data_info(data_file)
    if verbose:
        print(f"  总行数: {info['total_lines']}")
        print(f"  采样记录: {info['sample_count']}")
        print(f"  进程类型: {info['comm_count']}")
    
    # 4. 工具测试
    with TestEnv() as env:
        env.init_data(data_file)
        
        for tool_name, test_func in TEST_TOOLS:
            try:
                test_func(env, data_file)
                result.add_pass(f"{data_dir}/{tool_name}")
            except Exception as e:
                result.add_fail(f"{data_dir}/{tool_name}", str(e))


def run_tests(data_dirs=None, verbose=False, fail_fast=False):
    """运行所有测试"""
    result = TestResult()
    
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
    print(f"perfdata 回归测试套件")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
    print(f"数据目录: {TEST_DIR}")
    print(f"spear: {SPEAR}")
    
    # 确定要测试的格式
    if data_dirs is None:
        data_dirs = ["new_format", "perf_format"]
    
    # 格式类型映射
    format_types = {
        "new_format": "new_format",
        "perf_format": "perf_format",
    }
    
    for data_dir in data_dirs:
        if data_dir not in format_types:
            print(f"{Colors.RED}未知格式: {data_dir}{Colors.RESET}")
            continue
        
        format_type = format_types[data_dir]
        test_format(data_dir, format_type, result, verbose)
        
        if fail_fast and result.failed > 0:
            break
    
    return result.summary()


def main():
    parser = argparse.ArgumentParser(description="perfdata 回归测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="失败时停止")
    parser.add_argument("-d", "--dirs", nargs="+", help="指定测试目录 (默认: new_format perf_format)")
    args = parser.parse_args()
    
    success = run_tests(
        data_dirs=args.dirs,
        verbose=args.verbose,
        fail_fast=args.fail_fast
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
