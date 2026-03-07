# perf-hunter 代码冗余分析与重构计划

> 生成时间: 2026-03-03
> 核心原则: **不写 to_dict/from_dict，显式字段映射替代隐式转换**

---

## 核心原则

1. **不写 to_dict** - 用 `dataclasses.asdict()`，在 adapter 统一处理
2. **不写 from_dict** - JSON 反序列化直接用 `**kwargs` 解包，层间转换用显式字段映射
3. **不写 from_analysis_* 类方法** - facade 中直接构造，字段映射清晰可见
4. **统一 RiskInfo** - 全项目只有一个 Risk 类

---

## 问题详情与解决方案

### Category 1: 重复数据结构 (P0)

#### 1.1 RiskInfo 类重复定义

**位置**:
- `core/engine_types.py` (lines 386-412)
- `core/output_models.py` (lines 108-125)
- `analysis/models.py` (lines 14-28)
- `composite/models.py` (lines 18-82)

**简化方案 - 统一为单个类**:

```python
# core/models.py  (新建统一模型文件)
from dataclasses import dataclass, field
from typing import List

@dataclass
class RiskInfo:
    """统一的风险信息结构 - 全项目唯一来源"""
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    source: str = ""  # 追踪来源（如 "comm_top", "anomalies"）
    
    def __post_init__(self):
        if self.level not in ("critical", "warning", "info", "none"):
            self.level = "info"
    
    @property
    def action_required(self) -> bool:
        return self.level in ("critical", "warning")
    
    @classmethod
    def from_risk_list(cls, risks: List["RiskInfo"]) -> "RiskInfo":
        """从 risk 列表取最高级别（用于 CLI 输出）"""
        if not risks:
            return cls(level="none")
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        top = min(risks, key=lambda r: priority.get(r.level, 2))
        return top

# 删除以下重复定义：
# - output_models.py 中的 RiskInfo
# - analysis/models.py 中的 Risk  
# - composite/models.py 中的 RiskItem
# - engine_types.py 中的 RiskInfo
```

---

#### 1.2 TimeRange 重复定义

```python
# core/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass(frozen=True)
class TimeRange:
    start_time: Optional[str] = None  # ISO 8601
    end_time: Optional[str] = None
    duration_sec: float = 0.0
    
    @classmethod
    def from_samples(cls, samples: List) -> "TimeRange":
        if not samples or len(samples) < 2:
            return cls()
        start = datetime.fromtimestamp(samples[0].ts).isoformat()
        end = datetime.fromtimestamp(samples[-1].ts).isoformat()
        return cls(start, end, round(samples[-1].ts - samples[0].ts, 2))

# 删除 output_models.py 和 engine_types.py 中的重复定义
```

---

#### 1.3 Summary 类重复模式

```python
# core/models.py
from dataclasses import dataclass

@dataclass
class Summary:
    """通用摘要"""
    total: int = 0
    shown: int = 0

@dataclass  
class AnomalySummary(Summary):
    """异常摘要 - 继承扩展"""
    spike_count: int = 0
    drop_count: int = 0

# 删除 output_models.py 中空的 Summary 类
# 如 BottleneckSummary, CPUUsageSummary 直接用 Summary
```

---

### Category 2: 删除所有 to_dict/from_dict (P0)

#### 2.1 删除 to_dict

```python
# 删除这些代码：
def to_dict(self) -> Dict:
    return {"level": self.level, ...}

# 统一用 adapter:
# core/output_adapter.py
from dataclasses import asdict, is_dataclass
from typing import Any, Dict

def to_dict(obj: Any) -> Any:
    """递归转换为 dict，自动处理 dataclass"""
    if obj is None:
        return None
    if is_dataclass(obj):
        return {
            k: to_dict(v) 
            for k, v in asdict(obj).items() 
            if v is not None and v != [] and v != {}
        }
    if isinstance(obj, list):
        return [to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items() if v is not None}
    return obj
```

#### 2.2 删除 from_dict 和 from_analysis_*

```python
# 删除这些代码：
@classmethod
def from_dict(cls, d: Dict) -> "ProcessGroup":
    return cls(comm=d.get("comm"), ...)

@classmethod
def from_analysis_comm_group(cls, group) -> "ProcessGroup":
    return cls(comm=group.comm, ...)

# 替换方案:
# 1. JSON 反序列化直接用 **
config = Config(**json_data)

# 2. 层间转换用显式字段映射（在 facade/composite 中直接写）
composite_group = ProcessGroup(
    comm=analysis_group.comm,
    total_cpu=analysis_group.total_cpu,
    # 字段映射清晰可见
)
```

---

### Category 3: 层间转换模式

#### Analysis -> Composite 转换示例

```python
# composite/sys_audit.py
# ❌ 删除：不要用 from_analysis_result 类方法
report = CommTopReport.from_analysis_result(result)

# ✅ 改为：显式字段映射
groups = [
    ProcessGroup(
        comm=g.comm,
        total_cpu=g.total_cpu,
        kernel_cpu=g.kernel_cpu,
        cv=g.cv,
        monopoly=g.monopoly,
        diagnosis=g.diagnosis,
    )
    for g in result.groups
]

report = CommTopReport(
    groups=groups,
    risks=[RiskInfo(r.level, r.message, r.hint, source="comm_top") for r in result.risks],
    folded_count=result.folded_count,
    total_groups=result.total_groups,
)
```

---

### Category 4: CLI 命令简化

#### 简化前（50 行重复）

```python
@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(samples, top_n=args.top_n)
    
    for risk in result.risks:
        builder.record_risk(risk.level, risk.message, risk.hint)
    
    top_risk = None
    if result.risks:
        top_risk = min(result.risks, key=lambda r: priority[r.level])
    
    groups = [CommGroupItem.from_stats(...) for g in result.groups]
    
    return CommTopOutput(
        _risk=RiskInfo(...) if top_risk else RiskInfo(level="none"),
        comm_groups=groups,
        summary=CommGroupSummary(...)
    )
```

#### 简化后（20 行）

```python
@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    result = CommTopAnalyzer(engine).analyze(samples, top_n=args.top_n)
    
    builder.record_risks(result.risks)  # 封装到 builder
    
    return CommTopOutput(
        _risk=RiskInfo.from_risk_list(result.risks),
        comm_groups=[CommGroupItem(g.comm, g.pid_count, g.total_cpu) for g in result.groups],
        summary=Summary(total=result.total_groups, shown=len(result.groups))
    )
```

---

## 实施计划

### Phase 1: 基础结构统一 (Week 1)

**目标**: 统一 RiskInfo, TimeRange 等基础类型

**任务**:
1. [ ] 创建 `core/models.py`，定义统一的 `RiskInfo`、`TimeRange`、`Summary`
2. [ ] 删除 `core/engine_types.py` 中的 `RiskInfo`、`TimeRange`
3. [ ] 删除 `core/output_models.py` 中的 `RiskInfo`、`TimeRange`
4. [ ] 删除 `analysis/models.py` 中的 `Risk` 类
5. [ ] 删除 `composite/models.py` 中的 `RiskItem` 类
6. [ ] 更新所有 import 引用
7. [ ] 运行测试验证

**受影响文件**:
- 新增 `core/models.py`
- `core/engine_types.py` (删除)
- `core/output_models.py` (删除)
- `analysis/models.py` (修改)
- `composite/models.py` (修改)

---

### Phase 2: 删除 to_dict/from_dict (Week 2)

**目标**: 消除重复的数据转换逻辑

**任务**:
1. [ ] 创建 `core/output_adapter.py`，实现通用 `to_dict` 函数
2. [ ] 删除 `composite/models.py` 中所有 `to_dict` 方法
3. [ ] 删除 `analysis/models.py` 中所有 `to_dict` 方法
4. [ ] 删除所有 `from_dict` 方法（JSON 处理除外）
5. [ ] 运行测试验证

**受影响文件**:
- 新增 `core/output_adapter.py`
- `composite/models.py` (大量删除)
- `analysis/models.py` (中等删除)
- `core/output_models.py` (大量删除)

---

### Phase 3: 删除 from_analysis_* 类方法 (Week 3)

**目标**: 层间转换改为显式字段映射

**任务**:
1. [ ] 删除 `composite/models.py` 中所有 `from_analysis_*` 类方法
2. [ ] 在 `composite/sys_audit.py` 和 facade 中使用显式字段映射
3. [ ] 验证转换逻辑正确性
4. [ ] 运行测试验证

**受影响文件**:
- `composite/models.py` (大量删除)
- `composite/sys_audit.py` (修改)
- `cli/facade.py` (可能需要修改)

---

### Phase 4: CLI 命令简化 (Week 4)

**目标**: 消除 CLI 命令中的重复模式

**任务**:
1. [ ] 扩展 `OutputBuilder` 添加 `record_risks()` 方法
2. [ ] 重构一个命令作为试点（如 `get-comm-top`）
3. [ ] 验证模式正确性
4. [ ] 批量迁移其他命令（6个分析命令）

**受影响文件**:
- `cli/builders.py` (新增方法)
- `cli/commands/analysis/*.py` (大量修改)

---

### Phase 5: 命名规范化与清理 (Week 5)

**目标**: 统一字段命名规范，清理残留代码

**任务**:
1. [ ] 确定命名规范文档（原始值使用 `_pct` 后缀）
2. [ ] 统一字段命名（如 `total_cpu` -> `total_pct`）
3. [ ] 添加属性别名保持向后兼容
4. [ ] 清理空类定义（如 `BottleneckSummary` 直接用 `Summary`）
5. [ ] 更新文档
6. [ ] 全量回归测试

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

1. **单元测试**: 确保每个 dataclass 的构造正确
2. **集成测试**: 验证层间转换逻辑
3. **端到端测试**: 确保 CLI 命令输出格式不变
4. **回归测试**: 对比重构前后输出一致性

---

## 成功标准

- [ ] RiskInfo 定义唯一化
- [ ] TimeRange 定义唯一化
- [ ] 所有 Summary 类继承 SummaryBase
- [ ] 消除 100% 的手写 to_dict/from_dict
- [ ] 消除 100% 的 from_analysis_* 类方法
- [ ] 无裸 dict 在核心接口中使用
- [ ] 所有测试通过
- [ ] CLI 输出格式保持兼容

---

## 代码行数对比

| 文件/模块 | 当前 | 重构后 | 减少 |
|----------|------|-------|------|
| `output_models.py` | 1140 | ~600 | **47%** |
| `composite/models.py` | 948 | ~300 | **68%** |
| `analysis/models.py` | 307 | ~150 | **51%** |
| CLI 命令 (6个) | ~600 | ~300 | **50%** |
| **总计** | **~3000** | **~1350** | **55%** |

---

## 验证检查清单

- [ ] `grep -r "def to_dict" scripts/ | wc -l` == 0
- [ ] `grep -r "def from_dict" scripts/ | wc -l` == 0 (JSON 处理除外)
- [ ] `grep -r "from_analysis_" scripts/ | wc -l` == 0
- [ ] `grep -r "class Risk" scripts/ | grep -v RiskInfo | wc -l` == 0
- [ ] 所有测试通过
- [ ] JSON 输出格式保持不变

---

*极简原则：显式优于隐式，直接优于间接。*
