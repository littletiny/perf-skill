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

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


# =============================================================================
# DisplayPreset Dataclass
# =============================================================================

@dataclass
class DisplayPreset:
    """显示格式预设 - display_presets.py DISPLAY_PRESETS"""
    template_type: str
    list_field: Optional[str] = None
    header: Optional[str] = None
    display_fields: List[str] = field(default_factory=list)
    index_format: Optional[str] = None
    custom_renderer: Optional[str] = None
    empty_message: Optional[str] = None
    total_field: Optional[str] = None
    shown_field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于兼容旧代码）"""
        result = {
            "template_type": self.template_type,
        }
        if self.list_field is not None:
            result["list_field"] = self.list_field
        if self.header is not None:
            result["header"] = self.header
        if self.display_fields:
            result["display_fields"] = self.display_fields
        if self.index_format is not None:
            result["index_format"] = self.index_format
        if self.custom_renderer is not None:
            result["custom_renderer"] = self.custom_renderer
        if self.empty_message is not None:
            result["empty_message"] = self.empty_message
        if self.total_field is not None:
            result["total_field"] = self.total_field
        if self.shown_field is not None:
            result["shown_field"] = self.shown_field
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayPreset':
        """从字典创建 DisplayPreset"""
        return cls(
            template_type=data.get("template_type", "simple_list"),
            list_field=data.get("list_field"),
            header=data.get("header"),
            display_fields=data.get("display_fields", []),
            index_format=data.get("index_format"),
            custom_renderer=data.get("custom_renderer"),
            empty_message=data.get("empty_message"),
            total_field=data.get("total_field"),
            shown_field=data.get("shown_field"),
        )


# =============================================================================
# 显示格式预设 (使用 DisplayPreset dataclass)
# =============================================================================

_DISPLAY_PRESETS: Dict[str, DisplayPreset] = {
    # -------------------------------------------------------------------------
    # get-hotspots
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # get-process-top
    # -------------------------------------------------------------------------
    "processes": DisplayPreset(
        template_type="simple_list",
        list_field="processes",
        header="# comm(pid) (usr+sys)/sys",
        display_fields=["comm", "pid", "total_cpu_util", "kernel_cpu_util"],
        index_format=None,  # 使用特殊格式 comm(pid)
        empty_message="No processes found",
        total_field="total_processes",
        shown_field="shown_processes",
    ),

    # -------------------------------------------------------------------------
    # get-comm-top / cluster-comm
    # -------------------------------------------------------------------------
    "comm_groups": DisplayPreset(
        template_type="key_value",
        list_field="comm_groups",
        header="# comm,pids,cpu_util,event",
        display_fields=["comm", "pids", "cpu", "event"],
        empty_message="No process groups found",
        total_field="total_comm_groups",
        shown_field=None,  # comm_groups 不显示截断提示
    ),

    # -------------------------------------------------------------------------
    # cluster-symbols
    # -------------------------------------------------------------------------
    "symbol_clusters": DisplayPreset(
        template_type="key_value",
        list_field="symbol_clusters",
        header="# event_type | pct_of_total (cluster_weight / total_weight)",
        display_fields=["cluster", "pct_of_total"],
        empty_message="No symbol clusters found",
        total_field="clusters_found",
        shown_field="shown_clusters",
    ),

    # -------------------------------------------------------------------------
    # cluster-paths
    # -------------------------------------------------------------------------
    "path_clusters": DisplayPreset(
        template_type="simple_list",
        list_field="path_clusters",
        header="# index,percent,cpu_util,path",
        # 特殊字段说明:
        # - _ratio_pct: 由模板根据 weight/total_weight 计算并格式化为百分比
        # - _cpu_util: 由模板根据 weight/duration 计算并格式化为百分比
        display_fields=["_ratio_pct", "_cpu_util", "path_signature"],
        index_format="#{index}",
        empty_message="No path clusters found",
        total_field="total_clusters",
        shown_field="shown_clusters",
    ),

    # -------------------------------------------------------------------------
    # find-callers
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # find-callers --auto
    # -------------------------------------------------------------------------
    "traces": DisplayPreset(
        template_type="nested",
        list_field="traces",
        header="# target (cpu_util) <- callstack",
        empty_message="No traces found",
        total_field=None,  # traces 不显示截断提示
        shown_field=None,
    ),

    # -------------------------------------------------------------------------
    # analyze-core-distribution
    # -------------------------------------------------------------------------
    "cores": DisplayPreset(
        template_type="simple_list",
        list_field="cores",
        header="# SATURATED_CORES: index,cpu_id,(usr+sys)/sys",
        display_fields=["cpu_id", "total_cpu_util", "kernel_cpu_util"],
        index_format="#{index}",
        empty_message="No saturated cores found",
        total_field=None,  # cores 按阈值过滤，不是 top_n 截断
        shown_field=None,
    ),

    # -------------------------------------------------------------------------
    # count-process-variety
    # -------------------------------------------------------------------------
    "process_variety": DisplayPreset(
        template_type="key_value",
        list_field="process_variety",
        header="# PROCESS_STORM: comm,pids_per_min,cpu_util",
        display_fields=["comm", "pids_per_min", "cpu_util"],
        empty_message="No process variety data",
        total_field="total_processes",
        shown_field=None,
    ),

    # -------------------------------------------------------------------------
    # detect-anomalies
    # -------------------------------------------------------------------------
    "anomalies": DisplayPreset(
        template_type="table",
        list_field="anomalies",
        header="# type,cpu_id,time_range,change,severity",
        # 特殊字段说明:
        # - _time_range: 由模板将 time_range_start 和 time_range_end 格式化为 "start - end"
        # - _util_change: 由模板将 prev_util/curr_util/next_util 格式化为 "X% -> Y% -> Z%"
        display_fields=["type", "cpu_id", "_time_range", "_util_change", "severity"],
        empty_message="No anomalies detected",
        total_field="total_anomalies",
        shown_field=None,
    ),

    # -------------------------------------------------------------------------
    # detect-anomalies --export-mode
    # -------------------------------------------------------------------------
    "windows": DisplayPreset(
        template_type="table",
        list_field="windows",
        header="# cpu_id,start_time,end_time,util,weight",
        display_fields=["cpu_id", "start_time", "end_time", "utilization", "weight"],
        empty_message="No windows data",
        total_field="total_windows",
        shown_field=None,
    ),

    # -------------------------------------------------------------------------
    # check-cpu-bottleneck (custom)
    # -------------------------------------------------------------------------
    "bottleneck": DisplayPreset(
        template_type="custom",
        custom_renderer="bottleneck",
    ),

    # -------------------------------------------------------------------------
    # show-cpu-usage (custom)
    # -------------------------------------------------------------------------
    "cpu_usage": DisplayPreset(
        template_type="custom",
        custom_renderer="cpu_usage",
    ),
}


# 向后兼容：保留 DISPLAY_PRESETS 作为字典
DISPLAY_PRESETS: Dict[str, Dict[str, Any]] = {
    name: preset.to_dict() for name, preset in _DISPLAY_PRESETS.items()
}


def get_display_preset(name: str) -> Dict[str, Any]:
    """获取显示格式预设（返回字典格式，保持向后兼容）

    Args:
        name: 预设名称 (如 "hotspots", "processes")

    Returns:
        显示格式配置字典
    """
    preset = _DISPLAY_PRESETS.get(name)
    if preset:
        return preset.to_dict()
    return {}


def get_display_preset_dataclass(name: str) -> Optional[DisplayPreset]:
    """获取显示格式预设（返回 DisplayPreset dataclass）

    Args:
        name: 预设名称 (如 "hotspots", "processes")

    Returns:
        DisplayPreset dataclass 或 None
    """
    return _DISPLAY_PRESETS.get(name)


def list_presets() -> list:
    """列出所有可用的预设名称"""
    return list(_DISPLAY_PRESETS.keys())
