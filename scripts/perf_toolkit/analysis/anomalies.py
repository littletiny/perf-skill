#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection - Detect CPU utilization anomalies

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

from collections import defaultdict
from ..core.format_utils import format_timestamp
from ..core.output_builder import OutputBuilder, create_risk_info
from ..core.output_models import (
    RiskInfo, AnomalyItem, AnomalySummary, AnomaliesOutput,
    WindowItem, WindowSummary, WindowsOutput, TimeRange
)


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
    if builder.assess_quality(samples, early_return=True):
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
            
            win_weight = sum(engine.get_sample_weight(s) for s in win_samples_raw)
            utilization = win_weight / window_size if window_size > 0 else 0
            
            window_data = {
                "cpu_id": cpu_id_val,
                "start_time": format_timestamp(win_start),
                "end_time": format_timestamp(win_end),
                "utilization": f"{utilization*100:.2f}%",
                "weight": round(win_weight, 4)
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
        
        # 创建 WindowItem 数据项
        window_items = []
        for windows in all_windows_by_cpu.values():
            for w in windows:
                window_items.append(WindowItem(
                    cpu_id=w["cpu_id"],
                    start_time=w["start_time"],
                    end_time=w["end_time"],
                    utilization=w["utilization"],
                    weight=w["weight"]
                ))
        
        # 确定风险等级
        if args.detect_in_export and all_anomalies:
            risk = create_risk_info(
                level="warning",
                message=f"export 模式下检测到 {len(all_anomalies)} 个异常",
                patterns=["ANOMALY_IN_EXPORT"]
            )
        else:
            risk = create_risk_info(level="none")
        
        # 创建摘要
        summary = WindowSummary(
            mode="export",
            window_size_sec=window_size,
            export_samples=export_samples,
            cpu_count=len(all_windows_by_cpu),
            total_windows=sum(len(w) for w in all_windows_by_cpu.values())
        )
        
        # 创建时间范围
        time_range = TimeRange.from_timestamps(
            samples[0]['ts'] if samples else None,
            samples[-1]['ts'] if samples else None
        )
        
        # 创建统计信息
        statistics = {
            "mean_utilization": f"{mean_util*100:.2f}%",
            "std_utilization": f"{std_util*100:.2f}%"
        }
        
        # 构建输出
        output = WindowsOutput(
            _risk=risk,
            windows=window_items,
            summary=summary,
            time_range=time_range,
            statistics=statistics
        )
        
        builder.print_output(output)
        return
    
    # Normal anomaly detection mode
    all_anomalies.sort(key=lambda x: abs(x.get("change_magnitude", 0)), reverse=True)
    
    spike_count = sum(1 for a in all_anomalies if a["type"] == "SPIKE")
    drop_count = sum(1 for a in all_anomalies if a["type"] == "DROP")
    
    # 确定风险等级
    if spike_count > 0:
        risk = create_risk_info(
            level="warning",
            message=f"检测到 {spike_count} 个 CPU 利用率异常尖峰",
            hint=f"[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '检测到 {spike_count} 个 CPU 利用率异常尖峰' --risk 'warning' --hint 'get-hotspots --start-time {format_timestamp(samples[0]['ts'])}'",
            patterns=["CPU_SPIKE"]
        )
    else:
        risk = create_risk_info(level="none")
    
    # 创建 AnomalyItem（原始数据，格式由模板处理）
    anomaly_items = [
        AnomalyItem.from_raw(
            type=a["type"],
            cpu_id=a["cpu_id"],
            start=a["time_range_start"],
            end=a["time_range_end"],
            prev=a["prev_util"],
            curr=a["curr_util"],
            next=a["next_util"],
            z_score=a["z_score"]
        )
        for a in all_anomalies[:top_n]
    ]
    
    # 创建摘要
    summary = AnomalySummary(
        total_anomalies=len(all_anomalies),
        spike_count=spike_count,
        drop_count=drop_count
    )
    
    # 创建时间范围
    time_range = TimeRange.from_timestamps(
        samples[0]['ts'] if samples else None,
        samples[-1]['ts'] if samples else None
    )
    
    # 构建输出
    output = AnomaliesOutput(
        _risk=risk,
        anomalies=anomaly_items,
        summary=summary,
        time_range=time_range
    )
    
    builder.print_output(output)


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
                "time_range_start": start_time,
                "time_range_end": end_time,
                "prev_util": prev_util,
                "curr_util": curr_util,
                "next_util": next_util,
                "z_score": round(z_score, 2)
            })
        
        # DROP detection
        elif (change_from_prev < -spike_threshold and 
              change_to_next > spike_threshold / 2 and
              prev_util > min_utilization):
            anomalies.append({
                "type": "DROP",
                "cpu_id": cpu_id,
                "time_range_start": start_time,
                "time_range_end": end_time,
                "prev_util": prev_util,
                "curr_util": curr_util,
                "next_util": next_util,
                "z_score": round(abs(z_score), 2)
            })
    
    return anomalies



