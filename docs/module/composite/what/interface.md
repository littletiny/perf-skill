# Composite Layer Interface Specification

> Composite Layer（组合诊断层）接口规范
> 
> 职责：编排多个 Analysis 层分析器，聚合结果，生成综合诊断报告

---

## 概述

### 架构位置

```
┌─────────────────────────────────────────┐
│  Layer 3: Composite (组合层)             │
│  ┌───────────────────────────────────┐  │
│  │  • SysAuditor                     │  │
│  │  • BottleneckTracer               │  │
│  │  • RiskAggregator                 │  │
│  └───────────────────────────────────┘  │
└──────────────────┬──────────────────────┘
                   │ 调用 Analysis Facade
                   ▼
┌─────────────────────────────────────────┐
│  Layer 2: Analysis (分析层)              │
│  ┌───────────────────────────────────┐  │
│  │  • CommTopResult                  │  │
│  │  • HotspotsResult                 │  │
│  │  • AnomaliesResult                │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 设计原则

| 原则 | 说明 |
|------|------|
| **类型安全** | 使用 dataclass 替代裸 dict，编译期类型检查 |
| **转换显式** | 通过显式字段映射转换 Analysis 层类型 |
| **风险聚合** | 多分析器风险统一聚合，按 target 去重 |
| **职责分离** | Composite 只负责编排，不直接处理原始数据 |

---

## 组合命令列表

### 实际实现的组合命令（2个）

| 命令 | 文件路径 | 编排的分析器 | 输出类型 |
|------|----------|--------------|----------|
| `sys-audit` | `cli/commands/composite/sys_audit.py` | detect-anomalies → analyze-core-distribution → get-comm-top | `SysAuditOutput` |
| `bottleneck-trace` | `cli/commands/composite/bottleneck_trace.py` | get-comm-top → get-hotspots → find-callers | `BottleneckTraceOutput` |

---

## 内部数据模型

### RiskItem - Risk 内部表示

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class RiskItem:
    """
    Composite 层 Risk 内部表示
    
    从 Analysis 层的 Risk 转换而来，添加 Composite 层所需字段。
    """
    level: str                          # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)      # SHECR Attention Flags
    pending_targets: List[str] = field(default_factory=list)  # 待追踪目标
    action_required: bool = False
    source: str = ""                    # 来源分析器（如 "comm_top", "anomalies"）
```

### ProcessGroup - 进程组

```python
@dataclass
class ProcessGroup:
    """
    进程组数据（从 CommGroup 转换）
    
    包含 CV/Monopoly/SpawnRate 等增强指标，用于解决"A掩盖B"问题。
    """
    comm: str
    total_cpu: float = 0.0           # 总 CPU 利用率 (%)
    kernel_cpu: float = 0.0          # 内核态 CPU (%)
    user_cpu: float = 0.0            # 用户态 CPU (%)
    pid_count: int = 0               # 进程数量
    pids: List[int] = field(default_factory=list)
    
    # 增强指标（用于智能排序和降噪）
    cv: float = 0.0                  # 变异系数 (Coefficient of Variation)
    monopoly: float = 0.0            # 核心独占率 (0-1)
    spawn_rate: float = 0.0          # 进程产生速率 (个/秒)
    
    # 诊断结果
    diagnosis: str = "HEALTHY"       # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float = 0.0        # 危害指数（Composite 层计算）
    
    @property
    def kernel_ratio(self) -> float:
        """内核态占比 (%)"""
        return (self.kernel_cpu / self.total_cpu * 100) if self.total_cpu > 0 else 0
```

### AnomalyItem - 异常点内部表示

```python
@dataclass
class AnomalyItem:
    """
    异常点数据（从 Anomaly 转换）
    
    用于时间序列异常检测结果的内部表示。
    """
    cpu_id: int                      # 核心 ID
    timestamp: float                 # 异常发生时间戳
    change_magnitude: float          # 变化幅度 (%)
    utilization: float               # 当前利用率 (%)
    anomaly_type: str = "SPIKE"      # SPIKE | DROP
    z_score: float = 0.0             # 标准差倍数
```

### HotspotItem - 热点函数内部表示

```python
@dataclass
class HotspotItem:
    """
    热点函数数据（从 Hotspot 转换）
    
    用于瓶颈追踪中的热点分析结果。
    """
    symbol: str
    cpu_percent: float               # Self CPU 占比 (%)
    inclusive_percent: float = 0.0   # Inclusive CPU 占比 (%)
    call_count: int = 0              # 调用次数
    
    # 资源标签（用于快速分类）
    resource_tag: str = "COMPUTE"    # LOCK/SYSCALL/SCHED/MEMORY/IO/COMPUTE
```

### CallerInfo - 调用者信息

```python
@dataclass
class CallerInfo:
    """
    调用者信息（从 CallerAttribution 转换）
    
    用于调用链溯源分析。
    """
    symbol: str                      # 调用者符号（或调用链）
    call_count: int = 0              # 调用次数
    call_ratio: float = 0.0          # 调用占比 (%)
    total_weight: float = 0.0        # 总权重
```

---

## 报告结构

### DiagnosisReport - 综合诊断报告

```python
@dataclass
class DiagnosisReport:
    """
    sys-audit 综合诊断报告
    
    整合 anomalies、core_distribution、comm_top 三个分析器的结果，
    解决"A（高Count亮眼数字）掩盖B（真瓶颈）"问题。
    """
    # 分类结果
    primary_suspect: Optional[ProcessGroup] = None      # 主要嫌疑人（真瓶颈）
    secondary_loads: List[ProcessGroup] = field(default_factory=list)  # 次要负载
    background_noise: List[ProcessGroup] = field(default_factory=list) # 背景噪音
    
    # 统计信息
    background_count: int = 0        # 背景噪音组数量
    
    # 系统级异常
    mutation_detected: bool = False  # 是否检测到突变
    mutation_time: Optional[float] = None  # 突变时间戳
    
    # 核心状态
    saturated_cores: List[int] = field(default_factory=list)  # 饱和核心列表
    imbalance_level: str = "NORMAL"  # NORMAL/MODERATE/SEVERE
    
    # 根因分析
    root_cause_analysis: str = ""    # 根因链描述
    
    # 建议操作
    recommendations: List[str] = field(default_factory=list)
    
    # 来源风险（用于生成最终 _risk）
    risks: List[RiskItem] = field(default_factory=list)
```

### CommTopReport - CommTop 报告（Composite 版本）

```python
@dataclass
class CommTopMetrics:
    """CommTop 分析中间指标"""
    cv_map: Dict[str, float] = field(default_factory=dict)           # 变异系数映射
    monopoly_map: Dict[str, float] = field(default_factory=dict)     # 独占率映射
    spawn_rate_map: Dict[str, float] = field(default_factory=dict)   # 产生速率映射
    impact_score_map: Dict[str, float] = field(default_factory=dict) # 危害指数映射
    
    folded_groups: List[ProcessGroup] = field(default_factory=list)  # 被折叠的组
    all_groups: List[ProcessGroup] = field(default_factory=list)     # 所有组（含折叠）


@dataclass
class CommTopReport:
    """
    CommTop 分析报告（Composite 层）
    
    从 Analysis 层的 CommTopResult 转换而来。
    """
    groups: List[ProcessGroup] = field(default_factory=list)  # 关键进程组（已降噪）
    folded_count: int = 0                    # 折叠组数量
    total_groups: int = 0                    # 总组数量
    risks: List[RiskItem] = field(default_factory=list)
    metrics: Optional[CommTopMetrics] = None  # 中间指标（可选）
```

### AnomaliesReport - 异常报告（Composite 版本）

```python
@dataclass
class AnomaliesReport:
    """
    异常检测报告（Composite 层）
    
    从 Analysis 层的 AnomaliesResult 转换而来。
    """
    anomalies: List[AnomalyItem] = field(default_factory=list)
    mutation_detected: bool = False
    spike_count: int = 0
    drop_count: int = 0
    risks: List[RiskItem] = field(default_factory=list)
```

### HotspotsReport - 热点报告（Composite 版本）

```python
@dataclass
class HotspotsReport:
    """
    热点函数分析报告（Composite 层）
    
    从 Analysis 层的 HotspotsResult 转换而来。
    """
    hotspots: List[HotspotItem] = field(default_factory=list)
    top_symbol: Optional[str] = None      # 排名第一的热点符号
    total_hotspots: int = 0
    kernel_ratio: float = 0.0            # 内核态占比
    user_ratio: float = 0.0              # 用户态占比
    risks: List[RiskItem] = field(default_factory=list)
```

### CallersReport - 调用链报告（Composite 版本）

```python
@dataclass
class CallersReport:
    """
    调用链溯源报告（Composite 层）
    
    从 Analysis 层的 CallersResult 转换而来。
    """
    target: str = ""                      # 目标符号
    callers: List[CallerInfo] = field(default_factory=list)
    hot_paths: List[str] = field(default_factory=list)  # 热点调用路径
    risks: List[RiskItem] = field(default_factory=list)
```

### BottleneckAnalysis - 瓶颈分析中间结果

```python
@dataclass
class BottleneckAnalysis:
    """
    瓶颈深度分析中间结果
    
    用于内部分析的中间数据结构，非最终输出。
    """
    found: bool = False              # 是否发现瓶颈
    comm: str = ""                   # 瓶颈进程名
    
    # CPU 特征
    total_cpu: float = 0.0           # 总 CPU 利用率
    kernel_ratio: float = 0.0        # 内核态占比
    
    # 进程特征
    pid_count: int = 0               # PID 数量
    cv: float = 0.0                  # 变异系数
    monopoly: float = 0.0            # 核心独占率
    
    # 诊断结果
    diagnosis: str = "NORMAL"        # NORMAL/BOTTLENECK/STORM/UNBALANCED
    impact_score: float = 0.0        # 危害指数
    
    # 风险信息
    risks: List[RiskItem] = field(default_factory=list)
```

---

## CLI 输出模型（V2 强类型）

### SysAuditOutput - sys-audit 输出

```python
@dataclass
class SysAuditOutput:
    """
    sys-audit 输出结构 - V2 强类型版本
    
    字段：
    - _risk: RiskInfo                          # 风险信息（置顶）
    - system_fingerprint: SystemFingerprint    # 系统指纹
    - contention_matrix: List[ContentionItem]   # 竞争矩阵
    - process_hierarchy: ProcessHierarchy       # 进程分层
    - core_distribution: CoreDistributionData   # 核心分布
    - anomaly_summary: AnomalySummaryOutput     # 异常摘要
    - expert_anchors: List[ExpertAnchor]        # 专家锚点
    - root_cause_chain: Optional[RootCauseChain] # 根因链
    - recommendations: List[str]                # 建议操作
    - top_by_total_cpu: List[CommTopItem]       # 按 Total CPU 排序
    - top_by_sys_cpu: List[CommTopItem]         # 按 Sys CPU 排序
    - sensitive_events: List[Dict[str, Any]]    # 敏感事件
    - time_range: Optional[TimeRange]           # 时间范围
    """
    _risk: RiskInfo
    system_fingerprint: SystemFingerprint = field(default_factory=SystemFingerprint)
    contention_matrix: List[ContentionItem] = field(default_factory=list)
    process_hierarchy: ProcessHierarchy = field(default_factory=ProcessHierarchy)
    core_distribution: CoreDistributionData = field(default_factory=CoreDistributionData)
    anomaly_summary: AnomalySummaryOutput = field(default_factory=AnomalySummaryOutput)
    expert_anchors: List[ExpertAnchor] = field(default_factory=list)
    root_cause_chain: Optional[RootCauseChain] = None
    recommendations: List[str] = field(default_factory=list)
    top_by_total_cpu: List[CommTopItem] = field(default_factory=list)
    top_by_sys_cpu: List[CommTopItem] = field(default_factory=list)
    sensitive_events: List[Dict[str, Any]] = field(default_factory=list)
    time_range: Optional[TimeRange] = None
```

### BottleneckTraceOutput - bottleneck-trace 输出

```python
@dataclass
class BottleneckTraceOutput:
    """
    bottleneck-trace 输出结构 - V2 强类型版本
    
    字段：
    - _risk: RiskInfo                    # 风险信息（置顶）
    - target_comm: str                   # 目标进程名
    - bottleneck_profile: BottleneckProfile  # 瓶颈特征
    - hotspots: HotspotsOutputData       # 热点数据
    - call_chain: Optional[CallChainAnalysis]  # 调用链分析
    - root_cause: Optional[RootCauseAnalysis]  # 根因分析
    - recommendations: List[str]         # 建议操作
    - time_range: Optional[TimeRange]    # 时间范围
    """
    _risk: RiskInfo
    target_comm: str = ""
    bottleneck_profile: BottleneckProfile = field(default_factory=BottleneckProfile)
    hotspots: HotspotsOutputData = field(default_factory=HotspotsOutputData)
    call_chain: Optional[CallChainAnalysis] = None
    root_cause: Optional[RootCauseAnalysis] = None
    recommendations: List[str] = field(default_factory=list)
    time_range: Optional[TimeRange] = None
```

---

## Risk 聚合器

### 接口定义

```python
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

@dataclass
class AggregatedRisk:
    """聚合后的 Risk 结构"""
    level: str                       # 最高风险级别
    message: str = ""                # 综合消息
    hint: str = ""                   # 合并的建议
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False
    
    # 统计信息
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # 详细分解
    target_details: List['TargetDetail'] = field(default_factory=list)


@dataclass
class TargetDetail:
    """目标详情"""
    target: str
    level: str
    message: str
    hint: str


class RiskAggregator:
    """
    Risk 聚合器
    
    职责：
    1. 收集多个 Analysis 的 risk
    2. 按 target 去重：同一目标的多个 risk，取最高级别
    3. 分级展示：Primary Risk / Secondary Risk / Info
    4. 生成综合的 _risk 输出
    
    使用示例：
        aggregator = RiskAggregator()
        
        # 添加来自不同分析的 risk
        for risk in anomalies_report.risks:
            aggregator.add_risk(risk, source="anomalies")
        
        for risk in comm_top_report.risks:
            aggregator.add_risk(risk, source="comm_top")
        
        # 获取聚合结果
        aggregated = aggregator.get_aggregate_risk()
    """
    
    def __init__(self):
        self._risks: List[RiskItem] = []
        self._target_map: Dict[str, RiskItem] = {}  # target -> 最高级别 risk
    
    def add_risk(self, risk: RiskItem, source: str = "") -> None:
        """添加单个 risk"""
        if not risk or not isinstance(risk, RiskItem):
            return
        
        risk.source = source or risk.source
        self._risks.append(risk)
        
        # 按 target 去重，保留最高级别
        targets = risk.pending_targets if risk.pending_targets else [risk.message]
        
        for target in targets:
            if target not in self._target_map:
                self._target_map[target] = risk
            else:
                # 比较级别，保留更高的
                current = self._target_map[target]
                if self._level_priority(risk.level) < self._level_priority(current.level):
                    self._target_map[target] = risk
    
    def add_risks(self, risks: List[RiskItem], source: str = "") -> None:
        """批量添加 risks"""
        for risk in risks:
            self.add_risk(risk, source)
    
    def get_aggregate_risk(self) -> AggregatedRisk:
        """
        获取聚合后的 Risk
        
        策略：
        1. 按 target 去重，取最高级别
        2. 分级统计 critical/warning/info 数量
        3. 合并 hint，去重
        4. 生成综合 message
        """
        if not self._target_map:
            return AggregatedRisk(level="none", message="未发现明显风险")
        
        # 分类统计
        critical_targets: List[Tuple[str, RiskItem]] = []
        warning_targets: List[Tuple[str, RiskItem]] = []
        info_targets: List[Tuple[str, RiskItem]] = []
        all_patterns: Set[str] = set()
        
        for target, risk in self._target_map.items():
            all_patterns.update(risk.patterns)
            
            if risk.level == "critical":
                critical_targets.append((target, risk))
            elif risk.level == "warning":
                warning_targets.append((target, risk))
            else:
                info_targets.append((target, risk))
        
        # 构建 target_details
        target_details = []
        for target, risk in critical_targets + warning_targets + info_targets:
            target_details.append(TargetDetail(
                target=target,
                level=risk.level,
                message=risk.message,
                hint=risk.hint
            ))
        
        # 生成综合 risk
        if critical_targets:
            targets_str = ", ".join([t[0] for t in critical_targets[:3]])
            if len(critical_targets) > 3:
                targets_str += f" 等{len(critical_targets)}个"
            
            hints = list(dict.fromkeys([r.hint for _, r in critical_targets if r.hint]))
            
            return AggregatedRisk(
                level="critical",
                message=f"发现 {len(critical_targets)} 个关键性能瓶颈: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(self._target_map.keys()),
                action_required=True,
                critical_count=len(critical_targets),
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=target_details
            )
        
        elif warning_targets:
            targets_str = ", ".join([t[0] for t in warning_targets[:3]])
            if len(warning_targets) > 3:
                targets_str += f" 等{len(warning_targets)}个"
            
            hints = list(dict.fromkeys([r.hint for _, r in warning_targets if r.hint]))
            
            return AggregatedRisk(
                level="warning",
                message=f"发现 {len(warning_targets)} 个潜在风险: {targets_str}",
                hint="; ".join(hints) if hints else "",
                patterns=list(all_patterns),
                pending_targets=list(self._target_map.keys()),
                action_required=True,
                critical_count=0,
                warning_count=len(warning_targets),
                info_count=len(info_targets),
                target_details=target_details
            )
        
        elif info_targets:
            return AggregatedRisk(
                level="info",
                message=f"发现 {len(info_targets)} 个提示信息",
                hint="",
                patterns=list(all_patterns),
                pending_targets=[],
                action_required=False,
                critical_count=0,
                warning_count=0,
                info_count=len(info_targets),
                target_details=target_details
            )
        
        return AggregatedRisk(level="none", message="未发现明显风险")
    
    def _level_priority(self, level: str) -> int:
        """获取风险级别优先级（数字越小优先级越高）"""
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        return priority.get(level.lower(), 4)
```

---

## 诊断器接口

### SysAuditor - 系统审计器

```python
from typing import List, Dict, Optional, Tuple

class SysAuditor:
    """
    系统审计器
    
    编排多个 Analysis 层分析器，生成综合诊断报告。
    
    分析流程：
    1. detect-anomalies → 发现突变时刻
    2. analyze-core-distribution → 分析核心分布
    3. analyze-comm-top → 分析进程组（含 CV/Monopoly/SpawnRate）
    4. 综合分析，区分 Primary/Secondary/Background
    
    使用示例：
        engine = PerfExpertEngine()
        facade = AnalysisFacade(engine)
        auditor = SysAuditor(facade)
        
        samples = engine.get_filtered_samples()
        report, aggregated_risk = auditor.audit(samples)
    """
    
    def __init__(self, facade: 'AnalysisFacade'):
        """
        初始化审计器
        
        Args:
            facade: AnalysisFacade 实例
        """
        self._facade = facade
        self._aggregator = RiskAggregator()
    
    def audit(self, samples: List[Dict], 
              top_n: int = 10) -> Tuple[DiagnosisReport, AggregatedRisk]:
        """
        执行系统审计
        
        Args:
            samples: 样本数据（由 core.engine 提供）
            top_n: 返回前 N 个进程组
            
        Returns:
            Tuple[DiagnosisReport, AggregatedRisk]: 诊断报告和聚合风险
        """
        # 1. 执行各维度分析
        anomalies_result = self._facade.detect_anomalies(samples)
        core_dist_result = self._facade.analyze_core_distribution(samples)
        comm_top_result = self._facade.analyze_comm_top(samples, top_n=top_n)
        
        # 2. 转换为 Composite 层类型
        anomalies_report = _convert_anomalies_result(anomalies_result)
        comm_top_report = _convert_comm_top_result(comm_top_result)
        
        # 3. 聚合 risks
        self._aggregator.add_risks(anomalies_report.risks, source="anomalies")
        self._aggregator.add_risks(core_dist_result.risks, source="core_dist")
        self._aggregator.add_risks(comm_top_report.risks, source="comm_top")
        
        # 4. 综合分析结果
        diagnosis = self._synthesize(
            anomalies_report, 
            core_dist_result, 
            comm_top_report
        )
        diagnosis.risks = list(self._aggregator._risks)
        
        # 5. 返回结果
        aggregated_risk = self._aggregator.get_aggregate_risk()
        return diagnosis, aggregated_risk
```

### BottleneckTracer - 瓶颈追踪器

```python
class BottleneckTracer:
    """
    瓶颈追踪器
    
    自动识别 CPU 瓶颈进程并进行深度分析。
    
    分析流程（3 阶段）：
    1. 识别瓶颈进程：get-comm-top
    2. 热点分析阶段：get-hotspots
    3. 调用链分析阶段：find-callers
    
    使用示例：
        engine = PerfExpertEngine()
        facade = AnalysisFacade(engine)
        tracer = BottleneckTracer(facade)
        
        samples = engine.get_filtered_samples()
        analysis, hotspots, callers = tracer.trace(samples, target_comm="my_app")
        
        # 访问结果
        if analysis.found:
            print(f"发现瓶颈: {analysis.comm}")
            print(f"  CPU: {analysis.total_cpu:.1f}%")
            print(f"  Monopoly: {analysis.monopoly:.2f}")
            
            print("\n热点函数:")
            for h in hotspots.hotspots[:5]:
                print(f"  {h.symbol}: {h.cpu_percent:.1f}% [{h.resource_tag}]")
            
            if callers:
                print("\n调用链:")
                for c in callers.callers[:3]:
                    print(f"  {c.symbol}: {c.call_ratio:.1f}%")
    """
    
    def __init__(self, facade: 'AnalysisFacade'):
        """
        初始化追踪器
        
        Args:
            facade: AnalysisFacade 实例
        """
        self._facade = facade
        self._aggregator = RiskAggregator()
    
    def trace(self, samples: List[Dict],
              target_comm: Optional[str] = None) -> Tuple[BottleneckAnalysis, 
                                                         HotspotsReport,
                                                         Optional[CallersReport]]:
        """
        执行瓶颈追踪
        
        Args:
            samples: 样本数据
            target_comm: 可选，指定目标进程。如为 None，自动识别瓶颈进程
            
        Returns:
            Tuple[BottleneckAnalysis, HotspotsReport, Optional[CallersReport]]:
                瓶颈分析结果、热点报告、调用链报告（可选）
        """
        # 1. 自动识别或验证目标进程
        if not target_comm:
            target_comm = self._find_bottleneck_comm(samples)
        
        if not target_comm:
            # 未找到瓶颈进程
            return (
                BottleneckAnalysis(
                    found=False,
                    risks=[RiskInfo(
                        level="info",
                        message="未检测到明显瓶颈进程",
                        hint="尝试使用 sys-audit 进行全景扫描"
                    )]
                ),
                HotspotsReport(),
                None
            )
        
        # 2. 分析瓶颈特征
        bottleneck = self._analyze_bottleneck(samples, target_comm)
        
        # 3. 热点函数分析
        hotspots_result = self._facade.analyze_hotspots(samples, comm=target_comm)
        hotspots_report = _convert_hotspots_result(hotspots_result)

        # 4. 调用链溯源（如果热点明确）
        callers_report = None
        if hotspots_report.top_symbol:
            callers_result = self._facade.analyze_callers(
                samples,
                target_symbol=hotspots_report.top_symbol,
                comm=target_comm
            )
            callers_report = _convert_callers_result(callers_result)
        
        # 5. 聚合 risks
        self._aggregator.add_risks(bottleneck.risks, source="bottleneck")
        self._aggregator.add_risks(hotspots_report.risks, source="hotspots")
        if callers_report:
            self._aggregator.add_risks(callers_report.risks, source="callers")
        
        # 6. 更新 bottleneck risks
        bottleneck.risks = list(self._aggregator._risks)
        
        return bottleneck, hotspots_report, callers_report
```

---

## 完整使用示例

### sys-audit 完整流程

```python
from perf_toolkit.core.engine import PerfExpertEngine
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.sys_audit import SysAuditor
from perf_toolkit.core.output_builder import OutputBuilder

# 1. 初始化
data_file = "perf.data"
engine = PerfExpertEngine()
engine.load_data(data_file)

# 2. 创建 Facade
facade = AnalysisFacade(engine)

# 3. 创建 Auditor
auditor = SysAuditor(facade)

# 4. 执行审计
samples = engine.get_filtered_samples()
diagnosis, aggregated_risk = auditor.audit(samples, top_n=10)

# 5. 构建输出
builder = OutputBuilder(engine)
output = builder.build_sys_audit_output(diagnosis, aggregated_risk)

# 6. 打印结果
print(builder.format_output(output))
```

### bottleneck-trace 完整流程

```python
from perf_toolkit.core.engine import PerfExpertEngine
from perf_toolkit.analysis.facade import AnalysisFacade
from perf_toolkit.composite.bottleneck_trace import BottleneckTracer

# 1. 初始化
engine = PerfExpertEngine()
engine.load_data("perf.data")
facade = AnalysisFacade(engine)

# 2. 创建 Tracer
tracer = BottleneckTracer(facade)

# 3. 执行追踪（自动识别瓶颈）
samples = engine.get_filtered_samples()
analysis, hotspots, callers = tracer.trace(samples)

# 4. 处理结果
if analysis.found:
    print(f"发现瓶颈: {analysis.comm}")
    print(f"  CPU: {analysis.total_cpu:.1f}%")
    print(f"  Monopoly: {analysis.monopoly:.2f}")
    print(f"  诊断: {analysis.diagnosis}")
    
    print("\n热点函数:")
    for h in hotspots.hotspots[:5]:
        print(f"  {h.symbol}: {h.cpu_percent:.1f}% [{h.resource_tag}]")
    
    if callers:
        print("\n调用链:")
        for c in callers.callers[:3]:
            print(f"  {c.symbol}: {c.call_ratio:.1f}%")
else:
    print("未检测到明显瓶颈")
```

---

## 接口版本

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-03 | 初始版本，定义 Composite 层接口规范 |
| 1.1 | 2026-03-04 | 移除 storm-trace，更新为实际实现的2个组合命令 |

---

## 相关文档

- [三层架构设计](design-three-tier-architecture.md) - Core/Analysis/Composite 分层架构
- [输出格式规范](output-format-spec.md) - 统一 JSON 输出标准
- [Analysis 层接口](interface-analysis.md) - AnalysisFacade 接口规范
