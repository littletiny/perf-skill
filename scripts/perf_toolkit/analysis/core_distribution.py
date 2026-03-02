#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core Distribution Analysis - Analyze per-core CPU utilization

V3 版本（三层架构）：
- 提取 CoreDistAnalyzer 纯逻辑类
- 分析各 CPU 核心的负载分布
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict
from .base import BaseAnalyzer
from .models import Risk, CoreStat


def parse_cpu_quota(value: str) -> float:
    """
    Parse CPU quota string to float.
    
    Args:
        value: CPU quota string like '0.1c', '2c', '0.5'
        
    Returns:
        CPU quota as float (cores)
    """
    if value.endswith('c'):
        return float(value[:-1])
    return float(value)


class CoreDistAnalyzer(BaseAnalyzer):
    """
    核心分布分析器
    
    分析各 CPU 核心的负载分布，识别负载不均衡。
    """
    
    # 不均衡阈值
    IMBALANCE_CRITICAL = 10.0   # 极不均衡
    IMBALANCE_HIGH = 5.0        # 严重不均衡
    IMBALANCE_MEDIUM = 2.0      # 中度不均衡
    SATURATION_THRESHOLD = 90.0  # 核心饱和阈值
    
    def analyze(self, samples: List[Dict], top_n: int = 10) -> Dict[str, Any]:
        """
        分析核心级负载分布
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个饱和核心
            
        Returns:
            {
                "result": {
                    "cores": [...],
                    "imbalance_level": str,
                    "saturated_cores": [...]
                },
                "risks": [...]
            }
        """
        if not samples:
            return {
                "result": {
                    "cores": [],
                    "imbalance_level": "UNKNOWN",
                    "saturated_cores": []
                },
                "risks": []
            }
        
        # 1. 从 engine 获取核心级 CPU 利用率
        core_util = self._engine.get_core_cpu_util(samples)
        
        # 2. 构建核心列表
        cores: List[CoreStat] = []
        for cpu_id, info in sorted(core_util.items(), key=lambda x: x[1].total_pct, reverse=True):
            cores.append(CoreStat(
                cpu_id=cpu_id,
                total_cpu=info.total_pct,
                kernel_cpu=info.kernel_pct,
                user_cpu=info.user_pct
            ))
        
        # 3. 检测不均衡
        imbalance_level = "LOW"
        saturated_cores: List[CoreStat] = []
        risks: List[Risk] = []
        
        if len(cores) >= 2:
            max_util = cores[0].total_cpu
            min_util = cores[-1].total_cpu
            avg_util = sum(c.total_cpu for c in cores) / len(cores)
            
            imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
            
            # 分级判断
            if imbalance_ratio > self.IMBALANCE_CRITICAL and max_util > 50:
                imbalance_level = "CRITICAL"
            elif imbalance_ratio > self.IMBALANCE_HIGH:
                imbalance_level = "HIGH"
            elif imbalance_ratio > self.IMBALANCE_MEDIUM:
                imbalance_level = "MEDIUM"
            else:
                imbalance_level = "LOW"
            
            # 识别饱和核心
            saturated_cores = [c for c in cores if c.total_cpu > self.SATURATION_THRESHOLD]
            
            # 识别 risk
            if imbalance_level == "CRITICAL":
                risks.append(self._create_risk(
                    level="critical",
                    message="负载严重不均衡: 单核满载，其他核心空闲",
                    hint="使用 sys-audit 进行系统审计",
                    patterns=["SINGLE_CORE_SATURATION"]
                ))
            elif len(saturated_cores) == 1 and len(cores) > 1:
                risks.append(self._create_risk(
                    level="warning",
                    message=f"单核满载 (CPU {saturated_cores[0].cpu_id})",
                    hint="使用 sys-audit 分析负载分布",
                    patterns=["SINGLE_CORE_SATURATION"],
                    pending_targets=[f"cpu_{saturated_cores[0].cpu_id}"]
                ))
        
        return {
            "result": {
                "cores": [c.to_dict() for c in cores[:top_n]],
                "imbalance_level": imbalance_level,
                "saturated_cores": [c.to_dict() for c in saturated_cores],
                "total_cores": len(cores)
            },
            "risks": [r.to_dict() for r in risks]
        }


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import RiskInfo, CoreItem, CoreDistributionOutput, TimeRange


@command("analyze-core-distribution")
def cmd_analyze_core_distribution(builder, engine, args, samples):
    """[Skill] Analyze CPU core utilization distribution"""
    
    # 1. 调用 Analyzer
    analyzer = CoreDistAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        top_n=getattr(args, 'top_n', 10)
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
    cores = [
        CoreItem(
            cpu_id=c["cpu_id"],
            total_cpu_util=f"{c['total_cpu']:.2f}%",
            kernel_cpu_util=f"{c['kernel_cpu']:.2f}%"
        )
        for c in result["result"]["cores"]
    ]
    
    risk_output = create_risk_info(**top_risk) if top_risk else create_risk_info(level="none")
    
    output = CoreDistributionOutput(
        _risk=risk_output,
        cores=cores,
        time_range=TimeRange.from_timestamps(
            samples[0].get('ts') if samples else None,
            samples[-1].get('ts') if len(samples) > 1 else None
        )
    )
    
    return output
