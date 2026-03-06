#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization

V3 版本（三层架构）：
- 提取 CoreDistAnalyzer 纯逻辑类
- 分析各 CPU 核心的负载分布
- Task-2.4.1: 返回 CoreDistributionResult dataclass

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import ImbalanceLevel, Thresholds

from .base import BaseAnalyzer
from ..core.engine_types import Sample
from ..core.models import RiskInfo
from ..core.config_loader import get_analysis_thresholds
from .models import CoreStat, CoreDistributionResult


def parse_cpu_quota(value: str) -> float:
    """
    Parse CPU quota string to float.
    
    Args:
        value: CPU quota string like '0.1c', '2c', '0.5'
        
    Returns:
        CPU quota as float (cores)
    """
    if value.endswith('c'):
        return float(value[:-1])
    return float(value)


class CoreDistAnalyzer(BaseAnalyzer):
    """
    核心分布分析器
    
    分析各 CPU 核心的负载分布，识别负载不均衡。
    """
    
    def analyze(self, samples: List[Sample], top_n: int = 10) -> CoreDistributionResult:
        """
        分析核心级负载分布
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个饱和核心
            
        Returns:
            CoreDistributionResult dataclass
        """
        # 获取分析阈值配置
        thresholds = get_analysis_thresholds()
        
        if not samples:
            return CoreDistributionResult(
                cores=[],
                imbalance_level="UNKNOWN",
                saturated_cores=[],
                total_cores=0,
                risks=[]
            )
        
        # 1. 从 engine 获取核心级 CPU 利用率
        core_util = self._engine.get_core_cpu_util(samples)
        
        # 2. 构建核心列表
        cores: List[CoreStat] = []
        for cpu_id, info in sorted(core_util.items(), key=lambda x: x[1].total_pct, reverse=True):
            cores.append(CoreStat(
                cpu_id=cpu_id,
                total_cpu=info.total_pct,
                kernel_cpu=info.kernel_pct,
                user_cpu=info.user_pct
            ))
        
        # 3. 检测不均衡
        imbalance_level = ImbalanceLevel.NORMAL
        saturated_cores: List[CoreStat] = []
        risks: List[RiskInfo] = []
        
        if len(cores) >= 2:
            max_util = cores[0].total_cpu
            min_util = cores[-1].total_cpu
            avg_util = sum(c.total_cpu for c in cores) / len(cores)
            
            imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
            
            # 分级判断
            if imbalance_ratio > thresholds.imbalance_ratio_critical and max_util > thresholds.cpu_util_medium:
                imbalance_level = ImbalanceLevel.CRITICAL
            elif imbalance_ratio > thresholds.imbalance_high:
                imbalance_level = ImbalanceLevel.HIGH
            elif imbalance_ratio > thresholds.imbalance_medium:
                imbalance_level = ImbalanceLevel.MODERATE
            else:
                imbalance_level = ImbalanceLevel.NORMAL
            
            # 识别饱和核心
            saturated_cores = [c for c in cores if c.total_cpu > thresholds.core_saturated_threshold]
            
            # 识别 risk
            if imbalance_level == ImbalanceLevel.CRITICAL:
                risks.append(self._create_risk(
                    level="critical",
                    message="Load severely imbalanced: one core saturated",
                    hint="Use sys-audit for system audit",
                    patterns=["SINGLE_CORE_SATURATION"]
                ))
            elif len(saturated_cores) == 1 and len(cores) > 1:
                risks.append(self._create_risk(
                    level="warning",
                    message=f"Single-core saturation (CPU {saturated_cores[0].cpu_id})",
                    hint="Use sys-audit for load distribution analysis",
                    patterns=["SINGLE_CORE_SATURATION"],
                    pending_targets=[f"cpu_{saturated_cores[0].cpu_id}"]
                ))
        
        return CoreDistributionResult(
            cores=cores[:top_n],
            imbalance_level=imbalance_level,
            saturated_cores=saturated_cores,
            total_cores=len(cores),
            risks=risks
        )
