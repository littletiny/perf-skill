# Todo Tool Close 机制分析报告

## 核心结论

**Todo Tool 的有效使用 ≈ 70% 模型训练效果 + 30% Prompt 工程**

代码层面**不存在任何强制机制**保证 todo list 被正确关闭。

---

## 1. 驱动机制：纯模型驱动

### 1.1 无代码强制

| 组件 | 是否有强制逻辑 | 证据 |
|------|--------------|------|
| `kimisoul.py` | ❌ 无 | `_step()` 调用 `kosong.step()`，被动接收模型选择的 tool_calls |
| `agent.yaml` | ❌ 无 | 仅声明工具可用，不强制调用时机 |
| `system.md` | ❌ 无 | 系统提示词中无强制使用 todo 的指令 |
| `set_todo_list.md` | ⚠️ 软性建议 | 仅描述性指导："Once you finished a subtask...remember to update" |

### 1.2 调用链

```
模型生成 tool_call → kosong.step() → KimiToolset.handle() → SetTodoList.__call__()
```

整个过程**模型是唯一的决策者**，代码只负责执行。

---

## 2. 为什么模型通常会正确关闭 todo？

### 2.1 训练效果（70%）

代码中没有任何机制强制：
- ❌ 开始任务时必须创建 todo
- ❌ 子任务完成后必须更新状态
- ❌ 所有任务结束前必须标记为 done

但实际运行中模型**通常**会：
- ✅ 复杂任务自动创建 todo
- ✅ 完成子任务后主动更新状态
- ✅ 最终标记所有任务为 done

**行为模式来源**：

| 训练来源 | 作用 |
|---------|------|
| **Tool Use 训练** | 模型学会根据工具描述自主决定调用时机 |
| **Task Planning 训练** | 模型理解"任务分解 → 执行 → 完成确认"的流程 |
| **Instruction Following** | 模型遵守 "Once you finished...remember to update" 这类软性指令 |
| **Code Agent 训练数据** | 类似 Claude Code、Cursor 等工具的使用模式被内化 |

### 2.2 Prompt 工程（30%）

`set_todo_list.md` 中的关键软性约束：

```markdown
Todo list is a simple yet powerful tool to help you get things done. 
You typically want to use this tool when the given task involves 
multiple subtasks/milestones...

Once you finished a subtask/milestone, remember to update the todo list 
to reflect the progress. Also, you can give yourself a self-encouragement 
to keep you motivated.
```

这种 "建议型" prompt 依赖模型的**指令遵循能力**来执行。

---

## 3. 状态流转设计

```
pending → in_progress → done
   ↑________________________|
         (模型可任意回退/修改)
```

- **全量更新模式**：每次调用必须传完整列表，模型可随时修改任意任务状态
- **无状态持久化**：`SetTodoList` 不存储状态，仅将参数转换为 `TodoDisplayBlock` 返回

### 3.1 工具定义

```python
class Todo(BaseModel):
    title: str = Field(description="The title of the todo", min_length=1)
    status: Literal["pending", "in_progress", "done"] = Field(description="The status of the todo")

class SetTodoList(CallableTool2[Params]):
    name: str = "SetTodoList"
    description: str = load_desc(Path(__file__).parent / "set_todo_list.md")
    
    async def __call__(self, params: Params) -> ToolReturnValue:
        items = [TodoDisplayItem(title=todo.title, status=todo.status) for todo in params.todos]
        return ToolReturnValue(
            is_error=False,
            output="",
            message="Todo list updated",
            display=[TodoDisplayBlock(items=items)],
        )
```

工具只负责**数据转换**，无任何业务逻辑或状态校验。

---

## 4. UI 层仅负责渲染

| UI 模式 | 处理方式 | 是否强制 |
|--------|---------|---------|
| Shell UI | `_render_todo_markdown()` 转为 Markdown 显示 | 仅展示，不检查 |
| ACP 模式 | `_send_plan_update()` 转为 `AgentPlanUpdate` 协议消息 | 仅发送，不检查 |

UI 层**不验证** todo 是否全部完成，只负责**可视化**当前状态。

---

## 5. 反证：如果换用弱模型

如果将 Kimi 替换为未经过此类训练的模型（如早期 GPT-3.5 或轻量级本地模型）：

- 可能完全忽略 SetTodoList 工具
- 创建了 todo 后遗忘更新
- 任务完成了也不标记 done

这说明工具的有效使用**并非来自代码强制**，而是模型的**内化行为模式**。

---

## 6. 总结

```
┌─────────────────────────────────────────────────────────┐
│  用户观察：模型通常会正确创建/更新/关闭 todo list         │
│                                                          │
│  可能原因：                                               │
│  ├── A. 代码有强制机制 → ❌ 已验证不存在                  │
│  ├── B. Prompt 有强制指令 → ❌ 只有软性建议               │
│  └── C. 模型训练效果 → ✅ 最可能                         │
│       (Tool Use + Task Planning + Instruction Following) │
└─────────────────────────────────────────────────────────┘
```

### 关键代码引用

| 文件 | 行号 | 说明 |
|------|------|------|
| `src/kimi_cli/tools/todo/__init__.py` | 11-33 | 工具定义，无强制逻辑 |
| `src/kimi_cli/tools/todo/set_todo_list.md` | 1-15 | 软性建议的 prompt |
| `src/kimi_cli/soul/kimisoul.py` | 442-522 | agent loop，被动接收模型决策 |
| `src/kimi_cli/soul/toolset.py` | 111-138 | 工具执行，无状态校验 |

---

*文档生成时间: 2026-03-07*
*分析对象: kimi-cli/src/kimi_cli/tools/todo*
