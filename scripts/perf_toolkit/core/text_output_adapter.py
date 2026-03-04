#!/usr/bin/env python3
"""Text Output Adapter - 模板化文本输出系统"""

import sys
from pathlib import Path
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import (
    OutputDefaults, Thresholds, AttentionFlag,
    ImbalanceLevel, CompositeDefaults, RiskDisplayDefaults,
    DiagnosisType
)
from perf_toolkit.core.config_loader import get_config
from perf_toolkit.core.callchain_formatter import CallChainFormatter


def _get_attr(item: Any, field: str, default: Any = None) -> Any:
    """通用属性获取：支持 dict 和 dataclass"""
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def _calc_impact_score(item: Dict[str, Any]) -> float:
    total = item.get('total_cpu', 0)
    kernel = item.get('kernel_cpu', 0)
    cv = item.get('cv', 0)
    mono = item.get('monopoly', 0)
    spawn_rate = item.get('spawn_rate', 0)
    diagnosis = item.get('diagnosis', '')

    base_score = 0
    if diagnosis == DiagnosisType.BOTTLENECK:
        base_score = 100
    elif diagnosis == DiagnosisType.STORM:
        base_score = 50
    elif diagnosis == DiagnosisType.UNBALANCED:
        base_score = 20

    return base_score + (total * 0.5 + kernel * 0.8 + cv * 10 + mono * 5 + spawn_rate * 0.5)


def _get_attention_flag(diagnosis: str, monopoly: float, spawn_rate: float) -> str:
    if diagnosis == DiagnosisType.BOTTLENECK:
        return AttentionFlag.X0
    elif diagnosis in (DiagnosisType.STORM, DiagnosisType.UNBALANCED):
        return AttentionFlag.X1
    return ""


def _get_time_range_and_change(it: Any) -> Tuple[str, str]:
    """提取时间范围和变化信息（支持 dict 和 dataclass）"""
    tr = _get_attr(it, 'time_range')
    ch = _get_attr(it, 'utilization_change')
    
    if tr is None:
        s, e = _get_attr(it, 'time_range_start', ''), _get_attr(it, 'time_range_end', '')
        tr = f"{s} - {e}" if s and e else 'N/A'
    if ch is None:
        p = _get_attr(it, 'prev_util', 0) * 100
        c = _get_attr(it, 'curr_util', 0) * 100
        n = _get_attr(it, 'next_util', 0) * 100
        ch = f"{p:.1f}% -> {c:.1f}% -> {n:.1f}%"
    
    return tr, ch


class Template(ABC):
    @abstractmethod
    def render(self, data: Any, config: Any) -> List[str]:
        pass

    def _get_list_data(self, data: Any, list_field: str) -> List[Any]:
        data_dict = asdict(data) if is_dataclass(data) else data
        return data_dict.get(list_field, [])

    def _format_field_value(self, item: Any, field: str) -> str:
        value = _get_attr(item, field, "N/A")
        if isinstance(value, list):
            if field == "caller_stack":
                return " <- ".join(str(v) for v in value) if value else "(root)"
            return ", ".join(str(v) for v in value)
        return str(value) if value is not None else "N/A"

    def _format_process_line(self, item: Any) -> str:
        comm, pid = _get_attr(item, 'comm', 'N/A'), _get_attr(item, 'pid', 'N/A')
        total = _get_attr(item, 'total_cpu_util', '0.00%')
        kernel = _get_attr(item, 'kernel_cpu_util', '0.00%')
        return f"{comm}({pid}) {total}/{kernel}"

    def _get_empty_lines(self, config: Any, lines: List[str]) -> List[str]:
        msg = config.empty_message if config.empty_message else 'No data found'
        lines.append(f"({msg})")
        return lines


class SimpleListTemplate(Template):
    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []
        if config.header:
            lines.append(config.header)
        if not items:
            return self._get_empty_lines(config, lines)
        for i, item in enumerate(items, 1):
            if config.list_field == "processes":
                line = self._format_process_line(item)
            elif config.list_field == "attributions":
                line = self._format_attribution_line(item, i)
            elif config.list_field == "path_clusters":
                line = self._format_path_cluster_line(item, i, config)
            else:
                values = [self._format_field_value(item, f) for f in config.display_fields]
                prefix = config.index_format.format(index=i) if config.index_format else f"#{i}"
                line = f"{prefix} " + " ".join(values)
            lines.append(line)
        return lines

    def _format_path_cluster_line(self, item: Any, index: int, config: Any) -> str:
        weight, total = _get_attr(item, 'weight', 0), _get_attr(item, 'total_weight', 1)
        duration, path = _get_attr(item, 'duration', 1), _get_attr(item, 'path_signature', 'N/A')
        ratio_pct = (weight / total * 100) if total > 0 else 0
        cpu_util = (weight / duration * 100) if duration > 0 else 0
        prefix = config.index_format.format(index=index) if config.index_format else f"#{index}"
        return f"{prefix} {ratio_pct:.2f}% {cpu_util:.2f}% {path}"

    def _format_attribution_line(self, item: Any, index: int) -> str:
        ratio = self._format_field_value(item, "ratio_of_target_pct")
        stack = self._format_field_value(item, "caller_stack")
        return f"#{index} [{ratio}] {stack}"


class KeyValueTemplate(Template):
    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []
        if config.header:
            lines.append(config.header)
        if not items:
            return self._get_empty_lines(config, lines)
        for item in items:
            values = [self._format_field_value(item, f) for f in config.display_fields]
            lines.append(" ".join(values))
        return lines


class TableTemplate(Template):
    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []
        if config.header:
            lines.append(config.header)
        if not items:
            return self._get_empty_lines(config, lines)
        for item in items:
            if config.list_field == "anomalies":
                lines.append(self._format_anomaly_line(item))
            elif config.list_field == "windows":
                lines.append(self._format_window_line(item))
            else:
                values = [self._format_field_value(item, f) for f in config.display_fields]
                lines.append(" ".join(values))
        return lines

    def _format_anomaly_line(self, item: Any) -> str:
        anomaly_type = _get_attr(item, 'type', 'N/A')
        cpu_id = _get_attr(item, 'cpu_id', 'N/A')
        severity = _get_attr(item, 'severity', 'unknown')
        time_range, change = _get_time_range_and_change(item)
        if isinstance(time_range, dict):
            time_range = f"{time_range.get('start', '')} - {time_range.get('end', '')}"
        return f"{anomaly_type} cpu={cpu_id} time={time_range} change={change} severity={severity}"

    def _format_window_line(self, item: Any) -> str:
        cpu_id = _get_attr(item, 'cpu_id', 'N/A')
        start = _get_attr(item, 'start_time', 'N/A')
        end = _get_attr(item, 'end_time', 'N/A')
        util = _get_attr(item, 'utilization', 'N/A')
        weight = _get_attr(item, 'weight', 0)
        return f"cpu={cpu_id} start={start} end={end} util={util} weight={weight:.4f}"


class NestedTemplate(Template):
    def render(self, data: Any, config: Any) -> List[str]:
        items = self._get_list_data(data, config.list_field)
        lines = []
        if config.header:
            lines.append(config.header)
        if not items:
            return self._get_empty_lines(config, lines)
        for item in items:
            lines.extend(self._format_trace_item(item))
        return lines

    def _format_trace_item(self, item: Any) -> List[str]:
        target = _get_attr(item, 'target', 'N/A')
        target_ratio = _get_attr(item, 'target_ratio_pct', '0%')
        attributions = _get_attr(item, 'attributions', [])
        lines = [f">>> {target} ({target_ratio})"]
        try:
            target_ratio_val = float(target_ratio.rstrip('%'))
        except (ValueError, AttributeError):
            target_ratio_val = 0.0
        for i, attr in enumerate(attributions, 1):
            stack = _get_attr(attr, 'caller_stack', [])
            attr_ratio = _get_attr(attr, 'ratio_of_target_pct', '0%')
            try:
                attr_ratio_val = float(attr_ratio.rstrip('%'))
            except (ValueError, AttributeError):
                attr_ratio_val = 0.0
            total_ratio = target_ratio_val * attr_ratio_val / 100
            stack_str = " <- ".join(str(s) for s in stack) if stack else "(root)"
            lines.append(f"  #{i} [{total_ratio:.2f}%] {stack_str}")
        return lines


class CustomTemplate(Template):
    # Severity 图标映射
    SEVERITY_ICONS = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🟢",
    }

    def __init__(self):
        self.renderers = {
            "bottleneck": self._render_bottleneck,
            "cpu_usage": self._render_cpu_usage,
            "sys_audit_renderer": self._render_sys_audit,
            "bottleneck_trace_renderer": self._render_bottleneck_trace,
            "storm_trace_renderer": self._render_storm_trace,
            "sys_audit_renderer_v2": self._render_sys_audit_v2,
        }

    def render(self, data: Any, config: Any) -> List[str]:
        renderer = self.renderers.get(config.custom_renderer)
        if renderer:
            return renderer(data)
        return [f"[ERROR] Unknown custom renderer: {config.custom_renderer}"]

    def _render_bottleneck(self, data: Any) -> List[str]:
        data_dict = asdict(data) if is_dataclass(data) else data
        special_data = data_dict.get('data', {})
        lines = []
        verdict, events = special_data.get('verdict', 'N/A'), special_data.get('events', [])
        high_cpu, high_sys = special_data.get('high_cpu_cores', []), special_data.get('high_sys_cores', [])
        threshold = special_data.get('threshold', 80)
        sys_threshold, max_load = threshold + 10, special_data.get('max_core_load', {})
        limit_info = special_data.get('limit_info', {})
        lines.append(f"Verdict: {','.join(events)}" if len(events) > 1 else f"Verdict: {verdict}")
        if high_cpu:
            lines.append(f"CPU High: {','.join(map(str, high_cpu))} (total>{threshold}%)")
        if high_sys:
            lines.append(f"CPU Sys High: {','.join(map(str, high_sys))} (sys>{sys_threshold}%)")
        if max_load:
            lines.append(f"Max Core Load: CPU {max_load.get('cpu_id', 'N/A')} = {max_load.get('load', 'N/A')}")
        if limit_info:
            cores = limit_info.get('cpu_limit_cores', 0)
            if cores > 0:
                lines.append(f"CPU Limit: {cores}c (detected={limit_info.get('cpu_limit_detected', False)})")
        return lines

    def _render_cpu_usage(self, data: Any) -> List[str]:
        data_dict = asdict(data) if is_dataclass(data) else data
        special_data = data_dict.get('data', {})
        util = special_data.get('cpu_utilization', {})
        return [
            f"Target: {special_data.get('target', 'System')}",
            f"  Total: {util.get('total_pct', 'N/A')}",
            f"  User:  {util.get('user_pct', 'N/A')}",
            f"  Kernel: {util.get('kernel_pct', 'N/A')}",
        ]

    def _render_sys_audit(self, data: Any) -> List[str]:
        data_dict = asdict(data) if is_dataclass(data) else data
        diagnosis, details, lines = data_dict.get('diagnosis', {}), data_dict.get('details', {}), []
        primary = diagnosis.get('primary_suspect')
        if primary:
            lines.extend([
                f"Primary Suspect: {primary.get('comm', 'N/A')}",
                f"  CPU: {primary.get('total_cpu', 0):.2f}%",
                f"  Diagnosis: {primary.get('diagnosis', 'N/A')}",
            ])
            if primary.get('monopoly'):
                lines.append(f"  Monopoly: {primary.get('monopoly'):.2f}")
        else:
            lines.append("Primary Suspect: None detected")
        secondary = diagnosis.get('secondary_loads', [])
        if secondary:
            lines.append(f"\nSecondary Loads ({len(secondary)}):")
            for load in secondary[:3]:
                lines.append(f"  - {load.get('comm', 'N/A')}: {load.get('total_cpu', 0):.2f}% ({load.get('diagnosis', 'N/A')})")
        if diagnosis.get('mutation_detected'):
            lines.append(f"\nMutation Detected at: {diagnosis.get('mutation_time', 'N/A')}")
        saturated = diagnosis.get('saturated_cores', [])
        if saturated:
            lines.append(f"\nSaturated Cores: {', '.join(map(str, saturated[:5]))}")
        root_cause = diagnosis.get('root_cause_analysis', '')
        if root_cause:
            lines.append(f"\nRoot Cause: {root_cause}")
        lines.append("\n=== Analysis Details ===")
        anomalies = details.get('anomalies', {})
        if anomalies:
            lines.append(f"Anomalies: {anomalies.get('anomalies_count', 0)} detected")
            if anomalies.get('mutation_detected'):
                lines.append("  - Mutation detected")
        core_dist = details.get('core_distribution', {})
        if core_dist:
            lines.append(f"Core Distribution: {core_dist.get('core_count', 0)} cores, imbalance={core_dist.get('imbalance_level', 'N/A')}")
        comm_top = details.get('comm_top', {})
        if comm_top:
            lines.append(f"Process Groups: {comm_top.get('groups_count', 0)} shown, {comm_top.get('folded_count', 0)} folded")
        return lines

    def _render_storm_trace(self, data: Any) -> List[str]:
        data_dict = asdict(data) if is_dataclass(data) else data
        lines, target_comm = [], data_dict.get('target_comm', 'N/A')
        lines.extend([f"Target Process: {target_comm}", ""])
        storm = data_dict.get('storm_analysis', {})
        if storm:
            lines.extend([
                "=== Storm Analysis ===",
                f"  Spawn Rate: {storm.get('spawn_rate', 0):.1f} procs/sec",
                f"  Severity: {storm.get('severity', 'N/A')}",
                f"  PID Count: {storm.get('pid_count', 0)}",
                f"  Total CPU: {storm.get('total_cpu', 0):.2f}%",
            ])
        lifecycle = data_dict.get('lifecycle', {})
        if lifecycle:
            lines.extend(["", "=== Lifecycle Analysis ===",
                         f"  Sample Count: {lifecycle.get('sample_count', 0)}",
                         f"  Time Range: {lifecycle.get('time_range_sec', 0):.1f} sec"])
            unique_pids = lifecycle.get('unique_pids', [])
            if unique_pids:
                lines.append(f"  Unique PIDs: {len(unique_pids)}")
        callers = data_dict.get('callers')
        if callers:
            lines.extend(["", "=== Callers ===", f"Target: {callers.get('target', 'N/A')}"])
            caller_list = callers.get('callers', [])
            if caller_list:
                lines.append("\nTop Callers:")
                for i, caller in enumerate(caller_list[:3], 1):
                    lines.append(f"  #{i} {caller.get('symbol', 'N/A')}: {caller.get('call_ratio', 0):.1f}%")
        return lines

    def _render_bottleneck_trace(self, data: Any) -> List[str]:
        """
        渲染 bottleneck-trace 精简输出 - 仅 GLOBAL 完整调用链
        """
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []
        
        # 只保留 BIDIRECTIONAL_VIEW (GLOBAL 完整路径)
        lines.extend(self._build_bidirectional_view_section(data_dict))
        
        return lines

    def _build_bidirectional_view_section(self, data: Dict) -> List[str]:
        """构建 [BIDIRECTIONAL_VIEW] 段"""
        lines = []
        bidirectional_view = data.get('bidirectional_view', '')
        
        if bidirectional_view:
            # bidirectional_view 已经包含标题，直接追加
            lines.append("")
            lines.append(bidirectional_view)
            lines.append("")
        
        return lines

    def _build_entity_distribution_section(self, data: Dict) -> List[str]:
        """构建 [ENTITY_DISTRIBUTION_MATRIX] 段"""
        lines = []
        lines.append("## [ENTITY_DISTRIBUTION_MATRIX]")
        lines.append("")
        
        # 表头
        lines.append("| Comm_Group | Count | Incl_Saliency | Excl_Saliency | Core_Affinity | Throttle_Rate |")
        lines.append("|------------|-------|---------------|---------------|---------------|---------------|")
        
        # 数据行
        entity_distribution = data.get('entity_distribution', [])
        for entity in entity_distribution:
            incl_saliency = entity.get('incl_saliency', 0)
            excl_saliency = entity.get('excl_saliency', 0)
            is_bottleneck = incl_saliency > 0.5 or excl_saliency > 0.5
            
            comm = entity.get('comm', 'N/A')
            comm_str = f"**`{comm}`**" if is_bottleneck else f"`{comm}`"
            
            count_str = str(entity.get('count', 0))
            
            incl_str = f"**{incl_saliency:.2f}**" if (is_bottleneck and incl_saliency > Thresholds.MONOPOLY_HIGH) else f"{incl_saliency:.2f}"
            excl_str = f"**{excl_saliency:.2f}**" if (is_bottleneck and excl_saliency > Thresholds.MONOPOLY_HIGH) else f"{excl_saliency:.2f}"
            
            affinity = entity.get('core_affinity', 'N/A')
            affinity_str = f"**{affinity}**" if is_bottleneck else affinity
            
            throttle_rate = entity.get('throttle_rate', 0)
            throttle_str = f"**{throttle_rate:.1f}%**" if (is_bottleneck and throttle_rate > Thresholds.THROTTLE_RATE_MIN) else f"{throttle_rate:.1f}%"
            
            row = f"| {comm_str} | {count_str} | {incl_str} | {excl_str} | {affinity_str} | {throttle_str} |"
            lines.append(row)
        
        if not entity_distribution:
            lines.append("| *(无数据)* | - | - | - | - | - |")
        
        lines.append("")
        return lines

    def _build_convergence_trace_section(self, data: Dict) -> List[str]:
        """构建 [CONVERGENCE_TRACE] 段"""
        lines = []
        lines.append("## [CONVERGENCE_TRACE]")
        lines.append("")
        
        # COMMON_HOTSPOT
        common_hotspot = data.get('common_hotspot', '')
        common_hotspot_weight = data.get('common_hotspot_weight', 0)
        if common_hotspot:
            lines.append(f"### **COMMON_HOTSPOT: `{common_hotspot}` {common_hotspot_weight:.1f}%**")
            lines.append("")
            lines.append("*所有聚类共享的热点符号，通常是瓶颈汇聚点*")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 每个 Cluster
        clusters = data.get('clusters', [])
        for cluster in clusters:
            cluster_id = cluster.get('cluster_id', 'N/A')
            lines.append(f"#### **[{cluster_id}]**")
            lines.append("")
            
            # 路径展示：comm -> func1 -> func2 -> **[HOTSPOT]**
            path = cluster.get('path', [])
            hotspot = cluster.get('hotspot', 'N/A')
            weight = cluster.get('weight', 0)
            direction = cluster.get('direction', 'top_down')
            path_str = self._format_call_path(path, hotspot, direction=direction, ratio=weight)
            lines.append(path_str)
            lines.append("")
            
            # Characteristic 标签
            characteristic = cluster.get('characteristic', 'N/A')
            weight_val = cluster.get('weight', 0) or 0
            lines.append(f"* **Characteristic**: `{characteristic}`")
            lines.append(f"* **Weight**: {weight_val:.1f}%（占总样本比例）")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return lines

    def _format_call_path(self, path: List[str], hotspot: str, direction: str = "top_down", ratio: Optional[float] = None) -> str:
        """格式化调用路径: `comm` → `func1` → `func2` → **[HOTSPOT]**
        
        Args:
            path: 调用路径 (函数名列表)
            hotspot: 热点函数名
            direction: 调用链方向 "top_down" 或 "bottom_up"
            ratio: 占比百分比 (可选)，如果提供则显示在路径前
        """
        path_str = CallChainFormatter.format(
            path=path,
            hotspot=hotspot,
            direction=direction,
            style="markdown"
        )
        
        if ratio is not None and ratio > 0:
            return f"{ratio:.1f}%  {path_str}"
        return path_str

    def _build_correlation_flags_section(self, data: Dict) -> List[str]:
        """构建 [CORRELATION_FLAGS] 段"""
        lines = []
        lines.append("## [CORRELATION_FLAGS]")
        lines.append("")
        lines.append("*跨维度关联检测，自动标记系统性问题*")
        lines.append("")
        
        correlation_flags = data.get('correlation_flags', [])
        for flag in correlation_flags:
            severity = flag.get('severity', 'info').lower()
            icon = self.SEVERITY_ICONS.get(severity, "⚪")
            flag_type = flag.get('flag_type', 'N/A')
            target = flag.get('target', 'N/A')
            message = flag.get('message', '')
            flag_line = f"{icon} **[FLAG: {flag_type}]** : `{target}` {message}"
            lines.append(flag_line)
        
        if not correlation_flags:
            lines.append("*(未检测到关联标志)*")
        
        lines.append("")
        return lines

    def _build_data_summary_section(self, data: Dict) -> List[str]:
        """构建 [DATA_SUMMARY] 段"""
        lines = []
        lines.append("## [DATA_SUMMARY]")
        lines.append("")
        lines.append("*诊断会话元数据摘要*")
        lines.append("")
        
        # YAML 格式
        lines.append("```yaml")
        lines.append(f"total_pids: {data.get('total_pids', 0)}")
        lines.append(f"total_sys_cpu: {data.get('total_sys_cpu', 0.0):.1f}")
        
        top_bottlenecks = data.get('top_bottlenecks', [])
        top_bottleneck_str = ", ".join(f"`{b}`" for b in top_bottlenecks[:3])
        lines.append(f"top_bottleneck: {top_bottleneck_str if top_bottleneck_str else 'N/A'}")
        
        lines.append(f"duration_sec: {data.get('duration_sec', 0.0):.1f}")
        lines.append(f"sample_count: {data.get('sample_count', 0)}")
        
        # 数据质量评估
        quality = self._assess_data_quality(data)
        lines.append(f"data_quality: \"{quality}\"")
        
        lines.append("```")
        lines.append("")
        return lines

    def _assess_data_quality(self, data: Dict) -> str:
        """评估数据质量: good | fair | poor"""
        sample_count = data.get('sample_count', 0)
        if sample_count < 1000:
            return "poor"
        elif sample_count < 5000:
            return "fair"
        else:
            return "good"

    def _render_sys_audit_v2(self, data: Any) -> List[str]:
        data_dict = asdict(data) if is_dataclass(data) else data
        lines = []
        lines.append(OutputDefaults.SYS_AUDIT_TITLE)
        lines.append("> 策略: 自动降噪 + 危害排序，识别真瓶颈")
        lines.append("")
        fingerprint = data_dict.get('system_fingerprint', {})
        if fingerprint:
            pressure_state = fingerprint.get('pressure_state', 'NORMAL')
            if pressure_state != 'NORMAL':
                lines.extend(["### 系统指纹 (System Fingerprint)", "", f"State: {pressure_state}", ""])
        sensitive_events = data_dict.get('sensitive_events', [])
        if sensitive_events:
            lines.append("### 特殊事件检测 (Sensitive Events)")
            lines.append("")
            for event in sensitive_events:
                flag = event.get('flag', '<X1>')
                category, message, count = event.get('category', ''), event.get('message', ''), event.get('count', 0)
                processes = event.get('processes', [])
                lines.append(f"{flag} [{category}] {message}")
                lines.append(f"  检测到 {count} 个相关进程:")
                for proc in processes[:5]:
                    comm = proc.get('comm', '')
                    total, kernel = proc.get('total_cpu', 0), proc.get('kernel_cpu', 0)
                    lines.append(f"    - {comm}: {total:.1f}% (sys: {kernel:.1f}%)")
                lines.append("")
        top_by_total = data_dict.get('top_by_total_cpu', [])
        display_thresh = get_config().get_display_threshold()
        display_min, sys_display_min = display_thresh.display_min, display_thresh.sys_display_min
        filtered = []
        for item in top_by_total:
            total, kernel = item.get('total_cpu', 0), item.get('kernel_cpu', 0)
            if total > display_min or kernel > sys_display_min:
                filtered.append((item, _calc_impact_score(item)))
        filtered.sort(key=lambda x: x[1], reverse=True)
        TOP_N_DISPLAY = 5
        shown_comms = {item.get('comm', '') for item, _ in filtered[:TOP_N_DISPLAY]}
        total_all_cpu = sum(item.get('total_cpu', 0) for item in top_by_total)
        shown_cpu = sum(item.get('total_cpu', 0) for item in top_by_total if item.get('comm', '') in shown_comms)
        hidden_cpu = total_all_cpu - shown_cpu
        if filtered:
            lines.append("### Top 进程 (按危害指数排序)")
            lines.append("")
            for i, (item, score) in enumerate(filtered[:TOP_N_DISPLAY], 1):
                comm = item.get('comm', 'N/A')
                total, kernel = item.get('total_cpu', 0), item.get('kernel_cpu', 0)
                pids, diagnosis = item.get('pid_count', 0), item.get('diagnosis', '')
                monopoly, spawn_rate = item.get('monopoly', 0), item.get('spawn_rate', 0)
                attention = _get_attention_flag(diagnosis, monopoly, spawn_rate)
                attention_str = f"{attention}" if attention else ""
                diag_str = f" [{diagnosis}]" if diagnosis else ""
                lines.append(f"  {i:2d}. {attention_str:<4} {comm:20s}: {total:6.2f}% (sys: {kernel:6.2f}%) pids: {pids:4d} score: {score:.1f}{diag_str}")
            lines.append("")
            lines.append(f"  共显示 {min(TOP_N_DISPLAY, len(filtered))} / {len(filtered)} 个进程")
            lines.append(f"  未显示进程 CPU: {hidden_cpu:.2f}% / {total_all_cpu:.2f}%")
            lines.append("")
        core_dist = data_dict.get('core_distribution', {})
        if core_dist:
            imbalance = core_dist.get('imbalance_level', ImbalanceLevel.NORMAL)
            saturated = core_dist.get('saturated_cores', [])
            if imbalance != ImbalanceLevel.NORMAL or saturated:
                lines.append(OutputDefaults.CORE_DISTRIBUTION_HEADER)
                lines.append("")
                attention = AttentionFlag.X0 if imbalance in (ImbalanceLevel.CRITICAL, ImbalanceLevel.HIGH) else AttentionFlag.X1
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
                        total, kernel = core.get('total_util', 0), core.get('kernel_util', 0)
                        lines.append(f"  #{i} CPU {cpu_id}: {total:.2f}% (usr: {total-kernel:.2f}%)")
                    lines.append("")
        anomaly = data_dict.get('anomaly_summary', {})
        if anomaly and anomaly.get('mutation_detected'):
            lines.extend([OutputDefaults.ANOMALY_DETECTION_HEADER, "", f"Mutation Detected! Count: {anomaly.get('anomalies_count', 0)}", ""])
        anchors = data_dict.get('expert_anchors', [])
        if anchors:
            lines.append(OutputDefaults.EXPERT_ANCHORS_HEADER)
            lines.append("")
            for anchor in anchors:
                anchor_type, target = anchor.get('type', 'N/A'), anchor.get('target', 'N/A')
                attention = AttentionFlag.X0 if anchor_type in ('NOISY_NEIGHBOR', 'QUOTA_VICTIM', 'MEMORY_PRESSURE') else AttentionFlag.X1
                lines.append(f"{attention} !! DETECTED_{anchor_type}: {target} !!")
                lines.append(f"  - {anchor.get('description', 'N/A')}")
                lines.append(f"  - 影响: {anchor.get('impact', 'N/A')}")
                if anchor.get('recommendation'):
                    lines.append(f"  {AttentionFlag.XA} 建议: {anchor.get('recommendation')}")
                lines.append("")
        root_chain = data_dict.get('root_cause_chain')
        if root_chain:
            tree_branch, tree_end = OutputDefaults.TREE_BRANCH, OutputDefaults.TREE_END
            lines.append(OutputDefaults.ROOT_CAUSE_CHAIN_HEADER)
            lines.append("")
            attention = root_chain.get('attention_flag', '')
            lines.append(f"{attention} 第一推动力: {root_chain.get('primary_driver', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 现象: {root_chain.get('phenomenon', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 影响: {root_chain.get('impact', OutputDefaults.NA)}")
            lines.append(f"  {tree_branch} 受害者: {root_chain.get('victim', OutputDefaults.NA)}")
            lines.append(f"  {tree_end} 建议: {root_chain.get('recommendation', OutputDefaults.NA)}")
            lines.append("")
        recommendations = data_dict.get('recommendations', [])
        if recommendations:
            lines.append(f"{AttentionFlag.XA} 后续操作:")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        return lines


class TextOutputAdapter:
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
        if not is_dataclass(obj):
            return str(obj)
        data = asdict(obj)
        risk_info = data.get('_risk', {})
        risk_lines = self._format_risk(risk_info)
        template_config = data.get('_template_config')
        if template_config is None:
            template_config = getattr(obj, '_template_config', None)
        lines = []
        if risk_lines:
            lines.extend(risk_lines)
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
            lines.append("(No template configuration)")
        trunc_hint = self._check_truncation(data)
        if trunc_hint:
            lines.append(trunc_hint)
        return "\n".join(lines)

    def _format_table_border(self, widths: List[int], position: str = "middle") -> str:
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
        lines = []
        if not risk:
            return lines
        level = risk.get('level', 'none')
        if level == 'none':
            return lines
        message, hint = risk.get('message', ''), risk.get('hint', '')
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
            if AttentionFlag.XA not in hint:
                hint = f"{AttentionFlag.XA} {hint}"
            lines.append(f"  → hint: {hint}")
        return lines

    def _check_truncation(self, data: Dict) -> Optional[str]:
        summary = data.get('summary', {})
        if not summary:
            return None
        template_config = data.get('_template_config', {})
        total_field, shown_field = template_config.get('total_field'), template_config.get('shown_field')
        if total_field and shown_field:
            total, shown = summary.get(total_field, 0), summary.get(shown_field, 0)
            if total > shown:
                return f"# ... {total - shown} more items (use --top-n to show more)"
        return None
