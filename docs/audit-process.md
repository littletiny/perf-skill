# SPEAR Trace 审计流程

> 项目审计员指南：独立验证 issues 分析质量
> 版本: 2.1
> 创建时间: 2026-03-02

---

## 1. 核心理念：完全独立的两个流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        完全独立的两个流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  流程 A: 诊断流程                   流程 B: 审计流程                │
│  (诊断工程师)                       (独立审计员)                    │
│  ─────────────────                  ─────────────────             │
│                                                                  │
│  1. 发现问题 → 创建 issue           1. 诊断工程师完成诊断            │
│  2. 分析问题 → 标记 complete            ↓                         │
│  3. 所有 issues resolved            2. 审计员运行 audit            │
│  4. finalize 结束诊断                   ↓                         │
│                                         3. 生成审计报告            │
│                                         4. 反馈给团队              │
│                                                                  │
│  ═══════════════════════════════════════════════════════════     │
│  两个流程完全独立：                                                │
│  - 诊断工程师完成诊断后才进行 audit                                │
│  - audit 不 block finalize                                        │
│  - audit 是事后质量检查，不是诊断流程的一部分                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**关键原则**：
- 诊断工程师 **独立完成诊断**，包括 finalize
- 审计是 **事后独立流程**，由独立人员执行（Tech Lead / Reviewer / QA / 架构师）
- Audit **不依赖** finalize，finalize **不依赖** audit
- Audit 结果用于 **质量改进** 和 **团队学习**，不是诊断完成的必要条件

---

## 2. 流程 A：诊断流程（工程师独立完成）

### 2.1 完整流程

```bash
# 1. 初始化诊断文档
spear trace init --data perf.data

# 2. 执行分析，自动/手动记录 issues
spear get-comm-top
spear cluster-symbols --comm netstat
...

# 3. 查看待处理 issues
spear trace issues

# 4. 完成分析，标记 resolved（必须提供详细 result）
spear trace complete --id ISS-001 --result "根因: netstat(2633/min)进程风暴 - 详见 debug/analysis.md"

# 5. 确认所有 issues 已解决
spear trace issues --status open

# 6. finalize 结束诊断（完全独立，不依赖 audit）
spear trace finalize

# 7. 导出报告
spear trace export --format markdown --output report.md
```

### 2.2 诊断工程师职责

- 记录所有发现的问题
- 对每个 issue 进行充分分析
- 在 result 中提供因果推导过程
- 引用详细的诊断文档 (`debug/*.md`)
- **独立完成诊断并 finalize**，不等待 audit

---

## 3. 流程 B：审计流程（独立事后检查）

### 3.1 触发时机（诊断完成后）

| 场景 | 执行者 | 说明 |
|------|--------|------|
| 定期质量审计 | QA/架构师 | 每周/每月抽查已完成的诊断 |
| Code Review | Tech Lead | 审查 PR 时检查诊断质量 |
| 问题复盘 | 故障处理团队 | 事后分析历史诊断的充分性 |
| 新人培训 | 导师 | 检查新人诊断是否符合规范 |

### 3.2 审计流程

```bash
# 1. 获取诊断文档（已完成 finalize 的）
cd /path/to/completed/diagnosis

# 2. 运行审计
spear trace audit

# 3. 查看详细报告（JSON 格式便于处理）
spear trace audit --format json --output audit-report.json

# 4. 生成审计反馈
# 审计员根据结果给团队反馈
```

### 3.3 审计结果使用

**Audit 通过**：
- 标记为高质量诊断
- 可作为团队最佳实践案例

**Audit 发现问题**：
- 记录问题类型（敷衍 result / 分析不足 / 缺少文档）
- 反馈给诊断工程师（用于学习改进）
- **不需要 reopen**（因为是事后检查）
- 在团队内分享，避免类似问题

---

## 4. 审计 Checklist

### Phase 1: 结构完整性检查

```bash
# 获取所有 resolved issues
spear trace issues --status resolved

# 获取完整 timeline
spear trace timeline
```

**检查项**：

- [ ] 每个 resolved issue 都有非空的 `result`
- [ ] `result` 不是敷衍的标记（如 "ok", "fixed", "done"）
- [ ] `resolved_at` 时间晚于 issue `created_at`

**不合格示例**：
```json
{
  "id": "ISS-001",
  "status": "resolved",
  "result": "done"  // ❌ 敷衍，无实质内容
}
```

**合格示例**：
```json
{
  "id": "ISS-001",
  "status": "resolved",
  "result": "根因: netstat(2633/min)进程风暴导致内核态CPU飙升 - 详见 debug/mysql_performance_regression_analysis.md"
}
```

---

### Phase 2: Timeline 关联检查

**核心原则**：result 应该有 timeline 中的分析命令支撑

**检查项**：

- [ ] 每个 resolved issue 在 created_by_seq 之后有分析命令
- [ ] `result` 内容与 timeline 中的分析结果一致
- [ ] 无 analysis gap（创建 issue 后立即标记完成，无分析命令）

**风险信号**：

| 信号 | 含义 |
|------|------|
| `resolved_by_seq == null` | 手动标记完成，无关联命令 |
| `created_at` 与 `resolved_at` 间隔 < 30秒 | 分析时间过短 |
| timeline 中无相关 analysis commands | result 无数据支撑 |

---

### Phase 3: 分析深度检查

#### 3.1 三候选准则验证

**检查 result 是否体现多假设竞争**：

**不合格示例**：
```
Result: "锁竞争导致性能下降"
```

**合格示例**：
```
Result: "根因为锁竞争（排除算法复杂度、排除CPU限制）- 详见 debug/analysis.md 假设追踪表"
```

#### 3.2 驱动力分析验证

检查 result 是否明确问题驱动力：

- [ ] 请求流量驱动（Workload 增加）
- [ ] 系统资源驱动（内核瓶颈、资源争抢）
- [ ] 内部机制驱动（GC、定时任务、缓存刷新）

#### 3.3 溯源深度验证

对于热点函数类 issues：

- [ ] 是否使用 `find-callers` 溯源到调用链
- [ ] 是否定位到具体代码路径
- [ ] 是否建立负载语义（业务含义）

---

### Phase 4: 文档一致性检查

```bash
# 检查 debug/*.md 文件是否存在
ls debug/*.md

# 检查文档是否包含必要章节
grep -E "^## (假设|证据|结论|根因)" debug/*.md
```

**检查项**：

- [ ] `result` 中包含 `debug/*.md` 引用
- [ ] 引用的文档存在且内容完整
- [ ] 文档中包含假设追踪表

---

## 5. 审计命令

### 5.1 运行审计

```bash
# 完整审计（所有阶段）
spear trace audit

# 只检查结构完整性
spear trace audit --phase structural

# 只检查 timeline 关联
spear trace audit --phase timeline

# 只检查分析深度
spear trace audit --phase depth

# JSON 输出（便于集成到质量平台）
spear trace audit --format json --output audit-report.json
```

### 5.2 审计输出

**文本格式**：
```
=================================================================
AUDIT REPORT
=================================================================
Audit Time: 2026-03-02T14:30:00Z
Auditor: [name]

SUMMARY
-----------------------------------------------------------------
Total Issues: 8
  ✅ Passed:   6
  ⚠️  Warnings: 1
  ❌ Failed:   1
Pass Rate: 75.0%

FAILED ISSUES (质量不符合规范)
-----------------------------------------------------------------
[FAIL] ISS-003: sh 高内核态 86.8%
  └─ Perfunctory result: 'fixed'
  └─ 期望: 详细因果分析，引用诊断文档
  → 建议: 反馈给工程师，后续改进

WARNINGS (建议改进)
-----------------------------------------------------------------
[WARN] ISS-002: containerd-shim 高内核态 89.9%
  └─ Analysis time suspicious: 15.2s
  └─ 建议: 复核分析充分性

=================================================================
AUDIT COMPLETED - See report above
=================================================================
```

**JSON 格式**：
```json
{
  "audit_time": "2026-03-02T14:30:00Z",
  "auditor": "reviewer_name",
  "summary": {
    "total_issues": 8,
    "passed": 6,
    "failed": 1,
    "warnings": 1
  },
  "issues": [
    {
      "id": "ISS-003",
      "status": "failed",
      "checks": {
        "has_result": true,
        "substantive_result": false
      },
      "failures": ["Perfunctory result: 'fixed'"]
    }
  ]
}
```

---

## 6. 审计结果处理（非阻塞）

### 6.1 与诊断流程的关系

```
诊断流程 ────────► 诊断完成
                      │
                      ▼
               ┌─────────────┐
               │  finalize   │ ◄── 诊断结束，生成报告
               └─────────────┘
                      │
                      │ 事后审计（可选）
                      ▼
               ┌─────────────┐
               │   audit     │ ◄── 独立审计员事后检查
               └─────────────┘
                      │
              ┌──────┴──────┐
              ▼             ▼
        质量反馈      团队学习
```

### 6.2 审计发现问题处理（非阻塞）

**不 reopen**：因为是事后检查，诊断已经完成

**处理方式**：
1. **记录问题**：在审计报告中记录
2. **反馈给工程师**：一对一沟通，帮助改进
3. **团队分享**：在周会/技术分享中讨论
4. **更新规范**：如果多人犯同样错误，更新诊断规范

---

## 7. 质量度量

### 7.1 诊断质量指标

| 指标 | 计算方式 | 目标值 |
|------|---------|--------|
| 分析覆盖率 | resolved issues / total issues | > 90% |
| 平均分析时间 | avg(resolved_at - created_at) | > 5min |
| Timeline 支撑率 | issues with timeline support / resolved | 100% |
| 文档引用率 | issues with doc ref / resolved | 100% |

### 7.2 审计质量指标

| 指标 | 计算方式 | 目标值 |
|------|---------|--------|
| 审计通过率 | 通过 audit / 总审计数 | > 80% |
| 敷衍 result 率 | 敷衍 result / 总 result | < 5% |
| 文档缺失率 | 无 doc ref / 有 doc ref | < 10% |

---

## 8. 审计报告模板

```markdown
# 审计报告: [诊断名称]

**诊断信息**:
- 诊断工程师: [name]
- 诊断时间: 2026-03-01
- 审计时间: 2026-03-02T14:30:00Z
- 审计员: [name]
- 诊断文档: [path/.spear.json]

## 摘要
- 总 Issues: N
- 已解决: N
- 审计通过: N (通过率: X%)
- 需改进: N

## 问题详情

### ISS-003: sh 高内核态 86.8%
- **问题类型**: Failed
- **具体问题**: Result 敷衍（'fixed'），无实质分析
- **影响**: 无法追溯分析过程，不利于知识传承
- **建议**: 反馈给工程师，后续诊断注意

## 团队反馈建议
- [可改进的点]
- [值得推广的最佳实践]

---
**注**: 本审计为事后质量检查，不修改已完成的诊断
```

---

## 9. 与 finalize 的关系（完全独立）

### 9.1 职责分离

| 命令 | 执行者 | 执行时机 | 目的 |
|------|--------|---------|------|
| `audit` | 独立审计员 | 诊断完成后（事后） | **质量检查** |
| `finalize` | 诊断工程师 | 诊断结束时 | **状态确认** |

### 9.2 无依赖关系

```bash
# 场景 1: 只有诊断，无审计
spear trace complete --id ISS-001 --result "..."
spear trace finalize
# 诊断完成，结束

# 场景 2: 诊断 + 事后审计
spear trace complete --id ISS-001 --result "..."
spear trace finalize
# ... 过了一段时间 ...
spear trace audit  # 审计员独立执行

# 场景 3: 只有审计（检查历史诊断）
# 拿到历史诊断文档
spear trace audit
```

### 9.3 关键区别

| 特性 | audit | finalize |
|------|-------|----------|
| 执行者 | 独立审计员 | 诊断工程师 |
| 执行时机 | 事后（诊断完成后） | 诊断结束时 |
| 是否阻塞 | 不阻塞任何流程 | 如有 open issues 会提示 |
| 目的 | 质量检查和学习 | 确认诊断结束 |
| 失败处理 | 记录反馈 | reopen 或接受风险 |

---

## 10. 参考

- [Trace v2.0 设计文档](./design-rationale-trace-v2.md)
- [Trace 接口文档](./trace-interface.md)
- [SKILL.md](../SKILL.md) - 诊断流程指南
- [templates.md](../references/templates.md) - 诊断报告模板
