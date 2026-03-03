#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Builder - 核心分布数据构建器

提供统一的核心分布数据构建接口，供以下模块使用：
- analyze-core-distribution 命令（简单列表视图）
- sys-audit 命令（丰富上下文视图）

避免重复代码，确保输出格式一致性。
"""

import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import AttentionFlag, ImbalanceLevel, Thresholds

from ..analysis.models import CoreDistributionResult
from ..composite.models import CoreDistributionReport, CoreStat
from .output_models import (
    CoreDistributionOutput, CoreDistributionData, 
    CoreDistributionSummary, CoreItem, CoreSaturationItem
)
from .models import RiskInfo


@dataclass
class CoreDistributionBuildOptions:
    """构建选项"""
    include_details: bool = False  # 是否包含详细信息（饱和核心列表）
    max_cores: int = 10  # 最大返回核心数
    saturation_threshold: float = 50.0  # 饱和阈值


class CoreDistributionBuilder:
    """
    核心分布数据构建器
    
    将 Analysis 层的 CoreDistributionResult 转换为各种输出格式。
    """
    
    @staticmethod
    def build_simple_output(
        result: CoreDistributionResult,
        top_risk: Optional[RiskInfo] = None
    ) -> CoreDistributionOutput:
        """
        构建简单输出（用于 analyze-core-distribution 命令）
        
        Returns:
            CoreDistributionOutput: 包含 cores 列表的简单输出
        """
        cores = [
            CoreItem(
                cpu_id=c.cpu_id,
                total_cpu_util=f"{c.total_cpu:.2f}%",
                kernel_cpu_util=f"{c.kernel_cpu:.2f}%"
            )
            for c in result.cores
        ]
        
        risk = top_risk or RiskInfo(level="none")
        
        return CoreDistributionOutput(
            _risk=risk,
            cores=cores
        )
    
    @staticmethod
    def build_rich_output(
        result: CoreDistributionResult
    ) -> CoreDistributionData:
        """
        构建丰富输出（用于 sys-audit 命令）
        
        Returns:
            CoreDistributionData: 包含 imbalance_level, saturated_cores 等的丰富输出
        """
        # 提取饱和核心（按利用率排序）
        top_saturated = [
            CoreSaturationItem(
                cpu_id=c.cpu_id,
                total_util=c.total_cpu,
                kernel_util=c.kernel_cpu
            )
            for c in result.cores[:5]
            if c.total_cpu > Thresholds.CORE_SATURATED_THRESHOLD  # 只显示高负载核心
        ]
        
        # 确定 attention flag
        attention_flag = ""
        if result.imbalance_level in [ImbalanceLevel.HIGH, ImbalanceLevel.CRITICAL]:
            attention_flag = AttentionFlag.X1
        
        return CoreDistributionData(
            imbalance_level=result.imbalance_level,
            saturated_cores=result.saturated_cores,
            attention_flag=attention_flag,
            top_saturated=top_saturated
        )
    
    @staticmethod
    def convert_to_report(
        result: CoreDistributionResult
    ) -> CoreDistributionReport:
        """
        转换为 Composite 层报告格式
        
        Returns:
            CoreDistributionReport: Composite 层报告
        """
        core_stats = [
            CoreStat(
                cpu_id=c.cpu_id,
                total_cpu=c.total_cpu,
                kernel_cpu=c.kernel_cpu,
                user_cpu=c.user_cpu
            )
            for c in result.cores
        ]
        
        return CoreDistributionReport(
            core_stats=core_stats,
            saturated_cores=result.saturated_cores,
            imbalance_level=result.imbalance_level,
            risks=result.risks
        )


def build_core_distribution_for_sys_audit(
    result: CoreDistributionResult
) -> CoreDistributionData:
    """
    为 sys-audit 构建核心分布数据（便捷函数）
    
    Args:
        result: Analysis 层结果
        
    Returns:
        CoreDistributionData: 丰富格式输出
    """
    return CoreDistributionBuilder.build_rich_output(result)


def build_core_distribution_for_command(
    result: CoreDistributionResult,
    top_risk: Optional[RiskInfo] = None
) -> CoreDistributionOutput:
    """
    为 analyze-core-distribution 命令构建输出（便捷函数）
    
    Args:
        result: Analysis 层结果
        top_risk: 最高级别 risk（可选）
        
    Returns:
        CoreDistributionOutput: 简单格式输出
    """
    return CoreDistributionBuilder.build_simple_output(result, top_risk)
