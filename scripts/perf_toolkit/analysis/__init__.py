#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Layer - Three-tier architecture middle layer

三层架构中的 Analysis 层：
- 提供纯粹的分析逻辑（Analyzer 类）
- 通过 Facade 对外暴露统一接口
- 不直接操作 CLI/Trace，由上层处理

导出内容:
    - AnalysisFacade: 统一分析接口
    - BaseAnalyzer: Analyzer 基类
    - models: Analysis 层数据模型

使用示例:
    from perf_toolkit.analysis import AnalysisFacade
    
    facade = AnalysisFacade(engine)
    result = facade.analyze_comm_top(samples)
"""

from .base import BaseAnalyzer
from .facade import AnalysisFacade
from . import models

__all__ = [
    # Facade
    'AnalysisFacade',
    
    # Base Classes
    'BaseAnalyzer',
    
    # Models
    'models',
    
    # Analyzers (for direct use if needed)
    'CommTopAnalyzer',
    'HotspotsAnalyzer',
    'CoreDistAnalyzer',
    'AnomaliesAnalyzer',
    'PathClustersAnalyzer',
]

# 延迟导入 Analyzers（避免循环依赖）
def __getattr__(name):
    if name == 'CommTopAnalyzer':
        from .comm_top import CommTopAnalyzer
        return CommTopAnalyzer
    elif name == 'HotspotsAnalyzer':
        from .hotspots import HotspotsAnalyzer
        return HotspotsAnalyzer
    elif name == 'CoreDistAnalyzer':
        from .core_distribution import CoreDistAnalyzer
        return CoreDistAnalyzer
    elif name == 'AnomaliesAnalyzer':
        from .anomalies import AnomaliesAnalyzer
        return AnomaliesAnalyzer
    elif name == 'PathClustersAnalyzer':
        from .path_clusters import PathClustersAnalyzer
        return PathClustersAnalyzer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
