# Composite Layer Interface Specification

> Composite Layer（组合诊断层）接口规范
> 
> 职责：编排多个 Analysis 层分析器，聚合结果，生成综合诊断报告

---

## 1. 概述

### 1.1 架构位置

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

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **类型安全** | 使用 dataclass 替代裸 dict，编译期类型检查 |
| **转换显式** | 通过 `from_analysis_xxx()` 类方法显式转换 Analysis 层类型 |
| **风险聚合** | 多分析器风险统一聚合，按 target 去重 |
| **职责分离** | Composite 只负责编排，不直接处理原始数据 |

---

## 2. 内部数据模型

### 2.1 RiskItem - Risk 内部表示

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
    
    def __post_init__(self):
        if not self.action_required:
            self.action_required = self.level in ["critical", "warning"]
    
    @classmethod
    def from_analysis_risk(cls, risk: 'Risk', source: str = "") -> 'RiskItem':
        """
        从 Analysis 层的 Risk 转换
        
        Args:
            risk: Analysis 层的 Risk dataclass
            source: 来源标识，用于追踪 risk 产生位置
            
        Returns:
            RiskItem: Composite 层 Risk 表示
        """
        return cls(
            level=risk.level,
            message=risk.message,
            hint=risk.hint,
            patterns=risk.patterns,
            pending_targets=risk.pending_targets,
            action_required=risk.action_required,
            source=source
        )
    
    def to_dict(self) -> dict:
        """转换为 dict（用于序列化）"""
        return {
            "level": self.level,
            "message": self.message,
            "hint": self.hint,
            "patterns": self.patterns,
            "pending_targets": self.pending_targets,
            "action_required": self.action_required,
            "source": self.source
        }
```

### 2.2 ProcessGroup - 进程组

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
    
    @classmethod
    def from_analysis_comm_group(cls, group: 'CommGroup') -> 'ProcessGroup':
        """
        从 Analysis 层的 CommGroup 转换
        
        Args:
            group: Analysis 层的 CommGroup dataclass
            
        Returns:
            ProcessGroup: Composite 层进程组表示
        """
        return cls(
            comm=group.comm,
            total_cpu=group.total_cpu,
            kernel_cpu=group.kernel_cpu,
            user_cpu=group.user_cpu,
            pid_count=group.pid_count,
            pids=group.pids,
            cv=group.cv,
            monopoly=group.monopoly,
            spawn_rate=group.spawn_rate,
            diagnosis=group.diagnosis,
            impact_score=group.impact_score
        )
```

### 2.3 AnomalyItem - 异常点内部表示

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
    
    @classmethod
    def from_analysis_anomaly(cls, anomaly: 'Anomaly') -> 'AnomalyItem':
        """
        从 Analysis 层的 Anomaly 转换
        
        Args:
            anomaly: Analysis 层的 Anomaly dataclass
            
        Returns:
            AnomalyItem: Composite 层异常点表示
        """
        return cls(
            cpu_id=anomaly.cpu_id,
            timestamp=cls._parse_timestamp(anomaly.time_range_start),
            change_magnitude=abs(anomaly.curr_util - anomaly.prev_util),
            utilization=anomaly.curr_util,
            anomaly_type=anomaly.type,
            z_score=anomaly.z_score
        )
    
    @staticmethod
    def _parse_timestamp(time_str: str) -> float:
        """将 ISO 8601 时间字符串转换为时间戳"""
        from datetime import datetime
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt.timestamp()
```

### 2.4 HotspotItem - 热点函数内部表示

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
    
    @classmethod
    def from_analysis_hotspot(cls, hotspot: 'Hotspot', 
                              tag: str = "COMPUTE") -> 'HotspotItem':
        """
        从 Analysis 层的 Hotspot 转换
        
        Args:
            hotspot: Analysis 层的 Hotspot dataclass
            tag: 资源标签，由 Composite 层根据符号特征推断
            
        Returns:
            HotspotItem: Composite 层热点函数表示
        """
        return cls(
            symbol=hotspot.symbol,
            cpu_percent=hotspot.self_pct,
            inclusive_percent=hotspot.inclusive_pct,
            call_count=getattr(hotspot, 'call_count', 0),
            resource_tag=tag
        )
```

### 2.5 CallerInfo - 调用者信息

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
    
    @classmethod
    def from_analysis_caller(cls, caller: 'CallerAttribution') -> 'CallerInfo':
        """
        从 Analysis 层的 CallerAttribution 转换
        
        Args:
            caller: Analysis 层的 CallerAttribution dataclass
            
        Returns:
            CallerInfo: Composite 层调用者表示
        """
        return cls(
            symbol=caller.symbol,
            call_count=caller.call_count,
            call_ratio=caller.call_ratio,
            total_weight=caller.total_weight
        )
```

---

## 3. 报告结构

### 3.1 DiagnosisReport - 综合诊断报告

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

### 3.2 CommTopReport - CommTop 报告（Composite 版本）

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
    
    @classmethod
    def from_analysis_result(cls, result: 'CommTopResult') -> 'CommTopReport':
        """
        从 Analysis 层的 CommTopResult 转换
        
        Args:
            result: Analysis 层的 CommTopResult dataclass
            
        Returns:
            CommTopReport: Composite 层报告
        """
        groups = [
            ProcessGroup.from_analysis_comm_group(g)
            for g in result.groups
        ]
        
        risks = [
            RiskItem.from_analysis_risk(r, source="comm_top")
            for r in result.risks
        ]
        
        # 转换 metrics（如果存在）
        metrics = None
        if result.metrics:
            metrics = CommTopMetrics(
                cv_map=result.metrics.get("cv_map", {}),
                monopoly_map=result.metrics.get("monopoly_map", {}),
                spawn_rate_map=result.metrics.get("spawn_rate_map", {}),
                impact_score_map=result.metrics.get("impact_score_map", {}),
                folded_groups=[
                    ProcessGroup(comm=g.get("comm", ""), diagnosis=g.get("diagnosis", "HEALTHY"))
                    for g in result.metrics.get("folded_groups", [])
                ],
                all_groups=groups  # 简化处理，实际需要转换所有组
            )
        
        return cls(
            groups=groups,
            folded_count=result.folded_count,
            total_groups=result.total_groups,
            risks=risks,
            metrics=metrics
        )
```

### 3.3 AnomaliesReport - 异常报告（Composite 版本）

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
    
    @classmethod
    def from_analysis_result(cls, result: 'AnomaliesResult') -> 'AnomaliesReport':
        """
        从 Analysis 层的 AnomaliesResult 转换
        
        Args:
            result: Analysis 层的 AnomaliesResult dataclass
            
        Returns:
            AnomaliesReport: Composite 层报告
        """
        anomalies = [
            AnomalyItem.from_analysis_anomaly(a)
            for a in result.anomalies
        ]
        
        risks = [
            RiskItem.from_analysis_risk(r, source="anomalies")
            for r in result.risks
        ]
        
        return cls(
            anomalies=anomalies,
            mutation_detected=result.mutation_detected,
            spike_count=result.spike_count,
            drop_count=result.drop_count,
            risks=risks
        )
```

### 3.4 HotspotsReport - 热点报告（Composite 版本）

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
    
    @classmethod
    def from_analysis_result(cls, result: 'HotspotsResult') -> 'HotspotsReport':
        """
        从 Analysis 层的 HotspotsResult 转换
        
        Args:
            result: Analysis 层的 HotspotsResult dataclass
            
        Returns:
            HotspotsReport: Composite 层报告
        """
        # 推断资源标签
        def infer_tag(symbol: str) -> str:
            symbol_lower = symbol.lower()
            if any(k in symbol_lower for k in ['lock', 'mutex', 'spin', 'rwsem']):
                return "LOCK"
            if any(k in symbol_lower for k in ['syscall', 'sys_']):
                return "SYSCALL"
            if any(k in symbol_lower for k in ['schedule', 'switch']):
                return "SCHED"
            if any(k in symbol_lower for k in ['malloc', 'free', 'reclaim']):
                return "MEMORY"
            if any(k in symbol_lower for k in ['read', 'write', 'send', 'recv']):
                return "IO"
            return "COMPUTE"
        
        hotspots = [
            HotspotItem.from_analysis_hotspot(h, tag=infer_tag(h.symbol))
            for h in result.hotspots
        ]
        
        risks = [
            RiskItem.from_analysis_risk(r, source="hotspots")
            for r in result.risks
        ]
        
        top = result.hotspots[0].symbol if result.hotspots else None
        
        return cls(
            hotspots=hotspots,
            top_symbol=top,
            total_hotspots=len(result.hotspots),
            kernel_ratio=result.kernel_ratio,
            user_ratio=result.user_ratio,
            risks=risks
        )
```

### 3.5 CallersReport - 调用链报告（Composite 版本）

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
    
    @classmethod
    def from_analysis_result(cls, result: 'CallersResult') -> 'CallersReport':
        """
        从 Analysis 层的 CallersResult 转换
        
        Args:
            result: Analysis 层的 CallersResult dataclass
            
        Returns:
            CallersReport: Composite 层报告
        """
        callers = [
            CallerInfo.from_analysis_caller(c)
            for c in result.callers
        ]
        
        risks = [
            RiskItem.from_analysis_risk(r, source="callers")
            for r in result.risks
        ]
        
        # 提取热点路径（前3条）
        hot_paths = [c.symbol for c in callers[:3]]
        
        return cls(
            target=result.target,
            callers=callers,
            hot_paths=hot_paths,
            risks=risks
        )
```

### 3.6 BottleneckAnalysis - 瓶颈分析中间结果

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

### 3.7 EntityDistribution - 实体分布矩阵行

```python
@dataclass
class EntityDistribution:
    """
    实体分布矩阵行
    
    用于 [ENTITY_DISTRIBUTION_MATRIX] 输出区块。
    """
    comm: str                        # 进程组名称
    count: int                       # PID 数量
    incl_saliency: float             # Inclusive CPU 显著度
    excl_saliency: float             # Exclusive (Self) CPU 显著度
    core_affinity: str               # Fixed/Uniform/Scattered
    throttle_rate: float             # 节流比例
```

### 3.8 CallPathCluster - 调用路径聚类

```python
@dataclass
class CallPathCluster:
    """
    调用路径聚类
    
    用于 [CONVERGENCE_TRACE] 输出区块。
    """
    cluster_id: str                  # 聚类标识
    comm: str                        # 所属进程
    weight: float                    # 占总样本比例
    path: List[str]                  # 调用链符号列表
    hotspot: str                     # 汇聚热点符号
    characteristic: str              # 路径特征标签
```

### 3.9 CorrelationFlag - 关联标志

```python
@dataclass
class CorrelationFlag:
    """
    关联标志
    
    用于 [CORRELATION_FLAGS] 输出区块。
    """
    flag_type: str                   # GLOBAL_LOCK_CONTENTION, SINGLE_CORE_SATURATION, etc.
    target: str                      # 目标符号/进程
    message: str                     # 描述信息
    severity: str                    # critical/warning/info
```

### 3.10 BottleneckTraceResult - bottleneck-trace 完整输出

```python
@dataclass
class BottleneckTraceResult:
    """
    bottleneck-trace 完整输出
    
    对应 [ENTITY_DISTRIBUTION_MATRIX], [CONVERGENCE_TRACE], 
    [CORRELATION_FLAGS], [DATA_SUMMARY] 四个输出区块。
    """
    # 风险信息（置顶）
    _risk: RiskItem
    
    # 实体分布矩阵 [ENTITY_DISTRIBUTION_MATRIX]
    entity_distribution: List[EntityDistribution]
    
    # 收敛追踪 [CONVERGENCE_TRACE]
    common_hotspot: str              # 所有聚类共享的热点符号
    common_hotspot_weight: float     # 共同热点占比
    clusters: List[CallPathCluster]  # 调用路径聚类列表
    
    # 关联标志 [CORRELATION_FLAGS]
    correlation_flags: List[CorrelationFlag]
    
    # 数据摘要 [DATA_SUMMARY]
    total_pids: int                  # 采样期间唯一 PID 数
    total_sys_cpu: float             # 系统总 CPU 利用率(%)
    top_bottlenecks: List[str]       # 排名前三的热点符号
    duration_sec: float              # 采样持续时间
    sample_count: int                # 总样本数
    
    # 时间范围
    time_range: TimeRange
```

---

## 4. Risk 聚合器

### 4.1 接口定义

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
        """
        添加单个 risk
        
        Args:
            risk: RiskItem 实例
            source: 来源标识（如 "anomalies", "comm_top"）
        """
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
        """
        批量添加 risks
        
        Args:
            risks: RiskItem 列表
            source: 来源标识
        """
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
        
        Returns:
            AggregatedRisk: 聚合后的 risk 结果
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
    
    def get_all_patterns(self) -> List[str]:
        """
        获取所有检测到的 patterns（SHECR Attention Flags）
        
        Returns:
            List[str]: Pattern 列表，如 ["SINGLE_CORE_SATURATION", "HIGH_KERNEL"]
        """
        patterns = set()
        for risk in self._risks:
            patterns.update(risk.patterns)
        return list(patterns)
    
    def get_pending_targets(self) -> List[str]:
        """
        获取所有待追踪目标
        
        Returns:
            List[str]: 目标列表（通常是进程名或符号名）
        """
        return list(self._target_map.keys())
    
    def clear(self) -> None:
        """清空所有 risks"""
        self._risks = []
        self._target_map = {}
    
    def _level_priority(self, level: str) -> int:
        """获取风险级别优先级（数字越小优先级越高）"""
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        return priority.get(level.lower(), 4)
```

### 4.2 便捷函数

```python
def merge_risk_lists(risk_lists: List[List[RiskItem]], 
                     sources: Optional[List[str]] = None) -> AggregatedRisk:
    """
    便捷函数：合并多个 risk 列表
    
    Args:
        risk_lists: 多个 risk 列表，如 [anomaly_risks, core_dist_risks, comm_top_risks]
        sources: 可选，每个列表的来源标识
        
    Returns:
        AggregatedRisk: 聚合后的 risk
        
    示例：
        aggregated = merge_risk_lists(
            [anomalies_risks, comm_top_risks],
            sources=["anomalies", "comm_top"]
        )
    """
    aggregator = RiskAggregator()
    for i, risks in enumerate(risk_lists):
        source = sources[i] if sources and i < len(sources) else ""
        aggregator.add_risks(risks, source)
    return aggregator.get_aggregate_risk()
```

---

## 5. 诊断器接口

### 5.1 SysAuditor - 系统审计器

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
        anomalies_report = AnomaliesReport.from_analysis_result(anomalies_result)
        comm_top_report = CommTopReport.from_analysis_result(comm_top_result)
        
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
    
    def _synthesize(self, anomalies: AnomaliesReport,
                    core_dist: 'CoreDistributionResult',
                    comm_top: CommTopReport) -> DiagnosisReport:
        """
        综合分析结果，识别真正瓶颈
        
        核心逻辑（解决 A 掩盖 B 问题）：
        1. 识别突变时刻
        2. 分析核心饱和情况
        3. 按危害指数（而非绝对 CPU）排序进程组
        4. 区分 Primary/Secondary/Background
        
        Args:
            anomalies: 异常检测报告
            core_dist: 核心分布结果
            comm_top: 进程组报告
            
        Returns:
            DiagnosisReport: 综合诊断报告
        """
        # 1. 检查突变
        mutation_time = None
        if anomalies.mutation_detected and anomalies.anomalies:
            mutation_time = anomalies.anomalies[0].timestamp
        
        # 2. 获取核心饱和情况
        saturated_cores = [
            c.cpu_id for c in core_dist.cores 
            if c.total_cpu > 80  # 阈值可配置
        ]
        
        # 3. 获取所有进程组（包括被折叠的）
        all_groups = comm_top.metrics.all_groups if comm_top.metrics else comm_top.groups
        
        # 4. 分类：Primary / Secondary / Background
        primary = None
        secondary = []
        background = []
        
        for g in all_groups:
            if g.diagnosis == "BOTTLENECK":
                if primary is None:
                    primary = g
                else:
                    secondary.append(g)
            elif g.total_cpu > 10 or g.diagnosis in ["STORM", "UNBALANCED"]:
                secondary.append(g)
            else:
                background.append(g)
        
        # 5. 构建根因分析
        root_cause = self._build_root_cause(primary, secondary, anomalies, saturated_cores)
        
        return DiagnosisReport(
            primary_suspect=primary,
            secondary_loads=secondary[:3],
            background_noise=background[:5],
            background_count=len(background),
            mutation_detected=anomalies.mutation_detected,
            mutation_time=mutation_time,
            saturated_cores=saturated_cores,
            imbalance_level=core_dist.imbalance_level,
            root_cause_analysis=root_cause,
            recommendations=self._generate_recommendations(primary, secondary)
        )
    
    def _build_root_cause(self, primary: Optional[ProcessGroup],
                         secondary: List[ProcessGroup],
                         anomalies: AnomaliesReport,
                         saturated_cores: List[int]) -> str:
        """构建根因分析描述"""
        parts = []
        
        if primary:
            parts.append(f"主要瓶颈: {primary.comm} ({primary.diagnosis})")
        
        if anomalies.mutation_detected:
            parts.append("检测到性能突变")
        
        if saturated_cores:
            cores_str = ', '.join(map(str, saturated_cores[:3]))
            parts.append(f"核心饱和: CPU {cores_str}")
        
        if secondary:
            comms = ', '.join(s.comm for s in secondary[:2])
            parts.append(f"次要负载: {comms}")
        
        return "; ".join(parts) if parts else "未检测到明显瓶颈"
    
    def _generate_recommendations(self, primary: Optional[ProcessGroup],
                                 secondary: List[ProcessGroup]) -> List[str]:
        """生成建议操作"""
        recommendations = []
        
        if primary:
            recommendations.append(
                f"执行 bottleneck-trace --comm {primary.comm} 深入分析"
            )
        
        for g in secondary:
            if g.diagnosis == "STORM":
                recommendations.append(
                    f"进程 {g.comm} 可能存在进程风暴，建议检查进程生命周期"
                )
        
        return recommendations
```

### 5.2 BottleneckTracer - 瓶颈追踪器

```python
class BottleneckTracer:
    """
    瓶颈追踪器
    
    自动识别 CPU 瓶颈进程并进行深度分析。
    
    分析流程（4 阶段）：
    1. 预处理阶段：get-comm-top + analyze-core-distribution
    2. 热点分析阶段：get-hotspots (sort-by=self)
    3. 调用链分析阶段：find-callers (Bottom-Up) + cluster-paths (Top-Down)
    4. 聚合输出阶段：CONVERGENCE + AFFINITY_PATTERN 判定
    
    使用示例：
        engine = PerfExpertEngine()
        facade = AnalysisFacade(engine)
        tracer = BottleneckTracer(facade)
        
        samples = engine.get_filtered_samples()
        result = tracer.trace(samples, target_comm="my_app")
        
        # 访问结果
        print(result.entity_distribution)
        print(result.common_hotspot)
        print(result.clusters)
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
              target_comm: Optional[str] = None) -> BottleneckTraceResult:
        """
        执行瓶颈追踪
        
        Args:
            samples: 样本数据
            target_comm: 可选，指定目标进程。如为 None，自动识别瓶颈进程
            
        Returns:
            BottleneckTraceResult: 包含 entity_distribution, clusters, 
                                   correlation_flags, data_summary 的完整结果
        """
        # 1. 自动识别或验证目标进程
        if not target_comm:
            target_comm = self._find_bottleneck_comm(samples)
        
        if not target_comm:
            # 未找到瓶颈进程
            return (
                BottleneckAnalysis(
                    found=False,
                    risks=[RiskItem(
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
        hotspots_report = HotspotsReport.from_analysis_result(hotspots_result)
        
        # 4. 调用链溯源（如果热点明确）
        callers_report = None
        if hotspots_report.top_symbol:
            callers_result = self._facade.analyze_callers(
                samples, 
                target_symbol=hotspots_report.top_symbol,
                comm=target_comm
            )
            callers_report = CallersReport.from_analysis_result(callers_result)
        
        # 5. 聚合 risks
        self._aggregator.add_risks(bottleneck.risks, source="bottleneck")
        self._aggregator.add_risks(hotspots_report.risks, source="hotspots")
        if callers_report:
            self._aggregator.add_risks(callers_report.risks, source="callers")
        
        # 6. 更新 bottleneck risks
        bottleneck.risks = list(self._aggregator._risks)
        
        return bottleneck, hotspots_report, callers_report
    
    def _find_bottleneck_comm(self, samples: List[Dict]) -> Optional[str]:
        """
        自动识别瓶颈进程
        
        策略：通过 CommTop 获取按危害指数排序的进程组，
        找出第一个 BOTTLENECK 诊断的进程。
        
        Args:
            samples: 样本数据
            
        Returns:
            Optional[str]: 瓶颈进程名，如未找到返回 None
        """
        comm_top_result = self._facade.analyze_comm_top(
            samples, 
            top_n=20,
            include_metrics=True
        )
        
        # 获取所有组（包括被折叠的）
        if hasattr(comm_top_result, 'metrics') and comm_top_result.metrics:
            all_groups_data = comm_top_result.metrics.get("all_groups", [])
        else:
            all_groups_data = []
        
        # 转换为 ProcessGroup
        all_groups = [
            ProcessGroup(
                comm=g.get("comm", ""),
                total_cpu=g.get("total_cpu", 0.0),
                diagnosis=g.get("diagnosis", "HEALTHY"),
                monopoly=g.get("monopoly", 0.0),
                impact_score=g.get("impact_score", 0.0)
            )
            for g in all_groups_data
        ]
        
        # 按危害指数排序
        all_groups.sort(key=lambda x: x.impact_score, reverse=True)
        
        # 找第一个 BOTTLENECK
        for group in all_groups:
            if group.diagnosis == "BOTTLENECK":
                return group.comm
        
        # 如果没有明确的 BOTTLENECK，返回危害指数最高的
        if all_groups:
            return all_groups[0].comm
        
        return None
    
    def _analyze_bottleneck(self, samples: List[Dict], comm: str) -> BottleneckAnalysis:
        """
        分析指定进程的瓶颈特征
        
        Args:
            samples: 样本数据
            comm: 目标进程名
            
        Returns:
            BottleneckAnalysis: 瓶颈分析结果
        """
        # 获取进程组详细信息
        comm_top_result = self._facade.analyze_comm_top(
            samples, 
            top_n=50,
            include_metrics=True
        )
        
        # 找到目标 comm
        target_group = None
        for g in comm_top_result.groups:
            if g.comm == comm:
                target_group = ProcessGroup.from_analysis_comm_group(g)
                break
        
        if not target_group:
            return BottleneckAnalysis(
                found=False,
                comm=comm,
                risks=[RiskItem(
                    level="warning",
                    message=f"未找到进程 {comm}",
                    hint="执行 get-comm-top 查看可用进程",
                    patterns=["COMM_NOT_FOUND"]
                )]
            )
        
        # 计算内核占比
        kernel_ratio = target_group.kernel_ratio
        
        # 生成 risks
        risks = []
        
        if target_group.monopoly > 0.8:
            risks.append(RiskItem(
                level="critical",
                message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
                hint=f"get-hotspots --comm {comm}",
                patterns=["SINGLE_CORE_SATURATION"],
                pending_targets=[comm]
            ))
        
        if kernel_ratio > 50:
            risks.append(RiskItem(
                level="warning",
                message=f"{comm} 高内核态 ({kernel_ratio:.1f}%)",
                hint=f"cluster-paths --comm {comm}",
                patterns=["HIGH_KERNEL"],
                pending_targets=[comm]
            ))
        
        return BottleneckAnalysis(
            found=True,
            comm=comm,
            total_cpu=target_group.total_cpu,
            kernel_ratio=kernel_ratio,
            pid_count=target_group.pid_count,
            cv=target_group.cv,
            monopoly=target_group.monopoly,
            diagnosis=target_group.diagnosis,
            impact_score=target_group.impact_score,
            risks=risks
        )
```

---

## 6. 类型转换速查表

### 6.1 Analysis → Composite 类型映射

| Analysis 层类型 | Composite 层类型 | 转换方法 |
|----------------|-----------------|----------|
| `Risk` | `RiskItem` | `RiskItem.from_analysis_risk(risk, source)` |
| `CommGroup` | `ProcessGroup` | `ProcessGroup.from_analysis_comm_group(group)` |
| `Anomaly` | `AnomalyItem` | `AnomalyItem.from_analysis_anomaly(anomaly)` |
| `Hotspot` | `HotspotItem` | `HotspotItem.from_analysis_hotspot(hotspot, tag)` |
| `CallerAttribution` | `CallerInfo` | `CallerInfo.from_analysis_caller(caller)` |
| `CommTopResult` | `CommTopReport` | `CommTopReport.from_analysis_result(result)` |
| `AnomaliesResult` | `AnomaliesReport` | `AnomaliesReport.from_analysis_result(result)` |
| `HotspotsResult` | `HotspotsReport` | `HotspotsReport.from_analysis_result(result)` |
| `CallersResult` | `CallersReport` | `CallersReport.from_analysis_result(result)` |

### 6.2 转换示例

```python
from perf_toolkit.analysis.models import CommTopResult, Risk, CommGroup
from perf_toolkit.composite.models import CommTopReport, RiskItem, ProcessGroup

# 假设这是从 Facade 返回的 Analysis 层结果
analysis_result: CommTopResult = facade.analyze_comm_top(samples)

# 1. 转换整个报告
composite_report: CommTopReport = CommTopReport.from_analysis_result(analysis_result)

# 2. 单独转换 Risk
for risk in analysis_result.risks:
    risk_item: RiskItem = RiskItem.from_analysis_risk(risk, source="comm_top")

# 3. 单独转换 CommGroup
for group in analysis_result.groups:
    process_group: ProcessGroup = ProcessGroup.from_analysis_comm_group(group)
```

---

## 7. 完整使用示例

### 7.1 sys-audit 完整流程

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

### 7.2 bottleneck-trace 完整流程

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

## 8. 接口版本

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-03 | 初始版本，定义 Composite 层接口规范 |

---

## 9. 相关文档

- [三层架构设计](design-three-tier-architecture.md) - Core/Analysis/Composite 分层架构
- [输出格式规范](output-format-spec.md) - 统一 JSON 输出标准
- [Analysis 层接口](analysis/facade.py) - AnalysisFacade 实现
