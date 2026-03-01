#!/usr/bin/env python3
"""
Rules 文件加载与缓存机制测试

验证:
- 默认规则从 config/default-rules.json 加载
- 外部规则文件加载和解析
- 模块级缓存机制（同文件只加载一次）
- 规则优先级合并（内置 < 外部文件 < 命令行）
- 异常处理（文件不存在等）

用法:
    python3 tests/clusters/test_rules_loading.py        # 运行所有测试
    python3 tests/clusters/test_rules_loading.py -v     # 详细输出
    python3 tests/clusters/test_rules_loading.py -f     # 失败时停止
"""

import os
import sys
import json
import tempfile
import argparse
from pathlib import Path

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.perf_toolkit.analysis import clusters


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


def test_default_rules_path():
    """测试: 默认规则路径正确"""
    path = clusters.get_default_rules_path()
    expected = REPO_ROOT / "config" / "default-rules.json"
    assert path == str(expected), f"期望: {expected}, 实际: {path}"
    assert Path(path).exists(), f"默认规则文件不存在: {path}"


def test_default_rules_loading():
    """测试: 默认规则正确加载"""
    rules = clusters.load_default_rules()
    expected_rules = [
        "EVENT_IRQ_OFF",
        "EVENT_SCHEDULER",
        "EVENT_MEM_RECLAIM",
        "EVENT_LOCK_CONTENTION",
        "EVENT_SYNC_PRIMITIVE"
    ]
    for rule in expected_rules:
        assert rule in rules, f"缺少规则: {rule}"
    # 验证规则是正则字符串
    assert isinstance(rules["EVENT_IRQ_OFF"], str), "规则值应为字符串"


def test_load_rules_from_file():
    """测试: 从外部文件加载规则"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "_comment": "test",
            "EVENT_TEST": "test_pattern",
            "EVENT_CUSTOM": ["pattern1", "pattern2"]
        }, f)
        temp_path = f.name

    try:
        rules = clusters.load_rules_from_file(temp_path)
        assert "EVENT_TEST" in rules, "应加载 EVENT_TEST"
        assert "EVENT_CUSTOM" in rules, "应加载 EVENT_CUSTOM"
        assert "_comment" not in rules, "应过滤 _comment"
        assert rules["EVENT_TEST"] == "test_pattern"
        assert rules["EVENT_CUSTOM"] == ["pattern1", "pattern2"]
    finally:
        os.unlink(temp_path)


def test_rules_caching():
    """测试: 规则文件缓存机制"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"EVENT_CACHE_TEST": "cache_value"}, f)
        temp_path = f.name

    try:
        # 清空缓存
        clusters._rules_cache.clear()

        # 第一次加载（应读取文件）
        rules1 = clusters.load_rules_from_file(temp_path)
        assert temp_path in clusters._rules_cache, "应存入缓存"

        # 第二次加载（应使用缓存）
        rules2 = clusters.load_rules_from_file(temp_path)
        assert rules1 is rules2, "应返回同一对象（缓存）"

        # 使用绝对路径再次加载（应命中缓存）
        abs_path = os.path.abspath(temp_path)
        rules3 = clusters.load_rules_from_file(abs_path)
        assert rules1 is rules3, "绝对路径应命中相对路径的缓存"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_prepare_rules_priority():
    """测试: 规则优先级合并"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "EVENT_IRQ_OFF": "overridden_by_file",
            "EVENT_FILE": "file_pattern"
        }, f)
        temp_path = f.name

    try:
        # 清空缓存
        clusters._rules_cache.clear()

        # 测试: 内置 + 外部文件
        args = argparse.Namespace(
            include_experts=True,
            no_include_experts=False,
            rules_file=temp_path,
            custom_rules=None
        )
        rules = clusters.prepare_rules(args)

        assert "EVENT_SCHEDULER" in rules, "应包含内置规则"
        assert "EVENT_FILE" in rules, "应包含外部文件规则"
        assert rules["EVENT_IRQ_OFF"] == "overridden_by_file", "外部文件应覆盖内置"

        # 测试: 命令行最高优先级
        args2 = argparse.Namespace(
            include_experts=True,
            no_include_experts=False,
            rules_file=temp_path,
            custom_rules='{"EVENT_IRQ_OFF": "overridden_by_cli", "EVENT_CLI": "cli_pattern"}'
        )
        rules2 = clusters.prepare_rules(args2)

        assert rules2["EVENT_IRQ_OFF"] == "overridden_by_cli", "CLI应覆盖外部文件"
        assert rules2["EVENT_CLI"] == "cli_pattern", "应包含CLI规则"
        assert rules2["EVENT_FILE"] == "file_pattern", "应保留外部文件规则"
    finally:
        os.unlink(temp_path)
        clusters._rules_cache.clear()


def test_file_not_found():
    """测试: 文件不存在时抛出异常"""
    try:
        clusters.load_rules_from_file("/nonexistent/path/rules.json")
        assert False, "应抛出 FileNotFoundError"
    except FileNotFoundError as e:
        assert "/nonexistent/path/rules.json" in str(e)


def test_expert_rules_disabled():
    """测试: 禁用内置专家规则"""
    args = argparse.Namespace(
        include_experts=False,  # include_experts 为 False
        no_include_experts=True,  # no_include_experts 为 True
        rules_file=None,
        custom_rules='{"EVENT_CUSTOM": "custom"}'
    )
    rules = clusters.prepare_rules(args)

    assert "EVENT_IRQ_OFF" not in rules, "不应包含内置规则"
    assert "EVENT_CUSTOM" in rules, "应包含CLI规则"


def test_empty_rules():
    """测试: 空规则文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"_comment": "empty rules"}, f)
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


def test_module_level_expert_rules():
    """测试: 模块级 EXPERT_RULES 变量已加载"""
    # 模块导入时已加载
    assert clusters.EXPERT_RULES is not None, "EXPERT_RULES 应已加载"
    assert len(clusters.EXPERT_RULES) > 0, "EXPERT_RULES 不应为空"
    assert "EVENT_IRQ_OFF" in clusters.EXPERT_RULES, "应包含 EVENT_IRQ_OFF"


# 测试列表
TESTS = [
    ("默认规则路径", test_default_rules_path),
    ("默认规则加载", test_default_rules_loading),
    ("外部文件加载", test_load_rules_from_file),
    ("缓存机制", test_rules_caching),
    ("规则优先级合并", test_prepare_rules_priority),
    ("文件不存在处理", test_file_not_found),
    ("禁用内置规则", test_expert_rules_disabled),
    ("空规则文件", test_empty_rules),
    ("模块级 EXPERT_RULES", test_module_level_expert_rules),
]


def main():
    parser = argparse.ArgumentParser(description="Rules 加载与缓存测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="失败时停止")
    args = parser.parse_args()

    print(f"{Colors.BLUE}=== Rules 文件加载与缓存机制测试 ==={Colors.RESET}")
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
            result.add_fail(name, f"异常: {e}")
            if args.fail_fast:
                break

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
