# SPEAR 分析流程指南

基于 **Top-Down 宏观切入 + Bottom-Up 微观溯源** 混合分析模式的标准工作流程。

详细工具命令参考见 [tools.md](./tools.md)。

---

## 性能问题分类

诊断前先对问题进行分类，有助于选择正确的分析路径。

### 按表现形态分类

| 形态 | 特征 | 分析策略 | 推荐工具 |
|------|------|---------|---------|
| **持续高耗** | 稳定的高 CPU/内存 | 热点函数分析、代码优化 | `get-hotspots` + `find-callers` |
| **突发尖峰** | 间歇性资源飙升 | 异常检测、时序分析 | `detect-anomalies` |
| **长尾延迟** | P99 远高于均值 | 尾延迟分析、路径差异对比 | `analyze-core-distribution` |
| **资源压制** | Cgroup 限流触发 | 边界检查、配额分析 | `check-cpu-bottleneck` |

### 按系统层次分类

| 层次 | 问题域 | 关注信号 |
|------|--------|---------|
| **系统层** | 内核调度、中断、资源竞争 | `cluster-symbols` (EVENT_SCHEDULER, EVENT_IRQ_OFF) |
| **进程层** | 多进程协调、IPC | `cluster-comm`, `get-process-top` |
| **线程层** | 锁竞争、线程池效率 | `find-callers` 追溯同步原语 |
| **代码层** | 算法复杂度、数据结构 | `get-hotspots`, `cluster-paths` |

---

## 分析流程总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        性能分析流程 (Top-Down + Bottom-Up)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: 问题定义                                                            │
│  ├── 分析原始问题 → 明确观测到的异常现象                                        │
│  └── 提出可能性 → 基于领域知识枚举竞争性假设                                    │
│                              ↓                                              │
│  Phase 2: 宏观评估 (Top-Down)                                                 │
│  ├── show-cpu-usage → 系统/进程级资源消耗概览                                  │
│  ├── detect-anomalies → 时序异常检测与窗口定位                                 │
│  └── analyze-core-distribution → 核心级负载分布与均衡性分析                      │
│                              ↓                                              │
│  Phase 3: 敏感路径识别 (Bottom-Up 切入点)                                      │
│  ├── get-process-top → 识别高消耗进程                                          │
│  ├── get-hotspots → 识别热点函数 (self/inclusive)                             │
│  ├── find-callers → 热点函数调用溯源                                          │
│  └── cluster-paths → 调用路径聚类，识别共同前缀模式                             │
│                              ↓                                              │
│  Phase 4: 语义分析 (领域认知)                                                  │
│  └── 根据符号名猜测 workload 和技术领域                                        │
│      ├── 记录领域 workload 特征                                               │
│      ├── 识别框架/库类型 (Web框架、数据库、参数服务器等)                          │
│      └── 建立"预期 vs 现实"对比基线                                            │
│                              ↓                                              │
│  Phase 5: 空间搜索 (模式聚类)                                                  │
│  └── cluster-symbols → 按专家规则语义聚类                                      │
│      ├── 调度行为 (SCHEDULING)                                                │
│      ├── 锁竞争 (LOCK_CONTENTION)                                             │
│      ├── 内存回收 (MEM_RECLAIM)                                               │
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

### 1.1 分析原始问题

**目标**: 明确观测到的异常现象，建立问题陈述

**关键问题**:
- 用户报告的"慢"具体指什么？（延迟高？吞吐低？CPU高？）
- 是否有明确的性能指标基线？
- 异常是否可以复现？发生时有什么特征？

### 1.2 感知手段框架

从不同维度收集证据，形成完整的性能画像：

| 感知维度 | 原始数据 | 加工后信息 | 决策价值 |
|---------|---------|-----------|---------|
| **资源边界** | CPU quota, 利用率 | 瓶颈类型判定 | 确定优化天花板 |
| **时间分布** | 采样时间戳 | 异常模式识别 | 定位异常时刻 |
| **空间分布** | 调用栈 | 热点路径 | 识别性能主干 |
| **语义分类** | 函数名 | 业务模块归类 | 确定优化层级 |
| **进程视角** | PID/comm | 进程聚合统计 | 资源归属判定 |

### 1.3 提出可能性

**目标**: 基于领域知识枚举竞争性假设（至少 3 条）

**假设格式**:
```yaml
假设A_资源竞争:
  机制: 全局锁导致串行化
  预期指纹: 热点函数包含锁操作，负载分散在多个核心但单核满载
  验证: get-hotspots + find-callers + analyze-core-distribution
  证伪: 热点中无锁函数，或所有核心均衡满载

假设B_调度压制:
  机制: 应用层主动休眠或系统调度限制
  预期指纹: 调度函数占比高，imbalance_level=CRITICAL，states中sleeping多
  验证: cluster-symbols + analyze-core-distribution
  证伪: 调度开销正常，且无主动休眠证据

假设C_进程风暴:
  机制: 短生命周期进程频繁创建销毁
  预期指纹: count-process-variety 检测到 PROCESS_STORM
  验证: count-process-variety
  证伪: PID数量正常，样本/PID比值正常
```

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

---

## Phase 3: 敏感路径识别 (Bottom-Up 切入点)

**目标**: 从微观层面识别资源消耗热点，建立溯源起点

### 3.1 高消耗进程识别

| 工具 | 适用场景 | 关键区别 |
|------|----------|----------|
| `get-process-top` | 找单个高消耗进程 | 无法识别大量小进程集体消耗 |
| `get-comm-top` | 找同类进程集体消耗 | 识别 Worker pool 过度扩容等场景 |

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
    - 数据库往往有自己实现的spinlock，注意语义上等价spinlock的函数
```

---

## Phase 5: 空间搜索 (模式聚类)

**目标**: 按语义规则聚类符号，识别隐藏的行为模式

### 5.1 专家规则聚类

**工具**: `cluster-symbols`

**内置规则分类**:
| 类别 | 匹配模式 | 含义 |
|------|---------|------|
| `EVENT_IRQ_OFF` | IRQ off, spin_unlock | 长临界区 |
| `EVENT_SCHEDULER` | schedule, yield | 调度器活动 |
| `EVENT_MEM_RECLAIM` | reclaim, TLB, page | 内存回收 |
| `EVENT_LOCK_CONTENTION` | mutex, spinlock, futex | 锁竞争 |
| `EVENT_SYNC_PRIMITIVE` | pthread_cond, barrier | 同步原语 |

**自定义规则**: 支持按领域特定模式匹配（如 RPC、DB、ML 等）

---

## Phase 6: 领域定位 (系统行为刻画)

**目标**: 刻画进程级行为模式，识别异常行为

### 6.1 进程风暴检测

**工具**: `count-process-variety`

**检测模式**:
| 模式 | 条件 | 含义 |
|------|------|------|
| `PROCESS_STORM` | PID ≥ 阈值 且 样本/PID ≤ 阈值 | 短生命周期进程风暴 |
| `SHORT_LIVED_HEAVY` | 单样本进程 > 80% 且 PID > 20 | 大量瞬时进程 |
| `LONG_RUNNING` | 单进程主导 | 正常长期运行进程 |

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

| 信号 | 必须动作 | 验证工具 |
|------|---------|---------|
| 调度函数占比高 | 溯源：主动休眠 vs 被动抢占 | find-callers --target schedule |
| 负载不均衡 (imbalance_level≥HIGH) | 分析：不能并行 vs 不想并行 | analyze-core-distribution |
| 锁函数出现 | 评估：锁粒度和竞争范围 | find-callers + 代码审查 |
| 内存回收函数高 | 检查：内存压力或泄漏 | cluster-symbols (MEM_RECLAIM) |
| 单进程 CPU 异常高 | 对比：是否符合其角色定位 | get-hotspots --pid |
| 系统 CPU 高但无明显高耗进程 | 检查：是否存在大量小进程集体消耗 | get-comm-top |

### 7.2 全局一致性检查

在得出结论前，必须确认：

- [ ] **是否解释了所有观测到的异常？**
  - CPU 利用率异常
  - 负载分布异常
  - 时序异常
  - 进程行为异常

- [ ] **是否符合领域应有表现？**
  - 该类型应用的典型 CPU 模式
  - 该类型应用的典型负载分布
  - 该类型应用的典型热点函数

- [ ] **是否有无法解释的孤证？**
  - 某个异常信号无法被当前假设解释
  - 需要重置流程，补充新假设

- [ ] **证据链是否闭环？**
  - 每个结论都有工具输出支撑
  - 假设 → 验证 → 证据 → 结论

---

## 典型分析模式 (快捷路径)

### 模式 A: 单进程 CPU 高 (Top-Down → Bottom-Up)

```bash
# Step 1: 宏观确认
show-cpu-usage --pid 1234
analyze-core-distribution --pid 1234

# Step 2: 如果 imbalance_level=CRITICAL
#   sleeping 多 → 主动休眠问题
#   active 多 → 锁竞争问题

# Step 3: 热点溯源
get-hotspots --pid 1234 --sort-by self
find-callers --auto-target --pid 1234

# Step 4: 语义聚类
cluster-symbols --pid 1234 --custom-rules '{"SCHED": "schedule|sleep"}'
```

### 模式 B: 系统整体缓慢 (Top-Down 优先)

```bash
# 关注内核瓶颈
# Step 1: 系统级概览
check-cpu-bottleneck
get-process-top

# Step 2: 异常定位
detect-anomalies

# Step 3: 对异常窗口/进程深入
cluster-paths --start-time <t1> --end-time <t2>
get-hotspots --sort-by self
find-callers --auto-target
```

### 模式 C: 疑似进程风暴 (领域定位优先)

```bash
# Step 1: 行为检测
count-process-variety
get-comm-top

# Step 2: 如果检测到 PROCESS_STORM
cluster-comm
cluster-symbols --comm <storm-comm>

# Step 3: 溯源热点
get-hotspots --comm <storm-comm>
find-callers --auto-target --comm <storm-comm>
```

### 模式 D: 负载不均衡专项分析

```bash
# Step 1: 确认不均衡程度
analyze-core-distribution --pid 1234

# Step 2: 根据 patterns 建议行动
# SINGLE_CORE_SATURATION → 检查调度/锁
# WIDE_DISTRIBUTION_LOW_UTIL → 检查资源充足性

# Step 3: 定向分析
cluster-symbols --pid 1234  # 看 SCHEDULING/LOCK 占比
find-callers --target <调度函数或锁函数>
```

---

## 数据可靠性评估

| 等级 | 条件 | 误差范围 | 建议 |
|-----|------|---------|------|
| **CRITICAL** | CPU<3% 或 样本<10 | 不可信 | 延长采样时间后重新采集 |
| **WARNING** | CPU<10% 且 样本<30 | > ±25% | 关注趋势而非精确值 |
| **ACCEPTABLE** | CPU 10-30% 且 样本<100 | ±10-15% | 可用于粗略趋势分析 |
| **GOOD** | CPU 30-60% 且 样本≥100 | ±5-10% | 结论可信 |
| **EXCELLENT** | CPU≥60% 且 样本≥200 | < ±3% | 统计结论高度可信 |

---

## 参考文档

- 📘 **工具命令参考**: [tools.md](./tools.md) - 详细命令、参数、使用示例
- 📕 **启发式规则手册**: [heuristics.md](./heuristics.md) - 五大认知闭包、诊断规则
- 📗 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
