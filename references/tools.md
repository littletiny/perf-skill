# Perf Expert 工具命令参考

> 纯命令参考手册。分析策略和方法论请查阅 [methodology.md](./methodology.md)。

---

## 快速使用

```bash
# 初始化（只需一次）
scripts/shecr init --data-path <perf.data>

# 两个综合诊断入口
shecr sys-audit
shecr bottleneck-trace --comm <name>
```

---

## 命令速查表

### 核心分析工具（6个）

| 工具 | 层级 | 用途 | 典型场景 |
|------|------|------|---------|
| `analyze-core-distribution` | 系统级 | 核心级负载分析、单核饱和检测 | 负载不均衡检查 |
| `detect-anomalies` | 时间级 | 时序异常定位 | 突发问题分析 |
| `get-comm-top` | 实体级 | 进程组资源识别 + 离群检测 + 风暴检测 | 大量小进程场景、单进程瓶颈 |
| `get-hotspots` | 函数级 | 热点函数排名 | 代码级优化 |
| `find-callers` | 关系级 | 热点函数溯源 | 调用链分析 |
| `cluster-paths` | 模式级 | 调用路径聚类 | 业务逻辑定位 |

### 2个综合诊断入口

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `sys-audit` | 系统全景扫描 | 快速定位真瓶颈 |
| `bottleneck-trace` | 瓶颈深度追踪 | 单点性能问题 |

---

## 系统级工具

## 工具详情

### analyze-core-distribution

核心级负载分布分析。检测单核饱和、负载不均衡。

```bash
shecr analyze-core-distribution [options]
```

**特有参数**: `--threshold` (单核饱和度阈值), `--cpu-limit` (Cgroup limit检测)  
**检测模式**: `SINGLE_CORE_SATURATION`, `WIDE_DISTRIBUTION_LOW_UTIL`, `IRQ_IMBALANCE`

---

### detect-anomalies

时序异常检测。识别 CPU 利用率突变点。

```bash
shecr detect-anomalies [options]
```

**特有参数**: `--window-size` (滑动窗口秒数), `--spike-threshold` (变化倍数), `--min-utilization` (最小利用率)  
**检测类型**: `SPIKE`, `DROP`, `LEVEL_SHIFT`, `BURST`

---

### get-comm-top

进程组资源分析。识别离群进程和进程风暴。

```bash
shecr get-comm-top [options]
```

**特有参数**: `--show-all` (显示全部), `--cv-threshold` (CV异常阈值), `--monopoly-threshold` (核心独占阈值), `--spawn-threshold` (风暴检测阈值)  
**诊断标签**: `HEALTHY`, `UNBALANCED`, `BOTTLENECK`, `STORM`

---

### get-hotspots

热点函数识别。

```bash
shecr get-hotspots [options]
```

**特有参数**: `--sort-by` (inclusive/self)

---

### find-callers

热点函数溯源。

```bash
shecr find-callers --target <function> [options]
# 或
shecr find-callers --auto-target [options]
```

**特有参数**: `--target` (目标函数), `--auto-target` (自动追踪), `--min-ratio` (最小占比%)  
**常用 target**: `schedule`, `pthread_mutex_lock`, `epoll_wait`, `nanosleep`

---

### cluster-paths

调用路径聚类。

```bash
shecr cluster-paths [options]
```

**特有参数**: `--min-depth`, `--min-samples`

---

## 组合诊断工具

### sys-audit

系统全景扫描。

```bash
shecr sys-audit [options]
```

**特有参数**: `--show-all`

---

### bottleneck-trace

深度分析瓶颈进程。

```bash
shecr bottleneck-trace --comm <name> [options]
# 或
shecr bottleneck-trace --pid <PID> [options]
# 或
shecr bottleneck-trace --auto-detect
```

**特有参数**: `--comm`, `--pid`, `--auto-detect`

---

## Trace 命令

问题追踪：记录诊断过程中的发现和结论。

| 命令 | 用途 | 示例 |
|------|------|------|
| `trace add` | 添加问题 | `shecr trace add --desc "CPU异常" --level critical` |
| `trace complete` | 标记完成 | `shecr trace complete --id ISS-001 --result "根因: ..."` |
| `trace issues` | 查看问题列表 | `shecr trace issues [--status open\|resolved]` |
| `trace finalize` | 结束诊断 | `shecr trace finalize [--accept-risk "..."]` |

---

## 参数矩阵

| 工具 | `--cpu-id` | `--pid` | `--comm` | `--comm-regex` | `--start-time` | `--end-time` |
|------|:--------:|:----------:|:-------:|:--------:|:--------------:|:--------------:|:------------:|
| `analyze-core-distribution` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `detect-anomalies` | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `get-comm-top` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| `get-hotspots` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `find-callers` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cluster-paths` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `sys-audit` | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `bottleneck-trace` | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

**说明**:
- 所有工具支持 `--start-time`/`--end-time` 时间过滤（ISO 8601、Unix 时间戳、日期格式）
- `--comm`: 支持逗号分隔多值，如 `--comm nginx,php-fpm`
- 完整参数请使用 `shecr <command> --help` 查看

## 参考文档

- 📗 **分析方法论**: [methodology.md](./methodology.md) - 完整方法论
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
