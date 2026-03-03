# Trace 接口设计文档

## 概述

### 目的

定义 `shecr trace` 工具的命令行接口、数据格式和集成方式。

### 设计原则

- **极简**: 核心命令简洁
- **扁平**: JSON 结构最多 2 层
- **强制**: finalize 是结束诊断的必要步骤
- **分层**: 三层架构下的Trace边界
  - **Composite层**: 记录顶层命令到timeline
  - **Analysis层**: CLI调用记录，内部调用不记录
  - **Core层**: 不记录Trace

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
      "findings": []
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

### Trace边界说明（三层架构）

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

**记录规则**:
| 层级 | 调用方式 | 是否记录 | 示例 |
|------|----------|----------|------|
| Composite | CLI命令 | ✅ 记录 | `sys-audit`, `bottleneck-trace` |
| Analysis | CLI命令 | ✅ 记录 | `get-comm-top`, `get-hotspots` |
| Analysis | 内部调用（Facade） | ❌ 不记录 | `facade.analyze_comm_top()` |

**设计理由**:
- 避免Composite调用多个Analysis工具时timeline被污染
- 用户关心的是"执行了什么诊断"，不是"内部调用了哪些工具"

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| version | string | 是 | 文档格式版本（当前 2.0） |
| data_file | string | 是 | 关联的 perf 数据文件 |
| created_at | string | 是 | 文档创建时间 |
| updated_at | string | 是 | 最后更新时间 |
| timeline | array | 是 | 命令执行时间线 |
| timeline[].seq | int | 是 | 命令序号 |
| timeline[].type | string | 是 | 记录类型: command |
| timeline[].command | string | 是 | 执行的命令 |
| timeline[].timestamp | string | 是 | 执行时间 |
| timeline[].findings | array | 是 | 该命令产生的发现 |
| issues | object | 是 | 问题字典（以 issue_id 为键） |
| issues[].id | string | 是 | 唯一标识符，如 ISS-001 |
| issues[].desc | string | 是 | 问题描述 |
| issues[].level | string | 是 | 级别: critical / warning / info |
| issues[].status | string | 是 | open 或 resolved |
| issues[].created_at | string | 是 | 问题创建时间 |
| issues[].created_by_seq | int | 是 | 创建该问题的命令序号 |
| issues[].resolved_at | string | 否 | 问题完成时间 |
| issues[].resolved_by_seq | int | 否 | 解决该问题的命令序号 |
| issues[].result | string | 否 | 分析结果（兼容性） |
| issues[].results | array | 否 | 解决记录列表（支持 reopen） |
| issues[].hint | string | 否 | 建议的下一步操作 |
| issues[].reopen_history | array | 否 | 重新打开历史记录 |

---

## CLI 接口

### 命令总览

```bash
shecr trace init                    # 初始化文档
shecr trace add [options]           # 添加问题
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

**示例**:
```bash
shecr trace init --data netstat_perf.data
```

---

### add - 添加问题

**用途**: 手动记录新发现的问题或风险

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

**示例**:
```bash
shecr trace add --desc "containerd-shim 高内核态 89.9%" \
  --risk "可能比 netstat 更严重，单进程影响大" \
  --hint "bottleneck-trace --comm containerd-shim"
```

---

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

**text 格式输出**:
```
[1] 10:05:00 sys-audit --data netstat_perf.data
[WARNING] ISS-001: app_worker 核心独占率 0.92

[2] 10:15:00 bottleneck-trace --comm app_worker --data netstat_perf.data
[RESOLVED] ISS-001: spinlock_wait 85% - 数据库查询触发锁竞争

Commands: 2, Open: 0, Resolved: 1
```

**示例**:
```bash
shecr trace timeline                    # 默认 text 格式
shecr trace timeline --format json      # JSON 格式
```

---

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

**示例**:
```bash
shecr trace issues                    # 默认显示所有
shecr trace issues --status open      # 只显示待处理
shecr trace issues --status resolved  # 只显示已解决
```

---

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

**示例**:
```bash
shecr trace audit                       # 完整审计
shecr trace audit --phase depth         # 仅检查分析深度
shecr trace audit --format json         # JSON 格式输出
shecr trace audit --output report.json  # 保存到文件
```

---

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

**示例**:
```bash
shecr trace complete --id ISS-001 --result "spinlock_wait 85% - 数据库查询触发锁竞争"
```

---

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

**示例**:
```bash
shecr trace reopen --id ISS-001 --reason "发现新的调用路径"
shecr trace reopen --all --reason "需要重新验证所有结论"
```

---

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

**示例**:
```bash
shecr trace finalize                                    # 交互式检查
shecr trace finalize --accept-risk "与当前问题无关"      # 接受风险
```

---

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

**示例**:
```bash
shecr trace export --format markdown --output report.md
shecr trace export --format json --output report.json
```

---

## 集成到 shecr（三层架构）

### 自动记录机制

#### Analysis层（CLI命令）自动记录

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

#### Composite层（组合命令）自动记录

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

# 3. 手动添加issue
shecr trace add --desc "app_worker 高内核态" \
  --hint "find-callers --target spinlock_wait --comm app_worker"

# 4. 继续分析...
```

---

## 错误处理

### 常见错误

| 错误 | 原因 | 处理 |
|------|------|------|
| Issue not found | complete/reopen 时 ID 不存在 | 提示检查 ID 或使用模糊匹配 |
| Issue is not resolved | reopen 时 issue 不是 resolved 状态 | 提示检查 issue 状态 |
| Must specify --id or --all | reopen 时未指定目标 | 提示使用 --id 或 --all |

---

## 参考实现

### Python Trace 类设计

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

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-02-28 | 初始设计 |
| 2.0 | 2026-03-03 | 适配三层架构 |
| | | - 新增 timeline 字段，记录命令层级 |
| | | - 新增 findings 机制，关联 timeline 和 issues |
| | | - 新增 issues 字典结构（原为数组成员） |
| | | - 新增 reopen 功能支持 |
| | | - 新增 audit 命令进行质量审计 |

---

## 三层架构Trace规范

### 记录规则

| 场景 | 是否记录 | 示例 |
|------|----------|------|
| 用户执行Composite命令 | ✅ 记录 | `sys-audit`, `bottleneck-trace` |
| 用户执行Analysis命令 | ✅ 记录 | `get-comm-top`, `get-hotspots` |
| Composite内部调用Analysis | ❌ 不记录 | `facade.analyze_comm_top()` |
| Analysis内部调用Core | ❌ 不记录 | `engine.get_comm_cpu_util()` |

---

## 参考文档

- [设计意图文档](./design-rationale-trace-v1.md)
- [三层架构设计](./design-three-tier-architecture.md)
- [SKILL.md](../SKILL.md)
- [workflow.md](../references/workflow.md)
