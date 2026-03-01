# Live Document Tracing v2.0 设计文档

> 演进目标：从手动记录到全自动 Tracing 工具
> 版本: 2.0
> 创建时间: 2026-03-02

---

## 1. 设计演进

### 1.1 v1.0 的问题

v1.0 设计需要**人工执行** `perf-doc add` 和 `perf-doc complete`：

```bash
# 发现问题
perf-exp get-comm-top --data xxx.data
# 输出提示: [必须] 添加到 Live Document...

# 必须人工执行！
perf-doc add --id ISS-001 --desc "xxx" --risk "xxx"

# 分析完再人工标记完成
perf-doc complete --id ISS-001 --result "xxx"
```

**问题**：提示容易被忽略，agent 可能忘记执行。

### 1.2 v2.0 核心变化

| 维度 | v1.0 | v2.0 |
|------|------|------|
| 记录方式 | 手动 `add/complete` | **全自动** |
| 数据结构 | issues 列表 | **timeline + issues** |
| 链接关系 | 无 | **双向引用** |
| 使用模式 | 状态跟踪 | **tracing 追溯** |

---

## 2. 新数据结构

### 2.1 核心概念

```
┌─────────────────────────────────────────────────────────────┐
│                      Live Document v2.0                      │
├─────────────────────────────────────────────────────────────┤
│  timeline: [CommandRecord]  ← 按时间顺序记录所有命令执行      │
│  issues: {issue_id: Issue}  ← 问题聚合状态                   │
│  links: 双向引用，timeline 和 issues 互相指向                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 完整 JSON 结构

```json
{
  "version": "2.0",
  "data_file": "netstat_perf.data",
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:05:00Z",
  "timeline": [
    {
      "seq": 1,
      "type": "command",
      "command": "get-comm-top --data netstat_perf.data",
      "timestamp": "2026-03-02T10:00:00Z",
      "findings": [
        {
          "type": "risk_created",
          "level": "warning",
          "desc": "netstat 高内核态 94.7%",
          "issue_id": "ISS-001"
        },
        {
          "type": "risk_created",
          "level": "warning", 
          "desc": "containerd-shim 高内核态 89.9%",
          "issue_id": "ISS-002"
        }
      ]
    },
    {
      "seq": 2,
      "type": "command",
      "command": "cluster-symbols --comm netstat --data netstat_perf.data",
      "timestamp": "2026-03-02T10:01:00Z",
      "findings": [
        {
          "type": "issue_resolved",
          "issue_id": "ISS-001",
          "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
        }
      ]
    }
  ],
  "issues": {
    "ISS-001": {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "level": "warning",
      "status": "resolved",
      "created_at": "2026-03-02T10:00:00Z",
      "created_by_seq": 1,
      "resolved_at": "2026-03-02T10:01:00Z",
      "resolved_by_seq": 2,
      "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
    },
    "ISS-002": {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "level": "warning",
      "status": "open",
      "created_at": "2026-03-02T10:00:00Z",
      "created_by_seq": 1
    }
  }
}
```

### 2.3 字段说明

**timeline[n] - 命令执行记录**

| 字段 | 类型 | 说明 |
|------|------|------|
| seq | int | 全局序号，从1开始 |
| type | string | 固定为 "command" |
| command | string | 完整命令行 |
| timestamp | string | ISO-8601 时间戳 |
| findings | array | 该命令的发现/操作 |

**findings[n] - 发现/操作**

| type | 说明 |
|------|------|
| risk_created | 发现新风险，创建 issue |
| issue_resolved | 分析完成，解决问题 |
| info | 一般信息 |

**issues[id] - 问题聚合**

| 字段 | 说明 |
|------|------|
| id | 唯一标识 |
| desc | 问题描述 |
| level | critical/warning/info |
| status | open/resolved/ignored |
| created_by_seq | 由哪个命令创建 |
| resolved_by_seq | 由哪个命令解决 |

---

## 3. 自动记录机制

### 3.1 OutputBuilder 集成

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
    
    def record_resolution(self, issue_id, result):
        """分析完成时自动标记解决"""
        self.live_doc.resolve_issue(
            issue_id=issue_id,
            result=result,
            command_seq=self.current_seq
        )
    
    def end_command(self):
        """命令结束时保存"""
        self.live_doc.save()
```

### 3.2 使用示例

```python
def cmd_cluster_symbols(engine, args):
    builder = OutputBuilder(engine, args)
    
    # 1. 自动记录命令开始
    builder.begin_command(f"cluster-symbols --comm {args.comm}")
    
    # ... 分析逻辑 ...
    
    # 2. 如果这是针对某个 issue 的分析，自动标记解决
    if hasattr(args, 'resolve_issue'):
        builder.record_resolution(args.resolve_issue, "LOCK_CONTENTION 38.36%")
    
    # 3. 如果又发现新风险，自动创建 issue
    if new_risk_found:
        builder.record_risk("warning", "新发现的问题", "下一步操作...")
    
    # 4. 自动保存
    builder.end_command()
```

### 3.3 风险自动匹配

```python
# 智能匹配：cluster-symbols --comm xxx 自动解析为解决对应 issue
class LiveDoc:
    def match_issue_by_command(self, command, comm):
        """
        根据命令自动匹配可能相关的 issue
        
        例如:
        command: "cluster-symbols --comm netstat"
        自动匹配 desc 包含 "netstat" 的 open issue
        """
        for issue_id, issue in self.issues.items():
            if issue['status'] == 'open' and comm in issue['desc']:
                return issue_id
        return None
```

---

## 4. CLI 接口更新

### 4.1 保留命令

```bash
# 查看 timeline
perf-doc timeline [--format json]

# 查看 issues 状态  
perf-doc issues [--status open|resolved|all]

# 最终审计（检查是否还有 open issue）
perf-doc finalize [--accept-risk <reason>]

# 导出报告
perf-doc export [--format markdown|json]
```

### 4.2 移除命令

```bash
# 不再需要手动操作
perf-doc add      ← 移除，改为自动
perf-doc complete ← 移除，改为自动
```

### 4.3 timeline 输出示例

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
    ✅ ISSUE_RESOLVED: ISS-001 → LOCK_CONTENTION 38.36%

═══════════════════════════════════════════════════════════════════
PENDING ISSUES (1 remaining)
═══════════════════════════════════════════════════════════════════

⚠️  ISS-002  containerd-shim 高内核态 89.9%
    └─ 建议: cluster-symbols --comm containerd-shim

═══════════════════════════════════════════════════════════════════
```

---

## 5. 迁移路径

### 5.1 代码迁移

| 模块 | 变更 |
|------|------|
| `live_doc.py` | 完全重写，支持 v2.0 数据结构 |
| `output_builder.py` | 添加自动记录方法 |
| `analysis/*.py` | 逐步添加 `begin_command` / `record_*` 调用 |

### 5.2 向后兼容

- v1.0 的 `.perf-doc.json` 自动迁移到 v2.0
- v2.0 添加 `version` 字段用于识别

---

## 6. 优势总结

| 优势 | 说明 |
|------|------|
| **零人工干预** | 分析即记录，不会遗漏 |
| **完整追溯** | timeline 展示完整诊断路径 |
| **双向链接** | 知道 issue 从哪来、在哪解决 |
| **聚合视图** | issues 视图展示当前状态 |
| **渐进迁移** | 逐个模块更新，不影响现有功能 |

---

## 7. 参考

- v1.0 设计: `design-rationale-live-doc.md`
- 接口文档: `live-doc-interface.md`
