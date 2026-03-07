# Tool: `bottleneck-analyze`

> 瓶颈深度分析工具 - Composite Layer 组合诊断命令
> 
> 职责：通过多维度聚合分析，定位并解释 CPU 瓶颈根因

---

## 概述

`bottleneck-analyze` 是 perf-hunter 的核心组合诊断工具，整合多个 Analysis 层分析器，通过 **Bottom-Up + Top-Down 双视角聚合**，揭示瓶颈的完整上下文。

### 核心能力

| 能力 | 说明 | 对应分析器 |
|------|------|-----------|
| 瓶颈进程识别 | 基于 Monopoly/ImpactScore 自动识别真瓶颈 | `analyze_comm_top` |
| 热点函数定位 | Self/Inclusive 双维度热点分析 | `analyze_hotspots` |
| 调用链溯源 | Bottom-Up 视角，追踪热点来源 | `analyze_callers` |
| 路径聚类 | Top-Down 视角，识别业务调用模式 | `cluster_paths` |
| 核心分布分析 | 检测单核饱和与线程亲缘性 | `analyze_core_distribution` |
| 进程饱和度计算 | 交叉分析 busy_cores 与 hot_comms | Core 层查询 |

---

## 分析流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BOTTLENECK-ANALYZE 分析管线                         │
└─────────────────────────────────────────────────────────────────────────────┘

Phase 1: 预处理阶段
─────────────────
  ┌─────────────────┐
  │ get-comm-top    │  → 提取 hot_comms（按 impact_score 排序）
  └────────┬────────┘
           │ CommTopResult.groups[]
           ▼
  ┌─────────────────┐
  │ analyze-core-   │  → 提取 busy_cores（total_cpu > threshold）
  │ distribution    │
  └────────┬────────┘
           │ CoreDistributionResult.saturated_cores[]
           ▼
  ┌─────────────────┐
  │ Core层查询      │  → 获取 busy_cores 上的 (comm, pid) 列表
  │ get_pid_cpu_    │
  │ info()          │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │ Saturation(comm, pid) = hot_comms ∩ busy_cores(comm, pid) │
  │ （在忙核心上运行的热点进程，即真正瓶颈）                    │
  └─────────────────────────────────────────────────────────┘

Phase 2: 热点分析阶段
─────────────────────
  ┌─────────────────┐
  │ get-hotspots    │  → 提取 hot_funcs（针对每个 hot_comm）
  │ (hot_comm,      │     sort-by=self（自耗时排序）
  │  sort-by=self)  │
  └────────┬────────┘
           │ HotspotsResult.hotspots[]
           │
           ├──▶ Top N Self% 热点符号（CPU 消耗点）
           └──▶ 资源标签：LOCK / SYSCALL / SCHED / MEMORY / IO / COMPUTE

Phase 3: 调用链分析阶段
───────────────────────
  ┌─────────────────┐
  │ find-callers    │  → 获取 bottomup_callchains
  │ (hot_comm,      │     （谁调用了热点函数 - Bottom-Up 视角）
  │  hot_funcs,     │
  │  sort-by=       │
  │  inclusive)     │
  └────────┬────────┘
           │ CallersResult.callers[]
           │
           └──▶ Top N 调用者路径（按 inclusive 占比排序）

  ┌─────────────────┐
  │ cluster-paths   │  → 获取 topdown_callchains
  │ (hot_comm,      │     （从入口到热点的完整路径 - Top-Down 视角）
  │  hot_funcs,     │
  │  sort-by=       │
  │  inclusive)     │
  └────────┬────────┘
           │ PathClustersResult.clusters[]
           │
           └──▶ Top N 调用路径聚类（按 inclusive 占比排序）

Phase 4: 聚合输出阶段
─────────────────────
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ CONVERGENCE: 模糊匹配聚合 Top-Down 与 Bottom-Up                          │
  │                                                                         │
  │  - 识别 COMMON_HOTSPOT（共享热点符号）                                    │
  │  - 区分不同 Comm_Group 的调用路径特征                                     │
  │  - 标注 Path_Characteristic（路径特征标签）                               │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ AFFINITY_PATTERN 判定（基于分布熵 Entropy）                              │
  │                                                                         │
  │  - Fixed:    核心绑定（高熵）                                             │
  │  - Uniform:  均匀分布（低熵）                                             │
  │  - Scattered: 分散无规律                                                  │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 输出格式

### [ENTITY_DISTRIBUTION_MATRIX]

*工具在此处完成聚合，并根据分布熵（Entropy）判定 Affinity_Pattern*

| Comm_Group | Count | Incl_Saliency | Excl_Saliency | Core_Affinity | Throttle_Rate |
|------------|-------|---------------|---------------|---------------|---------------|
| **`app_B`** | 1 | **0.96** | 0.12 | **Fixed: [Core_4]** | **82.5%** |
| **`lsof`** | 2000 | 0.45 | **0.88** | **Uniform: [Core_0-255]** | 5.2% |
| `others` | 420 | 0.02 | 0.01 | Scattered | 0.0% |

**字段说明**:

| 字段 | 来源 | 说明 |
|------|------|------|
| Comm_Group | `get-comm-top` | 进程组名称 |
| Count | `get-comm-top` | PID 数量 |
| Incl_Saliency | `get-hotspots` (inclusive) | Inclusive CPU 占比 |
| Excl_Saliency | `get-hotspots` (self) | Self CPU 占比 |
| Core_Affinity | `analyze-core-distribution` | 核心亲缘性模式 |
| Throttle_Rate | Core 层计算 | CPU 限制/节流比例 |

**Core_Affinity 判定规则**:

| 模式 | 判定条件 | 说明 |
|------|----------|------|
| Fixed | Entropy < 0.3, Monopoly > 0.8 | 单核心绑定 |
| Uniform | Entropy > 2.0, CV < 0.5 | 均匀分布到多核 |
| Scattered | 其他情况 | 分散无规律 |

---

### [CONVERGENCE_TRACE]

*工具通过模糊匹配聚合 Top-Down 与 Bottom-Up，展示路径分叉与重合点*

#### **COMMON_HOTSPOT: `_raw_spin_lock` 72.4%**

*所有聚类共享的热点符号，通常是瓶颈汇聚点*

---

#### **[lsof Cluster 68%]**

`lsof` -> `vfs_read` -> `iterate_dir` -> `__d_lookup_rcu` -> **[HOTSPOT]**

* **Characteristic**: `High_Frequency_Exclusive_CPU`
* **Weight**: 68%（占总样本比例）
* **来源**: cluster-paths 聚类结果

---

#### **[appB single/serval 28%]**

`app_B` -> `handle_request` -> `write_log` -> `__cfs_rq_runtime_get` -> **[HOTSPOT]**

* **Characteristic**: `Inclusive_Latency_Victim` (Blocked on quota/lock)
* **Weight**: 28%（占总样本比例）
* **来源**: find-callers 调用链 + cluster-paths 路径匹配

**Path_Characteristic 标签体系**:

| 标签 | 说明 | 触发条件 |
|------|------|----------|
| `High_Frequency_Exclusive_CPU` | 高频独占 CPU | Self% >> Inclusive% |
| `Inclusive_Latency_Victim` | 包容性延迟受害者 | 等待资源/锁 |
| `Syscall_Bound` | 系统调用密集 | 内核态占比 > 50% |
| `Lock_Contention` | 锁竞争 | 热点为 lock/mutex/spinlock |
| `IO_Wait_Dominant` | IO 等待主导 | io_schedule 高频 |

---

### [CORRELATION_FLAGS]

*跨维度关联检测，自动标记系统性问题*

```markdown
[FLAG: GLOBAL_LOCK_CONTENTION] : `_raw_spin_lock` usage exceeds 40% of sys time.
[FLAG: SINGLE_CORE_SATURATION] : Core_4 utilization 98.5%, Monopoly 0.96
[FLAG: THROTTLE_VICTIM]        : `app_B` throttled 82.5% of observation window
[FLAG: STORM_PATTERN]          : `lsof` spawn rate 450/s, PID count 2000+
```

**Flag 生成规则**:

| Flag | 检测条件 | 来源数据 |
|------|----------|----------|
| `GLOBAL_LOCK_CONTENTION` | 全局锁符号 inclusive% > 40% | `get-hotspots` |
| `SINGLE_CORE_SATURATION` | 单核利用率 > 90% 且 Monopoly > 0.8 | `analyze-core-distribution` |
| `THROTTLE_VICTIM` | Throttle_Rate > 50% | Core 层 + cgroup 分析 |
| `STORM_PATTERN` | Spawn_Rate > 100/s 或 PID_Count > 1000 | `get-comm-top` |
| `KERNEL_HEAVY` | 内核态占比 > 50% | `get-hotspots` |
| `UNBALANCED_LOAD` | CV > 1.5 且 Monopoly < 0.5 | `get-comm-top` |

---

### [DATA_SUMMARY]

*诊断会话元数据摘要*

```yaml
total_pids: 2421
total_sys_cpu: 165.2
top_bottleneck: "_raw_spin_lock, cgroup_try_mem_free, futex_wait"
duration_sec: 60.0
sample_count: 31500
data_quality: "good"
```

**字段来源**:

| 字段 | 来源 | 说明 |
|------|------|------|
| total_pids | Core 层 | 采样期间出现的唯一 PID 数 |
| total_sys_cpu | Core 层 | 系统总 CPU 利用率(%) |
| top_bottleneck | 聚合结果 | 排名前三的热点符号 |
| duration_sec | Core 层 | 采样持续时间 |
| sample_count | Core 层 | 总样本数 |
| data_quality | OutputBuilder | 数据质量评估 |

---

## 数据结构定义

### BottleneckAnalyzeResult (Composite 层)

```python
@dataclass
class EntityDistribution:
    """实体分布矩阵行"""
    comm: str
    count: int                      # PID 数量
    incl_saliency: float            # Inclusive 显著度
    excl_saliency: float            # Exclusive 显著度
    core_affinity: str              # Fixed/Uniform/Scattered
    throttle_rate: float            # 节流比例


@dataclass
class CallPathCluster:
    """调用路径聚类"""
    cluster_id: str
    comm: str
    weight: float                   # 占比
    path: List[str]                 # 调用链符号列表
    hotspot: str                    # 汇聚热点
    characteristic: str             # 路径特征标签


@dataclass
class CorrelationFlag:
    """关联标志"""
    flag_type: str                  # GLOBAL_LOCK_CONTENTION, etc.
    target: str                     # 目标符号/进程
    message: str                    # 描述信息
    severity: str                   # critical/warning/info


@dataclass
class BottleneckAnalyzeResult:
    """bottleneck-analyze 完整输出"""
    
    # 风险信息（置顶）
    _risk: RiskInfo
    
    # 实体分布矩阵
    entity_distribution: List[EntityDistribution]
    
    # 收敛追踪
    common_hotspot: str
    common_hotspot_weight: float
    clusters: List[CallPathCluster]
    
    # 关联标志
    correlation_flags: List[CorrelationFlag]
    
    # 数据摘要
    total_pids: int
    total_sys_cpu: float
    top_bottlenecks: List[str]
    duration_sec: float
    sample_count: int
    
    # 时间范围
    time_range: TimeRange
```

---

## 使用示例

### 基础用法

```bash
# 自动检测并分析瓶颈进程
shecr bottleneck-analyze --auto-detect

# 分析指定进程
shecr bottleneck-analyze --comm app_B

# 分析指定 PID
shecr bottleneck-analyze --pid 1234

# 时间范围限定
shecr bottleneck-analyze --comm app_B --start-time "2026-03-01T10:00:00" --end-time "2026-03-01T10:05:00"
```

### 高级用法

```bash
# 调整热点分析数量
shecr bottleneck-analyze --comm app_B --hotspots-limit 30

# 调整调用链深度
shecr bottleneck-analyze --comm app_B --callers-limit 20 --max-depth 10

# 详细输出（包含中间指标）
shecr bottleneck-analyze --comm app_B --verbose
```

---

## 与其他工具的关系

```
sys-audit (入口)
    │
    ├──▶ 发现瓶颈进程 app_B
    │
    ▼
bottleneck-analyze --comm app_B (深度分析)
    │
    ├──▶ 热点: _raw_spin_lock
    │
    ├──▶ find-callers --target _raw_spin_lock --comm app_B
    │
    └──▶ cluster-paths --comm app_B
```

| 场景 | 推荐工具 | 说明 |
|------|----------|------|
| 不知道从何入手 | `sys-audit` | 全景扫描，自动识别瓶颈 |
| 已知瓶颈进程 | `bottleneck-analyze` | 深度分析，调用链追踪 |
| 已知热点函数 | `find-callers` | 精确溯源 |
| 业务逻辑分析 | `cluster-paths` | 调用模式识别 |

---

## 接口调用关系

```python
# Composite 层: BottleneckAnalyzer.analyze()
def analyze(self, samples, target_comm=None):
    
    # Phase 1: 预处理
    comm_top = self._facade.analyze_comm_top(samples)
    core_dist = self._facade.analyze_core_distribution(samples)
    busy_cores = [c.cpu_id for c in core_dist.saturated_cores]
    
    # Phase 2: 热点分析
    hotspots = self._facade.analyze_hotspots(
        samples, 
        comm=target_comm, 
        sort_by="self"
    )
    
    # Phase 3: 调用链分析 (Bottom-Up)
    for hotspot in hotspots.hotspots[:top_n]:
        callers = self._facade.analyze_callers(
            samples,
            target_symbol=hotspot.symbol,
            comm=target_comm,
            sort_by="inclusive"
        )
    
    # Phase 3: 路径聚类 (Top-Down)
    clusters = self._facade.cluster_paths(
        samples,
        comm=target_comm,
        sort_by="inclusive"
    )
    
    # Phase 4: 聚合输出
    return self._aggregate_results(
        comm_top, core_dist, hotspots, 
        callers_list, clusters
    )
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-03 | 初始版本，定义完整分析流程和输出格式 |

---

## 相关文档

- [Composite Layer 接口](interface-composite.md) - BottleneckAnalyzer 类定义
- [Analysis Layer 接口](interface-analysis.md) - Facade 接口说明
- [Core Layer 接口](interface-core.md) - Engine 数据接口
- [分析方法论](../references/methodology.md) - SHECR 方法论
- [工具命令参考](../references/tools.md) - CLI 参数速查
