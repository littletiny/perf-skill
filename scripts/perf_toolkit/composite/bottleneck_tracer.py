#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bottleneck Trace Adapter - 瓶颈追踪适配器

将现有的 BottleneckTracer 输出转换为 BottleneckTraceResult 格式，
用于生成四段式分析报告。

设计原则:
- 强类型: 使用 dataclass，禁止裸 dict
- 简单优先: let it crash，不做复杂错误处理
- AI 友好: 输出格式便于人类/AI 阅读
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import math

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.perf_toolkit.core.models import RiskInfo, TimeRange
from scripts.perf_toolkit.analysis.models import (
    CommTopResult, HotspotsResult, CoreDistributionResult,
    PathClustersResult, CallersResult, CommGroup, Hotspot,
    CoreStat, PathCluster, CallerAttribution
)
from scripts.perf_toolkit.analysis.facade import AnalysisFacade
from scripts.perf_toolkit.composite.bottleneck_trace import (
    BottleneckTracer, BottleneckAnalysis, HotspotsReport, CallersReport
)
from config.defaults import DiagnosisType, Thresholds, StringConstants, DiagnosisThresholds


# =============================================================================
# Data Structures - Bottleneck Trace Result Types
# =============================================================================

@dataclass
class EntityDistribution:
    """
    实体分布矩阵行
    
    描述进程组在多维度下的分布特征，用于识别瓶颈模式。
    """
    comm: str                       # 进程组名称
    count: int                      # PID 数量
    incl_saliency: float            # Inclusive 显著度 (0-1)
    excl_saliency: float            # Exclusive 显著度 (0-1)
    core_affinity: str              # Fixed/Uniform/Scattered
    throttle_rate: float            # 节流比例 (0-100%)


@dataclass
class CallPathCluster:
    """
    调用路径聚类
    
    表示从入口到热点的调用链，包含路径特征标签。
    """
    cluster_id: str                 # 聚类 ID
    comm: str                       # 所属进程
    weight: float                   # 占比 (0-100%)
    path: List[str]                 # 调用链符号列表（从入口到热点）
    hotspot: str                    # 汇聚热点符号
    characteristic: str             # 路径特征标签


@dataclass
class CorrelationFlag:
    """
    关联标志
    
    跨维度关联检测，标记系统性问题。
    """
    flag_type: str                  # GLOBAL_LOCK_CONTENTION, etc.
    target: str                     # 目标符号/进程
    message: str                    # 描述信息
    severity: str                   # critical/warning/info


@dataclass
class BottleneckTraceResult:
    """
    bottleneck-trace 完整输出
    
    Composite 层最终分析结果，供 CLI 层格式化输出。
    """
    # 风险信息（置顶）
    _risk: RiskInfo
    
    # 实体分布矩阵
    entity_distribution: List[EntityDistribution]
    
    # 收敛追踪
    common_hotspot: str
    common_hotspot_weight: float
    clusters: List[CallPathCluster]
    
    # 关联标志
    correlation_flags: List[CorrelationFlag]
    
    # 数据摘要
    total_pids: int
    total_sys_cpu: float
    top_bottlenecks: List[str]
    duration_sec: float
    sample_count: int
    
    # 时间范围
    time_range: TimeRange


# =============================================================================
# Bottleneck Trace Adapter - 适配现有 BottleneckTracer
# =============================================================================

class BottleneckTraceAdapter:
    """
    瓶颈追踪适配器
    
    包装现有的 BottleneckTracer，将其输出转换为 BottleneckTraceResult 格式，
    用于生成四段式分析报告。
    
    分析流程：
    1. 调用现有 BottleneckTracer 进行瓶颈分析
    2. 收集补充分析数据（核心分布、路径聚类等）
    3. 转换为 BottleneckTraceResult 格式
    """
    
    def __init__(self, facade: AnalysisFacade):
        """
        初始化适配器
        
        Args:
            facade: AnalysisFacade 实例
        """
        self._facade = facade
        self._tracer = BottleneckTracer(facade)
    
    def trace(self, samples: List[Any], 
              target_comm: Optional[str] = None) -> BottleneckTraceResult:
        """
        执行瓶颈追踪分析并返回 BottleneckTraceResult
        
        Args:
            samples: 样本数据列表
            target_comm: 可选，指定目标进程名。如为 None，自动识别
            
        Returns:
            BottleneckTraceResult: 完整分析结果
        """
        if not samples:
            return self._create_empty_result("无样本数据")
        
        # 步骤 1: 调用现有 BottleneckTracer
        bottleneck_analysis, hotspots_report, callers_report = self._tracer.trace(
            samples, target_comm=target_comm
        )
        
        actual_comm = bottleneck_analysis.comm if bottleneck_analysis.found else target_comm
        if not actual_comm:
            return self._create_empty_result("未检测到明显瓶颈进程")
        
        # 步骤 2: 收集补充分析数据
        comm_top_result = self._facade.analyze_comm_top(samples, top_n=20)
        core_dist_result = self._facade.analyze_core_distribution(samples, top_n=10)
        clusters_result = self._facade.cluster_paths(samples, comm=actual_comm, top_n=10)
        
        # 步骤 3: 转换为 BottleneckTraceResult
        return self._convert_to_result(
            bottleneck_analysis=bottleneck_analysis,
            hotspots_report=hotspots_report,
            callers_report=callers_report,
            comm_top_result=comm_top_result,
            core_dist_result=core_dist_result,
            clusters_result=clusters_result,
            samples=samples
        )
    
    def _find_bottleneck_comm(self, comm_top_result: CommTopResult) -> Optional[str]:
        """
        自动识别瓶颈进程
        
        策略：
        1. 优先选择 diagnosis == BOTTLENECK 的进程
        2. 否则选择 impact_score 最高的进程
        
        Args:
            comm_top_result: 进程组分析结果
            
        Returns:
            Optional[str]: 瓶颈进程名，未找到返回 None
        """
        groups = comm_top_result.groups
        if not groups:
            return None
        
        # 找第一个 BOTTLENECK
        for group in groups:
            if group.diagnosis == DiagnosisType.BOTTLENECK:
                return group.comm
        
        # 否则返回 impact_score 最高的
        sorted_groups = sorted(groups, key=lambda g: g.impact_score, reverse=True)
        return sorted_groups[0].comm if sorted_groups else None
    
    def _get_target_group(self, comm_top_result: CommTopResult, 
                          comm: str) -> Optional[CommGroup]:
        """
        获取指定进程组信息
        
        Args:
            comm_top_result: 进程组分析结果
            comm: 目标进程名
            
        Returns:
            Optional[CommGroup]: 进程组信息，未找到返回 None
        """
        for group in comm_top_result.groups:
            if group.comm == comm:
                return group
        return None
    
    def _calculate_saturation(self, hot_comms: List[CommGroup],
                              busy_cores_data: List[CoreStat]) -> Dict[str, float]:
        """
        计算进程饱和度
        
        Saturation(comm) = hot_comms ∩ busy_cores
        表示在忙核心上运行的热点进程的饱和程度
        
        Args:
            hot_comms: 热点进程列表
            busy_cores_data: 饱和核心数据列表
            
        Returns:
            Dict[str, float]: 进程名 -> 饱和度(0-1)
        """
        saturation_map = {}
        busy_core_ids = {c.cpu_id for c in busy_cores_data}
        
        if not busy_core_ids:
            return {g.comm: 0.0 for g in hot_comms}
        
        for group in hot_comms:
            # 简化计算：基于 Monopoly 和 CPU 利用率估算
            # 实际实现需要 Core 层提供更详细的 PID->Core 映射
            saturation = group.monopoly * min(group.total_cpu / 100.0, 1.0)
            saturation_map[group.comm] = min(saturation, 1.0)
        
        return saturation_map
    
    def _determine_affinity_pattern(self, distribution: Dict[int, float]) -> str:
        """
        判定核心亲缘性模式
        
        基于分布熵 Entropy 判定：
        - Fixed: Entropy < 1.0, Monopoly > 0.7 (单核心绑定)
        - Uniform: Entropy > 1.8, CV < 0.5 (均匀分布)
        - Scattered: 其他情况 (分散无规律)
        
        Args:
            distribution: 核心ID -> 权重的分布映射
            
        Returns:
            str: "Fixed" / "Uniform" / "Scattered"
        """
        if not distribution:
            return StringConstants.AFFINITY_SCATTERED
        
        values = list(distribution.values())
        total = sum(values)
        
        if total == 0:
            return StringConstants.AFFINITY_SCATTERED
        
        # 计算概率分布
        probs = [v / total for v in values]
        
        # 计算熵
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        
        # 计算变异系数 CV
        mean = total / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean if mean > 0 else float('inf')
        
        # 计算 Monopoly (最大值占比)
        monopoly = max(values) / total if total > 0 else 0
        
        # 判定模式
        # Fixed: 低熵(高度集中), 高垄断度
        if entropy < 1.0 and monopoly > Thresholds.MONOPOLY_HIGH:
            return StringConstants.AFFINITY_FIXED
        # Uniform: 高熵(分布均匀), 低变异系数
        elif entropy > 1.8 and cv < Thresholds.CV_AFFINITY_UNIFORM:
            return StringConstants.AFFINITY_UNIFORM
        else:
            return StringConstants.AFFINITY_SCATTERED
    
    def _detect_correlation_flags_from_reports(self, 
                                                bottleneck_analysis: BottleneckAnalysis,
                                                hotspots_report: HotspotsReport,
                                                core_dist_result: CoreDistributionResult,
                                                comm_top_result: CommTopResult) -> List[CorrelationFlag]:
        """
        从报告检测跨维度关联标志
        
        Args:
            bottleneck_analysis: 瓶颈分析结果
            hotspots_report: 热点报告
            core_dist_result: 核心分布结果
            comm_top_result: 进程组分析结果
            
        Returns:
            List[CorrelationFlag]: 检测到的标志列表
        """
        flags: List[CorrelationFlag] = []
        
        if not bottleneck_analysis.found:
            return flags
        
        comm = bottleneck_analysis.comm
        monopoly = bottleneck_analysis.monopoly
        total_cpu = bottleneck_analysis.total_cpu
        
        # 1. GLOBAL_LOCK_CONTENTION: 全局锁符号 inclusive% > LOCK_CONTENTION_INCLUSIVE_PCT
        if hotspots_report and hotspots_report.hotspots:
            for hotspot in hotspots_report.hotspots:
                symbol = hotspot.symbol if hasattr(hotspot, 'symbol') else ""
                inclusive_pct = hotspot.inclusive_percent if hasattr(hotspot, 'inclusive_percent') else 0
                
                if any(ls in symbol for ls in StringConstants.GLOBAL_LOCK_SYMBOLS):
                    if inclusive_pct > Thresholds.LOCK_CONTENTION_INCLUSIVE_PCT:
                        flags.append(CorrelationFlag(
                            flag_type="GLOBAL_LOCK_CONTENTION",
                            target=symbol,
                            message=f"全局锁 '{symbol}' 占用 {inclusive_pct:.1f}% CPU",
                            severity="critical"
                        ))
        
        # 2. SINGLE_CORE_SATURATION: 单核利用率 > 90% 且 Monopoly > MONOPOLY_HIGH
        for core_stat in core_dist_result.saturated_cores:
            if core_stat.total_cpu > Thresholds.AFFINITY_FIXED_CPU_MIN and monopoly > Thresholds.MONOPOLY_HIGH:
                flags.append(CorrelationFlag(
                    flag_type="SINGLE_CORE_SATURATION",
                    target=f"Core_{core_stat.cpu_id}",
                    message=f"核心 {core_stat.cpu_id} 利用率 {core_stat.total_cpu:.1f}%, "
                           f"{comm} Monopoly={monopoly:.2f}",
                    severity="critical"
                ))
        
        # 3. THROTTLE_VICTIM: 基于高 Monopoly 和低 CPU 推断
        if monopoly > Thresholds.MONOPOLY_HIGH and total_cpu < Thresholds.THROTTLE_VICTIM_CPU_MAX:
            throttle_rate = 100 - total_cpu
            if throttle_rate > Thresholds.THROTTLE_RATE_MIN:
                flags.append(CorrelationFlag(
                    flag_type="THROTTLE_VICTIM",
                    target=comm,
                    message=f"{comm} 可能被节流 (推断节流率 {throttle_rate:.1f}%)",
                    severity="warning"
                ))
        
        # 4. STORM_PATTERN: 从 comm_top_result 查找
        for group in comm_top_result.groups:
            if group.comm == comm:
                if group.spawn_rate > DiagnosisThresholds.STORM_RATE_MIN or group.pid_count > DiagnosisThresholds.STORM_PID_COUNT_MIN:
                    flags.append(CorrelationFlag(
                        flag_type="STORM_PATTERN",
                        target=comm,
                        message=f"{comm} 进程风暴 (Spawn_Rate={group.spawn_rate:.1f}/s, "
                               f"PID_Count={group.pid_count})",
                        severity="warning"
                    ))
                break
        
        # 5. KERNEL_HEAVY: 内核态占比 > KERNEL_RATIO_HIGH
        kernel_ratio = bottleneck_analysis.kernel_ratio
        if kernel_ratio > Thresholds.KERNEL_RATIO_HIGH:
            flags.append(CorrelationFlag(
                flag_type="KERNEL_HEAVY",
                target=comm,
                message=f"{comm} 高内核态占比 ({kernel_ratio:.1f}%)",
                severity="warning"
            ))
        
        # 6. UNBALANCED_LOAD: CV > CV_UNBALANCED_LOAD 且 Monopoly < MONOPOLY_HIGH
        cv = bottleneck_analysis.cv
        if cv > Thresholds.CV_UNBALANCED_LOAD and monopoly < Thresholds.MONOPOLY_HIGH:
            flags.append(CorrelationFlag(
                flag_type="UNBALANCED_LOAD",
                target=comm,
                message=f"{comm} 负载不均衡 (CV={cv:.2f}, "
                       f"Monopoly={monopoly:.2f})",
                severity="info"
            ))
        
        return flags
    
    def _infer_path_characteristic_from_hotspot(self, path: List[str], 
                                                 hotspot) -> str:
        """
        从热点信息推断调用路径特征
        
        Args:
            path: 调用路径符号列表
            hotspot: 热点项（来自 HotspotsReport）
            
        Returns:
            str: 路径特征标签
        """
        path_str = ' -> '.join(path).lower() if path else ""
        hotspot_symbol = hotspot.symbol.lower() if hasattr(hotspot, 'symbol') else ""
        
        # Lock_Contention: 热点为 lock/mutex/spinlock
        if any(k in hotspot_symbol for k in StringConstants.LOCK_KEYWORDS):
            return StringConstants.CHAR_LOCK_CONTENTION
        
        # IO_Wait_Dominant: io_schedule 高频
        if any(k in hotspot_symbol for k in StringConstants.IO_KEYWORDS) or any(k in path_str for k in StringConstants.IO_KEYWORDS):
            return StringConstants.CHAR_IO_WAIT
        
        # Syscall_Bound: 系统调用密集
        if any(k in path_str for k in StringConstants.SYSCALL_KEYWORDS):
            return StringConstants.CHAR_SYSCALL_BOUND
        
        # 获取 inclusive_percent 和 cpu_percent (self)
        inclusive_pct = getattr(hotspot, 'inclusive_percent', 0)
        self_pct = getattr(hotspot, 'cpu_percent', 0)
        
        # Inclusive_Latency_Victim: 等待资源/锁 (inclusive >> self)
        if inclusive_pct > self_pct * 3:
            return StringConstants.CHAR_LATENCY_VICTIM
        
        # High_Frequency_Exclusive_CPU: 高频独占 (self >> inclusive)
        if self_pct > inclusive_pct * 2:
            return StringConstants.CHAR_HIGH_FREQ_CPU
        
        return StringConstants.CHAR_COMPUTE
    
    def _find_common_hotspot(self, clusters: List[CallPathCluster],
                             hotspots: List[Hotspot]) -> Tuple[str, float]:
        """
        查找共享热点
        
        识别所有聚类共享的热点符号，通常是瓶颈汇聚点。
        
        Args:
            clusters: 调用路径聚类列表
            hotspots: 热点函数列表
            
        Returns:
            Tuple[str, float]: (共享热点名, 权重)
        """
        if not hotspots:
            return ("", 0.0)
        
        # 统计热点在聚类中的出现次数
        hotspot_count = defaultdict(int)
        for cluster in clusters:
            hotspot_count[cluster.hotspot] += 1
        
        # 找出现次数最多的热点
        if hotspot_count:
            common_hotspot = max(hotspot_count.items(), key=lambda x: x[1])
            # 查找对应的权重
            for h in hotspots:
                if h.symbol == common_hotspot[0]:
                    return (h.symbol, h.inclusive_pct)
        
        # 默认返回第一个热点
        if hotspots:
            return (hotspots[0].symbol, hotspots[0].inclusive_pct)
        
        return ("", 0.0)
    
    def _convert_to_result(self,
                           bottleneck_analysis: BottleneckAnalysis,
                           hotspots_report: HotspotsReport,
                           callers_report: Optional[CallersReport],
                           comm_top_result: CommTopResult,
                           core_dist_result: CoreDistributionResult,
                           clusters_result: PathClustersResult,
                           samples: List[Any]) -> BottleneckTraceResult:
        """
        将现有 BottleneckTracer 的输出转换为 BottleneckTraceResult
        
        Args:
            bottleneck_analysis: 瓶颈分析结果
            hotspots_report: 热点报告
            callers_report: 调用链报告（可选）
            comm_top_result: 进程组分析结果
            core_dist_result: 核心分布结果
            clusters_result: 路径聚类结果
            samples: 原始样本数据
            
        Returns:
            BottleneckTraceResult: 完整分析结果
        """
        target_comm = bottleneck_analysis.comm
        
        # 1. 构建 Entity Distribution
        entity_distribution = self._build_entity_distribution_from_reports(
            comm_top_result, core_dist_result, hotspots_report
        )
        
        # 2. 构建 Call Path Clusters
        clusters = self._build_call_path_clusters_from_reports(
            clusters_result, callers_report, hotspots_report, target_comm
        )
        
        # 3. 查找 Common Hotspot
        common_hotspot = hotspots_report.top_symbol if hotspots_report else ""
        common_hotspot_weight = 0.0
        if hotspots_report and hotspots_report.hotspots:
            common_hotspot_weight = hotspots_report.hotspots[0].inclusive_percent
        
        # 4. 检测 Correlation Flags
        correlation_flags = self._detect_correlation_flags_from_reports(
            bottleneck_analysis, hotspots_report, core_dist_result, comm_top_result
        )
        
        # 5. 计算摘要统计
        total_pids = sum(g.pid_count for g in comm_top_result.groups)
        total_sys_cpu = sum(g.total_cpu for g in comm_top_result.groups)
        top_bottlenecks = [h.symbol for h in hotspots_report.hotspots[:3]] if hotspots_report else []
        
        # 计算时间范围
        duration_sec = 0.0
        if samples:
            timestamps = [s.ts for s in samples if hasattr(s, 'ts')]
            if timestamps:
                duration_sec = max(timestamps) - min(timestamps)
        
        # 6. 构建 RiskInfo
        _risk = self._build_risk_info_from_analysis(correlation_flags, bottleneck_analysis)
        
        # 7. 构建时间范围
        time_range = self._build_time_range(samples)
        
        return BottleneckTraceResult(
            _risk=_risk,
            entity_distribution=entity_distribution,
            common_hotspot=common_hotspot,
            common_hotspot_weight=common_hotspot_weight,
            clusters=clusters,
            correlation_flags=correlation_flags,
            total_pids=total_pids,
            total_sys_cpu=total_sys_cpu,
            top_bottlenecks=top_bottlenecks,
            duration_sec=duration_sec,
            sample_count=len(samples),
            time_range=time_range
        )
    
    def _build_entity_distribution_from_reports(self,
                                                 comm_top_result: CommTopResult,
                                                 core_dist_result: CoreDistributionResult,
                                                 hotspots_report: HotspotsReport) -> List[EntityDistribution]:
        """
        从报告构建实体分布矩阵
        
        Args:
            comm_top_result: 进程组分析结果
            core_dist_result: 核心分布结果
            hotspots_report: 热点报告
            
        Returns:
            List[EntityDistribution]: 实体分布列表
        """
        distribution = []
        
        for group in comm_top_result.groups[:10]:  # 前10个进程组
            # 计算核心分布
            core_distribution = {c.cpu_id: c.total_cpu for c in core_dist_result.cores}
            affinity = self._determine_affinity_pattern(core_distribution)
            
            # 获取该进程的热点占比（简化处理，取最高热点）
            incl_saliency = 0.0
            excl_saliency = 0.0
            if hotspots_report and hotspots_report.hotspots:
                for hotspot in hotspots_report.hotspots:
                    if hotspot.symbol in group.comm or group.comm in hotspot.symbol:
                        incl_saliency = hotspot.inclusive_percent / 100.0
                        excl_saliency = hotspot.cpu_percent / 100.0
                        break
            
            # 计算节流率（简化：基于 Monopoly 和 CPU 利用率推断）
            throttle_rate = 0.0
            if group.monopoly > Thresholds.MONOPOLY_HIGH and group.total_cpu < Thresholds.AFFINITY_THROTTLE_INFER_CPU_MAX:
                throttle_rate = Thresholds.AFFINITY_THROTTLE_INFER_CPU_MAX - group.total_cpu
            
            distribution.append(EntityDistribution(
                comm=group.comm,
                count=group.pid_count,
                incl_saliency=incl_saliency,
                excl_saliency=excl_saliency,
                core_affinity=affinity,
                throttle_rate=throttle_rate
            ))
        
        return distribution
    
    def _build_call_path_clusters_from_reports(self,
                                                clusters_result: PathClustersResult,
                                                callers_report: Optional[CallersReport],
                                                hotspots_report: HotspotsReport,
                                                target_comm: str) -> List[CallPathCluster]:
        """
        从报告构建调用路径聚类
        
        Args:
            clusters_result: 路径聚类结果
            callers_report: 调用链报告（可选）
            hotspots_report: 热点报告
            target_comm: 目标进程名
            
        Returns:
            List[CallPathCluster]: 调用路径聚类列表
        """
        clusters: List[CallPathCluster] = []
        
        # 从路径聚类结果构建 (Top-Down)
        for i, pc in enumerate(clusters_result.clusters[:5]):
            path_sig = pc.path_signature if hasattr(pc, 'path_signature') else ""
            path = path_sig.split(' -> ') if path_sig else []
            
            # 推断关联的热点
            hotspot = ""
            if hotspots_report and hotspots_report.hotspots:
                for h in hotspots_report.hotspots:
                    if h.symbol in path_sig:
                        hotspot = h.symbol
                        break
                if not hotspot:
                    hotspot = hotspots_report.hotspots[0].symbol
            
            # 推断路径特征
            characteristic = StringConstants.CHAR_COMPUTE
            if hotspots_report and hotspots_report.hotspots:
                for h in hotspots_report.hotspots:
                    if h.symbol == hotspot:
                        characteristic = self._infer_path_characteristic_from_hotspot(path, h)
                        break
            
            clusters.append(CallPathCluster(
                cluster_id=f"cluster_{i}",
                comm=target_comm,
                weight=pc.weight if hasattr(pc, 'weight') else 0.0,
                path=path,
                hotspot=hotspot,
                characteristic=characteristic
            ))
        
        # 从调用者结果补充（Bottom-Up 视角）
        if callers_report and callers_report.callers:
            for i, caller in enumerate(callers_report.callers[:3]):
                symbol = caller.symbol if hasattr(caller, 'symbol') else ""
                path = symbol.split(' -> ') if symbol else []
                
                # 查找关联热点
                hotspot = callers_report.target if hasattr(callers_report, 'target') else ""
                characteristic = StringConstants.CHAR_COMPUTE
                if hotspots_report and hotspots_report.hotspots:
                    for h in hotspots_report.hotspots:
                        if h.symbol == hotspot:
                            characteristic = self._infer_path_characteristic_from_hotspot(path, h)
                            break
                
                clusters.append(CallPathCluster(
                    cluster_id=f"callers_{i}",
                    comm=target_comm,
                    weight=caller.call_ratio if hasattr(caller, 'call_ratio') else 0.0,
                    path=path,
                    hotspot=hotspot,
                    characteristic=characteristic
                ))
        
        # 按权重排序
        clusters.sort(key=lambda c: c.weight, reverse=True)
        
        return clusters[:8]  # 返回前8个聚类
    
    def _build_risk_info_from_analysis(self, 
                                        correlation_flags: List[CorrelationFlag],
                                        bottleneck_analysis: BottleneckAnalysis) -> RiskInfo:
        """
        从瓶颈分析构建 RiskInfo
        
        Args:
            correlation_flags: 关联标志列表
            bottleneck_analysis: 瓶颈分析结果
            
        Returns:
            RiskInfo: 风险信息
        """
        target_comm = bottleneck_analysis.comm
        patterns = [f.flag_type for f in correlation_flags]
        
        critical_flags = [f for f in correlation_flags if f.severity == "critical"]
        warning_flags = [f for f in correlation_flags if f.severity == "warning"]
        
        if not bottleneck_analysis.found:
            return RiskInfo(
                level="info",
                message=f"未检测到明显瓶颈进程",
                hint="尝试使用 sys-audit 进行全景扫描",
                patterns=["NO_BOTTLENECK_FOUND"],
                pending_targets=[],
                source="bottleneck_tracer"
            )
        
        if critical_flags:
            return RiskInfo(
                level="critical",
                message=f"发现关键性能瓶颈: {target_comm}",
                hint=f"{target_comm} Monopoly={bottleneck_analysis.monopoly:.2f}, "
                     f"Impact={bottleneck_analysis.impact_score:.1f}",
                patterns=patterns,
                pending_targets=[target_comm],
                source="bottleneck_tracer"
            )
        elif warning_flags:
            return RiskInfo(
                level="warning",
                message=f"发现潜在性能问题: {target_comm}",
                hint=f"{target_comm} 需要进一步分析",
                patterns=patterns,
                pending_targets=[target_comm],
                source="bottleneck_tracer"
            )
        else:
            return RiskInfo(
                level="info",
                message=f"{target_comm} 分析完成，未发现严重问题",
                hint="",
                patterns=patterns,
                pending_targets=[],
                source="bottleneck_tracer"
            )
    
    def _build_time_range(self, samples: List[Any]) -> TimeRange:
        """
        构建时间范围
        
        Args:
            samples: 样本数据列表
            
        Returns:
            TimeRange: 时间范围
        """
        if not samples:
            return TimeRange()
        
        timestamps = [s.ts for s in samples if hasattr(s, 'ts')]
        if not timestamps:
            return TimeRange()
        
        start_ts = min(timestamps)
        end_ts = max(timestamps)
        
        return TimeRange.from_timestamps(start_ts, end_ts)
    
    def _create_empty_result(self, message: str) -> BottleneckTraceResult:
        """
        创建空结果
        
        Args:
            message: 描述信息
            
        Returns:
            BottleneckTraceResult: 空结果
        """
        return BottleneckTraceResult(
            _risk=RiskInfo(
                level="info",
                message=message,
                hint="尝试使用 sys-audit 进行全景扫描",
                patterns=["NO_DATA"],
                pending_targets=[],
                source="bottleneck_tracer"
            ),
            entity_distribution=[],
            common_hotspot="",
            common_hotspot_weight=0.0,
            clusters=[],
            correlation_flags=[],
            total_pids=0,
            total_sys_cpu=0.0,
            top_bottlenecks=[],
            duration_sec=0.0,
            sample_count=0,
            time_range=TimeRange()
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def create_adapter(facade: AnalysisFacade) -> BottleneckTraceAdapter:
    """
    创建 BottleneckTraceAdapter 实例的便捷函数
    
    Args:
        facade: AnalysisFacade 实例
        
    Returns:
        BottleneckTraceAdapter: 瓶颈追踪适配器实例
    """
    return BottleneckTraceAdapter(facade)


def run_bottleneck_trace(facade: AnalysisFacade,
                         samples: List[Any],
                         target_comm: Optional[str] = None) -> BottleneckTraceResult:
    """
    执行瓶颈追踪分析并返回 BottleneckTraceResult
    
    Args:
        facade: AnalysisFacade 实例
        samples: 样本数据列表
        target_comm: 可选，目标进程名
        
    Returns:
        BottleneckTraceResult: 分析结果
    """
    adapter = create_adapter(facade)
    return adapter.trace(samples, target_comm)
