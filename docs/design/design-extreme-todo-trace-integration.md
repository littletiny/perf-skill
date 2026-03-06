# 极端方案：Todo 工具内置 Trace 联动

> 提案：修改 kimi-cli 的 SetTodoList 工具，内置 perf-hunter Trace 联动能力

---

## 核心洞察：为什么这个方案可行？

### 当前架构问题

```
┌─────────────────────────────────────────────────────────────┐
│                      当前松耦合架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   kimi-cli (通用)              perf-hunter (领域)            │
│   ┌─────────────┐              ┌─────────────┐              │
│   │ SetTodoList │◄─────────────│ 手动调用    │              │
│   │ (通用工具)  │              │ (易遗忘)    │              │
│   └─────────────┘              └─────────────┘              │
│         ↑                                                    │
│         └────────────────────────────────────┐              │
│                                              ▼              │
│                                        ┌─────────────┐      │
│                                        │   Trace     │      │
│                                        │  (独立状态)  │      │
│                                        └─────────────┘      │
│                                                              │
│   问题: Trace 和 Todo 是两条独立的状态线，依赖人工同步       │
└─────────────────────────────────────────────────────────────┘
```

### 极端方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                      内置联动架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   kimi-cli (增强)              perf-hunter (简化)            │
│   ┌─────────────────┐                                        │
│   │  SetTodoList    │◄─────────────────────────────┐         │
│   │  ┌───────────┐  │                              │         │
│   │  │ 内置Trace │  │  ← 自动检测 .shecr.json      │         │
│   │  │ 联动模块  │  │    自动同步 open issues      │         │
│   │  └───────────┘  │                              │         │
│   └─────────────────┘                              │         │
│           │                                        │         │
│           └────────────────────────────────────────┘         │
│                        自动同步 (不可绕过)                    │
│                                                              │
│   优势: 只要在 perf-hunter 目录，todo 自动感知 trace 状态    │
└─────────────────────────────────────────────────────────────┘
```

---

## 设计方案

### 方案 A：状态提供者协议（推荐）

**核心思想**：SetTodoList 支持"外部状态提供者"插件机制

```python
# kimi-cli 层（通用框架）
class SetTodoList(CallableTool2[Params]):
    """增强版 Todo 工具，支持外部状态联动"""
    
    # 状态提供者注册表
    STATE_PROVIDERS: Dict[str, StateProvider] = {}
    
    @classmethod
    def register_state_provider(cls, name: str, provider: StateProvider):
        """注册外部状态提供者"""
        cls.STATE_PROVIDERS[name] = provider
    
    async def __call__(self, params: Params) -> ToolReturnValue:
        # 1. 先执行正常的 todo 更新
        result = await self._update_todos(params)
        
        # 2. 自动同步所有已注册的状态提供者
        for name, provider in self.STATE_PROVIDERS.items():
            if provider.is_active():
                sync_result = provider.sync_with_todos(params.todos)
                if sync_result.has_conflicts:
                    result.warnings.extend(sync_result.warnings)
        
        return result

# perf-hunter 层（领域实现）
class TraceStateProvider(StateProvider):
    """Trace 状态提供者 - 由 perf-hunter 注册"""
    
    def is_active(self) -> bool:
        """检测当前是否在 perf-hunter 环境"""
        return Path('.shecr.json').exists()
    
    def sync_with_todos(self, todos: List[Todo]) -> SyncResult:
        """
        同步逻辑：
        1. 读取 .shecr.json 中的 open issues
        2. 检查是否每个 issue 都有对应的 todo
        3. 如果有遗漏，返回警告建议
        """
        trace = Trace('.shecr.json')
        open_issues = trace.get_open_issues()
        
        # 检查 [Trace] 前缀的 todo 是否覆盖所有 issues
        trace_todos = [t for t in todos if t.title.startswith('[Trace]')]
        covered_issue_ids = self._extract_issue_ids(trace_todos)
        
        missing = [i for i in open_issues if i['id'] not in covered_issue_ids]
        
        if missing:
            return SyncResult(
                has_conflicts=True,
                warnings=[
                    f"[Trace联动] 发现 {len(missing)} 个未覆盖的 issues:",
                    *[f"  - {i['id']}: {i['desc'][:30]}" for i in missing],
                    "建议: 添加对应 Todo 或执行 'shecr trace complete'"
                ]
            )
        
        return SyncResult(has_conflicts=False)
```

### 方案 B：环境感知自动注入

**核心思想**：SetTodoList 自动检测环境，动态注入 Trace 任务

```python
class SetTodoList(CallableTool2[Params]):
    """
    环境感知 Todo 工具
    
    当检测到 .shecr.json 存在时，自动将 open issues 注入 todo list
    """
    
    async def __call__(self, params: Params) -> ToolReturnValue:
        # 检测 perf-hunter 环境
        if self._is_perf_hunter_env():
            # 自动注入 Trace issues
            params = self._inject_trace_issues(params)
        
        return await self._process_todos(params)
    
    def _is_perf_hunter_env(self) -> bool:
        """检测当前工作目录是否在 perf-hunter 项目中"""
        return (
            Path('.shecr.json').exists() or
            Path('.shecr_env').exists() or
            self._detect_skill_context() == 'perf-hunter'
        )
    
    def _inject_trace_issues(self, params: Params) -> Params:
        """
        自动注入策略：
        1. 读取 .shecr.json open issues
        2. 检查用户提供的 todos 是否已包含
        3. 将遗漏的 issues 作为 "[Trace] ISS-XXX: ..." 自动注入
        4. 标记为 injected_by_system，以便区分
        """
        trace = Trace('.shecr.json')
        open_issues = trace.get_open_issues()
        
        # 提取用户已指定的 trace todos
        existing_ids = set()
        for todo in params.todos:
            if todo.title.startswith('[Trace]'):
                issue_id = self._extract_issue_id(todo.title)
                existing_ids.add(issue_id)
        
        # 注入遗漏的 issues
        new_todos = list(params.todos)
        for issue in open_issues:
            if issue['id'] not in existing_ids:
                new_todos.append(Todo(
                    title=f"[Trace] {issue['id']}: {issue['desc'][:40]}",
                    status='pending',
                    # 标记为系统自动注入
                    metadata={'injected_by': 'trace_sync', 'issue_id': issue['id']}
                ))
        
        params.todos = new_todos
        return params
```

### 方案 C：强制完成检查（最极端）

**核心思想**：在 finalize/结束会话前，强制检查 Trace issues 状态

```python
class SetTodoList(CallableTool2[Params]):
    """
    强制联动 Todo 工具
    
    当所有 todo 都标记为 done 时，强制检查 trace issues 是否都已解决
    """
    
    async def __call__(self, params: Params) -> ToolReturnValue:
        # 正常处理
        result = await self._update_todos(params)
        
        # 检查是否是 "全部完成" 状态
        if self._is_all_done(params.todos) and self._is_perf_hunter_env():
            # 强制检查 trace
            check_result = self._enforce_trace_check()
            if not check_result.passed:
                # 阻止完成，要求先处理 trace
                return ToolReturnValue(
                    is_error=True,  # 或使用 warning + 交互式确认
                    output="",
                    message=check_result.blocking_message,
                    display=[BlockingBlock(message=check_result.message)]
                )
        
        return result
    
    def _enforce_trace_check(self) -> CheckResult:
        """
        强制检查：
        1. 读取 .shecr.json
        2. 如果有 open issues，阻止 todo 全部完成
        3. 提供明确的解决方案
        """
        trace = Trace('.shecr.json')
        open_issues = trace.get_open_issues()
        
        if open_issues:
            return CheckResult(
                passed=False,
                blocking_message=f"""
[TRACE阻断] 您有 {len(open_issues)} 个未解决的 Trace issues，无法完成所有任务：

{self._format_issues(open_issues)}

解决方案（选择一项）：
1. 执行分析并标记解决：
   shecr trace complete --id ISS-XXX --result "分析结论"

2. 接受风险并强制完成（不推荐）：
   shecr trace finalize --accept-risk "原因"

3. 创建对应的 Trace 分析任务：
   在 Todo 中添加 "[Trace] ISS-XXX: ..." 任务
"""
            )
        
        return CheckResult(passed=True)
```

---

## 方案对比

| 维度 | 方案 A: 状态提供者 | 方案 B: 环境感知注入 | 方案 C: 强制完成检查 |
|------|-------------------|---------------------|---------------------|
| **侵入性** | 低（注册机制） | 中（自动修改参数） | 高（阻断操作） |
| **用户体验** | 提示警告 | 自动补充 | 强制阻断 |
| **实现复杂度** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **通用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **强制程度** | 弱（提示） | 中（自动） | 强（阻断） |
| **perf-hunter 改动** | 注册 provider | 无 | 无 |
| **kimi-cli 改动** | 扩展点 | 环境检测 | 阻断逻辑 |

---

## 推荐：方案 A + C 的组合

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                  Enhanced SetTodoList                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  StateProvider Protocol                │  │
│  │  - register_provider(name, provider)                   │  │
│  │  - is_active() -> bool                                 │  │
│  │  - sync_with_todos(todos) -> SyncResult                │  │
│  │  - can_finalize(todos) -> CheckResult                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                           ▲                                  │
│           ┌───────────────┼───────────────┐                  │
│           ▼               ▼               ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │ TraceProvider│ │GitHubProvider│ │JiraProvider  │         │
│  │ (perf-hunter)│ │ (未来扩展)    │ │ (未来扩展)    │         │
│  └──────────────┘ └──────────────┘ └──────────────┘         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 执行流程

```
用户调用 SetTodoList
        │
        ▼
┌───────────────┐
│ 1. 检测环境    │──→ 检查所有 registered providers
│    is_active  │    找到 active 的 providers
└───────────────┘
        │
        ▼
┌───────────────┐
│ 2. 同步检查    │──→ 调用 sync_with_todos()
│   (警告提示)   │    返回 warnings（非阻断）
└───────────────┘
        │
        ▼
┌───────────────┐
│ 3. 更新 Todo   │──→ 正常更新 todo list
│   (正常执行)   │
└───────────────┘
        │
        ▼
┌───────────────┐
│ 4. 完成检查    │──→ 如果是 "全部 done"
│   (阻断检查)   │    调用 can_finalize()
└───────────────┘    如果有 open issues，阻断
        │
        ▼
   返回结果
```

---

## 实施路径

### Phase 1: kimi-cli 扩展（通用框架）

```python
# src/kimi_cli/tools/todo/state_provider.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pydantic import BaseModel

class SyncResult(BaseModel):
    has_conflicts: bool
    warnings: List[str] = []
    suggestions: List[str] = []

class CheckResult(BaseModel):
    passed: bool
    blocking_message: str = ""
    severity: str = "warning"  # warning / error

class StateProvider(ABC):
    """外部状态提供者基类"""
    
    name: str
    
    @abstractmethod
    def is_active(self) -> bool:
        """检测当前环境是否激活此 provider"""
        pass
    
    @abstractmethod
    def sync_with_todos(self, todos: List[Todo]) -> SyncResult:
        """同步检查，返回警告建议（非阻断）"""
        pass
    
    def can_finalize(self, todos: List[Todo]) -> CheckResult:
        """
        完成前检查，可阻断
        默认通过，子类可覆盖实现强制检查
        """
        return CheckResult(passed=True)

# 全局注册表
_STATE_PROVIDERS: Dict[str, StateProvider] = {}

def register_state_provider(provider: StateProvider):
    """注册状态提供者"""
    _STATE_PROVIDERS[provider.name] = provider

def get_active_providers() -> List[StateProvider]:
    """获取当前激活的所有 providers"""
    return [p for p in _STATE_PROVIDERS.values() if p.is_active()]
```

### Phase 2: perf-hunter 注册（领域实现）

```python
# scripts/perf_toolkit/cli/trace_todo_provider.py

from kimi_cli.tools.todo.state_provider import StateProvider, SyncResult, CheckResult

class TraceStateProvider(StateProvider):
    """perf-hunter Trace 状态提供者"""
    
    name = "perf_hunter_trace"
    
    def is_active(self) -> bool:
        return Path('.shecr.json').exists()
    
    def sync_with_todos(self, todos: List[Todo]) -> SyncResult:
        """检查是否有遗漏的 Trace issues"""
        trace = self._load_trace()
        open_issues = trace.get_open_issues()
        
        # 分析当前 todos 对 issues 的覆盖情况
        coverage = self._analyze_coverage(todos, open_issues)
        
        if coverage.missing:
            return SyncResult(
                has_conflicts=True,
                warnings=[
                    f"[Trace联动] 有 {len(coverage.missing)} 个 issues 未创建对应任务："
                ],
                suggestions=[
                    f"添加 Todo: '[Trace] {i['id']}: {i['desc'][:30]}'" 
                    for i in coverage.missing
                ]
            )
        
        return SyncResult(has_conflicts=False)
    
    def can_finalize(self, todos: List[Todo]) -> CheckResult:
        """强制检查：如果有 open issues，阻止全部完成"""
        trace = self._load_trace()
        open_issues = trace.get_open_issues()
        
        # 检查是否有 [Trace] 前缀的未完成 todo
        trace_todos_pending = [
            t for t in todos 
            if t.title.startswith('[Trace]') and t.status != 'done'
        ]
        
        if open_issues or trace_todos_pending:
            return CheckResult(
                passed=False,
                severity="error",
                blocking_message=self._build_blocking_message(
                    open_issues, trace_todos_pending
                )
            )
        
        return CheckResult(passed=True)

# 模块加载时自动注册
def _register():
    from kimi_cli.tools.todo.state_provider import register_state_provider
    register_state_provider(TraceStateProvider())

_register()
```

### Phase 3: SetTodoList 集成

```python
# src/kimi_cli/tools/todo/__init__.py

from .state_provider import get_active_providers, CheckResult

class SetTodoList(CallableTool2[Params]):
    
    async def __call__(self, params: Params) -> ToolReturnValue:
        # 1. 获取激活的 providers
        active_providers = get_active_providers()
        
        # 2. 执行同步检查（收集警告）
        all_warnings = []
        for provider in active_providers:
            result = provider.sync_with_todos(params.todos)
            if result.has_conflicts:
                all_warnings.extend(result.warnings)
                all_warnings.extend(result.suggestions)
        
        # 3. 检查是否可以完成（阻断检查）
        is_all_done = all(t.status == 'done' for t in params.todos)
        if is_all_done:
            for provider in active_providers:
                check = provider.can_finalize(params.todos)
                if not check.passed:
                    return ToolReturnValue(
                        is_error=check.severity == "error",
                        output="",
                        message=check.blocking_message,
                        display=[WarningBlock(message="\n".join(all_warnings))] if all_warnings else []
                    )
        
        # 4. 正常处理
        items = [TodoDisplayItem(title=t.title, status=t.status) for t in params.todos]
        
        message = "Todo list updated"
        if all_warnings:
            message += f"\n\n{'='*50}\n外部状态联动提醒：\n{'='*50}\n" + "\n".join(all_warnings)
        
        return ToolReturnValue(
            is_error=False,
            output="",
            message=message,
            display=[TodoDisplayBlock(items=items)],
        )
```

---

## 优势与风险

### 优势

```
┌─────────────────────────────────────────────────────────────┐
│                      核心优势                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 不可绕过                                                 │
│     代码层面的强制，不依赖模型训练效果                        │
│                                                              │
│  2. 通用设计                                                 │
│     StateProvider 协议可被其他 skill 复用                     │
│                                                              │
│  3. 渐进增强                                                 │
│     现有 perf-hunter 逻辑无需改动，只需注册 provider          │
│                                                              │
│  4. 用户透明                                                 │
│     自动检测、自动提示，无需学习新命令                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| kimi-cli 侵入性改动 | 高 | 设计为通用扩展点，不硬编码 perf-hunter 逻辑 |
| 误判环境 | 中 | 多重检测（.shecr.json + .shecr_env + skill context） |
| 阻断过度 | 中 | 提供 `--accept-risk` 类似的强制绕过机制 |
| 性能影响 | 低 | 只在 SetTodoList 调用时检测，IO 开销极小 |

---

## 结论

这个"极端方案"实际上是**架构上的优雅升级**：

```
从：模型驱动的软性建议
到：协议驱动的强制检查

不变：perf-hunter 的领域逻辑
增强：kimi-cli 的通用扩展能力
```

### 决策建议

```
如果满足以下条件，推荐实施：
✓ kimi-cli 允许添加通用扩展机制
✓ perf-hunter 是重点维护的 skill
✓ 团队愿意承担架构升级的短期成本

如果不满足，退回标准方案：
→ 使用 docs/design/design-trace-todo-integration.md 的 Prompt 层联动
```

### 下一步行动

1. **与 kimi-cli 维护者确认**：是否接受 StateProvider 扩展机制
2. **原型验证**：实现 Phase 1 的核心框架，验证可行性
3. **A/B 测试**：对比新旧方案的实际效果
