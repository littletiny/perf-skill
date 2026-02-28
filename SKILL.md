---
name: SPEAR-perf-hunter
description: Systematic Linux performance diagnosis using SPEAR methodology. Use when analyzing CPU bottlenecks, high latency, resource contention, or performance regression in Linux environments.
---

# SPEAR 性能诊断

> **S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning

通过"领域知识驱动的假设验证"实现根因定位。

---

## ⚡ 三分钟开始

```bash
# 1. 创建诊断文档（强制执行）
mkdir -p debug
# 使用 references/templates.md 创建 debug/[问题描述].md

# 2. 初始化状态追踪
python3 $SKILL_DIR/scripts/perf_expert.py doc init --data <perf.data>

# 3. 提出三候选假说（在诊断文档中记录）
# - 假说 A: 代码维度（热点函数、算法复杂度）
# - 假说 B: 架构维度（锁竞争、线程池配置）
# - 假说 C: 环境维度（资源限制、内核瓶颈）
```

**环境变量**: `SKILL_DIR` = skill 根目录

---

## 🔍 典型场景速查

| 如果你看到... | 立即执行 | 完整路径 |
|--------------|---------|---------|
| 某 PID CPU 异常高 | `get-hotspots --pid <PID>` | [模式 A](./references/workflow-patterns.md#模式-a-单进程-cpu-高) |
| 整个系统都很慢 | `check-cpu-bottleneck` | [模式 B](./references/workflow-patterns.md#模式-b-系统整体缓慢) |
| 大量进程频繁创建 | `count-process-variety` | [模式 C](./references/workflow-patterns.md#模式-c-进程风暴) |
| 单核满载其他空闲 | `analyze-core-distribution` | [模式 D](./references/workflow-patterns.md#模式-d-负载不均衡) |
| kernel% > 50% | `cluster-symbols` | [模式 E](./references/workflow-patterns.md#模式-e-高内核态分析) |

**工具路径**: `$SKILL_DIR/scripts/perf_expert.py`

---

## 📚 文档分层

```
┌─ 第一层：快速开始（本文档）
│   └─ 场景速查 + 核心概念
│
├─ 第二层：分析模式 [workflow-patterns.md](./references/workflow-patterns.md)
│   └─ 5 种典型场景的完整分析路径
│
├─ 第三层：核心流程 [workflow.md](./references/workflow.md)
│   └─ 7 Phase 分析流程详解
│
├─ 第四层：工具参考 [tools.md](./references/tools.md)
│   └─ 命令参数速查
│
└─ 第五层：规则手册 [heuristics.md](./references/heuristics.md)
    └─ 五大认知闭包、问题边界判定
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

### 3. V 型对称模型

```
      宏观确认（Top-down）
           ↓
    资源定界 → 异常识别 → 搜索空间收敛
           ↓
    热点溯源（Bottom-up）
           ↓
    负载语义 → 领域建模 → 根因定位
           ↓
      因果验证（交汇点）
```

### 4. 关键检查点

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
| **状态追踪** | Live Document | 辅助：待办问题列表 | `doc init` 自动生成 |

**关键规则**：
1. `Live Document` **不能替代** `debug/*.md`
2. 所有证据、推理、结论必须写入 `debug/*.md`
3. `doc add/complete` 只是状态标记，分析内容要在 markdown 中详细记录

### 强制审计流程

```bash
# 发现问题时记录
perf-expert.py doc add --id ISS-001 --desc "高内核态" --hint "cluster-symbols"

# 每 2-3 个工具后审计
perf-expert.py doc list

# 生成报告前最终审计
perf-expert.py doc finalize
```

---

## 🛠️ 核心工具速查

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `check-cpu-bottleneck` | 资源限制判定 | 环境边界检查 |
| `show-cpu-usage` | CPU 利用率概览 | user/kernel 分解 |
| `get-comm-top` | 进程组资源识别 | 大量小进程集体消耗 |
| `get-hotspots` | 热点函数识别 | `--sort-by self/inclusive` |
| `find-callers` | 热点溯源 | `--target <func>` |
| `cluster-symbols` | 语义规则聚类 | `EVENT_LOCK_CONTENTION` |
| `analyze-core-distribution` | 核心级负载分析 | 负载不均衡检查 |
| `count-process-variety` | 进程风暴检测 | 短生命周期进程 |

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

- 📗 **典型分析模式**: [workflow-patterns.md](./references/workflow-patterns.md) - 5 种场景的完整路径
- 📘 **核心流程详解**: [workflow.md](./references/workflow.md) - 7 Phase 分析流程
- 📙 **工具命令参考**: [tools.md](./references/tools.md) - 详细命令、参数
- 📕 **启发式规则**: [heuristics.md](./references/heuristics.md) - 五大认知闭包
- 📋 **文档模板**: [templates.md](./references/templates.md) - 诊断报告格式
