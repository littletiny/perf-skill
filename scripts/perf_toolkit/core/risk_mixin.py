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


class RiskMixin:
    """Mixin for standardized risk hints in output"""
    
    RISK_LEVELS = ["critical", "warning", "info", "none"]
    
    # Risk level priority for comparison
    PRIORITY = {"critical": 0, "warning": 1, "info": 2, "none": 3}
    
    def __init__(self):
        self.risks = []
    
    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: List[str] = None, targets: List[str] = None):
        """
        Add a risk hint.
        
        Args:
            level: Risk level - critical/warning/info/none
            message: One-sentence risk description
            hint: Recommended next action (executable command)
            patterns: List of detected pattern names
            targets: List of pending targets to process
        """
        if level not in self.RISK_LEVELS:
            level = "info"
        
        self.risks.append({
            "level": level,
            "message": message,
            "hint": hint,
            "patterns": patterns or [],
            "pending_targets": targets or []
        })
    
    def get_top_risk(self) -> Dict:
        """
        Get the highest level risk.
        
        Returns:
            Risk dict with action_required flag
        """
        if not self.risks:
            return {
                "level": "none",
                "message": "无风险",
                "hint": "",
                "patterns": [],
                "pending_targets": [],
                "action_required": False
            }
        
        # Find highest priority (lowest number) risk
        top = min(self.risks, key=lambda r: self.PRIORITY.get(r["level"], 3))
        
        return {
            **top,
            "action_required": top["level"] in ["critical", "warning"]
        }
    
    def format_output(self, data: Dict) -> Dict:
        """
        Add _risk field to output data.
        
        Args:
            data: Output data dict
            
        Returns:
            Data with _risk field prepended
        """
        return {
            "_risk": self.get_top_risk(),
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
