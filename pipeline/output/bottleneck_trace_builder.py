#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BottleneckTraceOutputBuilder - bottleneck-trace 输出格式化

基于工具设计文档实现四个输出段：
- [ENTITY_DISTRIBUTION_MATRIX]: 实体分布矩阵（Markdown表格）
- [CONVERGENCE_TRACE]: 收敛追踪（调用路径聚类）
- [CORRELATION_FLAGS]: 关联标志（跨维度检测）
- [DATA_SUMMARY]: 数据摘要（YAML格式）

不使用 regex，输出格式 AI 友好。
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from perf_toolkit.core.models import RiskInfo, TimeRange


@dataclass
class EntityDistribution:
    """实体分布矩阵行"""
    comm: str
    count: int
    incl_saliency: float
    excl_saliency: float
    core_affinity: str
    throttle_rate: float


@dataclass
class CallPathCluster:
    """调用路径聚类"""
    cluster_id: str
    comm: str
    weight: float
    path: List[str]
    hotspot: str
    characteristic: str


@dataclass
class CorrelationFlag:
    """关联标志"""
    flag_type: str
    target: str
    message: str
    severity: str


@dataclass
class BottleneckTraceResult:
    """bottleneck-trace 完整输出"""
    _risk: RiskInfo
    entity_distribution: List[EntityDistribution]
    common_hotspot: str
    common_hotspot_weight: float
    clusters: List[CallPathCluster]
    correlation_flags: List[CorrelationFlag]
    total_pids: int
    total_sys_cpu: float
    top_bottlenecks: List[str]
    duration_sec: float
    sample_count: int
    time_range: TimeRange


class BottleneckTraceOutputBuilder:
    """
    bottleneck-trace 输出构建器
    
    职责：
    1. 将 BottleneckTraceResult 转换为 Markdown 格式输出
    2. 生成四个标准输出段
    3. 支持 severity 样式标注
    
    使用示例：
        result = BottleneckTraceResult(...)
        builder = BottleneckTraceOutputBuilder(result)
        output = builder.build()
        print(output)
    """
    
    # Severity 图标映射
    SEVERITY_ICONS = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🟢",
    }
    
    def __init__(self, result: BottleneckTraceResult):
        """
        初始化构建器
        
        Args:
            result: BottleneckTraceResult 数据对象
        """
        self._result = result
        self._lines: List[str] = []
    
    def build(self) -> str:
        """
        构建完整输出
        
        Returns:
            格式化的 Markdown 字符串
        """
        self._lines = []
        
        self._build_entity_distribution()
        self._build_convergence_trace()
        self._build_correlation_flags()
        self._build_data_summary()
        
        return "\n".join(self._lines)
    
    def _build_entity_distribution(self):
        """构建 [ENTITY_DISTRIBUTION_MATRIX] 段"""
        self._lines.append("## [ENTITY_DISTRIBUTION_MATRIX]")
        self._lines.append("")
        
        # 表头
        self._lines.append("| Comm_Group | Count | Incl_Saliency | Excl_Saliency | Core_Affinity | Throttle_Rate |")
        self._lines.append("|------------|-------|---------------|---------------|---------------|---------------|")
        
        # 数据行
        for entity in self._result.entity_distribution:
            is_bottleneck = entity.incl_saliency > 0.5 or entity.excl_saliency > 0.5
            
            comm_str = self._format_comm(entity.comm, is_bottleneck)
            count_str = self._format_number(entity.count)
            incl_str = self._format_saliency(entity.incl_saliency, is_bottleneck)
            excl_str = self._format_saliency(entity.excl_saliency, is_bottleneck)
            affinity_str = self._format_affinity(entity.core_affinity, is_bottleneck)
            throttle_str = self._format_throttle(entity.throttle_rate, is_bottleneck)
            
            row = f"| {comm_str} | {count_str} | {incl_str} | {excl_str} | {affinity_str} | {throttle_str} |"
            self._lines.append(row)
        
        self._lines.append("")
    
    def _build_convergence_trace(self):
        """构建 [CONVERGENCE_TRACE] 段"""
        self._lines.append("## [CONVERGENCE_TRACE]")
        self._lines.append("")
        
        # COMMON_HOTSPOT
        if self._result.common_hotspot:
            weight = self._result.common_hotspot_weight
            self._lines.append(f"### **COMMON_HOTSPOT: `{self._result.common_hotspot}` {weight:.1f}%**")
            self._lines.append("")
            self._lines.append("*所有聚类共享的热点符号，通常是瓶颈汇聚点*")
            self._lines.append("")
            self._lines.append("---")
            self._lines.append("")
        
        # 每个 Cluster
        for cluster in self._result.clusters:
            self._lines.append(f"#### **[{cluster.cluster_id}]**")
            self._lines.append("")
            
            # 路径展示：comm -> func1 -> func2 -> **[HOTSPOT]**
            path_str = self._format_path(cluster.path, cluster.hotspot)
            self._lines.append(path_str)
            self._lines.append("")
            
            # Characteristic 标签
            self._lines.append(f"* **Characteristic**: `{cluster.characteristic}`")
            self._lines.append(f"* **Weight**: {cluster.weight:.1f}%（占总样本比例）")
            self._lines.append("")
            self._lines.append("---")
            self._lines.append("")
    
    def _build_correlation_flags(self):
        """构建 [CORRELATION_FLAGS] 段"""
        self._lines.append("## [CORRELATION_FLAGS]")
        self._lines.append("")
        self._lines.append("*跨维度关联检测，自动标记系统性问题*")
        self._lines.append("")
        
        for flag in self._result.correlation_flags:
            icon = self.SEVERITY_ICONS.get(flag.severity.lower(), "⚪")
            flag_line = f"{icon} **[FLAG: {flag.flag_type}]** : `{flag.target}` {flag.message}"
            self._lines.append(flag_line)
        
        if not self._result.correlation_flags:
            self._lines.append("*(未检测到关联标志)*")
        
        self._lines.append("")
    
    def _build_data_summary(self):
        """构建 [DATA_SUMMARY] 段"""
        self._lines.append("## [DATA_SUMMARY]")
        self._lines.append("")
        self._lines.append("*诊断会话元数据摘要*")
        self._lines.append("")
        
        # YAML 格式
        self._lines.append("```yaml")
        self._lines.append(f"total_pids: {self._result.total_pids}")
        self._lines.append(f"total_sys_cpu: {self._result.total_sys_cpu:.1f}")
        
        top_bottleneck_str = ", ".join(f"`{b}`" for b in self._result.top_bottlenecks[:3])
        self._lines.append(f"top_bottleneck: {top_bottleneck_str}")
        
        self._lines.append(f"duration_sec: {self._result.duration_sec:.1f}")
        self._lines.append(f"sample_count: {self._result.sample_count}")
        
        # 数据质量评估
        quality = self._assess_data_quality()
        self._lines.append(f"data_quality: \"{quality}\"")
        
        self._lines.append("```")
        self._lines.append("")
    
    def _format_comm(self, comm: str, is_bottleneck: bool) -> str:
        """格式化 Comm_Group 字段"""
        if is_bottleneck:
            return f"**`{comm}`**"
        return f"`{comm}`"
    
    def _format_number(self, num: int) -> str:
        """格式化数字"""
        return str(num)
    
    def _format_saliency(self, value: float, is_bottleneck: bool) -> str:
        """格式化显著度值"""
        formatted = f"{value:.2f}"
        if is_bottleneck and value > 0.5:
            return f"**{formatted}**"
        return formatted
    
    def _format_affinity(self, affinity: str, is_bottleneck: bool) -> str:
        """格式化 Core_Affinity 字段"""
        if is_bottleneck:
            return f"**{affinity}**"
        return affinity
    
    def _format_throttle(self, rate: float, is_bottleneck: bool) -> str:
        """格式化 Throttle_Rate 字段"""
        formatted = f"{rate:.1f}%"
        if is_bottleneck and rate > 50:
            return f"**{formatted}**"
        return formatted
    
    def _format_path(self, path: List[str], hotspot: str) -> str:
        """
        格式化调用路径
        
        格式：`comm` -> `func1` -> `func2` -> **[HOTSPOT]**
        """
        if not path:
            return f"**[{hotspot}]**"
        
        parts = []
        for i, node in enumerate(path):
            if i == 0:
                parts.append(f"`{node}`")
            else:
                parts.append(f"-> `{node}`")
        
        parts.append(f"-> **[{hotspot}]**")
        return " ".join(parts)
    
    def _assess_data_quality(self) -> str:
        """
        评估数据质量
        
        Returns:
            "good" | "fair" | "poor"
        """
        if self._result.sample_count < 1000:
            return "poor"
        elif self._result.sample_count < 5000:
            return "fair"
        else:
            return "good"


# =============================================================================
# 便捷函数
# =============================================================================

def build_bottleneck_trace_output(result: BottleneckTraceResult) -> str:
    """
    便捷函数：构建 bottleneck-trace 输出
    
    Args:
        result: BottleneckTraceResult 数据对象
        
    Returns:
        格式化的 Markdown 字符串
        
    使用示例：
        result = tracer.trace(samples, target_comm="app_B")
        output = build_bottleneck_trace_output(result)
        print(output)
    """
    builder = BottleneckTraceOutputBuilder(result)
    return builder.build()
