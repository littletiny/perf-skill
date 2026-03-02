---
name: SHECR-perf-hunter
description: |
  SHECR: **S**ystematic **H**ypothesis **E**vidence **C**ontrolled **R**easoning performance diagnostic tools
  X0=critical | X1=major | X2=Minor | XA=action
---

# SHECR 性能诊断

```
┌─────────────────────────────────────────────────────────────┐
│  S - Systematic    │ 三层架构驱动，系统级→时间级→实体级→函数级→模式级  │
│  H - Hypothesis    │ 三假设准则，延迟收敛（≥3条竞争性假设并行验证）     │
│  E - Evidence      │ 证据优先，数据说话，拒绝主观臆断                  │
│  C - Controlled    │ 受控收敛，<X0>追踪到根因前禁止过早下结论          │
│  R - Reasoning     │ 逻辑推理，因果追踪，第一推动力分析                │
└─────────────────────────────────────────────────────────────┘
```

通过"领域知识驱动的假设验证"实现根因定位。

**最新更新**: 工具集已精简为 6 个核心工具 + 3 个组合命令，详见 [design-three-tier-architecture.md](./docs/design-three-tier-architecture.md)

---

## ⚡ 三分钟开始

### 快速初始化（推荐）

```bash
# 1. 使用 wrap 脚本初始化（自动配置路径）
scripts/shecr init --data-path <perf.data> [--freq <hz>]

# 2. 后续命令大幅简化（自动注入 --data）
shecr get-hotspots --comm myapp
shecr analyze-core-distribution
shecr find-callers --target pthread_mutex_lock

# 3. 查看配置状态
shecr status
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

## 🎯 核心原则（SHECR 五原则）

### S - Systematic（系统性）
**三层架构驱动诊断**：

| 层级 | 工具 | 关注点 |
|------|------|--------|
| 系统级 | `analyze-core-distribution` | 整体资源分布、单核饱和 |
| 时间级 | `detect-anomalies` | 时序异常、突发变化 |
| 实体级 | `get-comm-top` | 进程组、聚合分析 |
| 函数级 | `get-hotspots`, `find-callers` | 热点函数、调用关系 |
| 模式级 | `cluster-paths` | 调用模式、业务语义 |

### H - Hypothesis（假设驱动）
**三候选准则（强制执行）**：任何分析必须同时维护 ≥3 条竞争性假设，延迟收敛

| 维度 | 示例假设 | 验证方式 |
|------|---------|---------|
| 代码 | 热点函数算法复杂度高 | `get-hotspots` + 代码审查 |
| 架构 | 全局锁导致串行化 | `find-callers` 溯源锁竞争 |
| 环境 | Cgroup CPU 限制 | `analyze-core-distribution` |

### E - Evidence（证据驱动）
**数据说话，拒绝主观臆断**：

| 证据类型 | 获取方式 | 可信度要求 |
|---------|---------|-----------|
| 热点证据 | `get-hotspots` | self% ≥ 5% 或 inclusive% ≥ 10% |
| 调用链证据 | `find-callers` | 完整的 caller → callee 链条 |
| 时序证据 | `detect-anomalies` | 时间窗口内突变 ≥ 2σ |

### C - Controlled（受控收敛）
**禁止过早下结论**：

- `<X0>` 标记的阻塞级问题必须追踪到根因才能收敛
- 多轮诊断中保持对已识别 `<X0>` 的关注
- 审计轮检查：所有 `<X0>` 是否都已追踪到根因

### R - Reasoning（逻辑推理）
**因果追踪，识别第一推动力**：

| 驱动力类型 | 识别方法 | 典型表现 |
|-----------|---------|---------|
| 请求流量驱动 | Workload 监控 | 吞吐量与延迟同步上升 |
| 系统资源驱动 | 内核态占比、锁竞争 | `__lock_*` 或 `schedule` 高频 |
| 内部机制驱动 | 时序模式分析 | 周期性抖动、GC 规律出现 |

---

## 📝 文档规范（SHECR 强制执行）

基于 **SHECR** 五原则的双文档体系：

| 原则 | 文档 | 格式 | 用途 |
|------|------|------|------|
| **S**ystematic | 诊断报告 | `debug/*.md` | 系统级→模式级的完整分析 |
| **H**ypothesis | 诊断报告 | `debug/*.md` | 问题演进表、假设追踪 |
| **E**vidence | 诊断报告 | `debug/*.md` | 证据链记录 |
| **C**ontrolled | Trace | `.shecr.json` | 待办状态、审计标记 |
| **R**easoning | 诊断报告 | `debug/*.md` | 根因分析、第一推动力 |

**关键规则**：
1. `Trace` **不能替代** `debug/*.md`（E/R 必须在 markdown 中详细记录）
2. 所有证据、推理、结论必须写入 `debug/*.md`（对应 E/R）
3. `trace add/complete` 只是状态标记（对应 C），分析内容要在 markdown 中详细记录

### SHECR 诊断流程

```bash
# S - Systematic: 初始化诊断环境
shecr trace init --data perf.data

# H - Hypothesis: 执行分析，维护 ≥3 条假设
shecr sys-audit           # 系统级假设验证
shecr bottleneck-trace    # 深度假设追踪

# E - Evidence: 自动/手动记录 issues（基于证据）
shecr trace add --desc "<X0> 锁竞争证据..." --level critical

# C - Controlled: 查看待处理 issues，控制收敛
shecr trace issues

# R - Reasoning: 完成分析，标记根因追踪完成
shecr trace complete --id ISS-001 --result "根因: ..."

# C - Controlled: 确认所有 <X0> 已解决
shecr trace issues --status open

shecr trace finalize

# 导出最终报告
shecr trace export --format markdown --output report.md
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
shecr sys-audit

# 第二轮：深度追踪瓶颈进程（根据第一轮输出选择）
shecr bottleneck-trace --comm <瓶颈进程名>
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

## 🎯 诊断关注点（SHECR Attention Flags）

基于 **SHECR** 方法论的注意力引导机制：

```
┌────────────────────────────────────────────────────────────┐
│  X0  →  Critical（阻塞级）  │  对应 H/C：必须追踪到根因才收敛   │
│  X1  →  Major（重要级）     │  对应 S：应在当前阶段处理         │
│  X2  →  Minor（提示级）     │  对应 R：辅助推理线索             │
│  XA  →  Action（操作建议）  │  对应 E：基于证据的具体行动       │
└────────────────────────────────────────────────────────────┘
```

### 标记含义

| 标记 | 全称 | 处理要求 | 对应 SHECR |
|------|------|----------|-----------|
| `<X0>` | eXtreme Critical | 必须立即处理，追踪到根因前禁止收敛 | **H**ypothesis + **C**ontrolled |
| `<X1>` | eXtreme Major | 应在当前阶段处理 | **S**ystematic |
| `<X2>` | eXtreme Minor | 值得关注，但非紧急 | **R**easoning |
| `<XA>` | eXtreme Action | 具体的下一步操作 | **E**vidence-driven |

### 常见关注点

```markdown
<X0> 锁竞争：__lock、mutex、spinlock 等符号热点
<X0> 单核饱和：单核利用率 > 90% 且 Monopoly > 0.8  
<X0> 高内核态：内核态占比 > 50%

<X1> 进程风暴：Spawn Rate > 10/s
<X1> 负载不均衡：CV > 1.5

<XA> 执行 find-callers --target <func> 溯源热点
<XA> 执行 bottleneck-trace --comm <name> 深度追踪
```

### 使用规则（对应 SHECR 五原则）

| 规则 | SHECR 原则 | 说明 |
|------|-----------|------|
| **`<X0>` 立即处理** | **S**ystematic | 按三层架构系统排查，不遗漏 |
| **`<X0>` 追踪到根因** | **H**ypothesis | 满足三候选准则才收敛 |
| **`<XA>` 直接执行** | **E**vidence-driven | 每个行动都有数据支撑 |
| **多轮保持关注** | **C**ontrolled | 已识别的 `<X0>` 不要遗忘 |
| **因果追踪** | **R**easoning | 从现象到根因的逻辑链条 |

---

## 📖 完整参考

- 📗 **分析方法论**: [methodology.md](./references/methodology.md) - 三层架构驱动的完整方法论
- 📘 **典型分析模式**: [methodology.md](./references/methodology.md#附录-a典型分析模式) - 5 种场景的速查路径
- 📙 **工具命令参考**: [tools.md](./references/tools.md) - 详细命令、参数
- 📋 **文档模板**: [templates.md](./references/templates.md) - 诊断报告格式
