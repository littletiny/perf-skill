#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comm Top - Get top N comm groups by aggregated CPU utilization

V3 版本（三层架构）：
- 提取 CommTopAnalyzer 纯逻辑类
- 支持 CV（变异系数）、Monopoly（独占率）、SpawnRate（产生速率）计算
- 自动降噪，区分"值得关注"和"背景噪音"
- 危害指数排序，解决"A掩盖B"问题
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from .base import BaseAnalyzer
from .models import Risk, CommGroup


class CommTopAnalyzer(BaseAnalyzer):
    """
    CommTop 分析器 - 进程组 CPU 分析（增强版）
    
    新增指标:
    - CV (变异系数): 检测负载不均衡
    - Monopoly (独占率): 识别单进程瓶颈
    - SpawnRate (产生速率): 检测进程风暴
    - Impact Score (危害指数): 综合排序依据
    """
    
    # 诊断分级阈值
    CV_THRESHOLD = 1.0              # CV > 1.0 认为不均衡
    MONOPOLY_THRESHOLD = 0.8        # Monopoly > 0.8 认为单点瓶颈
    SPAWN_RATE_THRESHOLD = 10.0     # > 10/s 认为进程风暴
    
    # 显著性判断阈值（用于自动降噪）
    SIGNIFICANT_CPU_THRESHOLD = 5.0     # CPU% > 5 认为显著
    SIGNIFICANT_CV_THRESHOLD = 1.0      # CV > 1.0 认为显著
    SIGNIFICANT_MONOPOLY_THRESHOLD = 0.8 # Monopoly > 0.8 认为显著
    SIGNIFICANT_SPAWN_RATE_THRESHOLD = 10.0 # SpawnRate > 10/s 认为显著
    
    def analyze(self, samples: List[Dict], top_n: int = 10,
                include_metrics: bool = False) -> Dict[str, Any]:
        """
        分析进程组 CPU 利用率
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间指标（Composite 使用）
            
        Returns:
            {
                "result": {"groups": [...], "folded_count": N, "total_groups": N},
                "risks": [...],
                "metrics": {...}  # if include_metrics
            }
        """
        if not samples:
            return {
                "result": {"groups": [], "folded_count": 0, "total_groups": 0, "storm_analysis": None},
                "risks": [],
                "metrics": {} if include_metrics else None
            }
        
        # 1. 从 engine 获取数据
        comm_util = self._engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标
        groups: List[CommGroup] = []
        risks: List[Risk] = []
        
        for comm, info in comm_util.items():
            # 获取 PID 级分布用于计算 CV 和 Monopoly
            pid_dist = self._engine.get_pid_cpu_distribution(samples, comm)
            cv = self._calculate_cv(pid_dist)
            monopoly = self._calculate_monopoly(pid_dist)
            
            # 获取生命周期信息
            lifecycle = self._engine.get_process_lifecycle(samples, comm)
            spawn_rate = lifecycle.spawn_rate
            
            # 诊断分级
            diagnosis = self._classify(cv, monopoly, spawn_rate)
            
            # 计算危害指数
            impact_score = self._calculate_impact_score(
                info.total_pct, cv, monopoly, spawn_rate
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
        
        # 3. 按危害指数排序
        groups.sort(key=lambda x: x.impact_score, reverse=True)
        
        # 4. 自动降噪：区分"值得关注"和"背景噪音"
        display_groups, folded_groups = self._auto_filter(groups)
        
        # 5. Storm 详细分析（对所有 STORM 诊断的进程）
        storm_analysis = self._analyze_storms(samples, groups)
        
        result = {
            "result": {
                "groups": [g.to_dict() for g in display_groups[:top_n]],
                "folded_count": len(folded_groups),
                "total_groups": len(groups),
                "storm_analysis": storm_analysis
            },
            "risks": [r.to_dict() for r in risks]
        }
        
        if include_metrics:
            result["metrics"] = {
                "cv_map": {g.comm: g.cv for g in groups},
                "monopoly_map": {g.comm: g.monopoly for g in groups},
                "spawn_rate_map": {g.comm: g.spawn_rate for g in groups},
                "impact_score_map": {g.comm: g.impact_score for g in groups},
                "folded_groups": [g.to_dict() for g in folded_groups],
                "all_groups": [g.to_dict() for g in groups],
                "storm_analysis": storm_analysis
            }
        
        return result
    
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
    
    def _classify(self, cv: float, monopoly: float, spawn_rate: float) -> str:
        """
        诊断分级
        
        Returns:
            BOTTLENECK: 单进程瓶颈（Monopoly 高）
            STORM: 进程风暴（SpawnRate 高）
            UNBALANCED: 负载不均衡（CV 高）
            HEALTHY: 健康状态
        """
        if monopoly > self.MONOPOLY_THRESHOLD:
            return "BOTTLENECK"
        elif spawn_rate > self.SPAWN_RATE_THRESHOLD:
            return "STORM"
        elif cv > self.CV_THRESHOLD:
            return "UNBALANCED"
        else:
            return "HEALTHY"
    
    def _calculate_impact_score(self, total_cpu: float, cv: float, 
                                 monopoly: float, spawn_rate: float) -> float:
        """
        计算危害指数 (Impact Score)
        
        公式: CPU*0.3 + CV*40 + Monopoly*50 + SpawnRate*5
        
        用于综合排序，解决"A掩盖B"问题：
        - 单纯 CPU 高不一定是瓶颈（可能是背景负载）
        - CV 高、Monopoly 高才是真正的瓶颈信号
        """
        return (
            total_cpu * 0.3 +
            cv * 40 +
            monopoly * 50 +
            spawn_rate * 5
        )
    
    def _identify_risk(self, group: CommGroup) -> Optional[Risk]:
        """
        根据诊断分级识别 risk
        
        Returns:
            Risk 对象 或 None
        """
        if group.diagnosis == "BOTTLENECK":
            return self._create_risk(
                level="critical",
                message=f"{group.comm} 单核饱和 (Monopoly={group.monopoly:.2f})",
                hint=f"bottleneck-trace --comm {group.comm}",
                patterns=["SINGLE_CORE_SATURATION"],
                pending_targets=[group.comm]
            )
        elif group.diagnosis == "STORM":
            return self._create_risk(
                level="warning",
                message=f"{group.comm} 进程风暴 ({group.spawn_rate:.1f}/s)",
                hint=f"find-callers --comm {group.comm} 查看创建源头",
                patterns=["PROCESS_STORM"],
                pending_targets=[group.comm]
            )
        elif group.diagnosis == "UNBALANCED":
            return self._create_risk(
                level="warning",
                message=f"{group.comm} 负载不均衡 (CV={group.cv:.2f})",
                hint=f"get-hotspots --comm {group.comm}",
                patterns=["UNBALANCED_LOAD"],
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
        display: List[CommGroup] = []
        folded: List[CommGroup] = []
        
        for g in groups:
            is_significant = (
                g.total_cpu > self.SIGNIFICANT_CPU_THRESHOLD or
                g.cv > self.SIGNIFICANT_CV_THRESHOLD or
                g.monopoly > self.SIGNIFICANT_MONOPOLY_THRESHOLD or
                g.spawn_rate > self.SIGNIFICANT_SPAWN_RATE_THRESHOLD
            )
            
            if is_significant:
                display.append(g)
            else:
                folded.append(g)
        
        return display, folded
    
    def _analyze_storms(self, samples: List[Dict], groups: List[CommGroup]) -> Optional[Dict]:
        """
        分析所有 STORM 诊断的进程组的详细信息
        
        Returns:
            {
                "storm_groups": [
                    {
                        "comm": str,
                        "spawn_rate": float,
                        "pid_count": int,
                        "severity": str,  # CRITICAL/HIGH/MEDIUM/LOW
                        "top_creators": [{"symbol": str, "count": int}],
                        "short_lived_count": int,
                        "leaked_count": int
                    }
                ],
                "total_storm_comms": int,
                "max_spawn_rate": float
            }
            或 None（如果没有风暴）
        """
        storm_groups = [g for g in groups if g.diagnosis == "STORM"]
        
        if not storm_groups:
            return None
        
        # 按 spawn_rate 排序
        storm_groups.sort(key=lambda x: x.spawn_rate, reverse=True)
        
        storm_details = []
        max_spawn_rate = 0.0
        
        for group in storm_groups:
            max_spawn_rate = max(max_spawn_rate, group.spawn_rate)
            
            # 严重程度分级
            severity = "LOW"
            if group.spawn_rate > 100:
                severity = "CRITICAL"
            elif group.spawn_rate > 50:
                severity = "HIGH"
            elif group.spawn_rate > 20:
                severity = "MEDIUM"
            
            # 获取生命周期信息（创建热点分析）
            lifecycle = self._engine.get_process_lifecycle(samples, group.comm)
            
            # 分析创建热点（哪些函数在创建进程）
            creator_symbols: Dict[str, int] = defaultdict(int)
            for event in lifecycle.spawn_events:
                if hasattr(event, 'stack') and event.stack:
                    stack = event.stack
                elif isinstance(event, dict):
                    stack = event.get("stack", [])
                else:
                    stack = []
                
                if stack:
                    creator_symbols[stack[0]] += 1
            
            top_creators = [
                {"symbol": s, "count": c}
                for s, c in sorted(creator_symbols.items(), key=lambda x: x[1], reverse=True)[:3]
            ]
            
            # 生命周期统计
            spawn_count = len(lifecycle.spawn_events)
            exit_count = len(lifecycle.exit_events)
            leaked = max(0, spawn_count - exit_count)
            
            # 短生命周期估计（从 lifecycle_stats 获取）
            short_lived = getattr(lifecycle.lifecycle_stats, 'short_lived_count', 0)
            
            storm_details.append({
                "comm": group.comm,
                "spawn_rate": group.spawn_rate,
                "pid_count": group.pid_count,
                "total_cpu": group.total_cpu,
                "severity": severity,
                "top_creators": top_creators,
                "short_lived_count": short_lived,
                "leaked_count": leaked
            })
        
        return {
            "storm_groups": storm_details,
            "total_storm_comms": len(storm_groups),
            "max_spawn_rate": max_spawn_rate
        }


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, CommGroupItem, CommGroupSummary, CommTopOutput, TimeRange
)


@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """[Skill] Get top N comm groups by aggregated CPU utilization"""
    
    # 1. 调用 Analyzer（内部接口，不触发 Trace）
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(
        samples, 
        top_n=getattr(args, 'top_n', 10),
        include_metrics=False
    )
    
    # 2. 记录所有 risks 到 Trace（CLI 层负责）
    for risk_dict in result["risks"]:
        builder.record_risk(
            risk_dict["level"],
            risk_dict["message"],
            risk_dict["hint"]
        )
    
    # 3. 取最高级别 risk 放入 _risk 字段
    top_risk = None
    if result["risks"]:
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top_risk = min(result["risks"], key=lambda r: priority.get(r["level"], 3))
    
    # 4. 转换为 Output 模型
    groups = []
    for g in result["result"]["groups"]:
        kernel_ratio = (g["kernel_cpu"] / g["total_cpu"] * 100) if g["total_cpu"] > 0 else 0
        
        # 构建 event 描述
        if g["diagnosis"] == "BOTTLENECK":
            event = f"BOTTLENECK(M={g['monopoly']:.2f})"
        elif g["diagnosis"] == "STORM":
            event = f"STORM({g['spawn_rate']:.1f}/s)"
        elif g["diagnosis"] == "UNBALANCED":
            event = f"UNBALANCED(CV={g['cv']:.2f})"
        else:
            event = "normal"
        
        groups.append(CommGroupItem.from_stats(
            comm=g["comm"],
            pid_count=g["pid_count"],
            aggregate_cpu=g["total_cpu"],
            kernel_ratio=kernel_ratio,
            event_desc=event
        ))
    
    risk_output = create_risk_info(**top_risk) if top_risk else create_risk_info(level="none")
    
    output = CommTopOutput(
        _risk=risk_output,
        comm_groups=groups,
        summary=CommGroupSummary(
            total_comm_groups=result["result"]["total_groups"],
            high_kernel_groups=len([r for r in result["risks"] if "HIGH_KERNEL" in str(r.get("patterns", []))])
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].get('ts') if samples else None,
            samples[-1].get('ts') if len(samples) > 1 else None
        )
    )
    
    return output
