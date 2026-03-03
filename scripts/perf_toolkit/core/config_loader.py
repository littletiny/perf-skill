#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Perf Hunter Unified Configuration Loader

统一加载 perf-hunter.json 配置，包含:
- risk: 风险显示配置
- rules: 分析规则
- comm_thresholds: 进程瓶颈判定阈值
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CommThreshold:
    """单个进程的阈值配置"""
    sensitive: float = 80.0   # 敏感阈值
    limit: float = 100.0      # 上限阈值
    sys_high: float = 30.0    # 高sys比例阈值（配合 sensitive）
    sys_critical: float = 80.0  # 极高sys比例阈值（配合 total_min 触发）
    total_min: float = 5.0    # sys_critical 触发的最低 CPU 门槛


@dataclass
class DisplayThreshold:
    """显示过滤阈值配置"""
    display_min: float = 10.0      # 显示的最小 total CPU
    sys_display_min: float = 10.0  # 显示的最小 sys CPU


@dataclass
class CPUSpecs:
    """CPU 规格配置"""
    core_count: int = 8                    # 核心数
    critical_utilization: float = 0.8      # 严重利用率阈值（相对于总容量）
    moderate_utilization: float = 0.5      # 中度利用率阈值
    critical_sys_per_core: float = 50.0    # 每核心严重 sys 阈值


@dataclass
class SensitiveCategory:
    """敏感进程分类"""
    name: str
    comms: List[str]
    message: str
    flag: str


@dataclass
class CommThresholdsConfig:
    """进程阈值配置"""
    global_threshold: CommThreshold = field(default_factory=CommThreshold)
    per_comm: Dict[str, CommThreshold] = field(default_factory=dict)


# =============================================================================
# Unified Config Loader
# =============================================================================

class UnifiedConfig:
    """统一配置加载器"""

    _instance = None
    _config_data = None

    # 默认配置路径 - 基于项目根目录
    @classmethod
    def _get_default_paths(cls):
        """获取默认配置路径（基于项目根目录）"""
        # 当前文件位置: scripts/perf_toolkit/core/config_loader.py
        # 项目根目录: 向上3层
        project_root = Path(__file__).parent.parent.parent.parent
        return [
            project_root / 'config' / 'perf-hunter.json',
        ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config_data is None:
            self._load_config()

    def _load_config(self):
        """加载配置文件"""
        self._config_data = self._get_default_config()

        # 按优先级加载配置
        for path in self._get_default_paths():
            if path.exists():
                self._merge_config(path)
                break

        # 环境变量覆盖
        if env_path := os.getenv('PERF_HUNTER_CONFIG'):
            if Path(env_path).exists():
                self._merge_config(Path(env_path))

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "comm_thresholds": {
                "global": {
                    "sensitive": 80.0,
                    "limit": 100.0,
                    "sys_high": 30.0
                },
                "per_comm": {}
            }
        }

    def _merge_config(self, path: Path):
        """合并配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'comm_thresholds' in data:
                ct = data['comm_thresholds']
                if 'global' in ct:
                    self._config_data['comm_thresholds']['global'].update(ct['global'])
                if 'per_comm' in ct:
                    self._config_data['comm_thresholds']['per_comm'].update(ct['per_comm'])

            if 'rules' in data:
                self._config_data['rules'] = data['rules']

            if 'cpu_specs' in data:
                self._config_data['cpu_specs'] = data['cpu_specs']

            if 'display_threshold' in data:
                self._config_data['display_threshold'] = data['display_threshold']

            if 'risk' in data:
                self._config_data['risk'] = data['risk']

        except (json.JSONDecodeError, IOError):
            pass

    def get_comm_threshold(self, comm: str) -> CommThreshold:
        """
        获取指定进程的阈值配置

        Args:
            comm: 进程名

        Returns:
            CommThreshold: 该进程的配置（未配置则返回全局默认值）
        """
        per_comm = self._config_data.get('comm_thresholds', {}).get('per_comm', {})

        if comm in per_comm:
            cfg = per_comm[comm]
            return CommThreshold(
                sensitive=cfg.get('sensitive', 80.0),
                limit=cfg.get('limit', 100.0),
                sys_high=cfg.get('sys_high', 30.0),
                sys_critical=cfg.get('sys_critical', 80.0),
                total_min=cfg.get('total_min', 5.0)
            )

        # 返回全局默认值
        global_cfg = self._config_data.get('comm_thresholds', {}).get('global', {})
        return CommThreshold(
            sensitive=global_cfg.get('sensitive', 80.0),
            limit=global_cfg.get('limit', 100.0),
            sys_high=global_cfg.get('sys_high', 30.0),
            sys_critical=global_cfg.get('sys_critical', 80.0),
            total_min=global_cfg.get('total_min', 5.0)
        )

    def is_bottleneck(self, comm: str, total_cpu: float, kernel_cpu: float) -> bool:
        """
        判定是否为瓶颈

        条件1: total_cpu > sensitive 且 kernel_ratio > sys_high
        条件2: total_cpu >= limit
        条件3: kernel_cpu > sys_critical（绝对值，极高sys消耗）

        Args:
            comm: 进程名
            total_cpu: 总CPU利用率
            kernel_cpu: 内核态CPU利用率

        Returns:
            bool: 是否为瓶颈
        """
        threshold = self.get_comm_threshold(comm)

        # 条件1: 高于敏感阈值且sys高
        kernel_ratio = (kernel_cpu / total_cpu * 100) if total_cpu > 0 else 0
        condition1 = total_cpu > threshold.sensitive and kernel_ratio > threshold.sys_high

        # 条件2: 达到或超过limit
        condition2 = total_cpu >= threshold.limit

        # 条件3: sys绝对值极高且 CPU 不低于门槛（加害人判定）
        condition3 = total_cpu > threshold.total_min and kernel_cpu > threshold.sys_critical

        return condition1 or condition2 or condition3

    def get_display_threshold(self) -> DisplayThreshold:
        """
        获取显示过滤阈值配置
        
        Returns:
            DisplayThreshold: 显示阈值配置
        """
        display_cfg = self._config_data.get('display_threshold', {})
        return DisplayThreshold(
            display_min=display_cfg.get('display_min', 10.0),
            sys_display_min=display_cfg.get('sys_display_min', 10.0)
        )

    def get_cpu_specs(self) -> CPUSpecs:
        """
        获取 CPU 规格配置
        
        Returns:
            CPUSpecs: CPU 规格配置
        """
        specs_cfg = self._config_data.get('cpu_specs', {})
        thresholds = specs_cfg.get('thresholds', {})
        return CPUSpecs(
            core_count=specs_cfg.get('core_count', 8),
            critical_utilization=thresholds.get('critical_utilization', 0.8),
            moderate_utilization=thresholds.get('moderate_utilization', 0.5),
            critical_sys_per_core=thresholds.get('critical_sys_per_core', 50.0)
        )

    def get_sensitive_categories(self) -> List[SensitiveCategory]:
        """
        获取敏感进程分类配置
        
        Returns:
            List[SensitiveCategory]: 敏感进程分类列表
        """
        rules_cfg = self._config_data.get('rules', {})
        sensitive_cfg = rules_cfg.get('sensitive_comms', {})
        categories = sensitive_cfg.get('categories', [])
        
        result = []
        for cat in categories:
            result.append(SensitiveCategory(
                name=cat.get('name', 'UNKNOWN'),
                comms=cat.get('comms', []),
                message=cat.get('message', ''),
                flag=cat.get('flag', '<X1>')
            ))
        return result

    @classmethod
    def reload(cls):
        """重新加载配置（用于热更新）"""
        cls._config_data = None
        cls._instance = None


# =============================================================================
# Global Access
# =============================================================================

def get_config() -> UnifiedConfig:
    """获取全局配置实例"""
    return UnifiedConfig()


def get_comm_threshold(comm: str) -> CommThreshold:
    """便捷函数：获取指定进程的阈值"""
    return get_config().get_comm_threshold(comm)


def is_bottleneck(comm: str, total_cpu: float, kernel_cpu: float) -> bool:
    """便捷函数：判定是否为瓶颈"""
    return get_config().is_bottleneck(comm, total_cpu, kernel_cpu)
