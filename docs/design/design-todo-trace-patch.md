# Todo 工具 Trace 联动 Patch 设计

> 基于 `/home/tiny/kimi-cli/src/kimi_cli/tools/todo/__init__.py` 源码的具体修改方案

---

## 源码分析

### 当前实现

```python
# /home/tiny/kimi-cli/src/kimi_cli/tools/todo/__init__.py (33行)

class SetTodoList(CallableTool2[Params]):
    name: str = "SetTodoList"
    description: str = load_desc(Path(__file__).parent / "set_todo_list.md")
    params: type[Params] = Params

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        items = [TodoDisplayItem(title=todo.title, status=todo.status) for todo in params.todos]
        return ToolReturnValue(
            is_error=False,
            output="",
            message="Todo list updated",
            display=[TodoDisplayBlock(items=items)],
        )
```

**关键发现**：
1. 实现极简，无状态存储
2. 通过 `ToolReturnValue` 返回消息
3. 描述文件独立 (`set_todo_list.md`)

---

## 方案：环境感知增强版 SetTodoList

### 修改策略

**不修改核心逻辑，只增强 message 和添加可选阻断**。

### Patch 代码

```python
# /home/tiny/kimi-cli/src/kimi_cli/tools/todo/__init__.py

from pathlib import Path
from typing import Literal, override, Optional, List, Dict
from dataclasses import dataclass

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.display import TodoDisplayBlock, TodoDisplayItem
from kimi_cli.tools.utils import load_desc


class Todo(BaseModel):
    title: str = Field(description="The title of the todo", min_length=1)
    status: Literal["pending", "in_progress", "done"] = Field(description="The status of the todo")


class Params(BaseModel):
    todos: list[Todo] = Field(description="The updated todo list")


@dataclass
class TraceCheckResult:
    """Trace 环境检查结果"""
    is_perf_hunter_env: bool
    trace_path: Optional[Path]
    open_issues: List[Dict]
    has_trace_todos: bool  # 是否有 [Trace] 前缀的 todo
    pending_trace_todos: List[Todo]  # 未完成的 [Trace] todos


class SetTodoList(CallableTool2[Params]):
    name: str = "SetTodoList"
    description: str = load_desc(Path(__file__).parent / "set_todo_list.md")
    params: type[Params] = Params
    
    # Trace 文件检测路径（按优先级）
    TRACE_INDICATORS = [".shecr.json", ".shecr_env"]

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        # 1. 检测是否在 perf-hunter 环境
        trace_check = self._check_trace_environment(params.todos)
        
        # 2. 生成增强消息
        message = self._build_enhanced_message(params.todos, trace_check)
        
        # 3. 检查阻断条件（可选，可配置）
        if self._should_block_finalize(params.todos, trace_check):
            return ToolReturnValue(
                is_error=True,
                output="",
                message=message,
                display=[TodoDisplayBlock(items=self._build_display_items(params.todos, trace_check))],
            )
        
        # 4. 正常返回
        items = [TodoDisplayItem(title=todo.title, status=todo.status) for todo in params.todos]
        return ToolReturnValue(
            is_error=False,
            output="",
            message=message,
            display=[TodoDisplayBlock(items=items)],
        )
    
    def _check_trace_environment(self, todos: List[Todo]) -> TraceCheckResult:
        """检测 perf-hunter 环境和 Trace 状态"""
        # 查找 trace 文件
        trace_path = None
        for indicator in self.TRACE_INDICATORS:
            path = Path(indicator)
            if path.exists():
                trace_path = path
                break
        
        if not trace_path:
            return TraceCheckResult(
                is_perf_hunter_env=False,
                trace_path=None,
                open_issues=[],
                has_trace_todos=False,
                pending_trace_todos=[]
            )
        
        # 解析 .shecr.json 获取 open issues
        open_issues = self._parse_trace_issues(trace_path)
        
        # 分析 todos 中的 [Trace] 任务
        trace_todos = [t for t in todos if t.title.startswith("[Trace]")]
        pending_trace_todos = [t for t in trace_todos if t.status != "done"]
        
        return TraceCheckResult(
            is_perf_hunter_env=True,
            trace_path=trace_path,
            open_issues=open_issues,
            has_trace_todos=len(trace_todos) > 0,
            pending_trace_todos=pending_trace_todos
        )
    
    def _parse_trace_issues(self, trace_path: Path) -> List[Dict]:
        """解析 trace 文件中的 open issues"""
        try:
            import json
            data = json.loads(trace_path.read_text())
            issues = data.get("issues", {})
            return [
                {"id": k, **v} for k, v in issues.items()
                if v.get("status") == "open"
            ]
        except Exception:
            return []
    
    def _build_enhanced_message(self, todos: List[Todo], check: TraceCheckResult) -> str:
        """构建增强的消息（核心：在 message 中嵌入 Trace 状态）"""
        base_message = "Todo list updated"
        
        if not check.is_perf_hunter_env:
            return base_message
        
        # 构建 Trace 联动提醒
        reminders = []
        
        # 情况 1: 有 open issues 但没有对应的 [Trace] todos
        if check.open_issues and not check.has_trace_todos:
            reminders.append(
                f"\n[Trace联动] 检测到 {len(check.open_issues)} 个未关联的 issues:\n"
                + "\n".join([f"  - {i['id']}: {i.get('desc', 'No desc')[:30]}" 
                           for i in check.open_issues[:3]])
            )
            if len(check.open_issues) > 3:
                reminders.append(f"  ... 还有 {len(check.open_issues) - 3} 个")
            reminders.append(
                "\n建议: 添加 '[Trace] ISS-XXX: ...' 格式的 todo 进行关联"
            )
        
        # 情况 2: 有未完成的 [Trace] todos
        if check.pending_trace_todos:
            reminders.append(
                f"\n[Trace联动] 有 {len(check.pending_trace_todos)} 个 Trace 任务未完成:\n"
                + "\n".join([f"  - [{t.status}] {t.title[:40]}" 
                           for t in check.pending_trace_todos])
            )
        
        # 情况 3: 所有 todo 都 done，但还有 open issues
        all_done = all(t.status == "done" for t in todos) and len(todos) > 0
        if all_done and check.open_issues:
            reminders.append(
                f"\n[⚠️ Trace阻断] 所有任务已完成，但还有 {len(check.open_issues)} 个 issues 未解决:\n"
                + "\n".join([f"  - {i['id']}: {i.get('desc', 'No desc')[:30]}" 
                           for i in check.open_issues[:3]])
                + "\n\n解决方案:"
                + "\n  1. 执行: shecr trace complete --id ISS-XXX --result '结论'"
                + "\n  2. 或在 Todo 中保留对应的 [Trace] 任务"
            )
        
        if reminders:
            return base_message + "\n" + "\n".join(reminders)
        
        return base_message
    
    def _should_block_finalize(self, todos: List[Todo], check: TraceCheckResult) -> bool:
        """
        是否阻断完成（可配置）
        
        阻断条件：
        1. 在 perf-hunter 环境
        2. 所有 todo 都标记为 done
        3. 还有 open issues 未解决
        4. 没有 [Trace] 前缀的 todo（意味着用户完全忽略了 Trace）
        """
        if not check.is_perf_hunter_env:
            return False
        
        if len(todos) == 0:
            return False
        
        all_done = all(t.status == "done" for t in todos)
        if not all_done:
            return False
        
        # 有 open issues 且没有 [Trace] todo → 阻断
        if check.open_issues and not check.has_trace_todos:
            return True
        
        return False
    
    def _build_display_items(self, todos: List[Todo], check: TraceCheckResult) -> List[TodoDisplayItem]:
        """构建显示项目（可添加 Trace 状态图标）"""
        items = []
        for todo in todos:
            # 如果是 Trace 相关任务，添加标记
            if todo.title.startswith("[Trace]"):
                title = f"🔍 {todo.title}"  # 添加图标标记
            else:
                title = todo.title
            items.append(TodoDisplayItem(title=title, status=todo.status))
        
        # 如果有未关联的 issues，在末尾添加提示项
        if check.open_issues and not check.has_trace_todos:
            items.append(TodoDisplayItem(
                title=f"⚠️ 未关联: {len(check.open_issues)} 个 Trace issues",
                status="pending"
            ))
        
        return items
```

---

## 描述文件增强

```markdown
# /home/tiny/kimi-cli/src/kimi_cli/tools/todo/set_todo_list.md

Update the whole todo list.

Todo list is a simple yet powerful tool to help you get things done. You typically want to use this tool when the given task involves multiple subtasks/milestones, or, multiple tasks are given in a single request. This tool can help you to break down the task and track the progress.

This is the only todo list tool available to you. That said, each time you want to operate on the todo list, you need to update the whole. Make sure to maintain the todo items and their statuses properly.

Once you finished a subtask/milestone, remember to update the todo list to reflect the progress. Also, you can give yourself a self-encouragement to keep you motivated.

---

## Trace Integration (perf-hunter)

When working in a perf-hunter environment (detected by `.shecr.json` or `.shecr_env`), this tool automatically checks Trace issues status:

**Auto-detection:**
- Open Trace issues will be reported in the output message
- Suggestions for creating `[Trace] ISS-XXX: ...` format todos will be provided

**Best practices:**
1. When you see `[Trace联动] 检测到 X 个未关联的 issues`, create corresponding todos:
   - Title format: `[Trace] ISS-001: brief description`
   - This links your todo with the Trace issue

2. When completing a Trace-related todo:
   - First resolve the issue: `shecr trace complete --id ISS-001 --result "conclusion"`
   - Then mark the todo as done

3. If you try to mark all todos as done while open Trace issues remain:
   - The tool will warn you and provide guidance
   - Either resolve the issues or keep the Trace todos active

---

Abusing this tool to track too small steps will just waste your time and make your context messy. For example, here are some cases you should not use this tool:

- When the user just simply ask you a question. E.g. "What language and framework is used in the project?", "What is the best practice for x?"
- When it only takes a few steps/tool calls to complete the task. E.g. "Fix the unit test function 'test_xxx'", "Refactor the function 'xxx' to make it more solid."
- When the user prompt is very specific and the only thing you need to do is brainlessly following the instructions. E.g. "Replace xxx to yyy in the file zzz", "Create a file xxx with content yyy."

However, do not get stuck in a rut. Be flexible. Sometimes, you may try to use todo list at first, then realize the task is too simple and you can simply stop using it; or, sometimes, you may realize the task is complex after a few steps and then you can start using todo list to break it down.
```

---

## 实施步骤

### Step 1: 备份原文件

```bash
cd /home/tiny/kimi-cli
cp src/kimi_cli/tools/todo/__init__.py src/kimi_cli/tools/todo/__init__.py.bak
cp src/kimi_cli/tools/todo/set_todo_list.md src/kimi_cli/tools/todo/set_todo_list.md.bak
```

### Step 2: 应用 Patch

将上面的代码分别写入：
- `src/kimi_cli/tools/todo/__init__.py`
- `src/kimi_cli/tools/todo/set_todo_list.md`

### Step 3: 测试

```bash
cd /home/tiny/kimi-cli
python -c "from kimi_cli.tools.todo import SetTodoList; print('Import OK')"
```

### Step 4: 在 perf-hunter 项目验证

```bash
cd /home/tiny/skills/perf-hunter
# 确保 .shecr.json 存在且有 open issues
# 运行 kimi-cli，测试 SetTodoList 行为
```

---

## 效果预期

### 场景 1: 有 open issues 但无 Trace todos

```
User: 分析性能数据

Agent: (执行 shecr trace issues，发现有 ISS-001, ISS-002)

Agent: SetTodoList(todos=[...非Trace任务...])

返回消息:
  Todo list updated
  
  [Trace联动] 检测到 2 个未关联的 issues:
    - ISS-001: netstat 高内核态 94.7%
    - ISS-002: containerd-shim 高内核态 89...
  
  建议: 添加 '[Trace] ISS-XXX: ...' 格式的 todo 进行关联

Agent: (看到提示，自动添加 [Trace] todos)
```

### 场景 2: 全部 done 但有 open issues

```
Agent: SetTodoList(todos=[...全部done，无[Trace]...])

返回消息:
  Todo list updated
  
  [⚠️ Trace阻断] 所有任务已完成，但还有 2 个 issues 未解决:
    - ISS-001: netstat 高内核态 94.7%
    - ISS-002: containerd-shim 高内核态 89...
  
  解决方案:
    1. 执行: shecr trace complete --id ISS-XXX --result '结论'
    2. 或在 Todo 中保留对应的 [Trace] 任务

(返回 is_error=True，阻断完成)
```

### 场景 3: 正常联动

```
Agent: SetTodoList(todos=[
  "[Trace] ISS-001: 分析 netstat..." (done),
  "[Trace] ISS-002: 分析 containerd..." (in_progress)
])

返回消息:
  Todo list updated
  
  [Trace联动] 有 1 个 Trace 任务未完成:
    - [in_progress] [Trace] ISS-002: 分析 containerd...

(正常返回，无阻断)
```

---

## 优势

```
┌─────────────────────────────────────────────────────────────┐
│                      核心优势                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 零配置: 自动检测 .shecr.json，无需手动启用               │
│                                                              │
│  2. 非侵入: 只在 message 中提醒，不改变原有逻辑              │
│                                                              │
│  3. 可阻断: 极端情况下 (全部done但issues未解) 可阻断         │
│                                                              │
│  4. 通用: 可作为模板，支持其他 skill 类似集成                 │
│                                                              │
│  5. 渐进: 不影响非 perf-hunter 环境的使用                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 回滚方案

如果出现问题：

```bash
cd /home/tiny/kimi-cli
cp src/kimi_cli/tools/todo/__init__.py.bak src/kimi_cli/tools/todo/__init__.py
cp src/kimi_cli/tools/todo/set_todo_list.md.bak src/kimi_cli/tools/todo/set_todo_list.md
```

---

## 总结

这个方案的核心是：**在 SetTodoList 返回的 message 中嵌入 Trace 状态信息**。

- 不修改工具签名
- 不增加新工具
- 不强制改变用户流程
- 但通过 message 的强力提示，实现近乎强制的效果

相比 Prompt 层的软性建议，这个方案是**代码层的硬性提醒**，不可绕过。
