# SPEAR 典型分析模式

> 按问题形态快速选择分析路径，避免在工具海洋中迷失。

---

## 通用前置步骤（所有模式）

```bash
# 1. 创建诊断文档
mkdir -p debug
# 基于 references/templates.md 创建 debug/[问题描述].md

# 2. 初始化 Trace
spear trace init --data <perf.data>

# 3. 提出三候选假说（强制执行）
# 在诊断文档中记录至少 3 个竞争性假设：
# - 假说 A: 代码维度（如热点函数、算法复杂度）
# - 假说 B: 架构维度（如锁竞争、线程池配置）
# - 假说 C: 环境维度（如资源限制、内核瓶颈）
```

---

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| A1: 热点函数自消耗 | 某函数算法复杂度高 | self 占比 >30% | `get-hotspots --sort-by self` | 热点分散，无集中函数 |
| A2: 锁竞争串行化 | 全局锁导致并行失效 | 单核满载 + 锁函数高 | `find-callers --target <lock>` | 锁来自不同路径，无竞争 |
| A3: 主动休眠过多 | 应用层主动退让 CPU | schedule/nanosleep 高 | `find-callers --target schedule` | 调度来自被动抢占 |

### ⚠️ 常见错误
- `find-callers` 时遗漏 `--pid`，分析全系统数据，得出错误结论
- 过早收敛到单一假说，忽略其他可能性

---

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| C1: 正常扩容 | Workload 增加导致合理扩容 | 请求量与进程数正相关 | `detect-anomalies` 对比时间线 | 进程数与请求量无关 |
| C2: 配置不当 | 进程池过小或超时过短 | 进程创建/销毁频率高 | `count-process-variety` 看 samples_per_pid | 进程生命周期正常 |
| C3: 进程泄漏 | 代码缺陷导致进程未回收 | PID 数持续增长 | 多次执行 `get-comm-top` 对比 | PID 数稳定 |


---

### 内核活动类型速查

| cluster-symbols 类别 | 含义 | 典型根因 | 验证动作 |
|---------------------|------|---------|---------|
| EVENT_SCHEDULER | 调度器活动 | 上下文切换频繁、主动休眠 | `find-callers --target schedule` |
| EVENT_IRQ_OFF | 长临界区 | 内核锁持有时间过长、关中断 | `analyze-core-distribution` 查看 per-CPU |
| EVENT_LOCK_CONTENTION | 锁竞争 | 内核态或用户态锁竞争 | `find-callers --target <lock>` |
| EVENT_MEM_RECLAIM | 内存回收 | 内存压力、频繁分配释放 | 查看具体回收函数分布 |

### ⚠️ 关键检查点

1. **必须区分"用户态驱动" vs "内核态自消耗"**
   - 用户态驱动：业务逻辑大量 syscall（可优化业务代码）
   - 内核态自消耗：内核自身问题（需系统级优化）

2. **多进程高 kernel% 时必须检查是否为系统问题**
   - 使用 heuristics.md 中的"问题边界判定规则"
   - 避免优化单个进程，而忽略系统级根因

---

## 审计检查点（所有模式通用）

### 每 2-3 诊断工具后执行

```bash
spear trace issues
# 如有 PENDING 问题 → 继续分析，不要提前收敛
```

### 生成报告前执行

```bash
spear trace finalize
```

### 全局一致性检查清单

- [ ] **是否解释了所有观测到的异常？**
  - CPU 利用率异常
  - 负载分布异常
  - 时序异常
  - 进程行为异常

- [ ] **三候选假说是否都经过验证？**
  - 假说 A（代码维度）：验证状态 ___
  - 假说 B（架构维度）：验证状态 ___
  - 假说 C（环境维度）：验证状态 ___

- [ ] **是否排除了反向证据？**
  - 主动寻找证伪当前结论的证据
  - 确认没有无法解释的孤证

- [ ] **Trace 中是否还有未处理的 PENDING 问题？**
  - 执行 `trace issues` 确认
  - 执行 `trace finalize` 完成最终审计

---

## 参考文档

- 📗 **核心流程详解**: [workflow-core.md](./workflow-core.md) - 7 Phase 分析流程
- 📘 **工具命令参考**: [tools.md](./tools.md) - 详细命令、参数
- 📕 **启发式规则**: [heuristics.md](./heuristics.md) - 五大认知闭包、问题边界判定
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
