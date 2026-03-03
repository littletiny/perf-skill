#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection - Detect CPU utilization anomalies

V3 版本（三层架构）：
- 提取 AnomaliesAnalyzer 纯逻辑类
- 支持时序异常检测
- Task-2.2.1: 返回 AnomaliesResult dataclass
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from .base import BaseAnalyzer
from .models import Risk, Anomaly, AnomaliesResult


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


# =============================================================================
# AnomaliesAnalyzer
# =============================================================================

class AnomaliesAnalyzer(BaseAnalyzer):
    """
    异常检测分析器
    
    检测 CPU 利用率的时序异常（尖峰、跌落）。
    """
    
    def analyze(self, samples: List[Dict],
                window_size: float = 1.0,
                spike_threshold: float = 0.5,
                min_utilization: float = 0.3,
                cpu_id: Optional[int] = None,
                top_n: int = 10) -> AnomaliesResult:
        """
        分析时序异常
        
        Args:
            samples: 样本数据
            window_size: 滑动窗口大小（秒）
            spike_threshold: 变化倍数阈值
            min_utilization: 最小利用率阈值
            cpu_id: 可选，仅分析指定 CPU
            top_n: 返回前 N 个异常
            
        Returns:
            AnomaliesResult dataclass
        """
        if not samples:
            return AnomaliesResult(
                anomalies=[],
                mutation_detected=False,
                spike_count=0,
                drop_count=0,
                risks=[]
            )
        
        # 1. 按 CPU 分组样本
        cpu_samples = defaultdict(list)
        for s in samples:
            if cpu_id is None or s['cpu'] == cpu_id:
                cpu_samples[s['cpu']].append(s)
        
        all_anomalies: List[Anomaly] = []
        
        # 2. 对每个 CPU 进行异常检测
        for cpu_id_val, cpu_samples_list in cpu_samples.items():
            if not cpu_samples_list:
                continue
            
            cpu_samples_list.sort(key=lambda x: x['ts'])
            start_ts = cpu_samples_list[0]['ts']
            end_ts = cpu_samples_list[-1]['ts']
            cpu_duration = end_ts - start_ts
            
            if cpu_duration < window_size:
                continue
            
            # 构建时间窗口
            windows = self._build_windows(
                cpu_samples_list, window_size, cpu_id_val
            )
            
            # 检测异常
            cpu_anomalies = self._detect_anomalies(
                cpu_id_val, windows, spike_threshold, min_utilization
            )
            all_anomalies.extend(cpu_anomalies)
        
        # 3. 排序
        all_anomalies.sort(key=lambda x: x.change_magnitude, reverse=True)
        
        # 4. 识别 risk
        risks: List[Risk] = []
        spike_count = sum(1 for a in all_anomalies if a.type == "SPIKE")
        
        if spike_count > 0:
            risks.append(self._create_risk(
                level="warning",
                message=f"检测到 {spike_count} 个 CPU 利用率异常尖峰",
                hint="查看异常时间点，分析对应时间段",
                patterns=["CPU_SPIKE"]
            ))
        
        return AnomaliesResult(
            anomalies=all_anomalies[:top_n],
            mutation_detected=len(all_anomalies) > 0,
            spike_count=spike_count,
            drop_count=len(all_anomalies) - spike_count,
            risks=risks
        )
    
    def _build_windows(self, samples: List[Dict], window_size: float, 
                       cpu_id: int) -> List[WindowRawData]:
        """构建时间窗口"""
        from ..core.format_utils import format_timestamp
        
        start_ts = samples[0]['ts']
        end_ts = samples[-1]['ts']
        duration = end_ts - start_ts
        
        n_windows = int(duration / window_size) + 1
        windows: List[WindowRawData] = []
        
        for i in range(n_windows):
            win_start = start_ts + i * window_size
            win_end = win_start + window_size
            win_samples = [s for s in samples if win_start <= s['ts'] < win_end]
            
            weight = sum(self._engine.get_sample_weight(s) for s in win_samples)
            utilization = weight / window_size if window_size > 0 else 0
            
            window_data = WindowRawData(
                cpu_id=cpu_id,
                start_time=format_timestamp(win_start),
                end_time=format_timestamp(win_end),
                utilization=f"{utilization*100:.2f}%",
                weight=round(weight, 4)
            )
            windows.append(window_data)
        
        return windows
    
    def _detect_anomalies(self, cpu_id: int, windows: List[WindowRawData],
                          spike_threshold: float, 
                          min_utilization: float) -> List[Anomaly]:
        """检测单个 CPU 的异常"""
        anomalies: List[Anomaly] = []
        
        if len(windows) < 3:
            return anomalies
        
        utilizations = [w.get_utilization_float() for w in windows]
        if not utilizations:
            return anomalies
        
        mean_util = sum(utilizations) / len(utilizations)
        variance = sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)
        std_util = variance ** 0.5
        
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
                anomalies.append(Anomaly(
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
                anomalies.append(Anomaly(
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


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, AnomalyItem, AnomalySummary, AnomaliesOutput, TimeRange
)


@command("detect-anomalies")
def cmd_detect_anomalies(builder, engine, args, samples):
    """[Skill] Detect CPU utilization anomalies"""
    
    # 1. 调用 Analyzer
    analyzer = AnomaliesAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        window_size=getattr(args, 'window_size', 1.0),
        spike_threshold=getattr(args, 'spike_threshold', 0.5),
        min_utilization=getattr(args, 'min_utilization', 0.3),
        cpu_id=getattr(args, 'cpu_id', None),
        top_n=getattr(args, 'top_n', 10)
    )
    
    # 2. 记录 risks 到 Trace
    for risk in result.risks:
        builder.record_risk(
            risk.level,
            risk.message,
            risk.hint
        )
    
    # 3. 取最高级别 risk
    top_risk = None
    if result.risks:
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top_risk = min(result.risks, key=lambda r: priority.get(r.level, 3))
    
    # 4. 转换为 Output 模型
    anomaly_items = [
        AnomalyItem.from_raw(
            type=a.type,
            cpu_id=a.cpu_id,
            start=a.time_range_start,
            end=a.time_range_end,
            prev=a.prev_util,
            curr=a.curr_util,
            next=a.next_util,
            z_score=a.z_score
        )
        for a in result.anomalies
    ]
    
    risk_output = create_risk_info(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else create_risk_info(level="none")
    
    output = AnomaliesOutput(
        _risk=risk_output,
        anomalies=anomaly_items,
        summary=AnomalySummary(
            total_anomalies=result.spike_count + result.drop_count,
            spike_count=result.spike_count,
            drop_count=result.drop_count
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].get('ts') if samples else None,
            samples[-1].get('ts') if len(samples) > 1 else None
        )
    )
    
    return output
