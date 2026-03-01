#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - 基于统一数据模型的输出构建器

与 output_models.py 配合使用，提供：
- 类型安全的输出构建
- 统一的数据结构管理
- 自动转换到 JSON
- Live Document 自动记录 (v2.0)

使用方式:
    from output_builder import OutputBuilder
    from output_models import RiskInfo, ProcessItem, ProcessSummary, ProcessTopOutput
    
    builder = OutputBuilder(engine, args)
    builder.begin_command("get-comm-top")
    
    # ... 分析逻辑 ...
    
    # 检测到风险时自动记录
    builder.record_risk("warning", "高内核态", "cluster-symbols --comm xxx")
    
    # 分析完成时自动标记解决
    builder.record_resolution("ISS-001", "LOCK_CONTENTION 38.36%")
    
    builder.end_command()
    builder.print_output(output)
"""

import os
import sys
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
from .live_doc import LiveDoc


T = TypeVar('T', bound=BaseOutput)


class OutputBuilder:
    """
    基于统一数据模型的输出构建器 V2
    
    与 V1 版本的主要区别：
    - 使用 dataclass 定义的数据模型
    - 类型安全的输出构建
    - 通过 OutputAdapter 自动转换为 JSON
    - Live Document 自动记录 (v2.0)
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
        
        # Live Document v2.0 自动记录
        self._live_doc = None
        self._command_name = None
        self._auto_trace = getattr(args, 'live_doc', True)  # 默认开启
    
    # =====================================================================
    # Live Document v2.0 - 自动记录 API
    # =====================================================================
    
    def begin_command(self, command_name: str):
        """
        命令开始时调用，自动初始化 LiveDoc 并记录命令
        
        Args:
            command_name: 命令名称，如 "get-comm-top"
        """
        if not self._auto_trace:
            return
        
        self._command_name = command_name
        
        # 构建完整命令字符串
        cmd_parts = [command_name]
        data_file = getattr(self.args, 'data', None)
        if data_file:
            cmd_parts.append(f"--data {data_file}")
        
        # 添加其他常见参数
        for attr in ['comm', 'pid', 'cpu_id', 'start_time', 'end_time', 'top_n']:
            val = getattr(self.args, attr, None)
            if val is not None:
                cmd_parts.append(f"--{attr.replace('_', '-')} {val}")
        
        full_command = " ".join(cmd_parts)
        
        # 初始化 LiveDoc
        try:
            self._live_doc = LiveDoc()
            # 如果文档不存在，自动初始化
            if not self._live_doc.data.get('data_file') and data_file:
                self._live_doc.init(data_file)
            
            self._live_doc.begin_command(full_command)
        except Exception:
            # 自动记录失败不应影响主流程
            self._live_doc = None
    
    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """
        记录发现的风险，自动创建 issue
        
        Args:
            level: critical/warning/info
            desc: 风险描述
            hint: 建议操作
            
        Returns:
            issue_id: 创建的 issue ID（或空字符串）
        """
        if not self._auto_trace or not self._live_doc:
            return ""
        
        try:
            return self._live_doc.record_risk(level, desc, hint)
        except Exception:
            return ""
    
    def record_resolution(self, issue_id: str, result: str):
        """
        标记 issue 已解决
        
        Args:
            issue_id: 要解决的 issue ID
            result: 分析结果/结论
        """
        if not self._auto_trace or not self._live_doc:
            return
        
        try:
            self._live_doc.record_resolution(issue_id, result)
        except Exception:
            pass
    
    def auto_resolve_by_command(self, comm: str = None, result: str = ""):
        """
        根据命令参数自动匹配并解决 issue
        
        例如: cluster-symbols --comm netstat 会自动匹配 netstat 相关的 open issue
        
        Args:
            comm: 进程名，用于匹配
            result: 分析结果
        """
        if not self._auto_trace or not self._live_doc:
            return
        
        try:
            # 从 args 获取 comm
            if comm is None:
                comm = getattr(self.args, 'comm', None)
            
            if not comm:
                return
            
            # 查找匹配的 open issue
            for issue_id, issue in self._live_doc.data['issues'].items():
                if issue['status'] == 'open' and comm in issue['desc']:
                    self._live_doc.record_resolution(issue_id, result)
                    break
        except Exception:
            pass
    
    def record_info(self, message: str):
        """记录一般信息"""
        if not self._auto_trace or not self._live_doc:
            return
        
        try:
            self._live_doc.record_info(message)
        except Exception:
            pass
    
    def end_command(self):
        """命令结束时调用，保存 LiveDoc"""
        if not self._auto_trace or not self._live_doc:
            return
        
        try:
            self._live_doc.end_command()
        except Exception:
            pass
    
    def get_live_doc_summary(self) -> Dict:
        """获取 LiveDoc 摘要（用于输出）"""
        if not self._live_doc:
            return {"enabled": False}
        
        return {
            "enabled": True,
            **self._live_doc.get_summary()
        }
    
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
        
        total_weight, _ = self.engine.get_total_core_per_sec(samples)
        quality_level, warning_msg, metrics = assess_data_quality(
            duration, total_weight=total_weight, record_count=record_count
        )
        
        self._quality_level = quality_level
        self._quality_metrics = {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        }
        
        # 早期返回处理
        if early_return:
            if quality_level == "CRITICAL":
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
            else:
                # 数据质量良好，不提前返回
                return False
        
        return quality_level
    
    # =====================================================================
    # 输出方法
    # =====================================================================
    
    def print_output(self, output: BaseOutput, auto_end: bool = True):
        """
        打印输出对象
        
        Args:
            output: 继承自 BaseOutput 的输出对象
            auto_end: 是否自动结束命令记录（默认True）
        """
        if self.text_mode:
            text_str = self.adapter.format_output(output)
            print(text_str)
        else:
            json_str = self.adapter.to_json(output)
            print(json_str)
        
        # 自动结束命令记录
        if auto_end:
            self.end_command()
    
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
