# sys-audit 重构报告：方法论驱动的设计实践

> **文档性质**: 设计意图记录 (Design Intent Documentation)  
> **创建时间**: 2026-03-04  
> **对应版本**: perf-hunter v1.2+  
> **核心方法论**: SHECR (Systematic Hypothesis Evidence-driven Controlled Reasoning)

---

## 1. 重构背景：为什么要改 sys-audit

### 1.1 发现的问题

在三层架构（Core-Analysis-Composite）实施过程中，我们发现 `sys-audit` 命令存在以下与设计原则冲突的问题：

| 问题 | 表现 | 违背的方法论原则 |
|------|------|-----------------|
| **Issue 重复创建** | 重复执行相同命令生成多个 ISS-xxx | **C**ontrolled - 缺乏收敛控制 |
| **信息截断** | desc 只显示摘要，缺少详细数据 | **E**vidence - 证据不完整 |
| **Hint 误导** | `check-cpu-bottleneck` 过于笼统 | **S**ystematic - 未指向具体工具 |
| **排序不一致** | Risk 消息中的进程顺序与 TopN 列表不一致 | **R**easoning - 逻辑不一致 |

### 1.2 触发重构的具体场景

```bash
# 场景 1: 重复执行导致 Issue 泛滥
$ shecr sys-audit
# 创建 ISS-001

$ shecr sys-audit  
# 又创建 ISS-002 (完全相同的内容)

$ shecr sys-audit
# 又创建 ISS-003 ...

# 场景 2: Issue 信息不足
$ shecr trace issues
[OPEN] [ISS-001] [CRITICAL] 发现 4 个关键性能瓶颈: netstat, python3, hacontrol...
→ check-cpu-bottleneck  # 太笼统，不知道下一步该用什么工具

# 场景 3: 排序不一致
[RISK] 发现瓶颈: python3, kubelet, netstat...  # Risk 消息顺序
### Top 进程
   1. netstat     # TopN 列表顺序不同！
   2. python3
```

---

## 2. 设计意图：方法论原则如何指导修改

### 2.1 C - Controlled（受控收敛）

**原则**: 禁止过早下结论，相同诊断不应重复创建 Issue

**实现**: 命令指纹去重机制

```python
# trace.py: begin_command 保存完整命令作为指纹
self._current_fingerprint = command  # "sys-audit --data xxx --top-n 20"

# trace.py: add 方法检查去重
if fingerprint:
    for existing_id, existing_issue in self.data['issues'].items():
        if (existing_issue.get('status') == 'open' and
            existing_issue.get('command_fingerprint') == fingerprint):
            # 存在相同指纹的 open issue，记录为关联风险
            return None  # 跳过创建
```

**设计理由**:
- 相同命令 + 相同参数 = 确定性的相同结果
- 如果参数没变，问题状态就不应该改变
- 去重只针对 `open` 状态的 issue，已解决的可以重新创建（重新诊断场景）

### 2.2 E - Evidence（证据驱动）

**原则**: Issue 必须包含完整的证据数据，拒绝信息截断

**实现**: 详细 desc 格式

```python
# 重构前
desc = "发现 4 个关键性能瓶颈: netstat, python3, hacontrol 等4个"

# 重构后
desc = "发现 4 个关键性能瓶颈 | " \
       "#1 netstat: 288.3% CPU (sys: 273.7%/95%, pids: 78, score: 493.9, type: BOTTLENECK); " \
       "#2 python3: 189.7% CPU (sys: 65.7%/35%, pids: 34, score: 268.7, type: BOTTLENECK); " \
       "..."
```

**包含的完整证据**:
| 字段 | 说明 | 诊断价值 |
|------|------|----------|
| CPU% | 总利用率 | 绝对负载水平 |
| sys% | 内核态占比 | 系统 vs 业务瓶颈区分 |
| sys_ratio | 内核比例 | 高比例 → 系统调用/锁竞争 |
| pids | 进程数量 | 单进程 vs 进程风暴 |
| score | Impact Score | 危害指数（排序依据） |
| type | 诊断类型 | BOTTLENECK/STORM/UNBALANCED |

### 2.3 S - Systematic（系统性）

**原则**: 每层必须有明确的下一步操作，形成递进诊断链

**实现**: Hint 指向具体细分工具

```python
# 重构前
hint = "check-cpu-bottleneck"  # 太笼统

# 重构后  
hint = "get-hotspots --comm $COMM && find-callers --target <top_symbol>"
```

**三层架构映射**:

```
sys-audit (Composite层 - 系统级扫描)
    │
    ▼ 发现问题
    │
get-hotspots (Analysis层 - 函数级热点)  ◄── Hint 指向这里
    │
    ▼ 找到热点符号
    │
find-callers (Analysis层 - 调用链溯源)  ◄── 然后这里
    │
    ▼ 确认根因
```

### 2.4 R - Reasoning（逻辑推理）

**原则**: 输出必须一致，逻辑链条清晰可追溯

**实现**: 统一排序逻辑

```python
# 使用 diagnosis 中已排序的数据（按 impact_score）
sorted_targets = []
if diagnosis.primary_suspect:
    sorted_targets.append(diagnosis.primary_suspect.comm)
sorted_targets.extend([g.comm for g in diagnosis.secondary_loads])

# Risk message 和 TopN 列表使用相同顺序
risk.message = f"发现 {len(sorted_targets)} 个关键性能瓶颈: {', '.join(sorted_targets[:3])}"
```

**一致性保证**:
- `diagnosis.primary_suspect` 和 `diagnosis.secondary_loads` 在 `_synthesize_diagnosis` 中按 Impact Score 排序
- Risk message 直接使用这个排序
- TopN 列表也使用相同排序
- 确保用户看到的顺序完全一致

---

## 3. 实现细节：关键代码变更

### 3.1 文件变更清单

| 文件 | 变更类型 | 修改内容 |
|------|---------|----------|
| `scripts/perf_toolkit/core/trace.py` | 新增 | 命令指纹去重机制 |
| `scripts/perf_toolkit/cli/commands/composite/sys_audit.py` | 修改 | 详细 desc 生成、排序统一 |
| `scripts/perf_toolkit/cli/builders.py` | 修改 | Hint 模板更新 |
| `scripts/perf_toolkit/core/output_builder.py` | 修改 | Hint 模板更新 |

### 3.2 核心代码片段

#### 3.2.1 命令指纹去重 (trace.py)

```python
class Trace:
    def begin_command(self, command: str) -> int:
        """命令开始时保存指纹"""
        seq = len(self.data['timeline']) + 1
        self._current_seq = seq
        self._current_fingerprint = command  # 完整命令作为指纹
        
        record = TimelineRecord(
            seq=seq,
            type="command",
            command=command,
            timestamp=self._now(),
            findings=[]
        )
        self.data['timeline'].append(asdict(record))
        self.save()
        return seq
    
    def add(self, desc: str, ..., level: str = "warning") -> Optional[str]:
        """添加 issue，带指纹去重"""
        fingerprint = getattr(self, '_current_fingerprint', None)
        
        # 检查是否已有相同指纹的 open issue
        if fingerprint:
            for existing_id, existing_issue in self.data['issues'].items():
                if (existing_issue.get('status') == 'open' and
                    existing_issue.get('command_fingerprint') == fingerprint and
                    existing_issue.get('level') == level):
                    # 记录为关联风险，不新建
                    self._add_finding_to_current({
                        "type": "risk_duplicate",
                        "level": level,
                        "desc": desc,
                        "issue_id": existing_id
                    })
                    return None  # 跳过创建
        
        # 创建新 issue，带指纹
        issue_dict = asdict(Issue(...))
        issue_dict['command_fingerprint'] = fingerprint
        self.data['issues'][issue_id] = issue_dict
        return issue_id
```

#### 3.2.2 详细 Desc 生成 (sys_audit.py)

```python
# 收集所有 bottleneck 进程的详细信息
all_bottlenecks: List[ProcessGroup] = []
if diagnosis.primary_suspect:
    all_bottlenecks.append(diagnosis.primary_suspect)
all_bottlenecks.extend(diagnosis.secondary_loads)

# 构建详细描述
if all_bottlenecks:
    summary = f"发现 {len(all_bottlenecks)} 个关键性能瓶颈"
    details = []
    for i, g in enumerate(all_bottlenecks[:5], 1):
        sys_ratio = (g.kernel_cpu / g.total_cpu * 100) if g.total_cpu > 0 else 0
        details.append(
            f"#{i} {g.comm}: {g.total_cpu:.1f}% CPU "
            f"(sys: {g.kernel_cpu:.1f}%/{sys_ratio:.0f}%, "
            f"pids: {g.pid_count}, score: {g.impact_score:.1f}, "
            f"type: {g.diagnosis})"
        )
    
    detailed_message = summary + " | " + "; ".join(details)
```

#### 3.2.3 Hint 模板更新 (builders.py)

```python
def _generate_hint_from_message(self, message: str) -> str:
    """根据 risk message 生成 hint"""
    message_lower = message.lower()
    
    if '内核' in message_lower or 'kernel' in message_lower:
        return "get-hotspots --comm $COMM && find-callers --target <top_symbol>"
    elif '锁' in message_lower or 'lock' in message_lower:
        return "get-hotspots --comm $COMM && find-callers --target <lock_symbol>"
    elif 'cpu' in message_lower or '瓶颈' in message_lower:
        return "get-hotspots --comm $COMM && find-callers --target <top_symbol>"
    else:
        return "get-hotspots --comm $COMM"
```

---

## 4. 效果验证

### 4.1 去重效果

```bash
# 第一次执行
$ shecr sys-audit
# 创建 ISS-001

# 重复执行（相同参数）
$ shecr sys-audit
# Timeline 记录 risk_duplicate，不创建新 issue

# 不同参数
$ shecr sys-audit --top-n 3
# 创建 ISS-002（不同指纹）
```

### 4.2 完整信息展示

```bash
$ shecr trace issues
[OPEN] [ISS-001] [CRITICAL] <X0> 发现 4 个关键性能瓶颈 | 
#1 netstat: 288.3% CPU (sys: 273.7%/95%, pids: 78, score: 493.9, type: BOTTLENECK); 
#2 python3: 189.7% CPU (sys: 65.7%/35%, pids: 34, score: 268.7, type: BOTTLENECK); 
#3 hacontrol: 218.9% CPU (sys: 36.5%/17%, pids: 29, score: 266.1, type: BOTTLENECK); 
#4 dbatman: 200.7% CPU (sys: 29.2%/15%, pids: 50, score: 244.6, type: BOTTLENECK)

→ get-hotspots --comm $COMM && find-callers --target <top_symbol>
```

### 4.3 排序一致性

```bash
$ shecr sys-audit
[RISK-CRITICAL] <X0> 发现 4 个关键性能瓶颈 | #1 netstat, #2 python3, #3 hacontrol...

### Top 进程 (按危害指数排序)
   1. netstat     # 与 Risk 消息顺序一致
   2. python3
   3. hacontrol
```

---

## 5. 方法论映射：SHECR 五原则的实现

| 原则 | 设计决策 | 代码体现 |
|------|---------|----------|
| **S**ystematic | Hint 指向具体工具 | `get-hotspots --comm $COMM && find-callers --target <top_symbol>` |
| **H**ypothesis | 详细证据支持假设验证 | desc 包含 CPU/sys/pids/score/type 完整数据 |
| **E**vidence | 信息不截断 | 每个 bottleneck 的完整指标 |
| **C**ontrolled | 命令指纹去重 | `_current_fingerprint` + `command_fingerprint` |
| **R**easoning | 排序一致 | 统一使用 `diagnosis` 中的排序结果 |

---

## 6. 相关文档

- **三层架构设计**: [design-three-tier-architecture.md](./design-three-tier-architecture.md)
- **分层调试方法论**: [methodology-hierarchical-debugging.md](./methodology-hierarchical-debugging.md)
- **Trace 接口设计**: [trace-interface.md](./trace-interface.md)
- **SHECR 方法论**: [SKILL.md](../SKILL.md)

---

## 7. 总结

本次 `sys-audit` 重构不是简单的 Bug 修复，而是**方法论原则在代码层面的具体实现**：

1. **Controlled** → 命令指纹去重，防止诊断过程失控
2. **Evidence** → 完整 desc，确保证据链完整
3. **Systematic** → Hint 指向具体工具，形成递进诊断链
4. **Reasoning** → 排序一致，逻辑可追溯

这些修改使 `sys-audit` 真正成为符合 SHECR 方法论的系统级诊断入口。
