# Analysis Layer Interface Specification

> 版本: 1.0.0  
> 更新日期: 2026-03-03  
> 设计目标: 定义 Core 层与 Composite 层之间的强类型接口

---

## 1. 概述

Analysis Layer 是 perf-hunter 三层架构的中间层，作为 Core 层（数据）和 Composite 层（编排）之间的桥梁。

### 1.1 架构位置

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Composite (组合层)                                  │
│  - sys_audit.py, bottleneck_analyze.py                      │
│  - 通过 AnalysisFacade 调用下层                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ 调用 AnalysisFacade（本文档定义）
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Analysis (分析层) ← 本文档定义                       │
│  - facade.py        (AnalysisFacade)                        │
│  - base.py          (BaseAnalyzer)                          │
│  - models.py        (Result Dataclasses)                    │
│  - comm_top.py      (CommTopAnalyzer)                       │
│  - hotspots.py      (HotspotsAnalyzer)                      │
│  - ...                                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ 调用 Core Engine
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Core (核心层)                                       │
│  - engine.py        (PerfExpertEngine)                      │
│  - engine_types.py  (Sample 等数据类型)                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **强类型** | 所有接口使用 dataclass，禁止返回裸 dict |
| **输入统一** | 所有分析器接收 `List[Sample]` 作为输入 |
| **职责分离** | Analysis 层只负责分析逻辑，不处理 Trace |
| **延迟加载** | Facade 按需初始化 Analyzer 实例 |
| **错误封装** | 下层异常转换为有意义的错误信息 |

---

## 2. 数据类型定义

### 2.1 Core 层输入类型

```python
# From: scripts/perf_toolkit/core/engine_types.py

@dataclass
class Sample:
    """
    单个样本数据 - Analysis 层的统一输入类型
    
    由 Core 层的 PerfExpertEngine 解析生成，
    所有 Analyzer 的 analyze() 方法接收 List[Sample] 作为输入。
    """
    comm: str                    # 进程名
    pid: str                     # 进程 ID
    cpu: int                     # CPU 核心号
    ts: float                    # 时间戳（秒）
    core_per_sec: Optional[float]  # 每秒核心数
    stack: Optional[Any] = None    # SymbolStack 对象（调用栈）
```

### 2.2 Risk 数据类型

```python
# From: scripts/perf_toolkit/analysis/models.py

@dataclass
class Risk:
    """
    风险数据结构 - 所有分析结果的标准字段
    
    用于在 Analyzer 之间传递风险信息，供 Composite 层聚合。
    每个 Result dataclass 都包含 risks: List[Risk] 字段。
    """
    level: str                          # "critical" | "warning" | "info" | "none"
    message: str = ""                   # 风险描述
    hint: str = ""                      # 建议操作
    patterns: List[str] = field(default_factory=list)  # 检测到的模式标签
    pending_targets: List[str] = field(default_factory=list)  # 待处理目标列表
    action_required: bool = field(init=False)  # 是否需要立即处理
    
    def __post_init__(self):
        self.action_required = self.level in ["critical", "warning"]
```

---

## 3. 分析器结果类型

### 3.1 AnomaliesResult - 异常检测结果

```python
@dataclass
class Anomaly:
    """单个异常事件"""
    type: str                           # "SPIKE" | "DROP"
    cpu_id: int                         # 发生异常的 CPU
    time_range_start: str               # ISO 8601 格式
    time_range_end: str                 # ISO 8601 格式
    prev_util: float                    # 变化前利用率
    curr_util: float                    # 当前利用率
    next_util: float                    # 变化后利用率
    z_score: float                      # Z-score 统计值
    
    @property
    def change_magnitude(self) -> float:
        """变化幅度（用于排序）"""
        return abs(self.curr_util - self.prev_util)


@dataclass
class AnomaliesResult:
    """
    异常检测结果
    
    由 AnomaliesAnalyzer.analyze() 返回，
    包含时序异常检测的所有发现。
    """
    anomalies: List[Anomaly]            # 异常事件列表
    mutation_detected: bool             # 是否检测到突变
    spike_count: int                    # 上升突变数量
    drop_count: int                     # 下降突变数量
    risks: List[Risk] = field(default_factory=list)
```

### 3.2 CommTopResult - 进程组分析结果

```python
@dataclass
class CommGroup:
    """进程组数据结构"""
    comm: str                           # 进程名
    total_cpu: float                    # 总 CPU 利用率(%)
    kernel_cpu: float                   # 内核态 CPU(%)
    user_cpu: float                     # 用户态 CPU(%)
    pid_count: int                      # PID 数量
    pids: List[int] = field(default_factory=list)  # PID 列表
    cv: float = 0.0                     # 变异系数 (Coefficient of Variation)
    monopoly: float = 0.0               # 核心独占率
    spawn_rate: float = 0.0             # 进程产生速率(个/秒)
    diagnosis: str = "HEALTHY"          # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float = 0.0           # 危害指数


@dataclass
class StormGroupDetail:
    """风暴组详情 - StormAnalysisResult 子结构"""
    comm: str
    spawn_rate: float
    pid_count: int
    total_cpu: float
    severity: str
    top_creators: List[dict] = field(default_factory=list)
    short_lived_count: int = 0
    leaked_count: int = 0


@dataclass
class StormAnalysisResult:
    """进程风暴分析结果"""
    storm_groups: List[StormGroupDetail]
    total_storm_comms: int
    max_spawn_rate: float


@dataclass
class CommTopResult:
    """
    进程组分析结果
    
    由 CommTopAnalyzer.analyze() 返回，
    整合原 get-process-top + cluster-comm + count-process-variety 能力。
    """
    groups: List[CommGroup]             # 关键进程组列表（已降噪）
    folded_count: int                   # 被折叠的组数量
    total_groups: int                   # 总组数量
    risks: List[Risk] = field(default_factory=list)
    storm_analysis: Optional[StormAnalysisResult] = None
    metrics: Optional[dict] = None
```

### 3.3 CoreDistributionResult - 核心分布结果

```python
@dataclass
class CoreStat:
    """核心统计数据结构"""
    cpu_id: int                         # 核心 ID
    total_cpu: float                    # 总 CPU 利用率(%)
    kernel_cpu: float                   # 内核态 CPU(%)
    user_cpu: float                     # 用户态 CPU(%)


@dataclass
class CoreDistributionResult:
    """
    核心分布分析结果
    
    由 CoreDistAnalyzer.analyze() 返回，
    整合原 check-cpu-bottleneck + show-cpu-usage 能力。
    """
    cores: List[CoreStat]               # 各核心统计
    imbalance_level: str                # "HIGH" | "MEDIUM" | "LOW"
    saturated_cores: List[CoreStat]     # 饱和核心列表
    total_cores: int                    # 总核心数
    risks: List[Risk] = field(default_factory=list)
```

### 3.4 HotspotsResult - 热点函数结果

```python
@dataclass
class Hotspot:
    """热点函数数据结构"""
    symbol: str                         # 符号名
    self_pct: float                     # Self CPU(%)
    inclusive_pct: float                # Inclusive CPU(%)
    is_kernel: bool = False             # 是否内核符号


@dataclass
class HotspotsResult:
    """
    热点函数分析结果
    
    由 HotspotsAnalyzer.analyze() 返回。
    """
    hotspots: List[Hotspot]             # 热点函数列表
    kernel_ratio: float                 # 内核态占比
    user_ratio: float                   # 用户态占比
    sort_by: str                        # 排序方式
    risks: List[Risk] = field(default_factory=list)
```

### 3.5 PathClustersResult - 路径聚类结果

```python
@dataclass
class PathCluster:
    """路径聚类数据结构"""
    cluster_id: str                     # 聚类 ID
    path_signature: str                 # 路径签名
    depth: int                          # 调用深度
    weight: float                       # 权重
    cpu_util: float = 0.0               # CPU 贡献(%)


@dataclass
class PathClustersResult:
    """
    路径聚类分析结果
    
    由 PathClustersAnalyzer.analyze() 返回，
    整合原 cluster-symbols 能力。
    """
    clusters: List[PathCluster]         # 聚类列表
    total_clusters: int                 # 总聚类数
    shown_clusters: int                 # 显示的聚类数
    total_weight: float                 # 总权重
    clustered_weight: float             # 已聚类权重
    risks: List[Risk] = field(default_factory=list)
```

### 3.6 CallersResult - 调用链溯源结果

```python
@dataclass
class CallerAttribution:
    """调用归因详情"""
    symbol: str                         # 调用者符号（可能是调用链）
    call_count: int                     # 调用次数
    call_ratio: float                   # 调用占比(%)
    total_weight: float                 # 总权重


@dataclass
class CallersResult:
    """
    调用链溯源结果
    
    由 AnalysisFacade.analyze_callers() 返回，
    用于热点函数溯源分析。
    """
    target: str                         # 目标符号名
    callers: List[CallerAttribution]    # 调用者列表
    total_weight: float                 # 目标符号总权重
    risks: List[Risk] = field(default_factory=list)
```

---

## 4. 抽象基类定义

### 4.1 BaseAnalyzer

```python
# From: scripts/perf_toolkit/analysis/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import Risk, AnalysisResult


class BaseAnalyzer(ABC):
    """
    Analysis 层抽象基类
    
    所有具体 Analyzer 必须继承此类，实现 analyze() 方法。
    
    设计约束:
    1. 只依赖 engine 接口获取数据，不直接访问原始数据文件
    2. 不直接操作 trace（trace 由 CLI 层处理）
    3. 返回具体 Result dataclass，禁止返回裸 dict
    """
    
    def __init__(self, engine):
        """
        Args:
            engine: PerfExpertEngine 实例
        """
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Dict], **kwargs) -> Any:
        """
        执行分析
        
        Args:
            samples: 样本数据列表（Sample 对象列表）
            **kwargs: 分析特定参数
            
        Returns:
            具体 Result dataclass，如 AnomaliesResult, CommTopResult 等
        """
        pass
    
    def _create_risk(self, level: str, message: str, hint: str = "",
                     patterns: List[str] = None, 
                     pending_targets: List[str] = None) -> Risk:
        """
        创建标准化的 Risk 对象
        
        Args:
            level: 风险级别 - critical | warning | info | none
            message: 风险描述
            hint: 建议操作
            patterns: 检测到的模式标签（用于 Attention Steering）
            pending_targets: 待处理目标列表
            
        Returns:
            Risk 对象
        """
        return Risk(
            level=level,
            message=message,
            hint=hint,
            patterns=patterns or [],
            pending_targets=pending_targets or []
        )
```

### 4.2 具体 Analyzer 实现示例

```python
# From: scripts/perf_toolkit/analysis/comm_top.py

class CommTopAnalyzer(BaseAnalyzer):
    """
    进程组分析器
    
    整合能力:
    - 纵向聚合: 按进程名分组（原 cluster-comm）
    - 横向离群: CV 方差分析识别异常 PID（原 get-process-top）
    - 时间动态: Spawn Rate 检测进程风暴（原 count-process-variety）
    """
    
    def analyze(self, samples: List[Dict], 
                top_n: int = 10,
                include_metrics: bool = False) -> CommTopResult:
        """
        执行进程组分析
        
        Args:
            samples: 样本数据列表
            top_n: 返回前 N 个进程组
            include_metrics: 是否包含中间计算指标
            
        Returns:
            CommTopResult dataclass
        """
        # 1. 从 engine 获取数据
        comm_util = self._engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标（CV、Monopoly、SpawnRate）
        # ...
        
        # 3. 自动降噪
        # ...
        
        # 4. 构建结果
        return CommTopResult(
            groups=[...],
            folded_count=...,
            total_groups=...,
            risks=[...]
        )
```

---

## 5. AnalysisFacade 接口

### 5.1 类定义

```python
# From: scripts/perf_toolkit/analysis/facade.py

class AnalysisFacade:
    """
    Analysis Facade - Analysis 层对外暴露的唯一入口
    
    供 Composite 层调用，特点:
    - 延迟初始化 Analyzer 实例
    - 不触发 Trace 记录
    - 错误封装
    """
    
    def __init__(self, engine):
        """
        初始化 Facade
        
        Args:
            engine: PerfExpertEngine 实例
        """
        self._engine = engine
        self._analyzers = {}  # 延迟加载缓存
    
    def _get_analyzer(self, name: str) -> BaseAnalyzer:
        """延迟获取 Analyzer 实例"""
        ...
```

### 5.2 接口方法

#### analyze_comm_top - 进程组 CPU 分析

```python
def analyze_comm_top(self, 
                     samples: List[Dict], 
                     top_n: int = 10,
                     include_metrics: bool = False) -> CommTopResult:
    """
    进程组 CPU 分析（内部接口，不触发 Trace）
    
    整合原 get-process-top + cluster-comm + count-process-variety 能力：
    - 纵向聚合: 按进程名分组（原 cluster-comm）
    - 横向离群: CV 方差分析识别异常 PID（原 get-process-top）
    - 时间动态: Spawn Rate 检测进程风暴（原 count-process-variety）
    
    Args:
        samples: 样本数据（由 engine 过滤后提供）
        top_n: 返回前 N 个进程组（已过滤掉背景噪音）
        include_metrics: 是否包含中间计算指标
        
    Returns:
        CommTopResult: 包含 groups, folded_count, risks 等字段
    """
```

#### analyze_hotspots - 热点函数分析

```python
def analyze_hotspots(self, 
                     samples: List[Dict],
                     comm: Optional[str] = None,
                     pid: Optional[int] = None,
                     top_n: int = 20,
                     sort_by: str = "self") -> HotspotsResult:
    """
    热点函数分析（内部接口，不触发 Trace）
    
    Args:
        samples: 样本数据
        comm: 可选，按进程名过滤
        pid: 可选，按 PID 过滤
        top_n: 返回前 N 个热点
        sort_by: 排序方式 - "self" | "inclusive"
        
    Returns:
        HotspotsResult: 包含 hotspots, kernel_ratio, user_ratio 等字段
    """
```

#### analyze_core_distribution - 核心分布分析

```python
def analyze_core_distribution(self, 
                               samples: List[Dict], 
                               top_n: int = 10) -> CoreDistributionResult:
    """
    核心分布分析（内部接口，不触发 Trace）
    
    整合原 check-cpu-bottleneck + show-cpu-usage 能力。
    
    Args:
        samples: 样本数据
        top_n: 返回前 N 个饱和核心
        
    Returns:
        CoreDistributionResult: 包含 cores, imbalance_level, saturated_cores 等字段
    """
```

#### detect_anomalies - 异常检测

```python
def detect_anomalies(self, 
                     samples: List[Dict],
                     window_size: float = 1.0,
                     spike_threshold: float = 0.5,
                     min_utilization: float = 0.3,
                     cpu_id: Optional[int] = None,
                     top_n: int = 10) -> AnomaliesResult:
    """
    异常检测（内部接口，不触发 Trace）
    
    基于滑动窗口检测时序异常。
    
    Args:
        samples: 样本数据
        window_size: 滑动窗口大小（秒）
        spike_threshold: 变化倍数阈值
        min_utilization: 最小利用率阈值
        cpu_id: 可选，仅分析指定 CPU
        top_n: 返回前 N 个异常
        
    Returns:
        AnomaliesResult: 包含 anomalies, mutation_detected, spike_count 等字段
    """
```

#### cluster_paths - 路径聚类

```python
def cluster_paths(self, 
                  samples: List[Dict],
                  min_depth: int = 2,
                  min_samples: int = 5,
                  top_n: int = 10,
                  comm: Optional[str] = None,
                  pid: Optional[int] = None) -> PathClustersResult:
    """
    路径聚类（内部接口，不触发 Trace）
    
    按调用路径进行语义聚类。
    
    Args:
        samples: 样本数据
        min_depth: 最小调用深度
        min_samples: 最小样本数
        top_n: 返回前 N 个聚类
        comm: 可选，按进程名过滤
        pid: 可选，按 PID 过滤
        
    Returns:
        PathClustersResult: 包含 clusters, total_clusters, clustered_weight 等字段
    """
```

#### analyze_callers - 调用链溯源

```python
def analyze_callers(self, 
                    samples: List[Dict],
                    target_symbol: str,
                    comm: Optional[str] = None,
                    min_ratio: float = 0.5,
                    top_n: int = 10) -> CallersResult:
    """
    调用链溯源分析（内部接口，不触发 Trace）
    
    分析指定符号的调用者分布。
    
    Args:
        samples: 样本数据
        target_symbol: 目标符号名
        comm: 可选，按进程名过滤
        min_ratio: 最小占比阈值（百分比）
        top_n: 返回前 N 个调用者
        
    Returns:
        CallersResult: 包含 target, callers, total_weight 等字段
    """
```

### 5.3 Facade 工厂函数

```python
# Facade 缓存
_facade_cache: Dict[int, AnalysisFacade] = {}


def get_facade(engine) -> AnalysisFacade:
    """
    获取或创建 Facade 实例（带缓存）
    
    Args:
        engine: PerfExpertEngine 实例
        
    Returns:
        AnalysisFacade 实例
    """
    engine_id = id(engine)
    if engine_id not in _facade_cache:
        _facade_cache[engine_id] = AnalysisFacade(engine)
    return _facade_cache[engine_id]


def clear_facade_cache():
    """清除 Facade 缓存（主要用于测试）"""
    global _facade_cache
    _facade_cache = {}
```

---

## 6. 类型映射说明

### 6.1 Core 层 → Analysis 层类型映射

| Core 层类型 | 位置 | Analysis 层使用方式 |
|-------------|------|---------------------|
| `Sample` | `core/engine_types.py` | 所有 `analyze()` 方法的输入类型 `List[Sample]` |
| `PerfExpertEngine` | `core/engine.py` | Analyzer 构造函数注入，用于获取数据 |
| `CPUUtilization` | `core/engine_types.py` | 内部计算使用 |
| `CallGraph` | `core/engine_types.py` | `analyze_callers()` 内部使用 |

### 6.2 Analysis 层 → Composite 层类型映射

| Analysis 层类型 | Composite 层使用场景 |
|-----------------|----------------------|
| `AnomaliesResult` | `sys_audit` 检测系统突变 |
| `CommTopResult` | `sys_audit` / `bottleneck_analyze` 识别瓶颈进程 |
| `CoreDistributionResult` | `sys_audit` 分析核心负载均衡 |
| `HotspotsResult` | `bottleneck_analyze` 深度分析热点函数 |
| `PathClustersResult` | `bottleneck_analyze` 业务逻辑聚类 |
| `CallersResult` | `bottleneck_analyze` 热点溯源 |

### 6.3 输入类型演进说明

**当前实现**: `List[Dict]`

```python
# 当前代码中，samples 实际上是 List[Dict]
def analyze(self, samples: List[Dict], **kwargs) -> CommTopResult:
    # samples 是 engine 返回的字典列表
    pass
```

**未来演进**: `List[Sample]`

```python
# 理想情况下，应该使用强类型的 Sample
def analyze(self, samples: List[Sample], **kwargs) -> CommTopResult:
    # samples 是 Sample dataclass 列表
    pass
```

**迁移路径**:
1. 当前阶段保持 `List[Dict]` 兼容现有实现
2. 逐步将 engine 返回类型改为 `List[Sample]`
3. 最终统一使用 `List[Sample]` 作为输入

---

## 7. 异常类型

```python
# From: scripts/perf_toolkit/analysis/interfaces.py

class AnalysisError(Exception):
    """分析层基础异常"""
    pass


class EngineInterfaceError(AnalysisError):
    """Engine 接口调用错误"""
    pass


class InvalidSampleError(AnalysisError):
    """无效样本数据错误"""
    pass


class ConfigurationError(AnalysisError):
    """配置错误"""
    pass
```

---

## 8. 使用示例

### 8.1 Composite 层调用示例

```python
# composite/sys_audit.py

from ..analysis.facade import get_facade
from ..analysis.models import Risk

def cmd_sys_audit(builder, engine, args, samples):
    """系统审计组合命令"""
    
    # 1. 获取 Facade 实例
    facade = get_facade(engine)
    
    # 2. 执行多个分析（不触发 Trace）
    anomalies = facade.detect_anomalies(samples)
    core_dist = facade.analyze_core_distribution(samples)
    comm_top = facade.analyze_comm_top(samples, top_n=20)
    
    # 3. 综合分析结果
    primary_suspect = comm_top.groups[0] if comm_top.groups else None
    
    # 4. 记录风险（只记录综合结果）
    if primary_suspect and primary_suspect.impact_score > 50:
        builder.record_risk(
            level="critical",
            message=f"发现性能瓶颈: {primary_suspect.comm}",
            hint=f"执行: bottleneck-analyze --comm {primary_suspect.comm}"
        )
    
    # 5. 构建输出
    return SysAuditOutput(
        _risk=Risk(...),
        diagnosis={"primary_suspect": primary_suspect},
        details={
            "anomalies": anomalies,
            "core_distribution": core_dist,
            "comm_top": comm_top
        }
    )
```

### 8.2 直接调用 Analyzer 示例

```python
# 测试或自定义分析场景

from ..analysis.comm_top import CommTopAnalyzer
from ..analysis.models import CommTopResult

# 创建 Analyzer 实例
analyzer = CommTopAnalyzer(engine)

# 执行分析
result: CommTopResult = analyzer.analyze(samples, top_n=10)

# 处理结果
for group in result.groups:
    print(f"{group.comm}: CPU={group.total_cpu}%, Impact={group.impact_score}")

# 检查风险
for risk in result.risks:
    if risk.action_required:
        print(f"[ACTION] {risk.message}: {risk.hint}")
```

---

## 9. 接口版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-03 | 初始版本，定义 6 个分析器结果类型和 Facade 接口 |

---

## 10. 相关文档

- [三层架构设计](design-three-tier-architecture.md)
- [SHECR Attention Steering](design-attention-steering.md)
- [Output Format Spec](output-format-spec.md)
