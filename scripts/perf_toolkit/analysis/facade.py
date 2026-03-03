#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Facade - Analysis 层对外暴露的干净接口

设计原则:
1. 延迟初始化 - 按需创建 Analyzer 实例
2. 接口隔离 - Composite 只依赖 Facade，不依赖具体 Analyzer
3. 错误封装 - 下层异常转换为有意义的错误信息

供 Composite 层调用，不触发 Trace 记录。

Task-2.7.1: analyze_callers 返回 CallersResult dataclass
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict

from .models import (
    CommTopResult, HotspotsResult, CoreDistributionResult,
    AnomaliesResult, PathClustersResult, CallersResult,
    Risk, CallerAttribution
)


class AnalysisFacade:
    """
    Analysis Facade - 对外暴露的干净接口
    
    供 Composite 层调用，不触发 Trace 记录。
    """
    
    def __init__(self, engine):
        """
        初始化 Facade
        
        Args:
            engine: PerfExpertEngine 实例
        """
        self._engine = engine
        self._analyzers = {}  # 延迟加载缓存
    
    def _get_analyzer(self, name: str):
        """
        延迟获取 Analyzer 实例
        
        Args:
            name: Analyzer 名称
            
        Returns:
            BaseAnalyzer 实例
        """
        if name not in self._analyzers:
            if name == "comm_top":
                from .comm_top import CommTopAnalyzer
                self._analyzers[name] = CommTopAnalyzer(self._engine)
            elif name == "hotspots":
                from .hotspots import HotspotsAnalyzer
                self._analyzers[name] = HotspotsAnalyzer(self._engine)
            elif name == "core_dist":
                from .core_distribution import CoreDistAnalyzer
                self._analyzers[name] = CoreDistAnalyzer(self._engine)
            elif name == "anomalies":
                from .anomalies import AnomaliesAnalyzer
                self._analyzers[name] = AnomaliesAnalyzer(self._engine)
            elif name == "path_clusters":
                from .path_clusters import PathClustersAnalyzer
                self._analyzers[name] = PathClustersAnalyzer(self._engine)
            else:
                raise ValueError(f"Unknown analyzer: {name}")
        
        return self._analyzers[name]
    
    # ========== 供 Composite 调用的接口 ==========
    
    def analyze_comm_top(self, samples: List[Dict], top_n: int = 10,
                         include_metrics: bool = False) -> CommTopResult:
        """
        进程组 CPU 分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间指标
            
        Returns:
            CommTopResult dataclass
        """
        analyzer = self._get_analyzer("comm_top")
        return analyzer.analyze(samples, top_n=top_n, include_metrics=include_metrics)
    
    def analyze_hotspots(self, samples: List[Dict],
                         comm: Optional[str] = None,
                         pid: Optional[int] = None,
                         top_n: int = 20,
                         sort_by: str = "self") -> HotspotsResult:
        """
        热点函数分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            top_n: 返回前 N 个热点
            sort_by: 排序方式 - "self" | "inclusive"
            
        Returns:
            HotspotsResult dataclass
        """
        analyzer = self._get_analyzer("hotspots")
        return analyzer.analyze(samples, comm=comm, pid=pid, top_n=top_n, sort_by=sort_by)
    
    def analyze_core_distribution(self, samples: List[Dict], 
                                   top_n: int = 10) -> CoreDistributionResult:
        """
        核心分布分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个饱和核心
            
        Returns:
            CoreDistributionResult dataclass
        """
        analyzer = self._get_analyzer("core_dist")
        return analyzer.analyze(samples, top_n=top_n)
    
    def detect_anomalies(self, samples: List[Dict],
                         window_size: float = 1.0,
                         spike_threshold: float = 0.5,
                         min_utilization: float = 0.3,
                         cpu_id: Optional[int] = None,
                         top_n: int = 10) -> AnomaliesResult:
        """
        异常检测（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            window_size: 滑动窗口大小（秒）
            spike_threshold: 变化倍数阈值
            min_utilization: 最小利用率阈值
            cpu_id: 可选，仅分析指定 CPU
            top_n: 返回前 N 个异常
            
        Returns:
            AnomaliesResult dataclass
        """
        analyzer = self._get_analyzer("anomalies")
        return analyzer.analyze(
            samples, 
            window_size=window_size,
            spike_threshold=spike_threshold,
            min_utilization=min_utilization,
            cpu_id=cpu_id,
            top_n=top_n
        )
    
    def cluster_paths(self, samples: List[Dict],
                      min_depth: int = 2,
                      min_samples: int = 5,
                      top_n: int = 10,
                      comm: Optional[str] = None,
                      pid: Optional[int] = None) -> PathClustersResult:
        """
        路径聚类（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            min_depth: 最小调用深度
            min_samples: 最小样本数
            top_n: 返回前 N 个聚类
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            
        Returns:
            PathClustersResult dataclass
        """
        analyzer = self._get_analyzer("path_clusters")
        return analyzer.analyze(
            samples,
            min_depth=min_depth,
            min_samples=min_samples,
            top_n=top_n,
            comm=comm,
            pid=pid
        )
    
    def analyze_callers(self, samples: List[Dict],
                        target_symbol: str,
                        comm: Optional[str] = None,
                        min_ratio: float = 0.5,
                        top_n: int = 10) -> CallersResult:
        """
        调用链溯源分析（内部接口，不触发 Trace）
        
        Task-2.7.1: 返回 CallersResult dataclass
        
        Args:
            samples: 样本数据
            target_symbol: 目标符号名
            comm: 可选，按进程名过滤
            min_ratio: 最小占比阈值（百分比）
            top_n: 返回前 N 个调用者
            
        Returns:
            CallersResult dataclass
        """
        # 过滤样本
        filtered_samples = samples
        if comm:
            filtered_samples = [s for s in filtered_samples if s.comm == comm]
        
        if not filtered_samples:
            return CallersResult(
                target=target_symbol,
                callers=[],
                total_weight=0.0,
                risks=[]
            )
        
        # 获取总量用于计算比例
        total_weight, _ = self._engine.get_total_core_per_sec(filtered_samples)
        
        # 溯源分析
        attribution = defaultdict(float)
        target_weight = 0.0
        
        for s in filtered_samples:
            stack = s.stack
            if not stack:
                continue
            
            weight = self._engine.get_sample_weight(s)
            normalized_names = stack.get_normalized_names()
            
            if target_symbol in normalized_names:
                target_weight += weight
                idx = normalized_names.index(target_symbol)
                caller_stack = normalized_names[idx+1:idx+6]
                if caller_stack:
                    attribution[tuple(caller_stack)] += weight
        
        # 构建 callers 列表
        callers: List[CallerAttribution] = []
        for stack, weight_val in attribution.items():
            ratio_total = (weight_val / total_weight * 100) if total_weight > 0 else 0
            if ratio_total >= min_ratio:
                callers.append(CallerAttribution(
                    symbol=" -> ".join(stack),
                    call_count=int(weight_val * 100),  # 近似计数
                    call_ratio=ratio_total,
                    total_weight=weight_val
                ))
        
        # 按调用次数排序
        callers.sort(key=lambda x: x.call_count, reverse=True)
        callers = callers[:top_n]
        
        # 识别 risk
        risks: List[Risk] = []
        if target_weight < 0.01:
            risks.append(Risk(
                level="warning",
                message=f"目标函数 '{target_symbol}' 几乎无 CPU 活动",
                hint="检查目标函数名称是否正确",
                patterns=["LOW_TARGET_ACTIVITY"],
                pending_targets=[]
            ))
        
        return CallersResult(
            target=target_symbol,
            callers=callers,
            total_weight=target_weight,
            risks=risks
        )


# =============================================================================
# Facade Factory
# =============================================================================

_facade_cache: Dict[int, AnalysisFacade] = {}


def get_facade(engine) -> AnalysisFacade:
    """
    获取或创建 Facade 实例（带缓存）
    
    Args:
        engine: PerfExpertEngine 实例
        
    Returns:
        AnalysisFacade 实例
    """
    engine_id = id(engine)
    if engine_id not in _facade_cache:
        _facade_cache[engine_id] = AnalysisFacade(engine)
    return _facade_cache[engine_id]


def clear_facade_cache():
    """清除 Facade 缓存（主要用于测试）"""
    global _facade_cache
    _facade_cache = {}
