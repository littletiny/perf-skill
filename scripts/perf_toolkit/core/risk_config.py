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

常量定义统一从 config.defaults 导入。
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import RiskDisplayDefaults


# =============================================================================
# Risk Config Data Models
# =============================================================================

@dataclass
class RiskConfigColors:
    """Risk 配置颜色 - 使用 defaults 中的常量"""
    critical: str = RiskDisplayDefaults.COLOR_CRITICAL
    warning: str = RiskDisplayDefaults.COLOR_WARNING
    info: str = RiskDisplayDefaults.COLOR_INFO
    reset: str = RiskDisplayDefaults.COLOR_RESET


@dataclass
class RiskConfigTemplates:
    """Risk 配置模板 - 使用 defaults 中的常量"""
    issue_open: str = RiskDisplayDefaults.TEMPLATE_ISSUE_OPEN
    issue_resolved: str = RiskDisplayDefaults.TEMPLATE_ISSUE_RESOLVED
    hint: str = RiskDisplayDefaults.TEMPLATE_HINT
    result: str = RiskDisplayDefaults.TEMPLATE_RESULT
    list_header_open: str = RiskDisplayDefaults.TEMPLATE_LIST_HEADER_OPEN
    list_header_resolved: str = RiskDisplayDefaults.TEMPLATE_LIST_HEADER_RESOLVED
    list_header_all: str = RiskDisplayDefaults.TEMPLATE_LIST_HEADER_ALL
    timeline_command: str = RiskDisplayDefaults.TEMPLATE_TIMELINE_COMMAND
    timeline_finding_created: str = RiskDisplayDefaults.TEMPLATE_TIMELINE_FINDING_CREATED
    timeline_finding_resolved: str = RiskDisplayDefaults.TEMPLATE_TIMELINE_FINDING_RESOLVED
    timeline_info: str = RiskDisplayDefaults.TEMPLATE_TIMELINE_INFO


@dataclass
class RiskConfigShow:
    """Risk 配置显示开关"""
    hint: bool = True
    result: bool = True


@dataclass
class RiskConfigData:
    """Risk 配置完整结构"""
    colors: RiskConfigColors = field(default_factory=RiskConfigColors)
    templates: RiskConfigTemplates = field(default_factory=RiskConfigTemplates)
    show: RiskConfigShow = field(default_factory=RiskConfigShow)


# =============================================================================
# RiskDisplayConfig
# =============================================================================

@dataclass
class RiskDisplayConfig:
    """Risk 展示配置 - 控制 trace 命令的输出格式"""

    _config: RiskConfigData = field(default_factory=RiskConfigData)

    @property
    def colors(self) -> Dict[str, str]:
        return asdict(self._config.colors)

    @colors.setter
    def colors(self, value: Dict[str, str]):
        self._config.colors = RiskConfigColors(**value)

    @property
    def templates(self) -> Dict[str, str]:
        return asdict(self._config.templates)

    @templates.setter
    def templates(self, value: Dict[str, str]):
        self._config.templates = RiskConfigTemplates(**value)

    @property
    def show(self) -> Dict[str, bool]:
        return asdict(self._config.show)

    @show.setter
    def show(self, value: Dict[str, bool]):
        self._config.show = RiskConfigShow(**value)

    def get_config_data(self) -> RiskConfigData:
        """获取 RiskConfigData dataclass（类型安全访问）"""
        return self._config

    @classmethod
    def load(cls, explicit_path: Optional[str] = None) -> 'RiskDisplayConfig':
        """
        加载配置

        优先级（从低到高）：
        1. 内置默认（硬编码）
        2. ~/.config/shecr/risk.json
        3. .shecr/risk.json
        4. SPEAR_RISK_CONFIG 环境变量
        5. 显式指定路径
        """
        config = cls()

        search_paths = [
            Path.home() / '.config' / 'shecr' / 'risk.json',
            Path('.shecr/risk.json'),
        ]

        for path in search_paths:
            if path.exists():
                config._merge_from_file(path)

        if env_path := os.getenv('SPEAR_RISK_CONFIG'):
            if Path(env_path).exists():
                config._merge_from_file(Path(env_path))

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
                current = asdict(self._config.colors)
                current.update(risk_data['colors'])
                self._config.colors = RiskConfigColors(**current)
            if 'templates' in risk_data:
                current = asdict(self._config.templates)
                current.update(risk_data['templates'])
                self._config.templates = RiskConfigTemplates(**current)
            if 'show' in risk_data:
                current = asdict(self._config.show)
                current.update(risk_data['show'])
                self._config.show = RiskConfigShow(**current)

        except (json.JSONDecodeError, IOError, KeyError):
            pass

    def apply_mode(self, mode: str):
        """应用模式覆盖（从配置文件中查找 modes 部分）"""
        for path in [Path('.shecr/risk.json'), Path.home() / '.config' / 'shecr' / 'risk.json']:
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
                        current = asdict(self._config.colors)
                        current.update(mode_data['colors'])
                        self._config.colors = RiskConfigColors(**current)
                    if 'templates' in mode_data:
                        current = asdict(self._config.templates)
                        current.update(mode_data['templates'])
                        self._config.templates = RiskConfigTemplates(**current)
                    if 'show' in mode_data:
                        current = asdict(self._config.show)
                        current.update(mode_data['show'])
                        self._config.show = RiskConfigShow(**current)
                    break

            except (json.JSONDecodeError, IOError):
                continue


# =============================================================================
# Global Config Cache
# =============================================================================

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
