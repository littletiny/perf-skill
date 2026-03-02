#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analysis Facade - Analysis 层对外暴露的干净接口

设计原则:
1. 延迟初始化 - 按需创建 Analyzer 实例
2. 接口隔离 - Composite 只依赖 Facade，不依赖具体 Analyzer
3. 错误封装 - 下层异常转换为有意义的错误信息

供 Composite 层调用，不触发 Trace 记录。
"""

from typing import Dict, List, Any, Optional


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
            elif name == "symbol_clusters":
                from .clusters import SymbolClustersAnalyzer
                self._analyzers[name] = SymbolClustersAnalyzer(self._engine)
            elif name == "process_variety":
                from .process_variety import ProcessVarietyAnalyzer
                self._analyzers[name] = ProcessVarietyAnalyzer(self._engine)
            else:
                raise ValueError(f"Unknown analyzer: {name}")
        
        return self._analyzers[name]
    
    # ========== 供 Composite 调用的接口 ==========
    
    def analyze_comm_top(self, samples: List[Dict], top_n: int = 10,
                         include_metrics: bool = False) -> Dict:
        """
        进程组 CPU 分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间指标
            
        Returns:
            {
                "result": {"groups": [...], "folded_count": N, "total_groups": N},
                "risks": [...],
                "metrics": {...}  # if include_metrics
            }
        """
        analyzer = self._get_analyzer("comm_top")
        return analyzer.analyze(samples, top_n=top_n, include_metrics=include_metrics)
    
    def analyze_hotspots(self, samples: List[Dict],
                         comm: Optional[str] = None,
                         pid: Optional[int] = None,
                         top_n: int = 20,
                         sort_by: str = "self") -> Dict:
        """
        热点函数分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            top_n: 返回前 N 个热点
            sort_by: 排序方式 - "self" | "inclusive"
            
        Returns:
            {
                "result": {"hotspots": [...], "kernel_ratio": float},
                "risks": [...]
            }
        """
        analyzer = self._get_analyzer("hotspots")
        return analyzer.analyze(samples, comm=comm, pid=pid, top_n=top_n, sort_by=sort_by)
    
    def analyze_core_distribution(self, samples: List[Dict], 
                                   top_n: int = 10) -> Dict:
        """
        核心分布分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个饱和核心
            
        Returns:
            {
                "result": {"cores": [...], "imbalance_level": str},
                "risks": [...]
            }
        """
        analyzer = self._get_analyzer("core_dist")
        return analyzer.analyze(samples, top_n=top_n)
    
    def detect_anomalies(self, samples: List[Dict],
                         window_size: float = 1.0,
                         spike_threshold: float = 0.5,
                         min_utilization: float = 0.3,
                         cpu_id: Optional[int] = None,
                         top_n: int = 10) -> Dict:
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
            {
                "result": {"anomalies": [...], "mutation_detected": bool},
                "risks": [...]
            }
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
                      pid: Optional[int] = None) -> Dict:
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
            {
                "result": {"clusters": [...], "total_weight": float},
                "risks": [...]
            }
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
    
    def cluster_symbols(self, samples: List[Dict],
                        top_n: int = 10,
                        include_experts: bool = True,
                        no_include_experts: bool = False,
                        rules_file: Optional[str] = None,
                        custom_rules: Optional[str] = None,
                        comm: Optional[str] = None,
                        pid: Optional[int] = None) -> Dict:
        """
        符号聚类（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个聚类
            include_experts: 是否包含内置专家规则
            no_include_experts: 是否禁用内置规则
            rules_file: 外部规则文件路径
            custom_rules: 命令行自定义规则
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            
        Returns:
            {
                "result": {"clusters": [...], "lock_contention_ratio": float},
                "risks": [...]
            }
        """
        analyzer = self._get_analyzer("symbol_clusters")
        return analyzer.analyze(
            samples,
            top_n=top_n,
            include_experts=include_experts,
            no_include_experts=no_include_experts,
            rules_file=rules_file,
            custom_rules=custom_rules,
            comm=comm,
            pid=pid
        )
    
    def count_process_variety(self, samples: List[Dict],
                              top_n: int = 20,
                              storm_pid_threshold: int = 50,
                              storm_cpu_threshold: float = 0.5,
                              storm_ratio_threshold: float = 2.0,
                              comm: Optional[str] = None) -> Dict:
        """
        进程多样性分析（内部接口，不触发 Trace）
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个结果
            storm_pid_threshold: PID 数量阈值
            storm_cpu_threshold: 单 PID CPU 阈值
            storm_ratio_threshold: samples/PID 阈值
            comm: 可选，按进程名过滤
            
        Returns:
            {
                "result": {"processes": [...], "storm_comms": [...]},
                "risks": [...]
            }
        """
        analyzer = self._get_analyzer("process_variety")
        return analyzer.analyze(
            samples,
            top_n=top_n,
            storm_pid_threshold=storm_pid_threshold,
            storm_cpu_threshold=storm_cpu_threshold,
            storm_ratio_threshold=storm_ratio_threshold,
            comm=comm
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
