# Trace-Todo 联动设计

> 基于 `docs/todo_tool_close_analysis.md` 分析结论：Todo Tool 有效使用 ≈ 70% 模型训练 + 30% Prompt 工程
> 
> 本设计通过 **双向同步 + 智能提示** 实现 Trace Issues 与 Todo List 的联动。

---

## 核心洞察

### 为什么不能代码强制？

根据 `todo_tool_close_analysis.md` 的分析：

```
┌─────────────────────────────────────────────────────────┐
│  Todo Tool 驱动机制：纯模型驱动                          │
│  ├── 代码层面：无强制逻辑 ❌                             │
│  ├── Prompt 层面：软性建议 ⚠️                            │
│  └── 模型训练：内化行为模式 ✅（主要驱动力）              │
└─────────────────────────────────────────────────────────┘
```

**结论**：联动机制不能依赖代码强制，必须利用模型的**内化行为模式** + **精心设计的 Prompt 引导**。

---

## 设计目标

```
┌─────────────────────────────────────────────────────────────┐
│                    Trace-Todo 联动目标                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Trace Issues                    Todo List                  │
│   ┌─────────┐  ① 自动同步      ┌─────────┐                  │
│   │ ISS-001 │ ───────────────→ │ [ ]     │                  │
│   │ ISS-002 │                  │ [ ]     │                  │
│   └─────────┘                  └─────────┘                  │
│        ↑                            │                       │
│        └──────── ② 状态反馈 ←───────┘                       │
│                                                              │
│   ③ 统一视图：shecr trace issues 显示双状态                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 联动原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **自动同步** | Trace 新增 issue → 自动建议创建 Todo | Prompt 引导 + 工具输出提示 |
| **双向反馈** | Todo 完成 → 建议更新 Trace | Prompt 引导 + 状态检查 |
| **模型驱动** | 不代码强制，依赖模型自主决策 | 训练效果 + 精心设计的 Prompt |
| **无侵入** | 不修改现有 Trace/Todo 代码逻辑 | 纯 Prompt 层联动 |

---

## 联动机制设计

### 机制一：Issue → Todo 自动同步建议

**触发时机**：执行 `shecr trace issues` 或工具自动创建 issue 时

**Prompt 引导策略**：

```markdown
## Trace-Todo 联动规则

当 Trace 中存在 open issues 时：

1. **自动检查**: 执行 `shecr trace issues` 后，检查返回的 open issues
2. **创建对应 Todo**: 对每个 open issue，建议创建对应的 todo item
   - Title 格式: `[Trace] ISS-XXX: <issue描述>`
   - Status: pending 或 in_progress
3. **优先级映射**:
   - ISS level=critical → Todo 优先处理
   - ISS level=warning → Todo 正常处理
   - ISS level=info → Todo 可选处理

示例联动:
```
Trace Issue: ISS-001 [CRITICAL] netstat 锁竞争
      ↓
Todo: "[Trace] ISS-001: 分析 netstat 锁竞争问题"
```
```

**工具输出增强** (`shecr trace issues`)：

```
=================================================================
OPEN ISSUES (2 remaining)
=================================================================

⚠️  ISS-001 [CRITICAL] netstat 高内核态 94.7%
    └─ 建议: cluster-symbols --comm netstat
    
    [TODO联动] 建议创建 todo: "[Trace] ISS-001: 分析 netstat 高内核态"

⚠️  ISS-002 [WARNING] containerd-shim 高内核态 89.9%
    └─ 建议: cluster-symbols --comm containerd-shim
    
    [TODO联动] 建议创建 todo: "[Trace] ISS-002: 分析 containerd-shim 高内核态"

=================================================================
[提示] 使用 SetTodoList 创建对应任务，保持 Trace-Todo 同步
=================================================================
```

### 机制二：Todo 完成 → Trace 更新建议

**触发时机**：模型将 Todo 标记为 done 时

**Prompt 引导策略**：

```markdown
## Todo 完成时的 Trace 联动

当完成一个与 Trace 相关的 Todo 时：

1. **识别 Trace 关联**: 检查完成的 todo title 是否包含 `[Trace] ISS-XXX`
2. **提示更新 Trace**: 建议执行 `shecr trace complete` 标记对应 issue
3. **结果同步**: 将 todo 的完成结果作为 trace complete 的 result 参数

示例联动:
```
Todo 完成: "[Trace] ISS-001: 分析 netstat 锁竞争问题"
      ↓
建议执行: shecr trace complete --id ISS-001 --result "<分析结论>"
```
```

**SKILL.md 更新**（添加到诊断流程）：

```markdown
### Trace-Todo 联动流程

```bash
# 1. 查看待处理 issues（输出会提示创建对应 todo）
shecr trace issues

# 2. 创建联动 Todo（推荐按此格式）
# 模型应自动调用: SetTodoList with title="[Trace] ISS-001: xxx"

# 3. 执行分析任务...

# 4. 完成 Todo 时（模型应提示更新 Trace）
# 建议执行: shecr trace complete --id ISS-001 --result "..."

# 5. 确认同步状态
shecr trace issues  # 检查 ISS-001 是否已 resolved
```
```

### 机制三：统一状态视图

**增强 `shecr trace issues` 输出**：

```
=================================================================
TRACE-TODO 联动状态
=================================================================

ISS-001 [CRITICAL] netstat 高内核态 94.7%
  ├─ Status: open
  ├─ Trace Hint: cluster-symbols --comm netstat
  ├─ Todo Status: ✅ 已创建 (in_progress)  ← 联动状态
  └─ Action: 分析完成后执行 trace complete

ISS-002 [WARNING] containerd-shim 高内核态 89.9%
  ├─ Status: open
  ├─ Trace Hint: cluster-symbols --comm containerd-shim
  ├─ Todo Status: ❌ 未创建 Todo  ← 提示创建
  └─ Action: 建议创建 todo: "[Trace] ISS-002: ..."

=================================================================
```

---

## 实现方案

### 方案 A：Prompt 层联动（推荐）

**实现复杂度**: ⭐⭐
**效果**: ⭐⭐⭐⭐
**侵入性**: 无

```
┌─────────────────────────────────────────────────────────────┐
│                   Prompt 层联动架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ SKILL.md    │───→│  Prompt     │───→│  模型行为    │      │
│  │ 联动规则     │    │  引导       │    │  内化        │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐                          │
│  │ 工具输出    │───→│  联动提示   │                          │
│  │ 增强        │    │  [TODO联动] │                          │
│  └─────────────┘    └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**改动点**：
1. 更新 `SKILL.md` - 添加 Trace-Todo 联动章节
2. 增强 `shecr trace issues` 输出 - 添加 `[TODO联动]` 提示
3. 更新 `references/templates.md` - 诊断报告模板中体现联动

### 方案 B：代码层弱联动

**实现复杂度**: ⭐⭐⭐
**效果**: ⭐⭐⭐⭐⭐
**侵入性**: 低

```python
# scripts/perf_toolkit/core/trace_todo_bridge.py

class TraceTodoBridge:
    """Trace 与 Todo 的弱联动桥接
    
    不强制，仅提供辅助信息和状态检查
    """
    
    def suggest_todos_for_issues(self, trace_path: str) -> List[Dict]:
        """根据 open issues 建议创建的 todos"""
        trace = Trace(trace_path)
        suggestions = []
        for issue in trace.get_open_issues():
            suggestions.append({
                "suggested_title": f"[Trace] {issue['id']}: {issue['desc'][:40]}",
                "issue_id": issue['id'],
                "priority": self._map_priority(issue['level']),
                "hint": f"分析完成后执行: shecr trace complete --id {issue['id']} --result '...'"
            })
        return suggestions
    
    def check_sync_status(self, trace_path: str, todos: List[Dict]) -> SyncStatus:
        """检查 Trace Issues 与 Todo List 的同步状态"""
        # 返回哪些 issue 已/未创建对应 todo
        pass
```

**改动点**：
1. 新增 `trace_todo_bridge.py` - 桥接模块
2. 增强 `shecr trace issues` - 显示同步状态
3. 可选 CLI 命令: `shecr trace sync-check`

### 方案对比

| 维度 | 方案 A: Prompt 层 | 方案 B: 代码层弱联动 |
|------|------------------|---------------------|
| 实现成本 | 低 | 中 |
| 维护成本 | 低 | 中 |
| 模型依赖 | 高（依赖训练效果） | 中（辅助信息） |
| 强制程度 | 无（纯建议） | 无（弱辅助） |
| 可扩展性 | 高 | 中 |
| **推荐度** | **⭐⭐⭐⭐⭐** | ⭐⭐⭐⭐ |

---

## 推荐实现：方案 A + 部分 B

### Phase 1: Prompt 层联动（立即实施）

1. **更新 SKILL.md**
   - 添加 "Trace-Todo 联动规范" 章节
   - 更新诊断流程示例

2. **增强工具输出**
   - `shecr trace issues` 添加 `[TODO联动]` 提示
   - `shecr trace complete` 完成后提示更新 Todo

3. **更新 AGENTS.md**
   - 说明联动机制的存在和用途

### Phase 2: 辅助状态检查（可选）

1. **新增 `trace sync-check` 命令**（可选）
   ```bash
   shecr trace sync-check
   # 输出:
   # ISS-001: open → Todo: 已创建 (in_progress)
   # ISS-002: open → Todo: 未创建 ⚠️
   ```

2. **状态桥接模块**
   - 仅提供辅助信息，不强制任何行为

---

## Prompt 设计

### SKILL.md 新增章节

```markdown
## Trace-Todo 联动规范

### 为什么需要联动？

Trace 记录诊断过程中的 issues（长期持久化），Todo 管理当前任务（短期执行）。
联动确保：
- 每个 Trace issue 都有对应的执行计划
- 任务完成后同步更新状态

### 联动规则

**Rule 1: Issue → Todo**
```
当 shecr trace issues 显示 open issues 时：
→ 自动调用 SetTodoList 创建对应任务
→ Title 格式: "[Trace] ISS-XXX: <描述>"
```

**Rule 2: Todo → Trace**
```
当完成一个 [Trace] 前缀的 Todo 时：
→ 提示执行 shecr trace complete --id ISS-XXX --result "结论"
```

**Rule 3: 状态检查**
```
定期执行 shecr trace issues 确认：
- 所有 open issues 都有对应 Todo
- 所有 done Todo 的 Issue 都已 resolved
```
```

### 工具输出增强示例

```python
# 在 trace issues 输出末尾添加

if open_issues:
    print("\n" + "="*65)
    print("[TODO联动] 建议创建以下任务：")
    for issue in open_issues:
        print(f"  - SetTodoList: '[Trace] {issue['id']}: {issue['desc'][:30]}...'")
    print("="*65)
```

---

## 验证方案

### 如何验证联动有效？

根据 `todo_tool_close_analysis.md` 的方法论：

```
┌─────────────────────────────────────────────────────────┐
│  联动效果验证（观察模型行为）                              │
├─────────────────────────────────────────────────────────┤
│  1. 给定场景：Trace 中有 2 个 open issues                │
│  2. 观察：模型是否自动创建对应 Todo？                    │
│  3. 观察：Todo 完成后是否提示更新 Trace？                │
│  4. 观察：finalize 前是否检查 Todo 状态？                │
└─────────────────────────────────────────────────────────┘
```

### 预期行为模式

| 场景 | 预期模型行为 |
|------|-------------|
| 执行 `trace issues` 看到 open issues | 自动 SetTodoList 创建对应任务 |
| 分析完成，准备标记 Todo done | 先执行 `trace complete` 再更新 Todo |
| 执行 `trace finalize` | 检查所有 [Trace] Todo 是否已 done |

---

## 总结

```
┌─────────────────────────────────────────────────────────────┐
│                   Trace-Todo 联动设计总结                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  核心原则: 利用模型内化行为，而非代码强制                      │
│                                                              │
│  实现方式: Prompt 引导 + 工具输出增强                         │
│                                                              │
│  双向联动:                                                    │
│    Trace Issue ──→ Todo (自动建议创建)                       │
│         ↑____________↓ (完成后提示更新)                       │
│                                                              │
│  关键成功因素:                                                │
│    ✓ 清晰的 Prompt 规则                                       │
│    ✓ 明显的 [TODO联动] 提示                                  │
│    ✓ 符合模型训练的行为模式                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 附录：待修改文件清单

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `SKILL.md` | 添加 "Trace-Todo 联动规范" 章节 | P0 |
| `scripts/perf_toolkit/cli/commands/trace/issues.py` | 输出添加 `[TODO联动]` 提示 | P0 |
| `AGENTS.md` | 说明联动机制 | P1 |
| `references/templates.md` | 诊断报告模板体现联动 | P1 |
| `scripts/perf_toolkit/core/trace_todo_bridge.py` | 可选桥接模块 | P2 |
