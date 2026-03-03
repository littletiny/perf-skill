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

from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass, field

from .models import RiskItem, TargetDetail
from ..core.output_models import RiskInfo, RiskLevel


# Risk级别优先级（数字越小优先级越高）- 使用 RiskLevel 枚举
PRIORITY = {
    RiskLevel.CRITICAL.to_string(): RiskLevel.CRITICAL.value,
    RiskLevel.WARNING.to_string(): RiskLevel.WARNING.value,
    RiskLevel.INFO.to_string(): RiskLevel.INFO.value,
    RiskLevel.NONE.to_string(): RiskLevel.NONE.value,
}


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
    
    职责：
    1. 收集多个 Analysis 的 risk
    2. 按 target 去重：同一目标的多个 risk，取最高级别
    3. 分级展示：Primary Risk / Secondary Risk / Info
    4. 生成综合的 _risk 输出
    
    使用示例：
        aggregator = RiskAggregator()
        
        # 添加来自不同分析的risk
        for risk in anomalies_report.risks:
            aggregator.add_risk(risk, source="anomalies")
        
        for risk in comm_top_report.risks:
            aggregator.add_risk(risk, source="comm_top")
        
        # 获取聚合结果
        aggregated = aggregator.get_aggregate_risk()
    """
    
    def __init__(self):
        self._risks: List[RiskItem] = []
        self._target_map: Dict[str, RiskItem] = {}  # target -> 最高级别 risk
    
    def add_risk(self, risk: RiskItem, source: str = "") -> None:
        """
        添加单个 risk
        
        Args:
            risk: RiskItem 实例
            source: 来源标识（如 "anomalies", "comm_top"）
        """
        if not risk or not isinstance(risk, RiskItem):
            return
        
        risk.source = source or risk.source
        self._risks.append(risk)
        
        # 按 target 去重，保留最高级别
        targets = risk.pending_targets if risk.pending_targets else []
        
        # 如果没有明确target，使用message作为key
        if not targets:
            key = risk.message or "unknown"
            targets = [key]
        
        for target in targets:
            if target not in self._target_map:
                self._target_map[target] = risk
            else:
                # 比较级别，保留更高的
                current = self._target_map[target]
                if self._level_priority(risk.level) < self._level_priority(current.level):
                    self._target_map[target] = risk
    
    def add_risks(self, risks: List[RiskItem], source: str = "") -> None:
        """
        批量添加 risks
        
        Args:
            risks: RiskItem 列表
            source: 来源标识
        """
        for risk in risks:
            self.add_risk(risk, source)
    
    def get_aggregate_risk(self) -> AggregatedRisk:
        """
        获取聚合后的 Risk
        
        策略：
        1. 按 target 去重，取最高级别
        2. 分级统计 critical/warning/info 数量
        3. 合并 hint，去重
        4. 生成综合 message
        
        Returns:
            AggregatedRisk: 聚合后的 risk 结果
        """
        if not self._target_map:
            return AggregatedRisk(level="none", message="未发现明显风险")
        
        # 分类统计
        critical_targets: List[Tuple[str, RiskItem]] = []
        warning_targets: List[Tuple[str, RiskItem]] = []
        info_targets: List[Tuple[str, RiskItem]] = []
        all_patterns: Set[str] = set()
        
        for target, risk in self._target_map.items():
            all_patterns.update(risk.patterns)
            
            if risk.level == "critical":
                critical_targets.append((target, risk))
            elif risk.level == "warning":
                warning_targets.append((target, risk))
            else:
                info_targets.append((target, risk))
        
        # 构建 target_details
        target_details = []
        for target, risk in critical_targets + warning_targets + info_targets:
            target_details.append(TargetDetail(
                target=target,
                level=risk.level,
                message=risk.message,
                hint=risk.hint
            ))
        
        # 生成综合 risk
        if critical_targets:
            targets_str = ", ".join([t[0] for t in critical_targets[:3]])
            if len(critical_targets) > 3:
                targets_str += f" 等{len(critical_targets)}个"
            
            hints = list(dict.fromkeys([r.hint for _, r in critical_targets if r.hint]))
            
            return AggregatedRisk(
                level="critical",
                message=f"发现 {len(critical_targets)} 个关键性能瓶颈: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(self._target_map.keys()),
                action_required=True,
                critical_count=len(critical_targets),
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=target_details
            )
        
        elif warning_targets:
            targets_str = ", ".join([t[0] for t in warning_targets[:3]])
            if len(warning_targets) > 3:
                targets_str += f" 等{len(warning_targets)}个"
            
            hints = list(dict.fromkeys([r.hint for _, r in warning_targets if r.hint]))
            
            return AggregatedRisk(
                level="warning",
                message=f"发现 {len(warning_targets)} 个潜在风险: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(self._target_map.keys()),
                action_required=True,
                critical_count=0,
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=target_details
            )
        
        elif info_targets:
            return AggregatedRisk(
                level="info",
                message=f"发现 {len(info_targets)} 个提示信息",
                hint="",
                patterns=list(all_patterns),
                pending_targets=[],
                action_required=False,
                critical_count=0,
                warning_count=0,
                info_count=len(info_targets),
                target_details=target_details
            )
        
        return AggregatedRisk(level="none", message="未发现明显风险")
    
    # 别名方法，兼容 aggregate() 调用
    def aggregate(self) -> AggregatedRisk:
        """别名方法，同 get_aggregate_risk()"""
        return self.get_aggregate_risk()
    
    def get_all_patterns(self) -> List[str]:
        """
        获取所有检测到的 patterns（SHECR Attention Flags）
        
        Returns:
            List[str]: Pattern 列表，如 ["SINGLE_CORE_SATURATION", "HIGH_KERNEL"]
        """
        patterns: Set[str] = set()
        for risk in self._risks:
            patterns.update(risk.patterns)
        return list(patterns)
    
    def get_pending_targets(self) -> List[str]:
        """
        获取所有待追踪目标
        
        Returns:
            List[str]: 目标列表（通常是进程名或符号名）
        """
        return list(self._target_map.keys())
    
    def clear(self) -> None:
        """清空所有 risks"""
        self._risks = []
        self._target_map = {}
    
    def _level_priority(self, level: str) -> int:
        """获取风险级别优先级（数字越小优先级越高）"""
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        return priority.get(level.lower(), 4)
    
    # 属性访问器，兼容旧代码
    @property
    def risks(self) -> List[RiskItem]:
        """获取所有添加的 risks"""
        return self._risks


def merge_risk_lists(risk_lists: List[List[RiskItem]], 
                     sources: Optional[List[str]] = None) -> AggregatedRisk:
    """
    便捷函数：合并多个 risk 列表
    
    Args:
        risk_lists: 多个 risk 列表，如 [anomaly_risks, core_dist_risks, comm_top_risks]
        sources: 可选，每个列表的来源标识
        
    Returns:
        AggregatedRisk: 聚合后的 risk
        
    示例：
        aggregated = merge_risk_lists(
            [anomalies_risks, comm_top_risks],
            sources=["anomalies", "comm_top"]
        )
    """
    aggregator = RiskAggregator()
    for i, risks in enumerate(risk_lists):
        source = sources[i] if sources and i < len(sources) else ""
        aggregator.add_risks(risks, source)
    return aggregator.get_aggregate_risk()
