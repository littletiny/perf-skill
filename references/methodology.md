# SHECR 性能分析方法论

```
                         S.H.E.C.R 方法论
  S → Systematic     topdown-bottomup结合：系统级→时间级→实体级→函数级→模式级
  H → Hypothesis     假设驱动：根据符号语义和风险点构建搜索空间
  E → Evidence       证据驱动：基于工具输出数据验证，拒绝主观臆断
  C → Controlled     受控收敛：<X0>标记必须追踪到根因，禁止过早下结论
  R → Reasoning      逻辑推理：因果追踪，识别第一推动力
```

---

## 1. 分析入口决策树

SHECR 分析入口：从症状到工具的直达路径：

```
symptom                          → 推荐入口命令
─────────────────────────────────────────────────────────
不知道从何入手                    → sys-audit
单进程/进程组 CPU 异常             → bottleneck-trace --comm <name> --pid <pid>
突发性能下降/异常窗口              → detect-anomalies
已知热点函数，需调用链             → find-callers --target <func>
```

### 1.1 综合诊断入口

不知道从何入手？两个都来一轮：

```bash
# 第一轮：系统全景扫描
shecr sys-audit

# 第二轮：深度追踪瓶颈进程（根据第一轮输出选择）
shecr bottleneck-trace --comm <瓶颈进程名>
```

---

## 2. 核心指标解读

### 2.1 Entity 层指标（get-comm-top）

| 指标 | 含义 | 阈值 | 诊断意义 |
|------|------|------|---------|
| **CV** (变异系数) | 组内 PID 负载离散程度 | >1.0 异常 | 识别离群进程，组内负载不均 |
| **Monopoly** | 核心独占率 | >0.8 高危 | 单点瓶颈，可能引发调度延迟 |
| **Impact Score** | 危害指数 | 降序排列 | 综合评估，高分优先关注 |

### 2.2 System 层指标（analyze-core-distribution）

| 指标 | 含义 | 阈值 | 诊断意义 |
|------|------|------|---------|
| **imbalance_level** | 核心负载不均衡等级 | HIGH/CRITICAL | 需要分析负载分布原因 |
| **saturated_cores** | 饱和核心列表 | 非空 | 单核瓶颈，可能锁竞争或串行化 |

### 2.3 Pattern 层指标（detect-anomalies）

| 类型 | 含义 | 下一步动作 |
|------|------|-----------|
| **SPIKE** | 利用率突增 | 提取窗口，分析触发源 |
| **DROP** | 利用率突降 | 检查资源压制或外部依赖 |
| **LEVEL_SHIFT** | 水平迁移 | 检查配置变更或负载变化 |
| **BURST** | 短时爆发 | 检查定时任务或突发流量 |

---

## 3.

```
  Composite（全景图+自动诊断）:
   sys-audit         系统全景扫描，输出诊断摘要和建议
   bottleneck-trace  多维度聚合分析，定位 CPU 瓶颈根因
                       （输出: ENTITY_DISTRIBUTION_MATRIX,
                        CONVERGENCE_TRACE, CORRELATION_FLAGS）

  Analysis（分析层，针对特定场景具体分析）
   detect-anomalies       时间级异常检测
   analyze-core-distribution  系统级核心分布
   get-comm-top           实体级进程组分析
   get-hotspots           函数级热点识别
   find-callers           关系级调用溯源
   cluster-paths          模式级路径聚类
```

**使用原则**：
- 不确定从何入手 → 从 Composite 层开始
- 有明确目标 → 直接使用 Analysis 层工具

---

## 4. 典型陷阱与对策

### 4.1 陷阱：A（亮眼数字）掩盖 B（真瓶颈）

**表现**：
```
进程组          CPU%    Count    直观印象
─────────────────────────────────────────
lsof            400%    2000     ← 亮眼！
app_worker      12%     10       ← 平庸...
```

**真相**：`app_worker` Monopoly=0.92，独占 Core #7 导致系统卡顿；`lsof` 虽然总数高但分布均匀，是背景噪音。

**对策**：
- 使用 `sys-audit`（自动降噪 + Impact Score 排序）
- 关注 `Monopoly` 和 `CV`，而非单纯 CPU%
- 检查 `diagnosis` 标签：BOTTLENECK > UNBALANCED > STORM > HEALTHY

### 4.2 陷阱：参数遗漏

**表现**：`find-callers --target schedule` 未加 `--pid`，分析全系统数据。

**后果**：看到的是全系统的调度行为，而非目标进程的行为，得出错误结论。

**对策**：
- 分析前确认目标范围：系统级？进程级？时间窗口？
- 使用一致性检查清单（见附录 C）

### 4.3 陷阱：过早收敛

**表现**：看到一条证据立即下结论。

**对策**：
- 对每个工具提示的<X0>高风险issues都跟踪到底，彻底分析可能风险
- 每 2-3 个工具后执行 `shecr trace issues` 检查待办问题
- 生成报告前执行 `shecr trace finalize` 确认完整性

### 4.4 陷阱：忽视样本可靠性

**表现**：CPU < 3% 或样本 < 10 时仍做精确分析。

**对策**：

| 等级 | 条件 | 建议 |
|-----|------|------|
| CRITICAL | CPU<3% 或 样本<10 | 不可信，延长采样时间 |
| WARNING | CPU<10% 且 样本<30 | 关注趋势而非精确值 |
| ACCEPTABLE | CPU 10-30% 且 样本<100 | 可用于粗略分析 |
| GOOD | CPU 30-60% 且 样本≥100 | 结论可信 |
| EXCELLENT | CPU≥60% 且 样本≥200 | 高度可信 |

### 陷阱：强制单根因

**表现**：发现单一资源竞争就停止分析，忽略同时存在的配置问题或其他资源瓶颈。将复杂问题强行归因于单一因素。

**认知本质**：这是对问题复杂性的过度简化，忽视系统性能往往是多因素叠加的结果。

**对策**：

- 允许多因素叠加的结论形式
- 区分**主因**（解决后收益最大）和**辅因**（恶化主因或独立存在）
- 在诊断文档中明确记录："主因是 X，同时存在 Y 和 Z 的次要影响"

---

## 5. Hypothesis

**原则**：推测符号语义，推测领域知识，根据风险点构建假设空间，进行根因分析

### 5.1 文档格式

在诊断文档中记录：
```yaml
假说 ID: HYP-001
名称: 串行化瓶颈
机制: 同步机制导致并行失效，CPU 无法扩展
预期指纹:
  - monopoly: ">0.8"
  - imbalance_level: "HIGH"
验证方法: "analyze-core-distribution --comm <name>"
证伪条件: "负载均匀分布，各核心利用率差异小"
```

### 5.2 驱动力分析

识别性能问题的第一推动力，帮助选择验证优先级：
- **系统资源驱动**: 内核瓶颈、资源争抢 → 系统级优化
- **内部机制驱动**: GC、定时任务、缓存刷新 → 应用内部调优

---

## 6. 待验证假设（需外部信息）

无法判断问题是，需要询问更多信息
| 假设 | 需确认信息 | 何时询问 |
|------|-----------|---------|
| **突发限流** | Cgroup CPU burst 配置、throttle 次数 | 业务延迟异常但无明确热点时 |
| **负载变化** | 近期流量/数据量/并发数变化 | `detect-anomalies` 发现突变点时 |
| **链路抖动** | 下游服务延迟变化、网络状况 | 等待类函数高但本地无瓶颈时 |

---

## 7. 关键信号检查清单

| 信号 | 必须动作 | 验证工具 |
|------|---------|---------|
| 调度函数占比高 | 溯源：主动休眠 vs 被动抢占 | `find-callers --target schedule` |
| 负载不均衡 (imbalance_level≥HIGH) | 分析：不能并行 vs 不想并行 | `analyze-core-distribution` |
| 锁函数出现 | 评估：锁粒度和竞争范围 | `find-callers --target <lock>` |
| 内存回收函数高 | 检查：内存压力或泄漏 | `cluster-paths` |
| 单进程 CPU 异常高 | 对比：是否符合其角色定位 | `get-hotspots --pid <pid>` |
| 系统 CPU 高但无明显高耗进程 | 检查：大量小进程集体消耗 | `get-comm-top` |
| 疑似内核瓶颈 | 检查：全局锁、中断、调度器 | `get-hotspots` / `cluster-paths` |

---

## 附录 A：bottleneck-trace 深度解析

### A.1 工具定位

`bottleneck-trace` 是 Composite 层的核心诊断工具，通过 **Bottom-Up + Top-Down 双视角聚合**，揭示瓶颈的完整上下文。

**与相关工具的关系**：

```
1. sys-audit (入口)
     发现瓶颈进程 app_B
2. bottleneck-trace --comm app_B (深度分析)
     发现热点: _raw_spin_lock, ut_delay
3. find-callers --target _raw_spin_lock --comm app_B
   find-callers --auto-target --comm app_B # 全局热点追踪
   cluster-paths --comm app_B
```

| 场景 | 推荐工具 | 说明 |
|------|----------|------|
| 不知道从何入手 | `sys-audit` | 全景扫描，自动识别瓶颈 |
| 已知瓶颈进程 | `bottleneck-trace` | 深度分析，调用链追踪 |
| 已知热点函数 | `find-callers` | 精确溯源 |
| 业务逻辑分析 | `cluster-paths` | 调用模式识别 |

### A.2 四阶段分析流程

```
Phase 1: 预处理阶段

   1. get-comm-top    提取 hot_comms（按 impact_score 排序）
   2. analyze-core-dstribution   提取 busy_cores（total_cpu > threshold）
     Saturation(comm, pid) = hot_comms ∩ busy_cores(comm, pid)
     （在忙核心上运行的热点进程，即真正瓶颈）

Phase 2: 热点分析阶段

   get-hotspots(hot_comm, sort-by=self)
     提取 hot_funcs（针对每个 hot_comm）
     Top N Self% 热点符号（CPU 消耗点）
     **热点标签：LOCK / SYSCALL / SCHED / MEMORY / IO / COMPUTE**


Phase 3: 调用链分析阶段
   find-callers(hot_comm,hot_funcs,sort=inclusive)
     获取 bottomup_callchains (谁调用了热点函数 - Bottom-Up 视角)
     Top N 调用者路径（按 inclusive 占比排序）

     cluster-paths(hot_comm, hot_funcs, sort-by=inclusive)
       获取 topdown_callchains（从入口到热点的完整路径 - Top-Down 视角）
       Top N 调用路径聚类（按 inclusive 占比排序）

Phase 4: 聚合输出阶段
   CONVERGENCE: 模糊匹配聚合 Top-Down 与 Bottom-Up

     识别 COMMON_HOTSPOT（共享热点符号）
     区分不同 Comm_Group 的调用路径特征
     标注 Path_Characteristic（路径特征标签）
     AFFINITY_PATTERN 判定（基于分布熵 Entropy）
      - Fixed:    核心绑定（高熵）
      - Uniform:  均匀分布（低熵）
      - Scattered: 分散无规律
```

### A.3 输出格式详解

#### [ENTITY_DISTRIBUTION_MATRIX]

实体分布矩阵，基于分布熵判定核心亲缘性模式。

| 字段 | 说明 | 来源 |
|------|------|------|
| Comm_Group | 进程组名称 | get-comm-top |
| Count | PID 数量 | get-comm-top |
| Incl_Saliency | Inclusive CPU 占比 | get-hotspots |
| Excl_Saliency | Self CPU 占比 | get-hotspots |
| Core_Affinity | 核心亲缘性模式 | analyze-core-distribution |
| Throttle_Rate | CPU 节流比例 | Core 层 |

**Core_Affinity 判定规则**：

| 模式 | 判定条件 | 说明 |
|------|----------|------|
| Fixed | Entropy < 0.3, Monopoly > 0.8 | 单核心绑定 |
| Uniform | Entropy > 2.0, CV < 0.5 | 均匀分布到多核 |
| Scattered | 其他情况 | 分散无规律 |

#### [CONVERGENCE_TRACE]

通过模糊匹配聚合 Top-Down 与 Bottom-Up 视角。

**组成部分**：
- **COMMON_HOTSPOT**: 所有聚类共享的热点符号（瓶颈汇聚点）
- **Cluster 列表**: 每个聚类包含 path、characteristic、weight

**Path_Characteristic 标签**：

| 标签 | 说明 | 触发条件 |
|------|------|----------|
| High_Frequency_Exclusive_CPU | 高频独占 CPU | Self% >> Inclusive% |
| Inclusive_Latency_Victim | 包容性延迟受害者 | 等待资源/锁 |
| Syscall_Bound | 系统调用密集 | 内核态占比 > 50% |
| Lock_Contention | 锁竞争 | 热点为 lock/mutex/spinlock |
| IO_Wait_Dominant | IO 等待主导 | io_schedule 高频 |

#### [CORRELATION_FLAGS]

跨维度关联检测，自动标记系统性问题。

| Flag | 检测条件 | 来源数据 |
|------|----------|----------|
| GLOBAL_LOCK_CONTENTION | 全局锁符号 inclusive% > 40% | get-hotspots |
| SINGLE_CORE_SATURATION | 单核利用率 > 90% 且 Monopoly > 0.8 | analyze-core-distribution |
| THROTTLE_VICTIM | Throttle_Rate > 50% | Core 层 + cgroup 分析 |
| STORM_PATTERN | Spawn_Rate > 100/s 或 PID_Count > 1000 | get-comm-top |
| KERNEL_HEAVY | 内核态占比 > 50% | get-hotspots |
| UNBALANCED_LOAD | CV > 1.5 且 Monopoly < 0.5 | get-comm-top |

#### [DATA_SUMMARY]

诊断会话元数据摘要。

| 字段 | 说明 | 来源 |
|------|------|------|
| total_pids | 采样期间唯一 PID 数 | Core 层 |
| total_sys_cpu | 系统总 CPU 利用率(%) | Core 层 |
| top_bottleneck | 排名前三的热点符号 | Composite 层聚合 |
| duration_sec | 采样持续时间 | Core 层 |
| sample_count | 总样本数 | Core 层 |
| data_quality | 数据质量评估 | OutputBuilder |

### A.4 命令参数

```bash
# 基础用法
shecr bottleneck-trace --auto-detect
shecr bottleneck-trace --comm <name>
shecr bottleneck-trace --pid <PID>

# 高级用法
shecr bottleneck-trace --comm <name> --hotspots-limit 30
shecr bottleneck-trace --comm <name> --callers-limit 20 --max-depth 10
shecr bottleneck-trace --comm <name> --verbose
```

**参数说明**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--comm` | 指定目标进程名 | - |
| `--pid` | 指定目标 PID | - |
| `--auto-detect` | 自动识别瓶颈进程 | false |
| `--hotspots-limit` | 热点分析数量限制 | 20 |
| `--callers-limit` | 调用链分析数量限制 | 10 |
| `--max-depth` | 最大调用链深度 | 5 |
| `--verbose` | 详细输出（含中间指标） | false |
| `--start-time` | 开始时间（ISO 8601） | - |
| `--end-time` | 结束时间（ISO 8601） | - |

📘 **详细规范**: [`docs/report/tool-bottleneck-trace.md`](../docs/report/tool-bottleneck-trace.md)

---

## 附录 C：启发式规则

### 五大认知闭包

| 原则 | 描述 | 实践要求 |
|------|------|---------|
| **经验锚定** | 无工具数据，不进行逻辑推演 | 每个假设必须对应一个探测动作 |
| **竞争性假设** | 保持"双线思维" | 延迟收敛，≥3 条假说到 Phase 3 |
| **搜索空间收敛** | 漏斗模型 | 先定天花板，再找主干道，最后定位局部 |
| **因果交叉验证** | 证据必须形成链条 | 业务层锁竞争必须与系统层调度延迟关联 |
| **证伪优先** | 最终结论前审计证据链 | "还有其他可能性吗？" |

### 问题边界判定规则

通过行为相似性和依赖路径判断问题边界：

| 判定维度 | 系统问题 | 单体问题 |
|----------|----------|----------|
| **行为相似性** | 多个进程表现出相似症状 | 单个进程独有的异常行为 |
| **共同依赖路径** | 问题出现在共享依赖路径（内核、共享库） | 问题局限于进程自身代码路径 |
| **影响范围** | 跨进程、跨用户、全局性下降 | 仅限于特定进程实例 |

**判定逻辑**：
```
IF (多个进程相似症状) AND (共享共同依赖路径):
    → 系统问题（基础设施/平台层）
ELSE IF (症状局限于单个进程):
    → 单体问题（应用层）
```

---

## 附录 D：诊断流程检查清单

### 分析前
- [ ] 创建诊断文档（基于 templates.md）
- [ ] 初始化：`shecr init --data-path <file>`
- [ ] 提出多条有足够搜索空间的假说
  - **代码维度**: 算法/实现层（热点函数、调用路径）
  - **架构维度**: 并发/调度层（锁竞争、调度干扰、资源争抢）
  - **环境维度**: 系统/外部层（资源限制、依赖延迟）

### 分析中
- [ ] 发现风险立即记录：`shecr trace add --desc "..."`
- [ ] 冰山一角：Top1 问题不一定是全部，其他高风险也要跟进
- [ ] 检查样本可靠性等级

### 分析后（生成报告前）
- [ ] 执行 `shecr trace finalize` 确认完整性
- [ ] 全局一致性检查：
  - [ ] 是否解释了所有观测到的异常？
  - [ ] 所有搜索空间是否都完成了验证?
  - [ ] 是否排除了反向证据？
  - [ ] 所有发现的风险是否都已记录为 issues？
  - [ ] 是否符合领域应有表现？

---

## 参考文档

| 文档 | 内容 |
|------|------|
| [SKILL.md](../SKILL.md) | 快速开始、场景速查 |
| [tools.md](./tools.md) | 命令参数详细参考 |
| [templates.md](./templates.md) | 诊断报告模板 |
| [design/design-three-tier-architecture.md](../docs/design/design-three-tier-architecture.md) | 三层架构设计详情 |
