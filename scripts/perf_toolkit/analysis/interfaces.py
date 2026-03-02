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

from typing import Dict, List, Optional, Protocol, runtime_checkable
from abc import ABC, abstractmethod


# =============================================================================
# Base Analyzer Interface
# =============================================================================

class BaseAnalyzer(ABC):
    """
    所有 Analyzer 的基类
    
    设计约束:
    1. 只依赖 engine 接口获取数据，不直接访问原始数据
    2. 不操作 trace（trace 由 CLI 层处理）
    3. 返回原始 dict，由上层决定如何包装
    """
    
    def __init__(self, engine):
        """
        Args:
            engine: PerfExpertEngine 实例
        """
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Dict], **kwargs) -> Dict:
        """
        执行分析
        
        Args:
            samples: 样本数据列表
            **kwargs: 分析特定参数
            
        Returns:
            分析结果字典，必须包含以下字段:
            - result: 核心分析结果
            - risks: List[Dict] 可选，发现的风险列表
            - recommendations: List[Dict] 可选，建议操作
        """
        pass


# =============================================================================
# Analyzer Result Types
# =============================================================================

class AnalyzerResult(Dict):
    """
    Analyzer 返回结果的标准结构
    
    Example:
        {
            "groups": [...],           # 分析结果数据
            "risks": [...],            # 发现的风险（供 Composite 聚合）
            "recommendations": [...],  # 建议操作
            "metadata": {...}          # 额外元数据
        }
    """
    pass


class RiskItem(Dict):
    """
    Risk 条目结构
    
    Fields:
        level: str - "critical" | "warning" | "info" | "none"
        message: str - 风险描述
        hint: str - 建议操作
        patterns: List[str] - 检测到的模式标签
        pending_targets: List[str] - 待处理目标列表
        action_required: bool - 是否需要立即处理
    """
    pass


# =============================================================================
# Facade Interface
# =============================================================================

class AnalysisFacadeProtocol(Protocol):
    """
    Analysis Facade 协议定义
    
    Composite 层通过此接口与 Analysis 层交互。
    """
    
    def analyze_comm_top(self, samples, top_n: int = 10) -> Dict:
        """进程组 CPU 分析"""
        ...
    
    def analyze_hotspots(self, samples, comm: Optional[str] = None, 
                         pid: Optional[int] = None, top_n: int = 20) -> Dict:
        """热点函数分析"""
        ...
    
    def analyze_core_distribution(self, samples) -> Dict:
        """核心级负载分布分析"""
        ...
    
    def detect_anomalies(self, samples, window_size: int = 10, 
                         threshold: float = 2.0) -> Dict:
        """时序异常检测"""
        ...
    
    def analyze_callers(self, samples, target_symbol: str, 
                        comm: Optional[str] = None) -> Dict:
        """调用链分析"""
        ...
    
    def cluster_paths(self, samples, comm: Optional[str] = None) -> Dict:
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
    
    def get_process_lifecycle(self, samples=None, comm: Optional[str] = None) -> Dict:
        """
        获取进程生命周期信息
        
        Returns:
            {
                "spawn_events": List[Dict],
                "exit_events": List[Dict],
                "spawn_rate": float,
                "lifecycle_stats": Dict
            }
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
                       comm: Optional[str] = None) -> Dict:
        """
        获取调用图
        
        Returns:
            {
                "callers": List[Dict],
                "call_graph": Dict,
                "hot_paths": List[str]
            }
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
# Type Aliases
# =============================================================================

Sample = Dict[str, any]  # 单个样本数据结构
Samples = List[Sample]   # 样本列表
CPUUtil = Dict[str, float]  # CPU 利用率数据
RiskList = List[RiskItem]   # Risk 列表
