# Trace 接口设计文档

> 技术实现规格说明
> 版本: 1.0
> 创建时间: 2026-02-28

---

## 1. 概述

### 1.1 目的

定义 `spear trace` 工具的命令行接口、数据格式和集成方式。

### 1.2 设计原则

- **极简**: 3 个核心命令（add / complete / list）
- **扁平**: JSON 结构最多 2 层
- **强制**: finalize 是结束诊断的必要步骤

---

## 2. 数据格式

### 2.1 文件路径

```
.spear.json  # 当前工作目录
或
~/.perf-diagnosis/<data-file-basename>.json  # 全局存储
```

### 2.2 完整结构

```json
{
  "version": "1.0",
  "data_file": "string",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "issues": [
    {
      "id": "string",
      "desc": "string",
      "status": "pending | completed",
      "risk": "string (optional)",
      "hint": "string (optional)",
      "result": "string (optional, status=completed)",
      "created_at": "ISO-8601 timestamp",
      "completed_at": "ISO-8601 timestamp (optional)"
    }
  ]
}
```

### 2.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| version | string | 是 | 文档格式版本 |
| data_file | string | 是 | 关联的 perf 数据文件 |
| created_at | string | 是 | 文档创建时间 |
| updated_at | string | 是 | 最后更新时间 |
| issues | array | 是 | 问题列表 |
| issues[].id | string | 是 | 唯一标识符，如 ISS-001 |
| issues[].desc | string | 是 | 问题描述 |
| issues[].status | string | 是 | pending 或 completed |
| issues[].risk | string | 否 | 不处理的风险 |
| issues[].hint | string | 否 | 建议的下一步操作 |
| issues[].result | string | 否 | 分析结果（completed 时必填）|
| issues[].created_at | string | 是 | 问题创建时间 |
| issues[].completed_at | string | 否 | 问题完成时间 |

### 2.4 示例

```json
{
  "version": "1.0",
  "data_file": "netstat_perf.data",
  "created_at": "2026-02-28T10:00:00Z",
  "updated_at": "2026-02-28T11:30:00Z",
  "issues": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "completed",
      "risk": "进程风暴可能导致系统卡顿",
      "hint": "cluster-symbols --comm netstat",
      "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争",
      "created_at": "2026-02-28T10:05:00Z",
      "completed_at": "2026-02-28T11:00:00Z"
    },
    {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "status": "pending",
      "risk": "kernel_ratio 接近 netstat 但 PID 数少9倍，单进程影响可能更大",
      "hint": "cluster-symbols --comm containerd-shim",
      "created_at": "2026-02-28T10:10:00Z"
    }
  ]
}
```

---

## 3. CLI 接口

### 3.1 命令总览

```bash
spear trace init                    # 初始化文档
spear trace add [options]           # 添加问题
spear trace complete [options]      # 标记完成
spear trace list [options]          # 列出所有问题
spear trace finalize [options]      # 最终审计
spear trace export [options]        # 导出为其他格式
```

### 3.2 init - 初始化文档

**用途**: 创建新的诊断文档

**用法**:
```bash
spear trace init --data <data-file> [--path <doc-path>]
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --data | string | 是 | perf 数据文件路径 |
| --path | string | 否 | 文档存储路径，默认 .spear.json |

**输出**:
```
✓ 创建诊断文档: .spear.json
  数据文件: netstat_perf.data
```

**示例**:
```bash
spear trace init --data netstat_perf.data
```

---

### 3.3 add - 添加问题

**用途**: 记录新发现的问题或风险

**用法**:
```bash
spear trace add --id <id> --desc <desc> [--risk <risk>] [--hint <hint>]
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
spear trace add --id ISS-002 \
  --desc "containerd-shim 高内核态 89.9%" \
  --risk "可能比 netstat 更严重，单进程影响大" \
  --hint "cluster-symbols --comm containerd-shim"
```

---

### 3.4 complete - 标记完成

**用途**: 标记问题已分析完毕

**用法**:
```bash
spear trace complete --id <id> --result <result>
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
spear trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
```

---

### 3.5 list - 列出问题

**用途**: 查看所有问题状态，核心审计命令

**用法**:
```bash
spear trace list [--format <format>] [--status <status>]
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
      "next_step": "cluster-symbols --comm containerd-shim"
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
spear trace list                    # 默认 text 格式
spear trace list --format json      # JSON 格式
spear trace list --status pending   # 只显示待处理
```

---

### 3.6 finalize - 最终审计

**用途**: 结束诊断前的强制检查点

**用法**:
```bash
spear trace finalize [--accept-risk <reason>] [--format <format>]
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
    执行: cluster-symbols --comm containerd-shim

[B] 接受风险，生成报告
    必须提供理由（使用 --accept-risk）

[C] 标记为无需处理
    执行: spear trace complete --id ISS-002 --result "wontfix: <理由>"

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
spear trace finalize                                    # 交互式选择
spear trace finalize --accept-risk "与当前问题无关"      # 接受风险
```

---

### 3.7 export - 导出

**用途**: 导出为其他格式（markdown 报告等）

**用法**:
```bash
spear trace export [--format <format>] [--output <path>]
```

**参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --format | string | 否 | markdown | 导出格式: markdown / json |
| --output | string | 否 | stdout | 输出路径 |

**示例**:
```bash
spear trace export --format markdown --output report.md
```

---

## 4. 集成到 spear

### 4.1 自动记录机制

分析工具自动调用 `spear trace add` 记录 critical findings:

```python
# perf_toolkit/analysis/hotspots.py
def cmd_get_hotspots(engine, args):
    # ... 分析逻辑 ...

    # 发现高内核态进程
    if kernel_ratio > 0.8:
        doc = LiveDoc()
        doc.add(
            id=f"ISS-{doc.next_id()}",
            desc=f"{comm} 高内核态 {kernel_ratio:.1%}",
            risk="可能是系统瓶颈",
            hint=f"cluster-symbols --comm {comm}"
        )

    # ... 返回结果 ...
```

### 4.2 集成命令

```bash
# 通过 spear 调用
spear trace init --data <file>
spear trace add --desc <desc> [--hint <hint>]
spear trace complete --id <id> --result <result>
spear trace issues [--status open|resolved|all]
spear trace finalize
```

---

## 5. 使用流程示例

### 5.1 完整诊断流程

```bash
# 1. 初始化
spear trace init --data netstat_perf.data

# 2. 宏观评估，发现问题
spear show-cpu-usage --data netstat_perf.data
# 输出: kernel 51.5% 异常

spear get-comm-top --data netstat_perf.data
# 输出: 4 个高内核态进程

# 3. 记录所有问题
spear trace add --id ISS-001 --desc "netstat 高内核态 94.7%" \
  --risk "进程风暴" --hint "cluster-symbols --comm netstat"
spear trace add --id ISS-002 --desc "containerd-shim 高内核态 89.9%" \
  --risk "单进程影响可能更大" --hint "cluster-symbols --comm containerd-shim"
spear trace add --id ISS-003 --desc "sh 高内核态 86.8%" \
  --risk "未知" --hint "cluster-symbols --comm sh"

# 4. 检查待办
spear trace list
# 输出: 3 pending

# 5. 并行处理问题
spear cluster-symbols --comm netstat --data netstat_perf.data
spear trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"

spear cluster-symbols --comm containerd-shim --data netstat_perf.data
spear trace complete --id ISS-002 --result "LOCK_CONTENTION 79.84%"

# 6. 评估 sh 的重要性
spear trace complete --id ISS-003 --result "wontfix: 优先级低，CPU 占比小"

# 7. 最终审计
spear trace finalize
# 输出: ✅ 所有问题已处理

# 8. 导出报告
spear trace export --format markdown --output diagnosis-report.md
```

---

## 6. 错误处理

### 6.1 常见错误

| 错误 | 原因 | 处理 |
|------|------|------|
| Document not found | 未执行 init | 提示执行 spear trace init |
| Duplicate issue ID | ID 已存在 | 提示使用新的 ID |
| Issue not found | complete 时 ID 不存在 | 提示检查 ID |
| Cannot converge | finalize 时有 pending | 强制要求处理或提供理由 |

### 6.2 错误输出示例

```
ERROR: Document not found

请先初始化诊断文档:
  spear trace init --data <perf-data-file>
```

```
ERROR: Duplicate issue ID 'ISS-001'

该 ID 已存在:
  ISS-001: netstat 高内核态 94.7% (pending)

请使用新的 ID:
  spear trace add --id ISS-004 ...
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

    DEFAULT_PATH = ".spear.json"

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

---

## 9. 参考文档

- [设计意图文档](./design-rationale-trace-v1.md)
- [SKILL.md](../SKILL.md)
- [workflow.md](../references/workflow.md)
