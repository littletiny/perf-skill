# 跨层接口一致性检查报告

> 生成日期: 2026-03-03
> 检查范围: Core / Analysis / Composite / CLI 四层接口文档

---

## 1. 一致性检查汇总表

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **类型名称** | ⚠️ 部分不一致 | `Sample` vs `Dict`, `RiskInfo` vs `Risk` vs `RiskItem` |
| **方法签名** | ❌ 不一致 | `analyze()` 参数类型 `List[Dict]` vs `List[Sample]` |
| **字段名称** | ⚠️ 部分不一致 | CPU 字段 `total_pct` vs `total_cpu`, 时间字段 `start_time` vs `time_range_start` |
| **Risk 结构** | ✅ 基本一致 | 核心字段一致，Composite 层多 `source` 字段 |
| **BaseOutput 定义** | ✅ 一致 | 仅在 Core 层定义，其他层引用 |
| **AggregatedRisk 定义** | ✅ 已定义 | 在 Composite 层定义，使用位置正确 |
| **跨层数据流** | ⚠️ 存在类型转换问题 | `Sample` → `Dict` 隐式转换未明确 |
| **缺失接口** | ❌ 存在 | `AnalysisResult` 基类未定义，部分类型未导出 |

**图例**: ✅ 一致 | ⚠️ 部分问题 | ❌ 严重不一致

---

## 2. 发现的问题列表

### 问题 1: Sample 类型不一致

**位置**: 
- `interface-core.md` 第 2.3 节
- `interface-analysis.md` 第 2.1 节、第 6.3 节
- `interface-composite.md` 第 5.1 节
- `interface-cli.md` 第 2 节

**问题**: 
- Core 层输出 `List[Sample]` (强类型 dataclass)
- Analysis 层 `BaseAnalyzer.analyze()` 声明为 `List[Dict]` (第 4.1 节)
- Analysis 层 Facade 接口声明为 `List[Dict]` (第 5.2 节)
- Composite 层 `SysAuditor.audit()` 声明为 `List[Dict]` (第 5.1 节)
- CLI 层声明为 `List[Dict[str, Any]]` (第 2 节)

**影响**: 跨层数据流类型不明确，运行时可能出现类型错误。

**建议修复**:
```python
# 统一使用 Sample 类型，兼容现有实现

# interface-analysis.md 修改:
class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, samples: Union[List[Sample], List[Dict]], **kwargs) -> Any:
        """
        执行分析
        
        Args:
            samples: 样本数据列表（Sample 对象列表或兼容的 Dict 列表）
            **kwargs: 分析特定参数
            
        Returns:
            具体 Result dataclass
        """
        pass

# 或者分阶段演进（推荐）:
# 阶段1: 标注为兼容类型
SampleInput = Union[List[Sample], List[Dict]]

# 阶段2: 逐步迁移后统一为 List[Sample]
```

---

### 问题 2: Risk 类型名称不统一

**位置**:
- `interface-core.md` 第 2.6 节: `RiskInfo`
- `interface-analysis.md` 第 2.2 节: `Risk`
- `interface-composite.md` 第 2.1 节: `RiskItem`

**问题**: 同一概念在不同层使用不同名称，容易造成混淆。

**影响**: 开发者需要记住三层不同的 Risk 类型名，增加心智负担。

**建议修复**:
```python
# 在文档中明确说明映射关系，或统一命名

# 方案1: 文档明确（推荐，保持当前实现）
# Core 层: RiskInfo    - 基础风险结构
# Analysis 层: Risk    - 分析器风险结构
# Composite 层: RiskItem - 聚合层风险结构

# 方案2: 统一命名
# 全部改为 RiskInfo，通过命名空间区分
```

---

### 问题 3: CPU 利用率字段名不一致

**位置**:
- `interface-core.md` 第 2.2 节: `CPUUtilization.total_pct`, `user_pct`, `kernel_pct`
- `interface-analysis.md` 第 3.2 节: `CommGroup.total_cpu`, `kernel_cpu`, `user_cpu`
- `interface-analysis.md` 第 3.3 节: `CoreStat.total_cpu`, `kernel_cpu`, `user_cpu`
- `interface-composite.md` 第 2.2 节: `ProcessGroup.total_cpu`, `kernel_cpu`, `user_cpu`

**问题**: 
- Core 层使用 `_pct` 后缀（表示百分比）
- Analysis 和 Composite 层使用 `_cpu` 后缀

**影响**: 跨层转换时字段名映射容易出错。

**建议修复**:
```python
# 建议统一使用 _pct 后缀，语义更明确

# Analysis 层修改:
@dataclass
class CommGroup:
    comm: str
    total_pct: float    # 原为 total_cpu
    kernel_pct: float   # 原为 kernel_cpu
    user_pct: float     # 原为 user_cpu
    # ...

# 或者 Core 层改为 _cpu 后缀，保持一致
```

---

### 问题 4: 时间范围字段名不一致

**位置**:
- `interface-core.md` 第 2.6 节: `TimeRange.start_time`, `end_time`
- `interface-analysis.md` 第 3.1 节: `Anomaly.time_range_start`, `time_range_end`
- `interface-analysis.md` 第 2.1 节: `Sample.ts` (float 时间戳)

**问题**:
- Core 层 `TimeRange` 使用 `start_time/end_time` (ISO 8601 字符串)
- Analysis 层 `Anomaly` 使用 `time_range_start/time_range_end` (ISO 8601 字符串)
- 但 `Sample.ts` 使用 float 时间戳

**影响**: 时间类型混用，转换逻辑复杂。

**建议修复**:
```python
# 统一时间字段命名

# Anomaly 修改:
@dataclass
class Anomaly:
    type: str
    cpu_id: int
    start_time: str       # 原为 time_range_start
    end_time: str         # 原为 time_range_end
    prev_util: float
    curr_util: float
    next_util: float
    z_score: float
```

---

### 问题 5: CallerInfo 类型重复定义

**位置**:
- `interface-core.md` 第 2.5 节: `CallerInfo`
- `interface-composite.md` 第 2.5 节: `CallerInfo`

**问题**: 两个 `CallerInfo` 定义结构不同但名称相同，容易产生命名冲突。

**Core 层 CallerInfo**:
```python
@dataclass(frozen=True)
class CallerInfo:
    symbol: str
    call_count: int
    total_weight: float
    call_ratio: float = 0.0
```

**Composite 层 CallerInfo**:
```python
@dataclass
class CallerInfo:
    symbol: str
    call_count: int = 0
    call_ratio: float = 0.0
    total_weight: float = 0.0
```

**影响**: 命名冲突，IDE 提示混乱，开发者容易混淆。

**建议修复**:
```python
# Composite 层改名为 CompositeCallerInfo 或 CallerAttributionItem

@dataclass
class CallerAttributionItem:  # 改名
    """调用者信息（从 CallerAttribution 转换）"""
    symbol: str
    call_count: int = 0
    call_ratio: float = 0.0
    total_weight: float = 0.0
```

---

### 问题 6: AnalysisResult 基类缺失

**位置**:
- `interface-analysis.md` 第 4.1 节引用 `AnalysisResult`
- 但未在任何位置定义 `AnalysisResult`

**问题**: `BaseAnalyzer` 导入 `AnalysisResult` 但未定义。

```python
# interface-analysis.md 第 4.1 节
from .models import Risk, AnalysisResult  # AnalysisResult 未定义
```

**影响**: 接口不完整，类型检查失败。

**建议修复**:
```python
# 在 interface-analysis.md 第 3 节添加 AnalysisResult 基类定义

@dataclass
class AnalysisResult:
    """分析结果基类"""
    risks: List[Risk] = field(default_factory=list)
```

---

### 问题 7: CommGroup.pids 类型不一致

**位置**:
- `interface-analysis.md` 第 3.2 节: `CommGroup.pids: List[int]`
- `interface-core.md` 第 2.2 节: `CommCPUInfo.pids: Set[str]`
- `interface-composite.md` 第 2.2 节: `ProcessGroup.pids: List[int]`

**问题**:
- Core 层: `Set[str]` (字符串集合)
- Analysis 层: `List[int]` (整数列表)
- Composite 层: `List[int]` (整数列表)

**影响**: 类型转换时可能出错。

**建议修复**:
```python
# Core 层修改为 List[int]，与其他层一致
@dataclass(frozen=True)
class CommCPUInfo:
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    pid_count: int
    pids: List[int] = field(default_factory=list)  # 原为 Set[str]
```

---

### 问题 8: Hotspot 字段映射不一致

**位置**:
- `interface-analysis.md` 第 3.4 节: `Hotspot.self_pct`, `inclusive_pct`
- `interface-composite.md` 第 2.4 节: `HotspotItem.cpu_percent`, `inclusive_percent`

**问题**: `self_pct` 映射为 `cpu_percent`，命名不直观。

**影响**: 字段映射关系不清晰。

**建议修复**:
```python
# Composite 层修改为更明确的命名
@dataclass
class HotspotItem:
    symbol: str
    self_pct: float              # 原为 cpu_percent
    inclusive_pct: float = 0.0   # 原为 inclusive_percent
    call_count: int = 0
    resource_tag: str = "COMPUTE"
```

---

## 3. 跨层数据流验证

### 3.1 数据流类型传递验证

```
Sample[Core] → analyze_comm_top() → CommTopResult[Analysis] 
    │                    │                      │
    │                    ▼                      ▼
List[Dict]???  facade.analyze_comm_top()  CommGroup(groups)
    │                    │                      │
    ▼                    ▼                      ▼
from_analysis_comm_group() → ProcessGroup[Composite]
         │                              │
         ▼                              ▼
    参数: group(CommGroup)     SysAuditor.audit()输入
         │                              │
         ▼                              ▼
DiagnosisReport[Composite] → OutputBuilder.print_output() → JSON/Text[CLI]
         │                              │
         ▼                              ▼
primary_suspect: ProcessGroup    输入: output(BaseOutput)
```

### 3.2 验证结果

| 步骤 | 从 | 到 | 类型匹配 | 备注 |
|------|-----|-----|----------|------|
| 1 | Core.Sample | Analysis.samples | ⚠️ | Core 输出 `List[Sample]`，Analysis 期望 `List[Dict]` |
| 2 | Analysis.CommTopResult | Composite.ProcessGroup | ✅ | 通过 `from_analysis_comm_group()` 转换 |
| 3 | Composite.ProcessGroup | Composite.DiagnosisReport | ✅ | 直接使用 |
| 4 | Composite.DiagnosisReport | CLI.OutputBuilder | ✅ | 通过 `BaseOutput` 子类 |
| 5 | CLI.BaseOutput | JSON/Text | ✅ | 通过 Adapter 渲染 |

### 3.3 数据流问题汇总

**主要问题**: Core → Analysis 层的类型转换未明确

```python
# 当前隐含逻辑（未文档化）:
samples = engine.get_all_samples()  # List[Sample]
# 需要转换为 List[Dict] 才能传给 Analysis
samples_dict = [s.__dict__ for s in samples]  # ???

# 或者 Analysis 层实际上接收的是 List[Sample] 但声明为 List[Dict]
```

**建议**: 在文档中明确类型转换策略，或统一使用 `List[Sample]`。

---

## 4. 统一接口索引

### 4.1 接口定义位置速查表

| 类型/接口 | 定义位置 | 引用位置 | 说明 |
|-----------|----------|----------|------|
| **基础类型** | | | |
| `Sample` | `interface-core.md` 2.3 | Analysis, Composite, CLI | 基础数据单元 |
| `RiskInfo` | `interface-core.md` 2.6 | CLI (通过 BaseOutput) | Core 层 Risk 结构 |
| `Risk` | `interface-analysis.md` 2.2 | Composite (转换为 RiskItem) | Analysis 层 Risk 结构 |
| `RiskItem` | `interface-composite.md` 2.1 | Composite 内部使用 | Composite 层 Risk 结构 |
| `TimeRange` | `interface-core.md` 2.6 | CLI (通过 BaseOutput) | 时间范围 |
| **CPU 信息** | | | |
| `CPUUtilization` | `interface-core.md` 2.2 | Core 内部 | 整体 CPU 利用率 |
| `CoreCPUInfo` | `interface-core.md` 2.2 | Core 输出 | 核心级 CPU |
| `CommCPUInfo` | `interface-core.md` 2.2 | Core 输出 | 进程组级 CPU |
| `PidCPUInfo` | `interface-core.md` 2.2 | Core 输出 | PID 级 CPU |
| `ProcessCPUInfo` | `interface-core.md` 2.2 | Core 输出 | 进程级 CPU |
| **Analysis 层** | | | |
| `CommGroup` | `interface-analysis.md` 3.2 | Composite 输入 | 进程组数据 |
| `CommTopResult` | `interface-analysis.md` 3.2 | Composite 输入 | 进程组分析结果 |
| `Anomaly` | `interface-analysis.md` 3.1 | Composite 输入 | 异常事件 |
| `AnomaliesResult` | `interface-analysis.md` 3.1 | Composite 输入 | 异常检测结果 |
| `Hotspot` | `interface-analysis.md` 3.4 | Composite 输入 | 热点函数 |
| `HotspotsResult` | `interface-analysis.md` 3.4 | Composite 输入 | 热点分析结果 |
| `CoreStat` | `interface-analysis.md` 3.3 | Composite 输入 | 核心统计 |
| `CoreDistributionResult` | `interface-analysis.md` 3.3 | Composite 输入 | 核心分布结果 |
| `CallerAttribution` | `interface-analysis.md` 3.6 | Composite 输入 | 调用归因 |
| `CallersResult` | `interface-analysis.md` 3.6 | Composite 输入 | 调用链结果 |
| **Composite 层** | | | |
| `ProcessGroup` | `interface-composite.md` 2.2 | DiagnosisReport | 进程组内部表示 |
| `DiagnosisReport` | `interface-composite.md` 3.1 | SysAuditor 输出 | 综合诊断报告 |
| `RiskAggregator` | `interface-composite.md` 4 | SysAuditor 使用 | Risk 聚合器 |
| `AggregatedRisk` | `interface-composite.md` 4.1 | RiskAggregator 输出 | 聚合 Risk |
| **CLI 层** | | | |
| `BaseOutput` | `interface-core.md` 2.8 | CLI 所有输出 | 输出基类 |
| `OutputBuilder` | `interface-core.md` 4 | CLI 命令使用 | 输出构建器 |
| `AnalysisCommandHandler` | `interface-cli.md` 2.1 | 命令注册 | 分析命令处理器类型 |
| `CompositeCommandHandler` | `interface-cli.md` 2.2 | 命令注册 | 组合命令处理器类型 |
| `@command` | `interface-cli.md` 4 | 命令装饰 | 命令装饰器 |

### 4.2 接口快速查找图

```
┌─────────────────────────────────────────────────────────────────┐
│  Core Layer (interface-core.md)                                 │
│  ├── 基础类型: Sample, RiskInfo, TimeRange                      │
│  ├── CPU 类型: CPUUtilization, *CPUInfo                         │
│  ├── 调用图: CallGraph, CallerInfo (Core版)                     │
│  └── 输出: BaseOutput, OutputBuilder                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ get_all_samples(): List[Sample]
                           │ get_filtered_samples(): List[Sample]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Analysis Layer (interface-analysis.md)                         │
│  ├── Risk: Risk (需改为 RiskInfo?)                              │
│  ├── 输入: Sample (声明为 Dict)                                 │
│  ├── 结果: *Result (CommTopResult, AnomaliesResult...)          │
│  ├── 条目: CommGroup, Hotspot, Anomaly...                       │
│  ├── 调用: CallerAttribution (注意: 不是 CallerInfo)            │
│  ├── 基类: BaseAnalyzer (引用未定义的 AnalysisResult)           │
│  └── 入口: AnalysisFacade                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ analyze_*(): *Result
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Composite Layer (interface-composite.md)                       │
│  ├── Risk: RiskItem (from Risk)                                 │
│  ├── 进程组: ProcessGroup (from CommGroup)                      │
│  ├── 热点: HotspotItem (from Hotspot)                           │
│  ├── 调用者: CallerInfo (Composite版，注意命名冲突!)            │
│  ├── 报告: DiagnosisReport, *Report                             │
│  ├── 聚合: RiskAggregator → AggregatedRisk                      │
│  └── 诊断器: SysAuditor, BottleneckTracer                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ audit(): DiagnosisReport
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLI Layer (interface-cli.md)                                   │
│  ├── 处理器: AnalysisCommandHandler                             │
│  ├── 装饰器: @command                                           │
│  ├── 输出: BaseOutput 子类                                      │
│  └── 渲染: OutputBuilder.print_output()                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 修复优先级建议

| 优先级 | 问题 | 原因 |
|--------|------|------|
| **P0 (高)** | 问题 1: Sample 类型不一致 | 影响数据流正确性 |
| **P0 (高)** | 问题 5: CallerInfo 命名冲突 | 可能导致编译/运行时错误 |
| **P1 (中)** | 问题 3: CPU 字段名不一致 | 增加维护成本 |
| **P1 (中)** | 问题 4: 时间字段名不一致 | 影响可读性 |
| **P1 (中)** | 问题 6: AnalysisResult 缺失 | 接口不完整 |
| **P2 (低)** | 问题 2: Risk 类型名不一致 | 可通过文档说明 |
| **P2 (低)** | 问题 7: pids 类型不一致 | 边界情况 |
| **P2 (低)** | 问题 8: Hotspot 字段映射 | 语义问题 |

---

## 6. 结论

### 6.1 整体评估

- **接口设计**: 整体架构清晰，三层分离合理
- **类型安全**: 大部分接口使用 dataclass，类型安全较好
- **主要问题**: Sample 类型传递不明确，存在命名冲突
- **数据流**: 跨层数据流基本正确，类型转换需要明确

### 6.2 建议行动

1. **立即修复 (P0)**:
   - 明确 Sample 类型在各层的使用方式
   - 解决 CallerInfo 命名冲突

2. **短期修复 (P1)**:
   - 统一 CPU 和时间字段命名
   - 补充 AnalysisResult 定义

3. **长期优化 (P2)**:
   - 统一 Risk 类型命名（可选）
   - 完善类型转换文档

---

## 附录: 类型转换参考

### Analysis → Composite 类型转换速查表

| Analysis 类型 | Composite 类型 | 转换方法 | 字段映射注意事项 |
|--------------|----------------|----------|------------------|
| `Risk` | `RiskItem` | `from_analysis_risk(risk, source)` | source 字段新增 |
| `CommGroup` | `ProcessGroup` | `from_analysis_comm_group(group)` | pids 类型需转换 |
| `Anomaly` | `AnomalyItem` | `from_analysis_anomaly(anomaly)` | time_range_start → timestamp |
| `Hotspot` | `HotspotItem` | `from_analysis_hotspot(hotspot, tag)` | self_pct → cpu_percent |
| `CallerAttribution` | `CallerInfo` | `from_analysis_caller(caller)` | 注意命名冲突 |
| `CommTopResult` | `CommTopReport` | `from_analysis_result(result)` | 批量转换 |
| `AnomaliesResult` | `AnomaliesReport` | `from_analysis_result(result)` | 批量转换 |
| `HotspotsResult` | `HotspotsReport` | `from_analysis_result(result)` | 批量转换 |
| `CallersResult` | `CallersReport` | `from_analysis_result(result)` | 批量转换 |

### Core → Analysis 类型转换速查表

| Core 类型 | Analysis 使用 | 说明 |
|-----------|---------------|------|
| `Sample` | `List[Sample]` / `List[Dict]` | 需要明确类型 |
| `RiskInfo` | 转为 `Risk` | 字段名一致 |
| `TimeRange` | 按需使用 | 格式 ISO 8601 |
| `CommCPUInfo` | 转为 `CommGroup` | 字段名不同 |

---

*报告完成*
