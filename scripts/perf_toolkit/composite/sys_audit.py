#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sys Audit - 系统审计组合命令

Composite层命令，通过Facade编排多个analysis工具：
1. detect-anomalies → 发现突变时刻
2. analyze-core-distribution → 分析核心分布  
3. analyze-comm-top → 分析进程组（增强版，含CV/Monopoly/SpawnRate）

然后综合分析结果，解决"A掩盖B"问题。

注意：CLI 命令已迁移到 cli/commands/composite/sys_audit.py
本文件保留辅助函数和 SysAuditor 类供 CLI 命令使用
"""

from typing import Optional, List, Dict, Tuple

from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.risk_aggregator import RiskAggregator, AggregatedRisk
from perf_toolkit.composite.models import (
    RiskItem, ProcessGroup, DiagnosisReport,
    AnomaliesReport, CoreDistributionReport, CommTopReport,
    PrimarySuspectData, SecondaryLoadData, DiagnosisDetails,
    AnomaliesDetails, CoreDistDetails, CommTopDetails, SysAuditDetails
)


class SysAuditor:
    """
    系统审计器
    
    编排多个 Analysis 层分析器，生成综合诊断报告。
    
    分析流程：
    1. detect-anomalies → 发现突变时刻
    2. analyze-core-distribution → 分析核心分布
    3. analyze-comm-top → 分析进程组（含 CV/Monopoly/SpawnRate）
    4. 综合分析，区分 Primary/Secondary/Background
    
    使用示例：
        engine = PerfExpertEngine()
        facade = AnalysisFacade(engine)
        auditor = SysAuditor(facade)
        
        samples = engine.get_filtered_samples()
        report, aggregated_risk = auditor.audit(samples)
    """
    
    def __init__(self, facade: AnalysisFacade):
        """
        初始化审计器
        
        Args:
            facade: AnalysisFacade 实例
        """
        self._facade = facade
        self._aggregator = RiskAggregator()
    
    def audit(self, samples: List[Dict], 
              top_n: int = 10) -> Tuple[DiagnosisReport, AggregatedRisk]:
        """
        执行系统审计
        
        Args:
            samples: 样本数据（由 core.engine 提供）
            top_n: 返回前 N 个进程组
            
        Returns:
            Tuple[DiagnosisReport, AggregatedRisk]: 诊断报告和聚合风险
        """
        # 1. 执行各维度分析
        anomalies_result = self._facade.detect_anomalies(samples)
        core_dist_result = self._facade.analyze_core_distribution(samples)
        comm_top_result = self._facade.analyze_comm_top(samples, top_n=top_n)
        
        # 2. 转换为 Composite 层类型
        anomalies_report = AnomaliesReport.from_analysis_result(anomalies_result)
        comm_top_report = CommTopReport.from_analysis_result(comm_top_result)
        
        # 3. 聚合 risks
        self._aggregator.add_risks(anomalies_report.risks, source="anomalies")
        self._aggregator.add_risks(core_dist_result.risks, source="core_dist")
        self._aggregator.add_risks(comm_top_report.risks, source="comm_top")
        
        # 4. 综合分析结果
        diagnosis = self._synthesize(
            anomalies_report, 
            core_dist_result, 
            comm_top_report
        )
        diagnosis.risks = list(self._aggregator._risks)
        
        # 5. 返回结果
        aggregated_risk = self._aggregator.get_aggregate_risk()
        return diagnosis, aggregated_risk
    
    def _synthesize(self, anomalies: AnomaliesReport,
                    core_dist: 'CoreDistributionResult',
                    comm_top: CommTopReport) -> DiagnosisReport:
        """
        综合分析结果，识别真正瓶颈
        
        核心逻辑（解决 A 掩盖 B 问题）：
        1. 识别突变时刻
        2. 分析核心饱和情况
        3. 按危害指数（而非绝对 CPU）排序进程组
        4. 区分 Primary/Secondary/Background
        
        Args:
            anomalies: 异常检测报告
            core_dist: 核心分布结果
            comm_top: 进程组报告
            
        Returns:
            DiagnosisReport: 综合诊断报告
        """
        # 1. 检查突变
        mutation_time = None
        if anomalies.mutation_detected and anomalies.anomalies:
            mutation_time = anomalies.anomalies[0].timestamp
        
        # 2. 获取核心饱和情况
        saturated_cores = [
            c.cpu_id for c in core_dist.cores 
            if c.total_cpu > 80  # 阈值可配置
        ]
        
        # 3. 获取所有进程组（包括被折叠的）
        all_groups = comm_top.metrics.all_groups if comm_top.metrics else comm_top.groups
        
        # 4. 分类：Primary / Secondary / Background
        primary = None
        secondary = []
        background = []
        
        for g in all_groups:
            if g.diagnosis == "BOTTLENECK":
                if primary is None:
                    primary = g
                else:
                    secondary.append(g)
            elif g.total_cpu > 10 or g.diagnosis in ["STORM", "UNBALANCED"]:
                secondary.append(g)
            else:
                background.append(g)
        
        # 5. 构建根因分析
        root_cause = self._build_root_cause(primary, secondary, anomalies, saturated_cores)
        
        # 6. 生成建议
        recommendations = self._generate_recommendations(primary, secondary)
        
        return DiagnosisReport(
            primary_suspect=primary,
            secondary_loads=secondary[:3],
            background_noise=background[:5],
            background_count=len(background),
            mutation_detected=anomalies.mutation_detected,
            mutation_time=mutation_time,
            saturated_cores=saturated_cores,
            imbalance_level=core_dist.imbalance_level,
            root_cause_analysis=root_cause,
            recommendations=recommendations
        )
    
    def _build_root_cause(self, primary: Optional[ProcessGroup],
                         secondary: List[ProcessGroup],
                         anomalies: AnomaliesReport,
                         saturated_cores: List[int]) -> str:
        """构建根因分析描述"""
        parts = []
        
        if primary:
            parts.append(f"主要瓶颈: {primary.comm} ({primary.diagnosis})")
        
        if anomalies.mutation_detected:
            parts.append("检测到性能突变")
        
        if saturated_cores:
            cores_str = ', '.join(map(str, saturated_cores[:3]))
            parts.append(f"核心饱和: CPU {cores_str}")
        
        if secondary:
            comms = ', '.join(s.comm for s in secondary[:2])
            parts.append(f"次要负载: {comms}")
        
        return "; ".join(parts) if parts else "未检测到明显瓶颈"
    
    def _generate_recommendations(self, primary: Optional[ProcessGroup],
                                 secondary: List[ProcessGroup]) -> List[str]:
        """生成建议操作"""
        recommendations = []
        
        if primary:
            recommendations.append(
                f"执行 bottleneck-trace --comm {primary.comm} 深入分析"
            )
        
        for g in secondary:
            if g.diagnosis == "STORM":
                recommendations.append(
                    f"进程 {g.comm} 可能存在进程风暴，建议检查进程生命周期"
                )
        
        return recommendations


# 以下辅助函数保留供 cli/commands/composite/sys_audit.py 使用

def _synthesize_diagnosis(anomalies: AnomaliesReport, 
                          core_dist: CoreDistributionReport,
                          comm_top: CommTopReport) -> DiagnosisReport:
    """
    综合分析结果，识别真正的瓶颈
    
    核心逻辑（解决A掩盖B问题）:
    1. 识别突变时刻
    2. 分析核心饱和情况
    3. 按危害指数（而非绝对CPU）排序进程组
    4. 区分Primary/Secondary/Background
    """
    # 1. 检查是否有突变
    mutation_time = None
    if anomalies.mutation_detected and anomalies.anomalies:
        mutation_time = anomalies.anomalies[0].timestamp
    
    # 2. 分析核心饱和情况
    saturated_cores = core_dist.saturated_cores
    
    # 3. 获取进程组（已按危害指数排序）
    groups = comm_top.groups
    
    # 获取所有组（包括被折叠的）用于完整分析
    all_groups = comm_top.metrics.all_groups if comm_top.metrics else groups
    
    # 4. 分类：Primary / Secondary / Background
    primary: Optional[ProcessGroup] = None
    secondary: list[ProcessGroup] = []
    background: list[ProcessGroup] = []
    
    for g in all_groups:
        diagnosis = g.diagnosis
        total_cpu = g.total_cpu
        
        if diagnosis == "BOTTLENECK":
            if primary is None:
                primary = g
            else:
                secondary.append(g)
        elif total_cpu > 10 or diagnosis in ["STORM", "UNBALANCED"]:
            secondary.append(g)
        else:
            background.append(g)
    
    # 构建根因分析
    root_cause = _build_root_cause(primary, secondary, anomalies, core_dist)
    
    return DiagnosisReport(
        primary_suspect=primary,
        secondary_loads=secondary[:3],
        background_noise=background[:5],
        background_count=len(background),
        mutation_detected=anomalies.mutation_detected,
        mutation_time=mutation_time,
        saturated_cores=saturated_cores,
        root_cause_analysis=root_cause
    )


def _build_root_cause(primary: Optional[ProcessGroup], 
                      secondary: list[ProcessGroup],
                      anomalies: AnomaliesReport,
                      core_dist: CoreDistributionReport) -> str:
    """构建根因分析描述"""
    parts: list[str] = []
    
    if primary:
        parts.append(f"主要瓶颈: {primary.comm} ({primary.diagnosis})")
    
    if anomalies.mutation_detected:
        parts.append("检测到性能突变")
    
    if core_dist.saturated_cores:
        cores_str = ', '.join(map(str, core_dist.saturated_cores[:3]))
        parts.append(f"核心饱和: CPU {cores_str}")
    
    if secondary:
        comms = ', '.join(s.comm for s in secondary[:2])
        parts.append(f"次要负载: {comms}")
    
    return "; ".join(parts) if parts else "未检测到明显瓶颈"


def _diagnosis_to_dataclass(d: DiagnosisReport) -> DiagnosisDetails:
    """转换DiagnosisReport为DiagnosisDetails dataclass（用于输出）"""
    primary = None
    if d.primary_suspect:
        primary = PrimarySuspectData(
            comm=d.primary_suspect.comm,
            total_cpu=d.primary_suspect.total_cpu,
            diagnosis=d.primary_suspect.diagnosis,
            monopoly=d.primary_suspect.monopoly
        )
    
    secondary = [
        SecondaryLoadData(comm=g.comm, total_cpu=g.total_cpu, diagnosis=g.diagnosis)
        for g in d.secondary_loads
    ]
    
    return DiagnosisDetails(
        primary_suspect=primary,
        secondary_loads=secondary,
        background_count=d.background_count,
        mutation_detected=d.mutation_detected,
        mutation_time=d.mutation_time,
        saturated_cores=d.saturated_cores,
        root_cause_analysis=d.root_cause_analysis
    )


def _anomalies_to_dataclass(a: AnomaliesReport) -> AnomaliesDetails:
    """转换AnomaliesReport为AnomaliesDetails dataclass"""
    return AnomaliesDetails(
        anomalies_count=len(a.anomalies),
        mutation_detected=a.mutation_detected,
        risks=a.risks
    )


def _core_dist_to_dataclass(c: CoreDistributionReport) -> CoreDistDetails:
    """转换CoreDistributionReport为CoreDistDetails dataclass"""
    return CoreDistDetails(
        core_count=len(c.core_stats),
        saturated_cores=c.saturated_cores,
        imbalance_level=c.imbalance_level,
        risks=c.risks
    )


def _comm_top_to_dataclass(c: CommTopReport) -> CommTopDetails:
    """转换CommTopReport为CommTopDetails dataclass"""
    return CommTopDetails(
        groups_count=len(c.groups),
        folded_count=c.folded_count,
        total_groups=c.total_groups,
        risks=c.risks
    )
