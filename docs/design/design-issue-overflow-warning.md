# Issue Overflow Warning 设计文档

> 版本: 1.0
> 创建时间: 2026-03-02

---

## 1. 背景

### 1.1 问题

当 `shecr trace` 自动记录多个 issues 后，用户可能**未意识到**还有大量未处理的问题，直接生成结论，导致：
- 诊断覆盖不全
- 遗漏关键异常
- 结论被质疑

### 1.2 目标

在每次执行**非 trace 命令**时，强制提示用户查看未处理的 issues，必须触发 `trace issues` 查看全局现状。

---

## 2. 设计方案

### 2.1 触发条件

```python
# 触发条件
if open_issues >= 2 and command not in ['trace', 'init']:
    print_warning()
```

### 2.2 展示格式（固定模板）

```
[!] {总数}问题未闭环: {分类统计} | ⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状 | 现在执行: trace issues
```

**示例输出：**

```
$ shecr cluster-symbols --comm netstat
[!] 7问题未闭环: 内核异常x5, 锁竞争x2, 进程风暴x1 | ⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状 | 现在执行: trace issues

═══════════════════════════════════════════════════════════════════
EVENT: LOCK_CONTENTION 38.36%
...
```

### 2.3 问题分类规则

| 分类 | 判定条件 | 关键字匹配 |
|------|---------|-----------|
| 内核异常 | `kernel_ratio > 50%` | desc 包含 "内核" 或 "kernel" |
| 锁竞争 | `LOCK_CONTENTION > 10%` | desc 包含 "锁竞争" 或 "LOCK_CONTENTION" |
| 进程风暴 | `PROCESS_STORM` detected | desc 包含 "进程风暴" 或 "PROCESS_STORM" |

### 2.4 实现位置

**文件 1: `scripts/perf_toolkit/core/output_builder.py`**

新增方法 `print_issue_overflow_warning()`:

```python
def print_issue_overflow_warning(self):
    """
    检查 pending issues 并输出 overflow warning

    触发条件: open_issues >= 2
    输出格式: [!] {总数}问题未闭环: {分类统计} | {警告文案} | 现在执行: trace issues
    """
    if not self._trace:
        return

    open_issues = self._trace.get_open_issues()
    if len(open_issues) < 2:
        return

    # 分类统计
    categories = self._categorize_issues(open_issues)
    category_str = ", ".join([f"{cat}x{count}" for cat, count in categories.items()])

    # 固定警告文案
    warning = "⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状"

    # 输出
    print(f"[!] {len(open_issues)}问题未闭环: {category_str} | {warning} | 现在执行: trace issues")
```

**文件 2: `scripts/shecr.py`**

在分析命令执行前调用：

```python
# 在 engine 初始化后，命令执行前
if args.command in commands:
    # Issue Overflow Warning
    from perf_toolkit.core.output_builder import OutputBuilder
    builder = OutputBuilder(engine, args)
    builder.print_issue_overflow_warning()

    # 执行实际命令
    commands[args.command](engine, args)
```

---

## 3. 关键实现细节

### 3.1 避免循环依赖

`OutputBuilder` 已导入 `Trace`，无需额外处理。

### 3.2 性能考虑

- 只读取 `.shecr.json` 文件，不涉及数据解析
- 不影响主命令执行性能

### 3.3 兼容性

- 无 `.shecr.json` 时不输出（`Trace` 自动处理）
- 少于 2 个 issues 时不输出

---

## 4. 文案说明

### 4.1 为什么选择这段文案

> "用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状"

- **强烈语气**："质疑专业性"、"挑战底线"、"务必"
- **强调全局**：加粗 `**全局**`，对抗局部偏见
- **用户视角**：站在用户立场施压，而非系统提示

### 4.2 固定不变

该文案为**固定模板**，不随 issue 数量变化，确保每次提示强度一致。

---

## 5. 测试用例

### 5.1 有 7 个 pending issues

```bash
$ shecr cluster-symbols --comm netstat --data tests/scenario/netstat/case.data
[!] 7问题未闭环: 内核异常x5, 锁竞争x2, 进程风暴x1 | ⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状 | 现在执行: trace issues

═══════════════════════════════════════════════════════════════════
EVENT: LOCK_CONTENTION 38.36%
...
```

### 5.2 只有 1 个 pending issue

```bash
$ shecr cluster-symbols --comm netstat --data case.data
# 无提示（< 2 不触发）

═══════════════════════════════════════════════════════════════════
EVENT: LOCK_CONTENTION 38.36%
...
```

### 5.3 trace 命令不触发

```bash
$ shecr trace issues
# 无提示

⚠️  OPEN ISSUES (待处理)
...
```

---

## 6. 相关文档

- [design-rationale-trace-v2.md](./design-rationale-trace-v2.md) - Trace v2.0 设计
- [trace-interface.md](./trace-interface.md) - Trace 接口规范
