#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - 基于统一数据模型的输出构建器

与 output_models.py 配合使用，提供：
- 类型安全的输出构建
- 统一的数据结构管理
- 自动转换到 JSON

使用方式:
    from output_builder import OutputBuilder
    from output_models import RiskInfo, ProcessItem, ProcessSummary, ProcessTopOutput
    
    builder = OutputBuilder(engine, args)
    
    # 创建数据项
    items = [ProcessItem.from_stats(...), ...]
    
    # 构建输出
    output = ProcessTopOutput(
        _risk=RiskInfo(level="none"),
        processes=items,
        summary=ProcessSummary(total_processes=10, shown_processes=5),
        time_range=TimeRange(...)
    )
    
    builder.print_output(output)
"""

from typing import List, Dict, Optional, Any, Type, TypeVar, Generic
from dataclasses import dataclass

from .output_models import (
    RiskInfo, TimeRange, BaseSummary, BaseOutput,
    ProcessItem, CommGroupItem, HotspotItem, ClusterItem,
    ProcessSummary, CommGroupSummary, HotspotSummary, ClusterSummary,
    ProcessTopOutput, CommTopOutput, HotspotsOutput, ClustersOutput,
    ClusterCommOutput,
    # V2 新增模型
    BottleneckData, BottleneckSummary, BottleneckOutput,
    CPUUsageData, CPUUsageSummary, CPUUsageOutput,
    AnomalyItem, AnomalySummary, AnomaliesOutput,
    WindowItem, WindowSummary, WindowsOutput,
    AttributionItem, AttributionSummary, AttributionsOutput,
    TraceItem, TracesSummary, TracesOutput,
    PathClusterItem, PathClusterSummary, PathClustersOutput,
    ProcessVarietyItem, ProcessVarietySummary, ProcessVarietyOutput,
    CoreItem, CoreDistributionSummary, CoreDistributionOutput,
)
from .output_adapter import OutputAdapter, CompactOutputAdapter
from .text_output_adapter import TextOutputAdapter
from .risk_mixin import RiskAwareOutput
from .format_utils import format_time_range, safe_time_range
from .reliability import assess_data_quality


T = TypeVar('T', bound=BaseOutput)


class OutputBuilder:
    """
    基于统一数据模型的输出构建器 V2
    
    与 V1 版本的主要区别：
    - 使用 dataclass 定义的数据模型
    - 类型安全的输出构建
    - 通过 OutputAdapter 自动转换为 JSON
    """
    
    def __init__(self, engine, args, compact: bool = False, text_mode: bool = True):
        """
        初始化输出构建器
        
        Args:
            engine: PerfExpertEngine 实例
            args: argparse namespace
            compact: 是否使用紧凑模式输出
            text_mode: 是否使用人类可读的文本格式输出（默认True）
        """
        self.engine = engine
        self.args = args
        self.compact = compact
        self.text_mode = text_mode
        if text_mode:
            self.adapter = TextOutputAdapter()
        elif compact:
            self.adapter = CompactOutputAdapter()
        else:
            self.adapter = OutputAdapter()
        self._risk_output = RiskAwareOutput()
        self._quality_level = None
        self._quality_metrics = None
        self._samples = None
    
    # =====================================================================
    # 数据质量评估（与 V1 兼容）
    # =====================================================================
    
    def check_empty_samples(self, samples: List[Dict], filters: Dict = None) -> bool:
        """检查样本是否为空"""
        if samples:
            self._samples = samples
            return False
        
        # 构建错误响应
        error_data = {
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(self.args, 'start_time', None),
                getattr(self.args, 'end_time', None)
            ),
            "available_range": self.engine.get_time_range()
        }
        
        if filters:
            error_data["filters"] = filters
        
        # 创建风险输出
        risk_output = RiskAwareOutput()
        risk_output.add_risk(
            "warning",
            "未找到样本数据",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '未找到样本数据' --risk 'warning' --hint '检查过滤条件'",
            patterns=["NO_SAMPLES"]
        )
        
        result = risk_output.build(error_data)
        self.print_json(result)
        return True
    
    def assess_quality(self, samples: List[Dict] = None, 
                       early_return: bool = False) -> Optional[str]:
        """评估数据质量"""
        if samples is None:
            samples = self._samples
        
        if not samples:
            self._quality_level = "CRITICAL"
            self._quality_metrics = {}
            return self._quality_level if not early_return else False
        
        duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
        record_count = len(samples)
        
        total_core_per_sec, _ = self.engine.get_total_core_per_sec(samples)
        quality_level, warning_msg, metrics = assess_data_quality(
            duration, total_core_per_sec=total_core_per_sec, record_count=record_count
        )
        
        self._quality_level = quality_level
        self._quality_metrics = {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        }
        
        # 早期返回处理
        if early_return and quality_level == "CRITICAL":
            # 添加数据质量风险
            risk_output = RiskAwareOutput()
            risk_output.add_risk(
                "critical",
                "数据质量不足！分析结果完全不可信",
                "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！分析结果完全不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
                patterns=["CRITICAL_DATA_QUALITY"]
            )
            
            result = risk_output.build({
                "data_quality": self._quality_metrics,
                "error": "Insufficient data quality for analysis"
            })
            self.print_json(result)
            return True
        
        return quality_level
    
    # =====================================================================
    # 输出方法
    # =====================================================================
    
    def print_output(self, output: BaseOutput):
        """
        打印输出对象
        
        Args:
            output: 继承自 BaseOutput 的输出对象
        """
        if self.text_mode:
            text_str = self.adapter.format_output(output)
            print(text_str)
        else:
            json_str = self.adapter.to_json(output)
            print(json_str)
    
    def print_json(self, data: Dict):
        """打印 JSON 数据（兼容 V1）"""
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))
    
    def to_dict(self, output: BaseOutput) -> Dict:
        """将输出对象转换为字典"""
        return self.adapter.to_dict(output)


# =============================================================================
# Legacy Compatibility
# =============================================================================

def create_risk_info(level: str, message: str = "", hint: str = "",
                     patterns: List[str] = None, 
                     pending_targets: List[str] = None) -> RiskInfo:
    """
    快速创建 RiskInfo
    
    兼容旧版 RiskMixin 的使用方式
    """
    return RiskInfo(
        level=level,
        message=message,
        hint=hint,
        patterns=patterns or [],
        pending_targets=pending_targets or [],
        action_required=level in ["critical", "warning"]
    )
