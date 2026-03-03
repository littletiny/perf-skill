# 三层架构开发分工文档

> 版本: v1.0  
> 创建时间: 2026-03-02  
> 预期团队规模: 3-4人  
> 开发周期: 5周（含联调）

---

## 分工总览

### 角色定义

| 角色 | 人数 | 主要职责 | 核心技能要求 |
|------|------|----------|--------------|
| **Core架构师** | 1人 | Core层接口设计、Facade定义、架构把控 | 数据建模、API设计、性能优化 |
| **Analysis工程师** | 1-2人 | Analysis层重构、Analyzer实现 | 业务逻辑、代码重构、单测编写 |
| **Composite工程师** | 1人 | Composite层实现、增强功能 | 业务编排、诊断逻辑、集成测试 |
| **QA/文档工程师** | 0-1人 | 测试框架、文档维护（3人团队时可由其他角色兼任） | 测试设计、文档写作 |

### 工作包划分

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           三层架构开发工作包                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 工作包A: Core层与Facade (Core架构师)                                │   │
│  │ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │ │ Core接口扩展     │  │ Analysis Facade │  │ 架构规范制定     │      │   │
│  │ │  Week 1         │  │  Week 1-2       │  │  Week 1-5       │      │   │
│  │ └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼ (提供接口给下层)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 工作包B: Analysis层重构 (Analysis工程师)                            │   │
│  │ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │ │ 工具拆分Analyzer │  │ 适配Facade      │  │ 单测编写        │      │   │
│  │ │  Week 2         │  │  Week 2-3       │  │  Week 3-4       │      │   │
│  │ └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼ (提供接口给下层)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 工作包C: Composite与增强 (Composite工程师)                          │   │
│  │ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │ │ Composite命令   │  │ Enhanced功能    │  │ 集成联调        │      │   │
│  │ │  Week 3-4       │  │  Week 4         │  │  Week 5         │      │   │
│  │ └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 工作包D: 测试与文档 (QA/文档工程师，或由ABC兼任)                      │   │
│  │ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │ │ 测试框架搭建     │  │ 集成测试        │  │ 文档更新        │      │   │
│  │ │  Week 2         │  │  Week 4-5       │  │  Week 5         │      │   │
│  │ └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 详细分工（3人方案）

### 方案说明

本方案为**3人精简配置**，适用于小团队快速推进：

| 角色 | 人员 | 负责工作包 | 工作量占比 |
|------|------|-----------|-----------|
| Core架构师 | 人员A | 工作包A + 架构评审 | 35% |
| Analysis工程师 | 人员B | 工作包B + 部分测试 | 40% |
| Composite工程师 | 人员C | 工作包C + 文档 + 剩余测试 | 25% |

---

## Risk接口设计（全员必读）

### Risk在三层架构中的定位

Risk接口与Trace类似，贯穿三层架构，但职责不同：
- **Trace**: 记录诊断过程的"时间线"（What happened）
- **Risk**: 标识当前发现的"风险点"（What needs attention）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Risk在三层架构中的流转                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 3: Composite                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • 聚合多个Analysis的risk                                            │   │
│  │ • 去重：相同目标的多条risk合并                                       │   │
│  │ • 分级：Primary Risk / Secondary Risk / Info                        │   │
│  │ • 生成综合的_risk输出                                               │   │
│  │                                                                     │   │
│  │ Output: _risk = {                                                   │   │
│  │   level: "critical",                                                │   │
│  │   message: "发现2个性能瓶颈: app_B(单核饱和), lsof(进程风暴)",        │   │
│  │   hint: "1. bottleneck-trace --comm app_B; 2. storm-trace --comm lsof │   │
│  │ }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │ 聚合/去重/分级                          │
│  Layer 2: Analysis                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CommTopAnalyzer:                                                    │   │
│  │   if monopoly > 0.8:                                                │   │
│  │     return {                                                        │   │
│  │       result: {...},                                                │   │
│  │       risks: [{level: "critical", message: "...", hint: "..."}]       │   │
│  │     }                                                               │   │
│  │                                                                     │   │
│  │ HotspotsAnalyzer:                                                   │   │
│  │   if kernel_ratio > 80%:                                            │   │
│  │     return {result: {...}, risks: [...]}                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │ 封装                                   │
│  Layer 1: Core                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ RiskMixin - 基础能力:                                               │   │
│  │   • add_risk(level, message, hint, patterns, targets)               │   │
│  │   • get_top_risk() -> 最高级别risk                                  │   │
│  │   • format_output(data) -> 添加_risk字段                            │   │
│  │                                                                     │   │
│  │ RiskDisplayConfig - 展示配置:                                       │   │
│  │   • 颜色方案、模板、显示模式                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 各层Risk职责

| 层级 | Risk职责 | 关键行为 |
|------|----------|----------|
| **Core** | 提供Risk基础设施 | `RiskMixin`类、`RiskDisplayConfig`配置 |
| **Analysis** | 识别并上报风险 | Analyzer返回`risks`列表，包含level/message/hint |
| **Composite** | 聚合与分级 | 使用`RiskAggregator`收集子分析risk，去重合并，生成综合risk |

### Risk数据结构规范

```python
# 统一Risk结构（所有层级遵循）
Risk = {
    "level": str,           # "critical" | "warning" | "info" | "none"
    "message": str,         # 一句话风险描述
    "hint": str,            # 强制性下一步操作
    "patterns": List[str],  # 检测到的模式标签
    "pending_targets": List[str],  # 待处理目标列表
    "action_required": bool # level in ["critical", "warning"]
}
```

### 各层Risk接口设计

#### Core层（人员A负责）

文件: `core/risk_mixin.py`

```python
class RiskMixin:
    """
    Risk基础能力
    
    设计约束:
    1. 与输出格式解耦 - 只负责risk数据，不负责渲染
    2. 支持多risk累积 - 一个分析过程可能发现多个risk
    3. 自动分级 - get_top_risk()自动返回最高级别
    """
    
    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: List[str] = None, targets: List[str] = None):
        """添加risk（支持累积）"""
        pass
    
    def get_top_risk(self) -> Dict:
        """获取最高级别risk（用于_risk字段）"""
        pass
    
    def get_all_risks(self) -> List[Dict]:
        """获取所有risk（供Composite聚合使用）"""
        pass
    
    def format_output(self, data: Dict) -> Dict:
        """为输出添加_risk字段"""
        pass
```

#### Analysis层（人员B负责）

文件: `analysis/comm_top.py` - CommTopAnalyzer示例

```python
class CommTopAnalyzer(BaseAnalyzer):
    def analyze(self, samples, top_n=10) -> Dict:
        # ... 分析逻辑 ...
        
        # 识别risk
        risks = []
        for group in groups:
            if group.monopoly > 0.8:
                risks.append(self._create_risk(
                    level="critical",
                    message=f"{group.comm} 单核饱和 (Monopoly={group.monopoly:.2f})",
                    hint=f"bottleneck-trace --comm {group.comm}",
                    patterns=["SINGLE_CORE_SATURATION"],
                    pending_targets=[group.comm]
                ))
            elif group.spawn_rate > 10:
                risks.append(self._create_risk(...))
        
        return {
            "result": {"groups": [...], ...},
            "risks": risks,  # 返回所有risk，供Composite聚合
            "metrics": {...}  # 可选，供Composite使用
        }
```

#### Composite层（人员C负责）

文件: `composite/sys_audit.py` - Risk聚合逻辑

```python
from .risk_aggregator import RiskAggregator, AggregatedRisk

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    facade = AnalysisFacade(engine)
    
    # 收集各分析的risk
    aggregator = RiskAggregator()
    
    # 执行分析并收集risks
    anomalies = facade.detect_anomalies(samples)
    aggregator.add_risks([RiskItem.from_dict(r) for r in anomalies.get("risks", [])])
    
    core_dist = facade.analyze_core_distribution(samples)
    aggregator.add_risks([RiskItem.from_dict(r) for r in core_dist.get("risks", [])])
    
    # Risk聚合与去重
    aggregated_risk = aggregator.aggregate()
    
    # 记录到Trace（只记录聚合后的）
    if aggregated_risk.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated_risk.level,
            aggregated_risk.message,
            aggregated_risk.hint
        )
    
    output = SysAuditOutput(
        _risk=RiskInfo(...),
        diagnosis={...}
    )
    return output
```

RiskAggregator核心逻辑：
- 按target去重：同一目标的多个risk，取最高级别
- 分级统计：critical/warning/info数量
- 合并hint：多条hint用分号分隔

### Risk与Trace的协作

```
场景: 执行 sys-audit 命令

Timeline记录（只记录命令执行和关键发现）:
─────────────────────────────────────────
[1] 10:00:00 sys-audit --data test.data
    └── Finding: Risk created - ISS-001

Timeline不记录（子分析的内部risk）:
    └── NOT RECORDED: detect-anomalies risks
    └── NOT RECORDED: analyze-core-distribution risks  
    └── NOT RECORDED: get-comm-top risks

Issues记录（聚合后的risk）:
─────────────────────────────────────────
ISS-001: [critical] 发现2个性能瓶颈: app_B, lsof
  Hint: 1. bottleneck-trace --comm app_B; 2. storm-trace --comm lsof
  Status: open
```

### 分工调整（含Risk）

| 人员 | Risk相关工作 | 说明 |
|------|-------------|------|
| **人员A** | Core层RiskMixin优化 | 确保支持`get_all_risks()`供Composite使用 |
| **人员B** | 各Analyzer的risk识别 | 在分析逻辑中识别并返回risk |
| **人员C** | Composite的risk聚合 | 使用`RiskAggregator`实现聚合逻辑 |

---

## 工作包A：Core层与Facade（人员A）

### 职责范围

- Core层接口设计与实现
- Analysis Facade设计与定义
- 跨层接口规范制定
- Code Review与架构把控

### 交付物清单

#### Week 1：Core层接口扩展

| 交付物 | 文件路径 | 验收标准 |
|--------|----------|----------|
| Engine接口扩展 | `core/engine.py` | 新增接口全部实现，单测通过 |
| 生命周期接口 | `get_process_lifecycle()` | 能正确计算spawn_rate |
| 调用图接口 | `get_call_graph()` | 返回正确的调用关系 |
| 数据访问控制 | 代码审查 | analysis层无法直接访问原始数据 |

**详细任务**:

```python
# core/engine.py 需新增的接口

class PerfExpertEngine:
    # ========== 已有接口（保持兼容） ==========
    def get_comm_cpu_util(self, samples) -> Dict[str, CommCPUInfo]: ...
    def get_pid_cpu_util(self, samples) -> Dict[tuple, ProcessCPUInfo]: ...
    def get_core_cpu_util(self, samples) -> Dict[int, CoreCPUInfo]: ...
    
    # ========== 新增接口（Week 1完成） ==========
    def get_process_lifecycle(self, samples=None, comm=None) -> ProcessLifecycle:
        """
        获取进程生命周期信息
        
        Returns:
            ProcessLifecycle: 包含spawn_events, exit_events, spawn_rate, lifecycle_stats
        """
        pass
    
    def get_pid_cpu_distribution(self, samples=None, comm=None) -> Dict[int, float]:
        """
        获取指定comm下各PID的CPU分布
        
        Returns:
            {pid: cpu_percent, ...} 用于计算CV和Monopoly
        """
        pass
    
    def get_call_graph(self, samples=None, target_symbol=None, comm=None) -> CallGraph:
        """
        获取调用图
        
        Returns:
            CallGraph: 包含callers, call_graph, hot_paths
        """
        pass
```

数据类型定义在 `core/engine_types.py`：

```python
@dataclass
class ProcessLifecycle:
    """进程生命周期信息"""
    spawn_events: List[LifecycleEvent] = field(default_factory=list)
    exit_events: List[LifecycleEvent] = field(default_factory=list)
    spawn_rate: float = 0.0
    lifecycle_stats: LifecycleStats = field(default_factory=LifecycleStats)

@dataclass
class CallGraph:
    """调用图"""
    callers: List[CallerInfo] = field(default_factory=list)
    call_graph: Dict[str, List[CallEdge]] = field(default_factory=dict)
    hot_paths: List[str] = field(default_factory=list)
```

#### Week 1-2：Analysis Facade设计与实现

| 交付物 | 文件路径 | 验收标准 |
|--------|----------|----------|
| Facade基础框架 | `analysis/facade.py` | 类结构完整，延迟加载正确 |
| 基类定义 | `analysis/base.py` | BaseAnalyzer抽象基类 |
| 数据模型 | `analysis/models.py` | Risk、CommGroup等模型 |
| 错误处理机制 | 异常类定义 | 统一的异常类型和错误码 |

**详细任务**:

```python
# analysis/facade.py 框架

class AnalysisFacade:
    """
    Analysis Facade - 对外暴露的干净接口
    
    设计原则:
    1. 延迟初始化 - 按需创建Analyzer实例
    2. 接口隔离 - Composite只依赖Facade，不依赖具体Analyzer
    3. 错误封装 - 下层异常转换为有意义的错误信息
    """
    
    def __init__(self, engine: PerfExpertEngine):
        self._engine = engine
        self._analyzers = {}  # 延迟加载缓存
    
    def _get_analyzer(self, name: str) -> BaseAnalyzer:
        """延迟获取Analyzer实例"""
        if name not in self._analyzers:
            if name == "comm_top":
                from .comm_top import CommTopAnalyzer
                self._analyzers[name] = CommTopAnalyzer(self._engine)
            elif name == "hotspots":
                from .hotspots import HotspotsAnalyzer
                self._analyzers[name] = HotspotsAnalyzer(self._engine)
            # ... 其他analyzer
        return self._analyzers[name]
    
    # ========== 供Composite调用的接口 ==========
    def analyze_comm_top(self, samples, top_n=10, include_metrics=False) -> Dict: ...
    def analyze_hotspots(self, samples, comm=None, pid=None, top_n=20, sort_by="self") -> Dict: ...
    def analyze_core_distribution(self, samples, top_n=10) -> Dict: ...
    def detect_anomalies(self, samples, window_size=1.0, spike_threshold=0.5, 
                         min_utilization=0.3, cpu_id=None, top_n=10) -> Dict: ...
    def cluster_paths(self, samples, min_depth=2, min_samples=5, 
                      top_n=10, comm=None, pid=None) -> Dict: ...
    def cluster_symbols(self, samples, top_n=10, include_experts=True, 
                        rules_file=None, comm=None, pid=None) -> Dict: ...
    def count_process_variety(self, samples, top_n=20, storm_pid_threshold=50,
                              storm_cpu_threshold=0.5, storm_ratio_threshold=2.0,
                              comm=None) -> Dict: ...
```

### 协作接口

```
输入依赖:
- 无（Week 1可并行启动）

输出给下游:
- Week 1结束: Core Engine新接口可用
- Week 2结束: AnalysisFacade可用

协作方式:
- Week 1每天与人员B对齐接口设计
- Week 2 Code Review人员B的Analyzer实现
```

---

## 工作包B：Analysis层重构（人员B）

### 职责范围

- 现有analysis工具拆分重构
- Analyzer类实现
- 适配新的Facade接口
- 单元测试编写

### 交付物清单

#### Week 2：工具拆分与Analyzer实现

| 交付物 | 文件路径 | 验收标准 |
|--------|----------|----------|
| CommTopAnalyzer | `analysis/comm_top.py` | 纯逻辑类，无CLI/Trace依赖 |
| HotspotsAnalyzer | `analysis/hotspots.py` | 纯逻辑类，无CLI/Trace依赖 |
| CoreDistAnalyzer | `analysis/core_distribution.py` | 纯逻辑类，无CLI/Trace依赖 |
| AnomaliesAnalyzer | `analysis/anomalies.py` | 纯逻辑类，无CLI/Trace依赖 |
| PathClustersAnalyzer | `analysis/path_clusters.py` | 纯逻辑类，无CLI/Trace依赖 |
| SymbolClustersAnalyzer | `analysis/clusters.py` | 纯逻辑类，无CLI/Trace依赖 |
| ProcessVarietyAnalyzer | `analysis/process_variety.py` | 纯逻辑类，无CLI/Trace依赖 |
| CLI适配层 | 原文件底部 | 保持CLI兼容，通过@command装饰器调用Analyzer |

**重构模式（以comm_top为例）**:

```python
# analysis/comm_top.py

class CommTopAnalyzer(BaseAnalyzer):
    """
    CommTop分析器 - 纯逻辑实现
    
    设计约束:
    1. 只依赖engine接口获取数据
    2. 不操作trace
    3. 返回原始dict，包含result和risks
    """
    
    # 诊断分级阈值
    CV_THRESHOLD = 1.0
    MONOPOLY_THRESHOLD = 0.8
    SPAWN_RATE_THRESHOLD = 10.0
    
    def analyze(self, samples: List[Dict], top_n: int = 10,
                include_metrics: bool = False) -> Dict[str, Any]:
        """
        核心分析逻辑
        
        Returns:
            {
                "result": {"groups": [...], "folded_count": N, "total_groups": N},
                "risks": [...],
                "metrics": {...}  # if include_metrics
            }
        """
        # 1. 从engine获取数据
        comm_util = self._engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标
        groups = []
        risks = []
        
        for comm, info in comm_util.items():
            # 获取PID级分布用于计算CV和Monopoly
            pid_dist = self._engine.get_pid_cpu_distribution(samples, comm)
            cv = self._calculate_cv(pid_dist)
            monopoly = self._calculate_monopoly(pid_dist)
            
            # 获取生命周期信息
            lifecycle = self._engine.get_process_lifecycle(samples, comm)
            spawn_rate = lifecycle.spawn_rate
            
            # 诊断分级
            diagnosis = self._classify(cv, monopoly, spawn_rate)
            
            # 计算危害指数
            impact_score = self._calculate_impact_score(
                info.total_pct, cv, monopoly, spawn_rate
            )
            
            group = CommGroup(...)
            groups.append(group)
            
            # 识别risk
            risk = self._identify_risk(group)
            if risk:
                risks.append(risk)
        
        # 3. 按危害指数排序
        groups.sort(key=lambda x: x.impact_score, reverse=True)
        
        # 4. 自动降噪
        display_groups, folded_groups = self._auto_filter(groups)
        
        return {
            "result": {
                "groups": [g.to_dict() for g in display_groups[:top_n]],
                "folded_count": len(folded_groups),
                "total_groups": len(groups)
            },
            "risks": [r.to_dict() for r in risks],
            "metrics": {...} if include_metrics else None
        }
```

#### Week 2-3：Facade适配与联调

| 交付物 | 说明 |
|--------|------|
| Facade集成测试 | 验证Facade能正确调用所有Analyzer |
| 向后兼容验证 | 现有CLI命令行为不变 |
| 单元测试 | 每个Analyzer的单元测试覆盖 |

### 工作量估算

| 任务 | 预估工时 | 说明 |
|------|----------|------|
| CommTopAnalyzer | 8h | 最复杂，需要实现CV/Monopoly/SpawnRate计算 |
| HotspotsAnalyzer | 4h | 相对简单，主要是提取现有逻辑 |
| CoreDistAnalyzer | 4h | 中等复杂度 |
| AnomaliesAnalyzer | 4h | 中等复杂度 |
| PathClustersAnalyzer | 4h | 中等复杂度 |
| SymbolClustersAnalyzer | 4h | 中等复杂度 |
| ProcessVarietyAnalyzer | 4h | 中等复杂度 |
| Facade适配 | 8h | 确保所有Analyzer能被Facade调用 |
| 单元测试 | 12h | 为每个Analyzer编写测试 |
| **总计** | **48h** | 约6个工作日 |

### 协作接口

```
输入依赖:
- Week 1结束: Core Engine新接口可用
- Week 2开始: AnalysisFacade框架可用

输出给下游:
- Week 2结束: 2个核心Analyzer可用（CommTop + Hotspots）
- Week 3结束: 所有Analyzer可用，Facade集成完成

协作方式:
- 每天与人员A对齐接口使用问题
- Week 3开始与人员C对接，提供Facade使用培训
```

---

## 工作包C：Composite与增强功能（人员C）

### 职责范围

- Composite层实现（3个组合命令）
- Enhanced get-comm-top功能增强
- 集成测试
- 文档更新

### 交付物清单

#### Week 3-4：Composite命令实现

| 交付物 | 文件路径 | 验收标准 |
|--------|----------|----------|
| composite目录结构 | `composite/__init__.py` | 包结构正确 |
| RiskAggregator | `composite/risk_aggregator.py` | 能正确聚合去重risk |
| 数据模型 | `composite/models.py` | RiskItem等模型定义 |
| sys-audit命令 | `composite/sys_audit.py` | 能正确编排多个analysis工具 |
| bottleneck-trace命令 | `composite/bottleneck_trace.py` | 能自动识别瓶颈并深度分析 |
| storm-trace命令 | `composite/storm_trace.py` | 能追溯进程风暴来源 |
| CLI注册 | `scripts/shecr.py` | 新命令可用 |

**sys-audit实现示例**:

```python
# composite/sys_audit.py

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """
    系统审计组合命令
    
    编排: detect-anomalies → analyze-core-distribution → get-comm-top
    """
    from ..analysis.facade import AnalysisFacade
    from .risk_aggregator import RiskAggregator
    
    facade = AnalysisFacade(engine)
    aggregator = RiskAggregator()
    
    # 并行执行多个分析（内部调用，不触发Trace）
    anomalies = facade.detect_anomalies(samples)
    aggregator.add_risks([RiskItem.from_dict(r) for r in anomalies.get("risks", [])])
    
    core_dist = facade.analyze_core_distribution(samples)
    aggregator.add_risks([RiskItem.from_dict(r) for r in core_dist.get("risks", [])])
    
    # CommTop分析（增强版，通过include_metrics获取详细指标）
    from ..analysis.comm_top import CommTopAnalyzer
    comm_top_analyzer = CommTopAnalyzer(engine)
    comm_top_result = comm_top_analyzer.analyze(samples, top_n=top_n, include_metrics=True)
    aggregator.add_risks([RiskItem.from_dict(r) for r in comm_top_result.get("risks", [])])
    
    # 综合分析
    diagnosis = _synthesize_diagnosis(anomalies, core_dist, comm_top_result)
    
    # Risk聚合
    aggregated_risk = aggregator.aggregate()
    
    # 记录到Trace（只记录聚合后的）
    if aggregated_risk.level in ["critical", "warning"]:
        builder.record_risk(
            aggregated_risk.level,
            aggregated_risk.message,
            aggregated_risk.hint
        )
    
    # 构建输出
    output = SysAuditOutput(
        _risk=RiskInfo(...),
        diagnosis=diagnosis,
        details={...}
    )
    return output
```

#### Week 4：Enhanced功能增强

| 交付物 | 说明 | 依赖 |
|--------|------|------|
| CV计算优化 | 在CommTopAnalyzer中完善变异系数计算 | 人员B的Analyzer框架 |
| Monopoly计算 | 实现核心独占率计算 | 人员B的Analyzer框架 |
| 自动降噪 | 实现"平庸的大多数"折叠逻辑 | 人员B的Analyzer框架 |
| 危害指数 | 实现Impact Score排序 | 人员B的Analyzer框架 |

**增强功能实现**:

```python
# analysis/comm_top.py 中的增强实现

def _calculate_impact_score(self, total_cpu: float, cv: float, 
                           monopoly: float, spawn_rate: float) -> float:
    """
    计算危害指数
    
    公式: CPU*0.3 + CV*40 + Monopoly*50 + SpawnRate*5
    """
    return (
        total_cpu * 0.3 +
        cv * 40 +
        monopoly * 50 +
        spawn_rate * 5
    )

def _auto_filter(self, groups: List[CommGroup]) -> Tuple[List[CommGroup], List[CommGroup]]:
    """
    自动过滤，区分"值得关注"和"背景噪音"
    
    判断标准（满足任一即认为显著）：
    1. CPU 总量 > 5%
    2. CV > 1.0（分布严重不均）
    3. Monopoly > 0.8（单点极端离群）
    4. SpawnRate > 10/s（进程风暴）
    """
    display: List[CommGroup] = []
    folded: List[CommGroup] = []
    
    for g in groups:
        is_significant = (
            g.total_cpu > self.SIGNIFICANT_CPU_THRESHOLD or
            g.cv > self.SIGNIFICANT_CV_THRESHOLD or
            g.monopoly > self.SIGNIFICANT_MONOPOLY_THRESHOLD or
            g.spawn_rate > self.SIGNIFICANT_SPAWN_RATE_THRESHOLD
        )
        
        if is_significant:
            display.append(g)
        else:
            folded.append(g)
    
    return display, folded
```

### 工作量估算

| 任务 | 预估工时 | 说明 |
|------|----------|------|
| composite目录搭建 | 2h | 包结构、__init__.py |
| RiskAggregator实现 | 4h | risk聚合与去重逻辑 |
| sys-audit实现 | 8h | 最复杂的组合逻辑 |
| bottleneck-trace实现 | 6h | 自动识别+深度分析 |
| storm-trace实现 | 4h | 相对简单 |
| CLI注册 | 2h | shecr.py修改 |
| Enhanced功能 | 8h | CV/Monopoly/降噪/评分 |
| 集成测试 | 8h | 端到端测试 |
| 文档更新 | 6h | SKILL.md, tools.md |
| **总计** | **48h** | 约6个工作日 |

### 协作接口

```
输入依赖:
- Week 2结束: Core Engine接口稳定
- Week 3开始: AnalysisFacade可用（人员A提供培训）
- Week 3结束: 2个核心Analyzer可用（人员B交付）

输出给下游:
- Week 4结束: 3个Composite命令可用
- Week 5: 完整功能集成测试

协作方式:
- Week 3与人员A对接，学习Facade使用
- Week 3与人员B对齐Analyzer输出格式
- Week 5与人员A/B一起进行联调
```

---

## 协作流程

### 日常协作机制

```
每日站会 (15分钟):
├── 昨天完成了什么
├── 今天计划做什么
├── 有什么阻塞需要协助
└── 接口变更通知

每周同步会 (1小时):
├── 本周里程碑回顾
├── 下周计划对齐
├── 技术方案讨论
└── 架构调整决策
```

### 代码协作规范

| 场景 | 处理方式 |
|------|----------|
| 接口变更 | 在群里@所有人，更新接口文档 |
| Code Review | 所有PR需要至少1人Review，人员A的PR需要全员Review |
| 冲突解决 | 涉及架构的冲突由人员A决策 |
| 测试失败 | 提交者负责修复，阻塞发布 |

### 里程碑检查点

| 周次 | 检查点 | 交付标准 | 参与人 |
|------|--------|----------|--------|
| Week 1结束 | Core接口冻结 | 所有新接口实现+单测通过 | A+B+C |
| Week 2结束 | Facade就绪 | 2个核心Analyzer可用 | A+B |
| Week 3结束 | Analyzer完成 | 所有Analyzer可用 | A+B |
| Week 4结束 | Composite就绪 | 3个组合命令可用 | B+C |
| Week 5结束 | 发布就绪 | 集成测试通过+文档更新 | A+B+C |

---

## 风险与应对

### 风险清单

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| Core接口设计不合理导致重构 | 中 | 高 | Week 1每天与B对齐，快速迭代 |
| Analyzer拆分工作量超预期 | 高 | 中 | 优先级排序，先完成核心工具 |
| Composite编排逻辑复杂 | 中 | 中 | 提前设计算法，必要时简化 |
| Trace边界测试遗漏 | 中 | 高 | 专门的Trace边界测试用例 |
| 人员请假/变动 | 低 | 高 | 关键知识共享，文档齐全 |

### 应急预案

**场景1：人员B进度滞后**
- Week 2结束时只完成了1个Analyzer
- 应对：人员C先基于完成的Analyzer开发Composite，其他用Mock

**场景2：Facade接口需要大改**
- Week 3发现接口设计问题
- 应对：人员A快速修改，人员B/C暂停等待（做文档/测试）

**场景3：Composite逻辑过于复杂**
- 无法实现预期的智能诊断
- 应对：MVP版本，先实现基础编排，智能诊断延后

---

## 4人方案（可选）

如果团队有4人，建议分工如下：

| 角色 | 人员 | 工作包调整 | 优势 |
|------|------|-----------|------|
| Core架构师 | A | 同3人方案 | 专注架构 |
| Analysis工程师 | B | 负责核心工具（comm_top, hotspots） | 深度专注 |
| Analysis工程师 | B2 | 负责其他工具（core_dist, anomalies等） | 并行加速 |
| Composite+QA | C | 同3人方案的C | 端到端负责 |

**调整内容**:
- Week 2-3: B和B2并行开发不同Analyzer
- 每日站会需要B和B2同步接口使用
- 代码Review需要交叉Review（B Review B2，B2 Review B）

---

## 附录

### 接口冻结清单

以下接口在Week 1结束后冻结，不再修改：

**Core Engine新增接口**:
- `get_process_lifecycle(samples, comm=None) -> ProcessLifecycle`
- `get_pid_cpu_distribution(samples, comm) -> Dict[int, float]`
- `get_call_graph(samples, target_symbol, comm=None) -> CallGraph`

**Analysis Facade接口**:
- `analyze_comm_top(samples, top_n=10, include_metrics=False) -> Dict`
- `analyze_hotspots(samples, comm=None, pid=None, top_n=20, sort_by="self") -> Dict`
- `analyze_core_distribution(samples, top_n=10) -> Dict`
- `detect_anomalies(samples, window_size=1.0, spike_threshold=0.5, min_utilization=0.3, cpu_id=None, top_n=10) -> Dict`
- `cluster_paths(samples, min_depth=2, min_samples=5, top_n=10, comm=None, pid=None) -> Dict`
- `cluster_symbols(samples, top_n=10, include_experts=True, rules_file=None, comm=None, pid=None) -> Dict`
- `count_process_variety(samples, top_n=20, storm_pid_threshold=50, storm_cpu_threshold=0.5, storm_ratio_threshold=2.0, comm=None) -> Dict`

### 测试数据需求

| 数据文件 | 用途 | 负责准备 |
|----------|------|----------|
| `test_many_small_procs.data` | 测试CV计算和降噪 | A |
| `test_single_bottleneck.data` | 测试Monopoly识别 | B |
| `test_process_storm.data` | 测试SpawnRate计算 | B |
| `test_dual_sys_pressure.data` | 测试Composite编排 | C |

### 文档清单

| 文档 | 责任人 | 截止时间 |
|------|--------|----------|
| Core接口文档 | A | Week 1 |
| Facade使用指南 | A | Week 2 |
| Analyzer开发规范 | B | Week 3 |
| Composite命令文档 | C | Week 5 |
| SKILL.md更新 | C | Week 5 |
| references/tools.md更新 | C | Week 5 |
