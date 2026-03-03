#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text Output Adapter - 模板化文本输出系统

支持 5 种模板类型:
- simple_list: 带序号的简单列表, #index field1 field2 ...
- key_value: 无序号键值对, key value1 value2 ...
- table: 多字段表格
- nested: 嵌套结构,有父项和子项
- custom: 完全自定义格式

使用方式:
1. 在 Output 模型中定义 _template_config (TemplateConfig)
2. Adapter 自动根据 template_type 选择渲染器
3. 如需自定义渲染,继承 Template 基类并注册

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import (
    OutputDefaults, Thresholds, AttentionFlag,
    ImbalanceLevel, CompositeDefaults, RiskDisplayDefaults,
    DiagnosisType
)

# 导入配置加载器
from perf_toolkit.core.config_loader import get_config


class Template(ABC):
    """模板基类"""

    @abstractmethod
    def render(self, data: Any, config: Any) -> List[str]:
        """渲染数据,返回行列表"""
        pass

    def _get_list_data(self, data: Any, list_field: str) -> List[Any]:
        """获取列表数据"""
        data_dict = asdict(data) if is_dataclass(data) else data
        return data_dict.get(list_field, [])

    def _format_field_value(self, item: Any, field: str) -> str:
        """格式化字段值"""
        if isinstance(item, dict):
            value = item.get(field, "N/A")
        else:
            value = getattr(item, field, "N/A")

        # 特殊处理列表类型(如 caller_stack)
        if isinstance(value, list):
            if field == "caller_stack":
                return " <- ".join(str(v) for v in value) if value else "(root)"
            return ", ".join(str(v) for v in value)

        return str(value) if value is not None else "N/A"

    def _format_process_line(self, item: Any) -> str:
        """格式化进程行(特殊处理 comm(pid) 格式)"""
        if isinstance(item, dict):
            comm = item.get('comm', 'N/A')
            pid = item.get('pid', 'N/A')
            total = item.get('total_cpu_util', '0.00%')
            kernel = item.get('kernel_cpu_util', '0.00%')
        else:
            comm = getattr(item, 'comm', 'N/A')
            pid = getattr(item, 'pid', 'N/A')
            total = getattr(item, 'total_cpu_util', '0.00%')
            kernel = getattr(item, 'kernel_cpu_util', '0.00%')
        return f"{comm}({pid}) {total}/{kernel}"


class SimpleListTemplate(Template):
    """简单列表模板 - #index field1 field2 ...

    适用于: hotspots, processes, cores, attributions, path_clusters
    """

    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []

        if config.header:
            lines.append(config.header)

        if not items:
            msg = config.empty_message if config.empty_message else 'No data found'
            lines.append(f"({msg})")
            return lines

        for i, item in enumerate(items, 1):
            if config.list_field == "processes":
                # 特殊处理: processes 使用 comm(pid) 格式
                line = self._format_process_line(item)
            elif config.list_field == "attributions":
                # 特殊处理: attributions 的 ratio + callstack 格式
                line = self._format_attribution_line(item, i)
            elif config.list_field == "path_clusters":
                # 特殊处理: path_clusters 从原始权重计算百分比
                line = self._format_path_cluster_line(item, i, config)
            else:
                # 标准格式: #index field1 field2 ...
                values = [self._format_field_value(item, f) for f in config.display_fields]
                prefix = config.index_format.format(index=i) if config.index_format else f"#{i}"
                line = f"{prefix} " + " ".join(values)

            lines.append(line)

        return lines

    def _format_path_cluster_line(self, item: Any, index: int, config: Any) -> str:
        """格式化路径聚类行 - 从原始权重计算百分比"""
        # 从原始数据计算百分比
        if isinstance(item, dict):
            weight = item.get('weight', 0)
            total = item.get('total_weight', 1)
            duration = item.get('duration', 1)
            path = item.get('path_signature', 'N/A')
        else:
            weight = getattr(item, 'weight', 0)
            total = getattr(item, 'total_weight', 1)
            duration = getattr(item, 'duration', 1)
            path = getattr(item, 'path_signature', 'N/A')

        # 计算百分比
        ratio_pct = (weight / total * 100) if total > 0 else 0
        cpu_util = (weight / duration * 100) if duration > 0 else 0

        prefix = config.index_format.format(index=index) if config.index_format else f"#{index}"
        return f"{prefix} {ratio_pct:.2f}% {cpu_util:.2f}% {path}"

    def _format_attribution_line(self, item: Any, index: int) -> str:
        """格式化归因行 - #index [ratio] callstack"""
        ratio = self._format_field_value(item, "ratio_of_target_pct")
        stack = self._format_field_value(item, "caller_stack")
        return f"#{index} [{ratio}] {stack}"


class KeyValueTemplate(Template):
    """键值对模板 - key value1 value2 ...

    适用于: clusters, comm_groups, process_variety
    """

    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []

        if config.header:
            lines.append(config.header)

        if not items:
            msg = config.empty_message if config.empty_message else 'No data found'
            lines.append(f"({msg})")
            return lines

        for item in items:
            values = [self._format_field_value(item, f) for f in config.display_fields]
            lines.append(" ".join(values))

        return lines


class TableTemplate(Template):
    """表格模板 - field1=value1 field2=value2 ...

    适用于: anomalies, windows
    """

    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []

        if config.header:
            lines.append(config.header)

        if not items:
            msg = config.empty_message if config.empty_message else 'No data found'
            lines.append(f"({msg})")
            return lines

        for item in items:
            if config.list_field == "anomalies":
                lines.append(self._format_anomaly_line(item))
            elif config.list_field == "windows":
                lines.append(self._format_window_line(item))
            else:
                # 通用 table 格式
                values = [self._format_field_value(item, f) for f in config.display_fields]
                lines.append(" ".join(values))

        return lines

    def _format_anomaly_line(self, item: Any) -> str:
        """格式化异常行 - 从原始数据构建显示"""
        if isinstance(item, dict):
            anomaly_type = item.get('type', 'N/A')
            cpu_id = item.get('cpu_id', 'N/A')
            # 优先使用已格式化的字段（兼容性）
            if 'time_range' in item:
                time_range = item.get('time_range', 'N/A')
                change = item.get('utilization_change', 'N/A')
            else:
                # 从原始数据格式化
                start = item.get('time_range_start', '')
                end = item.get('time_range_end', '')
                time_range = f"{start} - {end}" if start and end else 'N/A'
                prev = item.get('prev_util', 0) * 100
                curr = item.get('curr_util', 0) * 100
                next_v = item.get('next_util', 0) * 100
                change = f"{prev:.1f}% -> {curr:.1f}% -> {next_v:.1f}%"
            severity = item.get('severity', 'unknown')
        else:
            anomaly_type = getattr(item, 'type', 'N/A')
            cpu_id = getattr(item, 'cpu_id', 'N/A')
            # 优先使用已格式化的字段（兼容性）
            time_range = getattr(item, 'time_range', None)
            change = getattr(item, 'utilization_change', None)
            if time_range is None:
                # 从原始数据格式化
                start = getattr(item, 'time_range_start', '')
                end = getattr(item, 'time_range_end', '')
                time_range = f"{start} - {end}" if start and end else 'N/A'
            if change is None:
                prev = getattr(item, 'prev_util', 0) * 100
                curr = getattr(item, 'curr_util', 0) * 100
                next_v = getattr(item, 'next_util', 0) * 100
                change = f"{prev:.1f}% -> {curr:.1f}% -> {next_v:.1f}%"
            severity = getattr(item, 'severity', 'unknown')

        if isinstance(time_range, dict):
            time_range = f"{time_range.get('start', '')} - {time_range.get('end', '')}"

        return f"{anomaly_type} cpu={cpu_id} time={time_range} change={change} severity={severity}"

    def _format_window_line(self, item: Any) -> str:
        """格式化窗口行"""
        if isinstance(item, dict):
            cpu_id = item.get('cpu_id', 'N/A')
            start = item.get('start_time', 'N/A')
            end = item.get('end_time', 'N/A')
            util = item.get('utilization', 'N/A')
            weight = item.get('weight', 0)
        else:
            cpu_id = getattr(item, 'cpu_id', 'N/A')
            start = getattr(item, 'start_time', 'N/A')
            end = getattr(item, 'end_time', 'N/A')
            util = getattr(item, 'utilization', 'N/A')
            weight = getattr(item, 'weight', 0)

        return f"cpu={cpu_id} start={start} end={end} util={util} weight={weight:.4f}"


class NestedTemplate(Template):
    """嵌套模板 - 有父项和子项的层次结构

    适用于: traces
    """

    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []

        if config.header:
            lines.append(config.header)

        if not items:
            msg = config.empty_message if config.empty_message else 'No data found'
            lines.append(f"({msg})")
            return lines

        for item in items:
            lines.extend(self._format_trace_item(item))

        return lines

    def _format_trace_item(self, item: Any) -> List[str]:
        """格式化单个 trace 项"""
        if isinstance(item, dict):
            target = item.get('target', 'N/A')
            target_ratio = item.get('target_ratio_pct', '0%')
            attributions = item.get('attributions', [])
        else:
            target = getattr(item, 'target', 'N/A')
            target_ratio = getattr(item, 'target_ratio_pct', '0%')
            attributions = getattr(item, 'attributions', [])

        lines = [f">>> {target} ({target_ratio})"]

        # 解析 target_ratio 用于计算
        try:
            target_ratio_val = float(target_ratio.rstrip('%'))
        except (ValueError, AttributeError):
            target_ratio_val = 0.0

        for i, attr in enumerate(attributions, 1):
            if isinstance(attr, dict):
                stack = attr.get('caller_stack', [])
                attr_ratio = attr.get('ratio_of_target_pct', '0%')
            else:
                stack = getattr(attr, 'caller_stack', [])
                attr_ratio = getattr(attr, 'ratio_of_target_pct', '0%')

            try:
                attr_ratio_val = float(attr_ratio.rstrip('%'))
            except (ValueError, AttributeError):
                attr_ratio_val = 0.0

            # 计算总占比
            total_ratio = target_ratio_val * attr_ratio_val / 100
            stack_str = " <- ".join(str(s) for s in stack) if stack else "(root)"
            lines.append(f"  #{i} [{total_ratio:.2f}%] {stack_str}")

        return lines


class CustomTemplate(Template):
    """自定义模板 - 完全自定义的渲染逻辑

    适用于: bottleneck, cpu_usage, sys_audit, bottleneck_trace
    """

    def __init__(self):
        self.renderers = {
            "bottleneck": self._render_bottleneck,
            "cpu_usage": self._render_cpu_usage,
            "sys_audit_renderer": self._render_sys_audit,
            "bottleneck_trace_renderer": self._render_bottleneck_trace,
            "storm_trace_renderer": self._render_storm_trace,
            # V2 强类型渲染器
            "bottleneck_trace_renderer_v2": self._render_bottleneck_trace_v2,
            "sys_audit_renderer_v2": self._render_sys_audit_v2,
        }

    def render(self, data: Any, config: Any) -> List[str]:
        renderer = self.renderers.get(config.custom_renderer)
        if renderer:
            return renderer(data)
        return [f"[ERROR] Unknown custom renderer: {config.custom_renderer}"]

    def _render_bottleneck(self, data: Any) -> List[str]:
        """渲染瓶颈检测结果"""
        data_dict = asdict(data) if is_dataclass(data) else data
        special_data = data_dict.get('data', {})
        lines = []

        verdict = special_data.get('verdict', 'N/A')
        events = special_data.get('events', [])
        high_cpu_cores = special_data.get('high_cpu_cores', [])
        high_sys_cores = special_data.get('high_sys_cores', [])
        threshold = special_data.get('threshold', 80)
        sys_threshold = threshold + 10
        max_load = special_data.get('max_core_load', {})
        limit_info = special_data.get('limit_info', {})

        # Verdict 包含所有 events
        if len(events) > 1:
            lines.append(f"Verdict: {','.join(events)}")
        else:
            lines.append(f"Verdict: {verdict}")

        # 显示检测到的瓶颈核心
        if high_cpu_cores:
            lines.append(f"CPU High: {','.join(map(str, high_cpu_cores))} (total>{threshold}%)")
        if high_sys_cores:
            lines.append(f"CPU Sys High: {','.join(map(str, high_sys_cores))} (sys>{sys_threshold}%)")

        if max_load:
            lines.append(f"Max Core Load: CPU {max_load.get('cpu_id', 'N/A')} = {max_load.get('load', 'N/A')}")

        if limit_info:
            detected = limit_info.get('cpu_limit_detected', False)
            cores = limit_info.get('cpu_limit_cores', 0)
            if cores > 0:
                lines.append(f"CPU Limit: {cores}c (detected={detected})")

        return lines

    def _render_cpu_usage(self, data: Any) -> List[str]:
        """渲染 CPU 使用率"""
        data_dict = asdict(data) if is_dataclass(data) else data
        special_data = data_dict.get('data', {})
        lines = []

        target = special_data.get('target', 'System')
        util = special_data.get('cpu_utilization', {})

        lines.append(f"Target: {target}")
        lines.append(f"  Total: {util.get('total_pct', 'N/A')}")
        lines.append(f"  User:  {util.get('user_pct', 'N/A')}")
        lines.append(f"  Kernel: {util.get('kernel_pct', 'N/A')}")

        return lines

    def _render_sys_audit(self, data: Any) -> List[str]:
        """渲染系统审计结果"""
        data_dict = asdict(data) if is_dataclass(data) else data
        diagnosis = data_dict.get('diagnosis', {})
        details = data_dict.get('details', {})
        lines = []

        # 主要嫌疑人
        primary = diagnosis.get('primary_suspect')
        if primary:
            lines.append(f"Primary Suspect: {primary.get('comm', 'N/A')}")
            lines.append(f"  CPU: {primary.get('total_cpu', 0):.2f}%")
            lines.append(f"  Diagnosis: {primary.get('diagnosis', 'N/A')}")
            if primary.get('monopoly'):
                lines.append(f"  Monopoly: {primary.get('monopoly'):.2f}")
        else:
            lines.append("Primary Suspect: None detected")

        # 次要负载
        secondary = diagnosis.get('secondary_loads', [])
        if secondary:
            lines.append(f"\nSecondary Loads ({len(secondary)}):")
            for load in secondary[:3]:
                lines.append(f"  - {load.get('comm', 'N/A')}: {load.get('total_cpu', 0):.2f}% ({load.get('diagnosis', 'N/A')})")

        # 突变检测
        if diagnosis.get('mutation_detected'):
            lines.append(f"\nMutation Detected at: {diagnosis.get('mutation_time', 'N/A')}")

        # 核心饱和
        saturated = diagnosis.get('saturated_cores', [])
        if saturated:
            lines.append(f"\nSaturated Cores: {', '.join(map(str, saturated[:5]))}")

        # 根因分析
        root_cause = diagnosis.get('root_cause_analysis', '')
        if root_cause:
            lines.append(f"\nRoot Cause: {root_cause}")

        # 详细信息摘要
        lines.append("\n=== Analysis Details ===")

        # 异常检测摘要
        anomalies = details.get('anomalies', {})
        if anomalies:
            lines.append(f"Anomalies: {anomalies.get('anomalies_count', 0)} detected")
            if anomalies.get('mutation_detected'):
                lines.append("  - Mutation detected")

        # 核心分布摘要
        core_dist = details.get('core_distribution', {})
        if core_dist:
            lines.append(f"Core Distribution: {core_dist.get('core_count', 0)} cores, imbalance={core_dist.get('imbalance_level', 'N/A')}")

        # CommTop 摘要
        comm_top = details.get('comm_top', {})
        if comm_top:
            lines.append(f"Process Groups: {comm_top.get('groups_count', 0)} shown, {comm_top.get('folded_count', 0)} folded")

        return lines

    def _render_bottleneck_trace(self, data: Any) -> List[str]:
        """渲染瓶颈追踪结果"""
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []

        target_comm = data_dict.get('target_comm', 'N/A')
        lines.append(f"Target Process: {target_comm}")
        lines.append("")

        # 瓶颈分析
        bottleneck = data_dict.get('bottleneck_analysis', {})
        if bottleneck:
            if bottleneck.get('found'):
                lines.append("=== Bottleneck Analysis ===")
                lines.append(f"  Total CPU: {bottleneck.get('total_cpu', 0):.2f}%")
                lines.append(f"  Kernel Ratio: {bottleneck.get('kernel_ratio', 0):.1f}%")
                lines.append(f"  PID Count: {bottleneck.get('pid_count', 0)}")
                lines.append(f"  CV: {bottleneck.get('cv', 0):.2f}")
                lines.append(f"  Monopoly: {bottleneck.get('monopoly', 0):.2f}")
                lines.append(f"  Diagnosis: {bottleneck.get('diagnosis', 'N/A')}")
                lines.append(f"  Impact Score: {bottleneck.get('impact_score', 0):.2f}")
            else:
                lines.append("Bottleneck: Not found")

        # 热点分析
        hotspots = data_dict.get('hotspots', {})
        if hotspots:
            lines.append("")
            lines.append("=== Hotspots ===")
            top_symbol = hotspots.get('top_symbol', 'N/A')
            lines.append(f"Top Symbol: {top_symbol}")
            lines.append(f"Total Hotspots: {hotspots.get('total_hotspots', 0)}")

            hotspot_list = hotspots.get('hotspots', [])
            if hotspot_list:
                lines.append("\nHotspot Details:")
                for i, hs in enumerate(hotspot_list[:5], 1):
                    lines.append(f"  #{i} {hs.get('symbol', 'N/A')}: {hs.get('cpu_percent', 0):.2f}%")

        # 调用链溯源
        callers = data_dict.get('callers')
        if callers:
            lines.append("")
            lines.append("=== Callers ===")
            lines.append(f"Target: {callers.get('target', 'N/A')}")
            caller_list = callers.get('callers', [])
            if caller_list:
                lines.append("\nTop Callers:")
                for i, caller in enumerate(caller_list[:3], 1):
                    lines.append(f"  #{i} {caller.get('symbol', 'N/A')}: {caller.get('call_ratio', 0):.1f}%")

        return lines

    def _render_storm_trace(self, data: Any) -> List[str]:
        """渲染进程风暴追踪结果"""
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []

        target_comm = data_dict.get('target_comm', 'N/A')
        lines.append(f"Target Process: {target_comm}")
        lines.append("")

        # 风暴分析
        storm = data_dict.get('storm_analysis', {})
        if storm:
            lines.append("=== Storm Analysis ===")
            lines.append(f"  Spawn Rate: {storm.get('spawn_rate', 0):.1f} procs/sec")
            lines.append(f"  Severity: {storm.get('severity', 'N/A')}")
            lines.append(f"  PID Count: {storm.get('pid_count', 0)}")
            lines.append(f"  Total CPU: {storm.get('total_cpu', 0):.2f}%")

        # 生命周期分析
        lifecycle = data_dict.get('lifecycle', {})
        if lifecycle:
            lines.append("")
            lines.append("=== Lifecycle Analysis ===")
            lines.append(f"  Sample Count: {lifecycle.get('sample_count', 0)}")
            lines.append(f"  Time Range: {lifecycle.get('time_range_sec', 0):.1f} sec")
            unique_pids = lifecycle.get('unique_pids', [])
            if unique_pids:
                lines.append(f"  Unique PIDs: {len(unique_pids)}")

        # 调用链溯源
        callers = data_dict.get('callers')
        if callers:
            lines.append("")
            lines.append("=== Callers ===")
            lines.append(f"Target: {callers.get('target', 'N/A')}")
            caller_list = callers.get('callers', [])
            if caller_list:
                lines.append("\nTop Callers:")
                for i, caller in enumerate(caller_list[:3], 1):
                    lines.append(f"  #{i} {caller.get('symbol', 'N/A')}: {caller.get('call_ratio', 0):.1f}%")

        return lines

    # =========================================================================
    # V2 强类型渲染方法 - 基于设计文档 docs/output-design-composite.md
    # =========================================================================

    def _render_bottleneck_trace_v2(self, data: Any) -> List[str]:
        """
        渲染瓶颈追踪结果 - V2 强类型版本

        基于设计文档格式：
        ## [BOTTLENECK_TRACE]
        ### 瓶颈特征 (Bottleneck Profile)
        ### 热点函数 (Hotspots)
        ### 调用链溯源 (Call Chain Analysis)
        ### 根因分析 (Root Cause)
        """
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []

        # 标题
        lines.append(OutputDefaults.BOTTLENECK_TRACE_TITLE)
        target_comm = data_dict.get('target_comm', OutputDefaults.NA)
        lines.append(f"> 目标进程: {target_comm}")
        lines.append("")

        # 瓶颈特征
        profile = data_dict.get('bottleneck_profile', {})
        if profile and profile.get('found'):
            lines.append(OutputDefaults.BOTTLENECK_PROFILE_HEADER)
            lines.append("")

            # 评估标签 - 根据 Monopoly 和 Kernel Ratio 确定整体评估标签
            monopoly = profile.get('monopoly', 0)
            kernel_ratio = profile.get('kernel_ratio', 0)

            # 优先级: 单核饱和 > 高内核态 > 负载不均衡
            if monopoly > Thresholds.MONOPOLY_HIGH:
                lines.append(f"{AttentionFlag.X0} 评估结果: 单核饱和 (Monopoly={monopoly:.2f})")
            elif kernel_ratio > Thresholds.KERNEL_RATIO_HIGH:
                lines.append(f"{AttentionFlag.X0} 评估结果: 高内核态占比 ({kernel_ratio:.1f}%)")
            elif profile.get('cv', 0) > Thresholds.CV_UNBALANCED:
                lines.append(f"{AttentionFlag.X1} 评估结果: 负载不均衡 (CV={profile.get('cv', 0):.2f})")

            lines.append(f"| Metric | Value | Assessment |")
            lines.append(f"|--------|-------|------------|")

            total_cpu = profile.get('total_cpu', 0)
            cpu_assessment = (
                f"{AttentionFlag.X0} 严重超载" if total_cpu > Thresholds.CPU_UTIL_EXTREME
                else f"{AttentionFlag.X1} 高负载" if total_cpu > Thresholds.CPU_UTIL_HIGH
                else 'Normal'
            )
            lines.append(f"| Total CPU | {total_cpu:.2f}% | {cpu_assessment} |")

            kernel_ratio = profile.get('kernel_ratio', 0)
            kernel_assessment = (
                f"{AttentionFlag.X0} {OutputDefaults.ASSESSMENT_HIGH_KERNEL}"
                if kernel_ratio > Thresholds.KERNEL_RATIO_HIGH
                else 'Normal'
            )
            lines.append(f"| Kernel Ratio | {kernel_ratio:.1f}% | {kernel_assessment} |")

            pid_count = profile.get('pid_count', 0)
            lines.append(f"| PID Count | {pid_count} | {'Single' if pid_count == 1 else 'Multi'} |")

            monopoly_assessment = (
                f"{AttentionFlag.X0} {OutputDefaults.ASSESSMENT_SINGLE_CORE_EXCLUSIVE}"
                if monopoly > Thresholds.MONOPOLY_HIGH
                else 'Normal'
            )
            lines.append(f"| Monopoly | {monopoly:.2f} | {monopoly_assessment} |")

            cv = profile.get('cv', 0)
            cv_assessment = (
                f"{AttentionFlag.X1} {OutputDefaults.ASSESSMENT_UNBALANCED}"
                if cv > Thresholds.CV_UNBALANCED
                else 'Balanced'
            )
            lines.append(f"| CV | {cv:.2f} | {cv_assessment} |")

            impact_score = profile.get('impact_score', 0)
            impact_assessment = (
                '极高' if impact_score > Thresholds.IMPACT_SCORE_HIGH
                else '高' if impact_score > Thresholds.IMPACT_SCORE_MEDIUM
                else '中' if impact_score > Thresholds.IMPACT_SCORE_LOW
                else '低'
            )
            lines.append(f"| Impact Score | {impact_score:.2f} | {impact_assessment} |")

            lines.append("")

        # 热点函数
        hotspots = data_dict.get('hotspots', {})
        if hotspots:
            lines.append(OutputDefaults.HOTSPOTS_HEADER)
            lines.append(OutputDefaults.HOTSPOTS_SORT_HINT)
            lines.append("")

            top_symbol = hotspots.get('top_symbol')
            items = hotspots.get('items', [])

            if items:
                # 第一个热点 - 根据类型和占比添加标签
                first = items[0]
                first_self_pct = first.get('self_pct', 0) * 100

                if first.get('resource_tag') == 'LOCK':
                    # 锁竞争热点标记为 X0
                    lines.append(f"{AttentionFlag.X0} 锁竞争热点: {first.get('symbol', OutputDefaults.NA)}")
                    lines.append(f"  - Self: {first_self_pct:.2f}% | Inclusive: {first.get('inclusive_pct', 0)*100:.2f}%")
                    lines.append(f"  - Resource Tag: {first.get('resource_tag', OutputDefaults.NA)}")
                    lines.append("")
                elif first_self_pct > 40:
                    # 高占比热点标记为 X0
                    lines.append(f"{AttentionFlag.X0} 高占比热点: {first.get('symbol', OutputDefaults.NA)}")
                    lines.append(f"  - Self: {first_self_pct:.2f}% | Inclusive: {first.get('inclusive_pct', 0)*100:.2f}%")
                    lines.append(f"  - Resource Tag: {first.get('resource_tag', OutputDefaults.NA)}")
                    lines.append("")

                # 其他热点 - 根据占比添加标签
                start_idx = 1 if (first.get('resource_tag') == 'LOCK' or first_self_pct > 40) else 0
                for i, hs in enumerate(items[:CompositeDefaults.DEFAULT_TOP_HOTSPOTS], 1):
                    if i == 1 and start_idx == 1:
                        continue  # 已显示

                    self_pct = hs.get('self_pct', 0) * 100
                    tag_str = f" ({hs.get('resource_tag', OutputDefaults.NA)})" if hs.get('resource_tag') else ""

                    # 根据占比添加标签
                    if self_pct > 20:
                        lines.append(f"{AttentionFlag.X1} #{i} {hs.get('symbol', OutputDefaults.NA)}: {self_pct:.2f}%{tag_str}")
                    else:
                        lines.append(f"#{i} {hs.get('symbol', OutputDefaults.NA)}: {self_pct:.2f}%{tag_str}")

            lines.append("")

        # 调用链溯源
        call_chain = data_dict.get('call_chain')
        if call_chain:
            lines.append(OutputDefaults.CALL_CHAIN_HEADER)
            target = call_chain.get('target', OutputDefaults.NA)
            lines.append(f"{OutputDefaults.CALL_CHAIN_TARGET_PREFIX} {target}")
            lines.append("")

            convergence = call_chain.get('convergence_path')
            if convergence:
                # 调用链分析总是重要的，标记为 X0
                lines.append(f"{AttentionFlag.X0} 聚合调用链:")
                lines.append(f"  {convergence.get('description', OutputDefaults.NA)}")
                lines.append(f"  - 影响: {convergence.get('impact', OutputDefaults.NA)}")
                lines.append("")

            top_callers = call_chain.get('top_callers', [])
            if top_callers:
                lines.append("Top Callers:")
                for i, caller in enumerate(top_callers[:CompositeDefaults.DEFAULT_TOP_CALLERS], 1):
                    symbol = caller.get('symbol', OutputDefaults.NA)
                    ratio = caller.get('call_ratio', 0)
                    stack = caller.get('call_stack', [])
                    stack_str = " <- ".join(stack) if stack else OutputDefaults.ROOT
                    lines.append(f"  #{i} [{ratio*100:.2f}%] {stack_str}")
                lines.append("")

        # 根因分析
        root_cause = data_dict.get('root_cause')
        if root_cause:
            lines.append(OutputDefaults.ROOT_CAUSE_HEADER)
            lines.append("")
            lines.append(f"{AttentionFlag.X0} 第一推动力: {root_cause.get('primary_driver', OutputDefaults.NA)}")
            lines.append(f"  - 证据: {root_cause.get('evidence', OutputDefaults.NA)}")
            lines.append(f"  - 机制: {root_cause.get('mechanism', OutputDefaults.NA)}")
            lines.append(f"  - 受害者: {root_cause.get('victim', OutputDefaults.NA)}")
            lines.append("")

        # 建议操作
        recommendations = data_dict.get('recommendations', [])
        if recommendations:
            lines.append(f"{AttentionFlag.XA} {OutputDefaults.RECOMMENDATIONS_HEADER}")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        return lines

    def _render_sys_audit_v2(self, data: Any) -> List[str]:
        """
        渲染系统审计结果 - V2 强类型版本

        基于设计文档格式：
        ## [SYSTEM_AUDIT]
        ### 系统指纹 (System Fingerprint)
        ### 竞争矩阵 (Contention Matrix)
        ### 进程分层 (Process Hierarchy)
        ### 核心分布 (Core Distribution)
        ### 专家锚点 (Expert Anchors)
        ### 根因链 (Root Cause Chain)
        """
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []

        # 标题
        lines.append(OutputDefaults.SYS_AUDIT_TITLE)
        lines.append("> 策略: 自动降噪 + 危害排序，识别真瓶颈")
        lines.append("")

        # 系统指纹
        fingerprint = data_dict.get('system_fingerprint', {})
        # NOTE: PSI 和 Throttle 数据需要从 /proc/pressure/ 和 cgroup 读取
        # 当前未实现，暂时简化显示
        if fingerprint:
            pressure_state = fingerprint.get('pressure_state', 'NORMAL')
            if pressure_state != 'NORMAL':
                lines.append("### 系统指纹 (System Fingerprint)")
                lines.append("")
                lines.append(f"State: {pressure_state}")
                lines.append("")

        # 敏感进程事件检测
        sensitive_events = data_dict.get('sensitive_events', [])
        if sensitive_events:
            lines.append("### 特殊事件检测 (Sensitive Events)")
            lines.append("")
            for event in sensitive_events:
                flag = event.get('flag', '<X1>')
                category = event.get('category', '')
                message = event.get('message', '')
                count = event.get('count', 0)
                processes = event.get('processes', [])

                lines.append(f"{flag} [{category}] {message}")
                lines.append(f"  检测到 {count} 个相关进程:")
                for proc in processes[:5]:  # 最多显示5个
                    comm = proc.get('comm', '')
                    total = proc.get('total_cpu', 0)
                    kernel = proc.get('kernel_cpu', 0)
                    lines.append(f"    - {comm}: {total:.1f}% (sys: {kernel:.1f}%)")
                lines.append("")

        # Top N 按 Impact Score 排序显示
        top_by_total = data_dict.get('top_by_total_cpu', [])

        # 从配置读取显示阈值
        display_thresh = get_config().get_display_threshold()
        display_min = display_thresh.display_min
        sys_display_min = display_thresh.sys_display_min

        # 过滤并计算 Impact Score
        def _calc_impact_score(item):
            """计算 Impact Score（与 comm_top.py 一致）"""
            total = item.get('total_cpu', 0)
            kernel = item.get('kernel_cpu', 0)
            cv = item.get('cv', 0)
            mono = item.get('monopoly', 0)
            spawn_rate = item.get('spawn_rate', 0)
            diagnosis = item.get('diagnosis', '')

            # 基础分
            base_score = 0
            if diagnosis == DiagnosisType.BOTTLENECK:
                base_score = 100
            elif diagnosis == DiagnosisType.STORM:
                base_score = 50
            elif diagnosis == DiagnosisType.UNBALANCED:
                base_score = 20

            return base_score + (
                total * 0.5 +
                kernel * 0.8 +
                cv * 10 +
                mono * 5 +
                spawn_rate * 0.5
            )

        # 辅助函数：根据诊断类型确定 attention flag
        def _get_attention_flag(diagnosis: str, monopoly: float, spawn_rate: float) -> str:
            """根据诊断类型和指标确定 attention flag

            标记规则:
            - <X0>: BOTTLENECK 诊断（无论 Monopoly 值，只要是瓶颈就是关键问题）
            - <X1>: STORM 诊断（进程风暴）或 UNBALANCED 诊断（负载不均衡）
            """
            if diagnosis == DiagnosisType.BOTTLENECK:
                # BOTTLENECK 标记为 X0（关键瓶颈）
                return AttentionFlag.X0
            elif diagnosis == DiagnosisType.STORM:
                # STORM 标记为 X1
                return AttentionFlag.X1
            elif diagnosis == DiagnosisType.UNBALANCED:
                # UNBALANCED 标记为 X1
                return AttentionFlag.X1
            return ""

        # 过滤并计算分数
        filtered = []
        for item in top_by_total:
            total = item.get('total_cpu', 0)
            kernel = item.get('kernel_cpu', 0)
            if total > display_min or kernel > sys_display_min:
                score = _calc_impact_score(item)
                filtered.append((item, score))

        # 按 Impact Score 排序
        filtered.sort(key=lambda x: x[1], reverse=True)

        # 计算所有进程的总 CPU（用于统计隐藏进程）
        all_groups = top_by_total
        TOP_N_DISPLAY = 5  # 默认只显示 top 5
        shown_comms = {item.get('comm', '') for item, _ in filtered[:TOP_N_DISPLAY]}

        total_all_cpu = sum(item.get('total_cpu', 0) for item in all_groups)
        shown_cpu = sum(item.get('total_cpu', 0) for item in all_groups if item.get('comm', '') in shown_comms)
        hidden_cpu = total_all_cpu - shown_cpu

        if filtered:
            lines.append("### Top 进程 (按危害指数排序)")
            lines.append("")
            for i, (item, score) in enumerate(filtered[:TOP_N_DISPLAY], 1):
                comm = item.get('comm', 'N/A')
                total = item.get('total_cpu', 0)
                kernel = item.get('kernel_cpu', 0)
                pids = item.get('pid_count', 0)
                diagnosis = item.get('diagnosis', '')
                monopoly = item.get('monopoly', 0)
                spawn_rate = item.get('spawn_rate', 0)

                # 动态计算 attention flag（覆盖 item 中的值）
                attention = _get_attention_flag(diagnosis, monopoly, spawn_rate)
                attention_str = f"{attention}" if attention else ""

                diag_str = f" [{diagnosis}]" if diagnosis else ""
                lines.append(f"  {i:2d}. {attention_str:<4} {comm:20s}: {total:6.2f}% (sys: {kernel:6.2f}%) pids: {pids:4d} score: {score:.1f}{diag_str}")

            # Summary
            lines.append("")
            lines.append(f"  共显示 {min(TOP_N_DISPLAY, len(filtered))} / {len(filtered)} 个进程")
            lines.append(f"  未显示进程 CPU: {hidden_cpu:.2f}% / {total_all_cpu:.2f}%")
            lines.append("")

        # 核心分布 - 只有存在不均衡或饱和核心时才显示
        core_dist = data_dict.get('core_distribution', {})
        if core_dist:
            imbalance = core_dist.get('imbalance_level', ImbalanceLevel.NORMAL)
            saturated = core_dist.get('saturated_cores', [])

            # 只有存在异常时才显示
            if imbalance != ImbalanceLevel.NORMAL or saturated:
                lines.append(OutputDefaults.CORE_DISTRIBUTION_HEADER)
                lines.append("")

                # 根据不均衡程度确定标签
                if imbalance in [ImbalanceLevel.CRITICAL, ImbalanceLevel.HIGH]:
                    attention = AttentionFlag.X0
                else:
                    attention = AttentionFlag.X1

                lines.append(f"{attention} 负载不均衡:")
                lines.append(f"  - Imbalance Level: {imbalance}")
                if saturated:
                    lines.append(f"  {AttentionFlag.X0} Saturated Cores: {', '.join(map(str, saturated))}")
                lines.append("")

                top_saturated = core_dist.get('top_saturated', [])
                if top_saturated:
                    lines.append("Top Saturated:")
                    for i, core in enumerate(top_saturated[:5], 1):
                        cpu_id = core.get('cpu_id', 'N/A')
                        total = core.get('total_util', 0)
                        kernel = core.get('kernel_util', 0)
                        lines.append(f"  #{i} CPU {cpu_id}: {total:.2f}% (usr: {total-kernel:.2f}%)")
                    lines.append("")

        # 异常检测 - 只有检测到异常时才显示
        anomaly = data_dict.get('anomaly_summary', {})
        if anomaly and anomaly.get('mutation_detected'):
            lines.append(OutputDefaults.ANOMALY_DETECTION_HEADER)
            lines.append("")
            lines.append(f"Mutation Detected! Count: {anomaly.get('anomalies_count', 0)}")
            lines.append("")

        # 专家锚点
        anchors = data_dict.get('expert_anchors', [])
        if anchors:
            lines.append(OutputDefaults.EXPERT_ANCHORS_HEADER)
            lines.append("")
            for anchor in anchors:
                anchor_type = anchor.get('type', 'N/A')
                target = anchor.get('target', 'N/A')

                # 根据锚点类型确定标签
                if anchor_type in ['NOISY_NEIGHBOR', 'QUOTA_VICTIM', 'MEMORY_PRESSURE']:
                    attention = AttentionFlag.X0
                else:
                    attention = AttentionFlag.X1

                lines.append(f"{attention} !! DETECTED_{anchor_type}: {target} !!")
                lines.append(f"  - {anchor.get('description', 'N/A')}")
                lines.append(f"  - 影响: {anchor.get('impact', 'N/A')}")
                if anchor.get('recommendation'):
                    lines.append(f"  {AttentionFlag.XA} 建议: {anchor.get('recommendation')}")
                lines.append("")

        # 根因链
        root_chain = data_dict.get('root_cause_chain')
        if root_chain:
            tree_branch = OutputDefaults.TREE_BRANCH
            tree_end = OutputDefaults.TREE_END
            lines.append(OutputDefaults.ROOT_CAUSE_CHAIN_HEADER)
            lines.append("")
            attention = root_chain.get('attention_flag', '')
            lines.append(f"{attention} 第一推动力: {root_chain.get('primary_driver', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 现象: {root_chain.get('phenomenon', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 影响: {root_chain.get('impact', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 受害者: {root_chain.get('victim', OutputDefaults.NA)}")
            lines.append(f"  {tree_end} 建议: {root_chain.get('recommendation', OutputDefaults.NA)}")
            lines.append("")

        # 建议操作
        recommendations = data_dict.get('recommendations', [])
        if recommendations:
            lines.append(f"{AttentionFlag.XA} 后续操作:")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        return lines


class TextOutputAdapter:
    """文本输出适配器 - 模板化版本

    自动根据 Output 对象的 _template_config 选择模板进行渲染
    """

    def __init__(self, max_width: int = 120):
        self.max_width = max_width
        self.templates = {
            "simple_list": SimpleListTemplate(),
            "key_value": KeyValueTemplate(),
            "table": TableTemplate(),
            "nested": NestedTemplate(),
            "custom": CustomTemplate(),
        }

    def format_output(self, obj: Any) -> str:
        """将输出对象转换为文本格式"""
        if not is_dataclass(obj):
            return str(obj)

        data = asdict(obj)

        # 获取风险信息
        risk_info = data.get('_risk', {})
        risk_lines = self._format_risk(risk_info)

        # 获取模板配置
        template_config = data.get('_template_config')
        if template_config is None:
            # 尝试从对象属性获取(未通过 dataclass field 暴露的)
            template_config = getattr(obj, '_template_config', None)

        # 组合输出
        lines = []
        if risk_lines:
            lines.extend(risk_lines)

        # 使用模板渲染数据
        if template_config:
            template_type = template_config.get('template_type', 'simple_list')
            template = self.templates.get(template_type)
            if template:
                from ..core.output_models import TemplateConfig
                config = TemplateConfig(**template_config)
                data_lines = template.render(obj, config)
                lines.extend(data_lines)
            else:
                lines.append(f"[ERROR] Unknown template type: {template_type}")
        else:
            # 无模板配置,使用通用格式
            lines.append("(No template configuration)")

        # 检查截断提示
        trunc_hint = self._check_truncation(data)
        if trunc_hint:
            lines.append(trunc_hint)

        return "\n".join(lines)

    def _format_table_border(self, widths: List[int], position: str = "middle") -> str:
        """格式化表格边框

        Args:
            widths: 各列宽度
            position: 位置 (top/middle/bottom)
        """
        if position == "top":
            left, right, cross = OutputDefaults.TABLE_CORNER_TL, OutputDefaults.TABLE_CORNER_TR, OutputDefaults.TABLE_T_DOWN
        elif position == "bottom":
            left, right, cross = OutputDefaults.TABLE_CORNER_BL, OutputDefaults.TABLE_CORNER_BR, OutputDefaults.TABLE_T_UP
        else:
            left, right, cross = OutputDefaults.TABLE_T_RIGHT, OutputDefaults.TABLE_T_LEFT, OutputDefaults.TABLE_CROSS

        parts = [left]
        for i, w in enumerate(widths):
            parts.append(OutputDefaults.TABLE_HLINE * (w + 2))
            if i < len(widths) - 1:
                parts.append(cross)
        parts.append(right)
        return "".join(parts)

    def _format_risk(self, risk: Dict) -> List[str]:
        """格式化风险信息

        确保 message 中的 attention tags (<X0>, <X1>, <XA>) 被正确显示。
        如果 message 中已包含 attention tags，则直接显示。
        """
        lines = []
        if not risk:
            return lines

        level = risk.get('level', 'none')
        if level == 'none':
            return lines

        message = risk.get('message', '')
        hint = risk.get('hint', '')

        # 如果 message 中已包含 attention tags，直接显示
        # 否则根据 level 添加前缀
        if level == 'critical':
            if AttentionFlag.X0 not in message and AttentionFlag.X1 not in message:
                message = f"{AttentionFlag.X0} {message}"
            lines.append(f"{RiskDisplayDefaults.RISK_CRITICAL_LABEL} {message}")
        elif level == 'warning':
            if AttentionFlag.X0 not in message and AttentionFlag.X1 not in message:
                message = f"{AttentionFlag.X1} {message}"
            lines.append(f"{RiskDisplayDefaults.RISK_WARNING_LABEL} {message}")
        else:
            lines.append(f"{RiskDisplayDefaults.RISK_INFO_LABEL} {message}")

        if hint:
            # 确保 hint 也有 <XA> 标签
            if AttentionFlag.XA not in hint:
                hint = f"{AttentionFlag.XA} {hint}"
            lines.append(f"  → hint: {hint}")

        return lines

    def _check_truncation(self, data: Dict) -> Optional[str]:
        """检查列表是否被截断,如果被截断返回提示信息"""
        summary = data.get('summary', {})
        if not summary:
            return None

        # 从 TemplateConfig 获取截断配置
        template_config = data.get('_template_config', {})
        total_field = template_config.get('total_field')
        shown_field = template_config.get('shown_field')

        # 只有在配置了这两个字段时才显示截断提示
        if total_field and shown_field:
            total = summary.get(total_field, 0)
            shown = summary.get(shown_field, 0)
            if total > shown:
                return f"# ... {total - shown} more items (use --top-n to show more)"

        return None
