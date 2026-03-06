# Trace-Todo 联动：Attention Steering 方案

> 基于核心洞察：**Todo Tool 权重很高 → Prompt + Attention Steering 即可驱动联动**
>
> 无需代码修改，纯 Prompt 工程实现。

---

## 核心洞察

### 为什么 Prompt + Attention Steering 足够？

根据 `docs/todo_tool_close_analysis.md`：

```
┌─────────────────────────────────────────────────────────┐
│  Todo Tool 驱动机制分析                                  │
├─────────────────────────────────────────────────────────┤
│  模型训练效果: 70% ✅ (内化行为模式)                      │
│  Prompt 工程: 30% ⚠️ (软性建议)                          │
│  代码强制: 0% ❌ (无强制逻辑)                            │
├─────────────────────────────────────────────────────────┤
│  结论: 模型对 Todo 工具高度敏感                          │
│  → 通过精心设计的 Prompt + Attention Steering 即可驱动   │
└─────────────────────────────────────────────────────────┘
```

**关键认知**：
- 模型已经内化 "任务分解 → 执行 → 完成确认" 的流程
- Todo 工具在模型决策中权重很高（复杂任务自动创建）
- **只要让模型"看到"Trace issues，它就会自然创建对应的 Todo**

---

## 设计原则

```
┌─────────────────────────────────────────────────────────────┐
│                 Attention Steering 原则                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 标签即权重 (Label = Weight)                              │
│     <XT0> = Trace-Todo 联动（最高优先级）                    │
│                                                              │
│  2. 重复强化 (Repetition Reinforcement)                      │
│     每次 trace issues 输出都携带 <XT0> 标记                  │
│                                                              │
│  3. 上下文关联 (Context Association)                         │
│     Trace issues 自动关联到 Todo 创建                        │
│                                                              │
│  4. 行动直接 (Action Direct)                                 │
│     <XA> 标记直接给出具体操作建议                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 方案架构

### 三层注意力注入

```
┌─────────────────────────────────────────────────────────────┐
│                   三层注意力注入架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: SKILL.md (全局上下文)                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ description: "... X0=critical | XT0=trace-todo-sync"  │  │
│  │          ↑                                            │  │
│  │   进入 System Prompt，最高权重                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           ▼                                  │
│  Layer 2: 工具输出 (触发时刺激)                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ shecr trace issues 输出:                              │  │
│  │   "<XT0> 发现 N 个未处理 issues"                      │  │
│  │   "<XA> 立即创建对应 Todo: [Trace] ISS-XXX: ..."      │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           ▼                                  │
│  Layer 3: AGENTS.md (环境提醒)                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ "注意：本目录检测到 .shecr.json，诊断时请保持        │  │
│  │        Trace issues 与 Todo 同步"                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 具体实现

### Layer 1: SKILL.md 增强

```yaml
---
name: SHECR-perf-hunter
description: |
  SHECR: **S**ystematic **H**ypothesis **E**vidence **C**ontrolled **R**easoning performance diagnostic tools
  X0=critical | X1=major | X2=Minor | XA=action
  XT0=trace-todo-sync | XT1=trace-pending | XT2=trace-info
  Use when analyzing CPU bottlenecks...
---
```

**新增 XT 系列标签定义**：

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<XT0>` | Trace-Todo 阻塞级 | 必须立即创建对应 Todo |
| `<XT1>` | Trace-Todo 重要级 | 建议创建对应 Todo |
| `<XT2>` | Trace-Todo 信息级 | Trace 状态提示 |
| `<XT-A>` | Trace-Todo 行动 | 具体同步操作建议 |

**SKILL.md 新增章节**：

```markdown
## Trace-Todo 联动规范 (XT Protocol)

### 触发条件

当满足以下任一条件时，**必须**执行 Trace-Todo 同步：

```
<XT0> 触发条件:
- 执行 shecr trace issues 发现 open issues
- 执行 shecr trace add 创建了新 issue
- 当前目录存在 .shecr.json 且有未解决问题
```

### 同步规则

**Rule 1: Issue → Todo (创建时)**
```
<XT0> 每个 open issue 必须对应一个 Todo
   ↓
Title 格式: "[Trace] {ISS-ID}: {简要描述}"
Status: pending 或 in_progress
```

**Rule 2: Todo → Trace (完成时)**
```
<XT0> 完成 [Trace] 前缀的 Todo 前，必须先执行 trace complete
   ↓
shecr trace complete --id {ISS-ID} --result "分析结论"
   ↓
然后标记 Todo 为 done
```

**Rule 3: 最终检查**
```
<XT0> 所有 Todo 标记为 done 前，必须确认:
   - shecr trace issues --status open 返回空
   - 或保留对应的 [Trace] Todo 为未完成状态
```

### 典型联动流程

```bash
# 1. 初始化诊断 (自动触发 XT0)
shecr trace init --data perf.data
# <XT0> 诊断环境已初始化，准备创建追踪任务

# 2. 系统审计 (可能自动创建 issues)
shecr sys-audit
# 输出: <XT0> 发现 2 个关键问题，需要创建对应 Todo
#        - ISS-001: netstat 高内核态
#        - ISS-002: containerd-shim 锁竞争
# <XA> 执行: SetTodoList 创建 [Trace] ISS-001 和 [Trace] ISS-002

# 3. 创建联动 Todo
SetTodoList(todos=[
  {"title": "[Trace] ISS-001: 分析 netstat 高内核态", "status": "pending"},
  {"title": "[Trace] ISS-002: 分析 containerd-shim 锁竞争", "status": "pending"}
])
# <XT1> Trace-Todo 同步完成，2 个任务待处理

# 4. 分析并解决
shecr trace complete --id ISS-001 --result "根因: ..."
SetTodoList(todos=[
  {"title": "[Trace] ISS-001: 分析 netstat 高内核态", "status": "done"},  # ← 先完成 Trace
  {"title": "[Trace] ISS-002: 分析 containerd-shim 锁竞争", "status": "in_progress"}
])

# 5. 最终确认
shecr trace finalize
# <XT0> 所有 issues 已解决，可以结束诊断
```
```

---

### Layer 2: 工具输出增强

#### `shecr trace issues` 输出格式

```python
# 修改 scripts/perf_toolkit/cli/commands/trace/issues.py

def format_issues_with_steering(issues, status_filter='all'):
    """带 Attention Steering 的 issues 格式化"""
    
    open_issues = [i for i in issues if i['status'] == 'open']
    resolved_issues = [i for i in issues if i['status'] == 'resolved']
    
    lines = []
    lines.append("=" * 65)
    lines.append(f"ISSUES ({len(open_issues)} open, {len(resolved_issues)} resolved)")
    lines.append("=" * 65)
    
    if open_issues:
        lines.append("")
        lines.append(f"<XT0> 发现 {len(open_issues)} 个待处理问题:")
        lines.append("")
        
        for issue in open_issues:
            level = issue.get('level', 'warning').upper()
            desc = issue['desc'][:40]
            hint = issue.get('hint', '')
            
            lines.append(f"  [{level}] {issue['id']}: {desc}")
            if hint:
                lines.append(f"      └─ Hint: {hint}")
        
        lines.append("")
        lines.append("-" * 65)
        lines.append("<XT0> 同步要求: 以上每个 issue 必须创建对应 Todo")
        lines.append("<XT-A> 执行: SetTodoList 添加 '[Trace] {ISS-ID}: ...' 格式任务")
        lines.append("-" * 65)
    
    if resolved_issues:
        lines.append("")
        lines.append(f"<XT2> 已解决 ({len(resolved_issues)}):")
        for issue in resolved_issues:
            lines.append(f"  ✓ {issue['id']}: {issue.get('result', 'No result')[:40]}")
    
    lines.append("=" * 65)
    return "\n".join(lines)
```

**输出示例**：

```
=================================================================
ISSUES (2 open, 1 resolved)
=================================================================

<XT0> 发现 2 个待处理问题:

  [CRITICAL] ISS-001: netstat 高内核态 94.7%
      └─ Hint: cluster-symbols --comm netstat
  [WARNING] ISS-002: containerd-shim 高内核态 89.9%
      └─ Hint: cluster-symbols --comm containerd-shim

-----------------------------------------------------------------
<XT0> 同步要求: 以上每个 issue 必须创建对应 Todo
<XT-A> 执行: SetTodoList 添加 '[Trace] {ISS-ID}: ...' 格式任务
-----------------------------------------------------------------

<XT2> 已解决 (1):
  ✓ ISS-003: 负载均衡问题 → 已优化调度策略

=================================================================
```

#### `shecr trace complete` 输出增强

```
[COMPLETED] ISS-001
→ Result: spinlock_wait 85% - 数据库查询触发锁竞争

<XT1> 对应的 [Trace] Todo 可以标记为 done
<XT-A> 执行: SetTodoList 更新 "[Trace] ISS-001: ..." 状态为 done
```

#### `shecr trace finalize` 输出增强

```
=================================================================
FINALIZE - Ready to generate report?
=================================================================

<XT0> 所有 issues 已解决 (3/3)
<XT0> 确认所有 [Trace] Todo 已标记为 done

[READY] 可以生成最终报告
=================================================================
```

---

### Layer 3: AGENTS.md 环境提醒

```markdown
## Attention Flags (本目录)

```
当前目录: /home/tiny/skills/perf-hunter
检测状态: .shecr.json 存在
```

### 当前 XT 状态

<XT0> Trace-Todo 联动: **激活**
- 未处理 issues: 2 (ISS-001, ISS-002)
- 同步要求: 每个 issue 必须有对应 [Trace] Todo

### 快速检查

```bash
# 查看待处理 issues
shecr trace issues

# 创建联动 Todo
SetTodoList(todos=[
  {"title": "[Trace] ISS-001: 分析...", "status": "pending"},
  ...
])

# 确认全部完成
shecr trace finalize
```
```

---

## Attention Steering 矩阵

### XT 标签使用矩阵

| 场景 | 标签 | 位置 | 目的 |
|------|------|------|------|
| 发现 open issues | `<XT0>` | 工具输出开头 | 最高优先级提醒 |
| 提示创建 Todo | `<XT-A>` | 工具输出末尾 | 具体操作建议 |
| 完成 issue | `<XT1>` | complete 输出 | 提示更新 Todo |
| finalize 就绪 | `<XT0>` | finalize 输出 | 双重确认 |
| 延迟同步 | `<XT2>` | 信息提示 | 低优先级提醒 |

### 标签频率策略

```
高频重复: <XT0> - 每次 trace 相关操作都出现
中频提示: <XT-A> - 需要行动时出现  
低频确认: <XT1> - 完成时出现
状态标记: <XT2> - 状态展示时使用
```

---

## 验证方案

### 如何验证 Attention Steering 有效

```
┌─────────────────────────────────────────────────────────────┐
│               XT Protocol 效果验证                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  测试场景 1: 首次进入 perf-hunter 目录                      │
│  预期: AGENTS.md 中的 XT 状态被模型读取                     │
│  验证: 模型自动询问是否需要查看 issues                       │
│                                                              │
│  测试场景 2: 执行 shecr trace issues                        │
│  预期: 输出中的 <XT0> 触发模型创建 Todo                      │
│  验证: 模型调用 SetTodoList 创建 [Trace] 格式任务           │
│                                                              │
│  测试场景 3: 试图完成所有任务                               │
│  预期: <XT0> 记忆触发，模型先检查 trace finalize            │
│  验证: 模型执行 shecr trace finalize 确认 issues 状态       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 实施清单

### 需要修改的文件

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `SKILL.md` | 添加 XT Protocol 章节，更新 description | P0 |
| `AGENTS.md` | 添加 XT 状态提醒 | P0 |
| `scripts/perf_toolkit/cli/commands/trace/issues.py` | 输出添加 XT 标签 | P0 |
| `scripts/perf_toolkit/cli/commands/trace/complete.py` | 输出添加 XT1/XT-A | P1 |
| `scripts/perf_toolkit/cli/commands/trace/finalize.py` | 输出添加 XT0 | P1 |
| `references/templates.md` | 诊断报告模板添加 XT 标记示例 | P2 |

### 不修改的文件

| 文件 | 原因 |
|------|------|
| `kimi-cli` 源码 | 纯 Prompt 方案，零代码侵入 |
| `SetTodoList` 工具 | 不修改工具实现，只通过输出引导 |

---

## 与代码方案对比

| 维度 | Attention Steering (本方案) | 代码 Patch 方案 |
|------|---------------------------|----------------|
| **实现成本** | 低 (改文案) | 中 (改代码) |
| **维护成本** | 极低 | 低 |
| **侵入性** | 零侵入 | 低侵入 |
| **强制程度** | 依赖模型训练 (高) | 代码层强制 (最高) |
| **可移植性** | 高 (可复制到其他 skill) | 低 (绑定 kimi-cli) |
| **回滚难度** | 极易 | 易 |
| **依赖假设** | Todo Tool 权重高 ✅ | kimi-cli 允许修改 ✅ |

---

## 总结

```
┌─────────────────────────────────────────────────────────────┐
│           Trace-Todo Attention Steering 方案总结              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  核心理念: Todo Tool 权重高 → Prompt + Attention 足够驱动    │
│                                                              │
│  关键设计:                                                   │
│    • XT0/XT1/XT2/XT-A 标签体系                              │
│    • 三层注意力注入 (SKILL/工具输出/AGENTS)                  │
│    • 高频重复强化模型记忆                                    │
│                                                              │
│  实施要点:                                                   │
│    • SKILL.md 定义 XT Protocol                               │
│    • trace 命令输出携带 XT 标签                              │
│    • AGENTS.md 环境状态提醒                                  │
│                                                              │
│  零侵入: 不修改 kimi-cli 源码，纯 Prompt 工程                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 附录：XT 标签速查表

```markdown
## XT (eXtra Trace) 标签速查

| 标签 | 全称 | 含义 | 触发动作 |
|------|------|------|---------|
| `<XT0>` | eXtra Trace Critical | Trace-Todo 阻塞级 | 必须立即同步 |
| `<XT1>` | eXtra Trace Major | Trace-Todo 重要级 | 建议同步 |
| `<XT2>` | eXtra Trace Minor | Trace-Todo 信息级 | 状态提示 |
| `<XT-A>` | eXtra Trace Action | Trace-Todo 行动 | 具体操作建议 |

## 使用规范

1. `<XT0>` 必须成对出现：发现问题 + 解决方案
2. `<XT-A>` 必须紧跟可执行的具体命令
3. 同一输出中 `<XT0>` 不超过 3 次，避免注意力稀释
```
