# bottleneck-trace 与 sys-audit 数值计算对齐

> 版本: 1.0  
> 日期: 2026-03-04

---

## 概述

本文档对比 `bottleneck-trace` 和 `sys-audit` 的数值计算逻辑，确保两者使用一致的阈值和计算方式。

---

## 阈值对比表

### 1. Monopoly 阈值

| 阈值用途 | sys-audit | bottleneck-trace | 状态 |
|----------|-----------|------------------|------|
| X0 标记 | `> Thresholds.MONOPOLY_HIGH (0.8)` | `> 0.8` | ✅ 一致 |
| Fixed 亲缘性 | 无 | `> 0.8` | N/A |
| 单核饱和检测 | 无直接检测 | `> 0.8` | ⚠️ 需对齐 |

**建议**: bottleneck-trace 使用 `Thresholds.MONOPOLY_HIGH` 常量。

### 2. CPU 利用率阈值

| 阈值用途 | sys-audit | bottleneck-trace | 状态 |
|----------|-----------|------------------|------|
| 高负载核心显示 | `> 50` (`_build_core_distribution`) | 无 | N/A |
| 节流推断 | 无 | `< 90` (throttle_rate) | 需确认 |
| 单核饱和 | 无 | `> 90` (设计中) | ⚠️ TODO |

**问题**: 
- bottleneck-trace 节流推断用 `< 90`，但设计文档说单核饱和需要 `> 90`
- **建议统一**: 使用 `Thresholds.CPU_UTIL_HIGH (80)` 或 `CPU_UTIL_CRITICAL (100)`

### 3. 内核态比例阈值

| 阈值用途 | sys-audit | bottleneck-trace | 状态 |
|----------|-----------|------------------|------|
| KERNEL_HEAVY flag | 无直接检测 | `> 50` | N/A |
| X1 标记 | 无 | 无 | - |

**建议**: 使用 `Thresholds.KERNEL_RATIO_HIGH (50)` 常量。

### 4. CV (变异系数) 阈值

| 阈值用途 | sys-audit | bottleneck-trace | 状态 |
|----------|-----------|------------------|------|
| Uniform 亲缘性 | 无 | `< 0.5` | N/A |
| UNBALANCED_LOAD | 无 | `> 1.5` | ⚠️ 不一致 |

**问题**: 
- `Thresholds.CV_UNBALANCED = 1.0`
- `Thresholds.CV_HIGH = 2.0`
- bottleneck-trace 用 `> 1.5`

**建议**: 使用 `Thresholds.CV_HIGH (2.0)` 或添加 `CV_UNBALANCED_LOAD = 1.5`

### 5. 其他阈值

| 阈值用途 | 当前值 | 建议值 | 状态 |
|----------|--------|--------|------|
| GLOBAL_LOCK_CONTENTION | `> 40` | 添加常量 `LOCK_CONTENTION_THRESHOLD = 40` | ⚠️ 硬编码 |
| THROTTLE_VICTIM (monopoly) | `> 0.8` | 使用 `MONOPOLY_HIGH` | ✅ 一致 |
| THROTTLE_VICTIM (cpu) | `< 80` | 使用 `CPU_UTIL_HIGH` | ⚠️ 不一致 |
| STORM_PATTERN | `> 100/s` | 添加常量 `STORM_RATE_THRESHOLD = 100` | ⚠️ 硬编码 |
| KERNEL_HEAVY | `> 50` | 使用 `KERNEL_RATIO_HIGH` | ✅ 一致 |
| UNBALANCED_LOAD | `> 1.5` | 添加常量 | ⚠️ 硬编码 |

---

## 计算逻辑对比

### 1. 内核比例计算

**sys-audit** (`sys_audit.py:364`):
```python
sys_ratio = (g.kernel_cpu / g.total_cpu * 100) if g.total_cpu > 0 else 0
```

**bottleneck-trace** (通过 `bottleneck_analysis.kernel_ratio`):
```python
# 来自 ProcessGroup.kernel_ratio 属性
return (self.kernel_cpu / self.total_cpu * 100) if self.total_cpu > 0 else 0
```

**状态**: ✅ 一致

### 2. Impact Score 计算

**sys-audit**: 由 `CommTopAnalyzer` 计算，考虑 Monopoly + CPU + CV

**bottleneck-trace**: 直接使用从 sys-audit 传递的值，或独立计算

**问题**: 如果 bottleneck-trace 独立计算，需要确保公式一致

**建议**: 统一使用 `CommTopAnalyzer` 的计算逻辑

### 3. Core Affinity 判定

**sys-audit**: 无直接输出（未来可扩展）

**bottleneck-trace** (`bottleneck_trace.py:62-67`):
```python
if bottleneck.monopoly > 0.8:
    core_affinity = "Fixed"
elif bottleneck.cv < 0.5:
    core_affinity = "Uniform"
else:
    core_affinity = "Scattered"
```

**与设计文档对比** (`tool-bottleneck-trace.md:142-144`):
- Fixed: Entropy < 0.3, Monopoly > 0.8
- Uniform: Entropy > 2.0, CV < 0.5
- Scattered: 其他

**问题**: 代码实现与设计文档不一致
- 代码用 Monopoly + CV
- 文档用 Entropy + Monopoly/CV

**建议**: 更新文档或代码，使其一致

### 4. Throttle Rate 计算

**bottleneck-trace** (`bottleneck_trace.py:71-72`):
```python
if bottleneck.monopoly > 0.8 and bottleneck.total_cpu < 90:
    throttle_rate = 100.0 - bottleneck.total_cpu
```

**问题**: 
- 只是推断，非真实节流率
- 阈值 `< 90` 无对应常量

**建议**: 使用 `Thresholds.CPU_UTIL_HIGH (80)` 或 `CPU_UTIL_CRITICAL (100)`

---

## 新增阈值常量建议

在 `config/defaults.py` 的 `Thresholds` 类中添加：

```python
@dataclass(frozen=True)
class Thresholds:
    # ... 现有阈值 ...
    
    # -------------------------------------------------------------------------
    # Correlation Flags Thresholds (bottleneck-trace)
    # -------------------------------------------------------------------------
    LOCK_CONTENTION_INCLUSIVE_PCT = 40.0   # GLOBAL_LOCK_CONTENTION 阈值
    THROTTLE_CPU_THRESHOLD = 80.0          # THROTTLE_VICTIM CPU 阈值
    STORM_SPAWN_RATE = 100.0               # STORM_PATTERN 产生速率阈值
    CV_UNBALANCED_LOAD = 1.5               # UNBALANCED_LOAD CV 阈值
    
    # -------------------------------------------------------------------------
    # Core Affinity Thresholds
    # -------------------------------------------------------------------------
    AFFINITY_CV_UNIFORM = 0.5              # Uniform 亲缘性 CV 阈值
```

---

## 代码修改清单

### TODO-1: 统一 Monopoly 阈值使用

**文件**: `cli/commands/composite/bottleneck_trace.py`

**修改**:
```python
# 当前
if bottleneck.monopoly > 0.8:

# 应改为
from config.defaults import Thresholds
if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
```

**行号**: 62, 71, 197, 206

### TODO-2: 统一 CV 阈值

**文件**: `cli/commands/composite/bottleneck_trace.py`

**选项 A**: 修改代码使用现有常量
```python
# 当前
elif bottleneck.cv < 0.5:
if bottleneck.cv > 1.5:

# 改为
elif bottleneck.cv < Thresholds.CV_UNBALANCED:  # 1.0
if bottleneck.cv > Thresholds.CV_HIGH:  # 2.0
```

**选项 B**: 添加新常量
```python
# 在 Thresholds 类中添加
CV_AFFINITY_UNIFORM = 0.5
CV_UNBALANCED_LOAD = 1.5
```

### TODO-3: 使用常量替代硬编码阈值

**文件**: `cli/commands/composite/bottleneck_trace.py`

**修改**:
```python
# 当前 (行 188)
if inclusive_pct > 40:

# 改为
if inclusive_pct > Thresholds.LOCK_CONTENTION_INCLUSIVE_PCT:

# 当前 (行 206)
if bottleneck.monopoly > 0.8 and bottleneck.total_cpu < 80:

# 改为
if (bottleneck.monopoly > Thresholds.MONOPOLY_HIGH and 
    bottleneck.total_cpu < Thresholds.THROTTLE_CPU_THRESHOLD):

# 当前 (行 216)
if bottleneck.diagnosis == DiagnosisType.STORM or bottleneck.spawn_rate > 100:

# 改为
if (bottleneck.diagnosis == DiagnosisType.STORM or 
    bottleneck.spawn_rate > Thresholds.STORM_SPAWN_RATE):

# 当前 (行 234)
if bottleneck.cv > 1.5 and bottleneck.monopoly < 0.5:

# 改为
if (bottleneck.cv > Thresholds.CV_UNBALANCED_LOAD and 
    bottleneck.monopoly < Thresholds.MONOPOLY_HIGH):
```

### TODO-4: 对齐单核饱和检测

**问题**: bottleneck-trace 缺少 CPU 利用率检查

**当前** (`bottleneck_trace.py:197`):
```python
# 2. SINGLE_CORE_SATURATION: Monopoly > 0.8
if bottleneck.monopoly > 0.8:
```

**建议修改**:
```python
# 2. SINGLE_CORE_SATURATION: Monopoly > 0.8
# Note: 完整的检测需要核心级数据，当前只能基于 Monopoly 推断
if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
```

**或** (如果有核心数据):
```python
# 需要 facade 提供核心级利用率
if (core_util > Thresholds.CPU_UTIL_HIGH and 
    bottleneck.monopoly > Thresholds.MONOPOLY_HIGH):
```

### TODO-5: 对齐 Core Affinity 判定

**选项 A**: 更新代码匹配文档
```python
# 需要实现 Entropy 计算
def calculate_entropy(distribution):
    # ... 熵计算逻辑
    pass

if entropy < 0.3 and monopoly > 0.8:
    return "Fixed"
elif entropy > 2.0 and cv < 0.5:
    return "Uniform"
else:
    return "Scattered"
```

**选项 B**: 更新文档匹配代码
修改 `tool-bottleneck-trace.md` 第 142-144 行，使用 Monopoly + CV 判定。

---

## 验证检查清单

- [ ] TODO-1: 所有 Monopoly > 0.8 改为使用 Thresholds.MONOPOLY_HIGH
- [ ] TODO-2: CV 阈值使用常量或添加新常量
- [ ] TODO-3: 所有硬编码阈值改为使用 Thresholds 常量
- [ ] TODO-4: 确认单核饱和检测逻辑（是否需要 CPU 利用率检查）
- [ ] TODO-5: Core Affinity 判定与文档一致
- [ ] 测试: 对比 sys-audit 和 bottleneck-trace 对相同数据的判断结果

---

## 相关文件

- `config/defaults.py` - 阈值常量定义
- `cli/commands/composite/bottleneck_trace.py` - 需要修改的代码
- `cli/commands/composite/sys_audit.py` - 参考实现
- `composite/models.py` - ProcessGroup 定义
- `report/tool-bottleneck-trace.md` - 设计文档
