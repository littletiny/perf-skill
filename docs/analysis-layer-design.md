# Analysis 层设计文档

> 角色: Analysis 工程师（人员B）
> 目标: 将现有 analysis 工具重构为三层架构中的 Analysis 层
> 依赖: Core Engine 接口（人员A Week 1 交付）

---

## 1. 设计目标

### 1.1 核心原则

| 原则 | 说明 | 约束 |
|------|------|------|
| 职责分离 | Analyzer 只负责纯分析逻辑 | 不处理 CLI/Trace/输出格式 |
| 数据边界 | 所有数据通过 Engine 接口获取 | 禁止直接访问原始样本数据 |
| 双接口设计 | 提供内部接口（Facade）和 CLI 接口 | CLI 接口通过 @command 包装 |
| Risk 内聚 | Analyzer 识别风险并返回 _risk 数据 | 由上层决定如何记录 |

### 1.2 重构前后对比

```
重构前（混合职责）:
┌─────────────────────────────────────────┐
│ @command("get-comm-top")                │
│ def cmd_get_comm_top(...):              │
│     # 数据获取                          │
│     # 分析逻辑                          │
│     # Risk 判断                         │
│     # Trace 记录                        │
│     # 输出构建                          │
└─────────────────────────────────────────┘

重构后（职责分离）:
┌─────────────────────────────────────────┐
│ class CommTopAnalyzer:                  │
│     def analyze(self, ...):             │
│         # 纯分析逻辑                    │
│         # 返回 {result, risks}          │
├─────────────────────────────────────────┤
│ @command("get-comm-top")                │
│ def cmd_get_comm_top(...):              │
│     # 调用 Analyzer                     │
│     # 记录 Trace                        │
│     # 构建输出                          │
└─────────────────────────────────────────┘
```

---

## 2. 架构设计

### 2.1 目录结构

```
analysis/
├── __init__.py                 # 包入口
├── facade.py                   # Facade 接口（由人员A提供框架）
├── interfaces.py               # 类型定义和接口契约
├── base.py                     # BaseAnalyzer 抽象基类
│
├── comm_top.py                 # CommTopAnalyzer + CLI
├── hotspots.py                 # HotspotsAnalyzer + CLI
├── core_distribution.py        # CoreDistAnalyzer + CLI
├── anomalies.py                # AnomaliesAnalyzer + CLI
├── path_clusters.py            # PathClusterAnalyzer + CLI
├── clusters.py                 # SymbolClusterAnalyzer + CLI
├── process_variety.py          # ProcessVarietyAnalyzer + CLI
└── trace.py                    # 保持现状（Trace 命令）
```

### 2.2 类层次结构

```
┌─────────────────────────────────────────────────────────────┐
│                    BaseAnalyzer (抽象基类)                   │
│  - engine: PerfExpertEngine                                 │
│  - analyze(samples, **kwargs) -> Dict                       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ CommTopAnalyzer       │    │ HotspotsAnalyzer      │    │ CoreDistAnalyzer      │
│ - _calculate_cv()     │    │ - _classify_hotspot() │    │ - _detect_imbalance() │
│ - _calculate_monopoly()    │    └───────────────┘    └───────────────┘
│ - _classify()         │
└───────────────┘
```

---

## 3. 核心类设计

### 3.1 BaseAnalyzer 抽象基类

```python
# analysis/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseAnalyzer(ABC):
    """
    Analysis 层抽象基类
    
    设计约束:
    1. 只依赖 engine 接口获取数据
    2. 不直接操作 trace
    3. 返回原始 dict，包含 result 和 risks
    """
    
    def __init__(self, engine: 'PerfExpertEngine'):
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Dict], **kwargs) -> Dict[str, Any]:
        """
        执行分析
        
        Args:
            samples: 样本数据（由 engine 过滤后提供）
            **kwargs: 分析特定参数
            
        Returns:
            {
                "result": Any,           # 分析结果（工具特定）
                "risks": List[Dict],     # 识别到的风险列表
                "metrics": Dict          # 中间指标（可选，供 Composite 使用）
            }
        """
        pass
    
    def _create_risk(self, level: str, message: str, hint: str = "",
                     patterns: List[str] = None, 
                     pending_targets: List[str] = None) -> Dict:
        """创建标准化的 risk 数据结构"""
        return {
            "level": level,  # critical | warning | info | none
            "message": message,
            "hint": hint,
            "patterns": patterns or [],
            "pending_targets": pending_targets or [],
            "action_required": level in ["critical", "warning"]
        }
```

### 3.2 Analyzer 统一返回格式

```python
# 所有 Analyzer 遵循的返回格式

AnalysisResult = {
    # ===== 分析结果（工具特定） =====
    "result": {
        # get-comm-top: {"groups": [...]}
        # get-hotspots: {"hotspots": [...]}
        # detect-anomalies: {"anomalies": [...]}
    },
    
    # ===== Risk 列表（供 Composite 聚合） =====
    "risks": [
        {
            "level": "critical",
            "message": "xxx 单核饱和",
            "hint": "bottleneck-trace --comm xxx",
            "patterns": ["SINGLE_CORE_SATURATION"],
            "pending_targets": ["xxx"],
            "action_required": True
        }
    ],
    
    # ===== 中间指标（供 Composite 综合判断） =====
    "metrics": {
        # 工具特定的中间指标
    }
}
```

---

## 4. 具体 Analyzer 设计

### 4.1 CommTopAnalyzer（最复杂，Week 2 重点）

```python
# analysis/comm_top.py

from typing import Dict, List
from .base import BaseAnalyzer


class CommTopAnalyzer(BaseAnalyzer):
    """
    CommTop 分析器 - 进程组 CPU 分析（增强版）
    
    新增指标:
    - CV (变异系数): 检测负载不均衡
    - Monopoly (独占率): 识别单进程瓶颈
    - SpawnRate (产生速率): 检测进程风暴
    - Impact Score (危害指数): 综合排序依据
    """
    
    # 诊断分级阈值
    CV_THRESHOLD = 1.0              # CV > 1.0 认为不均衡
    MONOPOLY_THRESHOLD = 0.8        # Monopoly > 0.8 认为单点瓶颈
    SPAWN_RATE_THRESHOLD = 10.0     # > 10/s 认为进程风暴
    
    def analyze(self, samples: List[Dict], top_n: int = 10,
                include_metrics: bool = False) -> Dict:
        """
        分析进程组 CPU 利用率
        
        Args:
            samples: 样本数据
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间指标（Composite 使用）
            
        Returns:
            {
                "result": {"groups": [...]},
                "risks": [...],
                "metrics": {"cv_map": ..., "monopoly_map": ...}  # if include_metrics
            }
        """
        # 1. 从 engine 获取数据
        comm_util = self._engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标
        groups = []
        risks = []
        
        for comm, info in comm_util.items():
            # 获取 PID 级分布用于计算 CV 和 Monopoly
            pid_dist = self._engine.get_pid_cpu_distribution(samples, comm)
            cv = self._calculate_cv(pid_dist)
            monopoly = self._calculate_monopoly(pid_dist)
            
            # 获取生命周期信息
            lifecycle = self._engine.get_process_lifecycle(samples, comm)
            spawn_rate = lifecycle.get("spawn_rate", 0)
            
            # 诊断分级
            diagnosis = self._classify(cv, monopoly, spawn_rate)
            
            # 计算危害指数
            impact_score = self._calculate_impact_score(
                info["total_pct"], cv, monopoly, spawn_rate
            )
            
            group = {
                "comm": comm,
                "total_cpu": info["total_pct"],
                "kernel_cpu": info["kernel_pct"],
                "pid_count": info["pid_count"],
                "cv": cv,
                "monopoly": monopoly,
                "spawn_rate": spawn_rate,
                "diagnosis": diagnosis,
                "impact_score": impact_score
            }
            groups.append(group)
            
            # 识别 risk
            risk = self._identify_risk(group)
            if risk:
                risks.append(risk)
        
        # 3. 按危害指数排序
        groups.sort(key=lambda x: x["impact_score"], reverse=True)
        
        # 4. 自动降噪：区分"值得关注"和"背景噪音"
        display_groups, folded_groups = self._auto_filter(groups)
        
        result = {
            "result": {
                "groups": display_groups[:top_n],
                "folded_count": len(folded_groups),
                "total_groups": len(groups)
            },
            "risks": risks
        }
        
        if include_metrics:
            result["metrics"] = {
                "cv_map": {g["comm"]: g["cv"] for g in groups},
                "monopoly_map": {g["comm"]: g["monopoly"] for g in groups},
                "spawn_rate_map": {g["comm"]: g["spawn_rate"] for g in groups},
                "folded_groups": folded_groups
            }
        
        return result
    
    def _calculate_cv(self, pid_dist: Dict[int, float]) -> float:
        """计算变异系数 (Coefficient of Variation)"""
        values = list(pid_dist.values())
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return (variance ** 0.5) / mean
    
    def _calculate_monopoly(self, pid_dist: Dict[int, float]) -> float:
        """计算核心独占率 (Monopoly Ratio)"""
        if not pid_dist:
            return 0.0
        total = sum(pid_dist.values())
        if total == 0:
            return 0.0
        max_pid_cpu = max(pid_dist.values())
        return max_pid_cpu / total
    
    def _classify(self, cv: float, monopoly: float, spawn_rate: float) -> str:
        """诊断分级"""
        if monopoly > self.MONOPOLY_THRESHOLD:
            return "BOTTLENECK"
        elif spawn_rate > self.SPAWN_RATE_THRESHOLD:
            return "STORM"
        elif cv > self.CV_THRESHOLD:
            return "UNBALANCED"
        else:
            return "HEALTHY"
    
    def _calculate_impact_score(self, total_cpu: float, cv: float, 
                                 monopoly: float, spawn_rate: float) -> float:
        """计算危害指数"""
        return (
            total_cpu * 0.3 +
            cv * 40 +
            monopoly * 50 +
            spawn_rate * 5
        )
    
    def _identify_risk(self, group: Dict) -> Optional[Dict]:
        """根据诊断分级识别 risk"""
        if group["diagnosis"] == "BOTTLENECK":
            return self._create_risk(
                level="critical",
                message=f"{group['comm']} 单核饱和 (Monopoly={group['monopoly']:.2f})",
                hint=f"bottleneck-trace --comm {group['comm']}",
                patterns=["SINGLE_CORE_SATURATION"],
                pending_targets=[group["comm"]]
            )
        elif group["diagnosis"] == "STORM":
            return self._create_risk(
                level="warning",
                message=f"{group['comm']} 进程风暴 ({group['spawn_rate']:.1f}/s)",
                hint=f"storm-trace --comm {group['comm']}",
                patterns=["PROCESS_STORM"],
                pending_targets=[group["comm"]]
            )
        elif group["diagnosis"] == "UNBALANCED":
            return self._create_risk(
                level="warning",
                message=f"{group['comm']} 负载不均衡 (CV={group['cv']:.2f})",
                hint=f"get-hotspots --comm {group['comm']}",
                patterns=["UNBALANCED_LOAD"],
                pending_targets=[group["comm"]]
            )
        return None
    
    def _auto_filter(self, groups: List[Dict]) -> tuple:
        """自动降噪，区分值得关注和背景噪音"""
        display = []
        folded = []
        
        for g in groups:
            is_significant = (
                g["total_cpu"] > 5 or
                g["cv"] > 1.0 or
                g["monopoly"] > 0.8 or
                g["spawn_rate"] > 10
            )
            if is_significant:
                display.append(g)
            else:
                folded.append(g)
        
        return display, folded


# ========== CLI 适配层（保持向后兼容） ==========

from ..core.command_decorator import command
from ..core.output_builder import create_risk_info
from ..core.output_models import CommTopOutput, CommGroupItem, CommGroupSummary, TimeRange

@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """[Skill] Get top N comm groups by aggregated CPU utilization"""
    
    # 1. 调用 Analyzer（内部接口，不触发 Trace）
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(
        samples, 
        top_n=getattr(args, 'top_n', 10),
        include_metrics=False
    )
    
    # 2. 记录所有 risks 到 Trace（CLI 层负责）
    for risk in result["risks"]:
        builder.record_risk(
            risk["level"],
            risk["message"],
            risk["hint"]
        )
    
    # 3. 取最高级别 risk 放入 _risk 字段
    top_risk = None
    if result["risks"]:
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top_risk = min(result["risks"], key=lambda r: priority.get(r["level"], 3))
    
    # 4. 转换为 Output 模型
    groups = [
        CommGroupItem.from_stats(
            comm=g["comm"],
            pid_count=g["pid_count"],
            aggregate_cpu=g["total_cpu"],
            kernel_ratio=g["kernel_cpu"] / g["total_cpu"] * 100 if g["total_cpu"] > 0 else 0,
            event_desc=g["diagnosis"]
        )
        for g in result["result"]["groups"]
    ]
    
    risk_output = create_risk_info(**top_risk) if top_risk else create_risk_info(level="none")
    
    output = CommTopOutput(
        _risk=risk_output,
        comm_groups=groups,
        summary=CommGroupSummary(
            total_comm_groups=result["result"]["total_groups"],
            folded_groups=result["result"]["folded_count"]
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].get('ts') if samples else None,
            samples[-1].get('ts') if samples else None
        )
    )
    
    return output
```

### 4.2 其他 Analyzer 概要

#### HotspotsAnalyzer

```python
class HotspotsAnalyzer(BaseAnalyzer):
    """热点函数分析器"""
    
    def analyze(self, samples, comm=None, pid=None, top_n=20) -> Dict:
        symbol_util = self._engine.get_symbol_cpu_util(samples, comm=comm, pid=pid)
        
        hotspots = []
        risks = []
        
        for sym in symbol_util['inclusive'].keys():
            self_pct = symbol_util['self'].get(sym, 0)
            incl_pct = symbol_util['inclusive'][sym]
            
            # 识别内核态热点 risk
            if sym.endswith('_[k]') and incl_pct > 30:
                risks.append(self._create_risk(
                    level="warning",
                    message=f"热点函数 {sym} 内核态占比 {incl_pct:.2f}%",
                    hint=f"find-callers --target {sym}",
                    patterns=["HIGH_KERNEL_HOTSPOT"]
                ))
            
            hotspots.append({
                "symbol": sym,
                "self_pct": self_pct,
                "inclusive_pct": incl_pct
            })
        
        hotspots.sort(key=lambda x: x["self_pct"], reverse=True)
        
        return {
            "result": {"hotspots": hotspots[:top_n]},
            "risks": risks
        }
```

#### CoreDistAnalyzer

```python
class CoreDistAnalyzer(BaseAnalyzer):
    """核心分布分析器"""
    
    def analyze(self, samples) -> Dict:
        core_util = self._engine.get_core_cpu_util(samples)
        
        cores = []
        risks = []
        
        for cpu_id, info in sorted(core_util.items(), key=lambda x: x[1]['total_pct'], reverse=True):
            cores.append({
                "cpu_id": cpu_id,
                "total_cpu": info["total_pct"],
                "kernel_cpu": info["kernel_pct"]
            })
        
        # 检测负载不均衡
        if len(cores) >= 2:
            max_util = cores[0]["total_cpu"]
            min_util = cores[-1]["total_cpu"]
            avg_util = sum(c["total_cpu"] for c in cores) / len(cores)
            
            imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
            
            if imbalance_ratio > 10 and max_util > 50:
                risks.append(self._create_risk(
                    level="critical",
                    message="负载严重不均衡: 单核满载，其他核心空闲",
                    hint="使用 sys-audit 进行系统审计",
                    patterns=["SINGLE_CORE_SATURATION"]
                ))
        
        return {
            "result": {"cores": cores, "imbalance_ratio": imbalance_ratio},
            "risks": risks
        }
```

#### AnomaliesAnalyzer

```python
class AnomaliesAnalyzer(BaseAnalyzer):
    """异常检测分析器"""
    
    def analyze(self, samples, window_size=10, threshold=2.0) -> Dict:
        # 异常检测逻辑
        anomalies = self._detect_anomalies(samples, window_size, threshold)
        
        risks = []
        if anomalies:
            risks.append(self._create_risk(
                level="warning",
                message=f"检测到 {len(anomalies)} 个时序异常",
                hint="查看异常时间点，分析对应时间段",
                patterns=["ANOMALY_DETECTED"]
            ))
        
        return {
            "result": {
                "anomalies": anomalies,
                "mutation_detected": len(anomalies) > 0
            },
            "risks": risks
        }
```

---

## 5. Facade 集成

### 5.1 Facade 调用方式

```python
# analysis/facade.py（由人员A提供框架）

class AnalysisFacade:
    """Analysis Facade - 对外暴露的干净接口"""
    
    def __init__(self, engine: PerfExpertEngine):
        self._engine = engine
        self._analyzers = {}
    
    def _get_analyzer(self, name: str) -> BaseAnalyzer:
        """延迟加载 Analyzer"""
        if name not in self._analyzers:
            if name == "comm_top":
                from .comm_top import CommTopAnalyzer
                self._analyzers[name] = CommTopAnalyzer(self._engine)
            elif name == "hotspots":
                from .hotspots import HotspotsAnalyzer
                self._analyzers[name] = HotspotsAnalyzer(self._engine)
            # ... 其他 analyzer
        return self._analyzers[name]
    
    # ========== 供 Composite 调用的接口 ==========
    
    def analyze_comm_top(self, samples, top_n=10) -> Dict:
        """进程组 CPU 分析（内部接口，不触发 Trace）"""
        analyzer = self._get_analyzer("comm_top")
        return analyzer.analyze(samples, top_n=top_n, include_metrics=True)
    
    def analyze_hotspots(self, samples, comm=None, pid=None, top_n=20) -> Dict:
        """热点函数分析（内部接口）"""
        analyzer = self._get_analyzer("hotspots")
        return analyzer.analyze(samples, comm=comm, pid=pid, top_n=top_n)
    
    def analyze_core_distribution(self, samples) -> Dict:
        """核心分布分析（内部接口）"""
        analyzer = self._get_analyzer("core_dist")
        return analyzer.analyze(samples)
    
    def detect_anomalies(self, samples, window_size=10, threshold=2.0) -> Dict:
        """异常检测（内部接口）"""
        analyzer = self._get_analyzer("anomalies")
        return analyzer.analyze(samples, window_size=window_size, threshold=threshold)
```

---

## 6. 测试策略

### 6.1 单元测试结构

```python
# tests/analysis/test_comm_top.py

import unittest
from unittest.mock import Mock, MagicMock
from scripts.perf_toolkit.analysis.comm_top import CommTopAnalyzer


class TestCommTopAnalyzer(unittest.TestCase):
    """CommTopAnalyzer 单元测试"""
    
    def setUp(self):
        """设置 Mock Engine"""
        self.engine = Mock()
        self.analyzer = CommTopAnalyzer(self.engine)
    
    def test_calculate_cv(self):
        """测试 CV 计算"""
        pid_dist = {1: 10.0, 2: 10.0, 3: 10.0}  # 均匀分布
        cv = self.analyzer._calculate_cv(pid_dist)
        self.assertAlmostEqual(cv, 0.0, places=2)
        
        pid_dist = {1: 30.0, 2: 0.0, 3: 0.0}  # 极度不均衡
        cv = self.analyzer._calculate_cv(pid_dist)
        self.assertGreater(cv, 1.0)
    
    def test_calculate_monopoly(self):
        """测试 Monopoly 计算"""
        pid_dist = {1: 50.0, 2: 30.0, 3: 20.0}
        monopoly = self.analyzer._calculate_monopoly(pid_dist)
        self.assertAlmostEqual(monopoly, 0.5, places=2)
    
    def test_classify_bottleneck(self):
        """测试 BOTTLENECK 诊断"""
        diagnosis = self.analyzer._classify(cv=0.5, monopoly=0.9, spawn_rate=1.0)
        self.assertEqual(diagnosis, "BOTTLENECK")
    
    def test_classify_storm(self):
        """测试 STORM 诊断"""
        diagnosis = self.analyzer._classify(cv=0.5, monopoly=0.5, spawn_rate=15.0)
        self.assertEqual(diagnosis, "STORM")
    
    def test_analyze_with_mock_data(self):
        """使用 Mock 数据测试完整分析流程"""
        # Setup mock
        self.engine.get_comm_cpu_util.return_value = {
            "nginx": {"total_pct": 45.0, "kernel_pct": 10.0, "pid_count": 4}
        }
        self.engine.get_pid_cpu_distribution.return_value = {
            1: 40.0, 2: 3.0, 3: 1.0, 4: 1.0
        }
        self.engine.get_process_lifecycle.return_value = {
            "spawn_rate": 0.1
        }
        
        samples = [{"ts": 1000.0, "comm": "nginx"}]
        
        # Execute
        result = self.analyzer.analyze(samples, top_n=10)
        
        # Assert
        self.assertIn("result", result)
        self.assertIn("risks", result)
        self.assertEqual(len(result["result"]["groups"]), 1)
```

### 6.2 测试覆盖计划

| 测试类型 | 覆盖内容 | 预计工时 |
|----------|----------|----------|
| 单元测试 | 每个 Analyzer 的核心方法 | 8h |
| 集成测试 | Facade 调用链 | 4h |
| Mock 测试 | 使用 Mock Engine 隔离测试 | 4h |
| 向后兼容 | 验证 CLI 行为不变 | 4h |

---

## 7. 交付计划

### 7.1 Week 2 里程碑

| 天数 | 任务 | 交付物 |
|------|------|--------|
| Day 1-2 | CommTopAnalyzer 实现 | comm_top.py（Analyzer + CLI） |
| Day 3 | HotspotsAnalyzer + CoreDistAnalyzer | hotspots.py, core_distribution.py |
| Day 4 | AnomaliesAnalyzer + 其他工具 | anomalies.py, 其他小工具 |
| Day 5 | 单元测试编写 | tests/analysis/ 测试文件 |

### 7.2 Week 3 里程碑

| 天数 | 任务 | 交付物 |
|------|------|--------|
| Day 1-2 | Facade 适配 | 与人员A联调 Facade 接口 |
| Day 3 | 向后兼容验证 | 验证所有 CLI 命令行为不变 |
| Day 4-5 | 问题修复 | 修复测试中发现的问题 |

### 7.3 协作检查点

```
Week 2 每日站会:
- 与人员A对齐 Engine 接口使用
- 反馈接口问题

Week 3 联调:
- Day 1: 与人员A进行 Facade 集成
- Day 3: 与人员C对接，提供 Analyzer 使用培训
- Day 5: 三方联调（A+B+C）
```

---

## 8. 风险与应对

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| Engine 接口延迟 | 中 | 高 | 先使用 Mock 实现 Analyzer 逻辑 |
| CV/Monopoly 计算复杂 | 低 | 中 | 使用标准统计公式，已有示例代码 |
| 向后兼容性问题 | 中 | 高 | Week 3 专门安排兼容测试 |
| 性能问题 | 低 | 中 | Analyzer 纯计算，无 IO，性能应在可接受范围 |

---

## 9. 附录

### 9.1 需要 Core 层提供的接口

```python
# 人员A Week 1 需交付

class PerfExpertEngine:
    # 已有接口（保持兼容）
    def get_comm_cpu_util(self, samples) -> Dict: ...
    def get_core_cpu_util(self, samples) -> Dict: ...
    def get_symbol_cpu_util(self, samples, comm=None, pid=None) -> Dict: ...
    
    # 新增接口（Week 1 交付）
    def get_pid_cpu_distribution(self, samples, comm) -> Dict[int, float]:
        """获取指定 comm 下各 PID 的 CPU 分布"""
        pass
    
    def get_process_lifecycle(self, samples, comm=None) -> Dict:
        """获取进程生命周期信息"""
        pass
```

### 9.2 关键公式参考

**变异系数 (CV)**:
```
CV = σ / μ
其中 σ 是标准差，μ 是均值
```

**核心独占率 (Monopoly)**:
```
Monopoly = max(PID_cpu) / sum(all_PID_cpu)
```

**危害指数 (Impact Score)**:
```
Impact = CPU * 0.3 + CV * 40 + Monopoly * 50 + SpawnRate * 5
```
