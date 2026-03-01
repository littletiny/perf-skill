#!/usr/bin/env python3
"""
外部规则文件集成测试套件

验证:
- 外部规则文件加载 (--rules-file)
- 规则优先级合并 (内置 < 外部文件 < CLI)
- 模块级缓存机制
- 统一入口 (run_analysis_command) 集成
- Trace 自动记录
- 与真实数据文件的兼容性

用法:
    python3 tests/clusters/test_external_rules_integration.py        # 运行所有测试
    python3 tests/clusters/test_external_rules_integration.py -v     # 详细输出
    python3 tests/clusters/test_external_rules_integration.py -f     # 失败时停止
"""

import os
import sys
import json
import tempfile
import argparse
import subprocess
from pathlib import Path

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.perf_toolkit.analysis import clusters
from scripts.perf_toolkit.core.output_builder import OutputBuilder


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
        print(f"      {Colors.RED}{msg}{Colors.RESET}")

    def summary(self):
        print()
        total = self.passed + self.failed
        if self.failed == 0:
            print(f"{Colors.GREEN}全部通过: {self.passed}/{total}{Colors.RESET}")
        else:
            print(f"{Colors.RED}失败: {self.failed}/{total}, 通过: {self.passed}/{total}{Colors.RESET}")
            print()
            print("失败详情:")
            for name, msg in self.failures:
                print(f"  - {name}: {msg}")
        return self.failed == 0


# =============================================================================
# 测试用例
# =============================================================================

def test_default_rules_loaded_from_config():
    """测试: 默认规则从 config/default-rules.json 加载"""
    default_path = clusters.get_default_rules_path()
    assert Path(default_path).exists(), f"默认规则文件不存在: {default_path}"

    rules = clusters.load_default_rules()
    assert len(rules) >= 5, f"规则数量不足: {len(rules)}"

    expected = ["EVENT_IRQ_OFF", "EVENT_SCHEDULER", "EVENT_MEM_RECLAIM",
                "EVENT_LOCK_CONTENTION", "EVENT_SYNC_PRIMITIVE"]
    for rule in expected:
        assert rule in rules, f"缺少规则: {rule}"


def test_external_rules_override_builtin():
    """测试: 外部规则覆盖内置规则"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_IRQ_OFF": "overridden_pattern",  # 覆盖内置
            "EVENT_CUSTOM": "custom_pattern"        # 新增
        }, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()

        args = argparse.Namespace(
            include_experts=True,
            no_include_experts=False,
            rules_file=temp_path,
            custom_rules=None
        )
        rules = clusters.prepare_rules(args)

        assert rules["EVENT_IRQ_OFF"] == "overridden_pattern", "外部规则应覆盖内置"
        assert rules["EVENT_CUSTOM"] == "custom_pattern", "应包含外部新增规则"
        assert "EVENT_SCHEDULER" in rules, "应保留其他内置规则"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_cli_rules_highest_priority():
    """测试: CLI 规则具有最高优先级"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_IRQ_OFF": "file_pattern",
            "EVENT_FILE": "file_only"
        }, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()

        args = argparse.Namespace(
            include_experts=True,
            no_include_experts=False,
            rules_file=temp_path,
            custom_rules='{"EVENT_IRQ_OFF": "cli_pattern", "EVENT_CLI": "cli_only"}'
        )
        rules = clusters.prepare_rules(args)

        assert rules["EVENT_IRQ_OFF"] == "cli_pattern", "CLI规则应覆盖文件规则"
        assert rules["EVENT_FILE"] == "file_only", "应保留文件规则"
        assert rules["EVENT_CLI"] == "cli_only", "应包含CLI规则"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_rules_caching_mechanism():
    """测试: 规则文件缓存机制有效"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"EVENT_CACHE": "cache_test"}, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()

        # 第一次加载
        rules1 = clusters.load_rules_from_file(temp_path)
        cache_key = os.path.abspath(temp_path)
        assert cache_key in clusters._rules_cache, "应存入缓存"

        # 第二次加载（应使用缓存）
        rules2 = clusters.load_rules_from_file(temp_path)
        assert rules1 is rules2, "应返回缓存的同一对象"

        # 使用绝对路径再次加载
        abs_path = os.path.abspath(temp_path)
        rules3 = clusters.load_rules_from_file(abs_path)
        assert rules1 is rules3, "绝对路径应命中相对路径的缓存"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_no_include_experts():
    """测试: --no-include-experts 禁用内置规则"""
    args = argparse.Namespace(
        include_experts=False,
        no_include_experts=True,
        rules_file=None,
        custom_rules='{"EVENT_ONLY": "only_custom"}'
    )
    rules = clusters.prepare_rules(args)

    assert "EVENT_IRQ_OFF" not in rules, "不应包含内置规则"
    assert rules["EVENT_ONLY"] == "only_custom", "应只包含CLI规则"


def test_empty_external_rules():
    """测试: 空外部规则文件处理"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"_comment": "empty"}, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()

        args = argparse.Namespace(
            include_experts=False,
            no_include_experts=True,
            rules_file=temp_path,
            custom_rules=None
        )
        rules = clusters.prepare_rules(args)
        assert rules == {}, "空规则文件应返回空字典"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_metadata_keys_filtered():
    """测试: 元数据键被正确过滤"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "_comment": "should be filtered",
            "_version": "1.0",
            "EVENT_VALID": "valid_pattern",
            "_private": "should also be filtered"
        }, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()
        rules = clusters.load_rules_from_file(temp_path)

        assert "_comment" not in rules, "_comment 应被过滤"
        assert "_version" not in rules, "_version 应被过滤"
        assert "_private" not in rules, "_private 应被过滤"
        assert "EVENT_VALID" in rules, "EVENT_VALID 应保留"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_list_format_in_rules():
    """测试: 规则值支持列表格式"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_LIST": ["pattern1", "pattern2", "pattern3"]
        }, f)
        temp_path = f.name

    try:
        clusters._rules_cache.clear()
        rules = clusters.load_rules_from_file(temp_path)

        assert isinstance(rules["EVENT_LIST"], list), "列表格式应保留"
        assert rules["EVENT_LIST"] == ["pattern1", "pattern2", "pattern3"]
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_file_not_found_error():
    """测试: 文件不存在时正确抛出异常"""
    clusters._rules_cache.clear()

    try:
        clusters.load_rules_from_file("/nonexistent/path/rules.json")
        assert False, "应抛出 FileNotFoundError"
    except FileNotFoundError as e:
        assert "/nonexistent/path/rules.json" in str(e)


def test_integration_with_real_data():
    """测试: 与真实数据文件集成"""
    data_file = REPO_ROOT / "tests" / "perfdata" / "new_format" / "case_test.data"
    if not data_file.exists():
        print(f"  {Colors.YELLOW}⚠ 跳过: 测试数据不存在{Colors.RESET}")
        return

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_INTEGRATION": "integration_test_pattern"
        }, f)
        rules_file = f.name

    try:
        # 使用 spear.py 直接测试
        cmd = [
            sys.executable, str(REPO_ROOT / "scripts" / "spear.py"),
            "cluster-symbols",
            "--data", str(data_file),
            "--rules-file", rules_file,
            "--top-n", "5"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # 命令应成功执行
        assert result.returncode == 0, f"命令失败: {result.stderr}"
        # 应有输出
        assert len(result.stdout) > 0, "命令无输出"

    finally:
        os.unlink(rules_file)


def test_unified_entry_trace_recording():
    """测试: 统一入口正确记录 Trace"""
    data_file = REPO_ROOT / "tests" / "perfdata" / "new_format" / "case_test.data"
    if not data_file.exists():
        print(f"  {Colors.YELLOW}⚠ 跳过: 测试数据不存在{Colors.RESET}")
        return

    # 创建临时 trace 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "version": "2.0",
            "data_file": str(data_file),
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "timeline": [],
            "issues": {},
            "profiles_used": [str(data_file)]
        }, f)
        trace_file = f.name

    try:
        # 设置工作目录并运行命令
        orig_dir = os.getcwd()
        work_dir = tempfile.mkdtemp()
        os.chdir(work_dir)

        # 复制 trace 文件到工作目录
        local_trace = Path(work_dir) / ".spear.json"
        local_trace.write_text(Path(trace_file).read_text())

        cmd = [
            sys.executable, str(REPO_ROOT / "scripts" / "spear.py"),
            "cluster-symbols",
            "--data", str(data_file),
            "--top-n", "3"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # 检查 trace 文件是否更新了
        if local_trace.exists():
            trace_data = json.loads(local_trace.read_text())
            timeline = trace_data.get("timeline", [])

            # 应至少有一条记录
            assert len(timeline) >= 1, "Trace 应记录命令执行"

            # 最后一条记录应是 cluster-symbols
            last_entry = timeline[-1]
            assert "cluster-symbols" in last_entry.get("command", ""), "应记录 cluster-symbols"

        os.chdir(orig_dir)

    finally:
        import shutil
        os.unlink(trace_file)
        if 'work_dir' in locals():
            shutil.rmtree(work_dir, ignore_errors=True)


def test_rules_file_with_wrap_script():
    """测试: 通过 spear_wrap 使用外部规则文件"""
    data_file = REPO_ROOT / "tests" / "perfdata" / "new_format" / "case_test.data"
    if not data_file.exists():
        print(f"  {Colors.YELLOW}⚠ 跳过: 测试数据不存在{Colors.RESET}")
        return

    # 使用测试中已知存在的 pattern（来自真实数据的 hotspot）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_RUNTIME": "runtime\\.",  # 测试数据中存在的 runtime.* 函数
            "EVENT_SPINLOCK": "_raw_spin_lock"  # 测试数据中存在的热点
        }, f)
        rules_file = f.name

    try:
        orig_dir = os.getcwd()
        work_dir = tempfile.mkdtemp()
        os.chdir(work_dir)

        # 初始化环境
        init_cmd = [
            sys.executable, str(REPO_ROOT / "scripts" / "spear_wrap.py"),
            "init", "--data-path", str(data_file)
        ]
        result = subprocess.run(init_cmd, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"init 失败: {result.stderr}"

        # 使用外部规则文件
        cmd = [
            sys.executable, str(REPO_ROOT / "scripts" / "spear_wrap.py"),
            "cluster-symbols",
            "--rules-file", rules_file,
            "--no-include-experts",
            "--top-n", "3"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"命令失败: {result.stderr}"
        # 验证输出中包含自定义规则分类
        assert "EVENT_RUNTIME" in result.stdout or "EVENT_SPINLOCK" in result.stdout, \
            f"应显示自定义规则结果, 实际输出: {result.stdout[:200]}"

        os.chdir(orig_dir)

    finally:
        os.unlink(rules_file)
        if 'work_dir' in locals():
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)


# =============================================================================
# 测试列表
# =============================================================================

TESTS = [
    ("默认规则从配置加载", test_default_rules_loaded_from_config),
    ("外部规则覆盖内置", test_external_rules_override_builtin),
    ("CLI规则最高优先级", test_cli_rules_highest_priority),
    ("规则缓存机制", test_rules_caching_mechanism),
    ("禁用内置规则", test_no_include_experts),
    ("空规则文件处理", test_empty_external_rules),
    ("元数据键过滤", test_metadata_keys_filtered),
    ("列表格式支持", test_list_format_in_rules),
    ("文件不存在错误", test_file_not_found_error),
    ("真实数据集成", test_integration_with_real_data),
    ("统一入口Trace记录", test_unified_entry_trace_recording),
    ("wrap脚本集成", test_rules_file_with_wrap_script),
]


def main():
    parser = argparse.ArgumentParser(description="外部规则文件集成测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="失败时停止")
    args = parser.parse_args()

    print(f"{Colors.BLUE}=== 外部规则文件集成测试套件 ==={Colors.RESET}")
    print(f"项目根目录: {REPO_ROOT}")
    print()

    result = TestResult()

    for name, test_func in TESTS:
        try:
            if args.verbose:
                print(f"\n运行: {name}")
            test_func()
            result.add_pass(name)
        except AssertionError as e:
            result.add_fail(name, str(e))
            if args.fail_fast:
                break
        except Exception as e:
            result.add_fail(name, f"异常: {type(e).__name__}: {e}")
            if args.fail_fast:
                break

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
