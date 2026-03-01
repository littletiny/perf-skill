#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection - Detect CPU utilization anomalies

检测 CPU 利用率异常。

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

from collections import defaultdict
from ..core.format_utils import format_timestamp
from ..core.output_builder import OutputBuilder


def cmd_detect_anomalies(engine, args):
    """[Skill] Detect CPU utilization anomalies or export window data"""
    
    builder = OutputBuilder(engine, args)
    
    # Fetch samples
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    # Check empty samples
    if builder.check_empty_samples(samples):
        return
    
    # Assess quality with early return for critical
    if builder.assess_quality(samples, early_return_critical=True):
        return
    
    # Get parameters
    window_size = args.window_size
    spike_threshold = args.spike_threshold
    min_utilization = args.min_utilization
    export_mode = args.export_mode
    export_samples = args.export_samples
    cpu_id = getattr(args, 'cpu_id', None)
    top_n = getattr(args, 'top_n', 10)
    
    # Group samples by CPU
    cpu_samples = defaultdict(list)
    for s in samples:
        if cpu_id is None or s['cpu'] == cpu_id:
            cpu_samples[s['cpu']].append(s)
    
    all_windows_by_cpu = {}
    all_anomalies = []
    
    for cpu_id_val, cpu_samples_list in cpu_samples.items():
        if not cpu_samples_list:
            continue
        
        cpu_samples_list.sort(key=lambda x: x['ts'])
        start_ts = cpu_samples_list[0]['ts']
        end_ts = cpu_samples_list[-1]['ts']
        cpu_duration = end_ts - start_ts
        
        if cpu_duration < window_size:
            continue
        
        n_windows = int(cpu_duration / window_size) + 1
        windows = []
        
        for i in range(n_windows):
            win_start = start_ts + i * window_size
            win_end = win_start + window_size
            win_samples_raw = [s for s in cpu_samples_list if win_start <= s['ts'] < win_end]
            
            win_core_per_sec = sum(s.get('core_per_sec') or 0 for s in win_samples_raw)
            utilization = win_core_per_sec / window_size if window_size > 0 else 0
            
            window_data = {
                "cpu_id": cpu_id_val,
                "start_time": format_timestamp(win_start),
                "end_time": format_timestamp(win_end),
                "utilization": f"{utilization*100:.2f}%",
                "core_sec": round(win_core_per_sec, 4)
            }
            
            if export_samples:
                window_data["samples"] = [
                    {
                        "comm": s["comm"],
                        "pid": s["pid"],
                        "timestamp": format_timestamp(s["ts"]),
                        "stack": s["stack"].get_normalized_names() if s.get("stack") else []
                    }
                    for s in win_samples_raw
                ]
            else:
                window_data["_samples"] = win_samples_raw
            
            windows.append(window_data)
        
        all_windows_by_cpu[cpu_id_val] = windows
        
        if not export_mode or args.detect_in_export:
            cpu_anomalies = _detect_cpu_anomalies(cpu_id_val, windows, spike_threshold, min_utilization)
            all_anomalies.extend(cpu_anomalies)
    
    # Export mode
    if export_mode:
        for cpu_id_val, windows in all_windows_by_cpu.items():
            for w in windows:
                w.pop("_samples", None)
        
        all_utils = []
        for windows in all_windows_by_cpu.values():
            all_utils.extend([float(w["utilization"].rstrip('%')) / 100 for w in windows])
        
        if all_utils:
            mean_util = sum(all_utils) / len(all_utils)
            variance = sum((u - mean_util) ** 2 for u in all_utils) / len(all_utils)
            std_util = variance ** 0.5
        else:
            mean_util = std_util = 0
        
        result = builder.build(
            data_type="windows",
            data=[w for windows in all_windows_by_cpu.values() for w in windows],
            summary={
                "mode": "export",
                "window_size_sec": window_size,
                "export_samples": export_samples,
                "cpu_count": len(all_windows_by_cpu),
                "total_windows": sum(len(w) for w in all_windows_by_cpu.values())
            },
            statistics={
                "mean_utilization": f"{mean_util*100:.2f}%",
                "std_utilization": f"{std_util*100:.2f}%"
            }
        )
        
        if args.detect_in_export and all_anomalies:
            result["anomalies"] = _format_anomalies(all_anomalies[:top_n])
        
        builder.print_json(result)
        return
    
    # Normal anomaly detection mode
    all_anomalies.sort(key=lambda x: abs(x.get("change_magnitude", 0)), reverse=True)
    
    spike_count = sum(1 for a in all_anomalies if a["type"] == "SPIKE")
    drop_count = sum(1 for a in all_anomalies if a["type"] == "DROP")
    
    # Add risk if anomalies found
    if spike_count > 0:
        builder.add_risk(
            "warning",
            f"检测到 {spike_count} 个 CPU 利用率异常尖峰",
            f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '检测到 {spike_count} 个 CPU 利用率异常尖峰' --risk 'warning' --hint 'get-hotspots --start-time {format_timestamp(samples[0]['ts'])}'",
            patterns=["CPU_SPIKE"]
        )
    
    # Build and output
    result = builder.build(
        data_type="anomalies",
        data=_format_anomalies(all_anomalies[:top_n]),
        summary={
            "total_anomalies": len(all_anomalies),
            "spike_count": spike_count,
            "drop_count": drop_count
        }
    )
    
    builder.print_json(result)


def _detect_cpu_anomalies(cpu_id, windows, spike_threshold, min_utilization):
    """Detect anomalies for a single CPU's time windows"""
    anomalies = []
    
    if len(windows) < 3:
        return anomalies
    
    utilizations = [float(w["utilization"].rstrip('%')) / 100 for w in windows]
    if not utilizations:
        return anomalies
    
    mean_util = sum(utilizations) / len(utilizations)
    std_util = (sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)) ** 0.5
    
    for i in range(1, len(windows) - 1):
        prev_util = utilizations[i - 1]
        curr_util = utilizations[i]
        next_util = utilizations[i + 1]
        
        change_from_prev = curr_util - prev_util
        change_to_next = next_util - curr_util
        z_score = (curr_util - mean_util) / std_util if std_util > 0 else 0
        
        win = windows[i]
        start_time = win["start_time"]
        end_time = win["end_time"]
        
        # SPIKE detection
        if (change_from_prev > spike_threshold and 
            change_to_next < -spike_threshold / 2 and
            curr_util > min_utilization):
            anomalies.append({
                "type": "SPIKE",
                "cpu_id": cpu_id,
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "utilization_change": f"{prev_util*100:.1f}% -> {curr_util*100:.1f}% -> {next_util*100:.1f}%",
                "change_magnitude": round(change_from_prev, 3),
                "z_score": round(z_score, 2)
            })
        
        # DROP detection
        elif (change_from_prev < -spike_threshold and 
              change_to_next > spike_threshold / 2 and
              prev_util > min_utilization):
            anomalies.append({
                "type": "DROP",
                "cpu_id": cpu_id,
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "utilization_change": f"{prev_util*100:.1f}% -> {curr_util*100:.1f}% -> {next_util*100:.1f}%",
                "change_magnitude": round(abs(change_from_prev), 3),
                "z_score": round(abs(z_score), 2)
            })
    
    return anomalies


def _format_anomalies(anomalies):
    """Format anomalies to simplified structure"""
    formatted = []
    for a in anomalies:
        formatted.append({
            "type": a["type"],
            "cpu_id": a["cpu_id"],
            "time_range": f"{a['time_range']['start']} - {a['time_range']['end']}",
            "utilization_change": a.get("utilization_change", ""),
            "severity": "high" if a.get("z_score", 0) > 2.5 else "medium"
        })
    return formatted
