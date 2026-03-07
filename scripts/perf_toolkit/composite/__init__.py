#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Composite Layer - 组合分析层

三层架构中的Layer 3：
- 编排多个Analysis工具
- 生成综合诊断报告
- Risk聚合与分级

Commands:
    sys-audit: 系统审计组合命令
    bottleneck-analyze: 瓶颈分析命令

Usage:
    from perf_toolkit.composite import SysAuditOutput, BottleneckAnalyzeResult
    from perf_toolkit.composite.risk_aggregator import RiskAggregator
    from perf_toolkit.core.models import RiskInfo
    from perf_toolkit.composite.models import (
        ProcessGroup, DiagnosisReport,
        AnomaliesReport, CoreDistributionReport, CommTopReport
    )
"""

from ..core.output_models import (
    SysAuditOutput,
    BottleneckAnalyzeResult
)

__all__ = [
    'SysAuditOutput',
    'BottleneckAnalyzeResult',
]
