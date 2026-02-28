# Perf Script 格式说明

## 基本格式

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

## 字段说明

| 字段 | 说明 | 示例 |
|-----|------|------|
| `comm` | 进程名 | `perf-exec` |
| `pid` | 进程 ID | `215053` |
| `cpu` | CPU 核心号（方括号内） | `[002]` |
| `timestamp` | 时间戳（秒） | `368330.780793` |
| `core_per_sec` | CPU 核秒数/秒（利用率比例） | `0.0526` |
| `symbol` | 函数符号名 | `zap_pte_range` |
| `module` | 所属模块 | `[kernel.kallsyms]` |

## core/s 字段详解

`core_per_sec`（core/s）是 perf 统计的 CPU 利用率指标：

- **含义**：该调用链在采样时刻每秒消耗的 CPU 核秒数
- **数值范围**：0.0 ~ 系统 CPU 核心数
- **换算**：`0.0526 core/s` = 占用单核 5.26% 的算力
- **多核累加**：系统总 CPU 利用率 = 所有样本 core/s 之和 / 采样时长 × 100%

**为什么使用 core/s**：
1. **直接反映利用率**：无需知道采样频率，直接得到 CPU 利用率
2. **聚合友好**：可以对多个样本的 core/s 值直接累加求和
3. **跨系统可比**：不受 CPU 核数差异影响

## 数据特点

1. **按进程聚合**：同一个进程的 callchain 在 1s 内针对 cpuid 做了聚合
2. **每个 header 代表一个聚合后的 callchain**：包含该时间段内该进程在指定 CPU 上的执行统计
3. **core_per_sec 代表聚合后 callchain 栈顶函数的开销**：即该调用链消耗的 CPU 时间

### 重要说明

**样本数量无参考价值**：
- 由于数据已按 1 秒聚合，样本数量（记录数）不代表原始采样数
- 原始采样频率（如 19Hz）已被聚合过程隐藏
- **分析时应只关注 core/s 值（CPU 利用率），不要关注样本数量**

**正确的分析方式**：
- 所有统计应基于 `core_per_sec` 累加
- 比例计算应使用 `core/s 占比` 而非 `样本数占比`
- 可靠性评估基于 CPU 利用率水平和数据覆盖时长

## 与旧格式对比

旧版 perf script 没有 `core/s` 字段，需要通过样本数和采样频率估算利用率：

```
# 旧格式（无 core/s）
perf-exec  215053 [002] 368330.780793:
        zap_pte_range+0x2d4 ([kernel.kallsyms])
        ...

# 新格式（有 core/s）
perf-exec  215053 [002] 368330.780793:     0.0526 core/s:
        zap_pte_range+0x2d4 ([kernel.kallsyms])
        ...
```

**工具处理**：工具优先使用 `core/s` 字段计算，样本数量仅作为数据覆盖度的参考。

**注意**：core/s 字段是这个系统的独有字段，和perf不一样，他是一种基于perf机制实现的new perf的output format
