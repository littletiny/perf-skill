# Perf Script 格式说明

## 支持的数据格式

本工具支持两种 perf script 数据格式：

1. **SPEAR 格式**（推荐）：包含 `core/s` 字段，直接使用预计算的 CPU 利用率
2. **原始 perf 格式**：标准 perf script 输出，需要通过 `--freq` 参数指定采样频率来计算利用率

---

## 格式一：SPEAR 格式（有 core/s）

### 基本格式

```
<comm> <pid> [<cpu>] <timestamp>: <core_per_sec> core/s:
                       <symbol> (<module>)
                       <symbol> (<module>)
                       ...
```

示例：
```
perf-exec  215053 [002] 368330.780793:     0.0526 core/s:
        ffff800080441754 zap_pte_range+0x2d4 ([kernel.kallsyms])
        ffff800080441e80 zap_pmd_range.isra.0+0xc0 ([kernel.kallsyms])
        ffff800080442800 unmap_page_range+0x118 ([kernel.kallsyms])
```

### 字段说明

| 字段 | 说明 | 示例 |
|-----|------|------|
| `comm` | 进程名 | `perf-exec` |
| `pid` | 进程 ID | `215053` |
| `cpu` | CPU 核心号（方括号内） | `[002]` |
| `timestamp` | 时间戳（秒） | `368330.780793` |
| `core_per_sec` | CPU 核秒数/秒（利用率比例） | `0.0526` |
| `symbol` | 函数符号名 | `zap_pte_range` |
| `module` | 所属模块 | `[kernel.kallsyms]` |

### core/s 字段详解

`core_per_sec`（core/s）是预计算的 CPU 利用率指标：

- **含义**：该调用链在采样时刻每秒消耗的 CPU 核秒数
- **数值范围**：0.0 ~ 系统 CPU 核心数
- **换算**：`0.0526 core/s` = 占用单核 5.26% 的算力
- **多核累加**：系统总 CPU 利用率 = 所有样本 core/s 之和 / 采样时长 × 100%

**为什么使用 core/s**：
1. **直接反映利用率**：无需知道采样频率，直接得到 CPU 利用率
2. **聚合友好**：可以对多个样本的 core/s 值直接累加求和
3. **跨系统可比**：不受 CPU 核数差异影响

---

## 格式二：原始 perf 格式（无 core/s）

### 基本格式

```
<comm> <pid> [<cpu>] <timestamp>: <period> <event_name>:
                       <symbol> (<module>)
                       <symbol> (<module>)
                       ...
```

示例：
```
swapper     0 [001] 460661.461601:     250000 cpu-clock:ppp:
        ffff800080152a30 cpuidle_idle_call+0xb8 ([kernel.kallsyms])
        ffff800080152c38 do_idle+0xb0 ([kernel.kallsyms])
```

### 字段说明

| 字段 | 说明 | 示例 |
|-----|------|------|
| `comm` | 进程名 | `swapper` |
| `pid` | 进程 ID | `0` |
| `cpu` | CPU 核心号（方括号内） | `[001]` |
| `timestamp` | 时间戳（秒） | `460661.461601` |
| `period` | 采样周期计数 | `250000` |
| `event_name` | 事件名称 | `cpu-clock:ppp:` |
| `symbol` | 函数符号名 | `cpuidle_idle_call` |
| `module` | 所属模块 | `[kernel.kallsyms]` |

### 使用方法

对于原始 perf 格式，**必须通过 `--freq` 参数指定采样频率**（默认 19Hz）：

```bash
# 指定采样频率 19Hz
spear show-cpu-usage --data perf.data --freq 19

# 如果 perf record 使用 -F 99 采样
spear show-cpu-usage --data perf.data --freq 99
```

### CPU 利用率计算原理

原始 perf 格式的 CPU 利用率计算：

```
core/s = 样本数 / 采样频率 = samples / freq
CPU利用率% = (core/s / 采样时长) × 100%
         = samples / (duration × freq) × 100%
```

工具内部通过 `get_sample_weight()` 方法处理：
- SPEAR 格式（有 core/s）：直接返回 core/s 值
- 原始格式（无 core/s）：返回 `1.0 / freq`，即单个样本代表的 core/s

---

## 两种格式对比

| 特性 | SPEAR 格式 | 原始 perf 格式 |
|------|-----------|--------------|
| core/s 字段 | ✅ 有 | ❌ 无 |
| 采样频率参数 | 不需要 | **必需**（默认 19Hz）|
| 计算精度 | 精确（已聚合） | 估算（依赖 freq 准确性）|
| 使用场景 | 推荐用于精确分析 | 兼容标准 perf 输出 |

### 格式识别

工具会自动检测数据格式：
- 如果检测到 `core/s:` 字段 → 使用 SPEAR 格式处理
- 否则 → 使用原始 perf 格式处理（需要 `--freq`）

可以通过 `--freq` 参数覆盖默认频率：
```bash
# 自动检测格式，原始格式使用 19Hz
spear show-cpu-usage --data perf.data

# 明确指定 99Hz 采样频率
spear show-cpu-usage --data perf.data --freq 99
```

---

## 数据特点

1. **按进程聚合**：同一个进程的 callchain 在 1s 内针对 cpuid 做了聚合
2. **每个 header 代表一个聚合后的 callchain**：包含该时间段内该进程在指定 CPU 上的执行统计
3. **core_per_sec 代表聚合后 callchain 栈顶函数的开销**：即该调用链消耗的 CPU 时间

### 重要说明

**样本数量无参考价值（SPEAR 格式）**：
- 由于数据已按 1 秒聚合，样本数量（记录数）不代表原始采样数
- 原始采样频率（如 19Hz）已被聚合过程隐藏
- **分析时应只关注 core/s 值（CPU 利用率），不要关注样本数量**

**正确的分析方式**：
- 所有统计应基于 `core_per_sec` 累加（或使用 `--freq` 参数正确计算）
- 比例计算应使用 `core/s 占比` 而非 `样本数占比`
- 可靠性评估基于 CPU 利用率水平和数据覆盖时长
