#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

V3 版本（三层架构）：
- 提取 CommTopAnalyzer 纯逻辑类
- 支持 CV（变异系数）、Monopoly（独占率）、SpawnRate（产生速率）计算
- 自动降噪，区分"值得关注"和"背景噪音"
- 危害指数排序，解决"A掩盖B"问题
- Task-2.3.1: 返回 CommTopResult dataclass

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import (
    DiagnosisType, RiskPattern, Thresholds, CompositeDefaults
)

from .base import BaseAnalyzer
from ..core.engine_types import Sample
from ..core.models import RiskInfo
from ..core.config_loader import get_config, get_analysis_thresholds
from .models import CommGroup, CommTopResult


class CommTopAnalyzer(BaseAnalyzer):
    """
    CommTop 分析器 - 进程组 CPU 分析（增强版）
    
    新增指标:
    - CV (变异系数): 检测负载不均衡
    - Monopoly (独占率): 识别单进程瓶颈
    - SpawnRate (产生速率): 检测进程风暴
    - Impact Score (危害指数): 综合排序依据
    """
    
    def analyze(self, samples: List[Sample], top_n: int = 10,
                include_metrics: bool = False) -> CommTopResult:
        """
        分析进程组 CPU 利用率
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间指标（Composite 使用）
            
        Returns:
            CommTopResult dataclass
        """
        # 获取分析阈值配置
        thresholds = get_analysis_thresholds()
        
        if not samples:
            result = CommTopResult(
                groups=[],
                folded_count=0,
                total_groups=0,
                risks=[],
                metrics={} if include_metrics else None
            )
            return result
        
        # 1. 从 engine 获取数据
        comm_util = self._engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标
        groups: List[CommGroup] = []
        risks: List[RiskInfo] = []
        
        for comm, info in comm_util.items():
            # 获取 PID 级分布用于计算 CV 和 Monopoly
            pid_dist = self._engine.get_pid_cpu_distribution(samples, comm)
            cv = self._calculate_cv(pid_dist)
            monopoly = self._calculate_monopoly(pid_dist)
            
            # 获取生命周期信息
            lifecycle = self._engine.get_process_lifecycle(samples, comm)
            spawn_rate = lifecycle.spawn_rate
            
            # 诊断分级
            diagnosis = self._classify(comm, info.total_pct, info.kernel_pct, cv, monopoly, spawn_rate)
            
            # 计算危害指数
            impact_score = self._calculate_impact_score(
                info.total_pct, info.kernel_pct, cv, monopoly, spawn_rate, diagnosis
            )
            
            group = CommGroup(
                comm=comm,
                total_cpu=info.total_pct,
                kernel_cpu=info.kernel_pct,
                user_cpu=info.user_pct,
                pid_count=info.pid_count,
                pids=info.pids,
                cv=cv,
                monopoly=monopoly,
                spawn_rate=spawn_rate,
                diagnosis=diagnosis,
                impact_score=impact_score
            )
            groups.append(group)
            
            # 识别 risk
            risk = self._identify_risk(group)
            if risk:
                risks.append(risk)
        
        # 3. 按危害指数排序（综合排序）
        groups.sort(key=lambda x: x.impact_score, reverse=True)
        
        # 3.1 按 total_cpu 排序（独立视图）
        groups_by_total = sorted(groups, key=lambda x: x.total_cpu, reverse=True)
        
        # 3.2 按 kernel_cpu 排序（独立视图，用于发现高 sys 的进程）
        groups_by_sys = sorted(groups, key=lambda x: x.kernel_cpu, reverse=True)
        
        # 4. 自动降噪：区分"值得关注"和"背景噪音"
        display_groups, folded_groups = self._auto_filter(groups)
        
        # 构建 metrics
        metrics = None
        if include_metrics:
            from ..composite.models import CommTopMetrics, ProcessGroup as PG
            metrics = CommTopMetrics(
                cv_map={g.comm: g.cv for g in groups},
                monopoly_map={g.comm: g.monopoly for g in groups},
                spawn_rate_map={g.comm: g.spawn_rate for g in groups},
                impact_score_map={g.comm: g.impact_score for g in groups},
                folded_groups=[
                    PG(
                        comm=g.comm,
                        total_cpu=g.total_cpu,
                        kernel_cpu=g.kernel_cpu,
                        user_cpu=g.user_cpu,
                        pid_count=g.pid_count,
                        pids=list(g.pids) if g.pids else [],
                        cv=g.cv,
                                    monopoly=g.monopoly,
                        spawn_rate=g.spawn_rate,
                        diagnosis=g.diagnosis,
                        impact_score=g.impact_score
                    )
                    for g in folded_groups
                ],
                all_groups=[
                    PG(
                        comm=g.comm,
                        total_cpu=g.total_cpu,
                        kernel_cpu=g.kernel_cpu,
                        user_cpu=g.user_cpu,
                        pid_count=g.pid_count,
                        pids=list(g.pids) if g.pids else [],
                        cv=g.cv,
                        monopoly=g.monopoly,
                        spawn_rate=g.spawn_rate,
                        diagnosis=g.diagnosis,
                        impact_score=g.impact_score
                    )
                    for g in groups
                ]
            )
        
        return CommTopResult(
            groups=display_groups[:top_n],
            folded_count=len(folded_groups),
            total_groups=len(groups),
            risks=risks,
            metrics=metrics,
            groups_by_total_cpu=groups_by_total[:top_n],
            groups_by_sys_cpu=groups_by_sys[:top_n]
        )
    
    def _calculate_cv(self, pid_dist: Dict[int, float]) -> float:
        """
        计算变异系数 (Coefficient of Variation)
        
        CV = σ / μ
        用于检测 PID 间的负载不均衡程度
        """
        values = list(pid_dist.values())
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        return std_dev / mean
    
    def _calculate_monopoly(self, pid_dist: Dict[int, float]) -> float:
        """
        计算核心独占率 (Monopoly Ratio)
        
        Monopoly = max(PID_cpu) / sum(all_PID_cpu)
        用于识别单进程是否垄断该 comm 的 CPU 资源
        """
        if not pid_dist:
            return 0.0
        
        total = sum(pid_dist.values())
        if total == 0:
            return 0.0
        
        max_pid_cpu = max(pid_dist.values())
        return max_pid_cpu / total
    
    def _classify(self, comm: str, total_cpu: float, kernel_cpu: float,
                  cv: float, monopoly: float, spawn_rate: float) -> str:
        """
        诊断分级
        
        BOTTLENECK 判定（基于配置）：
        1. total_cpu > sensitive 且 kernel_ratio > sys_high
        2. total_cpu >= limit
        
        Returns:
            BOTTLENECK: 达到配置阈值
            UNBALANCED: 负载不均衡（CV 高）
            HEALTHY: 健康状态
        """
        config = get_config()
        thresholds = get_analysis_thresholds()
        
        # 基于配置的 BOTTLENECK 判定
        if config.is_bottleneck(comm, total_cpu, kernel_cpu):
            return DiagnosisType.BOTTLENECK
        elif cv > thresholds.cv_unbalanced:
            return DiagnosisType.UNBALANCED
        else:
            return DiagnosisType.HEALTHY
    
    def _calculate_impact_score(self, total_cpu: float, kernel_cpu: float,
                                 cv: float, monopoly: float, spawn_rate: float,
                                 diagnosis: str) -> float:
        """
        计算危害指数 (Impact Score)
        
        新公式:
        - BOTTLENECK 基础分: +100
        - UNBALANCED 基础分: +20
        - 加上: total*0.5 + kernel*0.8 + cv*10 + monopoly*5 + spawn_rate*0.5
        
        调整思路:
        1. 降低基础分差距，避免分类过于绝对
        2. 大幅提高 kernel_cpu 权重 (0.8)，sys 问题更突出
        3. 降低 Monopoly 权重 (5→)，规则驱动，排序不过度强调
        4. 降低 Spawn_rate 权重 (0.5)，风暴通常伴随 sys 问题
        5. 降低 CV 权重 (10)，负载均衡问题优先级降低
        """
        # 基础分：缩小差距
        base_score = 0
        if diagnosis == DiagnosisType.BOTTLENECK:
            base_score = 100
        elif diagnosis == DiagnosisType.UNBALANCED:
            base_score = 20
        
        # 计算分项得分
        return base_score + (
            total_cpu * 0.5 +
            kernel_cpu * 0.8 +      # 大幅提高 sys 权重
            cv * 10 +
            monopoly * 5 +          # 大幅降低，规则驱动
            spawn_rate * 0.5        # 大幅降低，风暴看 sys
        )
    
    def _identify_risk(self, group: CommGroup) -> Optional[RiskInfo]:
        """
        根据诊断分级识别 risk

        Returns:
            RiskInfo 对象 或 None
        """
        if group.diagnosis == DiagnosisType.BOTTLENECK:
            return self._create_risk(
                level="critical",
                message=f"{group.comm} reached bottleneck threshold (CPU={group.total_cpu:.1f}%, Sys={group.kernel_cpu:.1f}%)",
                hint=f"bottleneck-analyze --comm {group.comm}",
                patterns=[RiskPattern.SINGLE_CORE_SATURATION],
                pending_targets=[group.comm]
            )
        elif group.diagnosis == DiagnosisType.UNBALANCED:
            return self._create_risk(
                level="warning",
                message=f"{group.comm} unbalanced load (CV={group.cv:.2f})",
                hint=f"get-hotspots --comm {group.comm}",
                patterns=[RiskPattern.UNBALANCED_LOAD],
                pending_targets=[group.comm]
            )
        return None
    
    def _auto_filter(self, groups: List[CommGroup]) -> Tuple[List[CommGroup], List[CommGroup]]:
        """
        自动降噪，区分"值得关注"和"背景噪音"
        
        判断标准（满足任一即认为显著）：
        1. CPU 总量 > 5%
        2. CV > 1.0（分布严重不均）
        3. Monopoly > 0.8（单点极端离群）
        4. SpawnRate > 10/s（进程风暴）
        
        Returns:
            (display_groups, folded_groups)
        """
        thresholds = get_analysis_thresholds()
        
        display: List[CommGroup] = []
        folded: List[CommGroup] = []
        
        for g in groups:
            is_significant = (
                g.total_cpu > thresholds.cpu_util_low or
                g.cv > thresholds.cv_unbalanced or
                g.monopoly > thresholds.monopoly_high
            )
            
            if is_significant:
                display.append(g)
            else:
                folded.append(g)
        
        return display, folded
