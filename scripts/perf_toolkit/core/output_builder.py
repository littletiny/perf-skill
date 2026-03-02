#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - 基于统一数据模型的输出构建器

与 output_models.py 配合使用，提供：
- 类型安全的输出构建
- 统一的数据结构管理
- 自动转换到 JSON
- Trace 自动记录 (v2.0)

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
from .trace import Trace


T = TypeVar('T', bound=BaseOutput)


class OutputBuilder:
    """
    基于统一数据模型的输出构建器 V2

    与 V1 版本的主要区别：
    - 使用 dataclass 定义的数据模型
    - 类型安全的输出构建
    - 通过 OutputAdapter 自动转换为 JSON
    - Trace 自动记录 (v2.0)
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

        # Trace v2.0 自动记录
        self._trace = None
        self._command_name = None
        self._auto_trace = getattr(args, 'trace', True)  # 默认开启

    # =====================================================================
    # Trace v2.0 - 自动记录 API
    # =====================================================================

    def begin_command(self, command_name: str):
        """
        命令开始时调用，自动初始化 Trace 并记录命令

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

        # 初始化 Trace
        try:
            self._trace = Trace()
            # 如果文档不存在，自动初始化
            if not self._trace.data.get('data_file') and data_file:
                self._trace.init(data_file)

            self._trace.begin_command(full_command)
        except Exception:
            # 自动记录失败不应影响主流程
            self._trace = None

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
        if not self._auto_trace or not self._trace:
            return ""

        try:
            return self._trace.record_risk(level, desc, hint)
        except Exception:
            return ""

    def record_resolution(self, issue_id: str, result: str):
        """
        标记 issue 已解决

        Args:
            issue_id: 要解决的 issue ID
            result: 分析结果/结论
        """
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.record_resolution(issue_id, result)
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
        if not self._auto_trace or not self._trace:
            return

        try:
            # 从 args 获取 comm
            if comm is None:
                comm = getattr(self.args, 'comm', None)

            if not comm:
                return

            # 查找匹配的 open issue
            for issue_id, issue in self._trace.data['issues'].items():
                if issue['status'] == 'open' and comm in issue['desc']:
                    self._trace.record_resolution(issue_id, result)
                    break
        except Exception:
            pass

    def record_info(self, message: str):
        """记录一般信息"""
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.record_info(message)
        except Exception:
            pass

    def end_command(self):
        """命令结束时调用，保存 Trace"""
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.end_command()
        except Exception:
            pass

    def get_trace_summary(self) -> Dict:
        """获取 Trace 摘要（用于输出）"""
        if not self._trace:
            return {"enabled": False}

        return {
            "enabled": True,
            **self._trace.get_summary()
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
            "[必须] 添加到 Trace: spear trace add --desc '未找到样本数据' --hint '检查过滤条件'",
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
                    "[必须] 添加到 Trace: spear trace add --desc '数据质量不足！分析结果完全不可信' --hint '使用更长的采样时间重新采集数据'",
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

    def print_issue_overflow_warning(self):
        """
        检查 pending issues 并输出 overflow warning

        触发条件: open_issues >= 2
        输出格式: [!] {总数}问题未闭环: {分类统计} | {警告文案} | 现在执行: trace issues
        """
        try:
            # 如果没有 trace 实例，创建一个临时的
            trace = self._trace if self._trace else Trace()
            open_issues = trace.get_open_issues()

            if len(open_issues) < 2:
                return

            # 分类统计
            categories = self._categorize_issues(open_issues)
            category_str = ", ".join([f"{cat}x{count}" for cat, count in categories.items()]) if categories else "未知类型"

            # 固定警告文案
            warning = "⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状"

            # 输出
            print(f"[!] {len(open_issues)}问题未闭环: {category_str} | {warning} | 现在执行: trace issues")
            print()  # 空行分割
        except Exception:
            # 提示失败不应影响主流程
            pass

    def _categorize_issues(self, issues: List[Dict]) -> Dict[str, int]:
        """
        对 issues 进行分类统计

        分类规则:
        - 内核异常: desc 包含 "内核" 或 "kernel"
        - 锁竞争: desc 包含 "锁竞争" 或 "LOCK_CONTENTION"
        - 进程风暴: desc 包含 "进程风暴" 或 "PROCESS_STORM"
        """
        categories = {
            "内核异常": 0,
            "锁竞争": 0,
            "进程风暴": 0,
        }

        for issue in issues:
            desc = issue.get('desc', '').lower()

            if '内核' in desc or 'kernel' in desc:
                categories["内核异常"] += 1
            elif '锁竞争' in desc or 'lock_contention' in desc:
                categories["锁竞争"] += 1
            elif '进程风暴' in desc or 'process_storm' in desc:
                categories["进程风暴"] += 1

        # 过滤掉计数为 0 的分类
        return {k: v for k, v in categories.items() if v > 0}

    def _auto_record_risk_from_output(self, output: BaseOutput):
        """
        自动从 output 中提取 risk 信息并记录到 Trace

        支持两种 risk 格式:
        - output.risk: RiskInfo 对象 (V2 模型)
        - output._risk: dict (兼容 RiskMixin)
        """
        if not self._auto_trace:
            return

        # 确保 trace 已初始化（即使 begin_command 未被调用）
        if not self._trace:
            try:
                self._trace = Trace()
                data_file = getattr(self.args, 'data', None)
                if data_file and not self._trace.data.get('data_file'):
                    self._trace.init(data_file)
            except Exception:
                return

        try:
            risk = None

            # 尝试获取 risk 字段 (V2 模型)
            if hasattr(output, 'risk') and output.risk:
                risk = output.risk
            # 尝试获取 _risk 字段 (RiskMixin 兼容)
            elif hasattr(output, '_risk') and output._risk:
                risk = output._risk

            if not risk:
                return

            # 提取 risk 信息
            level = "warning"
            message = ""
            hint = ""

            if isinstance(risk, RiskInfo):
                level = risk.level
                message = risk.message
                hint = risk.hint
            elif isinstance(risk, dict):
                level = risk.get('level', 'warning')
                message = risk.get('message', '')
                hint = risk.get('hint', '')

            # 只记录 critical 和 warning 级别的 risk
            if level in ['critical', 'warning'] and message:
                # 生成简洁的 hint（如果 hint 太长或为空）
                if not hint:
                    hint = self._generate_hint_from_message(message)

                self.record_risk(level, message, hint)

        except Exception:
            # 自动记录失败不应影响主流程
            pass

    def _generate_hint_from_message(self, message: str) -> str:
        """从 message 生成默认 hint"""
        # 简单启发式：根据消息内容推断 hint
        message_lower = message.lower()
        if '内核' in message_lower or 'kernel' in message_lower:
            return "cluster-symbols --comm $COMM"
        elif '锁' in message_lower or 'lock' in message_lower or 'mutex' in message_lower:
            return "find-callers --target $FUNC"
        elif '进程' in message_lower or 'process' in message_lower:
            return "count-process-variety --comm $COMM"
        elif 'cpu' in message_lower or '瓶颈' in message_lower:
            return "check-cpu-bottleneck"
        else:
            return "trace issues"

    def print_output(self, output: BaseOutput, auto_end: bool = True):
        """
        打印输出对象

        Args:
            output: 继承自 BaseOutput 的输出对象
            auto_end: 是否自动结束命令记录（默认True）
        """
        # 自动记录 risk 到 Trace（全自动化）
        self._auto_record_risk_from_output(output)

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
        """打印字典数据（兼容 V1，内部直接使用 dict，仅在输出时转 JSON）"""
        # 注意：这里只在最终输出时使用 JSON，内部处理均使用 Dict
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
                     pending_targets: List[str] = None,
                     action_required: bool = None) -> RiskInfo:
    """
    快速创建 RiskInfo

    兼容旧版 RiskMixin 的使用方式
    
    Args:
        action_required: 可选，如果为 None 则根据 level 自动计算
    """
    if action_required is None:
        action_required = level in ["critical", "warning"]
    
    return RiskInfo(
        level=level,
        message=message,
        hint=hint,
        patterns=patterns or [],
        pending_targets=pending_targets or [],
        action_required=action_required
    )
