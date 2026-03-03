#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Analyzer - Analysis 层抽象基类

设计约束:
1. 只依赖 engine 接口获取数据
2. 不直接操作 trace
3. 返回具体 Result dataclass（非裸 dict）
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from ..core.engine_types import Sample
from .models import (
    Risk, AnalysisResult, AnomaliesResult, CommTopResult,
    CoreDistributionResult, HotspotsResult, PathClustersResult, CallersResult
)


class BaseAnalyzer(ABC):
    """
    Analysis 层抽象基类
    
    所有具体 Analyzer 必须继承此类，实现 analyze() 方法。
    """
    
    def __init__(self, engine):
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Sample], **kwargs) -> Any:
        """
        执行分析
        
        Args:
            samples: 样本数据列表（Sample dataclass 列表）
            **kwargs: 分析特定参数
            
        Returns:
            具体 Result dataclass，如 AnomaliesResult, CommTopResult 等
        """
        pass
    
    def _create_risk(self, level: str, message: str, hint: str = "",
                     patterns: List[str] = None, 
                     pending_targets: List[str] = None) -> Risk:
        """
        创建标准化的 Risk 对象
        
        Args:
            level: 风险级别 - critical | warning | info | none
            message: 风险描述
            hint: 建议操作
            patterns: 检测到的模式标签
            pending_targets: 待处理目标列表
            
        Returns:
            Risk 对象
        """
        return Risk(
            level=level,
            message=message,
            hint=hint,
            patterns=patterns or [],
            pending_targets=pending_targets or []
        )
