# Trace v1.0 机制设计意图文档

> 记录从问题发现到方案设计的完整思考过程
> 创建时间: 2026-02-28
> 相关案例: netstat/containerd-shim 性能诊断案例

---

## 1. 背景与问题发现 (What Happened)

### 1.1 真实案例回顾

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
cluster-symbols --comm containerd-shim → LOCK_CONTENTION 79.84%
```

containerd-shim 的锁竞争比例是 netstat 的 **2 倍**，但 PID 数只有 9%。

### 1.2 造成的后果

- 诊断结论不完整
- 修复 netstat 后系统仍可能有问题
- 需要二次分析，浪费时间

---

## 2. 问题分析 (Why It Happened)

### 2.1 根本原因：搜索空间不足

诊断过程分析：

```
标准SPEAR流程要求:              实际执行:
  ├─ 并行验证假设                只验证了netstat
  └─ 全局一致性检查              遗漏了containerd-shim
```

**搜索覆盖率**: 1/4 = 25% (严重不足)

### 2.2 具体原因分解

| 原因 | 说明 |
|------|------|
| 人脑记忆有限 | 工具输出后靠人脑记忆，信息必然淹没 |
| 无客观审计 | 没有机制检查"还有哪些没分析" |
| 数字偏见 | 2623 vs 240，被大数字吸引 |
| 缺乏强制收敛检查 | 找到根因后没有机制阻止提前收敛 |

### 2.3 现有 Skill 的不足

**workflow.md** 中的要求：
- "列出 ≥3 条竞争性假设" → 只要求假设数量，不要求验证覆盖
- "延迟收敛" → 原则抽象，无量化指标
- "全局一致性检查" → 依赖人工执行，无强制

**根本问题**: 规则停留在"建议"层面，无强制力。

---

## 3. 设计决策过程 (How We Designed)

### 3.1 第一轮思考：Hints 工具

**想法**: 每个工具输出后给出智能提示

```bash
$ perf-exp get-comm-top --data xxx --hints
# 提示: 发现 4 个高内核态进程，建议都分析
```

**问题**:
- 单个工具看不到全貌
- hints 容易被忽略
- 仍然依赖人脑记忆跨工具关联

### 3.2 第二轮思考：独立 Hints 审计工具

**想法**: 独立的 hints 工具，累积多个工具的数据

```bash
$ perf-exp hints --add --tool get-comm-top --data xxx
$ perf-exp hints --add --tool cluster-symbols --comm netstat --data xxx
$ perf-exp hints --show
```

**优势**:
- 跨工具数据关联
- 可以检测"数据缺口"

**讨论反馈**:
> "需要让 agent 有意愿处理"

于是增加了：
- 进度可视化
- 成就徽章
- 后果强调
- 智能排序

**问题**: 过于复杂，引入奖励机制不必要。

**决策**: 简化，直接展示剩余风险。

### 3.3 第三轮思考：结构化 Trace

**核心洞察**: 需要一个"状态容器"记录诊断全过程。

**设计目标**:
1. **追加问题**: 发现风险时立即记录
2. **完成标记**: 分析完毕后标记状态
3. **强制审计**: 生成报告前必须检查剩余风险
4. **扁平结构**: 对 agent 友好，JSON 不超过 2 层

**关键设计决策**:

| 决策 | 理由 |
|------|------|
| 独立 `spear trace` 工具 | 不改造现有工具，最小侵入 |
| 仅两种状态: pending/completed | 简单明确，无中间状态 |
| 强制 `finalize` 命令 | 必须看到全貌才能输出报告 |
| 文本 + JSON 双输出 | 人类可读，程序可解析 |

---

## 4. 最终方案 (What We Built)

### 4.1 核心机制

```
诊断流程:
  1. spear trace init              # 初始化文档
  2. 分析工具执行                # 发现问题
  3. spear trace add --id ...      # 记录问题
  4. spear trace list              # 查看待办
  5. 继续分析                    # 处理问题
  6. spear trace complete --id ... # 标记完成
  7. spear trace list              # 检查是否还有遗留
  8. spear trace finalize          # 最终审计
  9. 生成报告                    # 结束
```

### 4.2 数据结构（极简扁平）

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

**设计原则**:
- 最多 2 层嵌套
- 字段精简：id, desc, status, result/risk/hint
- 状态明确：pending = 待处理，completed = 已处理

### 4.3 输出格式（人类可读）

```markdown
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

**设计理由**:
- 一眼看出还剩什么
- completed 和 pending 分离
- 风险和建议直接展示

### 4.4 强制审计机制

```bash
$ spear trace finalize
```

输出：
```markdown
═══════════════════════════════════════════════════════════════════
最终全局审计
═══════════════════════════════════════════════════════════════════

⚠️  剩余风险确认
───────────────────────────────────────────────────────────────────
以下问题尚未处理：

ISS-002  containerd-shim 高内核态 89.9%
  - 状态: 完全未分析
  - 风险: 锁竞争可能 >50%，单进程影响大于 netstat

═══════════════════════════════════════════════════════════════════
强制选择
═══════════════════════════════════════════════════════════════════

[A] 继续分析剩余问题（推荐）
[B] 接受风险，生成报告（必须提供理由）
[C] 标记为无需处理（必须提供证据）

选择 [A/B/C]:
```

**关键点**:
- 不选择不能退出
- 选择 B/C 必须提供理由
- 有明确的"推荐"选项

---

## 5. 与现有 Skill 的整合

### 5.1 双 Table 机制演进

传统方式：
- Table 1 (问题演进): 手工维护 markdown
- Table 2 (假设验证): 手工维护 markdown

新方式：
- Table 1 → Trace 的 `issues` 列表 (自动维护)
- Table 2 → 每个 issue 的 `desc`, `result`, `risk` 字段

**优势**: 从"手工维护"变为"工具自动维护"

### 5.2 SKILL.md 更新要点

```markdown
## 诊断文档规范（⚠️ 强制执行）

### Trace 机制

所有分析必须写入结构化诊断文档，作为唯一事实来源。

### 强制审计规则

**⚠️ 非常重要**: 每次执行 2-3 个工具后，必须运行审计。

```bash
spear trace list
```

**不审计的后果**:
- 不知道哪些关键问题未处理
- 可能遗漏同样严重的其他问题
- 诊断覆盖率不足，结论不可信

### 禁止行为

- ❌ 未执行 `spear trace list` 直接给出结论
- ❌ `pending` 列表不为空时生成最终报告
- ❌ 未执行 `spear trace finalize` 结束诊断
```

---

## 6. 预期效果

### 6.1 对 netstat/containerd-shim 案例的重演

```bash
# Step 1: 发现问题
$ perf-exp get-comm-top --data netstat_perf.data
# 输出显示 4 个高内核态进程

# Step 2: 立即记录所有问题
$ spear trace add --id ISS-001 --desc "netstat 高内核态 94.7%" --risk "进程风暴" --hint "cluster-symbols --comm netstat"
$ spear trace add --id ISS-002 --desc "containerd-shim 高内核态 89.9%" --risk "可能比 netstat 更严重" --hint "cluster-symbols --comm containerd-shim"
$ spear trace add --id ISS-003 --desc "sh 高内核态 86.8%" --risk "未知" --hint "cluster-symbols --comm sh"

# Step 3: 查看待办
$ spear trace list
输出:
  ⚠️  PENDING: ISS-001, ISS-002, ISS-003

# Step 4: 分析 netstat
$ perf-exp cluster-symbols --comm netstat
$ spear trace complete --id ISS-001 --result "LOCK_CONTENTION 38.36%"

# Step 5: 再次检查
$ spear trace list
输出:
  ✅ COMPLETED: ISS-001
  ⚠️  PENDING: ISS-002, ISS-003  ← 明确提示还有遗留

# Step 6: 被迫分析 containerd-shim
$ perf-exp cluster-symbols --comm containerd-shim
$ spear trace complete --id ISS-002 --result "LOCK_CONTENTION 79.84%"

# Step 7: 最终审计
$ spear trace finalize
输出:
  剩余风险: ISS-003 sh (可选择接受或继续)
  选择: [A]继续 [B]接受 [C]标记为无需处理
```

**结果**: containerd-shim 在 Step 5 就被明确提示，不会遗漏。

---

## 7. 讨论细节记录

### 7.1 为什么不要奖励机制？

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

### 7.2 为什么扁平结构？

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

### 7.3 为什么只有两种状态？

**讨论**:
> 是否需要 in_progress / verified / wontfix 等状态？

**决策**:
- 只有 `pending` / `completed`
- 简化认知负担
- 其他信息放在 `result` 字符串中

### 7.4 finalize 的必要性

**讨论**:
> 如何强制 agent 看到全貌？

**方案**:
- 单独的 `finalize` 命令
- 输出剩余风险清单
- 必须选择才能退出

**理由**:
- `list` 可以被忽略
- `finalize` 是显式的"结束仪式"
- 有明确的决策点

---

## 8. 参考文档

- [Trace 接口设计文档](./trace-interface.md)
- [原始案例讨论](../CHANGES.md#v2.8)
- [netstat 诊断案例参考](../../just_empty_dir/netstat/debug/)
