# bottleneck-trace 与 sys-audit 最终对齐方案

> 版本: 1.0 (Final)  
> 日期: 2026-03-04  
> 目标: 零硬编码，全配置驱动

---

## 核心原则

1. **单一真相源**: 所有阈值、字符串、格式统一在 `config/defaults.py`
2. **Event 命名统一**: 所有诊断类型、标志、事件名从配置获取
3. **代码零硬编码**: 业务逻辑代码中不出现任何字面量

---

## 第一部分: Event 命名统一

### 当前问题

```python
# comm_top.py 硬编码
SPAWN_RATE_THRESHOLD = 10.0  # 硬编码
SIGNIFICANT_SPAWN_RATE_THRESHOLD = 10.0  # 重复硬编码

# bottleneck_trace.py 硬编码
event = f"{DiagnosisType.BOTTLENECK}(M={g.monopoly:.4f})"  # 格式硬编码
event = f"{DiagnosisType.STORM}({g.spawn_rate:.1f}/s)"     # 格式硬编码
event = f"{DiagnosisType.UNBALANCED}(CV={g.cv:.4f})"       # 格式硬编码

# 检测逻辑硬编码
if bottleneck.diagnosis == DiagnosisType.STORM or bottleneck.spawn_rate > 100:
```

### 最终方案: EventConfig 配置类

```python
# config/defaults.py

@dataclass(frozen=True)
class EventConfig:
    """Event 配置 - 统一事件命名和格式"""
    
    # Event 类型标识
    BOTTLENECK_MARKER = "M"           # Monopoly 标记
    STORM_MARKER = "RATE"             # Spawn rate 标记  
    UNBALANCED_MARKER = "CV"          # CV 标记
    
    # Event 格式模板
    BOTTLENECK_FORMAT = "{type}({marker}={value:.4f})"
    STORM_FORMAT = "{type}({value:.1f}/s)"
    UNBALANCED_FORMAT = "{type}({marker}={value:.4f})"
    NORMAL_FORMAT = "normal"
    
    # Event 检测配置
    STORM_RATE_THRESHOLD = 100.0      # 风暴速率阈值 (/s)
    STORM_RATE_DISPLAY_UNIT = "/s"    # 显示单位


@dataclass(frozen=True)
class DiagnosisThresholds:
    """诊断阈值配置"""
    
    # Monopoly 诊断
    BOTTLENECK_MONOPOLY_MIN = 0.8
    
    # Storm 诊断  
    STORM_RATE_MIN = 100.0            # 与 EventConfig.STORM_RATE_THRESHOLD 一致
    STORM_PID_COUNT_MIN = 1000        # 进程数阈值
    
    # Unbalanced 诊断
    UNBALANCED_CV_MIN = 1.0
```

### 重构后的代码

```python
# comm_top.py
from config.defaults import EventConfig, DiagnosisThresholds

class CommTopAnalyzer:
    # 使用配置替代硬编码
    SPAWN_RATE_THRESHOLD = DiagnosisThresholds.STORM_RATE_MIN
    
    def _format_event(self, diagnosis: str, **kwargs) -> str:
        """统一 event 格式化"""
        if diagnosis == DiagnosisType.BOTTLENECK:
            return EventConfig.BOTTLENECK_FORMAT.format(
                type=diagnosis,
                marker=EventConfig.BOTTLENECK_MARKER,
                value=kwargs.get('monopoly', 0)
            )
        elif diagnosis == DiagnosisType.STORM:
            return EventConfig.STORM_FORMAT.format(
                type=diagnosis,
                value=kwargs.get('spawn_rate', 0)
            )
        elif diagnosis == DiagnosisType.UNBALANCED:
            return EventConfig.UNBALANCED_FORMAT.format(
                type=diagnosis,
                marker=EventConfig.UNBALANCED_MARKER,
                value=kwargs.get('cv', 0)
            )
        return EventConfig.NORMAL_FORMAT


# bottleneck_trace.py
from config.defaults import EventConfig, DiagnosisThresholds

def _detect_correlation_flags(bottleneck, hotspots_report, callers_report):
    # STORM_PATTERN 检测使用配置
    if (bottleneck.diagnosis == DiagnosisType.STORM or 
        bottleneck.spawn_rate > DiagnosisThresholds.STORM_RATE_MIN):
        flags.append(CorrelationFlag(
            flag_type=RiskPattern.STORM_PATTERN,
            ...
        ))
```

---

## 第二部分: 阈值配置全集

### 现有 Thresholds 类扩展

```python
# config/defaults.py

@dataclass(frozen=True)
class Thresholds:
    """统一阈值配置 - 所有数值从此获取"""
    
    # ==========================================================================
    # Monopoly 相关
    # ==========================================================================
    MONOPOLY_HIGH = 0.8
    MONOPOLY_CRITICAL = 0.9
    
    # ==========================================================================
    # CV (变异系数) 相关
    # ==========================================================================
    CV_UNBALANCED = 1.0
    CV_HIGH = 2.0
    CV_AFFINITY_UNIFORM = 0.5         # Core Affinity: Uniform
    CV_UNBALANCED_LOAD = 1.5          # UNBALANCED_LOAD flag
    
    # ==========================================================================
    # CPU 利用率相关
    # ==========================================================================
    CPU_UTIL_LOW = 30.0
    CPU_UTIL_MEDIUM = 50.0
    CPU_UTIL_HIGH = 80.0
    CPU_UTIL_CRITICAL = 100.0
    CPU_UTIL_EXTREME = 1000.0
    
    # Core Affinity 判定
    AFFINITY_FIXED_CPU_MIN = 90.0     # Fixed 需要 CPU > 90%
    AFFINITY_THROTTLE_INFER_CPU_MAX = 90.0  # 节流推断: CPU < 90
    
    # ==========================================================================
    # 内核态比例相关
    # ==========================================================================
    KERNEL_RATIO_HIGH = 50.0
    KERNEL_RATIO_CRITICAL = 70.0
    
    # ==========================================================================
    # Core Distribution 相关
    # ==========================================================================
    CORE_SATURATED_THRESHOLD = 50.0   # 核心饱和显示阈值
    IMBALANCE_RATIO_CRITICAL = 10.0
    
    # ==========================================================================
    # Correlation Flags 阈值 (bottleneck-trace)
    # ==========================================================================
    LOCK_CONTENTION_INCLUSIVE_PCT = 40.0   # GLOBAL_LOCK_CONTENTION
    THROTTLE_VICTIM_CPU_MAX = 80.0         # THROTTLE_VICTIM: CPU < 80
    THROTTLE_RATE_MIN = 50.0               # 节流率 > 50%
    
    # ==========================================================================
    # Z-Score (异常检测)
    # ==========================================================================
    Z_SCORE_MEDIUM = 2.0
    Z_SCORE_HIGH = 2.5
```

---

## 第三部分: 字符串常量统一

### 新增 StringConstants 类

```python
# config/defaults.py

@dataclass(frozen=True)
class StringConstants:
    """字符串常量 - 避免代码中硬编码字符串"""
    
    # ==========================================================================
    # Core Affinity 值
    # ==========================================================================
    AFFINITY_FIXED = "Fixed"
    AFFINITY_UNIFORM = "Uniform"
    AFFINITY_SCATTERED = "Scattered"
    
    # ==========================================================================
    # Path Characteristic 值
    # ==========================================================================
    CHAR_COMPUTE = "COMPUTE"
    CHAR_LOCK_CONTENTION = "Lock_Contention"
    CHAR_IO_WAIT = "IO_Wait_Dominant"
    CHAR_SYSCALL_BOUND = "Syscall_Bound"
    CHAR_LATENCY_VICTIM = "Inclusive_Latency_Victim"
    CHAR_HIGH_FREQ_CPU = "High_Frequency_Exclusive_CPU"
    
    # ==========================================================================
    # 符号检测关键词 (小写，用于 in 检查)
    # ==========================================================================
    LOCK_KEYWORDS = ["lock", "mutex", "spin", "rwsem"]
    IO_KEYWORDS = ["io_schedule"]
    SYSCALL_KEYWORDS = ["syscall", "sys_", "entry_syscall"]
    
    # ==========================================================================
    # 全局锁符号列表
    # ==========================================================================
    GLOBAL_LOCK_SYMBOLS = [
        "_raw_spin_lock",
        "mutex_lock", 
        "rwsem_down_read",
        "spin_lock",
        "queue_spin_lock"
    ]
```

---

## 第四部分: 重构代码示例

### 4.1 Core Affinity 判定

```python
# 重构前 (bottleneck_trace.py:62-67) - 硬编码
if bottleneck.monopoly > 0.8:
    core_affinity = "Fixed"
elif bottleneck.cv < 0.5:
    core_affinity = "Uniform"
else:
    core_affinity = "Scattered"

# 重构后 - 配置驱动
from config.defaults import Thresholds, StringConstants

def determine_core_affinity(bottleneck) -> str:
    if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
        return StringConstants.AFFINITY_FIXED
    elif bottleneck.cv < Thresholds.CV_AFFINITY_UNIFORM:
        return StringConstants.AFFINITY_UNIFORM
    else:
        return StringConstants.AFFINITY_SCATTERED
```

### 4.2 Path Characteristic 推断

```python
# 重构前 (bottleneck_trace.py:117-126) - 硬编码关键词
if any(k in hs.symbol.lower() for k in ['lock', 'mutex', 'spin', 'rwsem']):
    characteristic = "Lock_Contention"
elif 'io_schedule' in hs.symbol.lower():
    characteristic = "IO_Wait_Dominant"
elif any(k in hs.symbol.lower() for k in ['syscall', 'sys_', 'entry_syscall']):
    characteristic = "Syscall_Bound"
elif hs.inclusive_percent > hs.cpu_percent * 3:
    characteristic = "Inclusive_Latency_Victim"
elif hs.cpu_percent > hs.inclusive_percent * 2:
    characteristic = "High_Frequency_Exclusive_CPU"

# 重构后 - 配置驱动
from config.defaults import StringConstants

def infer_path_characteristic(hotspot) -> str:
    symbol_lower = hotspot.symbol.lower()
    
    if any(k in symbol_lower for k in StringConstants.LOCK_KEYWORDS):
        return StringConstants.CHAR_LOCK_CONTENTION
    elif any(k in symbol_lower for k in StringConstants.IO_KEYWORDS):
        return StringConstants.CHAR_IO_WAIT
    elif any(k in symbol_lower for k in StringConstants.SYSCALL_KEYWORDS):
        return StringConstants.CHAR_SYSCALL_BOUND
    elif hotspot.inclusive_percent > hotspot.cpu_percent * 3:
        return StringConstants.CHAR_LATENCY_VICTIM
    elif hotspot.cpu_percent > hotspot.inclusive_percent * 2:
        return StringConstants.CHAR_HIGH_FREQ_CPU
    
    return StringConstants.CHAR_COMPUTE
```

### 4.3 Correlation Flags 检测

```python
# 重构前 (bottleneck_trace.py:179-241) - 多处硬编码
lock_symbols = ['_raw_spin_lock', 'mutex_lock', 'rwsem_down_read',
               'spin_lock', 'queue_spin_lock']
if inclusive_pct > 40:
    flags.append(...)

if bottleneck.monopoly > 0.8:
    flags.append(...)

if bottleneck.monopoly > 0.8 and bottleneck.total_cpu < 80:
    ...

# 重构后 - 完全配置驱动
from config.defaults import (
    Thresholds, StringConstants, 
    DiagnosisThresholds, EventConfig
)

def detect_correlation_flags(bottleneck, hotspots_report):
    flags = []
    
    # 1. GLOBAL_LOCK_CONTENTION
    for hs in hotspots_report.hotspots:
        if any(ls in hs.symbol for ls in StringConstants.GLOBAL_LOCK_SYMBOLS):
            if hs.inclusive_percent > Thresholds.LOCK_CONTENTION_INCLUSIVE_PCT:
                flags.append(CorrelationFlag(
                    flag_type=RiskPattern.LOCK_CONTENTION,
                    ...
                ))
    
    # 2. SINGLE_CORE_SATURATION
    if bottleneck.monopoly > Thresholds.MONOPOLY_HIGH:
        flags.append(CorrelationFlag(
            flag_type=RiskPattern.SINGLE_CORE_SATURATION,
            ...
        ))
    
    # 3. THROTTLE_VICTIM
    if (bottleneck.monopoly > Thresholds.MONOPOLY_HIGH and 
        bottleneck.total_cpu < Thresholds.THROTTLE_VICTIM_CPU_MAX):
        throttle_rate = 100.0 - bottleneck.total_cpu
        if throttle_rate > Thresholds.THROTTLE_RATE_MIN:
            flags.append(...)
    
    # 4. STORM_PATTERN
    if (bottleneck.diagnosis == DiagnosisType.STORM or 
        bottleneck.spawn_rate > DiagnosisThresholds.STORM_RATE_MIN):
        flags.append(...)
    
    # 5. KERNEL_HEAVY
    if bottleneck.kernel_ratio > Thresholds.KERNEL_RATIO_HIGH:
        flags.append(...)
    
    # 6. UNBALANCED_LOAD
    if (bottleneck.cv > Thresholds.CV_UNBALANCED_LOAD and 
        bottleneck.monopoly < Thresholds.MONOPOLY_HIGH):
        flags.append(...)
    
    return flags
```

---

## 第五部分: 完整修改清单

### 5.1 配置文件修改 (`config/defaults.py`)

```python
# 新增以下类

@dataclass(frozen=True)
class EventConfig:
    """Event 配置"""
    BOTTLENECK_MARKER = "M"
    STORM_MARKER = "RATE"
    UNBALANCED_MARKER = "CV"
    
    BOTTLENECK_FORMAT = "{type}({marker}={value:.4f})"
    STORM_FORMAT = "{type}({value:.1f}/s)"
    UNBALANCED_FORMAT = "{type}({marker}={value:.4f})"
    NORMAL_FORMAT = "normal"

@dataclass(frozen=True)
class DiagnosisThresholds:
    """诊断阈值"""
    BOTTLENECK_MONOPOLY_MIN = 0.8
    STORM_RATE_MIN = 100.0
    STORM_PID_COUNT_MIN = 1000
    UNBALANCED_CV_MIN = 1.0

@dataclass(frozen=True)
class StringConstants:
    """字符串常量"""
    # Core Affinity
    AFFINITY_FIXED = "Fixed"
    AFFINITY_UNIFORM = "Uniform"
    AFFINITY_SCATTERED = "Scattered"
    
    # Path Characteristic
    CHAR_COMPUTE = "COMPUTE"
    CHAR_LOCK_CONTENTION = "Lock_Contention"
    CHAR_IO_WAIT = "IO_Wait_Dominant"
    CHAR_SYSCALL_BOUND = "Syscall_Bound"
    CHAR_LATENCY_VICTIM = "Inclusive_Latency_Victim"
    CHAR_HIGH_FREQ_CPU = "High_Frequency_Exclusive_CPU"
    
    # Keywords
    LOCK_KEYWORDS = ["lock", "mutex", "spin", "rwsem"]
    IO_KEYWORDS = ["io_schedule"]
    SYSCALL_KEYWORDS = ["syscall", "sys_", "entry_syscall"]
    
    # Symbols
    GLOBAL_LOCK_SYMBOLS = [
        "_raw_spin_lock", "mutex_lock", "rwsem_down_read",
        "spin_lock", "queue_spin_lock"
    ]

# Thresholds 类扩展
@dataclass(frozen=True)
class Thresholds:
    # 现有阈值保持不变...
    
    # 新增阈值
    CV_AFFINITY_UNIFORM = 0.5
    CV_UNBALANCED_LOAD = 1.5
    AFFINITY_FIXED_CPU_MIN = 90.0
    AFFINITY_THROTTLE_INFER_CPU_MAX = 90.0
    LOCK_CONTENTION_INCLUSIVE_PCT = 40.0
    THROTTLE_VICTIM_CPU_MAX = 80.0
    THROTTLE_RATE_MIN = 50.0
```

### 5.2 代码文件修改

| 文件 | 修改内容 | 行号 |
|------|----------|------|
| `analysis/comm_top.py` | 使用 `EventConfig` 和 `DiagnosisThresholds` | 52, 58, 102 |
| `cli/commands/composite/bottleneck_trace.py` | 替换所有硬编码 | 62-241 |
| `cli/commands/composite/sys_audit.py` | 使用 `Thresholds.CORE_SATURATED_THRESHOLD` | 175 |
| `composite/bottleneck_tracer.py` | 使用配置常量 | 306-403 |

---

## 第六部分: 验证检查

重构后，代码中不应出现以下硬编码：

- [ ] 数值: `0.8`, `0.5`, `1.5`, `40`, `50`, `80`, `90`, `100` 等
- [ ] 字符串: `"Fixed"`, `"Uniform"`, `"Scattered"`, `"COMPUTE"`, `"Lock_Contention"` 等
- [ ] 关键词: `["lock", "mutex", "spin", "rwsem"]` 等
- [ ] 格式字符串: `"{type}(M={value:.4f})"` 等

验证命令:
```bash
# 检查是否还有硬编码 0.8
grep -n "> 0.8\|< 0.8" scripts/perf_toolkit/**/*.py

# 检查是否还有硬编码字符串
grep -n '"Fixed"\|"Uniform"\|"Scattered"' scripts/perf_toolkit/**/*.py
```

---

## 附录: 修改后的完整文件示例

详见配套 PR 中的修改文件。
