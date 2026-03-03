#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Display Presets - 统一的显示格式配置

所有命令的文本输出格式配置集中在此定义，修改显示格式只需改此文件。

配置项说明:
- template_type: 模板类型 (simple_list/key_value/table/nested/custom)
- list_field: 数据列表字段名
- header: 表头描述行
- display_fields: 显示的字段列表(按顺序)
- index_format: 序号格式 (如 "#{index}")
- empty_message: 空列表提示信息
- total_field: 摘要中总数字段名 (用于截断提示)
- shown_field: 摘要中显示数字段名 (用于截断提示)
- custom_renderer: 自定义渲染器标识
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class DisplayPreset:
    """显示格式预设"""
    template_type: str
    list_field: Optional[str] = None
    header: Optional[str] = None
    display_fields: List[str] = field(default_factory=list)
    index_format: Optional[str] = None
    custom_renderer: Optional[str] = None
    empty_message: Optional[str] = None
    total_field: Optional[str] = None
    shown_field: Optional[str] = None


_DISPLAY_PRESETS: Dict[str, DisplayPreset] = {
    "hotspots": DisplayPreset(
        template_type="simple_list",
        list_field="hotspots",
        header="# index,funcname,self,inclusive",
        display_fields=["symbol", "self", "inclusive"],
        index_format="#{index}",
        empty_message="No hotspots found",
        total_field="total_hotspots",
        shown_field="shown_hotspots",
    ),
    "processes": DisplayPreset(
        template_type="simple_list",
        list_field="processes",
        header="# comm(pid) (usr+sys)/sys",
        display_fields=["comm", "pid", "total_cpu_util", "kernel_cpu_util"],
        index_format=None,
        empty_message="No processes found",
        total_field="total_processes",
        shown_field="shown_processes",
    ),
    "comm_groups": DisplayPreset(
        template_type="key_value",
        list_field="comm_groups",
        header="# comm,pids,cpu_util,event",
        display_fields=["comm", "pids", "cpu", "event"],
        empty_message="No process groups found",
        total_field="total_comm_groups",
        shown_field=None,
    ),
    "symbol_clusters": DisplayPreset(
        template_type="key_value",
        list_field="symbol_clusters",
        header="# event_type | pct_of_total (cluster_weight / total_weight)",
        display_fields=["cluster", "pct_of_total"],
        empty_message="No symbol clusters found",
        total_field="clusters_found",
        shown_field="shown_clusters",
    ),
    "path_clusters": DisplayPreset(
        template_type="simple_list",
        list_field="path_clusters",
        header="# index,percent,cpu_util,path",
        display_fields=["_ratio_pct", "_cpu_util", "path_signature"],
        index_format="#{index}",
        empty_message="No path clusters found",
        total_field="total_clusters",
        shown_field="shown_clusters",
    ),
    "attributions": DisplayPreset(
        template_type="simple_list",
        list_field="attributions",
        header="# index,ratio,callstack",
        display_fields=["ratio_of_target_pct", "caller_stack"],
        index_format="#{index}",
        empty_message="No attributions found",
        total_field="total_attributions",
        shown_field="shown_attributions",
    ),
    "traces": DisplayPreset(
        template_type="nested",
        list_field="traces",
        header="# target (cpu_util) <- callstack",
        empty_message="No traces found",
        total_field=None,
        shown_field=None,
    ),
    "cores": DisplayPreset(
        template_type="simple_list",
        list_field="cores",
        header="# SATURATED_CORES: index,cpu_id,(usr+sys)/sys",
        display_fields=["cpu_id", "total_cpu_util", "kernel_cpu_util"],
        index_format="#{index}",
        empty_message="No saturated cores found",
        total_field=None,
        shown_field=None,
    ),
    "process_variety": DisplayPreset(
        template_type="key_value",
        list_field="process_variety",
        header="# PROCESS_STORM: comm,pids_per_min,cpu_util",
        display_fields=["comm", "pids_per_min", "cpu_util"],
        empty_message="No process variety data",
        total_field="total_processes",
        shown_field=None,
    ),
    "anomalies": DisplayPreset(
        template_type="table",
        list_field="anomalies",
        header="# type,cpu_id,time_range,change,severity",
        display_fields=["type", "cpu_id", "_time_range", "_util_change", "severity"],
        empty_message="No anomalies detected",
        total_field="total_anomalies",
        shown_field=None,
    ),
    "windows": DisplayPreset(
        template_type="table",
        list_field="windows",
        header="# cpu_id,start_time,end_time,util,weight",
        display_fields=["cpu_id", "start_time", "end_time", "utilization", "weight"],
        empty_message="No windows data",
        total_field="total_windows",
        shown_field=None,
    ),
    "bottleneck": DisplayPreset(
        template_type="custom",
        custom_renderer="bottleneck",
    ),
    "cpu_usage": DisplayPreset(
        template_type="custom",
        custom_renderer="cpu_usage",
    ),
}


def get_display_preset(name: str) -> Optional[DisplayPreset]:
    """获取显示格式预设

    Args:
        name: 预设名称 (如 "hotspots", "processes")

    Returns:
        DisplayPreset dataclass 或 None
    """
    return _DISPLAY_PRESETS.get(name)


def list_presets() -> list:
    """列出所有可用的预设名称"""
    return list(_DISPLAY_PRESETS.keys())
