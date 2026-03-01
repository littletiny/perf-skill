#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text Output Adapter - 将数据模型转换为人类可读的文本格式

用于列表类型数据的友好展示：
- hotspots: 热点函数列表
- clusters: 聚类结果列表
- processes: 进程列表
- comm_groups: 进程组列表
- cores: CPU核心列表
- attributions: 调用链列表
"""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional


class TextOutputAdapter:
    """
    文本输出适配器，将列表数据转换为人类可读的格式
    
    输出格式：
    [元数据行] 总计=X, 显示=Y, 时间范围=...
    
    数据行1
    数据行2
    ...
    """
    
    def __init__(self, max_width: int = 120):
        self.max_width = max_width
    
    def format_output(self, obj: Any) -> str:
        """将输出对象转换为文本格式"""
        if not is_dataclass(obj):
            return str(obj)
        
        data = asdict(obj)
        
        # 获取风险信息
        risk_info = data.get('_risk', {})
        risk_lines = self._format_risk(risk_info)
        
        # 获取摘要信息
        summary = data.get('summary', {})
        time_range = data.get('time_range', {})
        
        # 获取列表数据
        list_data = None
        list_name = None
        
        for key in ['hotspots', 'clusters', 'processes', 'comm_groups', 
                    'cores', 'attributions', 'traces', 'path_clusters', 
                    'process_variety', 'windows', 'anomalies']:
            if key in data:
                list_data = data[key]
                list_name = key
                break
        
        # 获取特殊数据字段（如 bottleneck 和 cpu_usage）
        special_data = data.get('data')
        
        # 组合输出
        lines = []
        if risk_lines:
            lines.extend(risk_lines)
        
        # 添加列表数据和format header（如果需要）
        if list_data is not None:
            # list_data could be empty list, still need to show empty message
            format_header, formatted_lines = self._format_list(list_data, list_name)
            if format_header:
                lines.append(format_header)
            lines.extend(formatted_lines)
            # Check for truncation and add hint
            trunc_hint = self._check_truncation(summary, list_name)
            if trunc_hint:
                lines.append(trunc_hint)
        elif special_data:
            # 处理特殊数据类型
            lines.extend(self._format_special_data(special_data))
        
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
    
    def _format_summary(self, summary: Dict, list_name: str) -> List[str]:
        """格式化摘要信息"""
        parts = []
        
        if list_name == 'hotspots':
            parts.append(f"total_hotspots={summary.get('total_hotspots', 0)}")
        elif list_name == 'clusters':
            parts.append(f"clusters_found={summary.get('clusters_found', 0)}")
            if 'total_core_seconds' in summary:
                parts.append(f"total_core_sec={summary['total_core_seconds']}")
        elif list_name == 'processes':
            parts.append(f"total_processes={summary.get('total_processes', 0)}")
            parts.append(f"shown={summary.get('shown_processes', 0)}")
        elif list_name == 'comm_groups':
            parts.append(f"total_comm_groups={summary.get('total_comm_groups', 0)}")
            if summary.get('high_kernel_groups', 0) > 0:
                parts.append(f"high_kernel={summary['high_kernel_groups']}")
        elif list_name == 'cores':
            parts.append(f"imbalance_level={summary.get('imbalance_level', 'UNKNOWN')}")
        elif list_name == 'attributions':
            parts.append(f"target={summary.get('target', 'N/A')}")
            if 'target_core_sec' in summary:
                parts.append(f"target_core_sec={summary['target_core_sec']}")
        elif list_name == 'traces':
            parts.append(f"hotspots_traced={summary.get('hotspots_traced', 0)}")
        elif list_name == 'path_clusters':
            parts.append(f"total_clusters={summary.get('total_clusters', 0)}")
            if 'clustered_core_sec' in summary:
                parts.append(f"clustered_core_sec={summary['clustered_core_sec']}")
        elif list_name == 'process_variety':
            parts.append(f"total_processes={summary.get('total_processes', 0)}")
            if summary.get('storm_detected', False):
                parts.append(f"storm_count={summary.get('storm_count', 0)}")
        elif list_name == 'anomalies':
            parts.append(f"total_anomalies={summary.get('total_anomalies', 0)}")
            parts.append(f"spikes={summary.get('spike_count', 0)}")
            parts.append(f"drops={summary.get('drop_count', 0)}")
        elif list_name == 'windows':
            parts.append(f"mode={summary.get('mode', 'unknown')}")
            parts.append(f"windows={summary.get('total_windows', 0)}")
            parts.append(f"cpus={summary.get('cpu_count', 0)}")
        
        return parts
    
    def _check_truncation(self, summary: Dict, list_name: str) -> Optional[str]:
        """检查列表是否被截断，如果被截断返回提示信息"""
        if not summary:
            return None
        
        # Map list_name to summary fields
        field_map = {
            'hotspots': ('total_hotspots', 'shown_hotspots'),
            'clusters': ('clusters_found', 'shown_clusters'),
            'processes': ('total_processes', 'shown_processes'),
            'comm_groups': ('total_comm_groups', None),
            'cores': (None, None),  # cores filtered by threshold, not top_n
            'attributions': ('total_attributions', 'shown_attributions'),
            'traces': (None, None),
            'process_variety': ('total_processes', None),
            'anomalies': ('total_anomalies', None),
            'windows': ('total_windows', None),
        }
        
        # Special handling for 'clusters' which is used by both cluster-symbols and cluster-paths
        if list_name == 'clusters':
            # Try cluster-symbols fields first
            if 'clusters_found' in summary and 'shown_clusters' in summary:
                total = summary.get('clusters_found', 0)
                shown = summary.get('shown_clusters', 0)
                if total > shown:
                    return f"# ... {total - shown} more items (use --top-n to show more)"
            # Then try cluster-paths fields
            elif 'total_clusters' in summary and 'shown_clusters' in summary:
                total = summary.get('total_clusters', 0)
                shown = summary.get('shown_clusters', 0)
                if total > shown:
                    return f"# ... {total - shown} more items (use --top-n to show more)"
            return None
        
        if list_name not in field_map:
            return None
        
        total_field, shown_field = field_map[list_name]
        
        # For lists with shown field
        if shown_field and total_field:
            total = summary.get(total_field, 0)
            shown = summary.get(shown_field, 0)
            if total > shown:
                return f"# ... {total - shown} more items (use --top-n to show more)"
        
        return None
    
    def _format_list(self, items: List[Dict], list_name: str):
        """格式化列表数据，返回 (format_header, lines)"""
        if not items:
            # 返回友好的空状态消息
            empty_messages = {
                'anomalies': 'No anomalies detected',
                'hotspots': 'No hotspots found',
                'clusters': 'No clusters found',
                'processes': 'No processes found',
                'comm_groups': 'No process groups found',
                'cores': 'No saturated cores found',
                'attributions': 'No attributions found',
                'traces': 'No traces found',
                'path_clusters': 'No path clusters found',
                'process_variety': 'No process variety data',
                'windows': 'No windows data'
            }
            msg = empty_messages.get(list_name, f'No {list_name} found')
            return (None, [f"({msg})"])
        
        # 通过检查第一项的字段来区分不同类型的 clusters
        if list_name == 'clusters':
            first_item = items[0] if items else {}
            if 'path_signature' in first_item:
                return self._format_path_clusters(items)
            else:
                return self._format_clusters(items)
        elif list_name == 'hotspots':
            return self._format_hotspots(items)
        elif list_name == 'processes':
            return self._format_processes(items)
        elif list_name == 'comm_groups':
            return self._format_comm_groups(items)
        elif list_name == 'cores':
            return self._format_cores(items)
        elif list_name == 'attributions':
            return self._format_attributions(items)
        elif list_name == 'traces':
            return self._format_traces(items)
        elif list_name == 'process_variety':
            return self._format_process_variety(items)
        elif list_name == 'anomalies':
            return self._format_anomalies(items)
        elif list_name == 'windows':
            return self._format_windows(items)
        else:
            # 通用列表格式
            return (None, [str(item) for item in items])
    
    def _format_hotspots(self, items: List[Dict]):
        """格式化热点函数列表"""
        format_header = "# index,funcname,self,inclusive"
        lines = []
        for i, item in enumerate(items, 1):
            symbol = item.get('symbol', 'N/A')
            self_pct = item.get('self', '0%')
            inclusive = item.get('inclusive', '0%')
            lines.append(f"#{i} {symbol} {self_pct} {inclusive}")
        return (format_header, lines)
    
    def _format_clusters(self, items: List[Dict]):
        """格式化聚类结果 (cluster-symbols)"""
        format_header = "# type,percent,cpu_util"
        lines = []
        for item in items:
            cluster = item.get('cluster', 'N/A')
            ratio = item.get('ratio_pct', '0%')
            cpu_util = item.get('cpu_util', '0.00%')
            lines.append(f"{cluster} {ratio} {cpu_util}")
        return (format_header, lines)
    
    def _format_processes(self, items: List[Dict]):
        """格式化进程列表"""
        format_header = "# comm(pid) (usr+sys)/sys"
        lines = []
        for item in items:
            comm = item.get('comm', 'N/A')
            pid = item.get('pid', 'N/A')
            total = item.get('total_cpu_util', '0.00%')
            kernel = item.get('kernel_cpu_util', '0.00%')
            lines.append(f"{comm}({pid}) {total}/{kernel}")
        return (format_header, lines)
    
    def _format_comm_groups(self, items: List[Dict]):
        """格式化进程组列表 (cluster-comm, get-comm-top)"""
        format_header = "# comm,pids,cpu_util,event"
        lines = []
        for item in items:
            comm = item.get('comm', 'N/A')
            pids = item.get('pids', 0)
            cpu = item.get('cpu', '0%')
            event = item.get('event', 'normal')
            lines.append(f"{comm} {pids} {cpu} {event}")
        return (format_header, lines)
    
    def _format_cores(self, items: List[Dict]):
        """格式化CPU核心列表 (仅展示 saturated 核心)"""
        format_header = "# SATURATED_CORES: index,cpu_id,(usr+sys)/sys"
        lines = []
        for i, item in enumerate(items, 1):
            cpu_id = item.get('cpu_id', 'N/A')
            total = item.get('total_cpu_util', '0%')
            kernel = item.get('kernel_cpu_util', '0%')
            lines.append(f"#{i} CPU{cpu_id} {total}/{kernel}")
        return (format_header, lines)
    
    def _format_attributions(self, items: List[Dict]):
        """格式化调用归因列表 (从调用者到被调用者)"""
        format_header = "# index,ratio,callstack"
        lines = []
        for i, item in enumerate(items, 1):
            stack = item.get('caller_stack', [])
            ratio = item.get('ratio_of_target_pct', '0%')
            stack_str = " <- ".join(stack) if stack else "(root)"
            lines.append(f"#{i} [{ratio}] {stack_str}")
        return (format_header, lines)
    
    def _format_traces(self, items: List[Dict]):
        """格式化追踪热点列表 (从调用者到被调用者)"""
        format_header = "# target (cpu_util) <- callstack"
        lines = []
        for item in items:
            target = item.get('target', 'N/A')
            target_ratio_str = item.get('target_ratio_pct', '0%')
            target_ratio = float(target_ratio_str.rstrip('%'))
            lines.append(f">>> {target} ({target_ratio_str})")
            attributions = item.get('attributions', [])
            for i, attr in enumerate(attributions, 1):
                stack = attr.get('caller_stack', [])
                attr_ratio_str = attr.get('ratio_of_target_pct', '0%')
                attr_ratio = float(attr_ratio_str.rstrip('%'))
                # Calculate total ratio: target_ratio * attr_ratio / 100
                total_ratio = target_ratio * attr_ratio / 100
                stack_str = " <- ".join(stack) if stack else "(root)"
                lines.append(f"  #{i} [{total_ratio:.2f}%] {stack_str}")
        return (format_header, lines)
    
    def _format_path_clusters(self, items: List[Dict]):
        """格式化路径聚类列表"""
        format_header = "# index,percent,cpu_util,path"
        lines = []
        for i, item in enumerate(items, 1):
            ratio = item.get('ratio_pct', '0%')
            cpu_util = item.get('cpu_util', '0.00%')
            path = item.get('path_signature', 'N/A')
            lines.append(f"#{i} {ratio} {cpu_util} {path}")
        return (format_header, lines)
    
    def _format_process_variety(self, items: List[Dict]):
        """格式化进程多样性列表 (仅展示 process_storm)"""
        format_header = "# PROCESS_STORM: comm,pids,cpu_util"
        lines = []
        for item in items:
            comm = item.get('comm', 'N/A')
            pids = item.get('unique_pids', 0)
            cpu_util = item.get('cpu_util', '0.00%')
            lines.append(f"{comm} {pids} {cpu_util}")
        return (format_header, lines)
    
    def _format_anomalies(self, items: List[Dict]):
        """格式化异常检测列表"""
        format_header = "# type,cpu_id,time_range,change,severity"
        lines = []
        for item in items:
            anomaly_type = item.get('type', 'N/A')
            cpu_id = item.get('cpu_id', 'N/A')
            time_range = item.get('time_range', 'N/A')
            if isinstance(time_range, dict):
                time_range = f"{time_range.get('start', '')} - {time_range.get('end', '')}"
            change = item.get('utilization_change', 'N/A')
            severity = item.get('severity', 'unknown')
            lines.append(f"{anomaly_type} cpu={cpu_id} time={time_range} change={change} severity={severity}")
        return (format_header, lines)
    
    def _format_windows(self, items: List[Dict]):
        """格式化时间窗口列表"""
        format_header = "# cpu_id,start_time,end_time,util,core_sec"
        lines = []
        for item in items:
            cpu_id = item.get('cpu_id', 'N/A')
            start = item.get('start_time', 'N/A')
            end = item.get('end_time', 'N/A')
            util = item.get('utilization', 'N/A')
            core_sec = item.get('core_sec', 0)
            lines.append(f"cpu={cpu_id} start={start} end={end} util={util} core_sec={core_sec:.4f}")
        return (format_header, lines)
    
    def _format_special_data(self, data: Dict) -> List[str]:
        """格式化特殊数据类型（如 bottleneck, cpu_usage）"""
        lines = []
        
        # check-cpu-bottleneck 数据
        if 'verdict' in data:
            verdict = data.get('verdict', 'N/A')
            max_load = data.get('max_core_load', {})
            limit_info = data.get('limit_info', {})
            
            lines.append(f"Verdict: {verdict}")
            if max_load:
                lines.append(f"Max Core Load: CPU {max_load.get('cpu_id', 'N/A')} = {max_load.get('load', 'N/A')}")
            if limit_info:
                detected = limit_info.get('cpu_limit_detected', False)
                cores = limit_info.get('cpu_limit_cores', 0)
                lines.append(f"CPU Limit: {cores}c (detected={detected})")
        
        # show-cpu-usage 数据
        elif 'cpu_utilization' in data:
            target = data.get('target', 'System')
            util = data.get('cpu_utilization', {})
            
            lines.append(f"Target: {target}")
            lines.append(f"  Total: {util.get('total_pct', 'N/A')}")
            lines.append(f"  User:  {util.get('user_pct', 'N/A')}")
            lines.append(f"  Kernel: {util.get('kernel_pct', 'N/A')}")
        
        return lines
