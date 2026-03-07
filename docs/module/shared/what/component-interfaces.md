# 组件接口设计规范

本文档定义 perf-hunter 三层架构（Core/Analysis/Composite/CLI）之间的清晰交互接口。

**核心原则：**
- 禁止在层间传递裸 `dict`/`List[Dict]`，除非是真正的动态内容（如用户配置）
- 所有接口必须使用强类型 `dataclass` 或 `Protocol`
- 每层对外暴露的接口必须在单一位置定义

---

## 目录

- [架构概览](#架构概览)
- [Core Layer 接口](#core-layer-接口)
- [Analysis Layer 接口](#analysis-layer-接口)
- [Composite Layer 接口](#composite-layer-接口)
- [CLI Layer 接口](#cli-layer-接口)
- [跨层数据流](#跨层数据流)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│ CLI Layer (命令层)                                               │
│ - 参数解析、命令路由                                              │
│ - Trace 记录触发点                                               │
│ - 输出渲染                                                      │
├─────────────────────────────────────────────────────────────────┤
│ Composite Layer (组合诊断层)                                      │
│ - SysAudit, BottleneckTrace                                     │
│ - 多分析器结果聚合                                                │
│ - Risk 聚合与优先级排序                                           │
├─────────────────────────────────────────────────────────────────┤
│ Analysis Layer (分析层)                                           │
│ - 6个核心分析器实现                                               │
│ - Facade 统一接口                                                │
│ - 与 Engine 交互获取数据                                          │
├─────────────────────────────────────────────────────────────────┤
│ Core Layer (核心层)                                              │
│ - Engine: 数据加载与查询                                          │
│ - Symbol: 符号解析                                                │
│ - Trace: 诊断追踪                                                 │
│ - Output: 输出构建与格式化                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Layer 接口

📘 **详细接口文档**: [interface-core.md](interface-core.md) - 完整的强类型接口定义

### 1. 数据模型 (`core.engine_types`)

Core 层提供统一的数据结构，供上层使用：

#### 样本数据
```python
@dataclass(frozen=True)
class Sample:
    """单个样本 - 不可变数据"""
    comm: str
    pid: str
    cpu: int
    ts: float
    core_per_sec: Optional[float]
    stack: Optional[SymbolStack] = None
```

#### CPU 统计
```python
@dataclass
class CPUUtilization:
    """CPU 利用率统计"""
    total_pct: float
    user_pct: float
    kernel_pct: float
    total_core_seconds: float
    duration: float

@dataclass
class CommCPUInfo:
    """进程组 CPU 信息"""
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    pid_count: int
    pids: Set[str]

@dataclass
class CoreCPUInfo:
    """核心级 CPU 信息"""
    cpu_id: int
    total_pct: float
    kernel_pct: float
    user_pct: float
```

#### 生命周期
```python
@dataclass
class LifecycleEvent:
    """进程生命周期事件"""
    pid: str
    comm: str
    timestamp: float
    type: Literal["spawn", "exit"]

@dataclass
class ProcessLifecycle:
    """进程生命周期信息"""
    spawn_events: List[LifecycleEvent]
    exit_events: List[LifecycleEvent]
    spawn_rate: float
```

#### 调用图
```python
@dataclass
class CallerInfo:
    """调用者信息"""
    symbol: str
    call_count: int
    total_weight: float

@dataclass
class CallGraph:
    """调用图结构"""
    callers: List[CallerInfo]
    call_graph: Dict[str, List[CallEdge]]  # 动态结构，允许 dict
    hot_paths: List[str]
```

### 2. Engine 接口 (`core.engine.PerfExpertEngine`)

```python
class PerfExpertEngine:
    # ========== 数据加载 ==========
    def __init__(self, data_file: str, freq: int = 19) -> None
    
    # ========== 样本过滤 ==========
    def get_filtered_samples(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        cpu_id: Optional[int] = None,
        pid: Optional[int] = None,
        comm: Optional[str] = None,
        comm_regex: Optional[str] = None,
    ) -> List[Sample]  # 返回类型化的 Sample 列表
    
    # ========== CPU 统计 ==========
    def get_total_core_per_sec(self, samples: List[Sample]) -> Tuple[float, float]
    def get_comm_cpu_info(self, samples: List[Sample]) -> List[CommCPUInfo]
    def get_core_cpu_info(self, samples: List[Sample]) -> List[CoreCPUInfo]
    def get_cpu_utilization(self, samples: List[Sample]) -> CPUUtilization
    
    # ========== 生命周期 ==========
    def get_process_lifecycle(
        self, 
        samples: List[Sample],
        comm: Optional[str] = None
    ) -> ProcessLifecycle
    
    # ========== 调用图 ==========
    def get_call_graph(
        self,
        samples: List[Sample],
        target_symbol: Optional[str] = None,
        comm: Optional[str] = None
    ) -> CallGraph
    
    # ========== 样本权重 ==========
    def get_sample_weight(self, sample: Sample) -> float
```

### 3. Output 构建接口 (`core.output_builder`)

```python
@dataclass
class QualityMetrics:
    """数据质量指标"""
    record_count: int
    duration_sec: float
    cpu_utilization_pct: float
    reliability_level: str  # "high" | "medium" | "low"

class OutputBuilder:
    def __init__(self, engine: PerfExpertEngine, args: Namespace) -> None
    
    # 命令生命周期
    def begin_command(self, name: str) -> None
    def complete_command(self) -> None
    
    # 数据质量
    def assess_quality(self, samples: List[Sample]) -> QualityMetrics
    def check_empty_samples(self, samples: List[Sample], **kwargs) -> bool
    
    # 输出渲染（接受具体类型，不接受裸 dict）
    def print_output(self, output: BaseOutput) -> None
```

### 4. Risk 结构 (`core.output_models`)

```python
@dataclass
class RiskInfo:
    """标准化 Risk 信息 - 所有输出的第一个字段"""
    level: Literal["critical", "warning", "info", "none"]
    message: str
    hint: str
    patterns: List[str]               # Attention Steering flags
    pending_targets: List[str]        # 待追踪目标
    action_required: bool = field(init=False)

@dataclass
class TimeRange:
    """时间范围 - ISO 8601 格式"""
    start_time: Optional[str]
    end_time: Optional[str]
    duration: float  # seconds
```

---

## Analysis Layer 接口

### 1. Analysis 数据模型 (`analysis.models`)

#### 内部数据结构（Analyzer 内部使用）
```python
@dataclass
class CommGroup:
    """进程组内部数据"""
    comm: str
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
    pid_count: int
    pids: List[int]
    cv: float                # 变异系数
    monopoly: float          # 核心独占率
    spawn_rate: float        # 产生速率
    diagnosis: str           # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float

@dataclass
class Hotspot:
    """热点函数内部数据"""
    symbol: str
    self_pct: float
    inclusive_pct: float
    is_kernel: bool

@dataclass
class Anomaly:
    """异常点内部数据"""
    type: Literal["SPIKE", "DROP"]
    cpu_id: int
    time_range_start: str
    time_range_end: str
    prev_util: float
    curr_util: float
    next_util: float
    z_score: float

@dataclass
class PathCluster:
    """路径聚类内部数据"""
    cluster_id: str
    path_signature: str
    depth: int
    weight: float
    cpu_util: float
```

#### Analyzer 结果结构（返回给 Facade）
```python
@dataclass
class Risk:
    """Risk 传递结构"""
    level: str
    message: str
    hint: str
    patterns: List[str]
    pending_targets: List[str]

@dataclass
class AnomaliesResult:
    """异常检测结果"""
    anomalies: List[Anomaly]
    mutation_detected: bool
    spike_count: int
    drop_count: int
    risks: List[Risk]

@dataclass
class CommTopResult:
    """进程组分析结果"""
    groups: List[CommGroup]
    folded_count: int
    total_groups: int
    risks: List[Risk]
    metrics: Optional[CommTopMetrics]

@dataclass
class CoreDistributionResult:
    """核心分布分析结果"""
    cores: List[CoreStat]
    imbalance_level: str
    saturated_cores: List[CoreStat]
    total_cores: int
    risks: List[Risk]

@dataclass
class HotspotsResult:
    """热点函数分析结果"""
    hotspots: List[Hotspot]
    kernel_ratio: float
    user_ratio: float
    sort_by: str
    risks: List[Risk]

@dataclass
class PathClustersResult:
    """路径聚类分析结果"""
    clusters: List[PathCluster]
    total_clusters: int
    shown_clusters: int
    total_weight: float
    clustered_weight: float
    risks: List[Risk]

@dataclass
class CallersResult:
    """调用链溯源结果"""
    target: str
    callers: List[CallerAttribution]
    total_weight: float
    risks: List[Risk]
```

### 2. Base Analyzer 接口 (`analysis.base`)

```python
class BaseAnalyzer(ABC):
    """Analysis 层抽象基类"""
    
    def __init__(self, engine: PerfExpertEngine) -> None
    
    @abstractmethod
    def analyze(self, samples: List[Sample], **kwargs) -> AnalysisResult:
        """
        执行分析
        
        Args:
            samples: 类型化的 Sample 列表（由 engine 提供）
            **kwargs: 分析特定参数
            
        Returns:
            具体的结果 dataclass（非裸 dict）
        """
        pass
```

### 3. Facade 接口 (`analysis.facade`)

**Facade 是 Analysis 层对外的唯一入口。**

```python
class AnalysisFacade:
    """Analysis 层门面 - 供 Composite 层调用"""
    
    def __init__(self, engine: PerfExpertEngine) -> None
    
    # ========== 核心分析接口 ==========
    def analyze_comm_top(
        self, 
        samples: List[Sample], 
        top_n: int = 10
    ) -> CommTopResult
    
    def analyze_hotspots(
        self, 
        samples: List[Sample],
        comm: Optional[str] = None,
        pid: Optional[int] = None,
        top_n: int = 20,
        sort_by: str = "self"
    ) -> HotspotsResult
    
    def analyze_core_distribution(
        self, 
        samples: List[Sample],
        top_n: int = 10
    ) -> CoreDistributionResult
    
    def detect_anomalies(
        self, 
        samples: List[Sample],
        window_size: float = 1.0,
        spike_threshold: float = 0.5,
        min_utilization: float = 0.3,
        cpu_id: Optional[int] = None,
        top_n: int = 10
    ) -> AnomaliesResult
    
    def cluster_paths(
        self, 
        samples: List[Sample],
        min_depth: int = 2,
        min_samples: int = 5,
        top_n: int = 10,
        comm: Optional[str] = None,
        pid: Optional[int] = None
    ) -> PathClustersResult
    
    def analyze_callers(
        self, 
        samples: List[Sample],
        target_symbol: str,
        comm: Optional[str] = None,
        min_ratio: float = 0.5,
        top_n: int = 10
    ) -> CallersResult


# Facade 工厂函数
def get_facade(engine: PerfExpertEngine) -> AnalysisFacade
```

---

## Composite Layer 接口

### 1. Composite 数据模型 (`composite.models`)

Composite 层接收 Analysis 层的结果，转换为内部表示：

```python
@dataclass
class ProcessGroup:
    """进程组 - Composite 内部表示"""
    comm: str
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
    pid_count: int
    pids: List[int]
    cv: float
    monopoly: float
    spawn_rate: float
    diagnosis: str
    impact_score: float
    
    @property
    def kernel_ratio(self) -> float: ...

@dataclass
class RiskItem:
    """Risk - Composite 内部表示"""
    level: str
    message: str
    hint: str
    patterns: List[str]
    pending_targets: List[str]
    action_required: bool
    
    @classmethod
    def from_analysis_risk(cls, risk: Risk) -> "RiskItem": ...
```

#### 报告结构
```python
@dataclass
class AnomaliesReport:
    """异常检测报告"""
    anomalies: List[AnomalyItem]
    mutation_detected: bool
    risks: List[RiskItem]

@dataclass
class CommTopReport:
    """CommTop 分析报告"""
    groups: List[ProcessGroup]
    folded_count: int
    total_groups: int
    risks: List[RiskItem]
    metrics: Optional[CommTopMetrics]

@dataclass
class CoreDistributionReport:
    """核心分布报告"""
    core_stats: List[CoreStat]
    saturated_cores: List[int]
    imbalance_level: str
    risks: List[RiskItem]

@dataclass
class HotspotsReport:
    """热点分析报告"""
    hotspots: List[HotspotItem]
    top_symbol: Optional[str]
    total_hotspots: int
    kernel_ratio: float
    user_ratio: float
    risks: List[RiskItem]

@dataclass
class CallersReport:
    """调用链分析报告"""
    target: str
    callers: List[CallerInfo]
    hot_paths: List[str]
    risks: List[RiskItem]
```

#### 诊断报告
```python
@dataclass
class DiagnosisReport:
    """综合诊断报告（sys-audit 输出）"""
    primary_suspect: Optional[ProcessGroup]
    secondary_loads: List[ProcessGroup]
    background_noise: List[ProcessGroup]
    background_count: int
    mutation_detected: bool
    mutation_time: Optional[float]
    saturated_cores: List[int]
    root_cause_analysis: str

@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    found: bool
    comm: str
    total_cpu: float
    kernel_ratio: float
    pid_count: int
    cv: float
    monopoly: float
    diagnosis: str
    impact_score: float
    risks: List[RiskItem]
```

### 2. Risk 聚合接口 (`composite.risk_aggregator`)

```python
class RiskAggregator:
    """Risk 聚合器 - 合并多个分析器的 Risk"""
    
    def __init__(self) -> None
    
    def add_risks(self, risks: List[RiskItem], source: str) -> None
    
    def get_aggregate_risk(self) -> RiskItem:
        """获取聚合后的最高优先级 Risk"""
        
    def get_all_patterns(self) -> List[str]:
        """获取所有检测到的 patterns"""
        
    def get_pending_targets(self) -> List[str]:
        """获取待追踪目标列表"""
```

### 3. Composite 诊断器接口

```python
class SysAuditor:
    """系统审计器"""
    
    def __init__(self, facade: AnalysisFacade) -> None
    
    def audit(
        self, 
        samples: List[Sample],
        top_n: int = 10
    ) -> Tuple[DiagnosisReport, RiskItem]:
        """
        执行系统审计
        
        Returns:
            (诊断报告, 聚合 Risk)
        """

class BottleneckTracer:
    """瓶颈追踪器"""
    
    def __init__(self, facade: AnalysisFacade) -> None
    
    def trace(
        self,
        samples: List[Sample],
        target_comm: Optional[str] = None,
        top_n: int = 10
    ) -> Tuple[BottleneckAnalysis, HotspotsReport, Optional[CallersReport]]:
        """
        执行瓶颈追踪
        
        Returns:
            (瓶颈分析, 热点报告, 调用链报告(可选))
        """
```

---

## CLI Layer 接口

### 1. 命令处理器类型

```python
# 命令处理器函数签名
AnalysisCommandHandler = Callable[
    [OutputBuilder, PerfExpertEngine, Namespace, List[Sample]], 
    BaseOutput
]

CompositeCommandHandler = Callable[
    [OutputBuilder, PerfExpertEngine, Namespace, List[Sample]],
    BaseOutput
]
```

### 2. 命令注册接口

```python
# analysis/commands/__init__.py
def register_commands(subparsers: argparse._SubParsersAction) -> None:
    """注册所有分析命令"""

def get_command_handler(name: str) -> AnalysisCommandHandler:
    """获取命令处理器"""

# composite/commands/__init__.py
def register_commands(subparsers: argparse._SubParsersAction) -> None:
    """注册所有组合命令"""

def get_command_handler(name: str) -> CompositeCommandHandler:
    """获取命令处理器"""
```

### 3. 装饰器接口 (`cli.decorators`)

```python
def command(
    name: str, 
    filters: Optional[List[str]] = None
) -> Callable[[AnalysisCommandHandler], AnalysisCommandHandler]:
    """
    命令装饰器
    
    Args:
        name: 命令名称
        filters: 过滤参数列表，None 表示使用全部 6 个
        
    Returns:
        包装后的命令处理器
    """
```

---

## 跨层数据流

### 1. 正常分析流程

```
CLI Layer
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. 解析参数                              │
│ 2. 创建 Engine                          │
│ 3. 获取过滤后的 Samples (List[Sample])  │
└─────────────────────────────────────────┘
    │
    ▼
Core Layer (Engine)
    │
    ▼
┌─────────────────────────────────────────┐
│ Engine.get_filtered_samples()           │
│ 返回: List[Sample]                      │
└─────────────────────────────────────────┘
    │
    ▼
Analysis Layer (Facade)
    │
    ▼
┌─────────────────────────────────────────┐
│ Facade.analyze_*()                      │
│ 输入: List[Sample]                      │
│ 输出: *Result dataclass                 │
└─────────────────────────────────────────┘
    │
    ▼
Composite Layer (可选)
    │
    ▼
┌─────────────────────────────────────────┐
│ Composite 接收 *Result                  │
│ 转换为内部 *Report 格式                 │
│ 聚合 Risk                               │
└─────────────────────────────────────────┘
    │
    ▼
CLI Layer
    │
    ▼
┌─────────────────────────────────────────┐
│ OutputBuilder.print_output()            │
│ 输入: BaseOutput dataclass              │
│ 输出: JSON/Text                         │
└─────────────────────────────────────────┘
```

### 2. 类型转换边界

| 边界 | 输入 | 输出 | 转换方式 |
|------|------|------|----------|
| Engine → Analysis | raw data | `List[Sample]` | Engine 解析时创建 |
| Analysis → Composite | `*Result` | `*Report` | `from_result()` 类方法 |
| Composite → CLI | `*Report` | `BaseOutput` | OutputBuilder 渲染 |
| CLI → 外部 | `BaseOutput` | JSON/Text | Adapter 转换 |

### 3. 禁止的用法

❌ **禁止在层间传递裸 dict：**

```python
# 错误示例 - BaseAnalyzer
@abstractmethod
def analyze(self, samples: List[Dict], **kwargs) -> Dict:  # ❌ 禁止
    pass

# 正确示例
@abstractmethod  
def analyze(self, samples: List[Sample], **kwargs) -> CommTopResult:  # ✅ 正确
    pass
```

```python
# 错误示例 - Facade 返回
def analyze_comm_top(self, ...) -> Dict:  # ❌ 禁止
    return {"groups": [...], "risks": [...]}

# 正确示例
def analyze_comm_top(self, ...) -> CommTopResult:  # ✅ 正确
    return CommTopResult(groups=..., risks=...)
```

```python
# 错误示例 - Composite 接收
class SysAuditor:
    def audit(self, samples: List[Dict]) -> Dict:  # ❌ 禁止
        ...

# 正确示例
class SysAuditor:
    def audit(self, samples: List[Sample]) -> Tuple[DiagnosisReport, RiskItem]:  # ✅ 正确
        ...
```

---

## 接口版本管理

### 向后兼容策略

1. **字段扩展：** 使用 `field(default=...)` 添加可选字段
2. **废弃字段：** 标记为 deprecated，保留一个版本周期
3. **破坏性变更：** 新文件名 + 版本号（如 `interfaces_v2.py`）

### 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-03 | 初始版本，定义三层架构接口 |

---

## 附录：类型映射表

### Analysis ↔ Composite 类型映射

| Analysis 类型 | Composite 类型 | 转换方法 |
|--------------|----------------|----------|
| `Risk` | `RiskItem` | `RiskItem.from_analysis_risk()` |
| `CommGroup` | `ProcessGroup` | 字段直接映射 |
| `Anomaly` | `AnomalyItem` | 字段直接映射 |
| `Hotspot` | `HotspotItem` | 字段直接映射 |
| `CoreStat` | `CoreStat` | 字段直接映射 |

### Core ↔ Analysis 类型映射

| Core 类型 | Analysis 类型 | 转换方法 |
|-----------|---------------|----------|
| `Sample` | `Sample` | 直接使用 |
| `CommCPUInfo` | `CommGroup` | Analysis 层包装 |
| `CoreCPUInfo` | `CoreStat` | 字段直接映射 |
| `LifecycleEvent` | `SpawnEvent/ExitEvent` | 字段直接映射 |
