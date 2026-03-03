# Analysis 层设计文档

> 角色: Analysis 工程师
> 目标: 三层架构中的 Analysis 层
> 依赖: Core Engine 接口

---

## 设计目标

### 核心原则

| 原则 | 说明 | 约束 |
|------|------|------|
| 职责分离 | Analyzer 只负责纯分析逻辑 | 不处理 CLI/Trace/输出格式 |
| 数据边界 | 所有数据通过 Engine 接口获取 | 禁止直接访问原始样本数据 |
| 双接口设计 | 提供内部接口（Facade）和 CLI 接口 | CLI 接口通过 @command 包装 |
| Risk 内聚 | Analyzer 识别风险并返回 risks 数据 | 由上层决定如何记录 |

### 重构前后对比

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
│         # 返回 Result dataclass         │
├─────────────────────────────────────────┤
│ @command("get-comm-top")                │
│ def cmd_get_comm_top(...):              │
│     # 调用 Analyzer                     │
│     # 记录 Trace                        │
│     # 构建输出                          │
└─────────────────────────────────────────┘
```

---

## 架构设计

### 目录结构

```
analysis/
├── __init__.py                 # 包入口
├── facade.py                   # Facade 接口 - AnalysisFacade
├── interfaces.py               # 类型定义和接口契约
├── base.py                     # BaseAnalyzer 抽象基类
├── models.py                   # 分析数据模型 (dataclass)
│
├── comm_top.py                 # CommTopAnalyzer
├── hotspots.py                 # HotspotsAnalyzer
├── core_distribution.py        # CoreDistAnalyzer
├── anomalies.py                # AnomaliesAnalyzer
├── path_clusters.py            # PathClustersAnalyzer
└── trace.py                    # TraceAnalyzer (调用链分析)
```

### 类层次结构

```
┌─────────────────────────────────────────────────────────────┐
│                    BaseAnalyzer (抽象基类)                   │
│  - engine: PerfExpertEngine                                 │
│  - analyze(samples, **kwargs) -> Result dataclass           │
│  - _create_risk() -> RiskInfo                               │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│CommTopAnalyzer│    │HotspotsAnalyzer      │    │CoreDistAnalyzer      │
│- analyze()    │    │- analyze()           │    │- analyze()           │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│AnomaliesAnalyzer     │    │PathClustersAnalyzer  │    │TraceAnalyzer         │
│- analyze()           │    │- analyze()           │    │- analyze()           │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## 核心类设计

### BaseAnalyzer 抽象基类

```python
# analysis/base.py

from abc import ABC, abstractmethod
from typing import List, Any
from ..core.engine_types import Sample
from ..core.models import RiskInfo


class BaseAnalyzer(ABC):
    """
    Analysis 层抽象基类
    
    设计约束:
    1. 只依赖 engine 接口获取数据
    2. 不直接操作 trace
    3. 返回具体 Result dataclass（非裸 dict）
    """
    
    def __init__(self, engine):
        self._engine = engine
    
    @abstractmethod
    def analyze(self, samples: List[Sample], **kwargs) -> Any:
        """
        执行分析
        
        Args:
            samples: 样本数据列表（Sample dataclass 列表）
            **kwargs: 分析特定参数
            
        Returns:
            具体 Result dataclass，如 AnomaliesResult, CommTopResult 等
        """
        pass
    
    def _create_risk(self, level: str, message: str, hint: str = "",
                     patterns: List[str] = None,
                     pending_targets: List[str] = None) -> RiskInfo:
        """创建标准化的 RiskInfo 对象"""
        return RiskInfo(
            level=level,
            message=message,
            hint=hint,
            patterns=patterns or [],
            pending_targets=pending_targets or [],
            source=self.__class__.__name__
        )
```

---

## 实际实现的分析器（6个）

### 1. HotspotsAnalyzer - hotspots.py

热点函数分析器，分析自研/包含 CPU 利用率最高的符号。

```python
class HotspotsAnalyzer(BaseAnalyzer):
    """热点函数分析器"""
    
    def analyze(self, samples: List[Sample],
                comm: Optional[str] = None,
                pid: Optional[int] = None,
                top_n: int = 20,
                sort_by: str = "self") -> HotspotsResult:
        """
        分析热点函数
        
        Returns:
            HotspotsResult dataclass with hotspots, kernel_ratio, user_ratio
        """
```

**返回类型**: `HotspotsResult`
```python
@dataclass
class HotspotsResult:
    hotspots: List[Hotspot]
    kernel_ratio: float
    user_ratio: float
    sort_by: str
    risks: List[RiskInfo]

@dataclass  
class Hotspot:
    symbol: str
    self_pct: float
    inclusive_pct: float
    is_kernel: bool
```

### 2. CommTopAnalyzer - comm_top.py

进程组 CPU 分析器（增强版），支持 CV、Monopoly、Storm 检测。

```python
class CommTopAnalyzer(BaseAnalyzer):
    """
    CommTop 分析器 - 进程组 CPU 分析（增强版）
    
    新增指标:
    - CV (变异系数): 检测负载不均衡
    - Monopoly (独占率): 识别单进程瓶颈  
    - SpawnRate (产生速率): 检测进程风暴
    - Impact Score (危害指数): 综合排序依据
    """
    
    CV_THRESHOLD = 1.0
    MONOPOLY_THRESHOLD = 0.8
    SPAWN_RATE_THRESHOLD = 10.0
    
    def analyze(self, samples: List[Sample], top_n: int = 10,
                include_metrics: bool = False) -> CommTopResult:
        """
        分析进程组 CPU 利用率
        
        Returns:
            CommTopResult dataclass
        """
```

**返回类型**: `CommTopResult`
```python
@dataclass
class CommTopResult:
    groups: List[CommGroup]
    folded_count: int
    total_groups: int
    risks: List[RiskInfo]
    storm_analysis: Optional[StormAnalysisResult]
    metrics: Optional[dict]
    groups_by_total_cpu: Optional[List[CommGroup]]
    groups_by_sys_cpu: Optional[List[CommGroup]]

@dataclass
class CommGroup:
    comm: str
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
    pid_count: int
    pids: List[int]
    cv: float
    monopoly: float
    spawn_rate: float
    diagnosis: str  # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float
```

### 3. CoreDistAnalyzer - core_distribution.py

核心分布分析器，检测 CPU 负载不均衡。

```python
class CoreDistAnalyzer(BaseAnalyzer):
    """核心分布分析器"""
    
    def analyze(self, samples: List[Sample], top_n: int = 10) -> CoreDistributionResult:
        """
        分析核心级负载分布
        
        Returns:
            CoreDistributionResult dataclass
        """
```

**返回类型**: `CoreDistributionResult`
```python
@dataclass
class CoreDistributionResult:
    cores: List[CoreStat]
    imbalance_level: str
    saturated_cores: List[CoreStat]
    total_cores: int
    risks: List[RiskInfo]

@dataclass
class CoreStat:
    cpu_id: int
    total_cpu: float
    kernel_cpu: float
    user_cpu: float
```

### 4. AnomaliesAnalyzer - anomalies.py

异常检测分析器，检测时序异常和突变。

```python
class AnomaliesAnalyzer(BaseAnalyzer):
    """异常检测分析器"""
    
    def analyze(self, samples: List[Sample],
                window_size: float = 1.0,
                spike_threshold: float = 0.5,
                min_utilization: float = 0.3,
                cpu_id: Optional[int] = None,
                top_n: int = 10) -> AnomaliesResult:
        """
        检测时序异常
        
        Returns:
            AnomaliesResult dataclass
        """
```

**返回类型**: `AnomaliesResult`
```python
@dataclass
class AnomaliesResult:
    anomalies: List[Anomaly]
    mutation_detected: bool
    spike_count: int
    drop_count: int
    risks: List[RiskInfo]

@dataclass
class Anomaly:
    type: str  # "SPIKE" | "DROP"
    cpu_id: int
    time_range_start: str
    time_range_end: str
    prev_util: float
    curr_util: float
    next_util: float
    z_score: float
```

### 5. PathClustersAnalyzer - path_clusters.py

路径聚类分析器，按调用路径聚类分析。

```python
class PathClustersAnalyzer(BaseAnalyzer):
    """路径聚类分析器"""
    
    def analyze(self, samples: List[Sample],
                min_depth: int = 2,
                min_samples: int = 5,
                top_n: int = 10,
                comm: Optional[str] = None,
                pid: Optional[int] = None) -> PathClustersResult:
        """
        路径聚类分析
        
        Returns:
            PathClustersResult dataclass
        """
```

**返回类型**: `PathClustersResult`
```python
@dataclass
class PathClustersResult:
    clusters: List[PathCluster]
    total_clusters: int
    shown_clusters: int
    total_weight: float
    clustered_weight: float
    risks: List[RiskInfo]

@dataclass
class PathCluster:
    cluster_id: str
    path_signature: str
    depth: int
    weight: float
    cpu_util: float
```

### 6. TraceAnalyzer - trace.py

调用链分析器，分析函数调用关系和溯源。

**注意**: 调用链分析功能已整合到 AnalysisFacade.analyze_callers() 方法中，但 TraceAnalyzer 类仍然保留用于其他 trace 相关分析。

---

## AnalysisFacade 接口

### Facade 设计

```python
# analysis/facade.py

class AnalysisFacade:
    """
    Analysis Facade - 对外暴露的干净接口
    
    供 Composite 层调用，不触发 Trace 记录。
    """
    
    def __init__(self, engine):
        self._engine = engine
        self._analyzers = {}  # 延迟加载缓存
    
    def _get_analyzer(self, name: str):
        """延迟获取 Analyzer 实例"""
        if name not in self._analyzers:
            if name == "comm_top":
                from .comm_top import CommTopAnalyzer
                self._analyzers[name] = CommTopAnalyzer(self._engine)
            elif name == "hotspots":
                from .hotspots import HotspotsAnalyzer
                self._analyzers[name] = HotspotsAnalyzer(self._engine)
            elif name == "core_dist":
                from .core_distribution import CoreDistAnalyzer
                self._analyzers[name] = CoreDistAnalyzer(self._engine)
            elif name == "anomalies":
                from .anomalies import AnomaliesAnalyzer
                self._analyzers[name] = AnomaliesAnalyzer(self._engine)
            elif name == "path_clusters":
                from .path_clusters import PathClustersAnalyzer
                self._analyzers[name] = PathClustersAnalyzer(self._engine)
        return self._analyzers[name]
```

### Facade 接口方法

| 方法 | 参数 | 返回类型 | 说明 |
|------|------|----------|------|
| `analyze_comm_top()` | samples, top_n=10, include_metrics=False | `CommTopResult` | 进程组 CPU 分析 |
| `analyze_hotspots()` | samples, comm=None, pid=None, top_n=20, sort_by="self" | `HotspotsResult` | 热点函数分析 |
| `analyze_core_distribution()` | samples, top_n=10 | `CoreDistributionResult` | 核心分布分析 |
| `detect_anomalies()` | samples, window_size=1.0, spike_threshold=0.5, min_utilization=0.3, cpu_id=None, top_n=10 | `AnomaliesResult` | 异常检测 |
| `cluster_paths()` | samples, min_depth=2, min_samples=5, top_n=10, comm=None, pid=None | `PathClustersResult` | 路径聚类 |
| `analyze_callers()` | samples, target_symbol, comm=None, min_ratio=0.5, top_n=10 | `CallersResult` | 调用链溯源分析 |

### analyze_callers 详细说明

```python
def analyze_callers(self, samples: List[Sample],
                    target_symbol: str,
                    comm: Optional[str] = None,
                    min_ratio: float = 0.5,
                    top_n: int = 10) -> CallersResult:
    """
    调用链溯源分析（内部接口，不触发 Trace）
    
    Args:
        samples: 样本数据
        target_symbol: 目标符号名
        comm: 可选，按进程名过滤
        min_ratio: 最小占比阈值（百分比）
        top_n: 返回前 N 个调用者
        
    Returns:
        CallersResult dataclass
    """
```

**返回类型**: `CallersResult`
```python
@dataclass
class CallersResult:
    target: str
    callers: List[CallerAttribution]
    total_weight: float
    risks: List[RiskInfo]

@dataclass
class CallerAttribution:
    symbol: str
    call_count: int
    call_ratio: float
    total_weight: float
```

### Facade Factory

```python
_facade_cache: Dict[int, AnalysisFacade] = {}


def get_facade(engine) -> AnalysisFacade:
    """获取或创建 Facade 实例（带缓存）"""
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

## 数据模型

### 统一返回格式

所有 Analyzer 返回具体 dataclass（非裸 dict）：

```python
# analysis/models.py

@dataclass
class AnalysisResult:
    """统一分析结果结构"""
    result: dict = field(default_factory=dict)
    risks: List[RiskInfo] = field(default_factory=list)
    metrics: Optional[dict] = None
```

### 风险信息模型

```python
# core/models.py

@dataclass
class RiskInfo:
    level: str                    # critical | warning | info | none
    message: str
    hint: str
    patterns: List[str]
    pending_targets: List[str]
    source: str                   # 产生风险的 Analyzer 名称
    action_required: bool = False
```

### 诊断类型常量

```python
# config/defaults.py

class DiagnosisType:
    """诊断类型"""
    BOTTLENECK = "BOTTLENECK"      # 单点瓶颈
    STORM = "STORM"                # 进程风暴
    UNBALANCED = "UNBALANCED"      # 负载不均衡
    HEALTHY = "HEALTHY"            # 健康
```

---

## 测试策略

### 测试路径规范

| 测试类型 | 路径 | 说明 |
|----------|------|------|
| 三层架构测试 | `tests/three_tier/` | Core/Analysis/Composite 接口测试 |
| 分析器单元测试 | `tests/analysis/` | 各 Analyzer 独立测试 |

### 单元测试示例

```python
# tests/analysis/test_comm_top.py

import unittest
from unittest.mock import Mock
from scripts.perf_toolkit.analysis.comm_top import CommTopAnalyzer


class TestCommTopAnalyzer(unittest.TestCase):
    def setUp(self):
        self.engine = Mock()
        self.analyzer = CommTopAnalyzer(self.engine)
    
    def test_calculate_cv_uniform(self):
        """测试均匀分布 CV"""
        pid_dist = {1: 10.0, 2: 10.0, 3: 10.0}
        cv = self.analyzer._calculate_cv(pid_dist)
        self.assertAlmostEqual(cv, 0.0, places=2)
    
    def test_calculate_cv_imbalanced(self):
        """测试不均衡分布 CV"""
        pid_dist = {1: 30.0, 2: 0.0, 3: 0.0}
        cv = self.analyzer._calculate_cv(pid_dist)
        self.assertGreater(cv, 1.0)
```

### 运行测试

```bash
# 运行所有自动化测试
python3 tests/run_tests.py

# 详细输出
python3 tests/run_tests.py -v
```

---

## 附录

### 关键公式参考

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
