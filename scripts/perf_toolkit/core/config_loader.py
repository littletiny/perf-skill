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
from typing import Dict, Optional

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

    # 默认配置路径（按优先级排序）
    DEFAULT_PATHS = [
        Path.home() / '.config' / 'perf-hunter' / 'perf-hunter.json',
        Path('.perf-hunter.json'),
        Path('config') / 'perf-hunter.json',
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
        for path in self.DEFAULT_PATHS:
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
        条件3: kernel_ratio > sys_critical（极高sys占比，单独触发）

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

        # 条件3: sys占比极高且 CPU 不低于门槛（加害人判定）
        condition3 = total_cpu > threshold.total_min and kernel_ratio > threshold.sys_critical

        return condition1 or condition2 or condition3

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
