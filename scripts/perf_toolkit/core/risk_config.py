#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Risk Display Configuration - JSON format with built-in defaults

极简设计原则:
- 无 emoji 图标
- 无缩进
- 纯文本输出
- 级别使用大写标签 [CRITICAL]/[WARNING]/[INFO]
- Hint 使用箭头前缀 →
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional


# 内置默认配置（硬编码，确保无配置文件也能运行）
DEFAULT_CONFIG = {
    "colors": {
        "critical": "\033[91m",
        "warning": "\033[93m",
        "info": "\033[94m",
        "reset": "\033[0m"
    },
    "templates": {
        "issue_open": "[OPEN] [{id}] [{level}] {desc}",
        "issue_resolved": "[RESOLVED] [{id}] [{level}] {desc}",
        "hint": "→ {hint}",
        "result": "→ {result}",
        "list_header_open": "[OPEN] {count} issues pending",
        "list_header_resolved": "[RESOLVED] {count} issues",
        "list_header_all": "[ALL] {open_count} open, {resolved_count} resolved",
        "timeline_command": "[{seq}] {time} {command}",
        "timeline_finding_created": "[{level}] {issue_id}: {desc}",
        "timeline_finding_resolved": "[RESOLVED] {issue_id}: {result}",
        "timeline_info": "[INFO] {message}"
    },
    "show": {
        "hint": True,
        "result": True
    }
}


@dataclass
class RiskDisplayConfig:
    """Risk 展示配置 - 控制 trace 命令的输出格式"""

    colors: Dict[str, str] = field(default_factory=lambda: DEFAULT_CONFIG["colors"].copy())
    templates: Dict[str, str] = field(default_factory=lambda: DEFAULT_CONFIG["templates"].copy())
    show: Dict[str, bool] = field(default_factory=lambda: DEFAULT_CONFIG["show"].copy())

    @classmethod
    def load(cls, explicit_path: Optional[str] = None) -> 'RiskDisplayConfig':
        """
        加载配置

        优先级（从低到高）：
        1. 内置默认（硬编码）
        2. ~/.config/spear/risk.json
        3. .spear/risk.json
        4. SPEAR_RISK_CONFIG 环境变量
        5. 显式指定路径
        """
        config = cls()

        # 搜索路径（按优先级排序）
        search_paths = [
            Path.home() / '.config' / 'spear' / 'risk.json',
            Path('.spear/risk.json'),
        ]

        # 按顺序合并（后覆盖前）
        for path in search_paths:
            if path.exists():
                config._merge_from_file(path)

        # 环境变量指定
        if env_path := os.getenv('SPEAR_RISK_CONFIG'):
            if Path(env_path).exists():
                config._merge_from_file(Path(env_path))

        # 显式指定（最高优先级）
        if explicit_path and Path(explicit_path).exists():
            config._merge_from_file(Path(explicit_path))

        return config

    def _merge_from_file(self, path: Path):
        """从 JSON 文件合并配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict) or 'risk' not in data:
                return

            risk_data = data['risk']

            if 'colors' in risk_data:
                self.colors.update(risk_data['colors'])
            if 'templates' in risk_data:
                self.templates.update(risk_data['templates'])
            if 'show' in risk_data:
                self.show.update(risk_data['show'])

        except (json.JSONDecodeError, IOError, KeyError):
            pass

    def apply_mode(self, mode: str):
        """应用模式覆盖（从配置文件中查找 modes 部分）"""
        # 从已加载的配置文件中查找 modes
        for path in [Path('.spear/risk.json'), Path.home() / '.config' / 'spear' / 'risk.json']:
            if not path.exists():
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, dict) or 'modes' not in data:
                    continue

                if mode in data['modes']:
                    mode_data = data['modes'][mode]
                    if 'colors' in mode_data:
                        self.colors.update(mode_data['colors'])
                    if 'templates' in mode_data:
                        self.templates.update(mode_data['templates'])
                    if 'show' in mode_data:
                        self.show.update(mode_data['show'])
                    break

            except (json.JSONDecodeError, IOError):
                continue


# 全局配置缓存
_config_cache = None

def get_risk_config(explicit_path: str = None, mode: str = None) -> RiskDisplayConfig:
    """获取全局 Risk 配置"""
    global _config_cache
    if _config_cache is None:
        _config_cache = RiskDisplayConfig.load(explicit_path)
    if mode:
        _config_cache.apply_mode(mode)
    return _config_cache


def clear_risk_config_cache():
    """清除配置缓存（用于测试）"""
    global _config_cache
    _config_cache = None
