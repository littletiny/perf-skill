# XT Protocol 实施总结

> Trace-Todo 联动 Attention Steering 方案的实施记录

---

## 实施概览

```
┌─────────────────────────────────────────────────────────────┐
│                   XT Protocol 实施状态                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [✅] SKILL.md      - XT 标签定义 + XT Protocol 章节         │
│  [✅] AGENTS.md     - XT 状态提醒                           │
│  [✅] trace issues  - XT0/XT-A 联动提示                     │
│  [✅] trace complete - XT1/XT-A 完成提示                    │
│  [✅] trace finalize - XT0/XT-A 审计提示                    │
│                                                              │
│  实施方式: 纯 Prompt + 工具输出增强 (零代码侵入 kimi-cli)     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 修改详情

### 1. SKILL.md

**修改点**:
- `description` 添加 `XT0=trace-todo-sync | XT1=trace-pending | XT-A=trace-action`
- 新增 "Trace-Todo 联动规范 (XT Protocol)" 章节

**关键内容**:
```markdown
## Trace-Todo 联动规范 (XT Protocol)

### XT 标签定义

| 标记 | 全称 | 含义 | 触发动作 |
|------|------|------|---------|
| `<XT0>` | eXtra Trace Critical | Trace-Todo 阻塞级同步 | 必须立即创建对应 Todo |
| `<XT1>` | eXtra Trace Major | Trace-Todo 重要提醒 | 建议更新 Todo 状态 |
| `<XT-A>` | eXtra Trace Action | Trace-Todo 行动指令 | 具体同步操作命令 |

### 同步规则

**Rule 1: Issue → Todo (创建时)**
<XT0> 每个 open issue 必须对应一个 Todo
<XT-A> SetTodoList 格式: "[Trace] {ISS-ID}: {简要描述}"

**Rule 2: Todo → Trace (完成时)**
<XT0> 标记 [Trace] Todo 为 done 前，必须先执行 trace complete

**Rule 3: 最终检查**
<XT0> 所有 Todo 标记为 done 前，必须确认 trace issues --status open 返回空
```

### 2. AGENTS.md

**修改点**: Attention Steering 章节添加 XT 状态提醒

**关键内容**:
```markdown
#### XT Protocol (Trace-Todo 联动)

当前目录 Trace 状态检测：
检查: .shecr.json 存在 → <XT0> Trace-Todo 联动激活

**联动检查清单**:
- [ ] 执行 `shecr trace issues` 查看 open issues
- [ ] 为每个 open issue 创建 `[Trace] ISS-XXX: ...` 格式 Todo
- [ ] 完成分析后先执行 `shecr trace complete` 再标记 Todo done
- [ ] 结束前执行 `shecr trace finalize` 确认所有 issues 已解决
```

### 3. trace issues 输出

**文件**: `scripts/perf_toolkit/cli/commands/trace/issues.py`

**新增输出** (当有 open issues 时):
```
=================================================================
<XT0> 发现 N 个待处理问题需要同步到 Todo

<XT0> 同步要求: 每个 open issue 必须创建对应 Todo
<XT-A> SetTodoList 格式: '[Trace] {ISS-ID}: {简要描述}'

  <XT-A> {'title': '[Trace] ISS-001: 分析...', 'status': 'pending'}
  <XT-A> {'title': '[Trace] ISS-002: 分析...', 'status': 'pending'}
=================================================================
```

**新增输出** (当无 open issues 时):
```
<XT0> 所有 issues 已解决
<XT-A> 确认所有 [Trace] 前缀的 Todo 已标记为 done
```

### 4. trace complete 输出

**文件**: `scripts/perf_toolkit/cli/commands/trace/complete.py`

**新增输出**:
```
[COMPLETED] ISS-001
→ Result: xxx

<XT1> 还有 N 个 issues 待处理

--------------------------------------------------
<XT1> 对应的 [Trace] ISS-001 Todo 可以标记为 done
<XT-A> SetTodoList: 更新 '[Trace] ISS-001: ...' status: 'done'
--------------------------------------------------
```

### 5. trace finalize 输出

**文件**: `scripts/perf_toolkit/cli/commands/trace/finalize.py`

**状态: ready**:
```
<XT0> [READY] All issues resolved
<XT0> Trace 审计通过
<XT-A> 确认所有 [Trace] 前缀的 Todo 已标记为 done
```

**状态: blocked**:
```
<XT0> [BLOCKED] N open issues remaining
...
<XT0> 存在未解决的 Trace issues
<XT-A> 选项1: 继续分析并执行 trace complete
<XT-A> 选项2: 接受风险: --accept-risk '原因'
<XT-A> 选项3: 创建对应 Todo 跟踪: '[Trace] ISS-XXX: ...'
```

---

## 效果验证

### 测试场景 1: 发现 issues

```bash
shecr trace issues
```

**预期行为**:
1. 输出显示 `<XT0> 发现 N 个待处理问题`
2. 模型看到 `<XT0>` 标签，注意力被吸引
3. 根据 `<XT-A>` 提示，自动创建 `[Trace] ISS-XXX` 格式 Todo

### 测试场景 2: 完成分析

```bash
shecr trace complete --id ISS-001 --result "根因: ..."
```

**预期行为**:
1. 输出显示 `<XT1> 对应的 [Trace] ISS-001 Todo 可以标记为 done`
2. 模型执行 SetTodoList 更新对应任务状态

### 测试场景 3: 最终确认

```bash
shecr trace finalize
```

**预期行为**:
1. 如果有 open issues，`<XT0> [BLOCKED]` 阻止完成
2. 如果全部解决，`<XT0> [READY]` 确认通过

---

## 核心设计决策

### 为什么选择 Attention Steering 方案？

```
┌─────────────────────────────────────────────────────────────┐
│                    决策依据                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  根据 docs/todo_tool_close_analysis.md:                     │
│  - Todo Tool 70% 依赖模型训练效果                            │
│  - 模型已内化 "任务分解→执行→完成确认" 流程                  │
│  - Todo Tool 在模型决策中权重很高                            │
│                                                              │
│  结论:                                                       │
│  → 无需代码强制，Prompt + Attention Steering 足够驱动        │
│  → 利用模型对 Todo 的高敏感性，通过 XT 标签引导联动           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### XT 标签 vs X 标签

| 标签系列 | 用途 | 层级 |
|----------|------|------|
| `X0/X1/X2/XA` | 性能诊断关注点 | 业务层 |
| `XT0/XT1/XT-A` | Trace-Todo 联动 | 元数据层 |

**设计理由**:
- `XT` = eXtra Trace，表示 Trace 相关的额外注意力引导
- 与业务层的 `X` 标签区分，避免混淆
- 同样使用 X 前缀，符合模型已训练的注意力模式

---

## 后续优化建议

### 短期 (已实施)

- [x] SKILL.md XT Protocol 文档
- [x] AGENTS.md 环境提醒
- [x] trace 命令 XT 标签输出

### 中期 (可选)

- [ ] `shecr trace sync-check` 命令 - 手动检查同步状态
- [ ] `references/templates.md` 诊断报告模板添加 XT 标记示例
- [ ] 工具输出颜色高亮 XT 标签

### 长期 (观察效果后)

- [ ] 如果 Prompt 方案效果不足，考虑代码层联动方案
- [ ] 评估是否需要阻断机制 (is_error=True)

---

## 文档索引

| 文档 | 用途 |
|------|------|
| `docs/design/design-trace-todo-attention-steering.md` | 完整设计方案 |
| `docs/design/XT_PROTOCOL_IMPLEMENTATION.md` | 本实施总结 |
| `SKILL.md` | 用户/模型可见的 XT Protocol 规范 |
| `AGENTS.md` | 开发者可见的 XT 状态提醒 |

---

*实施时间: 2026-03-07*
*基于设计: docs/design/design-trace-todo-attention-steering.md*
