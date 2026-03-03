#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization

V3 版本（三层架构）：
- 提取 CoreDistAnalyzer 纯逻辑类
- 分析各 CPU 核心的负载分布
- Task-2.4.1: 返回 CoreDistributionResult dataclass
"""

from typing import Dict, List, Optional
from collections import defaultdict
from .base import BaseAnalyzer
from ..core.engine_types import Sample
from .models import Risk, CoreStat, CoreDistributionResult


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
    
    # 不均衡阈值
    IMBALANCE_CRITICAL = 10.0   # 极不均衡
    IMBALANCE_HIGH = 5.0        # 严重不均衡
    IMBALANCE_MEDIUM = 2.0      # 中度不均衡
    SATURATION_THRESHOLD = 90.0  # 核心饱和阈值
    
    def analyze(self, samples: List[Sample], top_n: int = 10) -> CoreDistributionResult:
        """
        分析核心级负载分布
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个饱和核心
            
        Returns:
            CoreDistributionResult dataclass
        """
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
        imbalance_level = "LOW"
        saturated_cores: List[CoreStat] = []
        risks: List[Risk] = []
        
        if len(cores) >= 2:
            max_util = cores[0].total_cpu
            min_util = cores[-1].total_cpu
            avg_util = sum(c.total_cpu for c in cores) / len(cores)
            
            imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
            
            # 分级判断
            if imbalance_ratio > self.IMBALANCE_CRITICAL and max_util > 50:
                imbalance_level = "CRITICAL"
            elif imbalance_ratio > self.IMBALANCE_HIGH:
                imbalance_level = "HIGH"
            elif imbalance_ratio > self.IMBALANCE_MEDIUM:
                imbalance_level = "MEDIUM"
            else:
                imbalance_level = "LOW"
            
            # 识别饱和核心
            saturated_cores = [c for c in cores if c.total_cpu > self.SATURATION_THRESHOLD]
            
            # 识别 risk
            if imbalance_level == "CRITICAL":
                risks.append(self._create_risk(
                    level="critical",
                    message="负载严重不均衡: 单核满载，其他核心空闲",
                    hint="使用 sys-audit 进行系统审计",
                    patterns=["SINGLE_CORE_SATURATION"]
                ))
            elif len(saturated_cores) == 1 and len(cores) > 1:
                risks.append(self._create_risk(
                    level="warning",
                    message=f"单核满载 (CPU {saturated_cores[0].cpu_id})",
                    hint="使用 sys-audit 分析负载分布",
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
