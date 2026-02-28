#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection - Detect CPU utilization anomalies

检测 CPU 利用率异常。

注意：数据已按 1 秒聚合，记录数量无参考价值，分析基于 core/s 值。
"""

import json
from collections import defaultdict
from ..core.reliability import assess_data_quality


def cmd_detect_anomalies(engine, args):
    """[Skill] Detect CPU utilization anomalies or export window data"""
    # Get filtered samples by time range, PID and comm
    samples = engine.get_filtered_samples(
        start_time=getattr(args, 'start_time', None),
        end_time=getattr(args, 'end_time', None),
        pid=getattr(args, 'pid', None),
        comm=getattr(args, 'comm', None),
        comm_regex=getattr(args, 'comm_regex', None)
    )
    
    if not samples:
        print(json.dumps({
            "error": "No samples found in the specified time range",
            "filters": {
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None)
            },
            "available_range": engine.get_time_range()
        }, indent=2))
        return
    
    # Calculate duration from filtered samples
    duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
    record_count = len(samples)
    
    # Get total core/s for accurate CPU utilization
    total_core_per_sec, _ = engine.get_total_core_per_sec(samples)
    quality_level, warning_msg, metrics = assess_data_quality(
        duration, total_core_per_sec=total_core_per_sec, record_count=record_count
    )
    
    # Early warning for critical quality
    if quality_level == "CRITICAL":
        print(json.dumps({
            "_WARNING": "数据质量不足，异常检测结果完全不可信。",
            "data_quality": {
                "level": quality_level,
                "warning": warning_msg,
                "metrics": metrics
            },
            "error": "Insufficient data quality for anomaly detection"
        }, indent=2, ensure_ascii=False))
        return

    window_size = args.window_size
    spike_threshold = args.spike_threshold
    min_utilization = args.min_utilization
    export_mode = args.export_mode
    export_samples = args.export_samples
    
    # Group samples by CPU
    cpu_samples = defaultdict(list)
    for s in samples:
        if args.cpu_id is None or s['cpu'] == args.cpu_id:
            cpu_samples[s['cpu']].append(s)
    
    all_windows_by_cpu = {}
    all_anomalies = []
    
    for cpu_id, cpu_samples_list in cpu_samples.items():
        if not cpu_samples_list:
            continue
            
        # Sort by timestamp
        cpu_samples_list.sort(key=lambda x: x['ts'])
        
        # Calculate time range
        start_ts = cpu_samples_list[0]['ts']
        end_ts = cpu_samples_list[-1]['ts']
        cpu_duration = end_ts - start_ts
        
        if cpu_duration < window_size:
            continue  # Not enough data
        
        # Create time windows
        n_windows = int(cpu_duration / window_size) + 1
        windows = []
        
        for i in range(n_windows):
            win_start = start_ts + i * window_size
            win_end = win_start + window_size
            win_samples_raw = [s for s in cpu_samples_list if win_start <= s['ts'] < win_end]
            
            record_count_in_window = len(win_samples_raw)
            
            # Calculate utilization using core/s values (accurate method)
            # Sum of core/s values divided by window size gives average CPU utilization
            win_core_per_sec = sum(s.get('core_per_sec') or 0 for s in win_samples_raw)
            utilization = win_core_per_sec / window_size if window_size > 0 else 0
            
            window_data = {
                "window_index": i,
                "start_time": win_start,
                "end_time": win_end,
                "duration_sec": round(win_end - win_start, 3),
                "record_count": record_count_in_window,
                "utilization": round(utilization, 4),
                "utilization_pct": f"{utilization*100:.1f}%",
                "total_core_per_sec": round(win_core_per_sec, 4)
            }
            
            # Optionally include sample details
            if export_samples:
                window_data["samples"] = [
                    {
                        "comm": s["comm"],
                        "pid": s["pid"],
                        "cpu": s["cpu"],
                        "timestamp": s["ts"],
                        "stack": s["stack"].get_normalized_names() if s.get("stack") else []
                    }
                    for s in win_samples_raw
                ]
            else:
                # Keep reference for anomaly detection
                window_data["_samples"] = win_samples_raw
            
            windows.append(window_data)
        
        all_windows_by_cpu[cpu_id] = windows
        
        # Detect anomalies (skip in pure export mode unless requested)
        if not export_mode or args.detect_in_export:
            cpu_anomalies = _detect_cpu_anomalies(cpu_id, windows, spike_threshold, min_utilization)
            all_anomalies.extend(cpu_anomalies)
    
    # Export mode: return all window data
    if export_mode:
        # Clean up internal fields
        for cpu_id, windows in all_windows_by_cpu.items():
            for w in windows:
                w.pop("_samples", None)
        
        # Calculate overall statistics
        all_utils = []
        for windows in all_windows_by_cpu.values():
            all_utils.extend([w["utilization"] for w in windows])
        
        if all_utils:
            mean_util = sum(all_utils) / len(all_utils)
            variance = sum((u - mean_util) ** 2 for u in all_utils) / len(all_utils)
            std_util = variance ** 0.5
        else:
            mean_util = std_util = 0
        
        result = {
            "mode": "export",
            "time_range": {
                "start": samples[0]['ts'],
                "end": samples[-1]['ts'],
                "duration_sec": round(duration, 2)
            },
            "filters": {
                "start_time": getattr(args, 'start_time', None),
                "end_time": getattr(args, 'end_time', None),
                "cpu_id": getattr(args, 'cpu_id', None)
            },
            "data_quality": {
                "level": quality_level,
                "warning": warning_msg,
                "metrics": metrics
            },
            "export_config": {
                "window_size_sec": window_size,
                "export_samples": export_samples,
                "cpu_count": len(all_windows_by_cpu),
                "total_windows": sum(len(w) for w in all_windows_by_cpu.values())
            },
            "statistics": {
                "mean_utilization": round(mean_util, 4),
                "std_utilization": round(std_util, 4),
                "mean_utilization_pct": f"{mean_util*100:.2f}%",
                "std_utilization_pct": f"{std_util*100:.2f}%"
            },
            "windows_by_cpu": all_windows_by_cpu
        }
        
        # Include anomalies if detected in export mode
        if args.detect_in_export and all_anomalies:
            result["anomalies_detected"] = all_anomalies[:args.top_n]
        
        if quality_level == "CRITICAL":
            result["_WARNING"] = "数据质量不足，时间窗口数据完全不可信。"
        elif quality_level in ["WARNING", "ACCEPTABLE"]:
            result["_NOTICE"] = "数据质量中等，时间窗口中的利用率数据仅供参考。"
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    # Normal anomaly detection mode
    all_anomalies.sort(key=lambda x: abs(x.get("change_magnitude", 0)), reverse=True)
    
    summary = {
        "total_anomalies_found": len(all_anomalies),
        "spike_count": sum(1 for a in all_anomalies if a["type"] == "SPIKE"),
        "drop_count": sum(1 for a in all_anomalies if a["type"] == "DROP"),
        "level_shift_count": sum(1 for a in all_anomalies if a["type"] == "LEVEL_SHIFT"),
        "burst_count": sum(1 for a in all_anomalies if a["type"] == "BURST"),
        "window_size_sec": window_size,
        "analyzed_cpus": list(cpu_samples.keys())
    }
    
    result = {
        "mode": "anomaly_detection",
        "time_range": {
            "start": samples[0]['ts'],
            "end": samples[-1]['ts'],
            "duration_sec": round(duration, 2)
        },
        "filters": {
            "start_time": getattr(args, 'start_time', None),
            "end_time": getattr(args, 'end_time', None),
            "cpu_id": getattr(args, 'cpu_id', None)
        },
        "data_quality": {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        },
        "summary": summary,
        "anomalies": all_anomalies[:args.top_n],
        "recommendations": _generate_recommendations(all_anomalies)
    }
    
    if quality_level in ["WARNING", "ACCEPTABLE"]:
        result["_NOTICE"] = "数据质量中等，可能遗漏短时异常。检测到的异常模式可信，但可能有未捕获的事件。"
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _detect_cpu_anomalies(cpu_id, windows, spike_threshold, min_utilization):
    """Detect anomalies for a single CPU's time windows"""
    anomalies = []
    
    if len(windows) < 3:
        return anomalies
    
    # Calculate global stats for Z-score based detection
    utilizations = [w["utilization"] for w in windows if w["record_count"] > 0]
    if not utilizations:
        return anomalies
    
    mean_util = sum(utilizations) / len(utilizations)
    std_util = (sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)) ** 0.5
    
    for i in range(1, len(windows) - 1):
        prev_win = windows[i-1]
        curr_win = windows[i]
        next_win = windows[i+1]
        
        # Skip windows with no records
        if curr_win["record_count"] == 0:
            continue
        
        curr_util = curr_win["utilization"]
        prev_util = prev_win["utilization"]
        next_util = next_win["utilization"]
        
        # Calculate change rates
        change_from_prev = curr_util - prev_util
        change_to_next = next_util - curr_util
        
        # Z-score for statistical anomaly detection
        z_score = (curr_util - mean_util) / std_util if std_util > 0 else 0
        
        anomaly = None
        
        # Pattern 1: SPIKE - Sudden increase followed by decrease
        if (change_from_prev > spike_threshold and 
            change_to_next < -spike_threshold / 2 and
            curr_util > min_utilization):
            anomaly = {
                "type": "SPIKE",
                "cpu_id": cpu_id,
                "window": {
                    "start": round(curr_win["start_time"], 3),
                    "end": round(curr_win["end_time"], 3),
                    "duration_sec": round(curr_win["end_time"] - curr_win["start_time"], 3)
                },
                "utilization": {
                    "before": f"{prev_util*100:.1f}%",
                    "during": f"{curr_util*100:.1f}%",
                    "after": f"{next_util*100:.1f}%"
                },
                "change_magnitude": round(change_from_prev, 3),
                "z_score": round(z_score, 2),
                "core_sec": round(curr_win["total_core_per_sec"], 4),
                "description": f"CPU spike detected: {prev_util*100:.1f}% -> {curr_util*100:.1f}% -> {next_util*100:.1f}%"
            }
        
        # Pattern 2: DROP - Sudden decrease (inverse of spike)
        elif (change_from_prev < -spike_threshold and 
              change_to_next > spike_threshold / 2 and
              prev_util > min_utilization):
            anomaly = {
                "type": "DROP",
                "cpu_id": cpu_id,
                "window": {
                    "start": round(curr_win["start_time"], 3),
                    "end": round(curr_win["end_time"], 3),
                    "duration_sec": round(curr_win["end_time"] - curr_win["start_time"], 3)
                },
                "utilization": {
                    "before": f"{prev_util*100:.1f}%",
                    "during": f"{curr_util*100:.1f}%",
                    "after": f"{next_util*100:.1f}%"
                },
                "change_magnitude": round(abs(change_from_prev), 3),
                "z_score": round(abs(z_score), 2),
                "core_sec": round(curr_win["total_core_per_sec"], 4),
                "description": f"CPU drop detected: {prev_util*100:.1f}% -> {curr_util*100:.1f}% -> {next_util*100:.1f}%"
            }
        
        # Pattern 3: LEVEL_SHIFT - Sustained change in baseline
        elif (abs(change_from_prev) > spike_threshold / 2 and
              abs(change_to_next) < spike_threshold / 4 and
              curr_util > min_utilization):
            shift_type = "HIGH_TO_LOW" if change_from_prev < 0 else "LOW_TO_HIGH"
            anomaly = {
                "type": "LEVEL_SHIFT",
                "subtype": shift_type,
                "cpu_id": cpu_id,
                "window": {
                    "start": round(curr_win["start_time"], 3),
                    "end": round(curr_win["end_time"], 3),
                    "duration_sec": round(curr_win["end_time"] - curr_win["start_time"], 3)
                },
                "utilization": {
                    "before": f"{prev_util*100:.1f}%",
                    "after": f"{curr_util*100:.1f}%",
                    "sustained": True
                },
                "change_magnitude": round(abs(change_from_prev), 3),
                "z_score": round(abs(z_score), 2),
                "core_sec": round(curr_win["total_core_per_sec"], 4),
                "description": f"Baseline shift {shift_type}: {prev_util*100:.1f}% -> {curr_util*100:.1f}% (sustained)"
            }
        
        # Pattern 4: BURST - Very short high-utilization window (micro-burst)
        elif (z_score > 2.0 and curr_util > 0.8 and 
              prev_util < 0.3 and next_util < 0.3):
            anomaly = {
                "type": "BURST",
                "cpu_id": cpu_id,
                "window": {
                    "start": round(curr_win["start_time"], 3),
                    "end": round(curr_win["end_time"], 3),
                    "duration_sec": round(curr_win["end_time"] - curr_win["start_time"], 3)
                },
                "utilization": {
                    "before": f"{prev_util*100:.1f}%",
                    "during": f"{curr_util*100:.1f}%",
                    "after": f"{next_util*100:.1f}%"
                },
                "change_magnitude": round(curr_util, 3),
                "z_score": round(z_score, 2),
                "core_sec": round(curr_win["total_core_per_sec"], 4),
                "description": f"Micro-burst detected: isolated {curr_util*100:.1f}% utilization spike"
            }
        
        if anomaly:
            # Add recommended actions
            anomaly["recommended_actions"] = _get_recommended_actions(anomaly)
            anomalies.append(anomaly)
    
    return anomalies


def _get_recommended_actions(anomaly):
    """Generate recommended analysis actions for an anomaly"""
    actions = []
    cpu_id = anomaly["cpu_id"]
    start_time = anomaly["window"]["start"]
    end_time = anomaly["window"]["end"]
    
    actions.append(f"Run: get-hotspots --cpu-id {cpu_id} to see what was running on CPU-{cpu_id}")
    
    if anomaly["type"] in ["SPIKE", "BURST"]:
        actions.append(f"Run: cluster-symbols --cpu-id {cpu_id} to check for system-level issues (scheduling, locks, interrupts)")
    
    if anomaly.get("z_score", 0) > 2.5:
        actions.append("High Z-score indicates statistical anomaly - worth investigating")
    
    actions.append(f"Time range to focus on: {start_time}s - {end_time}s")
    
    return actions


def _generate_recommendations(all_anomalies):
    """Generate overall recommendations based on anomaly patterns"""
    if not all_anomalies:
        return ["No significant CPU utilization anomalies detected. System appears stable."]
    
    recommendations = []
    
    # Check for specific patterns
    burst_count = sum(1 for a in all_anomalies if a["type"] == "BURST")
    spike_count = sum(1 for a in all_anomalies if a["type"] == "SPIKE")
    level_shifts = [a for a in all_anomalies if a["type"] == "LEVEL_SHIFT"]
    
    if burst_count > 0:
        recommendations.append(f"Found {burst_count} micro-burst(s). These may indicate event-driven processing or timer-based batch operations. Check for periodic jobs or I/O bursts.")
    
    if spike_count > 2:
        recommendations.append(f"Detected {spike_count} spikes. If these are periodic, check cron jobs or background tasks. If random, may indicate lock contention or resource competition.")
    
    if level_shifts:
        high_to_low = sum(1 for a in level_shifts if a.get("subtype") == "HIGH_TO_LOW")
        low_to_high = sum(1 for a in level_shifts if a.get("subtype") == "LOW_TO_HIGH")
        if low_to_high > high_to_low:
            recommendations.append("More LOW_TO_HIGH shifts detected. System may be experiencing increasing load or starting new workloads.")
        elif high_to_low > low_to_high:
            recommendations.append("More HIGH_TO_LOW shifts detected. Workloads may be completing or throttling may be occurring.")
    
    # Check for multi-CPU correlation
    cpus_with_anomalies = set(a["cpu_id"] for a in all_anomalies)
    if len(cpus_with_anomalies) > 1:
        recommendations.append(f"Anomalies detected on {len(cpus_with_anomalies)} different CPUs. Check for cross-CPU interference or global locks.")
    
    return recommendations
