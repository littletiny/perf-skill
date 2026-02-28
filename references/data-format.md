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

**工具兼容性**：工具优先使用 `core/s` 字段计算，如果数据中没有该字段会发出警告。

## 生成带 core/s 的 perf 数据

使用 `perf script` 的 `-F` 参数指定输出字段：

```bash
# 生成带 core/s 的 script 输出
perf script -F comm,pid,cpu,time,core,sym,dso > perf.script

# 或使用 report 的 raw 输出
perf report --stdio --show-nr-samples --show-total-period
```

**注意**：core/s 字段需要较新版本的 perf（Linux 5.x+），旧版本可能不支持。
