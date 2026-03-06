#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bottleneck-trace 命令实现

从 composite/bottleneck_trace.py 迁移而来
使用 V2 强类型输出模型（无裸 Dict）
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

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
from perf_toolkit.core.config_loader import get_analysis_thresholds
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import (
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
    ResourceUtilization,
    CPUOverview,
    CPUOverviewItem,
    CPUHotspotItem,
)
from perf_toolkit.core.bidirectional_view import (
    UpstreamBranch, DownstreamEntry, build_and_render_v2
)
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.models import (
    BottleneckAnalysis, HotspotsReport, CallersReport
)
from perf_toolkit.composite.bottleneck_trace import (
    _find_bottleneck_comm,
    _find_all_bottleneck_comms,
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


def _convert_to_resource_utilization(
    bottleneck: BottleneckAnalysis
) -> Optional[ResourceUtilization]:
    """
    将瓶颈分析结果转换为 ResourceUtilization
    
    用于展示被诊断进程/进程组的资源利用率。
    
    Args:
        bottleneck: 瓶颈分析结果
        
    Returns:
        Optional[ResourceUtilization]: 资源利用率数据，未找到瓶颈时返回 None
    """
    if not bottleneck.found:
        return None
    
    total_cpu = bottleneck.total_cpu
    kernel_ratio = bottleneck.kernel_ratio
    
    return ResourceUtilization(
        comm=bottleneck.comm,
        pid_count=bottleneck.pid_count,
        total_cpu=total_cpu,
        kernel_cpu=total_cpu * kernel_ratio / 100.0,
        user_cpu=total_cpu * (100.0 - kernel_ratio) / 100.0,
        kernel_ratio=kernel_ratio,
        monopoly=bottleneck.monopoly,
        cv=bottleneck.cv,
        impact_score=bottleneck.impact_score,
        diagnosis=bottleneck.diagnosis
    )


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
    
    # 从热点构建聚类 - Top-Down 方向
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
            path=[target_comm],
            hotspot=hs.symbol,
            characteristic=characteristic,
            direction="top_down"
        ))
    
    # 从调用者补充聚类 - Bottom-Up 方向
    if callers_report and callers_report.callers:
        for i, caller in enumerate(callers_report.callers[:3]):
            path = caller.symbol.split(' -> ') if ' -> ' in caller.symbol else [caller.symbol]
            
            clusters.append(CallPathCluster(
                cluster_id=f"caller_{i}",
                comm=target_comm,
                weight=caller.call_ratio if hasattr(caller, 'call_ratio') else 0.0,
                path=path,
                hotspot=callers_report.target if hasattr(callers_report, 'target') else "",
                characteristic=StringConstants.CHAR_COMPUTE,
                direction="bottom_up"
            ))
    
    # 按权重排序，返回前8个
    clusters.sort(key=lambda c: c.weight, reverse=True)
    return clusters[:8]


def _build_v2_bidirectional_view(
    comm: str,
    hotspot: str,
    callers_result: Optional[Any],
    path_clusters_result: Optional[Any],
    keep_top_n: int = 3
) -> str:
    """
    构建 V2 双向视图。
    
    从 callers 和 path_clusters 的结果中提取数据，构建三段式双向视图。
    
    Args:
        comm: 进程名
        hotspot: 热点函数
        callers_result: analyze_callers 的结果 (CallersResult)
        path_clusters_result: cluster_paths 的结果 (PathClustersResult)
        
    Returns:
        渲染后的双向视图字符串
    """
    # 1. 构建 Upstream Branches (Bottom-Up)
    upstream_branches: List[UpstreamBranch] = []
    if callers_result and callers_result.callers:
        for i, caller in enumerate(callers_result.callers):
            # caller.symbol 格式可能是 "sym1 -> sym2 -> sym3"
            if ' -> ' in caller.symbol:
                path = caller.symbol.split(' -> ')
            else:
                path = [caller.symbol]
            
            upstream_branches.append(UpstreamBranch(
                branch_id=chr(ord('A') + i),  # A, B, C...
                path=path,
                weight=caller.call_ratio if caller.call_ratio <= 100 else caller.call_ratio / 100,
                converges_at=None  # 稍后检测
            ))
    
    # 2. 构建 Downstream Entries (Top-Down)
    downstream_entries: List[DownstreamEntry] = []
    if path_clusters_result and path_clusters_result.clusters:
        for i, cluster in enumerate(path_clusters_result.clusters):
            # cluster.path_signature 格式: "sym1→sym2→sym3"
            if hasattr(cluster, 'path_signature') and cluster.path_signature:
                path = cluster.path_signature.split('→')
            elif hasattr(cluster, 'get_symbols'):
                path = cluster.get_symbols()
            else:
                path = []
            
            weight = cluster.weight if cluster.weight <= 100 else cluster.weight / 100
            
            downstream_entries.append(DownstreamEntry(
                entry_id=f"entry{i+1}",
                path=path,
                weight=weight
            ))
    
    # 3. 如果没有足够数据，返回提示信息
    if not upstream_branches and not downstream_entries:
        return f"*Insufficient data for bidirectional view of {comm}*"
    
    if not upstream_branches:
        # 只有 Top-Down 数据
        upstream_branches = [UpstreamBranch(
            branch_id="A",
            path=[hotspot],
            weight=100.0
        )]
    
    if not downstream_entries:
        # 只有 Bottom-Up 数据
        downstream_entries = [DownstreamEntry(
            entry_id="entry1",
            path=[comm],
            weight=100.0
        )]
    
    # 4. 构建并渲染 V2 视图（keep_top_n 条不聚合，其余聚合）
    return build_and_render_v2(
        comm=comm,
        hotspot=hotspot,
        upstream_branches=upstream_branches,
        downstream_entries=downstream_entries,
        keep_top_n=keep_top_n
    )


def _build_multi_hotspot_bidirectional_view(
    comm: str,
    hotspots_report: HotspotsReport,
    all_hotspots_callers: Dict[str, Any],
    keep_top_n: int = 3
) -> str:
    """
    构建多热点的双向视图。
    
    类似 find-callers --auto-target 的输出格式，为每个热点显示其调用来源。
    
    Args:
        comm: 进程名
        hotspots_report: 热点报告
        all_hotspots_callers: 每个热点的调用者结果 {symbol: CallersResult}
        keep_top_n: 每个热点保留的调用链数
        
    Returns:
        渲染后的多热点双向视图字符串
    """
    from perf_toolkit.core.symbol_formatter import SymbolFormatter
    
    lines: List[str] = []
    lines.append(f"## [BOTTLENECK: {comm}]")
    lines.append("")
    
    if not hotspots_report.hotspots:
        lines.append("*(No hotspot data)*")
        return "\n".join(lines)
    
    # 遍历所有热点，为每个热点显示调用链
    for hotspot in hotspots_report.hotspots[:10]:  # 最多显示前10个热点
        symbol = hotspot.symbol
        inclusive_pct = getattr(hotspot, 'inclusive_percent', getattr(hotspot, 'cpu_percent', 0))
        
        # 格式化热点符号
        is_agg = symbol.startswith('(aggregate:')
        formatted_symbol = SymbolFormatter.format_symbol(symbol, is_hotspot=True, is_aggregated=is_agg)
        
        # 显示热点函数头
        lines.append(f">>> {formatted_symbol} ({inclusive_pct:.2f}%)")
        
        # 获取该热点的调用者
        callers_result = all_hotspots_callers.get(symbol)
        
        if callers_result and callers_result.callers:
            # 显示该热点的调用链
            for i, caller in enumerate(callers_result.callers[:keep_top_n], 1):
                # caller.symbol 格式是 "sym1 -> sym2 -> sym3"
                if ' -> ' in caller.symbol:
                    path = caller.symbol.split(' -> ')
                else:
                    path = [caller.symbol]
                
                # 计算该调用链的 CPU 利用率贡献
                call_ratio = caller.call_ratio if caller.call_ratio <= 100 else caller.call_ratio / 100
                cpu_contrib = inclusive_pct * call_ratio / 100
                
                lines.append(f"  #{i} [{cpu_contrib:.2f}%] {' <- '.join(path)}")
        else:
            lines.append("  (No callchain data)")
        
        lines.append("")
    
    return "\n".join(lines)


def _build_cpu_overview(
    samples: List[Dict[str, Any]],
    engine: 'PerfExpertEngine',
    facade: AnalysisFacade
) -> CPUOverview:
    """
    构建 CPU Overview 数据 - 全局 CPU 视角
    
    展示 top 5 CPU 的利用率及其热点函数
    
    Args:
        samples: 样本数据
        engine: PerfExpertEngine 实例
        facade: AnalysisFacade 实例
        
    Returns:
        CPUOverview: CPU 全貌数据
    """
    from config.defaults import ImbalanceLevel
    
    # 1. 获取所有 CPU 的利用率
    core_util = engine.get_core_cpu_util(samples)
    
    if not core_util:
        return CPUOverview(
            imbalance_level=ImbalanceLevel.NORMAL,
            imbalance_message="No data available",
            top_cpus=[],
            total_cores=0,
            shown_cores=0
        )
    
    # 2. 按 total_pct 排序，过滤低于阈值的，取 top 5
    thresholds = get_analysis_thresholds()
    min_util = getattr(thresholds, 'cpu_overview_min_util', 40.0)
    sorted_cpus = sorted(
        [(k, v) for k, v in core_util.items() if v.total_pct >= min_util],
        key=lambda x: x[1].total_pct,
        reverse=True
    )[:5]
    
    # 3. 为每个 CPU 分析热点
    top_cpus: List[CPUOverviewItem] = []
    for cpu_id, util_info in sorted_cpus:
        # 过滤该 CPU 的样本
        cpu_samples = [s for s in samples if s.cpu == cpu_id]
        
        if not cpu_samples:
            continue
        
        # 分析该 CPU 的热点（top 5）
        hs_result = facade.analyze_hotspots(cpu_samples, top_n=5, sort_by='self')
        
        hotspots = [
            CPUHotspotItem(
                symbol=h.symbol,
                self_pct=h.self_pct,
                inclusive_pct=h.inclusive_pct
            )
            for h in hs_result.hotspots[:5]
        ]
        
        top_cpus.append(CPUOverviewItem(
            cpu_id=cpu_id,
            total_util=util_info.total_pct,
            kernel_util=util_info.kernel_pct,
            user_util=util_info.user_pct,
            hotspots=hotspots
        ))
    
    # 4. 计算不均衡等级
    all_utils = [info.total_pct for info in core_util.values()]
    max_util = max(all_utils) if all_utils else 0
    min_util = min(all_utils) if all_utils else 0
    avg_util = sum(all_utils) / len(all_utils) if all_utils else 0
    
    thresholds = get_analysis_thresholds()
    imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
    
    if imbalance_ratio > thresholds.imbalance_ratio_critical and max_util > thresholds.cpu_util_medium:
        imbalance_level = ImbalanceLevel.CRITICAL
        imbalance_message = "Load severely imbalanced: one core saturated"
    elif imbalance_ratio > thresholds.imbalance_high:
        imbalance_level = ImbalanceLevel.HIGH
        imbalance_message = "Load highly imbalanced"
    elif imbalance_ratio > thresholds.imbalance_medium:
        imbalance_level = ImbalanceLevel.MODERATE
        imbalance_message = "Load moderately imbalanced"
    else:
        imbalance_level = ImbalanceLevel.NORMAL
        imbalance_message = "Load balanced"
    
    return CPUOverview(
        imbalance_level=imbalance_level,
        imbalance_message=imbalance_message,
        top_cpus=top_cpus,
        total_cores=len(core_util),
        shown_cores=len(top_cpus)
    )


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
    
    # 获取分析阈值配置
    thresholds = get_analysis_thresholds()
    
    # 1. GLOBAL_LOCK_CONTENTION: 全局锁符号 inclusive% > 40%
    if hotspots_report.hotspots:
        for hs in hotspots_report.hotspots:
            symbol = hs.symbol if hasattr(hs, 'symbol') else ""
            inclusive_pct = hs.inclusive_percent if hasattr(hs, 'inclusive_percent') else 0
            
            if any(ls in symbol for ls in StringConstants.GLOBAL_LOCK_SYMBOLS) or any(k in symbol.lower() for k in StringConstants.LOCK_KEYWORDS):
                if inclusive_pct > thresholds.lock_contention_inclusive_pct:
                    flags.append(CorrelationFlag(
                        flag_type="GLOBAL_LOCK_CONTENTION",
                        target=symbol,
                        message=f"Global lock '{symbol}' uses {inclusive_pct:.1f}% CPU",
                        severity="critical"
                    ))
    
    # 2. SINGLE_CORE_SATURATION: Monopoly > 0.8
    if bottleneck.monopoly > thresholds.monopoly_high:
        flags.append(CorrelationFlag(
            flag_type="SINGLE_CORE_SATURATION",
            target=comm,
            message=f"{comm} Monopoly={bottleneck.monopoly:.2f}, single-core saturation",
            severity="critical"
        ))
    
    # 3. THROTTLE_VICTIM: 高 Monopoly 和低 CPU
    if (bottleneck.monopoly > thresholds.monopoly_high and 
        bottleneck.total_cpu < thresholds.throttle_victim_cpu_max):
        throttle_rate = 100 - bottleneck.total_cpu
        flags.append(CorrelationFlag(
            flag_type="THROTTLE_VICTIM",
            target=comm,
            message=f"{comm} may be throttled ({throttle_rate:.1f}% estimated)",
            severity="warning"
        ))
    
    # 4. STORM_PATTERN: 进程风暴
    if (bottleneck.diagnosis == DiagnosisType.STORM or 
        bottleneck.spawn_rate > thresholds.storm_spawn_rate):
        flags.append(CorrelationFlag(
            flag_type="STORM_PATTERN",
            target=comm,
            message=f"{comm} process storm ({bottleneck.spawn_rate:.1f}/s)",
            severity="warning"
        ))
    
    # 5. KERNEL_HEAVY: 内核态占比 > 50%
    if bottleneck.kernel_ratio > thresholds.kernel_ratio_high:
        flags.append(CorrelationFlag(
            flag_type="KERNEL_HEAVY",
            target=comm,
            message=f"{comm} high kernel ratio ({bottleneck.kernel_ratio:.1f}%)",
            severity="warning"
        ))
    
    # 6. UNBALANCED_LOAD: CV > 1.5 且 Monopoly < 0.5
    if (bottleneck.cv > thresholds.cv_unbalanced_load and 
        bottleneck.monopoly < thresholds.monopoly_high):
        flags.append(CorrelationFlag(
            flag_type="UNBALANCED_LOAD",
            target=comm,
            message=f"{comm} unbalanced load (CV={bottleneck.cv:.2f}, Monopoly={bottleneck.monopoly:.2f})",
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
            message="Not detected",
            hint="Try sys-audit for system-wide scan",
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
            message=f"Critical bottleneck found: {comm}",
            hint=f"{comm} Monopoly={bottleneck.monopoly:.2f}, Impact={bottleneck.impact_score:.1f}",
            patterns=patterns,
            pending_targets=[comm],
            source="bottleneck_trace"
        )
    elif warning_flags:
        return RiskInfo(
            level="warning",
            message=f"Potential issue found: {comm}",
            hint=f"{comm} needs further analysis",
            patterns=patterns,
            pending_targets=[comm],
            source="bottleneck_trace"
        )
    else:
        return RiskInfo(
            level="info",
            message=f"{comm} analysis complete, no critical issues found",
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
    
    # 记录用户是否手动指定了 comm
    user_specified_comm = target_comm is not None
    
    # 如果指定了 PID 但没有指定 comm，尝试推导 comm
    if target_pid and not target_comm:
        target_comm = _get_comm_by_pid(samples, target_pid)
        if not target_comm:
            risk = RiskInfo(
                level="error",
                message=f"Cannot find PID {target_pid} comm",
                hint="Check configuration"
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
        user_specified_comm = True  # 从 PID 推导出的 comm 视为用户指定
    
    # 如果同时指定了 comm 和 pid，验证 pid 是否属于该 comm
    if target_pid and target_comm:
        derived_comm = _get_comm_by_pid(samples, target_pid)
        if derived_comm and derived_comm != target_comm:
            risk = RiskInfo(
                level="warning",
                message=f"PID {target_pid} comm {derived_comm} does not match --comm {target_comm}",
                hint="Check configuration"
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
    
    # 所有待追踪的 bottleneck 进程列表
    all_bottleneck_comms: List[str] = []
    
    if not user_specified_comm:
        # 自动识别所有瓶颈进程
        all_bottleneck_comms = _find_all_bottleneck_comms(facade, samples)
        if not all_bottleneck_comms:
            # 未发现瓶颈
            risk = RiskInfo(
                level="info",
                message="Not detected",
                hint="Try sys-audit for comprehensive analysis"
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
        # 使用所有检测到的 bottleneck 进行分析
        target_comms = all_bottleneck_comms
    else:
        # 用户指定了特定 comm，只分析该进程
        target_comms = [target_comm]
    
    # 存储所有分析结果
    all_analyses: List[BottleneckAnalysis] = []
    all_hotspots: List[HotspotsReport] = []
    all_callers: List[Optional[CallersReport]] = []
    all_path_clusters: List[Optional[Any]] = []  # PathClustersResult
    all_entity_distributions: List[EntityDistribution] = []
    all_clusters_per_comm: Dict[str, List[CallPathCluster]] = {}
    all_correlation_flags: List[CorrelationFlag] = []
    
    for comm in target_comms:
        # 分析瓶颈特征
        analysis = _analyze_bottleneck(facade, samples, comm)
        if not analysis.found:
            continue
        all_analyses.append(analysis)
        
        # 热点分析
        hs_result = facade.analyze_hotspots(samples, comm=comm, pid=target_pid, top_n=top_n)
        hs_report = _convert_hotspots_result(hs_result)
        all_hotspots.append(hs_report)
        
        # 调用链溯源 (Bottom-Up) - 为所有热点获取调用者
        all_hotspots_callers: Dict[str, Any] = {}
        if hs_report.hotspots:
            for hotspot in hs_report.hotspots:
                # 跳过聚合符号（(aggregate:module)）
                if hotspot.symbol.startswith('(aggregate:'):
                    continue
                callers_result = facade.analyze_callers(
                    samples, 
                    target_symbol=hotspot.symbol, 
                    comm=comm, 
                    pid=target_pid
                )
                all_hotspots_callers[hotspot.symbol] = callers_result
        
        # 为兼容性，保留第一个有调用者的结果作为 callers_report
        callers_report: Optional[CallersReport] = None
        if hs_report.top_symbol and hs_report.top_symbol in all_hotspots_callers:
            callers_report = _convert_callers_result(all_hotspots_callers[hs_report.top_symbol])
        all_callers.append((callers_report, all_hotspots_callers))
        
        # 路径聚类 (Top-Down)
        path_clusters_result: Optional[Any] = None
        if hs_report.top_symbol:
            path_clusters_result = facade.cluster_paths(
                samples, 
                comm=comm, 
                pid=target_pid,
                top_n=5,
                min_depth=2
            )
        all_path_clusters.append(path_clusters_result)
        
        # 构建 Entity Distribution
        entity_dist = _convert_to_entity_distribution(analysis, hs_report)
        all_entity_distributions.extend(entity_dist)
        
        # 构建 Call Path Clusters (兼容旧格式)
        clusters = _convert_to_call_path_clusters(hs_report, callers_report, comm)
        all_clusters_per_comm[comm] = clusters
        
        # 检测 Correlation Flags
        flags = _detect_correlation_flags(analysis, hs_report, callers_report)
        all_correlation_flags.extend(flags)
    
    # 如果没有找到任何瓶颈
    if not all_analyses:
        risk = RiskInfo(
            level="info",
            message="Not detected",
            hint="Try sys-audit for comprehensive analysis"
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
    
    # ========== Phase 5: 构建聚合输出结果 ==========
    
    # 找到主要 bottleneck（按 impact_score 排序）
    primary_analysis = max(all_analyses, key=lambda a: a.impact_score)
    primary_idx = all_analyses.index(primary_analysis)
    primary_hotspots = all_hotspots[primary_idx]
    
    # 构建 RiskInfo - 报告所有发现的 bottleneck
    if len(all_analyses) == 1:
        # 只有一个 bottleneck
        risk = _build_risk_info(primary_analysis, all_correlation_flags)
    else:
        # 多个 bottleneck - 创建聚合 risk
        critical_count = sum(1 for a in all_analyses if a.monopoly > Thresholds.MONOPOLY_HIGH)
        warning_count = len(all_analyses) - critical_count
        
        comms_list = [a.comm for a in all_analyses]
        risk_level = "critical" if critical_count > 0 else "warning"
        risk_message = f"Found {len(all_analyses)} bottlenecks: {', '.join(comms_list[:3])}"
        if len(comms_list) > 3:
            risk_message += f" etc"
        
        risk = RiskInfo(
            level=risk_level,
            message=risk_message,
            hint=f"Auto-traced all {len(all_analyses)} bottleneck processes",
            patterns=["MULTI_BOTTLENECK_DETECTED"],
            pending_targets=comms_list,
            source="bottleneck_trace"
        )
    
    # 计算总 PIDs 和 Sys CPU
    total_pids = sum(a.pid_count for a in all_analyses)
    total_sys_cpu = sum(a.total_cpu for a in all_analyses)
    
    # 收集所有 top hotspots
    all_top_hotspots: List[str] = []
    for hs_report in all_hotspots:
        if hs_report.hotspots:
            all_top_hotspots.extend([hs.symbol for hs in hs_report.hotspots[:2]])
    
    # 去重并保持顺序
    seen = set()
    unique_hotspots = []
    for h in all_top_hotspots:
        if h not in seen:
            seen.add(h)
            unique_hotspots.append(h)
    
    # 计算时间范围
    duration_sec = 0.0
    if samples:
        timestamps = [s.get('ts') for s in samples if isinstance(s, dict) and 'ts' in s]
        if timestamps:
            duration_sec = max(timestamps) - min(timestamps)
    
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples and isinstance(samples[0], dict) else None,
        samples[-1].get('ts') if len(samples) > 1 and isinstance(samples[-1], dict) else None
    )
    
    # 为每个瓶颈进程生成双向视图 (V2) - 多热点模式
    bidirectional_views = []
    for idx, comm in enumerate(target_comms):
        if idx >= len(all_hotspots):
            continue
            
        hs_report = all_hotspots[idx]
        callers_info = all_callers[idx] if idx < len(all_callers) else (None, {})
        all_hotspots_callers = callers_info[1] if isinstance(callers_info, tuple) else {}
        
        if hs_report and hs_report.hotspots:
            # 使用多热点视图，类似 find-callers --auto-target 的输出
            view = _build_multi_hotspot_bidirectional_view(
                comm=comm,
                hotspots_report=hs_report,
                all_hotspots_callers=all_hotspots_callers,
                keep_top_n=min(top_n, 5)  # 每个热点显示前5个调用链
            )
            bidirectional_views.append(view)
    
    # Global legend for AI parsing (output once at the top)
    legend = "### [CALLCHAINS] Legend | Hotspot: **(hotspot:name)** | Aggregate: (aggregate:name) | Hotspot+Aggregate: **(hotspot:aggregate:name)** | Collapsed: (concept:name) | Omitted: .."
    bidirectional_view = legend + "\n\n---\n\n" + "\n\n---\n\n".join(bidirectional_views)
    
    # 收集所有 clusters（保持兼容性）
    all_clusters: List[CallPathCluster] = []
    for clusters in all_clusters_per_comm.values():
        all_clusters.extend(clusters)
    
    # 构建 ResourceUtilization（取主要瓶颈进程）
    target_resource_util = None
    if all_analyses:
        primary_analysis = max(all_analyses, key=lambda a: a.impact_score)
        target_resource_util = _convert_to_resource_utilization(primary_analysis)
    
    # 构建 CPU Overview（全局 CPU 视角）
    cpu_overview = _build_cpu_overview(samples, engine, facade)
    
    # 7. 返回聚合结果
    return BottleneckTraceResult(
        _risk=risk,
        target_resource_util=target_resource_util,
        entity_distribution=all_entity_distributions,
        common_hotspot=primary_hotspots.top_symbol if primary_hotspots else "",
        common_hotspot_weight=primary_hotspots.hotspots[0].inclusive_percent if primary_hotspots and primary_hotspots.hotspots else 0.0,
        clusters=all_clusters,
        correlation_flags=all_correlation_flags,
        total_pids=total_pids,
        total_sys_cpu=total_sys_cpu,
        top_bottlenecks=unique_hotspots[:5],
        duration_sec=duration_sec,
        sample_count=len(samples),
        time_range=time_range,
        bidirectional_view=bidirectional_view,
        cpu_overview=cpu_overview
    )
