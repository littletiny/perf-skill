#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection - Detect CPU utilization anomalies

V2 版本：使用统一数据模型，CPU 利用率计算收拢到 engine
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import List
from ..core.command_decorator import command
from ..core.format_utils import format_timestamp
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, AnomalyItem, AnomalySummary, AnomaliesOutput,
    WindowItem, WindowSummary, WindowsOutput, TimeRange
)


# =============================================================================
# Internal Data Structures
# =============================================================================

@dataclass
class WindowRawData:
    """窗口原始数据 - 异常检测中间结构"""
    cpu_id: int
    start_time: str
    end_time: str
    utilization: str
    weight: float

    def get_utilization_float(self) -> float:
        """获取利用率数值（0-1范围）"""
        return float(self.utilization.rstrip('%')) / 100


@dataclass
class AnomalyRawData:
    """异常检测原始数据 - 中间结构"""
    type: str  # "SPIKE" | "DROP"
    cpu_id: int
    time_range_start: str
    time_range_end: str
    prev_util: float
    curr_util: float
    next_util: float
    z_score: float

    @property
    def change_magnitude(self) -> float:
        """变化幅度（用于排序）"""
        return abs(self.curr_util - self.prev_util)

    def to_anomaly_item(self) -> AnomalyItem:
        """转换为输出模型"""
        return AnomalyItem.from_raw(
            type=self.type,
            cpu_id=self.cpu_id,
            start=self.time_range_start,
            end=self.time_range_end,
            prev=self.prev_util,
            curr=self.curr_util,
            next=self.next_util,
            z_score=self.z_score
        )


@command("detect-anomalies")
def cmd_detect_anomalies(builder, engine, args, samples):
    """[Skill] Detect CPU utilization anomalies or export window data"""

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

            window_data = WindowRawData(
                cpu_id=cpu_id_val,
                start_time=format_timestamp(win_start),
                end_time=format_timestamp(win_end),
                utilization=f"{utilization*100:.2f}%",
                weight=round(win_weight, 4)
            )

            windows.append(window_data)

        all_windows_by_cpu[cpu_id_val] = windows

        if not export_mode or args.detect_in_export:
            cpu_anomalies = _detect_cpu_anomalies(cpu_id_val, windows, spike_threshold, min_utilization)
            all_anomalies.extend(cpu_anomalies)

    # Export mode
    if export_mode:
        all_utils = []
        for windows in all_windows_by_cpu.values():
            all_utils.extend([w.get_utilization_float() for w in windows])

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
                    cpu_id=w.cpu_id,
                    start_time=w.start_time,
                    end_time=w.end_time,
                    utilization=w.utilization,
                    weight=w.weight
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

        return output

    # Normal anomaly detection mode
    all_anomalies.sort(key=lambda x: x.change_magnitude, reverse=True)

    spike_count = sum(1 for a in all_anomalies if a.type == "SPIKE")
    drop_count = sum(1 for a in all_anomalies if a.type == "DROP")

    # 确定风险等级
    if spike_count > 0:
        risk = create_risk_info(
            level="warning",
            message=f"检测到 {spike_count} 个 CPU 利用率异常尖峰",
            hint=f"[必须] 添加到 Trace: spear trace add --desc '检测到 {spike_count} 个 CPU 利用率异常尖峰' --hint 'get-hotspots --start-time {format_timestamp(samples[0]['ts'])}'",
            patterns=["CPU_SPIKE"]
        )
    else:
        risk = create_risk_info(level="none")

    # 创建 AnomalyItem（原始数据，格式由模板处理）
    anomaly_items = [a.to_anomaly_item() for a in all_anomalies[:top_n]]

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

    return output


def _detect_cpu_anomalies(cpu_id: int, windows: List[WindowRawData], spike_threshold: float,
                          min_utilization: float) -> List[AnomalyRawData]:
    """Detect anomalies for a single CPU's time windows"""
    anomalies: List[AnomalyRawData] = []

    if len(windows) < 3:
        return anomalies

    utilizations = [w.get_utilization_float() for w in windows]
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

        # SPIKE detection
        if (change_from_prev > spike_threshold and
            change_to_next < -spike_threshold / 2 and
            curr_util > min_utilization):
            anomalies.append(AnomalyRawData(
                type="SPIKE",
                cpu_id=cpu_id,
                time_range_start=win.start_time,
                time_range_end=win.end_time,
                prev_util=prev_util,
                curr_util=curr_util,
                next_util=next_util,
                z_score=round(z_score, 2)
            ))

        # DROP detection
        elif (change_from_prev < -spike_threshold and
              change_to_next > spike_threshold / 2 and
              prev_util > min_utilization):
            anomalies.append(AnomalyRawData(
                type="DROP",
                cpu_id=cpu_id,
                time_range_start=win.start_time,
                time_range_end=win.end_time,
                prev_util=prev_util,
                curr_util=curr_util,
                next_util=next_util,
                z_score=round(abs(z_score), 2)
            ))

    return anomalies
