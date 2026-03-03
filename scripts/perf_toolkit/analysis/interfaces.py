#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Interfaces - Type definitions for three-tier architecture

三层架构接口定义文档：
- 所有 Analyzer 必须遵循这些接口
- Facade 对外暴露的接口在此定义
- 用于类型检查和文档生成

设计原则:
1. 接口隔离 - Composite 只依赖 Facade，不依赖具体 Analyzer
2. 延迟初始化 - Facade 按需创建 Analyzer 实例
3. 错误封装 - 下层异常转换为有意义的错误信息
"""

from typing import Dict, List, Optional, Protocol, runtime_checkable, Any
from abc import ABC, abstractmethod

# Import dataclass types from models
from .models import (
    Risk, AnalysisResult, AnomaliesResult, CommTopResult,
    CoreDistributionResult, HotspotsResult, PathClustersResult, CallersResult,
    LifecycleInfo, CallGraphInfo
)


# =============================================================================
# Base Analyzer Interface
# =============================================================================

class BaseAnalyzer(ABC):
    """
    所有 Analyzer 的基类
    
    设计约束:
    1. 只依赖 engine 接口获取数据，不直接访问原始数据
    2. 不操作 trace（trace 由 CLI 层处理）
    3. 返回 AnalysisResult dataclass，由上层决定如何包装
    """
    
    def __init__(self, engine):
        """
        Args:
            engine: PerfExpertEngine 实例
        """
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Dict], **kwargs) -> AnalysisResult:
        """
        执行分析
        
        Args:
            samples: 样本数据列表
            **kwargs: 分析特定参数
            
        Returns:
            AnalysisResult: 标准分析结果结构
        """
        pass


# =============================================================================
# Analyzer Result Types (Deprecated - use dataclasses from models)
# =============================================================================

# Task-2.8.2: AnalyzerResult 类型别名已废弃，直接使用 AnalysisResult dataclass
# Task-2.8.3: RiskItem 类型别名已废弃，直接使用 Risk dataclass


# =============================================================================
# Facade Interface
# =============================================================================

class AnalysisFacadeProtocol(Protocol):
    """
    Analysis Facade 协议定义
    
    Composite 层通过此接口与 Analysis 层交互。
    """
    
    def analyze_comm_top(self, samples, top_n: int = 10) -> CommTopResult:
        """进程组 CPU 分析"""
        ...
    
    def analyze_hotspots(self, samples, comm: Optional[str] = None, 
                         pid: Optional[int] = None, top_n: int = 20) -> HotspotsResult:
        """热点函数分析"""
        ...
    
    def analyze_core_distribution(self, samples) -> CoreDistributionResult:
        """核心级负载分布分析"""
        ...
    
    def detect_anomalies(self, samples, window_size: int = 10, 
                         threshold: float = 2.0) -> AnomaliesResult:
        """时序异常检测"""
        ...
    
    def analyze_callers(self, samples, target_symbol: str, 
                        comm: Optional[str] = None) -> CallersResult:
        """调用链分析"""
        ...
    
    def cluster_paths(self, samples, comm: Optional[str] = None) -> PathClustersResult:
        """调用路径聚类"""
        ...


# =============================================================================
# Engine Extension Interfaces
# =============================================================================

class EngineLifecycleProtocol(Protocol):
    """
    Engine 生命周期接口协议
    
    Week 1 新增接口，用于 Analysis 层获取进程生命周期信息。
    """
    
    def get_process_lifecycle(self, samples=None, comm: Optional[str] = None) -> LifecycleInfo:
        """
        获取进程生命周期信息
        
        Returns:
            LifecycleInfo dataclass with spawn_events, exit_events, spawn_rate, lifecycle_stats
        """
        ...
    
    def get_pid_cpu_distribution(self, samples=None, comm: Optional[str] = None) -> Dict[int, float]:
        """
        获取指定 comm 下各 PID 的 CPU 分布
        
        Returns:
            {pid: cpu_percent, ...}
        """
        ...


class EngineCallGraphProtocol(Protocol):
    """
    Engine 调用图接口协议
    
    Week 1 新增接口，用于 Analysis 层获取调用关系。
    """
    
    def get_call_graph(self, samples=None, target_symbol: Optional[str] = None,
                       comm: Optional[str] = None) -> CallGraphInfo:
        """
        获取调用图
        
        Returns:
            CallGraphInfo dataclass with callers, call_graph, hot_paths
        """
        ...


# =============================================================================
# Exception Types
# =============================================================================

class AnalysisError(Exception):
    """分析层基础异常"""
    pass


class EngineInterfaceError(AnalysisError):
    """Engine 接口调用错误"""
    pass


class InvalidSampleError(AnalysisError):
    """无效样本数据错误"""
    pass


class ConfigurationError(AnalysisError):
    """配置错误"""
    pass


# =============================================================================
# Type Aliases (Task-2.8.1 - Deprecated)
# =============================================================================

# Note: Sample type alias kept for backward compatibility
# In the future, use Sample dataclass from engine_types
Sample = Dict[str, Any]  # 单个样本数据结构
Samples = List[Sample]   # 样本列表
CPUUtil = Dict[str, float]  # CPU 利用率数据

# RiskList is deprecated - use List[Risk] directly
RiskList = List[Risk]   # Risk 列表
