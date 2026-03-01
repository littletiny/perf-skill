# SPEAR 核心分析流程

> 基于 **Top-Down 宏观切入 + Bottom-Up 微观溯源** 混合分析模式。

详细工具命令参考见 [tools.md](./tools.md)，典型场景快速路径见 [workflow-patterns.md](./workflow-patterns.md)。

---

## 性能问题分类

诊断前先对问题进行分类，有助于选择正确的分析路径。

### 按表现形态分类

| 形态 | 特征 | 分析策略 | 快速路径 |
|------|------|---------|---------|
| **持续高耗** | 稳定的高 CPU/内存 | 热点函数分析、代码优化 | [模式 A](./workflow-patterns.md#模式-a-单进程-cpu-高) |
| **突发尖峰** | 间歇性资源飙升 | 异常检测、时序分析 | `detect-anomalies` |
| **长尾延迟** | P99 远高于均值 | 尾延迟分析、路径差异对比 | [模式 D](./workflow-patterns.md#模式-d-负载不均衡) |
| **资源压制** | Cgroup 限流触发 | 边界检查、配额分析 | [模式 B](./workflow-patterns.md#模式-b-系统整体缓慢) |

### 按系统层次分类

| 层次 | 问题域 | 关注信号 | 典型工具 |
|------|--------|---------|---------|
| **系统层** | 内核调度、中断、资源竞争 | `cluster-symbols` (EVENT_SCHEDULER, EVENT_IRQ_OFF) | `get-comm-top`, `cluster-symbols` |
| **进程层** | 多进程协调、IPC | `cluster-comm`, `get-process-top` | `count-process-variety` |
| **线程层** | 锁竞争、线程池效率 | `find-callers` 追溯同步原语 | `find-callers --target <lock>` |
| **代码层** | 算法复杂度、数据结构 | `get-hotspots`, `cluster-paths` | `get-hotspots --sort-by self` |

---

## 分析流程总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        性能分析流程 (Top-Down + Bottom-Up)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: 问题定义                                                            │
│  ├── 分析原始问题 → 明确观测到的异常现象                                        │
│  └── 提出三候选假说 → 基于领域知识枚举竞争性假设                                 │
│                              ↓                                              │
│  Phase 2: 宏观评估 (Top-Down)                                                 │
│  ├── show-cpu-usage → 系统/进程级资源消耗概览                                  │
│  ├── detect-anomalies → 时序异常检测与窗口定位                                 │
│  └── analyze-core-distribution → 核心级负载分布与均衡性分析                      │
│                              ↓                                              │
│  Phase 3: 敏感路径识别 (Bottom-Up 切入点)                                      │
│  ├── get-process-top / get-comm-top → 识别高消耗进程/进程组                     │
│  ├── get-hotspots → 识别热点函数 (self/inclusive)                             │
│  ├── find-callers → 热点函数调用溯源                                          │
│  └── cluster-paths → 调用路径聚类，识别共同前缀模式                             │
│                              ↓                                              │
│  Phase 4: 语义分析 (领域认知)                                                  │
│  └── 根据符号名猜测 workload 和技术领域                                        │
│      ├── 记录领域 workload 特征                                               │
│      ├── 识别框架/库类型 (Web框架、数据库、linux kernel)                          │
│      └── 建立"预期 vs 现实"对比基线                                            │
│                              ↓                                              │
│  Phase 5: 空间搜索 (模式聚类)                                                  │
│  └── cluster-symbols → 按专家规则语义聚类                                      │
│      ├── 调度行为 (EVENT_SCHEDULER)                                           │
│      ├── 锁竞争 (EVENT_LOCK_CONTENTION)                                       │
│      ├── 内存回收 (EVENT_MEM_RECLAIM)                                         │
│      └── 自定义规则匹配领域特定模式                                             │
│                              ↓                                              │
│  Phase 6: 领域定位 (系统行为刻画)                                               │
│  ├── count-process-variety → 检测进程风暴/短生命周期进程                         │
│  └── cluster-comm → 按进程名聚类分析进程组行为                                  │
│                              ↓                                              │
│  Phase 7: 专家经验查缺补漏                                                      │
│  ├── 基于领域知识验证假设                                                      │
│  ├── 检查关键信号 (调度函数→溯源、负载不均→分析、锁→评估粒度)                     │
│  └── 全局一致性检查：是否解释所有异常？                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 问题定义

> ⚠️ **Phase 1 第一步**: 创建诊断文档 + 初始化 Trace（强制执行）
>
> **必须按顺序执行以下步骤，缺一不可：**
>
> ```bash
> # 1. 创建 debug 目录（如果不存在）
> mkdir -p debug
>
> # 2. 【关键】基于 templates.md 创建诊断文档 —— 这是主记录文档
>
> # 3. 用编辑器填写 debug/*.md 中的表格：
> #    - 问题演进记录表（记录问题定义的变化）
> #    - 竞争性假设追踪表（至少3条竞争性假设：代码/架构/环境）
>
> # 4. 初始化 Trace —— 这只是辅助状态追踪
> spear trace init --data xxx.data
> ```
>
> **重要区分**：
> - `debug/*.md` = **主文档**（手动维护，记录完整分析过程）
> - `Trace` = **状态追踪**（自动生成，只记录问题列表和状态）
>
> **禁止行为**：❌ 只执行 `trace init` 而不创建 `debug/*.md` 文档

### 1.1 目标范围界定

**核心原则**: **目标问题与工具参数必须一致**

用户明确指定了分析目标（如特定 PID、特定进程名、特定时间窗口），所有工具命令必须携带对应的过滤参数，否则分析结果将偏离目标。

| 目标类型 | 用户描述示例 | 参数策略 | 错误后果 |
|---------|-------------|---------|---------|
| **特定进程** | "PID 12345 的 CPU 上不去" | **必须加** `--pid 12345` | 分析全系统数据，得出错误结论 |
| **特定进程组** | "worker 进程集体高消耗" | **必须加** `--comm worker` | 混入其他进程数据，稀释信号 |
| **特定时段** | "每天晚上 8 点卡顿" | **必须加** `--start-time/--end-time` | 被其他时段数据干扰 |
| **系统级瓶颈** | "整个系统都很慢/所有服务都受影响" | **不加** `--pid`/`--comm` | 过早过滤会遗漏全局锁、内核瓶颈等系统级问题 |

**一致性检查清单**:
- [ ] 用户是否指定了具体 PID？→ 所有命令加 `--pid`
- [ ] 用户是否提及进程名/服务名？→ 考虑加 `--comm`
- [ ] 问题是否有明确时间特征？→ 考虑加 `--start-time/--end-time`
- [ ] **问题是否可能是系统级？**（多服务同时受影响、内核相关、全局锁竞争）→ **先全局分析，定位后再定向深入**

### 1.2 分析原始问题

**目标**: 明确观测到的异常现象，建立问题陈述

**关键问题**:
- 用户报告的"慢"具体指什么？（延迟高？吞吐低？CPU高？）
- 是否有明确的性能指标基线？
- 异常是否可以复现？发生时有什么特征？

### 1.3 提出三候选假说（强制执行）

**目标**: 基于领域知识枚举竞争性假设（至少 3 条）

**三维度假说模板**:

| 维度 | 假说方向 | 示例 |
|------|---------|------|
| **代码维度** | 热点函数、算法复杂度、数据结构效率 | "某函数算法复杂度高导致 CPU 高" |
| **架构维度** | 锁竞争、线程池配置、并行度设计 | "全局锁导致串行化，无法扩展" |
| **环境维度** | 资源限制、内核瓶颈、基础设施 | "Cgroup CPU 限制导致压制" |

**假说格式**（在诊断文档中记录）:
```yaml
假说 ID: HYP-001
名称: 全局锁竞争
机制: 进程使用全局锁保护共享数据结构，导致串行化
预期指纹:
  - single_core_saturation: true
  - lock_ratio: ">30%"
验证方法: "find-callers --target <lock> --pid <PID>"
证伪条件: "锁来自不同调用路径，无集中竞争"
```

### 1.4 感知手段框架

从不同维度收集证据，形成完整的性能画像：

| 感知维度 | 原始数据 | 加工后信息 | 决策价值 |
|---------|---------|-----------|---------|
| **资源边界** | CPU quota, 利用率 | 瓶颈类型判定 | 确定优化天花板 |
| **时间分布** | 采样时间戳 | 异常模式识别 | 定位异常时刻 |
| **空间分布** | 调用栈 | 热点路径 | 识别性能主干 |
| **语义分类** | 函数名 | 业务模块归类 | 确定优化层级 |
| **进程视角** | PID/comm | 进程聚合统计 | 资源归属判定 |

### 1.5 记录待验证问题

**目标**: 将发现的潜在问题记录到 Trace，防止遗漏

**何时记录**:
- 发现多个高消耗进程/进程组时
- 检测到异常模式（如 `SINGLE_CORE_SATURATION`, `PROCESS_STORM`）
- 发现高内核态比例或其他异常指标

**如何记录**:
```bash
# 示例：get-comm-top 发现异常进程组，全部记录
spear trace add --id ISS-001 --desc "redis 内核开销 94.7%" \
  --risk "内核负载过高" --hint "cluster-symbols --comm redis"
```

**⚠️ 重要**: spearert 非doc子命令的任何风险都需要记录

---

## Phase 2: 宏观评估 (Top-Down)

**目标**: 从系统级视角建立资源消耗全貌，识别异常模式

### 2.1 资源消耗概览

**工具**: `show-cpu-usage`

**分析要点**:
- 总利用率与预期是否匹配？
- user/kernel 比例是否正常？（计算密集型 user 高，IO 型 kernel 可能高）
- 结合 cgroup limit 判断是否被压制

### 2.2 时序异常检测

**工具**: `detect-anomalies`

**检测类型**: `SPIKE` | `DROP` | `LEVEL_SHIFT` | `BURST`

**典型用途**:
- 定位异常发生的时间窗口
- 区分持续问题 vs 间歇性问题
- 为后续定向分析提供 `--start-time` / `--end-time` 参数

### 2.3 核心级负载分析

**工具**: `analyze-core-distribution`

**典型用途**:
- 是否存在单核瓶颈
- 是否存在负载不均匀

**下一步决策**:
- `imbalance_level=CRITICAL` → [模式 D: 负载不均衡](./workflow-patterns.md#模式-d-负载不均衡)
- `SINGLE_CORE_SATURATION` 模式 → 检查调度/锁竞争

---

## Phase 3: 敏感路径识别 (Bottom-Up 切入点)

**目标**: 从微观层面识别资源消耗热点，建立溯源起点

### 3.1 高消耗进程识别

| 工具 | 适用场景 | 关键区别 |
|------|----------|----------|
| `get-process-top` | 找单个高消耗进程 | 无法识别大量小进程集体消耗 |
| `get-comm-top` | 找同类进程集体消耗 | 识别 Worker pool 过度扩容等场景 |

**下一步决策**:
- 单个进程高消耗 → [模式 A: 单进程 CPU 高](./workflow-patterns.md#模式-a-单进程-cpu-高)
- 同类进程集体高消耗 → [模式 C: 进程风暴](./workflow-patterns.md#模式-c-进程风暴)
- kernel% 高 → [模式 E: 高内核态](./workflow-patterns.md#模式-e-高内核态分析)

### 3.2 热点函数识别

**工具**: `get-hotspots`

**排序方式**:
- `inclusive`: 包含子调用的时间，反映整体影响
- `self`: 仅函数自身执行时间，反映直接消耗

**分析策略**:
- CPU 高但不知道热点 → `--sort-by self` 找直接消耗
- 已知入口函数想分析子调用 → `--sort-by inclusive`，后续配合 `find-callers`

### 3.3 热点函数溯源

**工具**: `find-callers`

**关键检查点**:
- 发现调度函数 (`schedule`/`nanosleep`/`epoll_wait`) → **必须溯源**
  - 调用路径中有业务逻辑 → 主动休眠
  - 调用路径只有内核 → 被动抢占
- 发现锁函数 (`pthread_mutex_lock`/`spinlock`) → **评估粒度**
  - 调用频率高但持有时间短 → 可能正常
  - 调用频率低但持有时间长 → 粗粒度锁问题

### 3.4 调用路径聚类

**工具**: `cluster-paths`

**用途**:
- 从 top-down 视角审视 bottom-up 收集到的信息
- 使用 Trie 识别共同的调用前缀
- 识别高频调用模式

---

## Phase 4: 语义分析 (领域认知)

**目标**: 根据符号名识别 workload 类型和技术栈，建立领域预期

### 4.1 符号名领域映射

| 符号模式 | 推断技术领域 | 典型 Workload |
|---------|------------|--------------|
| `grpc`/`protobuf` | RPC 框架 | 微服务调用 |
| `rocksdb`/`leveldb` | 嵌入式 KV | 数据库/缓存 |
| `mysqld`/`postgres` | OLTP数据库 | 延迟敏感，平均利用率低，峰值高 |
| `clickhouse`/`duckdb` | OLAP数据库 | 带宽敏感，资源利用率高 |
| `redis`/`hiredis` | 缓存系统 | 高速缓存访问，延迟敏感 |
| `tensorflow`/`torch` | 深度学习 | 训练/推理 |
| `openssl`/`crypto` | 加密库 | HTTPS/加密通信 |
| `zlib`/`snappy`/`lz4` | 压缩库 | 数据压缩/解压 |
| `json`/`yaml`/`xml` | 序列化 | 配置解析/数据传输 |
| `malloc`/`free`/`new` | 内存管理 | 频繁内存分配 |
| `epoll`/`select`/`poll` | IO 多路复用 | 高并发网络服务 |
| `pthread_mutex`/`rwlock` | 线程同步 | 多线程竞争 |

### 4.2 领域 Workload 特征记录

建立当前系统的领域特征档案：

```yaml
领域档案示例:
  应用类型: OLTP数据库
  框架线索:
    - mysqld
    - postgres
  预期特征:
    CPU模式: 网络密集型 + 间歇性计算突发
    典型热点: 内核网络栈、磁盘IO栈、各种复杂的sql处理
    负载分布: 多线程并行，延迟敏感
  异常信号:
    - 单核满载 → 不符合预期，可能存在串行化瓶颈
    - 调度函数出现频率高 → 不符合预期，可能存在过度同步
```

---

## Phase 5: 空间搜索 (模式聚类)

**目标**: 按语义规则聚类符号，识别隐藏的行为模式

### 5.1 专家规则聚类

**工具**: `cluster-symbols`

**内置规则分类**:
| 类别 | 匹配模式 | 含义 | 下一步动作 |
|------|---------|------|-----------|
| `EVENT_IRQ_OFF` | IRQ off, spin_unlock | 长临界区 | `analyze-core-distribution` 查看 per-CPU |
| `EVENT_SCHEDULER` | schedule, yield | 调度器活动 | `find-callers --target schedule` |
| `EVENT_MEM_RECLAIM` | reclaim, TLB, page | 内存回收 | 查看具体回收函数分布 |
| `EVENT_LOCK_CONTENTION` | mutex, spinlock, futex | 锁竞争 | `find-callers --target <lock>` |
| `EVENT_SYNC_PRIMITIVE` | pthread_cond, barrier | 同步原语 | 评估同步粒度 |

**自定义规则**: 支持按领域特定模式匹配（如 RPC、DB、ML 等）

---

## Phase 6: 领域定位 (系统行为刻画)

**目标**: 刻画进程级行为模式，识别异常行为

### 6.1 进程风暴检测

**工具**: `count-process-variety`

**检测模式**:
| 模式 | 条件 | 含义 |
|------|------|------|
| `PROCESS_STORM` | samples_per_pid 低 且 short_lived_ratio 高 | 短生命周期进程风暴 |
| `LONG_RUNNING` | 单进程主导 | 正常长期运行进程 |

**下一步**:
- 检测到 `PROCESS_STORM` → [模式 C: 进程风暴](./workflow-patterns.md#模式-c-进程风暴)

### 6.2 进程名聚类

**工具**: `cluster-comm`

**用途**:
- 识别同类型进程的资源消耗汇总
- 发现异常进程类型（如预期外的辅助进程）
- 评估进程间资源分配合理性

---

## Phase 7: 专家经验查缺补漏

**目标**: 基于领域知识验证结论完整性，确保没有遗漏

### 7.1 关键信号检查清单

| 信号 | 必须动作 | 验证工具 | 参数策略 |
|------|---------|---------|---------|
| 调度函数占比高 | 溯源：主动休眠 vs 被动抢占 | `find-callers --target schedule` | **明确有特定进程异常** → 加 `--pid`<br>**系统级分析** → 不加，先看全局分布 |
| 负载不均衡 (imbalance_level≥HIGH) | 分析：不能并行 vs 不想并行 | `analyze-core-distribution` | **明确有特定进程异常** → 加 `--pid`<br>**系统级分析** → 不加，确认影响范围 |
| 锁函数出现 | 评估：锁粒度和竞争范围 | `find-callers --target <lock>` | **明确有特定进程异常** → 加 `--pid`<br>**全局锁竞争** → 不加，分析全系统影响 |
| 内存回收函数高 | 检查：内存压力或泄漏 | `cluster-symbols` (MEM_RECLAIM) | **明确有特定进程异常** → 加 `--pid`<br>**系统级内存压力** → 不加 |
| 单进程 CPU 异常高 | 对比：是否符合其角色定位 | `get-hotspots --pid <PID>` | **必须加** `--pid` |
| 系统 CPU 高但无明显高耗进程 | 检查：是否存在大量小进程集体消耗 | `get-comm-top` | **不加** 过滤参数，系统级视图 |
| 疑似内核瓶颈 | 检查：全局锁、中断、调度器 | `get-hotspots` / `cluster-symbols` | **不加** `--pid`，分析 kernel 空间热点 |

### 7.2 审计检查点（⚠️ 强制执行）

#### 定期审计（每 2-3 个工具后）

**必须执行 `trace issues` 检查待办问题**：

```bash
spear trace issues
```

**输出解读**:
- 如有 `PENDING` 问题 → 继续分析，不要提前收敛
- 确保所有重要问题都得到处理

#### 最终审计（生成报告前）

**必须执行 `trace finalize` 确认完整性**：

```bash
spear trace finalize
```

**可能输出**:
1. **全部完成**: ✅ 所有问题已处理 → 可以生成报告
2. **有未处理问题**: ⚠️ 剩余风险确认 → 选择 [A]继续分析 / [B]接受风险 / [C]标记为无需处理

### 7.3 全局一致性检查

在得出结论前，必须确认：

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

- [ ] **Trace 中是否还有未处理的 `PENDING` 问题？**
  - 执行 `trace issues` 确认
  - 执行 `trace finalize` 完成最终审计

- [ ] **是否符合领域应有表现？**
  - 该类型应用的典型 CPU 模式
  - 该类型应用的典型负载分布
  - 该类型应用的典型热点函数

---

## 快速参考

### 典型分析模式（详细路径）

| 模式 | 场景 | 文档 |
|------|------|------|
| 模式 A | 单进程 CPU 高 | [workflow-patterns.md#模式-a](./workflow-patterns.md#模式-a-单进程-cpu-高) |
| 模式 B | 系统整体缓慢 | [workflow-patterns.md#模式-b](./workflow-patterns.md#模式-b-系统整体缓慢) |
| 模式 C | 进程风暴 | [workflow-patterns.md#模式-c](./workflow-patterns.md#模式-c-进程风暴) |
| 模式 D | 负载不均衡 | [workflow-patterns.md#模式-d](./workflow-patterns.md#模式-d-负载不均衡) |
| 模式 E | 高内核态 | [workflow-patterns.md#模式-e](./workflow-patterns.md#模式-e-高内核态分析) |

### 参考文档

- 📗 **典型分析模式**: [workflow-patterns.md](./workflow-patterns.md) - 5 种场景的完整分析路径
- 📘 **工具命令参考**: [tools.md](./tools.md) - 详细命令、参数、使用示例
- 📕 **启发式规则手册**: [heuristics.md](./heuristics.md) - 五大认知闭包、诊断规则
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
- 📊 **数据格式**: [data-format.md](./data-format.md) - 输入数据格式说明
