#!/usr/bin/env python3
"""
shecr_wrap - perf-hunter 包装脚本

支持多数据文件管理，全局 timeline 跟踪诊断过程
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import asdict

# Import dataclass models for CLI layer (Task-4.1.x)
# Use relative import from perf_toolkit package
def _import_cli_models():
    """导入 CLI 层 dataclass 模型"""
    core_path = Path(__file__).parent / "perf_toolkit" / "core"
    if str(core_path.parent) not in sys.path:
        sys.path.insert(0, str(core_path.parent))
    from core.output_models import EnvironmentConfig, ProfileConfig, TraceConfig
    return EnvironmentConfig, ProfileConfig, TraceConfig

EnvironmentConfig, ProfileConfig, TraceConfig = _import_cli_models()

ENV_FILE = ".shecr_env"
GLOBAL_TRACE = ".shecr.json"


def get_script_dir() -> Path:
    """获取脚本所在目录"""
    return Path(__file__).parent.resolve()


def get_default_script_path() -> Path:
    """获取默认 shecr.py 路径"""
    return get_script_dir() / "shecr.py"


def load_env() -> EnvironmentConfig:
    """加载环境配置 (Task-4.1.1: 返回 EnvironmentConfig dataclass)"""
    env_path = Path(ENV_FILE)
    if env_path.exists():
        try:
            data = json.loads(env_path.read_text())
            profiles_data = data.get("profiles", {})
            profiles = {
                name: ProfileConfig(
                    name=name,
                    data_file=name,
                    init_time=pdata.get("init_time", ""),
                    script_path=pdata.get("script_path", ""),
                    freq=pdata.get("freq"),
                    risk_config=pdata.get("risk_config"),
                    rules_file=pdata.get("rules_file")
                )
                for name, pdata in profiles_data.items()
            }
            return EnvironmentConfig(profiles=profiles, default=data.get("default"))
        except json.JSONDecodeError:
            return migrate_old_env()
    return EnvironmentConfig()


def migrate_old_env() -> EnvironmentConfig:
    """迁移旧版 env 格式到新版 JSON (Task-4.1.2: 返回 EnvironmentConfig dataclass)"""
    env_path = Path(ENV_FILE)
    old_env = {}
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            old_env[key] = value

    data_path = old_env.get("SPEAR_DATA_PATH")
    if data_path and Path(data_path).exists():
        profile = ProfileConfig(
            name=data_path,
            data_file=data_path,
            init_time=datetime.now().isoformat(),
            script_path=old_env.get("SPEAR_SCRIPT_PATH", str(get_default_script_path())),
            freq=old_env.get("SPEAR_FREQ")
        )
        return EnvironmentConfig(
            profiles={data_path: profile},
            default=data_path
        )
    return EnvironmentConfig()


def save_env(env: EnvironmentConfig):
    """保存环境配置 (接受 EnvironmentConfig dataclass)"""
    Path(ENV_FILE).write_text(json.dumps(asdict(env), indent=2))


def get_profile_id(data_path: str) -> str:
    """根据数据路径生成 profile ID"""
    return hashlib.md5(data_path.encode()).hexdigest()[:8]


def init_global_trace(data_path: str) -> Tuple[bool, Optional[TraceConfig]]:
    """初始化全局 trace 文件 (Task-4.1.3: 返回 TraceConfig dataclass)
    
    Returns:
        Tuple[bool, Optional[TraceConfig]]: (是否为新创建, TraceConfig实例或None)
    """
    trace_path = Path(GLOBAL_TRACE)
    if not trace_path.exists():
        trace = TraceConfig.create_new(data_path)
        trace_path.write_text(json.dumps(asdict(trace), indent=2))
        return True, trace
    else:
        # 更新 profiles_used
        try:
            trace_data = json.loads(trace_path.read_text())
            trace = TraceConfig(**trace_data)
            if data_path not in trace.profiles_used:
                trace.profiles_used.append(data_path)
                trace.updated_at = datetime.now().isoformat()
                trace_path.write_text(json.dumps(asdict(trace), indent=2))
        except:
            pass
        return False, None


def cmd_init(args):
    """初始化配置"""
    data_path = Path(args.data_path).resolve()
    if not data_path.exists():
        print(f"Error: 数据文件不存在: {data_path}")
        sys.exit(1)

    script_path = Path(args.script_path).resolve() if args.script_path else get_default_script_path()
    if not script_path.exists():
        print(f"Error: 脚本不存在: {script_path}")
        sys.exit(1)

    env = load_env()
    data_path_str = str(data_path)

    # 创建或更新 profile (Task-4.1.4: 使用 ProfileConfig dataclass)
    profile = ProfileConfig(
        name=data_path_str,
        data_file=data_path_str,
        init_time=datetime.now().isoformat(),
        script_path=str(script_path),
        freq=args.freq,
        risk_config=getattr(args, 'risk_config', None),
        rules_file=getattr(args, 'rules_file', None)
    )

    is_new = data_path_str not in env.profiles
    env.profiles[data_path_str] = profile
    env.default = data_path_str
    save_env(env)

    if is_new:
        print(f"✓ 数据文件已添加: {data_path}")
    else:
        print(f"✓ 数据文件已更新: {data_path}")

    # 初始化 trace（如果不存在）或更新 profiles_used
    is_new_trace, _ = init_global_trace(data_path_str)

    if is_new_trace:
        print(f"✓ Trace 文档已创建: {GLOBAL_TRACE}")
    else:
        print(f"✓ Trace 文档已更新")

    print()
    cmd_status()


def cmd_use(args):
    """切换默认数据文件"""
    data_path = Path(args.data_path).resolve()
    data_path_str = str(data_path)

    env = load_env()

    # 如果路径不存在，尝试模糊匹配
    if data_path_str not in env.profiles:
        # 尝试匹配文件名
        for profile_path in env.profiles:
            if profile_path.endswith(f"/{data_path.name}") or profile_path == data_path.name:
                data_path_str = profile_path
                data_path = Path(profile_path)
                break
        else:
            print(f"Error: 数据文件未配置: {data_path}")
            print("请先运行: shecr init --data-path", data_path)
            sys.exit(1)

    env.default = data_path_str
    save_env(env)

    profile = env.profiles[data_path_str]
    print(f"✓ 已切换到: {data_path}")
    print(f"  初始化时间: {profile.init_time}")
    if profile.freq:
        print(f"  采样频率: {profile.freq}Hz")
    if profile.risk_config:
        print(f"  Risk配置: {profile.risk_config}")
    if profile.rules_file:
        print(f"  规则配置: {profile.rules_file}")


def cmd_list():
    """列出所有已配置的数据文件"""
    env = load_env()

    if not env.profiles:
        print("未配置任何数据文件")
        print("请运行: shecr init --data-path <path>")
        return

    # 读取全局 trace，获取使用统计
    profiles_used = []
    trace_path = Path(GLOBAL_TRACE)
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text())
            profiles_used = trace.get("profiles_used", [])
        except:
            pass

    print("=== 已配置的数据文件 ===")
    print()

    default_path = env.default

    for i, (path, profile) in enumerate(env.profiles.items(), 1):
        marker = "▶" if path == default_path else " "
        used = "✓" if path in profiles_used else " "
        display_path = path if len(path) <= 60 else f"...{path[-57:]}"
        print(f"{marker} [{i}] {display_path} [{used}]")
        if profile.freq:
            print(f"       Freq: {profile.freq}Hz")
        if profile.risk_config:
            print(f"       Risk: {profile.risk_config}")
        if profile.rules_file:
            print(f"       Rules: {profile.rules_file}")
        print()

    print("图例: ▶ 当前默认  ✓ 已在 trace 中使用")
    print()
    print("提示: 使用 'shecr use <path|index>' 切换默认数据文件")


def cmd_status():
    """显示状态"""
    env = load_env()

    print("=== shecr (perf-hunter) 环境配置 ===")
    print()
    print(f"配置文件: {Path.cwd() / ENV_FILE}")
    print(f"Trace 文件: {Path.cwd() / GLOBAL_TRACE}")
    print()

    if not env.profiles:
        print("未初始化。请运行: shecr init --data-path <path>")
        return

    default_path = env.default

    # 读取全局 trace 信息
    trace_path = Path(GLOBAL_TRACE)
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text())
            timeline_count = len(trace.get("timeline", []))
            issues_count = len(trace.get("issues", {}))
            open_issues = sum(1 for i in trace.get("issues", {}).values() if i.get("status") == "open")
            profiles_used = trace.get("profiles_used", [])

            print(f"Timeline: {timeline_count} 条命令记录")
            print(f"Issues: {issues_count} 个 ({open_issues} 个待处理)")
            print(f"涉及数据文件: {len(profiles_used)} 个")
            print()
        except:
            pass

    print(f"已配置 {len(env.profiles)} 个数据文件:")
    print()

    for path, profile in env.profiles.items():
        marker = "▶ " if path == default_path else "  "
        display_path = path if len(path) <= 60 else f"...{path[-57:]}"
        print(f"{marker}{display_path}")
        if profile.freq:
            print(f"    Freq: {profile.freq}Hz")
        if profile.risk_config:
            print(f"    Risk: {profile.risk_config}")
        if profile.rules_file:
            print(f"    Rules: {profile.rules_file}")
        print()

    if default_path:
        print("▶ 当前默认数据文件")
    print()
    print("提示: 使用 'shecr use <path>' 切换默认数据文件")


def get_active_config(env: EnvironmentConfig) -> Tuple[Optional[str], Optional[ProfileConfig]]:
    """获取当前激活的配置 (Task-4.1.5: 返回 ProfileConfig dataclass)"""
    # 使用默认配置
    default_path = env.default
    if default_path and default_path in env.profiles:
        return default_path, env.profiles[default_path]

    return None, None


def cmd_exec(subcommand: str, args: list):
    """执行 perf-hunter 命令"""
    env = load_env()
    data_path, profile = get_active_config(env)

    # trace 子命令特殊处理（不需要 data 文件配置，除了 init）
    if subcommand == "trace":
        # 如果 args 包含 init，需要检查 data 配置
        if args and args[0] == "init":
            if not data_path:
                print("Error: 未配置数据文件路径")
                print()
                print("请运行以下命令初始化:")
                print("  shecr init --data-path <path_to_perf.data.txt>")
                sys.exit(1)

        # 确定脚本路径（优先从 profile 读取）
        if profile and profile.script_path:
            script_path = Path(profile.script_path)
        else:
            script_path = get_default_script_path()

        if not script_path.exists():
            print(f"Error: 脚本不存在: {script_path}")
            sys.exit(1)

        # 构建命令
        # trace 命令格式: shecr.py trace <subcommand> [options]
        # --risk-config 需要在子命令之后
        cmd = ["python3", str(script_path), "trace"]

        # 提取子命令（如果有）
        trace_subcommand = None
        other_args = args
        if args and not args[0].startswith("-"):
            trace_subcommand = args[0]
            other_args = args[1:]
            cmd.append(trace_subcommand)

        # 自动注入 risk_config（如果 profile 有配置且用户未显式指定）
        if profile and profile.risk_config:
            if not any(arg.startswith("--risk-config") for arg in args):
                cmd.extend(["--risk-config", profile.risk_config])

        cmd.extend(other_args)
        os.execvp(cmd[0], cmd)
        return

    # 其他命令需要检查 data 文件配置
    if not data_path:
        print("Error: 未配置数据文件路径")
        print()
        print("请运行以下命令初始化:")
        print("  shecr init --data-path <path_to_perf.data.txt>")
        sys.exit(1)

    # 确定脚本路径
    if profile and profile.script_path:
        script_path = Path(profile.script_path)
    else:
        script_path = get_default_script_path()

    if not script_path.exists():
        print(f"Error: 脚本不存在: {script_path}")
        print("请检查配置或重新运行 shecr init")
        sys.exit(1)

    # 确定频率
    freq = profile.freq if profile else None

    # 构建命令
    cmd = ["python3", str(script_path)]
    cmd.extend([subcommand, "--data", data_path])

    # 自动注入频率
    if freq and "--freq" not in args:
        cmd.extend(["--freq", freq])

    # 自动注入 rules_file（仅限 cluster-symbols 命令）
    if subcommand == "cluster-symbols":
        if profile and profile.rules_file:
            if not any(arg.startswith("--rules-file") for arg in args):
                cmd.extend(["--rules-file", profile.rules_file])

    cmd.extend(args)

    # 执行
    os.execvp(cmd[0], cmd)


def show_help():
    """显示帮助信息"""
    help_text = """usage: shecr <command> [options]

perf-hunter 包装脚本 - 多数据文件全局跟踪

管理命令:
  init --data-path <path> [--freq <hz>]    添加并切换到新数据文件
  use <path|index>                         切换默认数据文件
  list                                     列出所有配置的数据文件
  status                                   显示当前配置和 trace 状态
  --help, -h                               显示此帮助
  --version, -v                            显示版本

分析子命令:
  check-cpu-bottleneck    检查资源限制和单核饱和
  get-hotspots            识别热点函数
  cluster-symbols         按专家规则聚类符号
  find-callers            热点溯源，调用链分析
  detect-anomalies        检测时序异常
  show-cpu-usage          查看 CPU 利用率
  get-process-top         进程 CPU 排行
  get-comm-top            按进程组统计 CPU
  cluster-comm            按进程名聚类
  cluster-paths           按调用路径聚类
  count-process-variety   检测进程风暴
  analyze-core-distribution  核心级负载分布分析
  trace                   Trace 诊断追踪管理

Trace 管理命令:
  trace timeline          查看完整 timeline（跨所有数据文件）
  trace issues            查看待处理 issues
  trace complete          标记 issue 完成
  trace finalize          最终审计
  trace export            导出报告

用法示例:
  # 添加第一个数据文件（自动设为默认）
  shecr init --data-path ./perf.data.txt

  # 添加第二个数据文件（用于同一问题的对比分析）
  shecr init --data-path ./perf2.data.txt --freq 99

  # 查看已配置的数据文件列表
  shecr list

  # 查看完整诊断 timeline（包含所有数据文件的分析）
  shecr trace timeline

  # 切换到第二个数据文件继续分析
  shecr use ./perf2.data.txt

  # 使用默认数据文件执行分析
  shecr get-hotspots --top-n 20

设计说明:
  - 全局 .shecr.json 记录整个诊断过程的 timeline
  - 多个数据文件的分析都汇总到同一个 timeline
  - 便于追踪跨数据文件的诊断路径和发现的问题
"""
    print(help_text)


def main():
    argv = sys.argv[1:]

    if not argv:
        show_help()
        return

    command = argv[0]
    remaining = argv[1:]

    if command in ("-h", "--help", "help"):
        show_help()
        return

    if command in ("-v", "--version", "version"):
        version_file = get_script_dir().parent / "version"
        version = version_file.read_text().strip() if version_file.exists() else "unknown"
        print(f"shecr (perf-hunter wrapper) version {version}")
        return

    if command == "init":
        parser = argparse.ArgumentParser(prog="shecr init", add_help=False)
        parser.add_argument("--data-path", required=True)
        parser.add_argument("--script-path")
        parser.add_argument("--freq")
        parser.add_argument("--risk-config", help="Risk display config file for trace commands")
        parser.add_argument("--rules-file", help="Expert rules file for cluster-symbols command")
        parser.add_argument("-h", "--help", action="store_true")

        args = parser.parse_args(remaining)
        if args.help:
            print("usage: shecr init --data-path <path> [--script-path <path>] [--freq <hz>] [--risk-config <path>] [--rules-file <path>]")
            print("\n添加新的数据文件，并设为默认")
            print("所有数据文件的分析都记录在同一个全局 timeline 中")
            print("\n选项:")
            print("  --risk-config    Risk display config file for trace commands")
            print("  --rules-file     Expert rules file for cluster-symbols command")
            return
        cmd_init(args)
        return

    if command == "use":
        if not remaining or remaining[0] in ("-h", "--help"):
            print("usage: shecr use <path|index>")
            print("\n切换到指定的数据文件")
            print("  path:  数据文件的完整路径或文件名")
            print("  index: 使用 'shecr list' 显示的索引号")
            return

        data_arg = remaining[0]
        env = load_env()

        try:
            index = int(data_arg)
            profiles = list(env.profiles.keys())
            if 1 <= index <= len(profiles):
                data_arg = profiles[index - 1]
            else:
                print(f"Error: 索引 {index} 超出范围 (1-{len(profiles)})")
                sys.exit(1)
        except ValueError:
            pass

        class Args:
            pass
        args = Args()
        args.data_path = data_arg
        cmd_use(args)
        return

    if command == "list":
        cmd_list()
        return

    if command == "status":
        cmd_status()
        return

    cmd_exec(command, remaining)


if __name__ == "__main__":
    main()
