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
"""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


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
                # 特殊处理: path_clusters 从原始 core_sec 计算百分比
                line = self._format_path_cluster_line(item, i, config)
            else:
                # 标准格式: #index field1 field2 ...
                values = [self._format_field_value(item, f) for f in config.display_fields]
                prefix = config.index_format.format(index=i) if config.index_format else f"#{i}"
                line = f"{prefix} " + " ".join(values)
            
            lines.append(line)
        
        return lines
    
    def _format_path_cluster_line(self, item: Any, index: int, config: Any) -> str:
        """格式化路径聚类行 - 从原始 core_sec 计算百分比"""
        # 从原始数据计算百分比
        if isinstance(item, dict):
            core_sec = item.get('core_sec', 0)
            total = item.get('total_core_sec', 1)
            duration = item.get('duration', 1)
            path = item.get('path_signature', 'N/A')
        else:
            core_sec = getattr(item, 'core_sec', 0)
            total = getattr(item, 'total_core_sec', 1)
            duration = getattr(item, 'duration', 1)
            path = getattr(item, 'path_signature', 'N/A')
        
        # 计算百分比
        ratio_pct = (core_sec / total * 100) if total > 0 else 0
        cpu_util = (core_sec / duration * 100) if duration > 0 else 0
        
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
            time_range = getattr(item, 'time_range', 'N/A')
            change = getattr(item, 'utilization_change', 'N/A')
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
            core_sec = item.get('core_sec', 0)
        else:
            cpu_id = getattr(item, 'cpu_id', 'N/A')
            start = getattr(item, 'start_time', 'N/A')
            end = getattr(item, 'end_time', 'N/A')
            util = getattr(item, 'utilization', 'N/A')
            core_sec = getattr(item, 'core_sec', 0)
        
        return f"cpu={cpu_id} start={start} end={end} util={util} core_sec={core_sec:.4f}"


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
    
    适用于: bottleneck, cpu_usage
    """
    
    def __init__(self):
        self.renderers = {
            "bottleneck": self._render_bottleneck,
            "cpu_usage": self._render_cpu_usage,
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
    
    def _format_risk(self, risk: Dict) -> List[str]:
        """格式化风险信息"""
        lines = []
        if not risk:
            return lines
        
        level = risk.get('level', 'none')
        if level == 'none':
            return lines
        
        message = risk.get('message', '')
        hint = risk.get('hint', '')
        
        if level == 'critical':
            lines.append(f"[RISK-CRITICAL] {message}")
        elif level == 'warning':
            lines.append(f"[RISK-WARNING] {message}")
        else:
            lines.append(f"[RISK-INFO] {message}")
        
        if hint:
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
