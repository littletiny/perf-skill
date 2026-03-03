#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottleneck-trace 命令实现

从 composite/bottleneck_trace.py 迁移而来
使用 V2 强类型输出模型（无裸 Dict）
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from config.defaults import (
    DiagnosisType,
    Thresholds,
    StringConstants,
    EventConfig,
    DiagnosisThresholds,
)

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import (
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
)
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.models import (
    BottleneckAnalysis, HotspotsReport, CallersReport
)
from perf_toolkit.composite.bottleneck_trace import (
    _find_bottleneck_comm,
    _analyze_bottleneck,
    _convert_hotspots_result,
    _convert_callers_result,
)

if TYPE_CHECKING:
    from perf_toolkit.core.output_builder import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


def _get_comm_by_pid(samples: List[Dict[str, Any]], pid: int) -> Optional[str]:
    """从样本中根据 PID 查找进程名"""
    for s in samples:
        if isinstance(s, dict):
            s_pid = s.get('pid')
            if str(s_pid) == str(pid):
                return s.get('comm')
        elif hasattr(s, 'pid'):
            s_pid = getattr(s, 'pid', None)
            if str(s_pid) == str(pid):
                return getattr(s, 'comm', None)
    return None


def _convert_to_entity_distribution(
    bottleneck: BottleneckAnalysis,
    hotspots_report: HotspotsReport
) -> List[EntityDistribution]:
    """
    将进程组数据转换为 EntityDistribution
    
    Args:
        bottleneck: 瓶颈分析结果
        hotspots_report: 热点报告
        
    Returns:
        List[EntityDistribution]: 实体分布列表
    """
    if not bottleneck.found:
        return []
    
    # 计算核心亲缘性
    if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
        core_affinity = StringConstants.AFFINITY_FIXED
    elif bottleneck.cv < Thresholds.CV_AFFINITY_UNIFORM:
        core_affinity = StringConstants.AFFINITY_UNIFORM
    else:
        core_affinity = StringConstants.AFFINITY_SCATTERED
    
    # 计算节流率（基于高 Monopoly 和低 CPU 推断）
    throttle_rate = 0.0
    if (bottleneck.monopoly > Thresholds.MONOPOLY_HIGH and 
        bottleneck.total_cpu < Thresholds.AFFINITY_THROTTLE_INFER_CPU_MAX):
        throttle_rate = 100.0 - bottleneck.total_cpu
    
    # 获取显著度
    incl_saliency = 0.0
    excl_saliency = 0.0
    if hotspots_report.hotspots:
        top_hotspot = hotspots_report.hotspots[0]
        incl_saliency = top_hotspot.inclusive_percent / 100.0
        excl_saliency = top_hotspot.cpu_percent / 100.0
    
    return [EntityDistribution(
        comm=bottleneck.comm,
        count=bottleneck.pid_count,
        incl_saliency=incl_saliency,
        excl_saliency=excl_saliency,
        core_affinity=core_affinity,
        throttle_rate=throttle_rate
    )]


def _convert_to_call_path_clusters(
    hotspots_report: HotspotsReport,
    callers_report: Optional[CallersReport],
    target_comm: str
) -> List[CallPathCluster]:
    """
    将聚类数据转换为 CallPathCluster
    
    Args:
        hotspots_report: 热点报告
        callers_report: 调用链报告（可选）
        target_comm: 目标进程名
        
    Returns:
        List[CallPathCluster]: 调用路径聚类列表
    """
    clusters: List[CallPathCluster] = []
    
    if not hotspots_report.hotspots:
        return clusters
    
    # 从热点构建聚类
    for i, hs in enumerate(hotspots_report.hotspots[:5]):
        # 推断路径特征
        characteristic = StringConstants.CHAR_COMPUTE
        symbol_lower = hs.symbol.lower()
        if any(k in symbol_lower for k in StringConstants.LOCK_KEYWORDS):
            characteristic = StringConstants.CHAR_LOCK_CONTENTION
        elif any(k in symbol_lower for k in StringConstants.IO_KEYWORDS):
            characteristic = StringConstants.CHAR_IO_WAIT
        elif any(k in symbol_lower for k in StringConstants.SYSCALL_KEYWORDS):
            characteristic = StringConstants.CHAR_SYSCALL_BOUND
        elif hs.inclusive_percent > hs.cpu_percent * 3:
            characteristic = StringConstants.CHAR_LATENCY_VICTIM
        elif hs.cpu_percent > hs.inclusive_percent * 2:
            characteristic = StringConstants.CHAR_HIGH_FREQ_CPU
        
        clusters.append(CallPathCluster(
            cluster_id=f"hotspot_{i}",
            comm=target_comm,
            weight=hs.inclusive_percent if hasattr(hs, 'inclusive_percent') else hs.cpu_percent,
            path=[target_comm, hs.symbol],
            hotspot=hs.symbol,
            characteristic=characteristic
        ))
    
    # 从调用者补充聚类
    if callers_report and callers_report.callers:
        for i, caller in enumerate(callers_report.callers[:3]):
            path = caller.symbol.split(' -> ') if ' -> ' in caller.symbol else [caller.symbol]
            
            clusters.append(CallPathCluster(
                cluster_id=f"caller_{i}",
                comm=target_comm,
                weight=caller.call_ratio if hasattr(caller, 'call_ratio') else 0.0,
                path=path,
                hotspot=callers_report.target if hasattr(callers_report, 'target') else "",
                characteristic=StringConstants.CHAR_COMPUTE
            ))
    
    # 按权重排序，返回前8个
    clusters.sort(key=lambda c: c.weight, reverse=True)
    return clusters[:8]


def _detect_correlation_flags(
    bottleneck: BottleneckAnalysis,
    hotspots_report: HotspotsReport,
    callers_report: Optional[CallersReport]
) -> List[CorrelationFlag]:
    """
    检测关联标志
    
    Args:
        bottleneck: 瓶颈分析结果
        hotspots_report: 热点报告
        callers_report: 调用链报告（可选）
        
    Returns:
        List[CorrelationFlag]: 检测到的标志列表
    """
    flags: List[CorrelationFlag] = []
    
    if not bottleneck.found:
        return flags
    
    comm = bottleneck.comm
    
    # 1. GLOBAL_LOCK_CONTENTION: 全局锁符号 inclusive% > 40%
    if hotspots_report.hotspots:
        for hs in hotspots_report.hotspots:
            symbol = hs.symbol if hasattr(hs, 'symbol') else ""
            inclusive_pct = hs.inclusive_percent if hasattr(hs, 'inclusive_percent') else 0
            
            if any(ls in symbol for ls in StringConstants.GLOBAL_LOCK_SYMBOLS) or any(k in symbol.lower() for k in StringConstants.LOCK_KEYWORDS):
                if inclusive_pct > Thresholds.LOCK_CONTENTION_INCLUSIVE_PCT:
                    flags.append(CorrelationFlag(
                        flag_type="GLOBAL_LOCK_CONTENTION",
                        target=symbol,
                        message=f"全局锁 '{symbol}' 占用 {inclusive_pct:.1f}% CPU",
                        severity="critical"
                    ))
    
    # 2. SINGLE_CORE_SATURATION: Monopoly > 0.8
    if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
        flags.append(CorrelationFlag(
            flag_type="SINGLE_CORE_SATURATION",
            target=comm,
            message=f"{comm} Monopoly={bottleneck.monopoly:.2f}，单核饱和",
            severity="critical"
        ))
    
    # 3. THROTTLE_VICTIM: 高 Monopoly 和低 CPU
    if (bottleneck.monopoly > Thresholds.MONOPOLY_HIGH and 
        bottleneck.total_cpu < Thresholds.THROTTLE_VICTIM_CPU_MAX):
        throttle_rate = 100 - bottleneck.total_cpu
        flags.append(CorrelationFlag(
            flag_type="THROTTLE_VICTIM",
            target=comm,
            message=f"{comm} 可能被节流 (推断节流率 {throttle_rate:.1f}%)",
            severity="warning"
        ))
    
    # 4. STORM_PATTERN: 进程风暴
    if (bottleneck.diagnosis == DiagnosisType.STORM or 
        bottleneck.spawn_rate > Thresholds.STORM_SPAWN_RATE):
        flags.append(CorrelationFlag(
            flag_type="STORM_PATTERN",
            target=comm,
            message=f"{comm} 进程风暴 (Spawn_Rate={bottleneck.spawn_rate:.1f}/s)",
            severity="warning"
        ))
    
    # 5. KERNEL_HEAVY: 内核态占比 > 50%
    if bottleneck.kernel_ratio > Thresholds.KERNEL_RATIO_HIGH:
        flags.append(CorrelationFlag(
            flag_type="KERNEL_HEAVY",
            target=comm,
            message=f"{comm} 高内核态占比 ({bottleneck.kernel_ratio:.1f}%)",
            severity="warning"
        ))
    
    # 6. UNBALANCED_LOAD: CV > 1.5 且 Monopoly < 0.5
    if (bottleneck.cv > Thresholds.CV_UNBALANCED_LOAD and 
        bottleneck.monopoly < Thresholds.MONOPOLY_HIGH):
        flags.append(CorrelationFlag(
            flag_type="UNBALANCED_LOAD",
            target=comm,
            message=f"{comm} 负载不均衡 (CV={bottleneck.cv:.2f}, Monopoly={bottleneck.monopoly:.2f})",
            severity="info"
        ))
    
    return flags


def _build_risk_info(
    bottleneck: BottleneckAnalysis,
    correlation_flags: List[CorrelationFlag]
) -> RiskInfo:
    """
    构建 RiskInfo
    
    Args:
        bottleneck: 瓶颈分析结果
        correlation_flags: 关联标志列表
        
    Returns:
        RiskInfo: 风险信息
    """
    if not bottleneck.found:
        return RiskInfo(
            level="info",
            message="未检测到明显瓶颈进程",
            hint="尝试使用 sys-audit 进行全景扫描",
            patterns=["NO_BOTTLENECK_FOUND"],
            pending_targets=[],
            source="bottleneck_trace"
        )
    
    patterns = [f.flag_type for f in correlation_flags]
    critical_flags = [f for f in correlation_flags if f.severity == "critical"]
    warning_flags = [f for f in correlation_flags if f.severity == "warning"]
    
    comm = bottleneck.comm
    
    if critical_flags:
        return RiskInfo(
            level="critical",
            message=f"发现关键性能瓶颈: {comm}",
            hint=f"{comm} Monopoly={bottleneck.monopoly:.2f}, Impact={bottleneck.impact_score:.1f}",
            patterns=patterns,
            pending_targets=[comm],
            source="bottleneck_trace"
        )
    elif warning_flags:
        return RiskInfo(
            level="warning",
            message=f"发现潜在性能问题: {comm}",
            hint=f"{comm} 需要进一步分析",
            patterns=patterns,
            pending_targets=[comm],
            source="bottleneck_trace"
        )
    else:
        return RiskInfo(
            level="info",
            message=f"{comm} 分析完成，未发现严重问题",
            hint="",
            patterns=patterns,
            pending_targets=[],
            source="bottleneck_trace"
        )


@command("bottleneck-trace")
def cmd_bottleneck_trace(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> BottleneckTraceResult:
    """
    [Composite] 瓶颈追踪命令
    
    自动识别CPU瓶颈进程并进行深度分析
    如未指定--comm，自动识别最主要的瓶颈进程。
    
    Args:
        --comm: 指定目标进程（可选，未指定时自动识别）
    """
    target_comm = getattr(args, 'comm', None)
    target_pid = getattr(args, 'pid', None)
    top_n = getattr(args, 'top_n', 10)
    
    facade = AnalysisFacade(engine)
    
    # ========== Phase 1: 识别瓶颈 ==========
    
    # 如果指定了 PID 但没有指定 comm，尝试推导 comm
    if target_pid and not target_comm:
        target_comm = _get_comm_by_pid(samples, target_pid)
        if not target_comm:
            from perf_toolkit.core.output_models import RiskInfo
            risk = RiskInfo(
                level="error",
                message=f"无法找到 PID {target_pid} 对应的进程名",
                hint="请检查 PID 是否正确，或同时使用 --comm 指定进程名"
            )
            
            return BottleneckTraceResult(
                _risk=risk,
                entity_distribution=[],
                common_hotspot="",
                common_hotspot_weight=0.0,
                clusters=[],
                correlation_flags=[],
                total_pids=0,
                total_sys_cpu=0.0,
                top_bottlenecks=[],
                duration_sec=0.0,
                sample_count=len(samples),
                time_range=TimeRange.from_timestamps(
                    samples[0].get('ts') if samples and isinstance(samples[0], dict) else None,
                    samples[-1].get('ts') if len(samples) > 1 and isinstance(samples[-1], dict) else None
                )
            )
    
    # 如果同时指定了 comm 和 pid，验证 pid 是否属于该 comm
    if target_pid and target_comm:
        derived_comm = _get_comm_by_pid(samples, target_pid)
        if derived_comm and derived_comm != target_comm:
            from perf_toolkit.core.output_models import RiskInfo
            risk = RiskInfo(
                level="warning",
                message=f"PID {target_pid} 对应的进程名是 {derived_comm}，与指定的 --comm {target_comm} 不匹配",
                hint="请检查 PID 和进程名是否正确"
            )
            
            return BottleneckTraceResult(
                _risk=risk,
                entity_distribution=[],
                common_hotspot="",
                common_hotspot_weight=0.0,
                clusters=[],
                correlation_flags=[],
                total_pids=0,
                total_sys_cpu=0.0,
                top_bottlenecks=[],
                duration_sec=0.0,
                sample_count=len(samples),
                time_range=TimeRange.from_timestamps(
                    samples[0].get('ts') if samples and isinstance(samples[0], dict) else None,
                    samples[-1].get('ts') if len(samples) > 1 and isinstance(samples[-1], dict) else None
                )
            )
    
    if not target_comm:
        # 自动识别瓶颈进程
        target_comm = _find_bottleneck_comm(facade, samples)
        if not target_comm:
            # 未发现瓶颈
            risk = RiskInfo(
                level="info",
                message="未检测到明显瓶颈进程",
                hint="尝试运行 sys-audit 进行全面分析"
            )
            
            return BottleneckTraceResult(
                _risk=risk,
                entity_distribution=[],
                common_hotspot="",
                common_hotspot_weight=0.0,
                clusters=[],
                correlation_flags=[],
                total_pids=0,
                total_sys_cpu=0.0,
                top_bottlenecks=[],
                duration_sec=0.0,
                sample_count=len(samples),
                time_range=TimeRange.from_timestamps(
                    samples[0].get('ts') if samples and isinstance(samples[0], dict) else None,
                    samples[-1].get('ts') if len(samples) > 1 and isinstance(samples[-1], dict) else None
                )
            )
    
    # ========== Phase 2: 瓶颈分析 ==========
    
    bottleneck_analysis = _analyze_bottleneck(facade, samples, target_comm)
    
    # ========== Phase 3: 热点分析 ==========
    
    hotspots_result = facade.analyze_hotspots(samples, comm=target_comm, pid=target_pid, top_n=top_n)
    hotspots_report = _convert_hotspots_result(hotspots_result)

    # ========== Phase 4: 调用链溯源 ==========

    callers_report: Optional[CallersReport] = None
    if hotspots_report.top_symbol:
        callers_result = facade.analyze_callers(samples, target_symbol=hotspots_report.top_symbol, comm=target_comm, pid=target_pid)
        callers_report = _convert_callers_result(callers_result)
    
    # ========== Phase 5: 构建四段式输出结果 ==========
    
    # 1. 构建 Entity Distribution
    entity_distribution = _convert_to_entity_distribution(
        bottleneck_analysis, hotspots_report
    )
    
    # 2. 构建 Call Path Clusters
    clusters = _convert_to_call_path_clusters(
        hotspots_report, callers_report, target_comm
    )
    
    # 3. 检测 Correlation Flags
    correlation_flags = _detect_correlation_flags(
        bottleneck_analysis, hotspots_report, callers_report
    )
    
    # 4. 构建 RiskInfo
    risk = _build_risk_info(bottleneck_analysis, correlation_flags)
    
    # 5. 计算摘要数据
    top_bottlenecks = [hs.symbol for hs in hotspots_report.hotspots[:3]] if hotspots_report else []
    
    duration_sec = 0.0
    if samples:
        timestamps = [s.get('ts') for s in samples if isinstance(s, dict) and 'ts' in s]
        if timestamps:
            duration_sec = max(timestamps) - min(timestamps)
    
    # 6. 构建时间范围
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples and isinstance(samples[0], dict) else None,
        samples[-1].get('ts') if len(samples) > 1 and isinstance(samples[-1], dict) else None
    )
    
    # 记录到 Trace（如果有严重风险）
    if risk.level in ["critical", "warning"]:
        builder.record_risk(
            risk.level,
            f"[{target_comm}] {risk.message}",
            risk.hint
        )
    
    # 7. 返回四段式结果
    return BottleneckTraceResult(
        _risk=risk,
        entity_distribution=entity_distribution,
        common_hotspot=hotspots_report.top_symbol if hotspots_report else "",
        common_hotspot_weight=hotspots_report.hotspots[0].inclusive_percent if hotspots_report and hotspots_report.hotspots else 0.0,
        clusters=clusters,
        correlation_flags=correlation_flags,
        total_pids=bottleneck_analysis.pid_count if bottleneck_analysis.found else 0,
        total_sys_cpu=bottleneck_analysis.total_cpu if bottleneck_analysis.found else 0.0,
        top_bottlenecks=top_bottlenecks,
        duration_sec=duration_sec,
        sample_count=len(samples),
        time_range=time_range
    )
