#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Risk Aggregator - Composite层Risk聚合与分级

职责:
1. 收集多个Analysis的risk
2. 按target去重：同一目标的多个risk，取最高级别
3. 分级展示：Primary Risk / Secondary Risk / Info
4. 生成综合的_risk输出

遵循 output-format-spec.md 规范:
- 扁平结构，嵌套不超过2层
- 风险置顶，包含 _risk 字段
"""

from typing import List, Optional
from dataclasses import dataclass, field

from .models import RiskItem, TargetDetail
from ..core.output_models import RiskInfo


# Risk级别优先级（数字越小优先级越高）
PRIORITY = {"critical": 0, "warning": 1, "info": 2, "none": 3}


@dataclass
class AggregatedRisk:
    """聚合后的Risk结构"""
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False
    
    # 详细分解（用于Composite展示）
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    target_details: List[TargetDetail] = field(default_factory=list)

    def __post_init__(self):
        self.action_required = self.level in ["critical", "warning"]
    
    def to_risk_info(self) -> RiskInfo:
        """
        转换为RiskInfo dataclass（用于output_models）
        
        Returns:
            RiskInfo: 标准风险信息结构
        """
        return RiskInfo(
            level=self.level,
            message=self.message,
            hint=self.hint,
            patterns=self.patterns,
            pending_targets=self.pending_targets,
            action_required=self.action_required
        )


class RiskAggregator:
    """
    Risk聚合器
    
    使用方式:
        aggregator = RiskAggregator()
        
        # 添加来自不同分析的risk
        for risk in analysis_result.get("risks", []):
            aggregator.add_risk(RiskItem.from_dict(risk))
        
        # 获取聚合结果
        aggregated = aggregator.aggregate()
    """
    
    def __init__(self):
        self.risks: List[RiskItem] = []
    
    def add_risk(self, risk: RiskItem):
        """
        添加单个risk
        
        Args:
            risk: RiskItem 实例
        """
        if not risk or not isinstance(risk, RiskItem):
            return
        
        self.risks.append(risk)
    
    def add_risks(self, risks: List[RiskItem]):
        """批量添加risks"""
        for risk in risks:
            self.add_risk(risk)
    
    def aggregate(self) -> AggregatedRisk:
        """
        执行Risk聚合
        
        策略:
        1. 按target去重：同一目标的多个risk，取最高级别
        2. 分级统计：critical/warning/info数量
        3. 合并hint：多条hint用分号分隔
        4. 生成综合message
        
        Returns:
            AggregatedRisk: 聚合后的risk结果
        """
        if not self.risks:
            return AggregatedRisk(level="none", message="未发现明显风险")
        
        # 按target去重，取最高级别
        target_risks: dict[str, RiskItem] = {}
        
        for risk in self.risks:
            targets = risk.pending_targets if risk.pending_targets else []
            
            # 如果没有明确target，使用message作为key
            if not targets:
                key = risk.message or "unknown"
                targets = [key]
            
            for target in targets:
                if target not in target_risks:
                    target_risks[target] = risk
                elif PRIORITY[risk.level] < PRIORITY[target_risks[target].level]:
                    target_risks[target] = risk
        
        # 分类统计
        critical_targets: list[tuple[str, RiskItem, TargetDetail]] = []
        warning_targets: list[tuple[str, RiskItem, TargetDetail]] = []
        info_targets: list[tuple[str, RiskItem, TargetDetail]] = []
        all_patterns: set[str] = set()
        
        for target, risk in target_risks.items():
            all_patterns.update(risk.patterns)
            
            detail = TargetDetail(
                target=target,
                level=risk.level,
                message=risk.message,
                hint=risk.hint
            )
            
            if risk.level == "critical":
                critical_targets.append((target, risk, detail))
            elif risk.level == "warning":
                warning_targets.append((target, risk, detail))
            else:
                info_targets.append((target, risk, detail))
        
        # 生成综合risk
        if critical_targets:
            # 有关键风险
            targets_str = ", ".join([t[0] for t in critical_targets[:3]])
            if len(critical_targets) > 3:
                targets_str += f" 等{len(critical_targets)}个"
            
            hints: list[str] = []
            for _, risk, _ in critical_targets:
                if risk.hint and risk.hint not in hints:
                    hints.append(risk.hint)
            
            return AggregatedRisk(
                level="critical",
                message=f"发现 {len(critical_targets)} 个关键性能瓶颈: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(target_risks.keys()),
                critical_count=len(critical_targets),
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=[d for _, _, d in critical_targets + warning_targets + info_targets]
            )
        
        elif warning_targets:
            # 有警告风险
            targets_str = ", ".join([t[0] for t in warning_targets[:3]])
            if len(warning_targets) > 3:
                targets_str += f" 等{len(warning_targets)}个"
            
            hints: list[str] = []
            for _, risk, _ in warning_targets:
                if risk.hint and risk.hint not in hints:
                    hints.append(risk.hint)
            
            return AggregatedRisk(
                level="warning",
                message=f"发现 {len(warning_targets)} 个潜在风险: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(target_risks.keys()),
                critical_count=0,
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=[d for _, _, d in warning_targets + info_targets]
            )
        
        elif info_targets:
            # 只有info级别
            return AggregatedRisk(
                level="info",
                message=f"发现 {len(info_targets)} 个提示信息",
                hint="",
                patterns=list(all_patterns),
                pending_targets=[],
                critical_count=0,
                warning_count=0,
                info_count=len(info_targets),
                target_details=[d for _, _, d in info_targets]
            )
        
        else:
            return AggregatedRisk(level="none", message="未发现明显风险")
    
    def clear(self):
        """清空所有risks"""
        self.risks = []


def merge_risk_lists(risk_lists: List[List[RiskItem]]) -> AggregatedRisk:
    """
    便捷函数：合并多个risk列表
    
    Args:
        risk_lists: 多个risk列表，如 [anomaly_risks, core_dist_risks, comm_top_risks]
    
    Returns:
        AggregatedRisk: 聚合后的risk
    """
    aggregator = RiskAggregator()
    for risks in risk_lists:
        if risks:
            aggregator.add_risks(risks)
    return aggregator.aggregate()
