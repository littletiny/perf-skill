#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiskMixin - Standardized risk hints for tool output

遵循 output-format-spec.md 规范：
- 所有输出必须包含 _risk 字段
- _risk 放在输出顶部，第一时间可见
- 风险信息简洁明确，包含建议操作
"""

from typing import List, Dict, Optional
from .output_models import RiskInfo


class RiskMixin:
    """Mixin for standardized risk hints in output"""

    RISK_LEVELS = ["critical", "warning", "info", "none"]

    # Risk level priority for comparison
    PRIORITY = {"critical": 0, "warning": 1, "info": 2, "none": 3}

    def __init__(self):
        self.risks: List[RiskInfo] = []

    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: List[str] = None, targets: List[str] = None):
        """
        Add a risk hint.

        Args:
            level: Risk level - critical/warning/info/none
            message: One-sentence risk description
            hint: **强制性**下一步操作命令，必须严格执行。该 hint 是诊断工作流的关键步骤，
                  用于对 pending_targets 中的每个目标执行深入分析。不得跳过、不得忽略。
            patterns: List of detected pattern names
            targets: **必须处理的目标列表**。hint 中指定的操作必须逐个应用于这些目标，
                     确保每个 pending target 都得到后续分析和处理。
        """
        if level not in self.RISK_LEVELS:
            level = "info"

        self.risks.append(RiskInfo(
            level=level,
            message=message,
            hint=hint,
            patterns=patterns or [],
            pending_targets=targets or []
        ))

    def get_top_risk(self) -> RiskInfo:
        """
        Get the highest level risk.

        Returns:
            RiskInfo dataclass with action_required flag
        """
        if not self.risks:
            return RiskInfo(
                level="none",
                message="无风险",
                hint="",
                patterns=[],
                pending_targets=[],
                action_required=False
            )

        # Find highest priority (lowest number) risk
        top = min(self.risks, key=lambda r: self.PRIORITY.get(r.level, 3))
        return top

    def get_all_risks(self) -> List[RiskInfo]:
        """
        Get all recorded risks.

        Returns:
            List of RiskInfo dataclasses, each with action_required flag
        """
        return self.risks

    def format_output(self, data: Dict) -> Dict:
        """
        Add _risk field to output data.

        Args:
            data: Output data dict

        Returns:
            Data with _risk field prepended
        """
        from dataclasses import asdict
        return {
            "_risk": asdict(self.get_top_risk()),
            **data
        }

    def clear_risks(self):
        """Clear all recorded risks"""
        self.risks = []


class RiskAwareOutput:
    """
    Helper class for building risk-aware output.

    Usage:
        output = RiskAwareOutput()
        output.add_risk("warning", "发现高内核态进程", "cluster-symbols --comm xxx")
        result = output.build({"data": "..."})
    """

    def __init__(self):
        self._risk_mixin = RiskMixin()

    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: List[str] = None, targets: List[str] = None):
        """Add a risk hint"""
        self._risk_mixin.add_risk(level, message, hint, patterns, targets)
        return self

    def build(self, data: Dict) -> Dict:
        """Build final output with _risk field"""
        return self._risk_mixin.format_output(data)
