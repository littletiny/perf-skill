"""
环境管理公共函数
从 shecr_wrap.py 迁移
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from dataclasses import asdict

from perf_toolkit.core.output_models import EnvironmentConfig, ProfileConfig, TraceData


ENV_FILE = ".shecr_env"
GLOBAL_TRACE = ".shecr.json"


def get_script_dir() -> Path:
    """获取脚本所在目录"""
    return Path(__file__).parent.parent.parent.resolve()


def get_default_script_path() -> Path:
    """获取默认 shecr.py 路径"""
    return get_script_dir() / "shecr.py"


def load_env() -> EnvironmentConfig:
    """加载环境配置"""
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

                )
                for name, pdata in profiles_data.items()
            }
            return EnvironmentConfig(profiles=profiles, default=data.get("default"))
        except json.JSONDecodeError:
            return migrate_old_env()
    return EnvironmentConfig()


def migrate_old_env() -> EnvironmentConfig:
    """迁移旧版 env 格式到新版 JSON"""
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
    """保存环境配置"""
    Path(ENV_FILE).write_text(json.dumps(asdict(env), indent=2))


def get_active_config(env: EnvironmentConfig) -> Tuple[Optional[str], Optional[ProfileConfig]]:
    """获取当前激活的配置"""
    default_path = env.default
    if default_path and default_path in env.profiles:
        return default_path, env.profiles[default_path]
    return None, None


def init_global_trace(data_path: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    初始化全局 trace 文件
    返回: (是否为新创建, trace_data dict 或 None)
    """
    trace_path = Path(GLOBAL_TRACE)
    if not trace_path.exists():
        trace_data = TraceData.create_new(data_path)
        trace_path.write_text(json.dumps(asdict(trace_data), indent=2))
        return True, asdict(trace_data)
    else:
        # 更新 profiles_used
        try:
            trace_data = json.loads(trace_path.read_text())
            if data_path not in trace_data.get("profiles_used", []):
                trace_data["profiles_used"].append(data_path)
                trace_data["updated_at"] = datetime.now().isoformat()
                trace_path.write_text(json.dumps(trace_data, indent=2))
        except (json.JSONDecodeError, KeyError, TypeError, IOError):
            pass
        return False, None
