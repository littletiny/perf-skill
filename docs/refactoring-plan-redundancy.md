# perf-hunter 代码冗余分析与重构计划

> 生成时间: 2026-03-03
> 分析范围: `scripts/perf_toolkit/` 核心模块

---

## 执行摘要

经过代码结构分析，发现以下主要冗余问题：

| 类别 | 问题数量 | 影响程度 | 优先级 |
|------|---------|---------|--------|
| 重复数据结构 | 8 处 | 高 | P0 |
| 重复转换逻辑 | 12 处 | 高 | P0 |
| 裸 dict 使用 | 6 处 | 中 | P1 |
| 不一致命名 | 5 处 | 中 | P1 |

---

## 问题详情与解决方案

### Category 1: 重复数据结构 (P0)

#### 1.1 RiskInfo 类重复定义

**位置**:
- `core/engine_types.py` (lines 386-412)
- `core/output_models.py` (lines 108-125)
- `analysis/models.py` (lines 14-28)
- `composite/models.py` (lines 18-82) - RiskItem

**问题描述**:
同一个 Risk 概念在四个地方定义，字段几乎相同但命名和实现有细微差异：

```python
# engine_types.py
@dataclass
class RiskInfo:
    level: str
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False

# output_models.py - 类似但 patterns 默认值为 [] 而非 field(default_factory=list)
# analysis/models.py - Risk 类，同上
# composite/models.py - RiskItem，额外有 source 字段
```

**解决方案**:
1. **统一使用单一来源** - 在 `core/engine_types.py` 定义基础 `RiskInfo`
2. **其他层使用扩展** - Analysis 层和 Composite 层通过继承或组合扩展
3. **删除重复定义** - 从 `output_models.py` 和 `analysis/models.py` 删除

**代码变更**:
```python
# core/engine_types.py - 保留为基础定义
@dataclass
class RiskInfo:
    level: str
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False
    
    def __post_init__(self):
        valid_levels = ["critical", "warning", "info", "none"]
        if self.level not in valid_levels:
            self.level = "info"
        self.action_required = self.level in ["critical", "warning"]

# composite/models.py - 改为继承或组合
@dataclass
class RiskItem:
    """Composite 层 Risk，添加 source 字段"""
    risk: RiskInfo  # 组合而非继承
    source: str = ""  # 额外字段
```

**迁移步骤**:
1. [ ] 统一 `RiskInfo` 定义到 `core/engine_types.py`
2. [ ] 更新所有 import 引用
3. [ ] 删除 `output_models.py` 中的 `RiskInfo`
4. [ ] 更新 `analysis/models.py` 中的 `Risk` 为 `RiskInfo` 的别名
5. [ ] 修改 `composite/models.py` 的 `RiskItem` 使用组合
6. [ ] 运行测试验证

---

#### 1.2 TimeRange 类重复定义

**位置**:
- `core/engine_types.py` (lines 415-437)
- `core/output_models.py` (lines 131-148)

**问题描述**:
两个完全相同的 `TimeRange` 定义，仅 docstring 不同。

**解决方案**:
1. 保留 `core/engine_types.py` 的定义（frozen=True）
2. 删除 `output_models.py` 的重复定义
3. 更新 import 引用

**迁移步骤**:
1. [ ] 从 `output_models.py` 删除 `TimeRange` 类
2. [ ] 更新 `output_models.py` 的 import: `from ..engine_types import TimeRange`
3. [ ] 验证所有使用 TimeRange 的地方正常工作

---

#### 1.3 CPU Utilization 相关类分散定义

**位置**:
- `core/engine_types.py` - CPUUtilization, UserKernelStats, ProcessCPUInfo, PidCPUInfo, CommCPUInfo, CoreCPUInfo, SymbolCPUInfo
- `analysis/models.py` - 部分重复（CoreStat, CommGroup 等）
- `composite/models.py` - 部分重复（CoreStat, ProcessGroup 等）

**问题描述**:
CPU 相关信息在三层架构中都有定义，但职责不清晰：
- Core 层定义基础数据结构
- Analysis 层又定义 CoreStat（与 CoreCPUInfo 类似）
- Composite 层又定义 ProcessGroup（与 CommGroup 类似）

**解决方案**:
1. **Core 层保留基础类型** - `CPUUtilization`, `ProcessCPUInfo`, `CoreCPUInfo`, `SymbolCPUInfo`
2. **Analysis 层使用扩展类型** - Analysis 层定义带业务逻辑的类（如 `CommGroup` 包含 cv/monopoly/spawn_rate）
3. **Composite 层使用转换** - Composite 层通过 `from_analysis_*` 类方法转换
4. **删除重复字段的类** - 如 `analysis/models.py` 的 `CoreStat` 可以用 `CoreCPUInfo` 替代

**代码变更**:
```python
# analysis/models.py
# 删除 CoreStat，直接使用 CoreCPUInfo
from ..core.engine_types import CoreCPUInfo as CoreStat

# composite/models.py - ProcessGroup 保留，但字段对齐
@dataclass
class ProcessGroup:
    """从 CommGroup 转换而来，使用相同字段名"""
    comm: str
    total_cpu: float = 0.0  # 对齐: total_cpu -> total_pct 不一致！
    # ...
```

---

#### 1.4 Summary 类大量重复模式

**位置**:
- `core/output_models.py` (lines 154-256)

**问题描述**:
所有 Summary 类都有相同模式：
- `total_*` 和 `shown_*` 字段
- 空类定义（如 `BottleneckSummary`, `CPUUsageSummary`）

**代码统计**:
```
当前 Summary 类数量: 13 个
重复代码行数: ~200 行
共同字段: total/shown 模式重复 11 次
```

**解决方案**:
1. **创建基础 Summary 类** - 使用泛型或继承

```python
# 新设计
@dataclass
class SummaryBase:
    """所有 Summary 的基础类"""
    total: int = 0
    shown: int = 0

@dataclass  
class HotspotSummary(SummaryBase):
    """热点摘要 - 继承基础字段"""
    pass  # 如无额外字段，可直接使用 SummaryBase

@dataclass
class AnomalySummary(SummaryBase):
    """异常摘要 - 扩展基础字段"""
    spike_count: int = 0
    drop_count: int = 0
```

**迁移步骤**:
1. [ ] 创建 `SummaryBase` 类
2. [ ] 修改所有 Summary 类继承 `SummaryBase`
3. [ ] 更新字段引用 `total_hotspots` -> `total`
4. [ ] 验证模板配置兼容性（检查 `display_presets.py`）

---

### Category 2: 重复转换逻辑 (P0)

#### 2.1 from_dict / to_dict 方法重复

**位置**:
- `composite/models.py` - 几乎所有类都有 `from_dict` 和 `to_dict`
- `analysis/models.py` - StormGroupDetail, StormAnalysisResult, CommGroup

**问题描述**:
每个类都手写 `from_dict` 和 `to_dict`，代码重复且容易出错：

```python
# 重复模式（在 composite/models.py 中出现 15+ 次）
@classmethod
def from_dict(cls, d: Dict) -> 'SomeClass':
    return cls(
        field1=d.get("field1", default),
        field2=d.get("field2", default),
        # ...
    )

def to_dict(self) -> Dict:
    return {
        "field1": self.field1,
        "field2": self.field2,
        # ...
    }
```

**解决方案**:
1. **使用 dataclass 自带方法** - `dataclasses.asdict()` 和 `**kwargs` 解包
2. **创建通用 mixin** - 对于需要自定义逻辑的类

```python
# core/utils/dataclass_helpers.py
from dataclasses import asdict, fields
from typing import Dict, Any, Type, TypeVar

T = TypeVar('T')

class DictConvertible:
    """提供通用的 dict 转换能力"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict，自动跳过 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从 dict 创建实例，忽略未知字段"""
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

# 使用
@dataclass
class ProcessGroup(DictConvertible):
    comm: str
    total_cpu: float = 0.0
    # ...
```

**迁移步骤**:
1. [ ] 创建 `core/utils/dataclass_helpers.py`
2. [ ] 让需要通用转换的类继承 `DictConvertible`
3. [ ] 删除手写的 `from_dict` / `to_dict` 方法（保留需要自定义的）
4. [ ] 运行测试验证

---

#### 2.2 层间转换逻辑重复

**位置**:
- `composite/models.py` - 多个 `from_analysis_*` 方法

**问题描述**:
每个 `from_analysis_*` 方法都重复相同的模式：

```python
@classmethod
def from_analysis_result(cls, result: Any) -> 'SomeReport':
    items = [
        SomeItem.from_analysis_item(i)
        for i in result.items
    ]
    risks = [
        RiskItem.from_analysis_risk(r, source="xxx")
        for r in result.risks
    ]
    return cls(items=items, risks=risks, ...)
```

**代码统计**:
```
from_analysis_* 方法数量: 6 个
重复代码: ~120 行
```

**解决方案**:
1. **创建通用转换器** - 使用泛型和映射配置

```python
# composite/converters.py
from typing import TypeVar, Callable, List, Type, Any

T = TypeVar('T')
S = TypeVar('S')

def convert_list(items: List[S], converter: Callable[[S], T]) -> List[T]:
    """通用列表转换"""
    return [converter(i) for i in items]

def convert_risks(risks: List[Any], source: str) -> List[RiskItem]:
    """通用 risk 转换"""
    return [
        RiskItem.from_analysis_risk(r, source=source)
        for r in risks
    ]

# 简化后的转换方法
@classmethod
def from_analysis_result(cls, result: Any) -> 'HotspotsReport':
    return cls(
        hotspots=convert_list(result.hotspots, HotspotItem.from_analysis_hotspot),
        risks=convert_risks(result.risks, source="hotspots"),
        top_symbol=result.hotspots[0].symbol if result.hotspots else None,
        total_hotspots=len(result.hotspots),
        kernel_ratio=result.kernel_ratio,
        user_ratio=result.user_ratio
    )
```

---

#### 2.3 CLI 命令中的重复模式

**位置**:
- `cli/commands/analysis/*.py` - 所有分析命令

**问题描述**:
每个 CLI 命令都重复相同的 4 步模式：
1. 调用 Analyzer
2. 记录 risks 到 Trace
3. 取最高级别 risk
4. 转换为 Output 模型

**代码统计**:
```
分析命令数量: 6 个
重复代码: ~50 行/命令 × 6 = 300 行
```

**解决方案**:
1. **创建命令基类或装饰器** - 封装通用流程

```python
# cli/builders.py 扩展
class AnalysisCommandBuilder:
    """分析命令构建器 - 封装通用流程"""
    
    def __init__(self, builder: OutputBuilder, engine: PerfExpertEngine, args: Namespace):
        self.builder = builder
        self.engine = engine
        self.args = args
    
    def execute(
        self,
        analyzer: BaseAnalyzer,
        result_converter: Callable[[Any], BaseOutput],
        **analyze_kwargs
    ) -> BaseOutput:
        """执行分析命令的标准流程"""
        # 1. 调用 Analyzer
        result = analyzer.analyze(**analyze_kwargs)
        
        # 2. 记录 risks
        for risk in getattr(result, 'risks', []):
            self.builder.record_risk(risk.level, risk.message, risk.hint)
        
        # 3. 转换结果
        output = result_converter(result, self.builder, self.engine, self.args)
        
        return output
```

---

### Category 3: 裸 dict 使用 (P1)

#### 3.1 需要 Dataclass 化的 Dict

**位置与问题**:

| 位置 | 当前类型 | 建议类型 | 原因 |
|------|---------|---------|------|
| `output_builder.py:205` | `Dict` | `TraceSummary` | 已部分 dataclass 化，但返回 dict |
| `composite/models.py:754` | `List[Dict]` | `List[TimelineRecord]` | 类型不明确 |
| `composite/models.py:777` | `List[Dict]` | `List[ReopenRecord]` | 类型不明确 |
| `composite/sys_audit.py:296` | `Dict` | `SysAuditDetails` | 输出结构 |

**解决方案**:
1. 为所有裸 dict 创建对应的 dataclass
2. 更新函数签名和返回类型
3. 添加类型检查

---

### Category 4: 不一致命名 (P1)

#### 4.1 字段命名不一致

| 类/位置 | 字段名 | 建议统一为 | 影响 |
|---------|-------|-----------|------|
| `analysis/models.py:CommGroup` | `total_cpu` | `total_pct` | 与 Core 层不一致 |
| `analysis/models.py:Hotspot` | `self_pct` | `self_percent` | 缩写不统一 |
| `composite/models.py:ProcessGroup` | `total_cpu` | `total_pct` | 同上 |
| `output_models.py:HotspotItem` | `self` | `self_pct` | 字符串 vs 原始值 |

**解决方案**:
1. 统一命名规范:
   - 原始值使用 `_pct` 后缀（如 `total_pct`, `self_pct`）
   - 字符串格式化值使用 `_str` 后缀或不加（如 `cpu="15.5%"`）
2. 添加属性别名保持向后兼容

```python
@dataclass
class CommGroup:
    total_pct: float = 0.0  # 新命名
    
    @property
    def total_cpu(self) -> float:
        """向后兼容别名"""
        return self.total_pct
```

---

## 重构实施计划

### Phase 1: 基础结构统一 (Week 1)

**目标**: 统一 RiskInfo, TimeRange 等基础类型

**任务**:
1. [ ] 统一 `RiskInfo` 定义到 `core/engine_types.py`
2. [ ] 删除 `output_models.py` 的 `TimeRange` 重复定义
3. [ ] 更新所有 import 引用
4. [ ] 运行测试验证

**受影响文件**:
- `core/engine_types.py` (修改)
- `core/output_models.py` (删除)
- `analysis/models.py` (修改)
- `composite/models.py` (修改)

---

### Phase 2: 转换逻辑抽象 (Week 2)

**目标**: 消除重复的数据转换逻辑

**任务**:
1. [ ] 创建 `core/utils/dataclass_helpers.py`
2. [ ] 实现 `DictConvertible` mixin
3. [ ] 创建 `composite/converters.py`
4. [ ] 迁移所有类使用新的转换方法
5. [ ] 删除手写的 `from_dict` / `to_dict`

**受影响文件**:
- `composite/models.py` (大量修改)
- `analysis/models.py` (中等修改)
- 新增 `core/utils/dataclass_helpers.py`
- 新增 `composite/converters.py`

---

### Phase 3: Summary 类重构 (Week 3)

**目标**: 统一 Summary 类的定义模式

**任务**:
1. [ ] 创建 `SummaryBase` 基础类
2. [ ] 重构所有 Summary 类继承基础类
3. [ ] 更新 `display_presets.py` 的字段引用
4. [ ] 验证模板配置兼容性

**受影响文件**:
- `core/output_models.py` (大量修改)
- `core/display_presets.py` (可能需要修改)
- `cli/` 中的模板配置 (可能需要修改)

---

### Phase 4: CLI 命令抽象 (Week 4)

**目标**: 消除 CLI 命令中的重复模式

**任务**:
1. [ ] 设计 `AnalysisCommandBuilder`
2. [ ] 重构一个命令作为试点
3. [ ] 验证模式正确性
4. [ ] 批量迁移其他命令

**受影响文件**:
- `cli/builders.py` (新增)
- `cli/commands/analysis/*.py` (大量修改)

---

### Phase 5: 命名规范化 (Week 5)

**目标**: 统一字段命名规范

**任务**:
1. [ ] 确定命名规范文档
2. [ ] 添加属性别名保持兼容
3. [ ] 逐步迁移内部使用
4. [ ] 更新文档

**受影响文件**:
- `analysis/models.py`
- `composite/models.py`
- `core/output_models.py`

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 破坏现有 API | 中 | 高 | 添加向后兼容别名，分阶段迁移 |
| 测试覆盖率不足 | 中 | 中 | 确保重构前测试覆盖 80%+ |
| 性能下降 | 低 | 低 | dataclass 性能优于 dict，基本无影响 |
| 引入新 Bug | 中 | 中 | 小步提交，每阶段充分测试 |

---

## 测试策略

1. **单元测试**: 确保每个 dataclass 的 from_dict/to_dict 正确
2. **集成测试**: 验证层间转换逻辑
3. **端到端测试**: 确保 CLI 命令输出格式不变
4. **回归测试**: 对比重构前后输出一致性

---

## 成功标准

- [ ] RiskInfo 定义唯一化
- [ ] TimeRange 定义唯一化
- [ ] 所有 Summary 类继承 SummaryBase
- [ ] 消除 80% 的手写 from_dict/to_dict
- [ ] 无裸 dict 在核心接口中使用
- [ ] 所有测试通过
- [ ] CLI 输出格式保持兼容

---

## 附录: 重复代码统计

### A.1 按文件统计

| 文件 | 总行数 | 可删除重复代码 | 重复率 |
|------|-------|--------------|-------|
| `core/output_models.py` | 1140 | 180 | 16% |
| `composite/models.py` | 948 | 280 | 30% |
| `analysis/models.py` | 307 | 60 | 20% |
| `cli/commands/analysis/*.py` | ~600 | 300 | 50% |

### A.2 按类别统计

| 类别 | 重复代码行数 | 预计减少行数 |
|------|-------------|-------------|
| 重复类定义 | 200 | 200 |
| 重复转换方法 | 350 | 280 |
| 重复 CLI 模式 | 300 | 250 |
| 重复字段模式 | 150 | 100 |
| **总计** | **1000** | **830** |

---

*本文档应随着重构进展持续更新。*
