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
class AnalysisThresholds:
    """分析阈值配置 - 所有分析模块使用的阈值"""
    # Monopoly 阈值
    monopoly_high: float = 0.8
    monopoly_critical: float = 0.9
    
    # CV (变异系数) 阈值
    cv_unbalanced: float = 1.0
    cv_high: float = 2.0
    cv_affinity_uniform: float = 0.5
    cv_unbalanced_load: float = 1.5
    
    # CPU 利用率阈值
    cpu_util_low: float = 30.0
    cpu_util_medium: float = 50.0
    cpu_util_high: float = 80.0
    cpu_util_critical: float = 100.0
    cpu_secondary_min: float = 10.0  # 次要负载进程的最小CPU阈值
    
    # 内核态比例阈值
    kernel_ratio_high: float = 50.0
    kernel_ratio_critical: float = 70.0
    
    # Core Distribution 阈值
    core_saturated_threshold: float = 50.0
    imbalance_ratio_critical: float = 10.0
    imbalance_high: float = 5.0
    imbalance_medium: float = 2.0
    
    # Correlation Flags 阈值
    lock_contention_inclusive_pct: float = 40.0
    throttle_victim_cpu_max: float = 80.0
    throttle_rate_min: float = 50.0
    
    # 数据质量阈值
    reliability_min_duration: float = 1.0
    reliability_short_duration: float = 2.0
    reliability_medium_duration: float = 5.0
    reliability_long_duration: float = 10.0
    reliability_low_cpu_threshold: float = 5.0
    reliability_medium_cpu_threshold: float = 10.0
    reliability_high_cpu_threshold: float = 30.0
    
    # 其他阈值
    z_score_medium: float = 2.0
    z_score_high: float = 2.5
    min_sample_count_low: int = 1000
    min_sample_count_medium: int = 5000
    entropy_fixed_threshold: float = 1.0
    entropy_uniform_threshold: float = 1.8
    aggregated_ratio_threshold: float = 50.0
    impact_score_saliency_threshold: float = 0.5


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

            if 'analysis_thresholds' in data:
                self._config_data['analysis_thresholds'] = data['analysis_thresholds']

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

    def get_analysis_thresholds(self) -> AnalysisThresholds:
        """
        获取分析阈值配置
        
        Returns:
            AnalysisThresholds: 分析阈值配置
        """
        at_cfg = self._config_data.get('analysis_thresholds', {})
        return AnalysisThresholds(
            monopoly_high=at_cfg.get('monopoly_high', 0.8),
            monopoly_critical=at_cfg.get('monopoly_critical', 0.9),
            cv_unbalanced=at_cfg.get('cv_unbalanced', 1.0),
            cv_high=at_cfg.get('cv_high', 2.0),
            cv_affinity_uniform=at_cfg.get('cv_affinity_uniform', 0.5),
            cv_unbalanced_load=at_cfg.get('cv_unbalanced_load', 1.5),
            cpu_util_low=at_cfg.get('cpu_util_low', 30.0),
            cpu_util_medium=at_cfg.get('cpu_util_medium', 50.0),
            cpu_util_high=at_cfg.get('cpu_util_high', 80.0),
            cpu_util_critical=at_cfg.get('cpu_util_critical', 100.0),
            cpu_secondary_min=at_cfg.get('cpu_secondary_min', 10.0),
            kernel_ratio_high=at_cfg.get('kernel_ratio_high', 50.0),
            kernel_ratio_critical=at_cfg.get('kernel_ratio_critical', 70.0),
            core_saturated_threshold=at_cfg.get('core_saturated_threshold', 50.0),
            imbalance_ratio_critical=at_cfg.get('imbalance_ratio_critical', 10.0),
            imbalance_high=at_cfg.get('imbalance_high', 5.0),
            imbalance_medium=at_cfg.get('imbalance_medium', 2.0),
            lock_contention_inclusive_pct=at_cfg.get('lock_contention_inclusive_pct', 40.0),
            throttle_victim_cpu_max=at_cfg.get('throttle_victim_cpu_max', 80.0),
            throttle_rate_min=at_cfg.get('throttle_rate_min', 50.0),
            reliability_min_duration=at_cfg.get('reliability_min_duration', 1.0),
            reliability_short_duration=at_cfg.get('reliability_short_duration', 2.0),
            reliability_medium_duration=at_cfg.get('reliability_medium_duration', 5.0),
            reliability_long_duration=at_cfg.get('reliability_long_duration', 10.0),
            reliability_low_cpu_threshold=at_cfg.get('reliability_low_cpu_threshold', 5.0),
            reliability_medium_cpu_threshold=at_cfg.get('reliability_medium_cpu_threshold', 10.0),
            reliability_high_cpu_threshold=at_cfg.get('reliability_high_cpu_threshold', 30.0),
            z_score_medium=at_cfg.get('z_score_medium', 2.0),
            z_score_high=at_cfg.get('z_score_high', 2.5),
            min_sample_count_low=at_cfg.get('min_sample_count_low', 1000),
            min_sample_count_medium=at_cfg.get('min_sample_count_medium', 5000),
            entropy_fixed_threshold=at_cfg.get('entropy_fixed_threshold', 1.0),
            entropy_uniform_threshold=at_cfg.get('entropy_uniform_threshold', 1.8),
            aggregated_ratio_threshold=at_cfg.get('aggregated_ratio_threshold', 50.0),
            impact_score_saliency_threshold=at_cfg.get('impact_score_saliency_threshold', 0.5),
        )

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


def get_analysis_thresholds() -> AnalysisThresholds:
    """便捷函数：获取分析阈值配置"""
    return get_config().get_analysis_thresholds()
