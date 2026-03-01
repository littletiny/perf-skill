# SPEAR 典型分析模式

> 按问题形态快速选择分析路径，避免在工具海洋中迷失。

---

## 模式选择决策树

```
                    开始分析
                      │
                      ▼
              ┌───────────────┐
              │  show-cpu-usage │
              │  get-comm-top   │
              └───────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   kernel% > 50%   单进程 CPU     多进程同类
        │         异常高          高消耗
        │             │             │
        ▼             ▼             ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│   模式 E     │ │  模式 A  │ │   模式 C     │
│ 高内核态分析  │ │ 单进程热点│ │  进程风暴    │
└──────────────┘ └──────────┘ └──────────────┘
        │             │             │
        │             ▼             │
        │      ┌──────────┐         │
        │      │负载不均衡？│         │
        │      │(单核满载) │         │
        │      └──────────┘         │
        │             │             │
        │        是 ──┘             │
        │             │             │
        │             ▼             │
        │      ┌──────────┐         │
        └──────│  模式 D  │─────────┘
               │ 负载不均衡│
               └──────────┘
                      │
                      ▼
               ┌──────────┐
               │  模式 B  │
               │ 系统整体 │
               │ 缓慢分析 │
               └──────────┘
```

---

## 通用前置步骤（所有模式）

```bash
# 1. 创建诊断文档
mkdir -p debug
# 基于 references/templates.md 创建 debug/[问题描述].md

# 2. 初始化 Live Document
spearert.py doc init --data <perf.data>

# 3. 提出三候选假说（强制执行）
# 在诊断文档中记录至少 3 个竞争性假设：
# - 假说 A: 代码维度（如热点函数、算法复杂度）
# - 假说 B: 架构维度（如锁竞争、线程池配置）
# - 假说 C: 环境维度（如资源限制、内核瓶颈）
```

---

## 模式 A: 单进程 CPU 高

### 场景特征
用户明确反馈"某个 PID 的 CPU 上不去/异常高"

### 驱动力分析
- **请求流量驱动**: Workload 增加导致正常消耗上升
- **内部机制驱动**: GC、定时任务、缓存刷新等内生行为
- **资源争抢驱动**: 与其他进程竞争 CPU，但本模式假设目标进程是主要消耗者

### 分析路径

```bash
# Step 1: 宏观确认（所有命令必须携带 --pid）
show-cpu-usage --pid <PID>
analyze-core-distribution --pid <PID>

# Step 2: 根据负载分布特征决策
#   - sleeping 多 → 主动休眠问题 → 溯源调度函数
#   - active 多 + 单核满载 → 锁竞争问题 → 分析锁粒度
#   - 均衡分布 → 计算密集型 → 热点函数优化

# Step 3: 热点识别与溯源
get-hotspots --pid <PID> --sort-by self
find-callers --auto-target --pid <PID>  # ❌ 不要遗漏 --pid

# Step 4: 语义聚类
cluster-symbols --pid <PID>
```

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

## 模式 B: 系统整体缓慢

### 场景特征
- "整个系统都很慢"
- "所有服务都受影响"
- 无明显单一高耗进程

### 驱动力分析
- **系统资源驱动**: 内核瓶颈、全局锁、中断风暴
- **基础设施驱动**: 存储、网络、容器运行时等底层组件
- **级联效应驱动**: 单点问题扩散影响全系统

### 分析路径

```bash
# Step 1: 系统级概览（不加 --pid，保持全局视图）
check-cpu-bottleneck
show-cpu-usage
get-comm-top  # 关注是否存在"大量小进程集体消耗"

# Step 2: 异常定位
detect-anomalies  # 定位时间窗口

# Step 3: 系统级热点分析
get-hotspots --sort-by self  # 不加 --pid
cluster-symbols  # 关注 EVENT_SCHEDULER, EVENT_IRQ_OFF

# Step 4: 问题边界判定
# - 多进程共同症状 + 共享依赖路径 → 系统问题
# - 单进程独有症状 → 单体问题（转入模式 A）
```

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| B1: 内核全局锁竞争 | 多进程竞争同一把内核锁 | 多进程 kernel% 均高，同一把锁热点 | `cluster-symbols` (LOCK_CONTENTION) + `find-callers` | 各进程锁路径不同 |
| B2: 调度器过载 | 进程/线程数过多，调度开销剧增 | schedule 函数高，上下文切换频繁 | `cluster-symbols` (EVENT_SCHEDULER) | 进程数正常，schedule 来自休眠 |
| B3: 中断/软中断风暴 | 硬件中断或网络包过多 | IRQ/软中断 CPU 高 | `analyze-core-distribution` 查看 per-CPU 中断分布 | 中断分布均匀，无集中 |

### 关键判定规则

**系统问题 vs 单体问题**（来自 heuristics.md）：

```
IF (多个进程表现出相似症状) AND (共享共同依赖路径):
    → 系统问题（基础设施/平台层）
ELSE IF (症状局限于单个进程) OR (无共同依赖路径):
    → 单体问题（应用层）
```

---

## 模式 C: 进程风暴

### 场景特征
- 大量短生命周期进程频繁创建/销毁
- 类似进程名数量激增
- 聚合 CPU 高但单进程消耗低

### 驱动力分析
- **Workload 激增驱动**: 请求量突增导致进程池扩容
- **配置异常驱动**: 进程池配置不当，频繁创建销毁
- **代码缺陷驱动**: 进程泄漏，未正确回收

### 分析路径

```bash
# Step 1: 行为检测
count-process-variety
get-comm-top  # 关注 cpu消耗总量，尤其是内核态cpu占用

# Step 2: 如果检测到lsof高内核开销
# 在 Live Document 中记录高内核开销
spearert.py doc add \
  --desc "lsof 内核开销高" \
  --risk "系统开销激增" \
  --hint "cluster-symbols --comm lsof"

# Step 3: 逐个分析风暴进程（对 pending_targets 循环执行）
cluster-symbols --comm <storm-comm>
get-hotspots --comm <storm-comm>
find-callers --auto-target --comm <storm-comm>

# Step 4: 定期审计
spearert.py doc list  # 确保所有风暴进程组都被分析
```

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| C1: 正常扩容 | Workload 增加导致合理扩容 | 请求量与进程数正相关 | `detect-anomalies` 对比时间线 | 进程数与请求量无关 |
| C2: 配置不当 | 进程池过小或超时过短 | 进程创建/销毁频率高 | `count-process-variety` 看 samples_per_pid | 进程生命周期正常 |
| C3: 进程泄漏 | 代码缺陷导致进程未回收 | PID 数持续增长 | 多次执行 `get-comm-top` 对比 | PID 数稳定 |

### ⚠️ 强制要求
- `count-process-variety` 检测到风暴后，**必须**在 Live Document 中记录所有风暴进程组
- **必须**对每个风暴进程组执行 `cluster-symbols`，不得遗漏

---

## 模式 D: 负载不均衡

### 场景特征
- `analyze-core-distribution` 显示 `imbalance_level=HIGH/CRITICAL`
- 多核分布但单核满载，其他核心空闲

### 驱动力分析
- **不能并行**: 代码串行化（全局锁、单线程设计）
- **不想并行**: 应用层主动退让（sleep、yield、epoll_wait）
- **被迫串行**: 数据依赖导致只能顺序执行

### 分析路径

```bash
# Step 1: 确认不均衡程度
analyze-core-distribution --pid <PID>

# Step 2: 区分"不能并行" vs "不想并行"
# 查看 analyze-core-distribution 输出：
#   - sleeping 多 → 不想并行（主动休眠）
#   - active 多 → 不能并行（锁竞争或设计缺陷）

# Step 3: 根据 patterns 建议行动
# SINGLE_CORE_SATURATION → 检查调度/锁
cluster-symbols --pid <PID>  # 看 SCHEDULING/LOCK 占比

# Step 4: 溯源（必须带 --pid）
# 如果是 SCHEDULING 高：
find-callers --target schedule --pid <PID>
# 如果是 LOCK_CONTENTION：
find-callers --target <lock_func> --pid <PID>

# Step 5: 判定根本原因
# - 调用路径中有业务逻辑 → 主动休眠（不想并行）
# - 调用路径只有内核/锁 → 被动压制（不能并行）
```

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| D1: 全局锁竞争 | 全局锁导致串行化 | 单核满载 + 锁函数高 | `find-callers --target <lock>` | 锁来自不同调用路径 |
| D2: 应用层主动休眠 | 代码主动退让 CPU | schedule/nanosleep 高，调用链含业务逻辑 | `find-callers --target schedule` | 调度来自被动抢占 |
| D3: 数据依赖串行 | 计算必须顺序执行 | 无锁/无调度，但单核满载 | `get-hotspots --sort-by self` | 热点分散 |

### ⚠️ 常见错误
- `find-callers` 时不带 `--pid`，得到的是全系统的 `futex_wait` 等调度函数调用，而非目标进程的行为

---

## 模式 E: 高内核态分析

### 场景特征
- `show-cpu-usage` 显示 kernel% > 50%
- `get-comm-top` 显示某进程组 kernel_pct > 80%
- 系统整体响应慢但无明显用户态热点

### 驱动力分析
- **系统调用频繁驱动**: 业务逻辑大量 syscall（IO、锁、计时器）
- **内核瓶颈驱动**: 内核锁竞争、调度延迟、中断处理
- **基础设施驱动**: 容器运行时、监控 agent、安全模块等系统组件

### 分析路径

```bash
# Step 1: 确认影响范围
get-comm-top                  # 识别高 kernel 的进程组
check-cpu-bottleneck          # 检查是否为系统级问题

# Step 2: 语义聚类定位内核活动类型
cluster-symbols --comm <xxx>  # 关键：识别内核活动类型
# 预期输出类别：
#   - EVENT_SCHEDULER: 调度压力大（上下文切换频繁）
#   - EVENT_IRQ_OFF: 长临界区/中断关闭
#   - EVENT_LOCK_CONTENTION: 内核锁竞争
#   - EVENT_MEM_RECLAIM: 内存回收压力

# Step 3: 根据聚类结果选择溯源目标
# CASE 1: SCHEDULER 高
find-callers --target schedule --comm <xxx>
#   └─ 调用路径中有业务逻辑 → 主动休眠过多
#   └─ 调用路径只有内核 → 调度器压制

# CASE 2: LOCK_CONTENTION 高
find-callers --target <具体锁函数> --comm <xxx>
#   └─ 确认是用户态锁还是内核态锁

# CASE 3: IRQ_OFF 高
analyze-core-distribution --comm <xxx>
#   └─ 检查是否存在特定 CPU 的长临界区

# CASE 4: MEM_RECLAIM 高
cluster-symbols --comm <xxx>  # 看具体回收函数
#   └─ 识别是正常回收还是内存压力

# Step 4: 问题边界判定（系统级 vs 应用级）
# - 多进程共同受影响 + 共享内核路径 → 系统问题
# - 单进程独有 + 进程私有代码路径 → 应用问题
```

### 三候选假说示例

| 假说 | 机制 | 预期指纹 | 验证工具 | 证伪条件 |
|------|------|---------|---------|---------|
| E1: 内核锁竞争 | 多进程竞争内核全局锁（如 inode、socket 锁） | 多进程 kernel% 均高，同一内核锁热点 | `cluster-symbols` (LOCK_CONTENTION) + `find-callers` | 各进程锁路径不同 |
| E2: 调度器活动频繁 | 进程/线程状态切换频繁 | schedule 函数高， sleeping 状态多 | `cluster-symbols` (EVENT_SCHEDULER) | schedule 来自少量进程 |
| E3: 系统调用风暴 | 业务逻辑大量 syscall（如频繁 IO、定时器） | syscall 入口函数高 | `find-callers --target __x64_sys_*` | syscall 数量与业务逻辑匹配 |

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

## 模式间转换规则

```
模式 A (单进程) ──发现多进程类似症状──→ 模式 B (系统级)
     │                                          │
     │                                          │
     └──发现 PID 激增──────────────────────→ 模式 C (进程风暴)
     │
     └──发现单核满载───────────────────────→ 模式 D (负载不均衡)
     │
     └──发现 kernel% 高────────────────────→ 模式 E (高内核态)

模式 B (系统级) ──定位到具体进程──────────→ 模式 A (单进程)
```

---

## 审计检查点（所有模式通用）

### 每 2-3 诊断工具后执行

```bash
spearert.py doc list
# 如有 PENDING 问题 → 继续分析，不要提前收敛
```

### 生成报告前执行

```bash
spearert.py doc finalize
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

- [ ] **Live Document 中是否还有未处理的 PENDING 问题？**
  - 执行 `doc list` 确认
  - 执行 `doc finalize` 完成最终审计

---

## 参考文档

- 📗 **核心流程详解**: [workflow-core.md](./workflow-core.md) - 7 Phase 分析流程
- 📘 **工具命令参考**: [tools.md](./tools.md) - 详细命令、参数
- 📕 **启发式规则**: [heuristics.md](./heuristics.md) - 五大认知闭包、问题边界判定
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
