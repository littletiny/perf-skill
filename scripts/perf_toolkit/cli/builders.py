#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - 基于统一数据模型的输出构建器

与 output_models.py 配合使用，提供：
- 类型安全的输出构建
- 统一的数据结构管理
- 自动转换到 JSON
- Trace 自动记录 (v2.0)
"""

import os
import sys
from typing import List, Dict, Optional, Any, Type, TypeVar, Generic
from dataclasses import dataclass

# 注意: import 路径从 core 改为相对导入
from ..core.output_models import (
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
    # Dict Refactor 新增模型
    TraceSummary, ErrorData, QualityMetrics, IssueCategories,
)
from ..core.output_adapter import OutputAdapter, CompactOutputAdapter
from ..core.text_output_adapter import TextOutputAdapter
from ..core.output_models import RiskInfo
from ..core.format_utils import format_time_range, safe_time_range
from ..core.reliability import assess_data_quality
from ..core.trace import Trace


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

    def get_trace_summary(self) -> TraceSummary:
        """获取 Trace 摘要（返回 TraceSummary dataclass）"""
        if not self._trace:
            return TraceSummary(enabled=False)

        summary = self._trace.get_summary()
        return TraceSummary(
            enabled=True,
            total_commands=summary.total_commands,
            open_issues=summary.open_issues,
            resolved_issues=summary.resolved_issues,
            can_finalize=summary.can_finalize
        )

    # =====================================================================
    # 数据质量评估（与 V1 兼容）
    # =====================================================================

    def check_empty_samples(self, samples: List[Dict], filters: Dict = None) -> bool:
        """检查样本是否为空"""
        if samples:
            self._samples = samples
            return False

        # 构建错误响应（使用 ErrorData dataclass）
        error_data = ErrorData(
            error="No samples found",
            message="未找到匹配过滤条件的样本数据",
            recovery_hint="检查过滤条件或扩大时间范围"
        )

        # 创建风险输出
        risk_info = RiskInfo(
            level="warning",
            message="未找到样本数据",
            hint="[必须] 添加到 Trace: shecr trace add --desc '未找到样本数据' --hint '检查过滤条件'",
            patterns=["NO_SAMPLES"]
        )

        result = {
            "_risk": risk_info,
            **{
                "error": error_data.error,
                "message": error_data.message,
                "recovery_hint": error_data.recovery_hint,
                "time_range": format_time_range(
                    getattr(self.args, 'start_time', None),
                    getattr(self.args, 'end_time', None)
                ),
                "available_range": self.engine.get_time_range(),
                "filters": filters or {}
            }
        }
        self.print_json(result)
        return True

    def assess_quality(self, samples: List[Dict] = None,
                       early_return: bool = False) -> Optional[str]:
        """评估数据质量（使用 QualityMetrics dataclass）"""
        if samples is None:
            samples = self._samples

        if not samples:
            self._quality_level = "CRITICAL"
            self._quality_metrics = QualityMetrics()
            return self._quality_level if not early_return else False

        duration = samples[-1].ts - samples[0].ts if len(samples) > 1 else 0
        record_count = len(samples)

        total_weight, _ = self.engine.get_total_core_per_sec(samples)
        quality_level, warning_msg, metrics = assess_data_quality(
            duration, total_weight=total_weight, record_count=record_count
        )

        # 使用 QualityMetrics dataclass
        self._quality_level = quality_level
        self._quality_metrics = QualityMetrics(
            total_samples=getattr(metrics, 'record_count', 0),
            time_range_seconds=getattr(metrics, 'duration_sec', 0.0),
            cpu_count=getattr(self.args, 'cpu_id', 0) or 0
        )

        # 早期返回处理
        if early_return:
            if quality_level == "CRITICAL":
                # 添加数据质量风险
                risk_info = RiskInfo(
                    level="critical",
                    message="数据质量不足！分析结果完全不可信",
                    hint="[必须] 添加到 Trace: shecr trace add --desc '数据质量不足！分析结果完全不可信' --hint '使用更长的采样时间重新采集数据'",
                    patterns=["CRITICAL_DATA_QUALITY"]
                )

                result = {
                    "_risk": risk_info,
                    **{
                        "data_quality": {
                            "level": self._quality_metrics.level,
                            "warning": self._quality_metrics.warning,
                            "total_samples": self._quality_metrics.total_samples,
                            "time_range_seconds": self._quality_metrics.time_range_seconds,
                            "cpu_count": self._quality_metrics.cpu_count,
                        },
                        "error": "Insufficient data quality for analysis"
                    }
                }
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

    def _categorize_issues(self, issues: List[Dict]) -> IssueCategories:
        """
        对 issues 进行分类统计（返回 IssueCategories dataclass）

        分类规则:
        - 内核异常: desc 包含 "内核" 或 "kernel"
        - 锁竞争: desc 包含 "锁竞争" 或 "LOCK_CONTENTION"
        - 进程风暴: desc 包含 "进程风暴" 或 "PROCESS_STORM"
        """
        categories = IssueCategories()

        for issue in issues:
            desc = issue.get('desc', '').lower()

            if '内核' in desc or 'kernel' in desc:
                categories.kernel_anomaly += 1
            elif '锁竞争' in desc or 'lock_contention' in desc:
                categories.lock_contention += 1
            elif '进程风暴' in desc or 'process_storm' in desc:
                categories.process_storm += 1

        return categories

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
            risk = output._risk

            # 只记录 critical 和 warning 级别的 risk
            if risk.level in ['critical', 'warning'] and risk.message:
                # 生成简洁的 hint（如果 hint 太长或为空）
                hint = risk.hint or self._generate_hint_from_message(risk.message)
                self.record_risk(risk.level, risk.message, hint)

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
        # 使用 OutputAdapter 处理数据，支持 dataclass 自动转换
        print(self.adapter.to_json(data))

    def to_dict(self, output: BaseOutput) -> Dict:
        """将输出对象转换为字典"""
        return self.adapter.to_dict(output)


