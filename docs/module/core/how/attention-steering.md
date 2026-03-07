# Attention Steering 设计文档

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                           S.H.E.C.R 方法论                                ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  S → Systematic    │ 三层架构：系统级 → 时间级 → 实体级 → 函数级 → 模式级  ║
║  H → Hypothesis    │ 三候选准则：任何分析必须同时维护 ≥3 条竞争性假设       ║
║  E → Evidence      │ 证据驱动：基于数据验证，拒绝主观臆断                   ║
║  C → Controlled    │ 受控收敛：<X0> 标记必须追踪到根因，禁止过早收敛       ║
║  R → Reasoning     │ 逻辑推理：因果追踪，识别第一推动力                   ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

> 版本: 3.0
> 更新时间: 2026-03-03

---

## 核心思想

**标签 = 注意力开关**

当标签出现在文本中时，其后的内容自动获得更高权重。无需复杂解析，LLM 对 `<X0>`、`<XA>` 等标记天然敏感。

```
<X0> 检测到锁竞争
 ↑    ↑
 │    └── 获得注意力的内容
 └─────── 注意力开关（高亮标记）
```

---

## SHECR 方法论详解

| 字母 | 全称 | 核心原则 | 在 Attention Steering 中的体现 |
|------|------|----------|------------------------------|
| **S** | **S**ystematic | 系统性方法 | 三层架构驱动诊断流程（Core/Analysis/Composite） |
| **H** | **H**ypothesis | 假设驱动 | `<X0>` 必须追踪到根因才能收敛（延迟收敛） |
| **E** | **E**vidence-driven | 证据优先 | `<XA>` 基于证据的行动建议，每个标签都有数据支撑 |
| **C** | **C**ontrolled | 受控收敛 | 多轮 Pipeline 控制收敛节奏，审计轮检查 <X0> |
| **R** | **R**easoning | 逻辑推理 | 因果关系追踪，从现象到根因的逻辑链条 |

### 核心洞察：Label = Weight

**标签本身就是注意力权重。**

当 `<X0>` 出现在 context 中时，其后的 token 自动获得更高注意力分数。不需要完整句子，不需要复杂语法——标签就是权重开关。

使用 **X 前缀**（X0/X1/XA）避免与日常单词冲突：
- X = eXpert / eXtreme（极端重要）
- 0/1/A = 优先级编码

```
<X0> lock,kernel,saturation
 ↑      ↑
 │      └── 获得更高权重的 token
 └───────── 权重开关（attention gate）
```

### 设计原则

| 原则 | 说明 |
|------|------|
| **Label 即权重** | 看到 `<P0>`，后面的内容自然被重视 |
| **极简表达** | 只放 label + level，10-20 词足够 |
| **重复强化** | Tool output 中反复出现，持续刺激 |
| **分层定义** | Description 放关键词，Body 放完整定义 |

---

## Skill 加载机制

根据 kimi-cli 源码分析：

```
System Prompt 始终包含：
├── 基础指令（代码规范、工具使用等）
├── ${KIMI_WORK_DIR} 等环境变量
├── ${KIMI_AGENTS_MD}      ← 项目根目录的 AGENTS.md
├── ${KIMI_SKILLS}         ← Skill 列表（name + description）
└── ...

Skill 触发后额外加载：
└── SKILL.md body          ← 完整诊断指南
```

### 分层权重策略

| 位置 | 内容 | 作用 |
|------|------|------|
| **Description** | `X0=lock,kernel` | System Prompt 中，关键词预敏感 |
| **Tool Output** | `<X0> 检测到锁竞争` | 每次诊断时重复刺激 |
| **Skill Body** | 完整定义 + 规则 | 触发后补充细节 |

### 当前实现

```yaml
# SKILL.md frontmatter
description: |
  SPEAR methodology for Linux performance diagnosis.
  X0=lock,kernel,saturation | X1=storm,unbalanced | XA=action
  Use when analyzing CPU bottlenecks...
```

**Steering Tokens 层级**：
1. **SPEAR** - 方法论锚点，激活系统性诊断思维
2. **X0/X1/XA** - 优先级标签，引导具体关注点
3. **关键词**（lock/kernel/storm）- 领域线索

**Token 统计**：
- 13 个核心 steering tokens
- `SPEAR` + `X0`/`X1`/`XA` 进入 system prompt
- **全大写/ X 前缀**：双重保障避免与日常单词冲突

---

## 标签规范

### 预定义级别标签

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<P0>` | 阻塞级 | 必须立即处理，完成后才能继续 |
| `<P1>` | 重要级 | 应在当前阶段处理 |
| `<P2>` | 提示级 | 值得关注，但非紧急 |
| `<HINT>` | 动作建议 | 具体的下一步操作 |

### 使用原则

1. **标签即权重**：看到 `<P0>` 就知道后面内容是最高优先级
2. **简洁直接**：标签后紧跟描述，无需额外格式
3. **多轮保持**：一旦标记 `<P0>`，后续诊断不要遗忘
4. **收敛门槛**：`<P0>` 标记的内容必须追踪到根因

---

## 使用示例

### 在 SKILL.md 中定义关注点

```markdown
## 诊断关注点

<P0> 锁竞争：__lock、mutex、spinlock 等符号热点
<P0> 单核饱和：单核利用率 > 90% 且 Monopoly > 0.8  
<P0> 高内核态：内核态占比 > 50%

<P1> 进程风暴：Spawn Rate > 10/s
<P1> 负载不均衡：CV > 1.5

<HINT> 执行 find-callers --target <func> 溯源热点
<HINT> 执行 bottleneck-analyze --comm <name> 深度分析
```

### 在工具输出中使用

```json
{
  "_risk": {
    "level": "warning",
    "message": "<P0> 检测到锁竞争热点 __lock_text_start",
    "hint": "<HINT> 执行 find-callers --target __lock_text_start",
    "patterns": ["LOCK_CONTENTION"]
  }
}
```

### 在诊断报告中标记

```markdown
## 分析发现

1. <P0> 锁竞争严重
   - 证据：__lock_text_start 占 CPU 45%
   - 根因：mysql_query 调用路径中存在全局锁
   - 状态：已追踪完成

2. <P1> 进程创建频繁
   - 证据：spawn rate 12/s
   - 待确认：是否为预期的健康检查行为
```

---

## 触发条件对照表

| 标签 | 触发条件 | 典型场景 |
|------|----------|----------|
| `<P0>` | 锁相关符号在热点 top10 | __lock, mutex, spinlock, futex 高频 |
| `<P0>` | 单核利用率 > 90% 且 Monopoly > 0.8 | 单点瓶颈，其他核心空闲 |
| `<P0>` | 内核态占比 > 50% | 系统调用过多、内核瓶颈 |
| `<P1>` | Spawn Rate > 10/s | 频繁创建销毁进程 |
| `<P1>` | CV > 1.5 | 多进程负载严重不均衡 |
| `<P1>` | schedule 函数占比高 | 调度开销大，需区分主动/被动休眠 |
| `<P2>` | syscall 入口在热点 top10 | 用户态频繁陷入内核 |
| `<P2>` | page_fault 高频 | 内存分配压力大 |

---

## 与现有系统集成

### 与 `_risk` 字段的集成

现有 `_risk` 结构无需修改，在 `message` 和 `hint` 中直接嵌入标签：

```python
# 示例：工具输出构建
risk = {
    "level": "warning",
    "message": "<X0> 单核饱和 (CPU5 利用率 95%)",
    "hint": "<XA> 执行 bottleneck-analyze --comm worker",
    "patterns": ["SINGLE_CORE_SATURATION"]
}
```

### 与 Trace 系统的集成

创建 issue 时携带标签：

```bash
shecr trace add --desc "<X0> 检测到锁竞争" --id ISS-001
```

### 与 Pipeline Agent 的集成

在 Agent 的系统 prompt 中增加：

```markdown
## Attention Steering

文本中出现以下标记时，自动提升后续内容的处理优先级：
- <X0> = 立即处理，追踪到根因前禁止收敛
- <X1> = 当前阶段处理
- <X2> = 有时间再处理
- <XA> = 建议执行的操作

多轮诊断规则：
- 第一轮识别的 <X0>，后续轮次必须保持关注
- 审计轮检查：所有 <X0> 是否都已追踪到根因
```

---

## 实施步骤

1. **更新 SKILL.md**：增加「诊断关注点」章节，使用 `<P0>`、`<P1>`、`<HINT>` 格式
2. **更新 AGENTS.md**：说明标签机制的存在和用途
3. **更新工具输出**：在 `_risk.message` 和 `_risk.hint` 中嵌入优先级标签
4. **更新文档模板**：在 `references/templates.md` 中示范标签使用

---

## 设计优势

| 特性 | 说明 |
|------|------|
| **极简** | 无需解析复杂语法，标签即意义 |
| **独特** | X 前缀避免与日常单词（Priority/High/Medium）冲突 |
| **灵活** | 标签后内容可自由描述，不受格式约束 |
| **兼容** | 可嵌入现有文本字段（message/hint/markdown） |
| **有效** | `<>` 符号和 X 标记对 LLM 注意力有天然引导作用 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0 | 2026-03-03 | 简化方案：从复杂属性标签改为预定义级别标签 |
| 2.1 | 2026-03-03 | 补充 Skill 加载机制说明（基于 kimi-cli 源码分析） |
| 2.2 | 2026-03-03 | 标签改为 X 前缀（X0/X1/XA），避免与日常单词冲突 |
| 3.0 | 2026-03-03 | 方法论升级为 SHECR（Systematic Hypothesis Evidence-driven Controlled Reasoning） |
| 1.0 | 2026-03-03 | 初始设计：`<FLAG: XXX p=P0 action=...>` 格式 |
