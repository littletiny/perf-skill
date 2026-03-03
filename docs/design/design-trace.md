# Trace 机制设计文档

> Trace 是 perf-hunter 的诊断过程追踪工具，确保性能诊断的完整性和可追溯性。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-02-28 | 初始设计 - 手动记录机制 |
| | | - 基础 issues 列表结构 |
| | | - `add/complete/issues/finalize` 命令 |
| 2.0 | 2026-03-03 | 演进设计 - 自动记录机制 |
| | | - 新增 timeline 字段，记录完整诊断时间线 |
| | | - 新增 findings 机制，双向关联 timeline 和 issues |
| | | - issues 结构从数组改为字典（以 issue_id 为键） |
| | | - 新增 reopen 功能支持 |
| | | - 新增 audit 命令进行质量审计 |
| | | - 适配三层架构，明确 Trace 记录边界 |

---

## 背景与问题发现

### 真实案例回顾

在某次性能诊断中，分析 `netstat_perf.data` 数据时发现：

```
get-comm-top 输出:
  netstat:          2623 PIDs, 243.87% CPU, 94.7% kernel
  python3:           826 PIDs, 207.17% CPU, 35.2% kernel
  dbatman:           311 PIDs, 147.94% CPU, 26.4% kernel
  containerd-shim:   240 PIDs,  96.01% CPU, 89.9% kernel  ← 最初遗漏
```

**实际分析路径**:
1. 被 netstat 的 2623 PIDs 吸引注意力
2. 执行 cluster-symbols --comm netstat → LOCK_CONTENTION 38.36%
3. 得出结论：netstat 进程风暴导致锁竞争
4. **遗漏**: 未分析 containerd-shim (89.9% kernel)

**事后发现**:
```
shecr cluster-symbols --comm containerd-shim → LOCK_CONTENTION 79.84%
```

containerd-shim 的锁竞争比例是 netstat 的 **2 倍**，但 PID 数只有 9%。

### 造成的后果

- 诊断结论不完整
- 修复 netstat 后系统仍可能有问题
- 需要二次分析，浪费时间

### 根本原因分析

诊断过程分析：

```
标准SHECR流程要求:              实际执行:
  ├─ 并行验证假设                只验证了netstat
  └─ 全局一致性检查              遗漏了containerd-shim
```

**搜索覆盖率**: 1/4 = 25% (严重不足)

| 原因 | 说明 |
|------|------|
| 人脑记忆有限 | 工具输出后靠人脑记忆，信息必然淹没 |
| 无客观审计 | 没有机制检查"还有哪些没分析" |
| 数字偏见 | 2623 vs 240，被大数字吸引 |
| 缺乏强制收敛检查 | 找到根因后没有机制阻止提前收敛 |

**现有 Skill 的不足**:
- "列出 ≥3 条竞争性假设" → 只要求假设数量，不要求验证覆盖
- "延迟收敛" → 原则抽象，无量化指标
- "全局一致性检查" → 依赖人工执行，无强制

**根本问题**: 规则停留在"建议"层面，无强制力。

---

## 设计演进

### v1.0 手动记录机制

**设计目标**:
1. **追加问题**: 发现风险时立即记录
2. **完成标记**: 分析完毕后标记状态
3. **强制审计**: 生成报告前必须检查剩余风险
4. **扁平结构**: 对 agent 友好，JSON 不超过 2 层

**核心机制**:

```
诊断流程:
  1. shecr trace init              # 初始化文档
  2. 分析工具执行                  # 发现问题
  3. shecr trace add --id ...      # 手动记录问题
  4. shecr trace issues            # 查看待办问题列表
  5. 继续分析                      # 处理问题
  6. shecr trace complete --id ... # 标记完成
  7. shecr trace finalize          # 最终审计
  8. shecr trace export            # 导出报告
```

**数据结构**:
```json
{
  "version": "1.0",
  "data_file": "netstat_perf.data",
  "issues": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "completed",
      "result": "LOCK_CONTENTION 38.36%",
      "completed_at": "2026-02-28T11:00:00Z"
    },
    {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "status": "pending",
      "risk": "可能比 netstat 更严重",
      "hint": "cluster-symbols --comm containerd-shim"
    }
  ]
}
```

### v1.0 的问题

v1.0 设计需要**人工执行** `shecr trace add` 和 `shecr trace complete`：

```bash
# 发现问题
perf-exp get-comm-top --data xxx.data
# 输出提示: [必须] 添加到 Trace...

# 必须人工执行！
shecr trace add --id ISS-001 --desc "xxx" --risk "xxx"

# 分析完再人工标记完成
shecr trace complete --id ISS-001 --result "xxx"
```

**问题**：提示容易被忽略，agent 可能忘记执行。

### v2.0 自动记录机制

| 维度 | v1.0 | v2.0 |
|------|------|------|
| 记录方式 | 手动 `add/complete` | **全自动** |
| 数据结构 | issues 列表 | **timeline + issues** |
| 链接关系 | 无 | **双向引用** |
| 使用模式 | 状态跟踪 | **tracing 追溯** |

**核心概念**:

```
┌─────────────────────────────────────────────────────────────┐
│                      Trace v2.0                      │
├─────────────────────────────────────────────────────────────┤
│  timeline: [CommandRecord]  ← 按时间顺序记录所有命令执行      │
│  issues: {issue_id: Issue}  ← 问题聚合状态                   │
│  links: 双向引用，timeline 和 issues 互相指向                │
└─────────────────────────────────────────────────────────────┘
```

**OutputBuilder 集成**:

```python
# 伪代码
class OutputBuilder:
    def __init__(self, engine, args):
        self.live_doc = LiveDoc()  # 自动加载或创建
        self.current_seq = None

    def begin_command(self, command_name):
        """命令开始时记录"""
        self.current_seq = self.live_doc.record_command(command_name)

    def record_risk(self, level, desc, hint=""):
        """检测到风险时自动创建 issue"""
        issue_id = self.live_doc.create_issue(
            level=level,
            desc=desc,
            hint=hint,
            command_seq=self.current_seq
        )
        return issue_id

    # ❌ 不提供自动解决功能
    # def record_resolution(self, issue_id, result): ...

    def end_command(self):
        """命令结束时保存"""
        self.live_doc.save()
```

**为什么只添加不解决？**
- 自动解决容易误判（无法确定分析是否充分）
- 解决 issue 是**决策行为**，需要人工确认
- 保持灵活性：分析后可以选择继续深入或标记完成

**使用示例**:
```python
def cmd_get_comm_top(engine, args):
    builder = OutputBuilder(engine, args)

    # 1. 自动记录命令开始
    builder.begin_command("get-comm-top")

    # ... 分析逻辑 ...

    # 2. 发现风险时自动创建 issue
    for comm in high_kernel_comms:
        builder.record_risk(
            level="warning",
            desc=f"{comm} 高内核态 94.7%",
            hint=f"cluster-symbols --comm {comm}"
        )

    # 3. 自动保存
    builder.end_command()
```

**解决 issue 仍需人工执行**：
```bash
# 分析后，人工确认并标记完成
shecr trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"
```

---

## 数据格式

### 文件路径

```
.shecr.json  # 当前工作目录
或
~/.perf-diagnosis/<data-file-basename>.json  # 全局存储
```

### 完整结构

```json
{
  "version": "2.0",
  "data_file": "string",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "timeline": [
    {
      "seq": 1,
      "type": "command",
      "command": "sys-audit --data perf.data",
      "timestamp": "ISO-8601 timestamp",
      "findings": [
        {
          "type": "risk_created",
          "level": "warning",
          "desc": "netstat 高内核态 94.7%",
          "issue_id": "ISS-001"
        }
      ]
    }
  ],
  "issues": {
    "ISS-001": {
      "id": "ISS-001",
      "desc": "string",
      "level": "critical | warning | info",
      "status": "open | resolved",
      "created_at": "ISO-8601 timestamp",
      "created_by_seq": 1,
      "resolved_at": "ISO-8601 timestamp (optional)",
      "resolved_by_seq": 2,
      "result": "string (optional)",
      "results": [...],
      "hint": "string (optional)",
      "reopen_history": []
    }
  }
}
```

### 字段说明

**根级别字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| version | string | 是 | 文档格式版本（当前 2.0） |
| data_file | string | 是 | 关联的 perf 数据文件 |
| created_at | string | 是 | 文档创建时间 |
| updated_at | string | 是 | 最后更新时间 |
| timeline | array | 是 | 命令执行时间线 |
| issues | object | 是 | 问题字典（以 issue_id 为键） |

**timeline[n] - 命令执行记录**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| seq | int | 是 | 全局序号，从1开始 |
| type | string | 是 | 固定为 "command" |
| command | string | 是 | 完整命令行 |
| timestamp | string | 是 | ISO-8601 时间戳 |
| findings | array | 是 | 该命令的发现/操作 |

**findings[n] - 发现/操作**

| type | 说明 |
|------|------|
| risk_created | 发现新风险，创建 issue |
| info | 一般信息/分析结果记录 |

**注意**: 不提供 `issue_resolved` 类型，解决 issue 需要人工执行命令。

**issues[id] - 问题聚合**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识符，如 ISS-001 |
| desc | string | 是 | 问题描述 |
| level | string | 是 | 级别: critical / warning / info |
| status | string | 是 | open 或 resolved |
| created_at | string | 是 | 问题创建时间 |
| created_by_seq | int | 是 | 由哪个命令序号创建 |
| resolved_at | string | 否 | 问题完成时间 |
| resolved_by_seq | int | 否 | 解决该问题的命令序号 |
| result | string | 否 | 分析结果（兼容性） |
| results | array | 否 | 解决记录列表（支持 reopen） |
| hint | string | 否 | 建议的下一步操作 |
| reopen_history | array | 否 | 重新打开历史记录 |

---

## CLI 接口

### 命令总览

```bash
shecr trace init                    # 初始化文档
shecr trace add [options]           # 手动添加问题
shecr trace timeline [options]      # 查看诊断时间线
shecr trace issues [options]        # 列出所有问题
shecr trace audit [options]         # 审计已解决问题质量
shecr trace complete [options]      # 标记完成
shecr trace reopen [options]        # 重新打开问题
shecr trace finalize [options]      # 最终审计
shecr trace export [options]        # 导出为其他格式
```

### init - 初始化文档

**用途**: 创建新的诊断文档

**用法**:
```bash
shecr trace init --data <data-file> [--path <doc-path>]
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --data | string | 是 | perf 数据文件路径 |
| --path | string | 否 | 文档存储路径，默认 .shecr.json |

**输出**:
```
[INIT] Created: .shecr.json
→ Data file: netstat_perf.data
```

### add - 手动添加问题

**用途**: 手动记录新发现的问题或风险（v2.0 主要使用自动记录，此命令用于特殊情况）

**用法**:
```bash
shecr trace add --desc <desc> [--level <level>] [--risk <risk>] [--hint <hint>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --desc | string | 是 | - | 问题描述 |
| --level | string | 否 | warning | 级别: critical / warning / info |
| --risk | string | 否 | "" | 不处理此问题的风险 |
| --hint | string | 否 | "" | 建议的下一步操作 |

**输出**:
```
[ADDED] ISS-001
→ Desc: containerd-shim 高内核态 89.9%
→ Hint: bottleneck-trace --comm containerd-shim
```

### timeline - 查看诊断时间线

**用途**: 查看按时间顺序记录的所有命令执行及发现

**用法**:
```bash
shecr trace timeline [--format <format>] [--risk-config <path>] [--risk-style <style>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --format | string | 否 | text | 输出格式: text / json |
| --risk-config | string | 否 | - | Risk 显示配置文件路径 |
| --risk-style | string | 否 | - | Risk 显示样式: default / ci / compact |

**text 格式输出示例**:
```
═══════════════════════════════════════════════════════════════════
DIAGNOSIS TIMELINE  (2 commands executed)
═══════════════════════════════════════════════════════════════════

[1] 10:00:00  get-comm-top --data netstat_perf.data
    ───────────────────────────────────────────────────────────
    ⚠️  RISK_CREATED: ISS-001  netstat 高内核态 94.7%
    ⚠️  RISK_CREATED: ISS-002  containerd-shim 高内核态 89.9%

[2] 10:01:00  cluster-symbols --comm netstat --data netstat_perf.data
    ───────────────────────────────────────────────────────────
    ℹ️  分析结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争
        (ISS-001 仍需人工确认: shecr trace complete --id ISS-001 --result "...")

═══════════════════════════════════════════════════════════════════
OPEN ISSUES (2 remaining, 需人工处理)
═══════════════════════════════════════════════════════════════════

⚠️  ISS-001  netstat 高内核态 94.7%
    ├─ 分析结果: LOCK_CONTENTION 38.36%
    └─ 确认解决: shecr trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"

⚠️  ISS-002  containerd-shim 高内核态 89.9%
    └─ 建议: cluster-symbols --comm containerd-shim
═══════════════════════════════════════════════════════════════════
```

### issues - 列出问题

**用途**: 查看所有问题状态，核心审计命令

**用法**:
```bash
shecr trace issues [--status <status>] [--risk-config <path>] [--risk-style <style>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --status | string | 否 | all | 过滤状态: open / resolved / all |
| --risk-config | string | 否 | - | Risk 显示配置文件路径 |
| --risk-style | string | 否 | - | Risk 显示样式: default / ci / compact |

**text 格式输出**:
```
[ALL] 1 open, 1 resolved

[RESOLVED] [ISS-001] [WARNING] app_worker 核心独占率 0.92
[创建] app_worker 核心独占率 0.92 → [解决] spinlock_wait 85%

[OPEN] [ISS-002] [WARNING] containerd-shim 高内核态 89.9%
→ bottleneck-trace --comm containerd-shim
```

### audit - 审计已解决问题质量

**用途**: 对 resolved issues 进行质量审计，检查分析深度

**用法**:
```bash
shecr trace audit [--phase <phase>] [--format <format>] [--output <path>] [--no-fail]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --phase | string | 否 | all | 审计阶段: all / structural / timeline / depth |
| --format | string | 否 | text | 输出格式: text / json |
| --output | string | 否 | stdout | 输出文件路径 |
| --no-fail | flag | 否 | - | 失败时不以错误码退出 |
| --risk-config | string | 否 | - | Risk 显示配置文件路径 |
| --risk-style | string | 否 | - | Risk 显示样式: default / ci / compact |

**审计检查项**:
- **structural**: 检查结果是否过短或敷衍（如 "ok", "fixed"）
- **timeline**: 检查是否有足够的分析命令关联
- **depth**: 检查是否包含因果推理关键词（如 "because", "caused by", "原因"）

**text 格式输出**:
```
=================================================================
AUDIT REPORT
=================================================================
Total: 2, Passed: 1, Warning: 1, Failed: 0

[PASSED] ISS-001: app_worker 核心独占率 0.92
  ✓ structural: passed
  ✓ timeline: 2 analysis commands found
  ✓ depth: passed

[WARNING] ISS-002: containerd-shim 高内核态 89.9%
  ✓ structural: passed
  ✓ timeline: passed
  ⚠ depth: Result lacks causal reasoning (no depth keywords)
```

### complete - 标记完成

**用途**: 标记问题已分析完毕

**用法**:
```bash
shecr trace complete --id <id> --result <result>
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --id | string | 是 | Issue 标识符 |
| --result | string | 是 | 分析结果和结论 |

**输出**:
```
[COMPLETED] ISS-001
→ Result: spinlock_wait 85% - 数据库查询触发锁竞争

[ALL DONE] No more issues
```

### reopen - 重新打开问题

**用途**: 重新打开已解决的 issue，支持添加原因

**用法**:
```bash
shecr trace reopen --id <id> [--reason <reason>]
shecr trace reopen --all [--reason <reason>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --id | string | 否 | - | Issue 标识符（与 --all 二选一） |
| --all | flag | 否 | - | 重新打开所有已解决问题 |
| --reason | string | 否 | "" | 重新打开的原因 |

**输出**:
```
[REOPENED] ISS-001
→ Reason: 发现新的调用路径

→ 2 issues now open
```

### finalize - 最终审计

**用途**: 结束诊断前的强制检查点

**用法**:
```bash
shecr trace finalize [--accept-risk <reason>] [--format <format>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --accept-risk | string | 否 | - | 接受剩余风险的理由 |
| --format | string | 否 | text | 输出格式: text / json |
| --risk-config | string | 否 | - | Risk 显示配置文件路径 |
| --risk-style | string | 否 | - | Risk 显示样式: default / ci / compact |

**行为**:
1. 检查 open issues 列表
2. 如有 pending，展示并要求选择
3. 如无 pending，生成完成报告

**无 pending 时的输出**:
```
=================================================================
FINALIZE - Ready to generate report?
=================================================================

[READY] All issues resolved
→ Total resolved: 2

=================================================================
Report can be generated
=================================================================
```

**有 pending 时的输出**:
```
=================================================================
FINALIZE - Ready to generate report?
=================================================================

[BLOCKED] 1 open issues remaining

Note: This is NOT an audit. Use 'shecr trace audit' for quality review.

[WARNING] ISS-002: containerd-shim 高内核态 89.9%
→ bottleneck-trace --comm containerd-shim

-----------------------------------------------------------------
[A] Continue analysis (recommended)
[B] Accept risk and finalize: --accept-risk 'reason'
=================================================================
```

### export - 导出

**用途**: 导出为其他格式（markdown 报告等）

**用法**:
```bash
shecr trace export [--format <format>] [--output <path>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --format | string | 否 | markdown | 导出格式: markdown / json |
| --output | string | 否 | stdout | 输出路径 |

---

## 三层架构集成

### Trace 边界说明

```
用户执行: shecr sys-audit --data perf.data

记录行为:
┌─────────────────────────────────────────────────────────┐
│ timeline[0]: command="sys-audit --data perf.data"      │  ◄── 记录（Composite层）
│              type="command"                             │
└─────────────────────────────────────────────────────────┘
                          │
                    内部调用（不记录）
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   detect-anomalies  core-distribution   get-comm-top
   （不记录）         （不记录）          （不记录）

用户执行: shecr get-comm-top --data perf.data

记录行为:
┌─────────────────────────────────────────────────────────┐
│ timeline[0]: command="get-comm-top --data perf.data"   │  ◄── 记录（Analysis CLI）
│              type="command"                             │
└─────────────────────────────────────────────────────────┘
```

### 记录规则

| 层级 | 调用方式 | 是否记录 | 示例 |
|------|----------|----------|------|
| Composite | CLI命令 | ✅ 记录 | `sys-audit`, `bottleneck-trace` |
| Analysis | CLI命令 | ✅ 记录 | `get-comm-top`, `get-hotspots` |
| Analysis | 内部调用（Facade） | ❌ 不记录 | `facade.analyze_comm_top()` |
| Analysis | 内部调用Core | ❌ 不记录 | `engine.get_comm_cpu_util()` |

**设计理由**:
- 避免Composite调用多个Analysis工具时timeline被污染
- 用户关心的是"执行了什么诊断"，不是"内部调用了哪些工具"

### Analysis层自动记录示例

```python
# perf_toolkit/analysis/hotspots.py

@command("get-hotspots")
def cmd_get_hotspots(builder, engine, args, samples):
    """CLI入口 - 记录到timeline"""
    # 1. 分析
    analyzer = HotspotsAnalyzer(engine)
    result = analyzer.analyze(samples, ...)
    
    # 2. 自动记录risk到Trace
    for risk_dict in result["risks"]:
        builder.record_risk(
            risk_dict["level"],
            risk_dict["message"],
            risk_dict["hint"]
        )
    
    return output
```

### Composite层自动记录示例

```python
# perf_toolkit/composite/sys_audit.py

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """系统审计 - 只记录顶层，内部调用不记录"""
    from ..analysis.facade import AnalysisFacade
    
    # 创建facade（内部调用，不触发Trace）
    facade = AnalysisFacade(engine)
    
    # 执行多个分析（不记录到timeline）
    anomalies = facade.detect_anomalies(samples)      # 不记录
    core_dist = facade.analyze_core_distribution(samples)  # 不记录
    comm_top = facade.analyze_comm_top(samples)       # 不记录
    
    # 综合分析结果
    diagnosis = _synthesize(anomalies, core_dist, comm_top)
    
    # 记录综合诊断结果
    if diagnosis["primary_suspect"]:
        builder.record_risk(
            "critical",
            f"主要性能瓶颈: {diagnosis['primary_suspect']['comm']}",
            f"执行 bottleneck-trace --comm {diagnosis['primary_suspect']['comm']} 深入分析"
        )
    
    return output
```

**关键区别**:
- Analysis CLI命令（如`get-hotspots`）: 自动记录到timeline
- Composite命令内部通过Facade调用: 不记录到timeline
- Composite命令本身（如`sys-audit`）: 记录到timeline

---

## 使用流程示例

### 完整诊断流程（推荐：组合命令入口）

```bash
# 1. 初始化
shecr trace init --data netstat_perf.data

# 2. 系统全景扫描（自动降噪 + 危害排序）
shecr sys-audit --data netstat_perf.data
# 输出: 
#   - 主要瓶颈: app_worker (Monopoly 0.92)
#   - 次要负载: lsof (Count 2000, 但分布均匀)
#   - 自动记录到timeline: sys-audit
#   - 自动添加issues: ISS-001 (BOTTLENECK), ISS-002 (STORM)

# 3. 检查待办
shecr trace issues
# 输出: 1 open (ISS-002)

# 4. 查看诊断时间线
shecr trace timeline
# 输出: 显示命令执行顺序和发现

# 5. 深度分析主要瓶颈
shecr bottleneck-trace --comm app_worker --data netstat_perf.data
# 输出: spinlock_wait 85% - 数据库查询触发锁竞争
# 自动记录到timeline: bottleneck-trace
shecr trace complete --id ISS-001 --result "spinlock_wait 85% - 数据库查询触发锁竞争"

# 6. 分析进程风暴源头
shecr find-callers --target do_fork --comm lsof --data netstat_perf.data
# 输出: 所有lsof追溯到app_worker调用的system()函数
shecr trace complete --id ISS-002 --result "lsof风暴由app_worker超时处理逻辑触发"

# 7. 审计分析质量
shecr trace audit
# 输出: 检查各issue的分析深度和质量

# 8. 最终审计
shecr trace finalize
# 输出: [READY] All issues resolved

# 9. 导出报告
shecr trace export --format markdown --output diagnosis-report.md
```

### 传统方式（单工具调用）

如果不需要组合命令的智能降噪，仍可使用单个工具：

```bash
# 1. 初始化
shecr trace init --data netstat_perf.data

# 2. 使用单个analysis工具（会自动记录到timeline）
shecr get-comm-top --data netstat_perf.data
# 输出: 进程组分析（含CV/Monopoly指标）
# 自动记录到timeline: get-comm-top

shecr get-hotspots --comm app_worker --data netstat_perf.data
# 输出: 热点函数
# 自动记录到timeline: get-hotspots

# 3. 手动添加issue（特殊情况）
shecr trace add --desc "app_worker 高内核态" \
  --hint "find-callers --target spinlock_wait --comm app_worker"

# 4. 继续分析...
```

---

## 设计决策记录

### 为什么不要奖励机制？

**讨论**:
> 怎么能让 agent 有意愿处理？

**第一轮方案**: 进度条、徽章、积分、成就系统

**反馈**:
> "不要玩那么多奖励机制，太复杂了，直接点"

**决策**:
- 去掉所有激励元素
- 直接展示剩余风险
- 用 SKILL 规范强制要求

**理由**:
- Agent 不需要游戏化激励
- 直接展示后果更有效
- 简单设计更容易落地

### 为什么扁平结构？

**讨论**:
> JSON 结构设计要考虑 agent 友好

**第一轮方案**: 嵌套结构，按 phase 组织

```json
{
  "phases": {
    "phase_2": {
      "critical_findings": {
        "CF-001": {
          "items": [...]
        }
      }
    }
  }
}
```

**问题**:
- 3 层嵌套，解析复杂
- agent 需要理解 phase 概念

**决策**:
- 扁平化为 `issues` 列表
- 最多 2 层嵌套
- 字符串字段为主

### 为什么只有两种状态？

**讨论**:
> 是否需要 in_progress / verified / wontfix 等状态？

**决策**:
- 只有 `pending/open` / `completed/resolved`
- 简化认知负担
- 其他信息放在 `result` 字符串中

### finalize 的必要性

**讨论**:
> 如何强制 agent 看到全貌？

**方案**:
- 单独的 `finalize` 命令
- 输出剩余风险清单
- 必须选择才能退出

**理由**:
- `issues` 可以被忽略
- `finalize` 是显式的"结束仪式"
- 有明确的决策点

---

## 错误处理

### 常见错误

| 错误 | 原因 | 处理 |
|------|------|------|
| Issue not found | complete/reopen 时 ID 不存在 | 提示检查 ID 或使用模糊匹配 |
| Issue is not resolved | reopen 时 issue 不是 resolved 状态 | 提示检查 issue 状态 |
| Must specify --id or --all | reopen 时未指定目标 | 提示使用 --id 或 --all |

---

## Python Trace 类设计参考

```python
# perf_toolkit/core/trace.py

class Trace:
    """
    Trace v2.0 - 诊断过程追踪实现

    数据文件: .shecr.json (当前目录)
    """

    DEFAULT_PATH = ".shecr.json"
    CURRENT_VERSION = "2.0"

    def __init__(self, path: Optional[str] = None, config: RiskDisplayConfig = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self.config = config

    def init(self, data_file: str):
        """初始化新诊断文档"""
        ...

    def begin_command(self, command: str) -> int:
        """命令开始时调用，创建 timeline 记录"""
        ...

    def add(self, desc: str, risk: str = "", hint: str = "", level: str = "warning") -> Optional[str]:
        """添加新 issue（自动生成 ID）"""
        ...

    def complete(self, issue_id: str, result: str):
        """标记 issue 为已完成"""
        ...

    def reopen(self, issue_id: str, reason: str = ""):
        """重新打开已解决的 issue"""
        ...

    def get_open_issues(self) -> List[Dict]:
        """获取所有待处理问题"""
        ...

    def get_resolved_issues(self) -> List[Dict]:
        """获取所有已解决问题"""
        ...

    def get_timeline(self) -> List[Dict]:
        """获取完整时间线"""
        ...

    def finalize(self, accept_risk: Optional[str] = None) -> FinalizeResult:
        """最终审计 - 检查是否可以结束诊断"""
        ...

    def format_timeline(self, cfg: RiskDisplayConfig = None) -> str:
        """格式化 timeline"""
        ...

    def format_issue_list(self, issues: List[Dict], status_filter: str = 'all',
                          cfg: RiskDisplayConfig = None) -> str:
        """格式化 issue 列表"""
        ...

    def export_markdown(self) -> str:
        """导出为 Markdown 报告"""
        ...
```

---

## 参考文档

- [三层架构设计](./design-three-tier-architecture.md)
- [SKILL.md](../SKILL.md)
