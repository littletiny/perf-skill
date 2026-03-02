---
name: SPEAR-perf-hunter
description: Systematic Linux performance diagnosis using SPEAR methodology. Use when analyzing CPU bottlenecks, high latency, resource contention, or performance regression in Linux environments.
---

# SPEAR 性能诊断

> **S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning

通过"领域知识驱动的假设验证"实现根因定位。

**最新更新**: 工具集已精简为 6 个核心工具 + 3 个组合命令，详见 [design-three-tier-architecture.md](./docs/design-three-tier-architecture.md)

---

## ⚡ 三分钟开始

### 快速初始化（推荐）

```bash
# 1. 使用 wrap 脚本初始化（自动配置路径）
scripts/spear init --data-path <perf.data> [--freq <hz>]

# 2. 后续命令大幅简化（自动注入 --data）
spear get-hotspots --comm myapp
spear analyze-core-distribution
spear find-callers --target pthread_mutex_lock

# 3. 查看配置状态
spear status
```

### 传统方式（备用）

```bash
# 1. 创建诊断文档（强制执行）
mkdir -p debug
# 使用 references/templates.md 创建 debug/[问题描述].md

# 2. 初始化状态追踪
spear trace init --data <perf.data>
```

---

## 🔍 典型场景速查

| 如果你看到... | 立即执行 | 完整路径 |
|--------------|---------|---------|
| 不知道从何入手 | `sys-audit` | 自动扫描全景，识别真瓶颈 |
| 某 PID CPU 异常高 | `bottleneck-trace --comm <name>` | [模式 A](./references/methodology.md#模式-a单进程-cpu-高) |
| 整个系统都很慢 | `sys-audit` | [模式 B](./references/methodology.md#模式-b系统整体缓慢) |
| 大量进程频繁创建 | `get-comm-top`（查看Spawn Rate） | [模式 C](./references/methodology.md#模式-c进程风暴) |
| 单核满载其他空闲 | `analyze-core-distribution` | [模式 D](./references/methodology.md#模式-d负载不均衡) |
| kernel 开销高 | `cluster-paths` | [模式 E](./references/methodology.md#模式-e高内核态分析) |
| 某进程组CPU高 | `get-comm-top` | 查看CV/Monopoly指标 |
| 突发性能下降 | `detect-anomalies` | 定位异常时刻 |

---

## 📚 文档分层

```
┌─ 第一层：快速开始（本文档）
│   └─ 场景速查 + 核心概念
│
├─ 第二层：分析方法论 [methodology.md](./references/methodology.md)
│   └─ 三层架构驱动的完整方法论（决策树、指标解读、陷阱对策）
│
├─ 第三层：典型分析模式 [methodology.md](./references/methodology.md#附录-a典型分析模式)
│   └─ 5 种典型场景的速查路径
│
└─ 第四层：工具参考 [tools.md](./references/tools.md)
    └─ 命令参数速查
```

---

## 🎯 核心原则

### 1. 三候选准则（强制执行）

**任何分析必须同时维护 ≥3 条竞争性假设**，延迟收敛：

| 维度 | 示例假设 |
|------|---------|
| 代码 | 热点函数算法复杂度高 |
| 架构 | 全局锁导致串行化 |
| 环境 | Cgroup CPU 限制 |

### 2. 驱动力分析

识别性能问题的第一推动力：
- **请求流量驱动**: Workload 增加
- **系统资源驱动**: 内核瓶颈、资源争抢
- **内部机制驱动**: GC、定时任务、缓存刷新

### 3. 关键检查点

| 信号 | 必须动作 | 工具 |
|------|---------|------|
| 调度函数高 | 溯源：主动休眠 vs 被动抢占 | `find-callers --target schedule` |
| 负载不均衡 | 分析：不能并行 vs 不想并行 | `analyze-core-distribution` |
| 锁函数出现 | 评估：锁粒度和竞争范围 | `find-callers --target <lock>` |

---

## 📝 文档规范（⚠️ 强制执行）

### 双文档体系

| 文档 | 格式 | 用途 | 创建方式 |
|------|------|------|---------|
| **诊断报告** | `debug/*.md` | 主文档：问题演进、假设追踪、审计记录 | 手动基于 templates.md |
| **状态追踪** | Trace | 辅助：待办问题列表 | `trace init` 自动生成 |

**关键规则**：
1. `Trace` **不能替代** `debug/*.md`
2. 所有证据、推理、结论必须写入 `debug/*.md`
3. `trace add/complete` 只是状态标记，分析内容要在 markdown 中详细记录

### 诊断流程

```bash
# 1. 初始化诊断文档
spear trace init --data perf.data

# 2. 执行分析，自动/手动记录 issues
spear get-comm-top
spear cluster-paths --comm netstat
...

# 3. 查看待处理 issues
spear trace issues

# 4. 完成分析，标记 resolved（result 必须详细）
spear trace complete --id ISS-001 --result "根因: xxx - 详见 debug/analysis.md"

# 5. 确认所有 issues 已解决
spear trace issues --status open

# 6. finalize 结束诊断
spear trace finalize

# 7. 导出报告
spear trace export --format markdown --output report.md
```

---

## 🛠️ 核心工具速查

### 6个原子工具

| 工具 | 层级 | 用途 | 典型场景 |
|------|------|------|---------|
| `analyze-core-distribution` | 系统级 | 核心负载分析、单核饱和检测 | 负载不均衡检查 |
| `detect-anomalies` | 时间级 | 时序异常定位 | 突发问题分析 |
| `get-comm-top` | 实体级 | 进程组分析（聚合+离群+风暴） | 大量小进程、单点瓶颈 |
| `get-hotspots` | 函数级 | 热点函数识别 | `--sort-by self/inclusive` |
| `find-callers` | 关系级 | 热点溯源 | `--target <func>` |
| `cluster-paths` | 模式级 | 调用路径聚类 | 业务逻辑定位 |

### 2个综合诊断入口

不知道从何入手？两个都来一轮：

```bash
# 第一轮：系统全景扫描（自动降噪 + 危害排序）
spear sys-audit

# 第二轮：深度追踪瓶颈进程（根据第一轮输出选择）
spear bottleneck-trace --comm <瓶颈进程名>
```

---

## ⚠️ 典型陷阱

| 陷阱 | 表现 | 自检问题 |
|------|------|---------|
| 过早收敛 | 看到一条证据立即下结论 | 是否列出 ≥3 条竞争性假设？ |
| 忽视领域背景 | 只关注数值，不问是否符合应有表现 | 是否建立预期 vs 现实对比？ |
| 参数遗漏 | `find-callers` 忘记 `--pid` | 分析目标与工具参数是否一致？ |
| 单因思维 | 强制找单一根因 | 是否考虑多因素叠加？ |

---

## 📖 完整参考

- 📗 **分析方法论**: [methodology.md](./references/methodology.md) - 三层架构驱动的完整方法论
- 📘 **典型分析模式**: [methodology.md](./references/methodology.md#附录-a典型分析模式) - 5 种场景的速查路径
- 📙 **工具命令参考**: [tools.md](./references/tools.md) - 详细命令、参数
- 📋 **文档模板**: [templates.md](./references/templates.md) - 诊断报告格式
