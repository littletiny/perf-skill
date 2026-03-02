# Trace 接口设计文档

> 技术实现规格说明
> 版本: 2.0
> 创建时间: 2026-02-28
> 更新日期: 2026-03-03
>
> **本次更新**: 适配三层架构设计，明确Trace边界（Composite记录，Analysis内部不记录）

---

## 1. 概述

### 1.1 目的

定义 `shecr trace` 工具的命令行接口、数据格式和集成方式。

### 1.2 设计原则

- **极简**: 3 个核心命令（add / complete / list）
- **扁平**: JSON 结构最多 2 层
- **强制**: finalize 是结束诊断的必要步骤
- **分层**: 三层架构下的Trace边界
  - **Composite层**: 记录顶层命令到timeline
  - **Analysis层**: CLI调用记录，内部调用不记录
  - **Core层**: 不记录Trace

---

## 2. 数据格式

### 2.1 文件路径

```
.shecr.json  # 当前工作目录
或
~/.perf-diagnosis/<data-file-basename>.json  # 全局存储
```

### 2.2 完整结构

```json
{
  "version": "2.0",
  "data_file": "string",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "timeline": [
    {
      "command": "sys-audit --data perf.data",
      "timestamp": "ISO-8601 timestamp",
      "layer": "composite"
    }
  ],
  "issues": [
    {
      "id": "string",
      "desc": "string",
      "status": "pending | completed",
      "risk": "string (optional)",
      "hint": "string (optional)",
      "result": "string (optional, status=completed)",
      "created_at": "ISO-8601 timestamp",
      "completed_at": "ISO-8601 timestamp (optional)",
      "source_command": "string (optional)"
    }
  ]
}
```

### 2.3 Trace边界说明（三层架构）

```
用户执行: shecr sys-audit --data perf.data

记录行为:
┌─────────────────────────────────────────────────────────┐
│ timeline[0]: command="sys-audit --data perf.data"      │  ◄── 记录（Composite层）
│              layer="composite"                          │
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
│              layer="analysis"                           │
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

### 2.4 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| version | string | 是 | 文档格式版本（当前 2.0） |
| data_file | string | 是 | 关联的 perf 数据文件 |
| created_at | string | 是 | 文档创建时间 |
| updated_at | string | 是 | 最后更新时间 |
| timeline | array | 是 | 命令执行时间线 |
| timeline[].command | string | 是 | 执行的命令 |
| timeline[].timestamp | string | 是 | 执行时间 |
| timeline[].layer | string | 是 | 命令层级: composite / analysis |
| issues | array | 是 | 问题列表 |
| issues[].id | string | 是 | 唯一标识符，如 ISS-001 |
| issues[].desc | string | 是 | 问题描述 |
| issues[].status | string | 是 | pending 或 completed |
| issues[].risk | string | 否 | 不处理的风险 |
| issues[].hint | string | 否 | 建议的下一步操作 |
| issues[].result | string | 否 | 分析结果（completed 时必填）|
| issues[].created_at | string | 是 | 问题创建时间 |
| issues[].completed_at | string | 否 | 问题完成时间 |
| issues[].source_command | string | 否 | 触发该issue的命令（如 sys-audit）|

### 2.5 示例（v2.0 三层架构）

**场景**: 用户执行 `sys-audit`，内部调用多个analysis工具

```json
{
  "version": "2.0",
  "data_file": "netstat_perf.data",
  "created_at": "2026-02-28T10:00:00Z",
  "updated_at": "2026-02-28T11:30:00Z",
  "timeline": [
    {
      "command": "sys-audit --data netstat_perf.data",
      "timestamp": "2026-02-28T10:05:00Z",
      "layer": "composite"
    },
    {
      "command": "bottleneck-trace --comm app_worker --data netstat_perf.data",
      "timestamp": "2026-02-28T10:15:00Z",
      "layer": "composite"
    }
  ],
  "issues": [
    {
      "id": "ISS-001",
      "desc": "app_worker 核心独占率 0.92（单核瓶颈）",
      "status": "completed",
      "risk": "独占Core #7导致响应延迟",
      "hint": "bottleneck-trace --comm app_worker",
      "result": "spinlock_wait 85% - 数据库查询触发锁竞争",
      "created_at": "2026-02-28T10:05:00Z",
      "completed_at": "2026-02-28T10:20:00Z",
      "source_command": "sys-audit"
    },
    {
      "id": "ISS-002",
      "desc": "lsof 进程风暴 2000个（Spawn Rate 100/s）",
      "status": "pending",
      "risk": "虽然CPU总量高但分布均匀，可能被误判为主要瓶颈",
      "hint": "find-callers --target do_fork --comm lsof",
      "created_at": "2026-02-28T10:05:00Z",
      "source_command": "sys-audit"
    }
  ]
}
```

**注意**: timeline只记录了`sys-audit`和`bottleneck-trace`两个composite命令，
没有记录内部的`detect-anomalies`、`get-comm-top`、`get-hotspots`等analysis调用。

---

## 3. CLI 接口

### 3.1 命令总览

```bash
shecr trace init                    # 初始化文档
shecr trace add [options]           # 添加问题
shecr trace complete [options]      # 标记完成
shecr trace list [options]          # 列出所有问题
shecr trace finalize [options]      # 最终审计
shecr trace export [options]        # 导出为其他格式
```

### 3.2 init - 初始化文档

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
✓ 创建诊断文档: .shecr.json
  数据文件: netstat_perf.data
```

**示例**:
```bash
shecr trace init --data netstat_perf.data
```

---

### 3.3 add - 添加问题

**用途**: 记录新发现的问题或风险

**用法**:
```bash
shecr trace add --id <id> --desc <desc> [--risk <risk>] [--hint <hint>]
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --id | string | 是 | 问题唯一标识，如 ISS-001 |
| --desc | string | 是 | 问题描述 |
| --risk | string | 否 | 不处理此问题的风险 |
| --hint | string | 否 | 建议的下一步操作 |

**输出**:
```
✓ 已添加问题: ISS-002
  描述: containerd-shim 高内核态 89.9%
  风险: 可能比 netstat 更严重
```

**示例**:
```bash
shecr trace add --id ISS-002 \
  --desc "containerd-shim 高内核态 89.9%" \
  --risk "可能比 netstat 更严重，单进程影响大" \
  --hint "bottleneck-trace --comm containerd-shim"
```

---

### 3.4 complete - 标记完成

**用途**: 标记问题已分析完毕

**用法**:
```bash
shecr trace complete --id <id> --result <result>
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --id | string | 是 | 问题标识 |
| --result | string | 是 | 分析结果和结论 |

**输出**:
```
✓ 已完成: ISS-001
  结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争
```

**示例**:
```bash
shecr trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
```

---

### 3.5 list - 列出问题

**用途**: 查看所有问题状态，核心审计命令

**用法**:
```bash
shecr trace list [--format <format>] [--status <status>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --format | string | 否 | text | 输出格式: text / json |
| --status | string | 否 | all | 过滤状态: pending / completed / all |

**text 格式输出**:
```
═══════════════════════════════════════════════════════════════════
ISSUES  STATUS  (1 completed, 1 pending)
═══════════════════════════════════════════════════════════════════

✅ COMPLETED
───────────────────────────────────────────────────────────────────
ISS-001  netstat 高内核态 94.7%
         └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

⚠️  PENDING  ← 需处理
───────────────────────────────────────────────────────────────────
ISS-002  containerd-shim 高内核态 89.9%
         ├─ 风险: 可能比 netstat 更严重，单进程影响大
         └─ 建议: cluster-symbols --comm containerd-shim

═══════════════════════════════════════════════════════════════════
```

**json 格式输出**:
```json
{
  "pending_count": 1,
  "completed_count": 1,
  "can_converge": false,
  "pending": [
    {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "risk": "可能比 netstat 更严重，单进程影响大",
      "next_step": "bottleneck-trace --comm containerd-shim"
    }
  ],
  "completed": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
    }
  ]
}
```

**示例**:
```bash
shecr trace list                    # 默认 text 格式
shecr trace list --format json      # JSON 格式
shecr trace list --status pending   # 只显示待处理
```

---

### 3.6 finalize - 最终审计

**用途**: 结束诊断前的强制检查点

**用法**:
```bash
shecr trace finalize [--accept-risk <reason>] [--format <format>]
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --accept-risk | string | 否 | 接受剩余风险的理由 |
| --format | string | 否 | 输出格式: text / json |

**行为**:
1. 检查 pending issues 列表
2. 如有 pending，展示并要求选择
3. 如无 pending，生成完成报告

**有 pending 时的输出**:
```
═══════════════════════════════════════════════════════════════════
最终全局审计
═══════════════════════════════════════════════════════════════════

⚠️  剩余风险确认
───────────────────────────────────────────────────────────────────
以下问题尚未处理：

ISS-002  containerd-shim 高内核态 89.9%
  - 状态: 完全未分析
  - 风险: 锁竞争可能 >50%，单进程影响大于 netstat

───────────────────────────────────────────────────────────────────
强制选择
───────────────────────────────────────────────────────────────────

[A] 继续分析剩余问题（推荐）
    执行: bottleneck-trace --comm containerd-shim

[B] 接受风险，生成报告
    必须提供理由（使用 --accept-risk）

[C] 标记为无需处理
    执行: shecr trace complete --id ISS-002 --result "wontfix: <理由>"

═══════════════════════════════════════════════════════════════════
ERROR: 存在未处理问题，无法直接生成报告
请选择 [A/B/C] 或提供 --accept-risk
```

**无 pending 时的输出**:
```
═══════════════════════════════════════════════════════════════════
最终全局审计
═══════════════════════════════════════════════════════════════════

✅ 所有问题已处理

已完成清单:
  ISS-001  netstat 高内核态 94.7% → LOCK_CONTENTION 38.36%
  ISS-002  containerd-shim 高内核态 89.9% → LOCK_CONTENTION 79.84%

═══════════════════════════════════════════════════════════════════
✓ 可以生成诊断报告
═══════════════════════════════════════════════════════════════════
```

**示例**:
```bash
shecr trace finalize                                    # 交互式选择
shecr trace finalize --accept-risk "与当前问题无关"      # 接受风险
```

---

### 3.7 export - 导出

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
```

---

## 4. 集成到 shecr（三层架构）

### 4.1 自动记录机制

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

### 4.2 集成命令

```bash
# 通过 shecr 调用
shecr trace init --data <file>
shecr trace add --desc <desc> [--hint <hint>]
shecr trace complete --id <id> --result <result>
shecr trace issues [--status open|resolved|all]
shecr trace finalize
```

---

## 5. 使用流程示例

### 5.1 完整诊断流程（推荐：组合命令入口）

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
shecr trace list
# 输出: 2 pending (ISS-001, ISS-002)

# 4. 深度分析主要瓶颈
shecr bottleneck-trace --comm app_worker --data netstat_perf.data
# 输出: spinlock_wait 85% - 数据库查询触发锁竞争
# 自动记录到timeline: bottleneck-trace
shecr trace complete --id ISS-001 --result "spinlock_wait 85% - 数据库查询触发锁竞争"

# 5. 分析进程风暴源头
shecr find-callers --target do_fork --comm lsof --data netstat_perf.data
# 输出: 所有lsof追溯到app_worker调用的system()函数
shecr trace complete --id ISS-002 --result "lsof风暴由app_worker超时处理逻辑触发"

# 6. 最终审计
shecr trace finalize
# 输出: ✅ 所有问题已处理

# 7. 导出报告
shecr trace export --format markdown --output diagnosis-report.md
```

### 5.2 传统方式（单工具调用）

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
shecr trace add --id ISS-001 --desc "app_worker 高内核态" \
  --hint "find-callers --target spinlock_wait --comm app_worker"

# 4. 继续分析...
```

---

## 6. 错误处理

### 6.1 常见错误

| 错误 | 原因 | 处理 |
|------|------|------|
| Document not found | 未执行 init | 提示执行 shecr trace init |
| Duplicate issue ID | ID 已存在 | 提示使用新的 ID |
| Issue not found | complete 时 ID 不存在 | 提示检查 ID |
| Cannot converge | finalize 时有 pending | 强制要求处理或提供理由 |

### 6.2 错误输出示例

```
ERROR: Document not found

请先初始化诊断文档:
  shecr trace init --data <perf-data-file>
```

```
ERROR: Duplicate issue ID 'ISS-001'

该 ID 已存在:
  ISS-001: netstat 高内核态 94.7% (pending)

请使用新的 ID:
  shecr trace add --id ISS-004 ...
```

---

## 7. 参考实现

### 7.1 Python 类设计

```python
# perf_toolkit/core/live_doc.py

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class LiveDoc:
    """Trace for tracking diagnostic issues"""

    DEFAULT_PATH = ".shecr.json"

    def __init__(self, path: Optional[str] = None):
        self.path = path or self._find_doc()
        self.data = self._load()

    def _find_doc(self) -> str:
        """Find existing doc or return default path"""
        if os.path.exists(self.DEFAULT_PATH):
            return self.DEFAULT_PATH
        # TODO: Check ~/.perf-diagnosis/
        return self.DEFAULT_PATH

    def _load(self) -> Dict:
        """Load document from disk"""
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"version": "1.0", "issues": []}

    def save(self):
        """Save document to disk"""
        self.data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def init(self, data_file: str, path: Optional[str] = None):
        """Initialize new document"""
        if path:
            self.path = path

        self.data = {
            "version": "1.0",
            "data_file": data_file,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "issues": []
        }
        self.save()
        return self

    def add(self, id: str, desc: str, risk: str = "", hint: str = ""):
        """Add new issue"""
        # Check duplicate
        if any(i["id"] == id for i in self.data["issues"]):
            raise ValueError(f"Duplicate issue ID: {id}")

        issue = {
            "id": id,
            "desc": desc,
            "status": "pending",
            "risk": risk,
            "hint": hint,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        self.data["issues"].append(issue)
        self.save()
        return self

    def complete(self, id: str, result: str):
        """Mark issue as completed"""
        for issue in self.data["issues"]:
            if issue["id"] == id:
                issue["status"] = "completed"
                issue["result"] = result
                issue["completed_at"] = datetime.utcnow().isoformat() + "Z"
                self.save()
                return self

        raise ValueError(f"Issue not found: {id}")

    def list(self, status: str = "all") -> Dict:
        """List issues"""
        issues = self.data["issues"]

        if status == "pending":
            issues = [i for i in issues if i["status"] == "pending"]
        elif status == "completed":
            issues = [i for i in issues if i["status"] == "completed"]

        pending = [i for i in issues if i["status"] == "pending"]
        completed = [i for i in issues if i["status"] == "completed"]

        return {
            "pending_count": len(pending),
            "completed_count": len(completed),
            "can_converge": len(pending) == 0,
            "pending": pending,
            "completed": completed
        }

    def next_id(self) -> str:
        """Generate next issue ID"""
        count = len(self.data["issues"]) + 1
        return f"ISS-{count:03d}"
```

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-02-28 | 初始设计 |
| 2.0 | 2026-03-03 | 适配三层架构 |
| | | - 新增timeline字段，记录命令层级 |
| | | - 新增layer字段（composite/analysis） |
| | | - 明确Trace边界：Composite记录，Analysis内部调用不记录 |
| | | - 新增source_command字段标记issue来源 |

## 9. 三层架构Trace规范

### 9.1 记录规则

| 场景 | 是否记录 | 示例 |
|------|----------|------|
| 用户执行Composite命令 | ✅ 记录 | `sys-audit`, `bottleneck-trace` |
| 用户执行Analysis命令 | ✅ 记录 | `get-comm-top`, `get-hotspots` |
| Composite内部调用Analysis | ❌ 不记录 | `facade.analyze_comm_top()` |
| Analysis内部调用Core | ❌ 不记录 | `engine.get_comm_cpu_util()` |

### 9.2 问题来源标记

issue的`source_command`字段标记触发该issue的命令：

```json
{
  "issues": [
    {
      "id": "ISS-001",
      "desc": "app_worker 核心独占率 0.92",
      "source_command": "sys-audit"
    }
  ]
}
```

这有助于追溯：
- 该issue是通过哪个composite命令发现的
- 诊断路径的完整性

---

## 10. 参考文档

- [设计意图文档](./design-rationale-trace-v1.md)
- [三层架构设计](./design-three-tier-architecture.md)
- [SKILL.md](../SKILL.md)
- [workflow.md](../references/workflow.md)
