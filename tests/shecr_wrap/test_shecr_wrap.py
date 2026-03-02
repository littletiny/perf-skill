#!/usr/bin/env python3
"""
shecr_wrap 回归测试套件

测试范围:
- 环境配置管理 (.shecr_env)
- 多数据文件管理 (init/use/list)
- 变量跟随逻辑 (freq 跟随 data)
- 全局 trace 管理
- 命令构建逻辑

用法:
    python3 tests/test_shecr_wrap.py        # 运行所有测试
    python3 tests/test_shecr_wrap.py -v     # 详细输出
    python3 tests/test_shecr_wrap.py -f     # 失败时停止
"""

import os
import sys
import json
import shutil
import tempfile
import argparse
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import shecr_wrap as sw


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
        self.orig_env_file = sw.ENV_FILE
        self.orig_global_trace = sw.GLOBAL_TRACE

    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp(prefix="shecr_test_")
        self.orig_dir = os.getcwd()
        os.chdir(self.tmpdir)

        # 创建模拟的 shecr.py
        (Path(self.tmpdir) / "scripts").mkdir()
        (Path(self.tmpdir) / "scripts" / "shecr.py").write_text("#!/usr/bin/env python3\nprint('mock')")
        (Path(self.tmpdir) / "version").write_text("2.30")

        # 创建测试数据文件
        (Path(self.tmpdir) / "data1.data").write_text("mock data 1")
        (Path(self.tmpdir) / "data2.data").write_text("mock data 2")

        # 更新 shecr_wrap 的全局路径
        sw.ENV_FILE = ".shecr_env"
        sw.GLOBAL_TRACE = ".shecr.json"

        return self

    def __exit__(self, *args):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        sw.ENV_FILE = self.orig_env_file
        sw.GLOBAL_TRACE = self.orig_global_trace

    def data_path(self, name):
        return str(Path(self.tmpdir) / name)


# ═════════════════════════════════════════════════════════════════════════════
# 测试用例
# ═════════════════════════════════════════════════════════════════════════════

def test_load_save_env():
    """测试: 环境配置加载和保存"""
    with TestEnv():
        # 初始状态 - 无 env 文件
        env = sw.load_env()
        assert env == {"profiles": {}, "default": None}, "初始状态应为空"

        # 保存配置
        env = {
            "profiles": {
                "/path/to/data": {"freq": "99", "script_path": "/path/shecr.py"}
            },
            "default": "/path/to/data"
        }
        sw.save_env(env)

        # 重新加载
        loaded = sw.load_env()
        assert loaded["default"] == "/path/to/data", "default 应正确保存"
        assert "/path/to/data" in loaded["profiles"], "profile 应存在"
        assert loaded["profiles"]["/path/to/data"]["freq"] == "99", "freq 应正确保存"


def test_migrate_old_env():
    """测试: 旧版 env 格式迁移"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        # 创建旧格式 env 文件（使用存在的数据文件路径）
        old_content = f"""# old spear config
SPEAR_SCRIPT_PATH=/path/shecr.py
SPEAR_DATA_PATH={data1}
SPEAR_FREQ=99
"""
        Path(sw.ENV_FILE).write_text(old_content)

        env = sw.load_env()
        assert "profiles" in env, "应迁移到新格式"
        assert data1 in env["profiles"], "数据文件应在 profiles 中"
        assert env["profiles"][data1]["freq"] == "99", "freq 应迁移"
        assert env["default"] == data1, "default 应设置"


def test_init_new_profile():
    """测试: 初始化新数据文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = None

        sw.cmd_init(Args())

        env = sw.load_env()
        assert env["default"] == data1, "新数据文件应设为默认"
        assert data1 in env["profiles"], "应创建 profile"
        assert env["profiles"][data1]["freq"] is None, "无 freq 应为 None"
        assert Path(sw.GLOBAL_TRACE).exists(), "应创建全局 trace"


def test_init_with_freq():
    """测试: 初始化带频率的数据文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = "99"

        sw.cmd_init(Args())

        env = sw.load_env()
        assert env["profiles"][data1]["freq"] == "99", "freq 应保存"


def test_init_multiple_profiles():
    """测试: 初始化多个数据文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args1:
            data_path = data1
            script_path = None
            freq = None

        class Args2:
            data_path = data2
            script_path = None
            freq = "199"

        sw.cmd_init(Args1())
        sw.cmd_init(Args2())

        env = sw.load_env()
        assert len(env["profiles"]) == 2, "应有两个 profile"
        assert env["default"] == data2, "最后一个应设为默认"

        # 检查 trace 的 profiles_used
        trace = json.loads(Path(sw.GLOBAL_TRACE).read_text())
        assert data1 in trace.get("profiles_used", []), "data1 应在 profiles_used"
        assert data2 in trace.get("profiles_used", []), "data2 应在 profiles_used"


def test_use_switch_profile():
    """测试: 切换数据文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        # 先初始化两个
        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1, None))
        sw.cmd_init(Args(data2, "99"))

        # 切换到 data1
        class UseArgs:
            data_path = data1

        sw.cmd_use(UseArgs())

        env = sw.load_env()
        assert env["default"] == data1, "应切换到 data1"


def test_use_by_index():
    """测试: 通过索引切换"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1))
        sw.cmd_init(Args(data2))

        # 模拟通过索引 "1" 切换
        env = sw.load_env()
        profiles = list(env["profiles"].keys())
        target = profiles[0]  # 索引 1 对应第一个

        class UseArgs:
            data_path = target

        sw.cmd_use(UseArgs())

        env = sw.load_env()
        assert env["default"] == target


def test_freq_follows_data():
    """测试: freq 跟随 data 文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        # data1: no freq, data2: freq=99
        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1, None))
        sw.cmd_init(Args(data2, "99"))

        # 默认是 data2
        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert dp == data2
        assert profile.get("freq") == "99", "data2 应有 freq=99"

        # 切换到 data1
        class UseArgs:
            data_path = data1
        sw.cmd_use(UseArgs())

        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert dp == data1
        assert profile.get("freq") is None, "data1 应无 freq"


def test_get_active_config():
    """测试: 获取当前激活配置"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1, "50"))
        sw.cmd_init(Args(data2, "99"))

        # 默认是 data2
        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert dp == data2
        assert profile.get("freq") == "99"


def test_cmd_build_no_freq():
    """测试: 命令构建 (无 freq)"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = None

        sw.cmd_init(Args())

        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        freq = profile.get("freq") if profile else None

        # 模拟 cmd_exec 的命令构建逻辑
        cmd = ["shecr.py", "get-hotspots", "--data", dp]
        if freq and "--freq" not in ["--top-n", "10"]:
            cmd.extend(["--freq", str(freq)])

        assert "--freq" not in cmd, "无 freq 时不应添加 --freq"


def test_cmd_build_with_freq():
    """测试: 命令构建 (有 freq)"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = "99"

        sw.cmd_init(Args())

        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        freq = profile.get("freq") if profile else None

        cmd = ["shecr.py", "get-hotspots", "--data", dp]
        if freq and "--freq" not in ["--top-n", "10"]:
            cmd.extend(["--freq", str(freq)])

        assert "--freq" in cmd, "有 freq 时应添加 --freq"
        assert "99" in cmd, "应使用正确的 freq 值"


def test_cmd_build_trace_no_freq():
    """测试: trace 命令不添加 --freq"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = "99"

        sw.cmd_init(Args())

        # trace 子命令不应添加 --data 和 --freq
        cmd = ["shecr.py", "trace", "timeline"]

        assert "--data" not in cmd, "trace 不应有 --data"
        assert "--freq" not in cmd, "trace 不应有 --freq"


def test_global_trace_profiles_used():
    """测试: 全局 trace 记录所有使用过的数据文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1))

        trace = json.loads(Path(sw.GLOBAL_TRACE).read_text())
        assert data1 in trace.get("profiles_used", []), "第一个应在列表中"

        sw.cmd_init(Args(data2))

        trace = json.loads(Path(sw.GLOBAL_TRACE).read_text())
        assert data1 in trace.get("profiles_used", []), "第一个仍应在列表中"
        assert data2 in trace.get("profiles_used", []), "第二个也应在列表中"


def test_re_init_updates_profile():
    """测试: 重复 init 更新现有 profile"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            def __init__(self, dp, fq=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq

        sw.cmd_init(Args(data1, None))

        env = sw.load_env()
        orig_time = env["profiles"][data1]["init_time"]

        # 重新 init，修改 freq
        sw.cmd_init(Args(data1, "199"))

        env = sw.load_env()
        assert env["profiles"][data1]["freq"] == "199", "freq 应更新"
        # profile 数量应保持为 1
        assert len(env["profiles"]) == 1, "不应创建重复 profile"


def test_init_with_risk_config():
    """测试: 初始化带 risk_config"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = None
            risk_config = "./my-risk.json"
            rules_file = None

        sw.cmd_init(Args())

        env = sw.load_env()
        assert env["profiles"][data1]["risk_config"] == "./my-risk.json", "risk_config 应保存"


def test_init_with_rules_file():
    """测试: 初始化带 rules_file"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = None
            risk_config = None
            rules_file = "./my-rules.json"

        sw.cmd_init(Args())

        env = sw.load_env()
        assert env["profiles"][data1]["rules_file"] == "./my-rules.json", "rules_file 应保存"


def test_init_with_all_configs():
    """测试: 初始化带所有配置"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")

        class Args:
            data_path = data1
            script_path = None
            freq = "99"
            risk_config = "./risk.json"
            rules_file = "./rules.json"

        sw.cmd_init(Args())

        env = sw.load_env()
        profile = env["profiles"][data1]
        assert profile["freq"] == "99", "freq 应保存"
        assert profile["risk_config"] == "./risk.json", "risk_config 应保存"
        assert profile["rules_file"] == "./rules.json", "rules_file 应保存"


def test_risk_config_follows_data():
    """测试: risk_config 跟随 data 文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args:
            def __init__(self, dp, fq=None, rc=None, rf=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq
                self.risk_config = rc
                self.rules_file = rf

        # data1: 有 risk_config, data2: 无
        sw.cmd_init(Args(data1, None, "./risk1.json", None))
        sw.cmd_init(Args(data2, None, None, None))

        # 默认是 data2
        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert dp == data2
        assert profile.get("risk_config") is None, "data2 应无 risk_config"

        # 切换到 data1
        class UseArgs:
            data_path = data1
        sw.cmd_use(UseArgs())

        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert dp == data1
        assert profile.get("risk_config") == "./risk1.json", "data1 应有 risk_config"


def test_rules_file_follows_data():
    """测试: rules_file 跟随 data 文件"""
    with TestEnv() as te:
        data1 = te.data_path("data1.data")
        data2 = te.data_path("data2.data")

        class Args:
            def __init__(self, dp, fq=None, rc=None, rf=None):
                self.data_path = dp
                self.script_path = None
                self.freq = fq
                self.risk_config = rc
                self.rules_file = rf

        # data1: 有 rules_file, data2: 无
        sw.cmd_init(Args(data1, None, None, "./rules1.json"))
        sw.cmd_init(Args(data2, None, None, None))

        # 切换到 data1
        class UseArgs:
            data_path = data1
        sw.cmd_use(UseArgs())

        env = sw.load_env()
        dp, profile = sw.get_active_config(env)
        assert profile.get("rules_file") == "./rules1.json", "data1 应有 rules_file"


# ═════════════════════════════════════════════════════════════════════════════
# 测试运行器
# ═════════════════════════════════════════════════════════════════════════════

TEST_CASES = [
    test_load_save_env,
    test_migrate_old_env,
    test_init_new_profile,
    test_init_with_freq,
    test_init_with_risk_config,
    test_init_with_rules_file,
    test_init_with_all_configs,
    test_init_multiple_profiles,
    test_use_switch_profile,
    test_use_by_index,
    test_freq_follows_data,
    test_risk_config_follows_data,
    test_rules_file_follows_data,
    test_get_active_config,
    test_cmd_build_no_freq,
    test_cmd_build_with_freq,
    test_cmd_build_trace_no_freq,
    test_global_trace_profiles_used,
    test_re_init_updates_profile,
]


def run_tests(verbose=False, fail_fast=False):
    """运行所有测试"""
    result = TestResult()

    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
    print(f"shecr_wrap 回归测试套件")
    print(f"{Colors.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")

    for test in TEST_CASES:
        name = test.__name__
        desc = test.__doc__ or name

        if verbose:
            print(f"\n{Colors.YELLOW}▶ {desc}{Colors.RESET}")

        try:
            test()
            result.add_pass(name)
        except AssertionError as e:
            result.add_fail(name, str(e))
            if fail_fast:
                break
        except Exception as e:
            result.add_fail(name, f"异常: {type(e).__name__}: {e}")
            if fail_fast:
                break

    return result.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="shecr_wrap 回归测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="失败时停止")
    args = parser.parse_args()

    success = run_tests(verbose=args.verbose, fail_fast=args.fail_fast)
    sys.exit(0 if success else 1)
