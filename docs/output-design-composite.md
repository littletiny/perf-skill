# Composite 层工具输出设计文档

> 基于 design-attention-steering.md 和 example_output.txt 设计
> 版本: 1.0
> 更新日期: 2026-03-03

---

## 设计原则

### 1. SHECR Attention Flags 集成

根据 `design-attention-steering.md`，输出必须嵌入注意力引导标签：

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<X0>` | Critical（阻塞级） | 锁竞争、单核饱和、高内核态，必须追踪到根因 |
| `<X1>` | Major（重要级） | 进程风暴、负载不均衡 |
| `<X2>` | Minor（提示级） | 一般提示信息 |
| `<XA>` | Action（操作建议） | 具体的下一步操作 |

### 2. Risk 置顶原则

所有输出必须包含 `_risk` 字段，放在最前面：

```json
{
  "_risk": {
    "level": "critical",
    "message": "<X0> 检测到单核饱和 (CPU5 利用率 95%)",
    "hint": "<XA> 执行 bottleneck-trace --comm worker",
    "patterns": ["SINGLE_CORE_SATURATION"],
    "pending_targets": ["worker"],
    "action_required": true
  },
  ...
}
```

### 3. 输出格式规范

- **扁平结构**: JSON 嵌套不超过 2 层
- **时间格式**: ISO 8601 字符串
- **简单列表**: 避免多级 children 嵌套
- **数值原始**: 百分比存 0.15 而不是 "15%"

---

## bottleneck-trace 输出设计

### 设计目标

通过多维度聚合分析，定位并解释 CPU 瓶颈根因：
1. **实体分布矩阵** - 进程维度的资源消耗全景
2. **收敛追踪** - Bottom-Up + Top-Down 双视角调用链分析
3. **关联标志** - 跨维度系统性问题检测
4. **数据摘要** - 诊断会话元数据

### 文本输出格式

```
## [BOTTLENECK_TRACE]
> 策略: 多维度聚合分析，揭示瓶颈完整上下文

[X0] 发现关键瓶颈: app_B (Monopoly=0.96, Throttle=82.5%)
  → hint: 查看 [CONVERGENCE_TRACE] 中的调用链分析

### [ENTITY_DISTRIBUTION_MATRIX]
> 基于分布熵判定核心亲缘性模式

| Comm_Group | Count | Incl_Saliency | Excl_Saliency | Core_Affinity      | Throttle_Rate |
|------------|-------|---------------|---------------|--------------------|---------------|
| app_B      | 1     | 0.96          | 0.12          | Fixed: [Core_4]    | 82.5%         |
| lsof       | 2000  | 0.45          | 0.88          | Uniform: [Core_0-255] | 5.2%       |
| others     | 420   | 0.02          | 0.01          | Scattered          | 0.0%          |

Core_Affinity 判定:
  - Fixed:    Entropy < 0.3, Monopoly > 0.8 (单核心绑定)
  - Uniform:  Entropy > 2.0, CV < 0.5 (均匀分布)
  - Scattered: 其他情况 (分散无规律)

### [CONVERGENCE_TRACE]
> 模糊匹配聚合 Top-Down 与 Bottom-Up 视角

[X0] COMMON_HOTSPOT: _raw_spin_lock (72.4%)
  所有聚类共享的热点符号，瓶颈汇聚点

--- [Cluster: lsof 68%] ---
Path: lsof → vfs_read → iterate_dir → __d_lookup_rcu → [HOTSPOT]
  Characteristic: High_Frequency_Exclusive_CPU
  Weight: 68% (占总样本比例)
  来源: cluster-paths 聚类结果

--- [Cluster: appB single/serval 28%] ---
Path: app_B → handle_request → write_log → __cfs_rq_runtime_get → [HOTSPOT]
  Characteristic: Inclusive_Latency_Victim (Blocked on quota/lock)
  Weight: 28% (占总样本比例)
  来源: find-callers + cluster-paths 匹配

Path_Characteristic 标签:
  - High_Frequency_Exclusive_CPU: Self% >> Inclusive% (高频独占)
  - Inclusive_Latency_Victim: 等待资源/锁 (延迟受害者)
  - Syscall_Bound: 内核态占比 > 50%
  - Lock_Contention: 热点为 lock/mutex/spinlock
  - IO_Wait_Dominant: io_schedule 高频

### [CORRELATION_FLAGS]
> 跨维度关联检测，标记系统性问题

[X0] GLOBAL_LOCK_CONTENTION: _raw_spin_lock usage exceeds 40% of sys time
[X0] SINGLE_CORE_SATURATION: Core_4 utilization 98.5%, Monopoly 0.96
[X0] THROTTLE_VICTIM: app_B throttled 82.5% of observation window
[X1] STORM_PATTERN: lsof spawn rate 450/s, PID count 2000+

Flag 生成规则:
  - GLOBAL_LOCK_CONTENTION: 全局锁符号 inclusive% > 40%
  - SINGLE_CORE_SATURATION: 单核利用率 > 90% 且 Monopoly > 0.8
  - THROTTLE_VICTIM: Throttle_Rate > 50%
  - STORM_PATTERN: Spawn_Rate > 100/s 或 PID_Count > 1000
  - KERNEL_HEAVY: 内核态占比 > 50%
  - UNBALANCED_LOAD: CV > 1.5 且 Monopoly < 0.5

### [DATA_SUMMARY]

total_pids: 2421
total_sys_cpu: 165.2%
top_bottleneck: "_raw_spin_lock, cgroup_try_mem_free, futex_wait"
duration_sec: 60.0
sample_count: 31500
data_quality: "good"
```

### JSON 输出格式

```json
{
  "_risk": {
    "level": "critical",
    "message": "<X0> 发现关键瓶颈: app_B (Monopoly=0.96, Throttle=82.5%)",
    "hint": "<XA> 查看 [CONVERGENCE_TRACE] 中的调用链分析",
    "patterns": ["BOTTLENECK_CONFIRMED", "THROTTLE_VICTIM"],
    "action_required": true
  },
  "entity_distribution": [
    {
      "comm": "app_B",
      "count": 1,
      "incl_saliency": 0.96,
      "excl_saliency": 0.12,
      "core_affinity": "Fixed: [Core_4]",
      "throttle_rate": 0.825
    },
    {
      "comm": "lsof",
      "count": 2000,
      "incl_saliency": 0.45,
      "excl_saliency": 0.88,
      "core_affinity": "Uniform: [Core_0-255]",
      "throttle_rate": 0.052
    }
  ],
  "common_hotspot": "_raw_spin_lock",
  "common_hotspot_weight": 0.724,
  "clusters": [
    {
      "cluster_id": "lsof_cluster_68",
      "comm": "lsof",
      "weight": 0.68,
      "path": ["lsof", "vfs_read", "iterate_dir", "__d_lookup_rcu"],
      "hotspot": "_raw_spin_lock",
      "characteristic": "High_Frequency_Exclusive_CPU"
    },
    {
      "cluster_id": "appB_single_28",
      "comm": "app_B",
      "weight": 0.28,
      "path": ["app_B", "handle_request", "write_log", "__cfs_rq_runtime_get"],
      "hotspot": "_raw_spin_lock",
      "characteristic": "Inclusive_Latency_Victim"
    }
  ],
  "correlation_flags": [
    {
      "flag_type": "GLOBAL_LOCK_CONTENTION",
      "target": "_raw_spin_lock",
      "message": "_raw_spin_lock usage exceeds 40% of sys time",
      "severity": "critical"
    },
    {
      "flag_type": "THROTTLE_VICTIM",
      "target": "app_B",
      "message": "app_B throttled 82.5% of observation window",
      "severity": "critical"
    }
  ],
  "total_pids": 2421,
  "total_sys_cpu": 165.2,
  "top_bottlenecks": ["_raw_spin_lock", "cgroup_try_mem_free", "futex_wait"],
  "duration_sec": 60.0,
  "sample_count": 31500,
  "time_range": {
    "start_time": "2026-03-02T10:30:00+08:00",
    "end_time": "2026-03-02T10:35:00+08:00"
  }
}
```

### 数据结构定义

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
class BottleneckTraceResult:
    """bottleneck-trace 完整输出"""
    _risk: RiskItem                 # 风险信息（置顶）
    entity_distribution: List[EntityDistribution]
    common_hotspot: str
    common_hotspot_weight: float
    clusters: List[CallPathCluster]
    correlation_flags: List[CorrelationFlag]
    total_pids: int
    total_sys_cpu: float
    top_bottlenecks: List[str]
    duration_sec: float
    sample_count: int
    time_range: TimeRange
```

### Flag 与标签映射

| Flag | 触发条件 | Severity | Attention Flag |
|------|----------|----------|----------------|
| GLOBAL_LOCK_CONTENTION | 全局锁 inclusive% > 40% | critical | `<X0>` |
| SINGLE_CORE_SATURATION | 单核利用率 > 90% 且 Monopoly > 0.8 | critical | `<X0>` |
| THROTTLE_VICTIM | Throttle_Rate > 50% | critical | `<X0>` |
| STORM_PATTERN | Spawn_Rate > 100/s 或 PID_Count > 1000 | warning | `<X1>` |
| KERNEL_HEAVY | 内核态占比 > 50% | warning | `<X1>` |
| UNBALANCED_LOAD | CV > 1.5 且 Monopoly < 0.5 | info | `<X2>` |

📘 **详细规范**: [`docs/tool-bottleneck-trace.md`](tool-bottleneck-trace.md) - 完整分析流程和接口关系

---

## sys-audit 输出设计

### 设计目标

系统级全景扫描，自动识别真正的瓶颈（解决"A掩盖B"问题）：
1. **系统指纹** - 整体压力状态、PSI 指标
2. **竞争矩阵** - 资源需求 vs 限制分析
3. **专家锚点** - 自动识别的关键发现

### 文本输出格式

```
## [SYSTEM_AUDIT]
> 策略: 自动降噪 + 危害排序，识别真瓶颈

<X0> 发现 2 个关键性能瓶颈: kubelet, logcollector
  → hint: bottleneck-trace --comm kubelet; bottleneck-trace --comm logcollector

### 系统指纹 (System Fingerprint)

State: CRITICAL_CONTENTION
┌─────────────────┬────────┬────────┬────────┐
│ PSI             │ CPU    │ Memory │ IO     │
├─────────────────┼────────┼────────┼────────┤
│ some            │ 0.92   │ -      │ 0.12   │
│ full            │ 0.45   │ -      │ -      │
└─────────────────┴────────┴────────┴────────┘

Throttle Events: 1250
Context Switch: EXTREME

### 竞争矩阵 (Contention Matrix)

<X0> CPU_QUOTA 竞争:
  - Demand: 260% | Limit: 200% | Gap: -60%
  - <X0> Primary Contenders: lsof_scanner, app_B_logic

<X1> Memory 压力:
  - Reclaim Rate: 150MB/s
  - Page Fault: 5000/s

### 进程分层 (Process Hierarchy)

<X0> Primary Suspect (真瓶颈):
  ├─ Comm: kubelet
  ├─ CPU: 54.73%
  ├─ Diagnosis: BOTTLENECK
  ├─ Monopoly: 1.00  (<X0> 单核饱和)
  └─ Impact Score: 0.95

<X1> Secondary Loads (次要负载):
  ├─ netstat: 288.26% (STORM: 59.3/s) - 进程风暴
  ├─ dbatman: 200.69% (STORM: 34.7/s) - 进程风暴  
  └─ hacontrol: 218.93% (STORM: 20.4/s) - 进程风暴

Background Noise (背景噪音):
  └─ others (152 procs): 8.4% (已折叠)

### 核心分布 (Core Distribution)

<X1> 负载不均衡:
  - Imbalance Level: MODERATE
  - Saturated Cores: 3, 5, 7
  
Top Saturated:
  #1 CPU 3: 18522.36% (usr: 12909.53%)
  #2 CPU 5: 1122.57% (usr: 1122.57%)
  #3 CPU 7: 561.28% (usr: 561.28%)

### 异常检测 (Anomaly Detection)

(未检测到异常突变)

### 专家锚点 (Expert Anchors)

<X0> !! DETECTED_NOISY_NEIGHBOR: lsof_scanner !!
  - 2000 个进程高频扫描 /proc
  - 触发系统级锁竞争
  - 影响其他正常业务进程

<X0> !! DETECTED_QUOTA_VICTIM: app_B_logic !!
  - 被 Cgroup CPU 限制阻塞
  - 业务逻辑健康但执行被暂停
  - 建议: 调整 CPU quota 或优化 noisy neighbor

### 根因链 (Root Cause Chain)

<X0> 第一推动力: lsof_scanner 进程风暴
  ├─ 现象: 2000 个 lsof 进程汇聚在 _raw_spin_lock
  ├─ 影响: CPU  quota 耗尽，app_B_logic 被节流
  ├─ 受害者: app_B_logic (业务关键路径)
  └─ 建议: 限制 lsof 并发或改用事件驱动监控

<XA> 后续操作:
  1. bottleneck-trace --comm lsof_scanner 深度分析
  2. 检查监控脚本为何创建大量 lsof 进程
  3. 考虑调整 Cgroup CPU limit 或隔离 noisy neighbor
```

### JSON 输出格式

```json
{
  "_risk": {
    "level": "critical",
    "message": "<X0> 发现 2 个关键性能瓶颈: kubelet, logcollector",
    "hint": "<XA> 执行 bottleneck-trace --comm kubelet",
    "patterns": ["BOTTLENECK_DETECTED", "PROCESS_STORM"],
    "pending_targets": ["kubelet", "logcollector", "netstat"],
    "action_required": true
  },
  "system_fingerprint": {
    "pressure_state": "CRITICAL_CONTENTION",
    "global_psi": {
      "cpu_some": 0.92,
      "cpu_full": 0.45,
      "io_some": 0.12
    },
    "total_throttle_events": 1250,
    "context_switch_rate": "EXTREME"
  },
  "contention_matrix": [
    {
      "dimension": "CPU_QUOTA",
      "demand_sum": 2.6,
      "limit": 2.0,
      "gap": -0.6,
      "attention_flag": "<X0>",
      "primary_contenders": ["lsof_scanner", "app_B_logic"]
    },
    {
      "dimension": "MEMORY",
      "reclaim_rate_mbps": 150,
      "page_fault_rate": 5000,
      "attention_flag": "<X1>"
    }
  ],
  "process_hierarchy": {
    "primary_suspect": {
      "comm": "kubelet",
      "total_cpu": 54.73,
      "diagnosis": "BOTTLENECK",
      "monopoly": 1.0,
      "impact_score": 0.95,
      "attention_flag": "<X0>"
    },
    "secondary_loads": [
      {
        "comm": "netstat",
        "total_cpu": 288.26,
        "diagnosis": "STORM",
        "spawn_rate": 59.3,
        "attention_flag": "<X1>"
      },
      {
        "comm": "dbatman",
        "total_cpu": 200.69,
        "diagnosis": "STORM",
        "spawn_rate": 34.7,
        "attention_flag": "<X1>"
      }
    ],
    "background_noise": {
      "count": 152,
      "total_cpu": 8.4,
      "folded": true
    }
  },
  "core_distribution": {
    "imbalance_level": "MODERATE",
    "saturated_cores": [3, 5, 7],
    "attention_flag": "<X1>",
    "top_saturated": [
      {"cpu_id": 3, "total_util": 18522.36, "kernel_util": 12909.53},
      {"cpu_id": 5, "total_util": 1122.57, "kernel_util": 1122.57},
      {"cpu_id": 7, "total_util": 561.28, "kernel_util": 561.28}
    ]
  },
  "anomaly_detection": {
    "mutation_detected": false,
    "anomalies_count": 0
  },
  "expert_anchors": [
    {
      "type": "NOISY_NEIGHBOR",
      "target": "lsof_scanner",
      "description": "2000 个进程高频扫描 /proc，触发系统级锁竞争",
      "impact": "影响其他正常业务进程",
      "attention_flag": "<X0>"
    },
    {
      "type": "QUOTA_VICTIM",
      "target": "app_B_logic",
      "description": "被 Cgroup CPU 限制阻塞，业务逻辑健康但执行被暂停",
      "recommendation": "调整 CPU quota 或优化 noisy neighbor",
      "attention_flag": "<X0>"
    }
  ],
  "root_cause_chain": {
    "primary_driver": "lsof_scanner 进程风暴",
    "phenomenon": "2000 个 lsof 进程汇聚在 _raw_spin_lock",
    "impact": "CPU quota 耗尽，app_B_logic 被节流",
    "victim": "app_B_logic (业务关键路径)",
    "recommendation": "限制 lsof 并发或改用事件驱动监控",
    "attention_flag": "<X0>"
  },
  "recommendations": [
    "<XA> bottleneck-trace --comm lsof_scanner 深度分析",
    "<XA> 检查监控脚本为何创建大量 lsof 进程",
    "考虑调整 Cgroup CPU limit 或隔离 noisy neighbor"
  ],
  "time_range": {
    "start": "2026-03-02T10:30:00+08:00",
    "end": "2026-03-02T10:35:00+08:00"
  }
}
```

### 触发条件与标签映射

| 场景 | 触发条件 | Risk Level | Attention Flag | Patterns |
|------|----------|------------|----------------|----------|
| 发现瓶颈 | 存在 BOTTLENECK 诊断 | critical | `<X0>` | BOTTLENECK_DETECTED |
| 进程风暴 | Spawn Rate > 10/s | warning | `<X1>` | PROCESS_STORM |
| CPU 竞争 | Demand > Limit | critical | `<X0>` | CPU_CONTENTION |
| Noisy Neighbor | 高 Count 进程影响其他 | critical | `<X0>` | NOISY_NEIGHBOR |
| Quota Victim | 被 Cgroup 限制的健康进程 | warning | `<X1>` | QUOTA_VICTIM |

---

## 实现指南

### 1. 修改 TextOutputAdapter

在 `text_output_adapter.py` 中更新 `_render_bottleneck_trace` 和 `_render_sys_audit` 方法：

```python
def _render_bottleneck_trace(self, data: Any) -> List[str]:
    """渲染瓶颈追踪结果 - 新格式"""
    # 实现新的输出格式
    ...

def _render_sys_audit(self, data: Any) -> List[str]:
    """渲染系统审计结果 - 新格式"""
    # 实现新的输出格式
    ...
```

### 2. 更新 Output Models

确保 `BottleneckTraceOutput` 和 `SysAuditOutput` 包含所有必要字段。

### 3. Risk 信息构建

在命令实现中使用 `X0`/`X1`/`XA` 标签：

```python
risk = RiskInfo(
    level="critical",
    message="<X0> 单核饱和 (Monopoly=1.00)",
    hint="<XA> 执行 find-callers --target __lock_text_start",
    patterns=["SINGLE_CORE_SATURATION"],
    pending_targets=[target_comm]
)
```

---

## 与 example_output.txt 的对比

| 方面 | example_output.txt | 新设计 |
|------|-------------------|--------|
| 风险标记 | `!! DETECTED_NOISY_NEIGHBOR !!` | `<X0> !! DETECTED_NOISY_NEIGHBOR` |
| 建议操作 | 单独的 `expert_anchors` | 嵌入 `<XA>` 标签 |
| 层级结构 | `Primary Suspect` / `Secondary Loads` | 统一的 `Process Hierarchy` |
| 根因分析 | `root_cause_analysis` 字符串 | 结构化的 `root_cause_chain` |
| 输出格式 | 混合 JSON/文本 | 统一支持文本+JSON |

---

## 核心指标计算逻辑

### 1. Monopoly (核心独占率)

**用途**: 识别单进程是否垄断该 comm 的 CPU 资源，检测单核瓶颈。

**计算公式**:
```
Monopoly = max(PID_cpu) / sum(all_PID_cpu)
```

**参数说明**:
- `PID_cpu`: 单个 PID 的 CPU 利用率 (%)
- `max(PID_cpu)`: 该 comm 下 CPU 利用率最高的 PID
- `sum(all_PID_cpu)`: 该 comm 下所有 PID 的 CPU 利用率之和

**阈值定义** (CommTopAnalyzer):
```python
MONOPOLY_THRESHOLD = 0.8   # Monopoly > 0.8 认为单点瓶颈
SIGNIFICANT_MONOPOLY_THRESHOLD = 0.8  # 自动降噪阈值
```

**诊断分级**:
| Monopoly 值 | 诊断 | 说明 |
|-------------|------|------|
| > 0.8 | BOTTLENECK | 单进程独占大部分 CPU，典型单核瓶颈 |
| ≤ 0.8 | - | 需结合 CV、SpawnRate 进一步判断 |

**示例**:
```
comm = "kubelet"
  PID 1001: CPU = 50%  (唯一进程)
  Monopoly = 50 / 50 = 1.0  →  BOTTLENECK

comm = "netstat"
  PID 2001: CPU = 5%
  PID 2002: CPU = 3%
  ... (2000 个进程)
  Monopoly = 5 / (5+3+...) ≈ 0.002  →  非单点瓶颈，可能是 STORM
```

---

### 2. CV (变异系数)

**用途**: 检测 PID 间的负载不均衡程度。

**计算公式**:
```
CV = σ / μ

其中:
  μ = sum(all_PID_cpu) / PID_count    # 平均 CPU
  σ = sqrt(sum((PID_cpu - μ)²) / PID_count)  # 标准差
```

**阈值定义** (CommTopAnalyzer):
```python
CV_THRESHOLD = 1.0              # CV > 1.0 认为不均衡
SIGNIFICANT_CV_THRESHOLD = 1.0  # 自动降噪阈值
```

**诊断分级**:
| CV 值 | 含义 | 说明 |
|-------|------|------|
| > 1.0 | UNBALANCED | PID 间负载严重不均衡 |
| ≤ 1.0 | - | 负载相对均衡 |

**示例**:
```
场景 A: 4 个 worker 进程均衡负载
  PID 1-4: CPU = 25%, 24%, 26%, 25%
  μ = 25, σ ≈ 0.7, CV ≈ 0.03  →  均衡

场景 B: 1 个主进程 + 3 个空闲进程
  PID 1-4: CPU = 95%, 1%, 2%, 2%
  μ = 25, σ ≈ 41, CV ≈ 1.64  →  UNBALANCED
```

---

### 3. Spawn Rate (进程产生速率)

**用途**: 检测进程风暴（短时间内大量进程创建）。

**计算公式**:
```
Spawn Rate = unique_PID_count / duration

其中:
  unique_PID_count: 时间窗口内出现的不同 PID 数量
  duration: 采样时间窗口（秒）
```

**阈值定义** (CommTopAnalyzer):
```python
SPAWN_RATE_THRESHOLD = 10.0              # > 10/s 认为进程风暴
SIGNIFICANT_SPAWN_RATE_THRESHOLD = 10.0  # 自动降噪阈值
```

**风暴严重程度分级**:
```python
if spawn_rate > 100: severity = "CRITICAL"
elif spawn_rate > 50: severity = "HIGH"
elif spawn_rate > 20: severity = "MEDIUM"
else: severity = "LOW"
```

**诊断分级**:
| Spawn Rate | 诊断 | 说明 |
|------------|------|------|
| > 10/s | STORM | 进程风暴，频繁创建销毁 |
| ≤ 10/s | - | 正常进程创建频率 |

**示例**:
```
监控脚本异常: 每秒创建 50 个 lsof 进程
  duration = 30s
  unique_PID_count = 1500
  Spawn Rate = 1500 / 30 = 50/s  →  STORM (HIGH)

正常服务: 常驻进程
  duration = 60s
  unique_PID_count = 4
  Spawn Rate = 4 / 60 ≈ 0.07/s  →  正常
```

---

### 4. Impact Score (危害指数)

**用途**: 综合排序指标，解决"A掩盖B"问题（高 Count 进程掩盖真瓶颈）。

**计算公式**:
```
Impact Score = CPU*0.3 + CV*40 + Monopoly*50 + SpawnRate*5

权重设计原理:
  - CPU * 0.3:    绝对 CPU 利用率权重较低（背景负载可能很高但不是瓶颈）
  - CV * 40:      不均衡度权重高（不均衡意味着调度问题）
  - Monopoly * 50: 独占率权重最高（单点瓶颈是首要问题）
  - SpawnRate * 5: 进程风暴权重中等（风暴通常伴随其他问题）
```

**排序策略**:
```python
groups.sort(key=lambda x: x.impact_score, reverse=True)
```

**示例**:
```
场景对比:
  
进程 A: 100 个 nginx worker
  CPU=500%, CV=0.1, Monopoly=0.02, SpawnRate=0
  Impact Score = 500*0.3 + 0.1*40 + 0.02*50 + 0*5 = 154
  → 高 CPU 但均衡，可能是正常负载

进程 B: 1 个 kubelet
  CPU=50%, CV=0, Monopoly=1.0, SpawnRate=0
  Impact Score = 50*0.3 + 0*40 + 1.0*50 + 0*5 = 65
  → 相对低 CPU 但 Monopoly 极高，真瓶颈

进程 C: 2000 个 lsof
  CPU=300%, CV=2.0, Monopoly=0.002, SpawnRate=60
  Impact Score = 300*0.3 + 2.0*40 + 0.002*50 + 60*5 = 478
  → 综合危害最高，需要优先处理
```

---

### 5. Core Distribution (核心分布不均衡度)

**用途**: 检测系统级 CPU 负载不均衡。

**计算公式**:
```
Imbalance Ratio = max(core_util) / avg(core_util)

其中:
  max(core_util): 利用率最高的核心
  avg(core_util): 所有核心的平均利用率
```

**阈值定义** (CoreDistAnalyzer):
```python
IMBALANCE_CRITICAL = 10.0   # 极不均衡 (max/avg > 10)
IMBALANCE_HIGH = 5.0        # 严重不均衡 (max/avg > 5)
IMBALANCE_MEDIUM = 2.0      # 中度不均衡 (max/avg > 2)
SATURATION_THRESHOLD = 90.0  # 核心饱和阈值
```

**不均衡分级**:
| 条件 | 分级 | 说明 |
|------|------|------|
| ratio > 10 且 max > 50% | CRITICAL | 单核满载，其他核心空闲 |
| ratio > 5 | HIGH | 严重不均衡 |
| ratio > 2 | MEDIUM | 中度不均衡 |
| ratio ≤ 2 | LOW | 相对均衡 |

**饱和核心识别**:
```python
saturated_cores = [c for c in cores if c.total_cpu > 90.0]
```

**示例**:
```
8 核系统负载分布:
  CPU 0: 95% (满载)
  CPU 1-7: 5% each (空闲)
  
  max = 95, avg = (95 + 5*7) / 8 = 16.25
  Imbalance Ratio = 95 / 16.25 ≈ 5.8  →  HIGH
  
  同时 CPU 0 > 90%  →  单核饱和风险
```

---

### 6. 诊断分级逻辑

**综合诊断流程** (CommTopAnalyzer._classify):
```python
def _classify(cv, monopoly, spawn_rate):
    if monopoly > 0.8:
        return "BOTTLENECK"     # 单进程瓶颈优先
    elif spawn_rate > 10.0:
        return "STORM"          # 进程风暴次之
    elif cv > 1.0:
        return "UNBALANCED"     # 负载不均衡
    else:
        return "HEALTHY"        # 健康状态
```

**优先级规则**:
1. **Monopoly > 0.8** → BOTTLENECK（单核独占是首要问题）
2. **Spawn Rate > 10/s** → STORM（进程风暴可能导致系统不稳定）
3. **CV > 1.0** → UNBALANCED（负载调度问题）
4. **其他** → HEALTHY

---

### 7. 自动降噪逻辑

**显著性判断** (CommTopAnalyzer._auto_filter):
```python
is_significant = (
    total_cpu > 5.0 or        # CPU 总量 > 5%
    cv > 1.0 or               # 分布严重不均
    monopoly > 0.8 or         # 单点极端离群
    spawn_rate > 10.0         # 进程风暴
)
```

**降噪策略**:
- **Display Groups**: 满足任一显著性条件的进程组（值得关注）
- **Folded Groups**: 不满足任何条件的进程组（背景噪音，折叠显示）

**目的**: 避免大量低 CPU 进程淹没真正的瓶颈信号。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-03 | 初始设计，基于 design-attention-steering.md 和 example_output.txt |
| 1.1 | 2026-03-03 | 补充核心指标计算逻辑 (Monopoly, CV, SpawnRate, ImpactScore, CoreDistribution) |
