---
name: SPEAR-perf-hunter
description: Systematic Linux performance diagnosis using SPEAR methodology. Use when analyzing CPU bottlenecks, high latency, resource contention, or performance regression in Linux environments - especially with Cgroup constraints, low-frequency sampling (19Hz), or complex multi-threaded applications. Requires perf script data with core/s field as input.
---

# SPEAR 性能诊断

> **S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning
> 通过"领域知识驱动的假设验证"实现根因定位


## 快速开始

**工具路径**: `$SKILL_DIR/scripts/perf_expert.py`

环境变量 `SKILL_DIR` 为 skill 的根目录路径。

```bash
python3 $SKILL_DIR/scripts/perf_expert.py <子命令> [选项]
```

**使用工具之前仔细阅读 `references/tools.md` 和 `references/workflow.md` 文档**
💡 每个子命令均支持 `--help` 参数获取完整帮助

## 参考文档

| 文档 | 内容 | 路径 |
|------|------|------|
| 📗 分析流程 | 标准工作流程、典型分析模式 | `references/workflow.md` |
| 📘 工具命令 | 详细命令、参数、使用说明 | `references/tools.md` |
| 📕 启发式规则 | 五大认知闭包、诊断规则 | `references/heuristics.md` |
| 📊 数据格式 | perf script 解析、core/s 说明 | `references/data-format.md` |
| 📋 文档模板 | 诊断报告格式、检查清单 | `references/templates.md` |


---

## 核心原则

### 1. 领域知识优先于工具
- **建立预期先于验证**: 识别应用类型，建立性能预期基线
- **工具服务于假设**: 验证"为什么现实不符合预期"，而非"发现热点"
- **异常驱动分析**: 发现"预期 vs 现实"差距才需深入分析

### 2. 竞争性假设并行验证
- **延迟收敛**: 同时维护 ≥3 条竞争性假设，避免过早下结论
- **证伪优先**: 证据用于证伪假设，而非证实假设
- **多因叠加**: 保留多因素共同作用的可能性

### 3. 逻辑可溯源
- **结论附带证据**: 具体到工具输出、函数名、调用链
- **假设可证伪**: 每个假设必须有"预期指纹"和"验证方法"
- **过程可复刻**: 完整记录在 `debug/*.md` 文档中

---

## 标准工作流

```
Step 1: 领域认知与预期建立
    ↓ 识别应用类型，建立预期基线
Step 2: 假设空间构建
    ↓ 枚举 ≥3 条竞争性假设（机制、指纹、验证、证伪）
Step 3: 机制评估与剪枝
    ↓ 基于领域知识评估可行性，排除不可能路径
Step 4: 循证深挖
    ↓ 并行验证高置信度假设，收集证据
Step 5: 全局审计
    ↓ 确保结论解释所有异常，证据链闭环
结论输出
```

### 各步骤要点

所有的关键信息都需要文档记录

| 步骤 | 核心动作 | 关键输出 |
|------|---------|---------|
| **Step 1** | 分析原始问题，记录关键信息。识别应用类型，激活领域知识，对比预期 vs 现实 | 异常判定 |
| **Step 2** | 假设格式：机制、预期指纹、验证方法、证伪条件 | 假设列表 ≥3 条 |
| **Step 3** | 机制可行性评估（是否符合领域知识？） | 剪枝后的假设 |
| **Step 4** | 工具验证：`check-cpu-bottleneck` → `analyze-core-distribution` → `get-hotspots` → `find-callers` | 深度审计记录 |
| **Step 5** | 检查：所有异常解释？孤证？领域表现？证据闭环？ | 根因结论 |

### 关键检查点

| 信号 | 必须动作 | 工具 | 参数策略 |
|------|---------|------|---------|
| 调度函数高 | 溯源：主动休眠 vs 被动抢占 | `find-callers --target schedule` | 用户指定 PID → 加 `--pid`<br>系统级分析 → 不加 |
| 负载不均衡 | 分析：不能并行 vs 不想并行 | `analyze-core-distribution` | 用户指定 PID → 加 `--pid`<br>系统级分析 → 不加 |
| 锁函数出现 | 评估：锁粒度和竞争范围 | `find-callers --target <lock>` | 用户指定 PID → 加 `--pid`<br>全局锁竞争 → 不加 |
| 单进程 CPU 异常 | 对比：是否符合其角色定位 | `get-hotspots --pid <PID>` | **必须加** `--pid` |
| 系统整体缓慢 | 检查：内核瓶颈/全局锁 | `get-hotspots` / `cluster-symbols` | **不加** `--pid`，系统级视图 |

---

## 文档规范（⚠️ 分析前必读）

### 第一步：创建诊断文档

**在开始分析之前，立即创建 `debug/[问题描述].md` 文档，使用 `references/templates.md` 中的完整模板。**

📋 **模板文件**: `references/templates.md` - 包含完整的诊断报告结构：
- 问题演进记录（双表结构之一）
- 竞争性假设追踪（双表结构之二）
- 深度审计记录
- 全局审计检查清单
- 优化建议与验证方案

### 双表结构说明

在诊断文档中必须维护以下两个表格：

1. **问题演进记录**: 问题定义版本迭代和关键证据引用
2. **竞争性假设追踪**: 假设、机制评估、预期指纹、验证状态

### 证据引用格式
- 工具输出: `<工具名>: <关键指标> (样本数/可靠性)`
- 调用链: `caller → callee → ...`
- 数据定位: `CPU核心/时间戳/进程ID`

---

## 典型陷阱与自检

| 陷阱 | 表现 | 自检问题 |
|------|------|---------|
| 过早收敛 | 看到一条证据立即下结论 | 是否列出 ≥3 条竞争性假设？ |
| 忽视领域背景 | 只关注数值，不问是否符合应有表现 | 是否建立预期 vs 现实对比？ |
| 工具驱动 | "执行 get-hotspots"而非"验证为什么 CPU 低" | 是否明确要验证的假设？ |
| 忽视异常信号 | 看到调度函数不溯源，负载不均不分析 | 所有异常信号是否得到解释？ |
| 单因思维 | 强制找单一根因 | 是否考虑多因素叠加？ |

---

## 核心工具速查

| 工具 | 用途 | 场景 |
|------|------|------|
| `check-cpu-bottleneck` | 资源限制判定 | 环境边界检查 |
| `show-cpu-usage` | CPU 利用率概览 | user/kernel 分解 |
| `analyze-core-distribution` | 核心级负载分析 | 负载不均衡检查 |
| `get-hotspots` | 热点函数识别 | `--sort-by self/inclusive` |
| `find-callers` | 热点溯源 | `--target <func>` 或 `--auto-target` |
| `cluster-symbols` | 语义规则聚类 | `EVENT_LOCK_CONTENTION` 等 |
| `detect-anomalies` | 时序异常检测 | `SPIKE/DROP/BURST` |
| `count-process-variety` | 进程风暴检测 | 短生命周期进程 |
