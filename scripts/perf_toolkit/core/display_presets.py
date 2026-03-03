#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Display Presets - 统一的显示格式配置

所有命令的文本输出格式配置集中在此定义，修改显示格式只需改此文件。
常量定义统一从 config.defaults 导入。

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

import sys
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, field

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import DisplayPresets as DisplayPresetConstants


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
        header=DisplayPresetConstants.HOTSPOTS_HEADER,
        display_fields=["symbol", "self", "inclusive"],
        index_format="#{index}",
        empty_message=DisplayPresetConstants.NO_HOTSPOTS,
        total_field="total_hotspots",
        shown_field="shown_hotspots",
    ),
    "processes": DisplayPreset(
        template_type="simple_list",
        list_field="processes",
        header=DisplayPresetConstants.PROCESSES_HEADER,
        display_fields=["comm", "pid", "total_cpu_util", "kernel_cpu_util"],
        index_format=None,
        empty_message=DisplayPresetConstants.NO_PROCESSES,
        total_field="total_processes",
        shown_field="shown_processes",
    ),
    "comm_groups": DisplayPreset(
        template_type="key_value",
        list_field="comm_groups",
        header=DisplayPresetConstants.COMM_GROUPS_HEADER,
        display_fields=["comm", "pids", "cpu", "event"],
        empty_message=DisplayPresetConstants.NO_COMM_GROUPS,
        total_field="total_comm_groups",
        shown_field=None,
    ),
    "symbol_clusters": DisplayPreset(
        template_type="key_value",
        list_field="symbol_clusters",
        header=DisplayPresetConstants.SYMBOL_CLUSTERS_HEADER,
        display_fields=["cluster", "pct_of_total"],
        empty_message=DisplayPresetConstants.NO_SYMBOL_CLUSTERS,
        total_field="clusters_found",
        shown_field="shown_clusters",
    ),
    "path_clusters": DisplayPreset(
        template_type="simple_list",
        list_field="path_clusters",
        header=DisplayPresetConstants.PATH_CLUSTERS_HEADER,
        display_fields=["_ratio_pct", "_cpu_util", "path_signature"],
        index_format="#{index}",
        empty_message=DisplayPresetConstants.NO_PATH_CLUSTERS,
        total_field="total_clusters",
        shown_field="shown_clusters",
    ),
    "attributions": DisplayPreset(
        template_type="simple_list",
        list_field="attributions",
        header=DisplayPresetConstants.ATTRIBUTIONS_HEADER,
        display_fields=["ratio_of_target_pct", "caller_stack"],
        index_format="#{index}",
        empty_message=DisplayPresetConstants.NO_ATTRIBUTIONS,
        total_field="total_attributions",
        shown_field="shown_attributions",
    ),
    "traces": DisplayPreset(
        template_type="nested",
        list_field="traces",
        header=DisplayPresetConstants.TRACES_HEADER,
        empty_message=DisplayPresetConstants.NO_TRACES,
        total_field=None,
        shown_field=None,
    ),
    "cores": DisplayPreset(
        template_type="simple_list",
        list_field="cores",
        header=DisplayPresetConstants.CORES_HEADER,
        display_fields=["cpu_id", "total_cpu_util", "kernel_cpu_util"],
        index_format="#{index}",
        empty_message=DisplayPresetConstants.NO_CORES,
        total_field=None,
        shown_field=None,
    ),
    "process_variety": DisplayPreset(
        template_type="key_value",
        list_field="process_variety",
        header=DisplayPresetConstants.PROCESS_VARIETY_HEADER,
        display_fields=["comm", "pids_per_min", "cpu_util"],
        empty_message=DisplayPresetConstants.NO_PROCESS_VARIETY,
        total_field="total_processes",
        shown_field=None,
    ),
    "anomalies": DisplayPreset(
        template_type="table",
        list_field="anomalies",
        header=DisplayPresetConstants.ANOMALIES_HEADER,
        display_fields=["type", "cpu_id", "_time_range", "_util_change", "severity"],
        empty_message=DisplayPresetConstants.NO_ANOMALIES,
        total_field="total_anomalies",
        shown_field=None,
    ),
    "windows": DisplayPreset(
        template_type="table",
        list_field="windows",
        header=DisplayPresetConstants.WINDOWS_HEADER,
        display_fields=["cpu_id", "start_time", "end_time", "utilization", "weight"],
        empty_message=DisplayPresetConstants.NO_WINDOWS,
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
