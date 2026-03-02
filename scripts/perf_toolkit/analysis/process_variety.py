#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Variety Analysis - Count process variety to detect short-lived process storms

V3 版本（三层架构）：
- 提取 ProcessVarietyAnalyzer 纯逻辑类
- 支持进程风暴检测
"""

from collections import defaultdict
from typing import Dict, List, Any, Optional
from .base import BaseAnalyzer
from .models import Risk, ProcessVariety


class ProcessVarietyAnalyzer(BaseAnalyzer):
    """
    进程多样性分析器
    
    检测进程风暴/短生命周期进程。
    """
    
    # 风暴检测阈值
    STORM_PID_THRESHOLD_DEFAULT = 50      # 默认 PID 数量阈值
    STORM_CPU_THRESHOLD_DEFAULT = 0.5     # 默认单 PID CPU 阈值
    STORM_RATIO_THRESHOLD_DEFAULT = 2.0   # 默认 samples/PID 阈值
    STORM_MIN_PIDS = 10                   # 最小 PID 数（低于此值不认为是风暴）
    
    def analyze(self, samples: List[Dict],
                top_n: int = 20,
                storm_pid_threshold: int = None,
                storm_cpu_threshold: float = None,
                storm_ratio_threshold: float = None,
                comm: Optional[str] = None) -> Dict[str, Any]:
        """
        分析进程多样性，检测进程风暴
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个结果
            storm_pid_threshold: PID 数量阈值
            storm_cpu_threshold: 单 PID CPU 阈值
            storm_ratio_threshold: samples/PID 阈值
            comm: 可选，按进程名过滤
            
        Returns:
            {
                "result": {"processes": [...], "storm_comms": [...]},
                "risks": [...]
            }
        """
        if not samples:
            return {
                "result": {"processes": [], "storm_comms": []},
                "risks": []
            }
        
        # 使用默认值
        pid_threshold = storm_pid_threshold or self.STORM_PID_THRESHOLD_DEFAULT
        cpu_threshold = storm_cpu_threshold or self.STORM_CPU_THRESHOLD_DEFAULT
        ratio_threshold = storm_ratio_threshold or self.STORM_RATIO_THRESHOLD_DEFAULT
        
        # 1. 聚合 comm-pid 统计
        comm_pid_stats = defaultdict(lambda: defaultdict(lambda: {
            'weight': 0.0,
            'seconds': set(),
        }))
        
        for s in samples:
            s_comm = s['comm']
            if comm and s_comm != comm:
                continue
            
            pid = s['pid']
            ts = s['ts']
            weight = self._engine.get_sample_weight(s)
            
            comm_pid_stats[s_comm][pid]['weight'] += weight
            comm_pid_stats[s_comm][pid]['seconds'].add(int(ts))
        
        # 2. 获取时间范围
        duration = self._engine.get_duration(samples)
        duration_minutes = duration / 60 if duration > 0 else 0
        
        # 3. 分析多样性
        processes: List[ProcessVariety] = []
        storm_comms: List[str] = []
        
        for comm_name, pid_dict in sorted(comm_pid_stats.items(), key=lambda x: -len(x[1])):
            pid_count = len(pid_dict)
            total_comm_weight = sum(stats['weight'] for stats in pid_dict.values())
            cpu_per_pid = total_comm_weight / pid_count if pid_count > 0 else 0
            
            single_second_pids = sum(1 for stats in pid_dict.values() if len(stats['seconds']) == 1)
            short_lived_ratio = single_second_pids / pid_count if pid_count > 0 else 0
            
            total_samples_for_comm = sum(len(stats['seconds']) for stats in pid_dict.values())
            samples_per_pid = total_samples_for_comm / pid_count if pid_count > 0 else 0
            
            behavior = "normal"
            
            # 进程风暴检测（需要至少 10 个 PID）
            if pid_count >= self.STORM_MIN_PIDS:
                if samples_per_pid <= ratio_threshold and short_lived_ratio > 0.5:
                    behavior = "process_storm"
                    storm_comms.append(comm_name)
                elif cpu_per_pid <= cpu_threshold and short_lived_ratio > 0.5:
                    behavior = "process_storm"
                    storm_comms.append(comm_name)
            
            # 跳过正常行为和少量 PID
            if behavior == "normal" or pid_count < self.STORM_MIN_PIDS:
                continue
            
            # 计算 CPU 利用率
            cpu_util = (total_comm_weight / duration * 100) if duration > 0 else 0
            
            # 计算每分钟 PID 数
            pids_per_min = int(pid_count / duration_minutes) if duration_minutes > 0 else 0
            
            processes.append(ProcessVariety(
                comm=comm_name,
                pids_per_min=pids_per_min,
                cpu_util=cpu_util,
                behavior=behavior,
                pid_count=pid_count,
                samples_per_pid=samples_per_pid
            ))
        
        # 4. 识别 risk
        risks: List[Risk] = []
        if storm_comms:
            risks.append(self._create_risk(
                level="critical",
                message=f"检测到 {len(storm_comms)} 个进程风暴（短生命周期进程）",
                hint=f"storm-trace --comm {storm_comms[0]}",
                patterns=["PROCESS_STORM"],
                pending_targets=storm_comms
            ))
        
        return {
            "result": {
                "processes": [p.to_dict() for p in processes[:top_n]],
                "storm_comms": storm_comms,
                "storm_count": len(storm_comms),
                "total_processes": len(processes)
            },
            "risks": [r.to_dict() for r in risks]
        }


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import (
    RiskInfo, ProcessVarietyItem, ProcessVarietySummary, ProcessVarietyOutput, TimeRange
)


@command("count-process-variety")
def cmd_count_process_variety(builder, engine, args, samples):
    """[Skill] Count process variety - detect short-lived process storms"""
    
    # 1. 调用 Analyzer
    analyzer = ProcessVarietyAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        top_n=getattr(args, 'top_n', 20),
        storm_pid_threshold=getattr(args, 'storm_pid_threshold', 50),
        storm_cpu_threshold=getattr(args, 'storm_cpu_threshold', 0.5),
        storm_ratio_threshold=getattr(args, 'storm_ratio_threshold', 2.0),
        comm=getattr(args, 'comm', None)
    )
    
    # 2. 记录 risks 到 Trace
    for risk_dict in result["risks"]:
        builder.record_risk(
            risk_dict["level"],
            risk_dict["message"],
            risk_dict["hint"]
        )
    
    # 3. 取最高级别 risk
    top_risk = None
    if result["risks"]:
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top_risk = min(result["risks"], key=lambda r: priority.get(r["level"], 3))
    
    # 4. 转换为 Output 模型
    processes = [
        ProcessVarietyItem(
            comm=p["comm"],
            pids_per_min=p["pids_per_min"],
            cpu_util=f"{p['cpu_util']:.2f}%",
            behavior=p["behavior"]
        )
        for p in result["result"]["processes"]
    ]
    
    risk_output = create_risk_info(**top_risk) if top_risk else create_risk_info(level="none")
    
    time_range = TimeRange.from_timestamps(
        samples[0].get('ts') if samples else None,
        samples[-1].get('ts') if len(samples) > 1 else None
    )
    
    summary = ProcessVarietySummary(
        total_processes=result["result"]["total_processes"],
        storm_detected=len(result["result"]["storm_comms"]) > 0,
        storm_count=len(result["result"]["storm_comms"])
    )
    
    output = ProcessVarietyOutput(
        _risk=risk_output,
        process_variety=processes,
        summary=summary,
        time_range=time_range
    )
    
    return output
