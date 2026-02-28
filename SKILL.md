---
name: SPEAR-perf-hunter
description: Systematic Linux performance diagnosis using SPEAR methodology. Use when analyzing CPU bottlenecks, high latency, resource contention, or performance regression in Linux environments - especially with Cgroup constraints, time-aggregated data (1s), or complex multi-threaded applications.
---

# SPEAR 性能诊断

> **S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning
> 通过"领域知识驱动的假设验证"实现根因定位


## 快速开始

### ⚠️ 第一步：创建诊断文档（强制执行）

**在开始任何分析之前，必须立即执行：**

```bash
# 1. 创建 debug 目录并基于模板创建诊断文档
mkdir -p debug

# 2. 初始化 Live Document（用于问题状态追踪）
python3 $SKILL_DIR/scripts/perf_expert.py doc init --data <perf.data>
```

**为什么必须创建 debug/*.md？**
- 这是诊断过程的**主记录文档**，包含问题演进记录、竞争性假设追踪、深度审计记录
- `doc init` 创建只是**辅助状态追踪**，不能替代 markdown 文档
- 所有关键发现、证据链、推理过程必须写入 `debug/*.md`

---

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
| 📊 数据格式 | 输入数据格式说明 | `references/data-format.md` |
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

## 文档规范（⚠️ 强制执行）

### 文档体系说明

SPEAR 使用**双文档体系**：

| 文档 | 格式 | 用途 | 创建方式 |
|------|------|------|---------|
| **诊断报告** | `debug/*.md` | **主文档**：问题演进、假设追踪、审计记录、结论 | 手动基于模板创建 |
| **状态追踪** | Live Document | **辅助**：待办问题列表、完成状态 | `doc init` 自动生成 |

**关键规则**：
1. **`Live Document` 不能替代 `debug/*.md`** ——  只记录问题状态，不记录分析过程
2. **所有证据、推理、结论必须写入 `debug/*.md`** —— 这是诊断的可复现基础
3. **`doc add/complete` 只是状态标记** —— 真正的分析内容要在 markdown 中详细记录

### 第一步：创建诊断文档

**在开始任何分析之前，立即执行：**

```bash
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

## Live Document 机制（状态追踪辅助工具）

### 机制概述

Live Document 是诊断过程的**辅助状态追踪工具**，用于跟踪待验证问题的状态（pending/completed），防止遗漏关键问题。

**⚠️ 重要：Live Document 不能替代 `debug/*.md` 主文档**

| 对比项 | `debug/*.md` 主文档 | Live Document |
|--------|---------------------|-------------------------------|
| **内容** | 完整的问题演进、假设、证据、推理 | 仅问题ID、描述、状态 |
| **创建方式** | 手动基于模板创建 | `doc init` 自动生成 |
| **维护方式** | 用编辑器填写表格和记录 | `doc add/complete` 命令更新 |
| **作用** | 诊断过程的可复现记录 | 防止遗漏待办问题的检查清单 |
| **必要性** | **必须有** | 辅助工具 |

**核心命令** (通过 `perf_expert.py doc <command>` 调用):

| 命令 | 用途 | 示例 |
|------|------|------|
| `doc init` | 初始化状态追踪 | `doc init --data perf.data` |
| `doc add` | 记录发现的问题（仅标记状态） | `doc add --id ISS-001 --desc "高内核态" --risk "全局风险"` |
| `doc complete` | 标记问题已分析 | `doc complete --id ISS-001 --result "锁竞争 38%"` |
| `doc list` | 查看待办列表 | `doc list` |
| `doc finalize` | 最终审计（生成报告前必须执行） | `doc finalize` |

### 强制审计规则

**⚠️ 非常重要**: 以下规则必须严格遵守，否则可能导致诊断遗漏。

**1. 发现问题时必须记录**

当工具输出显示多个潜在问题时（如 `get-comm-top` 显示多个高内核态进程组），**根据方法论记录hint，并使用`doc add`记录所有问题**：

```bash
# 发现 4 个高内核态进程组，全部记录
perf-expert.py doc add --id ISS-001 --desc "redis 内核开销 94.7%" \
  --risk "内核负载过高" --hint "cluster-symbols --comm redis"
perf-expert.py doc add --id ISS-002 --desc "xxxx 高内核态 89.9%" \
  --risk "单进程影响可能更大" --hint "cluster-symbols --comm xxxx"
# ... 继续记录其他问题
```

**2. 定期执行审计检查: perf-expert.py doc list**

**每次要对当前问题输出结论之前，必须审计**：
**每次按照方法论完成一轮问题追踪后，必须审计**

```bash
perf-expert.py doc list
```

**3. 生成报告前必须最终审计**

**在生成最终诊断报告前，必须执行 finalize**：

```bash
perf-expert.py doc finalize
```

### 禁止行为

#### 文档相关（严重）
- ❌ **只执行 `doc init` 而不创建 `debug/*.md`** —— Live Document 不能替代主诊断文档
- ❌ **`debug/*.md` 中缺少问题演进记录表** —— 无法追踪问题定义的变化
- ❌ **`debug/*.md` 中少于3条竞争性假设** —— 搜索空间不足，容易过早收敛
- ❌ **只在 Live Document 中记录状态，不在 markdown 中记录分析过程** —— 诊断不可复现

#### 流程相关
- ❌ **未执行 `doc init` 直接开始分析** —— 无法跟踪问题状态
- ❌ **发现多个问题只记录一个** —— 导致搜索覆盖率不足
- ❌ **`pending` 列表不为空时生成最终报告** —— 可能遗漏关键问题
- ❌ **未执行 `doc finalize` 结束诊断** —— 无法确认审计完整性

### 典型使用流程

```bash
# ===== Phase 1: 问题定义（强制执行） =====

# 1. 创建 debug 目录和主诊断文档

# 2. 【关键】用编辑器填写 debug/*.md 中的表格：
#    - 问题演进记录表（V1/V2/V3...）
#    - 竞争性假设追踪表（至少3条假设：主动消耗/被动压制/其他）
#    - 深度审计记录（后续填写）

# 3. 初始化 Live Document（辅助状态追踪）
perf-expert.py doc init --data xxx.data

# ===== Phase 2-6: 分析与证据收集 =====

# 4. 宏观评估，发现问题
perf-expert.py get-comm-top --data xxx.data
# 发现: 异常1，异常2

# 5. 在 Live Document 中标记待办问题（同时在 debug/*.md 中记录详细分析）
perf-expert.py doc add --id ISS-001 --desc "netstat进程风暴" \
  --risk "系统开销激增" --hint "cluster-symbols --comm netstat"
# 【同时写入 debug/*.md】: 问题演进记录V2、假设验证状态更新

# 6. 循证分析
perf-expert.py cluster-symbols --comm netstat --data xxx.data
perf-expert.py find-callers --target established_get_first --comm netstat --data xxx.data
# 【同时写入 debug/*.md】: 深度审计记录（工具输出、调用链、机制发现、推论）

# 7. 标记问题完成
perf-expert.py doc complete --id ISS-001 --result "PROCESS_STORM + LOCK_CONTENTION"
# 【同时写入 debug/*.md】: 假设追踪表状态更新为"确认"

# 8. 定期审计检查
perf-expert.py doc list
# 输出: 1 pending → 继续分析下一个问题

# ===== Phase 7: 最终审计与报告 =====

# 9. 最终审计（强制执行）
perf-expert.py doc finalize
# 【同时完成 debug/*.md】: 全局审计检查清单

# 10. 诊断报告已在 debug/*.md 中完成，可选导出 Live Document 摘要
perf-expert.py doc export --format markdown --output summary.md
```

**关键原则**：`doc add/complete` 只是状态标记，真正的分析内容（证据、调用链、推理）必须写入 `debug/*.md`！

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
