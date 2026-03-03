#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotspot Analysis - Extract function rankings by self/inclusive time

V3 版本（三层架构）：
- 提取 HotspotsAnalyzer 纯逻辑类
- 支持符号级热点分析
- Task-2.5.1: 返回 HotspotsResult dataclass

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.defaults import RiskPattern, Thresholds

from .base import BaseAnalyzer
from ..core.engine_types import Sample
from ..core.models import RiskInfo
from .models import Hotspot, HotspotsResult
from ..core.output_models import RiskLevel


class HotspotsAnalyzer(BaseAnalyzer):
    """
    热点函数分析器
    
    分析符号级 CPU 利用率，识别热点函数。
    """
    
    # Risk 阈值 - 使用 config.defaults 中的常量
    KERNEL_HOTSPOT_THRESHOLD = Thresholds.KERNEL_RATIO_HIGH  # 内核态热点占比阈值
    
    def analyze(self, samples: List[Sample], 
                comm: Optional[str] = None,
                pid: Optional[int] = None,
                top_n: int = 20,
                sort_by: str = "self") -> HotspotsResult:
        """
        分析热点函数
        
        Args:
            samples: 样本数据
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤
            top_n: 返回前 N 个热点
            sort_by: 排序方式 - "self" | "inclusive"
            
        Returns:
            HotspotsResult dataclass
        """
        if not samples:
            return HotspotsResult(
                hotspots=[],
                kernel_ratio=0.0,
                user_ratio=100.0,
                sort_by=sort_by,
                risks=[]
            )
        
        # 1. 从 engine 获取符号级 CPU 利用率
        symbol_util = self._engine.get_symbol_cpu_util(samples, comm=comm, pid=pid)
        
        # 2. 构建热点列表
        hotspots: List[Hotspot] = []
        risks: List[RiskInfo] = []
        top_kernel_hotspot = None
        top_kernel_ratio = 0.0
        
        total_self = sum(symbol_util.self_pct.values()) if symbol_util.self_pct else 0
        total_kernel = 0.0
        
        for sym in symbol_util.inclusive_pct.keys():
            self_pct = symbol_util.self_pct.get(sym, 0.0)
            incl_pct = symbol_util.inclusive_pct[sym]
            
            # 识别内核态符号
            is_kernel = sym.endswith('_[k]')
            if is_kernel:
                total_kernel += self_pct
            
            # 追踪内核态热点
            if is_kernel and incl_pct > top_kernel_ratio:
                top_kernel_ratio = incl_pct
                top_kernel_hotspot = sym
            
            hotspots.append(Hotspot(
                symbol=sym,
                self_pct=self_pct,
                inclusive_pct=incl_pct,
                is_kernel=is_kernel
            ))
        
        # 3. 排序
        if sort_by == "self":
            hotspots.sort(key=lambda x: x.self_pct, reverse=True)
        else:
            hotspots.sort(key=lambda x: x.inclusive_pct, reverse=True)
        
        # 4. 计算内核态占比
        kernel_ratio = (total_kernel / total_self * 100) if total_self > 0 else 0.0
        
        # 5. 识别 risk
        if top_kernel_ratio > self.KERNEL_HOTSPOT_THRESHOLD:
            risks.append(self._create_risk(
                level="warning",
                message=f"热点函数 {top_kernel_hotspot} 内核态占比 {top_kernel_ratio:.2f}%",
                hint=f"find-callers --target {top_kernel_hotspot}",
                patterns=[RiskPattern.HIGH_KERNEL_HOTSPOT],
                pending_targets=[top_kernel_hotspot]
            ))
        
        return HotspotsResult(
            hotspots=hotspots[:top_n],
            kernel_ratio=kernel_ratio,
            user_ratio=100.0 - kernel_ratio,
            sort_by=sort_by,
            risks=risks
        )


# =============================================================================
# CLI 适配层（保持向后兼容）
# =============================================================================

from ..core.command_decorator import command
from ..core.output_models import (
    RiskInfo, HotspotItem, HotspotSummary, HotspotsOutput, TimeRange
)


@command("get-hotspots")
def cmd_get_hotspots(builder, engine, args, samples):
    """[Skill] Extract macro hotspot paths or function rankings"""
    
    # 1. 调用 Analyzer
    analyzer = HotspotsAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        comm=getattr(args, 'comm', None),
        pid=getattr(args, 'pid', None),
        top_n=getattr(args, 'top_n', 10),
        sort_by=getattr(args, 'sort_by', 'self')
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
        top_risk = min(result.risks, key=lambda r: RiskLevel.from_string(r.level).value)
    
    # 4. 转换为 Output 模型
    hotspots = [
        HotspotItem.from_stats(
            symbol=h.symbol,
            self_pct=h.self_pct,
            inclusive_pct=h.inclusive_pct
        )
        for h in result.hotspots
    ]
    
    risk_output = RiskInfo(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else RiskInfo(level="none")
    
    output = HotspotsOutput(
        _risk=risk_output,
        hotspots=hotspots,
        summary=HotspotSummary(
            total_hotspots=len(result.hotspots),
            shown_hotspots=len(hotspots)
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None if samples else None,
            samples[-1].ts if len(samples) > 1 else None if len(samples) > 1 else None
        )
    )
    
    return output
