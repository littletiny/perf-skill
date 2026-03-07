---
name: systematic-hypothesis-evidence-controlled-reasoning
description: |
  SHECR: **S**ystematic **H**ypothesis **E**vidence **C**ontrolled **R**easoning performance diagnostic tools
  X0=critical | X1=major | X2=Minor | XA=action
---

# SHECR 性能诊断

```
S - Systematic: topdown-bottomup结合，系统级→时间级→实体级→函数级→模式级
H - Hypothesis: 假设驱动,根据符号语义和风险点构建搜索空间
E - Evidence: 证据优先，数据说话，拒绝主观臆断
C - Controlled: 受控收敛，<X0>追踪到根因前禁止过早下结论
R - Reasoning: 逻辑推理，因果追踪，第一推动力分析
```

通过"领域知识驱动的假设验证"实现根因定位。

---

## 快速初始化

```bash
scripts/shecr init --data-path <perf.data> [--freq <hz>]

shecr get-hotspots --comm myapp
shecr analyze-core-distribution
shecr find-callers --target pthread_mutex_lock
```

---

## 典型场景速查

| 如果你看到... | 立即执行 |
|--------------|---------|
| 不知道从何入手 | `sys-audit` |
| 某 PID CPU 异常高 | `bottleneck-analyze --comm <name> --pid<pid> ` |
| 整个系统都很慢 | `sys-audit` |
| 单核满载其他空闲 | `analyze-core-distribution` |
| kernel 开销高 | `cluster-paths, get-hotspots` |
| 某进程组CPU高 | `get-comm-top`, 查看CV/Monopoly指标 |
| 突发性能突变 | `detect-anomalies` |

---

## 相关文档

- **分析方法论** [methodology.md](./references/methodology.md), topdown-bottomup架构驱动的完整方法论
- **工具参考**: [tools.md](./references/tools.md), 参数速查
-  **文档模板**: [templates.md](./references/templates.md), 诊断报告格式

---

## 核心原则（SHECR 五原则）

### S - Systematic（系统性）
**topdown-bottomup结合**：

| 层级 | 工具 | 关注点 |
|------|------|--------|
| 系统级 | `sys-audit, bottleneck-analyze` | 系统异常追踪 |
| 时间级 | `detect-anomalies` | 时序异常、突发变化 |
| 实体级 | `get-comm-top` | 进程组、聚合分析 |
| 函数级 | `get-hotspots`, `find-callers` | 热点函数、调用关系 |
| 模式级 | `cluster-paths` | 调用模式、业务语义 |

### H - Hypothesis（假设驱动）
**Catastrophe requires multiple failures – single point failures are not enough.**
**大胆假设**: 根据暴露的风险项，逐个假设可能的原因
**semantics**: 根据各种符号名合理推测业务领域，联想相关领域知识，避免无序发散

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

### R - Reasoning（逻辑推理）
**因果追踪，识别第一推动力**：

| 驱动力类型 | 识别方法 | 典型表现 |
|-----------|---------|---------|
| 请求流量驱动 | Workload 监控 | 吞吐量与延迟同步上升 |
| 系统资源驱动 | 内核态占比、锁竞争 | `__lock_*` 或 `schedule` 高频 |
| 内部机制驱动 | 时序模式分析 | 周期性抖动、GC 规律出现 |

---

## 文档规范（SHECR 强制执行）

基于 **SHECR** 五原则的双文档体系：

| 原则 | 文档 | 格式 | 用途 |
|------|------|------|------|
| **S**ystematic | 诊断报告 | `debug/*.md` | 系统级→模式级的完整分析 |
| **H**ypothesis | 诊断报告 | `debug/*.md` | 问题演进表、假设追踪 |
| **E**vidence | 诊断报告 | `debug/*.md` | 证据链记录 |
| **C**ontrolled | Trace | `.shecr.json` | 待办状态、审计标记 |
| **R**easoning | 诊断报告 | `debug/*.md` | 根因分析、第一推动力 |

**关键规则**：
1. 所有证据、推理、结论必须写入 `debug/*.md`
2. Trace和文档双线并行
3. 文档格式参考references/template.md

### SHECR 诊断流程

```bash

# 初始化诊断环境
shecr trace init --data perf.data
# 根据用户输入，初始化debug/*.md，拆解详细的问题现象，初步根据问题领域知识构建合理猜想

# H - Hypothesis: 根据符号语义和风险点构建搜索空间
shecr sys-audit           # 系统级假设验证
shecr bottleneck-analyze [--pid <pid>]  # 深度假设追踪
# 按照template.md规范更新debug/*.md，记录问题，猜想，推论

# E - Evidence: 自动/手动记录 issues（基于证据）
shecr trace add --desc "<X0> 锁竞争证据..." --level critical

# C - Controlled: 查看待处理 issues，控制收敛
shecr trace issues

# R - Reasoning: 完成分析，标记根因追踪完成
# 更新debug/*.md，更新问题现状
shecr trace complete --id ISS-001 --result "根因: ..."

# C - Controlled: 确认所有 <X0> 已解决
shecr trace issues --status open

# 确保所有isses关闭
shecr trace finalize

# 导出最终报告
shecr trace export --format markdown --output report.md
# 整理最终的 debug/*.md 文档
```

---

## 核心工具速查

### 原子工具

| 工具 | 层级 | 用途 | 典型场景 |
|------|------|------|---------|
| `detect-anomalies` | 时间级 | 时序异常定位 | 突发问题分析 |
| `get-comm-top` | 实体级 | 进程组分析（聚合+离群） | 大量小进程、单点瓶颈 |
| `get-hotspots` | 函数级 | 热点函数识别 | `--sort-by self/inclusive` |
| `find-callers` | 关系级 | 热点溯源 | `--target <func>` |
| `cluster-paths` | 模式级 | 调用路径聚类 | 业务逻辑定位 |

### **2个综合诊断入口**

不知道从何入手？两个都来一轮：

```bash
# 第一轮：系统全景扫描（自动降噪 + 危害排序）
shecr sys-audit

# 第二轮：深度追踪瓶颈进程（根据原始问题/第一轮输出选择）
shecr bottleneck-analyze --comm <瓶颈进程名>
shecr bottleneck-analyze --pid <pid>
```

---

## **典型陷阱**

| 陷阱 | 表现 | 自检问题 |
|------|------|---------|
| 过早收敛 | 看到一条证据立即下结论 | 是否列出足够多的假设？ |
| 忽视领域背景 | 只关注数值，不问是否符合应有表现 | 是否建立预期 vs 现实对比？ |
| 参数遗漏 | `find-callers` 忘记 `--pid` | 分析目标与工具参数是否一致？ |
| 单因思维 | 强制找单一根因 | 是否考虑多因素叠加？ |

---

## 诊断关注点（SHECR Attention Flags）

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
<X0> 单核饱和：单核利用率
<X0> 高内核态：内核态占比

<X1> 负载不均衡：CV > 1.5

<XA> 执行 find-callers --target <func> --pid <pid> 溯源热点
<XA> 执行 bottleneck-analyze --comm <name> --pid <pid> 深度追踪
```
---
