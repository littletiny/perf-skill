# perf-hunter 代码冗余分析与重构计划 (v2 - 极致简化版)

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

## 重构步骤

### Step 1: 创建 core/models.py

```python
# core/models.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class RiskInfo:
    level: str
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    source: str = ""
    
    @property
    def action_required(self) -> bool:
        return self.level in ("critical", "warning")
    
    @classmethod
    def from_risk_list(cls, risks: List["RiskInfo"]) -> "RiskInfo":
        if not risks:
            return cls(level="none")
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}
        return min(risks, key=lambda r: priority.get(r.level, 2))

@dataclass(frozen=True)
class TimeRange:
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_sec: float = 0.0
    
    @classmethod
    def from_samples(cls, samples: List) -> "TimeRange":
        if not samples or len(samples) < 2:
            return cls()
        return cls(
            datetime.fromtimestamp(samples[0].ts).isoformat(),
            datetime.fromtimestamp(samples[-1].ts).isoformat(),
            round(samples[-1].ts - samples[0].ts, 2)
        )

@dataclass
class Summary:
    total: int = 0
    shown: int = 0
```

### Step 2: 删除冗余定义

删除以下文件中的重复定义：
- [ ] `core/engine_types.py` - `RiskInfo`, `TimeRange`
- [ ] `core/output_models.py` - `RiskInfo`, `TimeRange`
- [ ] `analysis/models.py` - `Risk` 类
- [ ] `composite/models.py` - `RiskItem` 类
- [ ] 所有文件中的 `to_dict` 方法
- [ ] 所有文件中的 `from_dict` 方法（仅保留处理 JSON 的特殊情况）
- [ ] 所有 `from_analysis_*` 类方法

### Step 3: 更新 adapter

```python
# core/output_adapter.py
from dataclasses import asdict, is_dataclass
import json

def to_dict(obj):
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

def to_json(obj, compact=False):
    return json.dumps(to_dict(obj), indent=None if compact else 2, ensure_ascii=False)
```

### Step 4: 更新 import

```python
# 批量替换
from perf_toolkit.core.models import RiskInfo, TimeRange, Summary

# 删除旧 import
# from perf_toolkit.core.output_models import RiskInfo  # 删除
# from perf_toolkit.analysis.models import Risk  # 删除
# from perf_toolkit.composite.models import RiskItem  # 删除
```

### Step 5: 简化层间转换

在 `composite/sys_audit.py` 和 facade 中：
- 删除 `from_analysis_result` 调用
- 改为显式字段映射构造

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
