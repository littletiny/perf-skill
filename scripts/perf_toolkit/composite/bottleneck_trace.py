#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bottleneck Trace - 瓶颈追踪命令

自动识别CPU瓶颈进程并进行深度分析。

分析流程:
1. 识别瓶颈进程（通过Monopoly指标）
2. 热点函数分析
3. 调用链溯源
4. 生成诊断报告

注意：CLI 命令已迁移到 cli/commands/composite/bottleneck_trace.py
本文件保留辅助函数和 BottleneckTracer 类供 CLI 命令使用

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import DiagnosisType, RiskPattern

from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator
from perf_toolkit.core.models import RiskInfo
from perf_toolkit.composite.models import (
    ProcessGroup, BottleneckAnalysis,
    HotspotData, HotspotsDetails, CallerData, CallersDetails,
    HotspotsReport, CallersReport
)


class BottleneckTracer:
    """
    瓶颈追踪器
    
    自动识别 CPU 瓶颈进程并进行深度分析。
    
    分析流程：
    1. 识别瓶颈进程（通过 Monopoly 指标）
    2. 热点函数分析
    3. 调用链溯源
    4. 生成诊断报告
    
    使用示例：
        engine = PerfExpertEngine()
        facade = AnalysisFacade(engine)
        tracer = BottleneckTracer(facade)
        
        samples = engine.get_filtered_samples()
        analysis, hotspots, callers = tracer.trace(samples, target_comm="my_app")
    """
    
    def __init__(self, facade: AnalysisFacade):
        """
        初始化追踪器
        
        Args:
            facade: AnalysisFacade 实例
        """
        self._facade = facade
        self._aggregator = RiskAggregator()
    
    def trace(self, samples: List[Dict],
              target_comm: Optional[str] = None,
              target_pid: Optional[int] = None) -> Tuple[BottleneckAnalysis, 
                                                         HotspotsReport,
                                                         Optional[CallersReport]]:
        """
        执行瓶颈追踪
        
        Args:
            samples: 样本数据
            target_comm: 可选，指定目标进程。如为 None，自动识别瓶颈进程
            target_pid: 可选，指定目标 PID。如指定，只分析该 PID 的数据
            
        Returns:
            Tuple[BottleneckAnalysis, HotspotsReport, Optional[CallersReport]]:
                瓶颈分析结果、热点报告、调用链报告（可选）
        """
        # 1. 如果指定了 target_pid，先过滤样本
        if target_pid is not None:
            samples = self._filter_samples_by_pid(samples, target_pid)
        
        # 2. 自动识别或验证目标进程
        if not target_comm:
            target_comm = self._find_bottleneck_comm(samples)
        
        if not target_comm:
            # 未找到瓶颈进程
            return (
                BottleneckAnalysis(
                    found=False,
                    risks=[RiskInfo(
                        level="info",
                        message="未检测到明显瓶颈进程",
                        hint="尝试使用 sys-audit 进行全景扫描"
                    )]
                ),
                HotspotsReport(),
                None
            )
        
        # 3. 分析瓶颈特征
        bottleneck = self._analyze_bottleneck(samples, target_comm, pid=target_pid)
        
        # 4. 热点函数分析
        hotspots_result = self._facade.analyze_hotspots(
            samples,
            comm=target_comm,
            pid=target_pid,
            top_n=10
        )
        hotspots_report = _convert_hotspots_result(hotspots_result)

        # 5. 调用链溯源（如果热点明确）
        callers_report = None
        if hotspots_report.top_symbol:
            callers_result = self._facade.analyze_callers(
                samples,
                target_symbol=hotspots_report.top_symbol,
                comm=target_comm,
                pid=target_pid
            )
            callers_report = _convert_callers_result(callers_result)
        
        # 5. 聚合 risks
        self._aggregator.add_risks(bottleneck.risks, source="bottleneck")
        self._aggregator.add_risks(hotspots_report.risks, source="hotspots")
        if callers_report:
            self._aggregator.add_risks(callers_report.risks, source="callers")
        
        # 6. 更新 bottleneck risks
        bottleneck.risks = list(self._aggregator._risks)
        
        return bottleneck, hotspots_report, callers_report
    
    def _filter_samples_by_pid(self, samples: List[Dict], pid: int) -> List[Dict]:
        """
        按 PID 过滤样本
        
        Args:
            samples: 样本数据
            pid: 目标 PID
            
        Returns:
            List[Dict]: 只包含指定 PID 的样本
        """
        return [s for s in samples if str(s.get('pid', '')) == str(pid)]
    
    def _find_bottleneck_comm(self, samples: List[Dict]) -> Optional[str]:
        """
        自动识别瓶颈进程
        
        策略：通过 CommTop 获取按危害指数排序的进程组，
        找出第一个 BOTTLENECK 诊断的进程。
        
        Args:
            samples: 样本数据
            
        Returns:
            Optional[str]: 瓶颈进程名，如未找到返回 None
        """
        comm_top_result = self._facade.analyze_comm_top(
            samples, 
            top_n=20,
            include_metrics=True
        )
        
        # 获取所有组（包括被折叠的）
        if hasattr(comm_top_result, 'metrics') and comm_top_result.metrics:
            all_groups_data = comm_top_result.metrics.get("all_groups", [])
        else:
            all_groups_data = []
        
        # 转换为 ProcessGroup
        all_groups = [
            ProcessGroup(
                comm=g.get("comm", ""),
                total_cpu=g.get("total_cpu", 0.0),
                diagnosis=g.get("diagnosis", DiagnosisType.HEALTHY),
                monopoly=g.get("monopoly", 0.0),
                impact_score=g.get("impact_score", 0.0)
            )
            for g in all_groups_data
        ]
        
        # 按危害指数排序
        all_groups.sort(key=lambda x: x.impact_score, reverse=True)
        
        # 找第一个 BOTTLENECK
        for group in all_groups:
            if group.diagnosis == DiagnosisType.BOTTLENECK:
                return group.comm
        
        # 如果没有明确的 BOTTLENECK，返回危害指数最高的
        if all_groups:
            return all_groups[0].comm
        
        return None
    
    def _analyze_bottleneck(self, samples: List[Dict], comm: str, pid: Optional[int] = None) -> BottleneckAnalysis:
        """
        分析指定进程的瓶颈特征
        
        Args:
            samples: 样本数据
            comm: 目标进程名
            pid: 可选，目标 PID
            
        Returns:
            BottleneckAnalysis: 瓶颈分析结果
        """
        # 获取进程组详细信息
        comm_top_result = self._facade.analyze_comm_top(
            samples, 
            top_n=50,
            include_metrics=True
        )
        
        # 找到目标 comm
        target_group = None
        for g in comm_top_result.groups:
            if g.comm == comm:
                target_group = _convert_comm_group(g)
                break
        
        if not target_group:
            return BottleneckAnalysis(
                found=False,
                comm=comm,
                risks=[RiskInfo(
                    level="warning",
                    message=f"未找到进程 {comm}",
                    hint="执行 get-comm-top 查看可用进程",
                    patterns=["COMM_NOT_FOUND"]
                )]
            )
        
        # 计算内核占比
        kernel_ratio = target_group.kernel_ratio
        
        # 生成 risks
        risks = []
        
        if target_group.monopoly > 0.8:
            risks.append(RiskInfo(
                level="critical",
                message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
                hint=f"get-hotspots --comm {comm}",
                patterns=["SINGLE_CORE_SATURATION"],
                pending_targets=[comm],
                source="bottleneck"
            ))

        if kernel_ratio > 50:
            risks.append(RiskInfo(
                level="warning",
                message=f"{comm} 高内核态 ({kernel_ratio:.1f}%)",
                hint=f"cluster-paths --comm {comm}",
                patterns=[RiskPattern.HIGH_KERNEL],
                pending_targets=[comm],
                source="bottleneck"
            ))
        
        return BottleneckAnalysis(
            found=True,
            comm=comm,
            total_cpu=target_group.total_cpu,
            kernel_ratio=kernel_ratio,
            pid_count=target_group.pid_count,
            cv=target_group.cv,
            monopoly=target_group.monopoly,
            spawn_rate=target_group.spawn_rate,
            diagnosis=target_group.diagnosis,
            impact_score=target_group.impact_score,
            risks=risks
        )


# 以下辅助函数保留供 cli/commands/composite/bottleneck_trace.py 使用

def _find_bottleneck_comm(facade: AnalysisFacade, samples) -> Optional[str]:
    """
    自动识别瓶颈进程（兼容旧接口，返回第一个BOTTLENECK）
    
    策略：通过CommTop获取按危害指数排序的进程组，
    找出第一个BOTTLENECK诊断的进程。
    """
    all_bottlenecks = _find_all_bottleneck_comms(facade, samples)
    return all_bottlenecks[0] if all_bottlenecks else None


def _find_all_bottleneck_comms(facade: AnalysisFacade, samples) -> List[str]:
    """
    自动识别所有瓶颈进程
    
    策略：通过CommTop获取按危害指数排序的进程组，
    返回所有BOTTLENECK诊断的进程列表。
    
    Args:
        facade: AnalysisFacade 实例
        samples: 样本数据
        
    Returns:
        List[str]: 所有BOTTLENECK进程的comm列表，按危害指数排序
    """
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    # 使用CommTopAnalyzer获取带metrics的结果
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=20, include_metrics=True)
    
    # 从result中提取all_groups（处理 CommTopResult dataclass）
    metrics = result.metrics if hasattr(result, 'metrics') else result.get("metrics", {})
    # 处理 metrics 可能是 dict 或 dataclass 的情况
    if hasattr(metrics, 'all_groups'):
        all_groups_data = metrics.all_groups
    elif isinstance(metrics, dict):
        all_groups_data = metrics.get("all_groups", [])
    else:
        all_groups_data = []
    
    all_groups = [
        ProcessGroup(
            comm=g["comm"] if isinstance(g, dict) else getattr(g, 'comm', ''),
            total_cpu=g.get("total_cpu", 0.0) if isinstance(g, dict) else getattr(g, 'total_cpu', 0.0),
            diagnosis=g.get("diagnosis", DiagnosisType.HEALTHY) if isinstance(g, dict) else getattr(g, 'diagnosis', DiagnosisType.HEALTHY),
            monopoly=g.get("monopoly", 0.0) if isinstance(g, dict) else getattr(g, 'monopoly', 0.0),
            impact_score=g.get("impact_score", 0.0) if isinstance(g, dict) else getattr(g, 'impact_score', 0.0)
        )
        for g in all_groups_data
    ]
    
    # 按危害指数排序
    all_groups.sort(key=lambda x: x.impact_score, reverse=True)
    
    # 收集所有BOTTLENECK
    bottlenecks = [g.comm for g in all_groups if g.diagnosis == DiagnosisType.BOTTLENECK]
    
    return bottlenecks


def _analyze_bottleneck(facade: AnalysisFacade, samples, comm: str, pid: Optional[int] = None) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征"""
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    
    analyzer = CommTopAnalyzer(facade._engine)
    result = analyzer.analyze(samples, top_n=50, include_metrics=True)
    
    # 找到目标comm（处理 CommTopResult dataclass）
    metrics = result.metrics if hasattr(result, 'metrics') else result.get("metrics", {})
    target_group: Optional[ProcessGroup] = None
    
    # 处理 metrics 可能是 dict 或 dataclass 的情况
    if hasattr(metrics, 'all_groups'):
        # metrics 是 dataclass，all_groups 中是 ProcessGroup 对象
        for g in metrics.all_groups:
            if g.comm == comm:
                target_group = g
                break
    elif isinstance(metrics, dict):
        # metrics 是 dict
        for g in metrics.get("all_groups", []):
            if g.get("comm") == comm:
                target_group = ProcessGroup(
                    comm=g["comm"],
                    total_cpu=g.get("total_cpu", 0.0),
                    kernel_cpu=g.get("kernel_cpu", 0.0),
                    pid_count=g.get("pid_count", g.get("count", 0)),
                    cv=g.get("cv", 0.0),
                    monopoly=g.get("monopoly", 0.0),
                    diagnosis=g.get("diagnosis", DiagnosisType.NORMAL),
                    impact_score=g.get("impact_score", 0.0)
                )
                break
    
    if not target_group:
        return BottleneckAnalysis(
            found=False,
            comm=comm,
            risks=[RiskInfo(
                level="warning",
                message=f"未找到进程 {comm}",
                hint="get-comm-top",
                patterns=["COMM_NOT_FOUND"]
            )]
        )
    
    # 计算内核占比
    kernel_ratio = target_group.kernel_ratio
    
    # 生成risks
    risks: list[RiskInfo] = []

    if target_group.monopoly > 0.8:
        risks.append(RiskInfo(
            level="critical",
            message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
            hint=f"get-hotspots --comm {comm}",
            patterns=["SINGLE_CORE_SATURATION"],
            pending_targets=[comm],
            source="bottleneck"
        ))

    if kernel_ratio > 50:
        risks.append(RiskInfo(
            level="warning",
            message=f"{comm} 高内核态 ({kernel_ratio:.1f}%)",
            hint=f"cluster-paths --comm {comm}",
            patterns=["HIGH_KERNEL"],
            pending_targets=[comm],
            source="bottleneck"
        ))
    
    return BottleneckAnalysis(
        found=True,
        comm=comm,
        total_cpu=target_group.total_cpu,
        kernel_ratio=kernel_ratio,
        pid_count=target_group.pid_count,
        cv=target_group.cv,
        monopoly=target_group.monopoly,
        spawn_rate=target_group.spawn_rate,
        diagnosis=target_group.diagnosis,
        impact_score=target_group.impact_score,
        risks=risks
    )


def _hotspots_to_dataclass(h: HotspotsReport) -> HotspotsDetails:
    """转换HotspotsReport为HotspotsDetails dataclass"""
    hotspots = [
        HotspotData(
            symbol=hs.symbol,
            cpu_percent=hs.cpu_percent,
            resource_tag=hs.resource_tag
        )
        for hs in h.hotspots[:5]
    ]
    
    return HotspotsDetails(
        hotspots=hotspots,
        top_symbol=h.top_symbol,
        total_hotspots=h.total_hotspots,
        risks=h.risks
    )


def _callers_to_dataclass(c: CallersReport) -> CallersDetails:
    """转换CallersReport为CallersDetails dataclass"""
    callers = [
        CallerData(symbol=caller.symbol, call_ratio=caller.call_ratio)
        for caller in c.callers[:3]
    ]
    
    return CallersDetails(
        target=c.target,
        callers=callers,
        risks=c.risks
    )



# =============================================================================
# Conversion Helpers - 显式字段映射（替代已删除的 from_analysis_* 方法）
# =============================================================================

def _convert_comm_group(group) -> ProcessGroup:
    """从 Analysis 层的 CommGroup 转换为 Composite 层的 ProcessGroup"""
    return ProcessGroup(
        comm=group.comm,
        total_cpu=group.total_cpu,
        kernel_cpu=group.kernel_cpu,
        user_cpu=group.user_cpu,
        pid_count=group.pid_count,
        pids=list(group.pids) if hasattr(group, 'pids') else [],
        cv=group.cv,
        monopoly=group.monopoly,
        spawn_rate=group.spawn_rate,
        diagnosis=group.diagnosis,
        impact_score=group.impact_score
    )


def _convert_hotspots_result(result) -> 'HotspotsReport':
    """从 Analysis 层的 HotspotsResult 转换为 Composite 层的 HotspotsReport"""
    from .models import HotspotItem, HotspotsReport

    def infer_tag(symbol: str) -> str:
        """推断资源标签"""
        symbol_lower = symbol.lower()
        if any(k in symbol_lower for k in ['lock', 'mutex', 'spin', 'rwsem']):
            return "LOCK"
        if any(k in symbol_lower for k in ['syscall', 'sys_']):
            return "SYSCALL"
        if any(k in symbol_lower for k in ['schedule', 'switch']):
            return "SCHED"
        if any(k in symbol_lower for k in ['malloc', 'free', 'reclaim']):
            return "MEMORY"
        if any(k in symbol_lower for k in ['read', 'write', 'send', 'recv']):
            return "IO"
        return "COMPUTE"

    hotspots = [
        HotspotItem(
            symbol=h.symbol,
            cpu_percent=h.self_pct,
            inclusive_percent=h.inclusive_pct,
            call_count=getattr(h, 'call_count', 0),
            resource_tag=infer_tag(h.symbol)
        )
        for h in result.hotspots
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="hotspots"
        )
        for r in result.risks
    ]

    top = result.hotspots[0].symbol if result.hotspots else None

    return HotspotsReport(
        hotspots=hotspots,
        top_symbol=top,
        total_hotspots=len(result.hotspots),
        kernel_ratio=result.kernel_ratio,
        user_ratio=result.user_ratio,
        risks=risks
    )


def _convert_callers_result(result) -> 'CallersReport':
    """从 Analysis 层的 CallersResult 转换为 Composite 层的 CallersReport"""
    from .models import CallerInfo, CallersReport

    callers = [
        CallerInfo(
            symbol=c.symbol,
            call_count=c.call_count,
            call_ratio=c.call_ratio,
            total_weight=c.total_weight
        )
        for c in result.callers
    ]

    risks = [
        RiskInfo(
            level=r.level,
            message=r.message,
            hint=r.hint,
            patterns=list(r.patterns) if hasattr(r, 'patterns') else [],
            pending_targets=list(r.pending_targets) if hasattr(r, 'pending_targets') else [],
            source="callers"
        )
        for r in result.risks
    ]

    hot_paths = [c.symbol for c in callers[:3]]

    return CallersReport(
        target=result.target,
        callers=callers,
        hot_paths=hot_paths,
        risks=risks
    )
