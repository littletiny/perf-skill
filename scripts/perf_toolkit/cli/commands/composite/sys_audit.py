#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sys-audit 命令实现

从 composite/sys_audit.py 迁移而来
使用 V2 强类型输出模型（无裸 Dict）
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from config.defaults import (
    DiagnosisType, PressureState, ContextSwitchRate,
    AttentionFlag, RiskPattern, Thresholds,
    ImbalanceLevel, ExpertAnchorType, CompositeDefaults,
    SeverityLevel
)

from perf_toolkit.cli.decorators import command
from perf_toolkit.core.models import RiskInfo, TimeRange
from perf_toolkit.core.output_models import (
    SysAuditOutput, SystemFingerprint, ContentionItem,
    PrimarySuspectOutput, SecondaryLoadOutput, BackgroundNoiseOutput,
    ProcessHierarchy, CoreDistributionData, CoreSaturationItem,
    AnomalySummaryOutput, ExpertAnchor, RootCauseChain,
    CommTopItem
)
from perf_toolkit.core.core_distribution_builder import (
    build_core_distribution_for_sys_audit
)
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator
from perf_toolkit.composite.models import (
    AnomaliesReport, CoreDistributionReport, CommTopReport,
    ProcessGroup
)
from perf_toolkit.composite.sys_audit import (
    _synthesize_diagnosis,
    _convert_anomalies_result,
    _convert_core_dist_result,
    _convert_comm_top_result,
)

if TYPE_CHECKING:
    from perf_toolkit.cli.builders import OutputBuilder
    from perf_toolkit.core import PerfExpertEngine
    from argparse import Namespace


def _build_system_fingerprint(
    diagnosis: 'DiagnosisReport',
    core_dist: CoreDistributionReport,
    all_groups: List['ProcessGroup']
) -> SystemFingerprint:
    """构建系统指纹（强类型）"""
    from perf_toolkit.core.config_loader import get_config
    
    # 读取 CPU 规格配置
    cpu_specs = get_config().get_cpu_specs()
    core_count = cpu_specs.core_count
    total_capacity = core_count * 100.0  # 总容量 = 核心数 * 100%
    
    # 指标1: 最高 sys 占比（系统级问题严重程度）
    max_sys = max((g.kernel_cpu for g in all_groups), default=0)
    
    # 指标2: 总 CPU 需求（系统负载）
    total_demand = sum(g.total_cpu for g in all_groups)
    utilization = total_demand / total_capacity if total_capacity > 0 else 0
    
    # 指标3: BOTTLENECK 进程数量
    bottleneck_count = sum(1 for g in all_groups if g.diagnosis == DiagnosisType.BOTTLENECK)
    
    # 判定逻辑（基于相对阈值）
    # CRITICAL: 利用率 > critical_utilization 或 单核心 sys > critical_sys_per_core
    if utilization > cpu_specs.critical_utilization or max_sys > cpu_specs.critical_sys_per_core:
        pressure_state = PressureState.CRITICAL_CONTENTION
    # MODERATE: 利用率 > moderate_utilization 或 多个瓶颈
    elif utilization > cpu_specs.moderate_utilization or bottleneck_count >= 2:
        pressure_state = PressureState.MODERATE_CONTENTION
    else:
        pressure_state = PressureState.NORMAL
    
    return SystemFingerprint(
        pressure_state=pressure_state,
        # NOTE: PSI 数据需要从 /proc/pressure/ 读取，当前未实现
        cpu_some=0.0,
        cpu_full=0.0,
        io_some=0.0,
        # NOTE: Throttle 事件需要从 cgroup v2 cpu.stat 读取，当前未实现
        throttle_events=0,
        context_switch_rate=ContextSwitchRate.NORMAL
    )


def _build_contention_matrix(
    diagnosis: 'DiagnosisReport',
    comm_top: CommTopReport
) -> List[ContentionItem]:
    """构建竞争矩阵（强类型）
    
    TODO: 暂时移除 CPU Quota 竞争显示，因为无法获取真实的 cgroup limit。
    当前硬编码的 200% 假设不准确，需要后续从 /sys/fs/cgroup/cpu.max 读取真实值。
    """
    items: List[ContentionItem] = []
    
    # NOTE: CPU Quota 竞争分析已禁用
    # 真实 cgroup limit 读取需要容器内访问权限，暂时无法可靠获取
    # 如有需要，可通过环境变量或手动配置传入 limit 值
    
    return items


def _build_process_hierarchy(
    diagnosis: 'DiagnosisReport'
) -> ProcessHierarchy:
    """构建进程分层（强类型）"""
    # Primary Suspect
    primary = None
    if diagnosis.primary_suspect:
        p = diagnosis.primary_suspect
        primary = PrimarySuspectOutput(
            comm=p.comm,
            total_cpu=p.total_cpu,
            diagnosis=p.diagnosis,
            monopoly=p.monopoly,
            impact_score=p.impact_score,
            attention_flag=AttentionFlag.X0 if p.monopoly > Thresholds.MONOPOLY_HIGH else ""
        )
    
    # Secondary Loads
    secondary = [
        SecondaryLoadOutput(
            comm=g.comm,
            total_cpu=g.total_cpu,
            diagnosis=g.diagnosis,
            spawn_rate=g.spawn_rate,
            attention_flag=AttentionFlag.X1 if g.diagnosis == DiagnosisType.STORM else ""
        )
        for g in diagnosis.secondary_loads
    ]
    
    # Background Noise
    background = None
    if diagnosis.background_noise:
        total_bg_cpu = sum(g.total_cpu for g in diagnosis.background_noise)
        background = BackgroundNoiseOutput(
            count=diagnosis.background_count,
            total_cpu=total_bg_cpu,
            folded=True
        )
    
    return ProcessHierarchy(
        primary_suspect=primary,
        secondary_loads=secondary,
        background_noise=background
    )


def _build_core_distribution(
    core_dist: CoreDistributionReport
) -> CoreDistributionData:
    """构建核心分布输出（强类型）"""
    top_saturated = [
        CoreSaturationItem(
            cpu_id=c.cpu_id,
            total_util=c.total_cpu,
            kernel_util=c.kernel_cpu
        )
        for c in core_dist.core_stats[:5]
        if c.total_cpu > 50  # 只显示高负载核心
    ]
    
    return CoreDistributionData(
        imbalance_level=core_dist.imbalance_level,
        saturated_cores=core_dist.saturated_cores,
        attention_flag=AttentionFlag.X1 if core_dist.imbalance_level in [ImbalanceLevel.HIGH, ImbalanceLevel.CRITICAL] else "",
        top_saturated=top_saturated
    )


def _build_expert_anchors(
    diagnosis: 'DiagnosisReport',
    comm_top: CommTopReport
) -> List[ExpertAnchor]:
    """构建专家锚点（强类型）
    
    注意：只有 CPU 绝对值 (>display_min) 或 sys 绝对值 (>sys_display_min) 
    高的进程才展示锚点，避免低负载进程的噪音干扰。
    阈值从配置 display_threshold 读取。
    """
    from perf_toolkit.core.config_loader import get_config
    
    anchors: List[ExpertAnchor] = []
    
    # 从配置读取显示阈值
    display_thresh = get_config().get_display_threshold()
    CPU_MIN = display_thresh.display_min
    SYS_MIN = display_thresh.sys_display_min
    
    # Noisy Neighbor 检测 - 过滤低负载进程
    storm_groups = [g for g in comm_top.groups 
                   if g.diagnosis == DiagnosisType.STORM 
                   and (g.total_cpu > CPU_MIN or g.kernel_cpu > SYS_MIN)]
    if storm_groups:
        for g in storm_groups[:CompositeDefaults.DEFAULT_EXPERT_ANCHORS_LIMIT]:  # 最多显示 2 个
            anchors.append(ExpertAnchor(
                type=ExpertAnchorType.NOISY_NEIGHBOR,
                target=g.comm,
                description=f"{g.pid_count} 个进程高频活动，可能触发系统级资源竞争",
                impact="影响其他正常业务进程",
                attention_flag=AttentionFlag.X0,
                recommendation=f"检查 {g.comm} 的进程创建源头"
            ))
    
    # NOTE: QUOTA_VICTIM 检测已移除
    # 原因：
    # 1. 无法获取真实 cgroup limit，无法准确判断谁是受害者
    # 2. 真正的受害者（被抢占 CPU 的进程）已在"进程分层"中体现
    # 3. 主嫌疑人（如 netstat）实际上是加害人而非受害者
    
    return anchors


def _build_root_cause_chain(
    diagnosis: 'DiagnosisReport'
) -> Optional[RootCauseChain]:
    """构建根因链（强类型）
    
    NOTE: 已禁用。原因：
    1. 信息重复：Primary/Secondary 已在"进程分层"中展示
    2. 描述不准确：硬编码"单进程独占"但 Monopoly 低时是多进程
    3. 受害者判断错误：primary 是加害人而非受害者
    4. 建议操作已在"后续操作"中提供
    """
    return None


@command("sys-audit")
def cmd_sys_audit(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> SysAuditOutput:
    """
    [Composite] 系统审计组合命令
    
    自动编排多个分析工具，生成综合诊断报告。
    通过Facade调用Analysis层，不触发子命令的Trace记录。
    使用 V2 强类型输出模型（无裸 Dict）。
    """
    top_n = getattr(args, 'top_n', 20)
    
    # ========== Phase 1: 通过Facade执行各维度分析 ==========
    
    facade = AnalysisFacade(engine)
    
    # 1.1 异常检测
    anomalies_result = facade.detect_anomalies(samples, window_size=10, spike_threshold=0.5)
    anomalies = _convert_anomalies_result(anomalies_result)

    # 1.2 核心分布分析
    core_dist_result = facade.analyze_core_distribution(samples)
    core_dist = _convert_core_dist_result(core_dist_result)

    # 1.3 CommTop分析（增强版，通过include_metrics获取详细指标）
    from perf_toolkit.analysis.comm_top import CommTopAnalyzer
    comm_top_analyzer = CommTopAnalyzer(engine)
    comm_top_result = comm_top_analyzer.analyze(samples, top_n=top_n, include_metrics=True)
    comm_top = _convert_comm_top_result(comm_top_result)
    
    # ========== Phase 2: 综合分析 ==========
    
    diagnosis = _synthesize_diagnosis(anomalies, core_dist, comm_top)
    
    # ========== Phase 3: 收集Risks ==========
    
    aggregator = RiskAggregator()
    aggregator.add_risks(anomalies.risks)
    aggregator.add_risks(core_dist.risks)
    aggregator.add_risks(comm_top.risks)
    
    # 如果综合分析发现了额外风险，添加到aggregator
    if diagnosis.primary_suspect:
        primary = diagnosis.primary_suspect
        aggregator.add_risk(RiskInfo(
            level=SeverityLevel.CRITICAL.lower(),
            message=f"{AttentionFlag.X0} 主要性能瓶颈: {primary.comm}",
            hint=f"{AttentionFlag.XA} bottleneck-trace --comm {primary.comm}",
            patterns=[RiskPattern.PRIMARY_SUSPECT],
            pending_targets=[primary.comm],
            source="sys_audit"
        ))
    
    # ========== Phase 4: 生成聚合Risk ==========
    
    aggregated_risk = aggregator.aggregate()
    
    # 记录到Trace（只记录聚合后的，不记录子分析）
    if aggregated_risk.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated_risk.level,
            aggregated_risk.message,
            aggregated_risk.hint
        )
    
    # 构建 RiskInfo，嵌入 SHECR Attention Flags
    risk = RiskInfo(
        level=aggregated_risk.level,
        message=f"{AttentionFlag.X0} {aggregated_risk.message}" if diagnosis.primary_suspect else aggregated_risk.message,
        hint=f"{AttentionFlag.XA} {aggregated_risk.hint}" if aggregated_risk.hint else "",
        patterns=aggregated_risk.patterns,
        pending_targets=aggregated_risk.pending_targets
    )
    
    # ========== Phase 5: 构建强类型输出 ==========
    
    time_range = TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if len(samples) > 1 else None
    )
    
    # 构建所有强类型数据（无裸 Dict）
    # 获取所有进程组用于系统状态计算
    all_groups = comm_top.metrics.all_groups if comm_top.metrics else comm_top.groups
    system_fingerprint = _build_system_fingerprint(diagnosis, core_dist, all_groups)
    contention_matrix = _build_contention_matrix(diagnosis, comm_top)
    process_hierarchy = _build_process_hierarchy(diagnosis)
    core_distribution = _build_core_distribution(core_dist)
    anomaly_summary = AnomalySummaryOutput(
        anomalies_count=len(anomalies.anomalies),
        mutation_detected=anomalies.mutation_detected
    )
    expert_anchors = _build_expert_anchors(diagnosis, comm_top)
    root_cause_chain = _build_root_cause_chain(diagnosis)
    
    # 构建 Top By Total CPU 和 Top By Sys CPU 列表
    top_by_total = []
    top_by_sys = []
    
    if hasattr(comm_top_result, 'groups_by_total_cpu') and comm_top_result.groups_by_total_cpu:
        top_by_total = [
            CommTopItem(
                comm=g.comm,
                total_cpu=g.total_cpu,
                kernel_cpu=g.kernel_cpu,
                user_cpu=g.user_cpu,
                pid_count=g.pid_count,
                monopoly=g.monopoly,
                diagnosis=g.diagnosis,
                attention_flag=AttentionFlag.X0 if g.monopoly > Thresholds.MONOPOLY_HIGH else ""
            )
            for g in comm_top_result.groups_by_total_cpu[:top_n]
        ]
    
    if hasattr(comm_top_result, 'groups_by_sys_cpu') and comm_top_result.groups_by_sys_cpu:
        top_by_sys = [
            CommTopItem(
                comm=g.comm,
                total_cpu=g.total_cpu,
                kernel_cpu=g.kernel_cpu,
                user_cpu=g.user_cpu,
                pid_count=g.pid_count,
                monopoly=g.monopoly,
                diagnosis=g.diagnosis,
                attention_flag=AttentionFlag.X0 if g.monopoly > Thresholds.MONOPOLY_HIGH else ""
            )
            for g in comm_top_result.groups_by_sys_cpu[:top_n]
        ]
    
    # 构建建议
    recommendations = []
    if diagnosis.primary_suspect:
        recommendations.append(f"{AttentionFlag.XA} bottleneck-trace --comm {diagnosis.primary_suspect.comm} 深度分析")
    for g in diagnosis.secondary_loads:
        if g.diagnosis == DiagnosisType.STORM:
            recommendations.append(f"{AttentionFlag.XA} 检查 {g.comm} 的进程创建源头")
    recommendations.append(f"{AttentionFlag.XA} trace issues 查看所有待处理 issue")
    
    output = SysAuditOutput(
        _risk=risk,
        system_fingerprint=system_fingerprint,
        contention_matrix=contention_matrix,
        process_hierarchy=process_hierarchy,
        core_distribution=core_distribution,
        anomaly_summary=anomaly_summary,
        expert_anchors=expert_anchors,
        root_cause_chain=root_cause_chain,
        recommendations=recommendations,
        time_range=time_range,
        top_by_total_cpu=top_by_total,
        top_by_sys_cpu=top_by_sys
    )
    
    return output
