# perf-hunter 待办事项

> 记录代码与文档的不一致问题及修复任务

---

## 快速导航

- **最终对齐方案**: `BOTTLENECK_FINAL_ALIGNMENT.md` - 零硬编码、全配置驱动的重构方案
- **与 sys-audit 数值对比**: `BOTTLENECK_SYSAUDIT_ALIGNMENT.md` - 详细阈值对比表
- **继承设计**: `design/design-bottleneck-trace-audit-integration.md` - 从 sys-audit 继承 issues

---

## P1 - 高优先级（影响功能理解）

### TODO-1: 修复 `BottleneckTraceOutput` 与 `BottleneckTraceResult` 命名不一致

**问题描述**:
- `interface-composite.md` 第 358-384 行定义的 `BottleneckTraceOutput` 结构在代码中不存在
- 实际代码使用的是 `core/output_models.py` 中的 `BottleneckTraceResult`
- 字段定义完全不匹配

**影响文件**:
- `docs/interface/interface-composite.md`
- `docs/interface/interface-cli.md` 第 382-387 行

**修复方案**:
1. 将 `interface-composite.md` 中的 `BottleneckTraceOutput` 替换为 `BottleneckTraceResult`
2. 更新字段定义以匹配实际代码
3. 同步更新 `interface-cli.md` 中的输出类型继承关系图

**参考代码** (`core/output_models.py:629-684`):
```python
@dataclass
class BottleneckTraceResult:
    _risk: RiskInfo
    entity_distribution: List[EntityDistribution]
    common_hotspot: str
    common_hotspot_weight: float
    clusters: List[CallPathCluster]
    correlation_flags: List[CorrelationFlag]
    total_pids: int
    total_sys_cpu: float
    top_bottlenecks: List[str]
    duration_sec: float
    sample_count: int
    time_range: Optional[TimeRange]
```

---

### TODO-2: 统一 `SINGLE_CORE_SATURATION` 检测阈值

**问题描述**:
- **CLI 代码** (`cli/commands/composite/bottleneck_trace.py:197`): 仅检查 `monopoly > 0.8`
- **Adapter 代码** (`composite/bottleneck_tracer.py:351`): 检查 `total_cpu > 90 and monopoly > 0.8`
- **设计文档** (`tool-bottleneck-trace.md:204`): "单核利用率 > 90% 且 Monopoly > 0.8"

**不一致点**:
- CLI 代码缺少 CPU 利用率检查，与文档和其他实现不一致

**修复方案**:
统一使用文档定义的标准：`total_cpu > 90 and monopoly > 0.8`

**影响代码**:
- `scripts/perf_toolkit/cli/commands/composite/bottleneck_trace.py:197-203`

---

### TODO-3: 统一 `THROTTLE_VICTIM` 检测逻辑

**问题描述**:
- **代码实现**: `monopoly > 0.8 and total_cpu < 80`，基于 CPU 利用率推断
- **设计文档** (`tool-bottleneck-trace.md:205`): "Throttle_Rate > 50%"

**不一致点**:
- 代码使用间接推断，文档使用直接检测

**修复方案**:
两种方式选择其一：
- 方案 A: 修改代码，实现真实的 Throttle_Rate 检测
- 方案 B: 修改文档，明确说明是基于高 Monopoly + 低 CPU 的推断

**建议**: 采用方案 B，当前推断逻辑简单有效，只需更新文档说明

---

## P2 - 中优先级（文档准确性）

### TODO-4: 更新 `STORM_PATTERN` 检测条件文档

**问题描述**:
- **代码实现**: `diagnosis == STORM or spawn_rate > 100`
- **设计文档** (`tool-bottleneck-trace.md:206`): "Spawn_Rate > 100/s 或 PID_Count > 1000"

**不一致点**:
- 代码多一个 STORM 诊断条件，文档缺少 PID_Count 检查

**修复方案**:
1. 确认代码逻辑是否正确
2. 更新文档以匹配代码，或反之

**影响文件**:
- `docs/report/tool-bottleneck-trace.md` 第 199-208 行

---

### TODO-5: 同步文档版本历史

**问题描述**:
- `tool-bottleneck-trace.md`: 版本 1.0.0 (2026-03-03)，未记录后续变更
- `interface-composite.md`: 版本 1.1 (2026-03-04)，提到"移除 storm-trace"，但 bottleneck-trace 描述过时
- `interface-cli.md`: 版本 1.1 (2026-03-04)，输出类型描述与代码不一致

**修复方案**:
1. 为 `tool-bottleneck-trace.md` 添加版本 1.1 记录（四段式输出格式变更）
2. 更新 `interface-composite.md` 中的 `BottleneckTraceOutput` 描述
3. 更新 `interface-cli.md` 第 382-387 行的输出类型描述

---

### TODO-6: 明确 BottleneckTracer 分层差异

**问题描述**:
- `interface-composite.md` 第 658-767 行定义的 `BottleneckTracer.trace()` 返回 `Tuple[BottleneckAnalysis, HotspotsReport, Optional[CallersReport]]`
- CLI 层实际返回的是 `BottleneckTraceResult`

**不一致点**:
- 文档未明确说明 Composite 层内部与 CLI 层输出的差异

**修复方案**:
在 `interface-composite.md` 中添加说明：
- Composite 层内部使用 `BottleneckAnalysis` 等中间结构
- CLI 层通过转换输出 `BottleneckTraceResult`

---

## P3 - 低优先级（代码清理）

### TODO-7: 清理 `bottleneck_tracer.py` 适配器代码

**问题描述**:
- `composite/bottleneck_tracer.py` 存在大量与 CLI 命令重复的转换逻辑
- 部分逻辑（如 `_determine_affinity_pattern`）使用了更复杂的熵计算
- CLI 命令使用的是简化版本

**不一致点**:
- 两个实现路径的逻辑不一致，可能导致不同入口行为不同

**修复方案**:
1. 检查 `bottleneck_tracer.py` 是否仍在使用
2. 如已废弃，标记为 deprecated
3. 如仍在使用，统一转换逻辑，或合并为一个实现

---

### TODO-8: 统一 `entity_distribution` 构建逻辑

**问题描述**:
- CLI 命令 (`bottleneck_trace.py:44-89`): 只构建一个 EntityDistribution（目标进程）
- Adapter (`bottleneck_tracer.py:565-611`): 构建前 10 个进程组的列表

**不一致点**:
- 输出格式不一致，CLI 命令输出列表只有一个元素

**修复方案**:
确认设计意图：
- 如果设计是只显示目标进程，更新 Adapter 代码
- 如果设计是显示多个进程，更新 CLI 代码

**参考文档**:
`tool-bottleneck-trace.md` 第 121-125 行显示多个进程组

---

## 修复检查清单

修复完成后，请更新此清单：

- [ ] TODO-1: 修复 `BottleneckTraceOutput` 命名不一致
- [ ] TODO-2: 统一 `SINGLE_CORE_SATURATION` 阈值
- [ ] TODO-3: 统一 `THROTTLE_VICTIM` 检测逻辑
- [ ] TODO-4: 更新 `STORM_PATTERN` 文档
- [ ] TODO-5: 同步文档版本历史
- [ ] TODO-6: 明确 BottleneckTracer 分层差异
- [ ] TODO-7: 清理 `bottleneck_tracer.py` 适配器代码
- [ ] TODO-8: 统一 `entity_distribution` 构建逻辑
- [ ] TODO-9: 统一阈值使用 `Thresholds` 常量
- [ ] TODO-10: Core Affinity 判定与文档一致
- [ ] TODO-11: Throttle Rate 计算阈值对齐
- [ ] TODO-12: 统一 CallChain 输出风格 - 详见 `BOTTLENECK_CALLCHAIN_UNIFICATION.md`

---

## 相关文件索引

### 代码文件
- `scripts/perf_toolkit/cli/commands/composite/bottleneck_trace.py`
- `scripts/perf_toolkit/composite/bottleneck_tracer.py`
- `scripts/perf_toolkit/composite/bottleneck_trace.py`
- `scripts/perf_toolkit/core/output_models.py`

### 设计文档
- `docs/interface/interface-composite.md`
- `docs/interface/interface-cli.md`
- `docs/report/tool-bottleneck-trace.md`
- `docs/design/design-three-tier-architecture.md`
- `docs/BOTTLENECK_SYSAUDIT_ALIGNMENT.md` - 数值计算对齐详情
- `docs/design/design-bottleneck-trace-audit-integration.md` - 继承设计
- `docs/BOTTLENECK_CALLCHAIN_UNIFICATION.md` - CallChain 输出风格统一

---

## P1 - 新增（与 sys-audit 数值对齐）

### TODO-9: 统一阈值使用 `Thresholds` 常量

**问题描述**:
bottleneck-trace 中多处硬编码阈值，应使用 `config/defaults.py` 中的常量：

| 位置 | 硬编码值 | 应使用常量 |
|------|----------|------------|
| `bottleneck_trace.py:62` | `> 0.8` | `Thresholds.MONOPOLY_HIGH` |
| `bottleneck_trace.py:64` | `< 0.5` | 新增 `CV_AFFINITY_UNIFORM` |
| `bottleneck_trace.py:71` | `< 90` | `Thresholds.CPU_UTIL_CRITICAL` |
| `bottleneck_trace.py:188` | `> 40` | 新增 `LOCK_CONTENTION_INCLUSIVE_PCT` |
| `bottleneck_trace.py:197` | `> 0.8` | `Thresholds.MONOPOLY_HIGH` |
| `bottleneck_trace.py:206` | `< 80` | `Thresholds.CPU_UTIL_HIGH` |
| `bottleneck_trace.py:216` | `> 100` | 新增 `STORM_SPAWN_RATE` |
| `bottleneck_trace.py:225` | `> 50` | `Thresholds.KERNEL_RATIO_HIGH` |
| `bottleneck_trace.py:234` | `> 1.5` | 新增 `CV_UNBALANCED_LOAD` |

**修复方案**:
1. 在 `Thresholds` 类中添加新常量
2. 修改代码使用常量替代硬编码

**相关文档**: `BOTTLENECK_SYSAUDIT_ALIGNMENT.md`

---

### TODO-10: Core Affinity 判定与文档不一致

**问题描述**:
- **代码** (`bottleneck_trace.py:62-67`): 使用 Monopoly + CV 判定
- **文档** (`tool-bottleneck-trace.md:142-144`): 使用 Entropy + Monopoly/CV 判定

**修复方案**:
- 方案 A: 修改代码实现 Entropy 计算
- 方案 B: 更新文档匹配代码实现

**建议**: 方案 B，代码实现更简单有效

---

### TODO-11: Throttle Rate 计算阈值不一致

**问题描述**:
- **bottleneck-trace**: `< 90` 用于节流推断
- **sys-audit 设计**: 使用 `< 80` (CPU_UTIL_HIGH) 或 `> 90` (CPU_UTIL_CRITICAL)

**建议**: 统一使用 `Thresholds.CPU_UTIL_HIGH (80)` 或 `CPU_UTIL_CRITICAL (100)`

---

### TODO-12: 统一 CallChain 输出风格

**问题描述**:
三个命令使用不同的 callchain 输出格式：

| 命令 | 当前格式 | 问题 |
|------|----------|------|
| **find-callers** | `#1 [ratio%] func1 <- func2` | 使用 `_format_attribution_line` |
| **cluster-paths** | `#1 ratio% cpu% path` | 使用 `_format_path_cluster_line` |
| **bottleneck-trace** | `` `comm` -> `func` -> **[HOTSPOT]** `` | 使用 `_format_call_path` |

**冗余代码**: `text_output_adapter.py` 中有 3 个独立的格式化函数

**解决方案**:
1. 创建统一的 `CallChainFormatter` 类
2. 支持参数化: direction (top_down/bottom_up), style (markdown/plain), ratio
3. 所有命令使用同一个格式化函数

**详细设计**: 见 `BOTTLENECK_CALLCHAIN_UNIFICATION.md`

**实施步骤**:
1. 创建 `perf_toolkit/core/callchain_formatter.py`
2. 重构 `text_output_adapter.py` 使用统一格式化器
3. 可选: 在 `output_models.py` 中添加统一的 `_path` 字段

---

## 记录更新

| 日期 | 更新人 | 变更内容 |
|------|--------|----------|
| 2026-03-04 | - | 初始创建 TODO 文件 |
| 2026-03-04 | - | 添加与 sys-audit 数值对齐问题 (TODO-9 ~ TODO-11) |
