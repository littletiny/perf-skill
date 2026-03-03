# Output System 设计文档

> 统一输出格式设计规范，涵盖数据结构、工具输出格式、核心指标计算
> 
> 合并来源: output-format-spec.md + output-system.md + output-design-composite.md
> 版本: 3.0
> 更新日期: 2026-03-04

---

## 设计原则

### Risk 置顶原则
- 所有输出必须包含 `_risk` 字段，放在 JSON 最前面
- 风险信息简洁明确，包含建议操作
- 当 `_risk.action_required=true` 时，**必须**将问题添加到 Trace

```bash
# 任何返回 action_required=true 的 tool 输出，必须执行：
shecr trace add --desc "<_risk.message>" \
  --risk "<_risk.level>" --hint "<_risk.hint>"
```

### 扁平结构原则
- JSON 嵌套不超过 2 层
- 优先使用简单列表而非嵌套对象
- 列表项使用平面对象，避免多级 children 嵌套

### 时间格式原则
- 所有时间字段使用 **ISO 8601 格式字符串**
- 禁止使用 Unix 时间戳数字
- 时区信息可选，但必须统一

### 数值原始原则
- 百分比存储为原始数字（如 0.15 表示 15%），格式化交给渲染层
- 时间存储为时间戳或 ISO 字符串，避免自定义格式

### SHECR Attention Flags

输出必须嵌入注意力引导标签：

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<X0>` | Critical（阻塞级） | 锁竞争、单核饱和、高内核态，必须追踪到根因 |
| `<X1>` | Major（重要级） | 进程风暴、负载不均衡 |
| `<X2>` | Minor（提示级） | 一般提示信息 |
| `<XA>` | Action（操作建议） | 具体的下一步操作 |

---

## 核心数据结构

### RiskInfo - 风险信息

所有输出的第一个字段，遵循统一规范：

```python
from perf_toolkit.core import RiskInfo

risk = RiskInfo(
    level="warning",              # "critical" | "warning" | "info" | "none"
    message="发现性能瓶颈",        # 简短描述
    hint="执行: bottleneck-trace --comm xxx",  # 建议操作
    patterns=["BOTTLENECK"],      # 检测到的模式
    pending_targets=["xxx"],      # 待处理目标
    action_required=True          # 是否需要处理
)
```

**Level 定义**:

| Level | 条件 | Agent 响应 |
|-------|------|-----------|
| `critical` | 严重问题，诊断可能不完整 | 立即处理，禁止收敛 |
| `warning` | 潜在问题，建议处理 | 优先处理，记录风险 |
| `info` | 值得关注的信息 | 了解即可 |
| `none` | 无风险 | 继续正常流程 |

### TimeRange - 时间范围

```python
from perf_toolkit.core import TimeRange

# 从时间戳创建（自动转换为 ISO 8601 格式）
time_range = TimeRange.from_timestamps(start_ts, end_ts)
# 输出: {"start_time": "2026-03-02T10:00:00", "end_time": "2026-03-02T10:30:00", "duration": 1800}
```

### 数据项类型

| 数据类型 | Item 类 | Summary 类 | Output 类 |
|---------|---------|-----------|-----------|
| processes | ProcessItem | ProcessSummary | ProcessTopOutput |
| comm_groups | CommGroupItem | CommGroupSummary | CommTopOutput |
| hotspots | HotspotItem | HotspotSummary | HotspotsOutput |
| symbol_clusters | ClusterItem | ClusterSummary | ClustersOutput |
| anomalies | AnomalyItem | AnomalySummary | AnomaliesOutput |
| path_clusters | PathClusterItem | PathClusterSummary | PathClustersOutput |
| attributions | AttributionItem | AttributionSummary | AttributionsOutput |
| cores | CoreItem | CoreDistributionSummary | CoreDistributionOutput |

---

## 各工具输出格式规范

### 核心分析工具

#### analyze-core-distribution

核心级负载分布分析。

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "单核满载 (CPU 5)",
    "hint": "使用 sys-audit 分析负载分布",
    "patterns": ["SINGLE_CORE_SATURATION"],
    "pending_targets": ["cpu_5"],
    "action_required": true
  },
  "summary": null,
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "cores": [
    {
      "cpu_id": 5,
      "total_cpu_util": "95.20%",
      "kernel_cpu_util": "55.30%"
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `cpu_id` | int | CPU 核心 ID |
| `total_cpu_util` | string | 总 CPU 利用率（带 %） |
| `kernel_cpu_util` | string | 内核态 CPU 利用率（带 %） |

---

#### detect-anomalies

时序异常检测。

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "检测到 3 个 CPU 利用率异常尖峰",
    "hint": "查看异常时间点，分析对应时间段",
    "patterns": ["CPU_SPIKE"],
    "action_required": true
  },
  "summary": {
    "total_anomalies": 5,
    "spike_count": 3,
    "drop_count": 2
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "anomalies": [
    {
      "type": "SPIKE",
      "cpu_id": 5,
      "time_range_start": "2026-03-02T10:15:00",
      "time_range_end": "2026-03-02T10:16:00",
      "prev_util": 0.1,
      "curr_util": 0.85,
      "next_util": 0.15,
      "severity": "high"
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 异常类型: SPIKE/DROP |
| `cpu_id` | int | CPU 核心 ID |
| `time_range_start` | string | 异常开始时间（ISO 8601） |
| `time_range_end` | string | 异常结束时间（ISO 8601） |
| `prev_util` | float | 前一个窗口利用率（0-1） |
| `curr_util` | float | 当前窗口利用率（0-1） |
| `next_util` | float | 后一个窗口利用率（0-1） |
| `severity` | string | 严重程度: high/medium |

---

#### get-comm-top

进程组分析（含 CV/Monopoly/SpawnRate 指标）。

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "app_worker 单核饱和 (Monopoly=0.92)",
    "hint": "bottleneck-trace --comm app_worker",
    "patterns": ["SINGLE_CORE_SATURATION"],
    "pending_targets": ["app_worker"],
    "action_required": true
  },
  "summary": {
    "total_comm_groups": 15,
    "high_kernel_groups": 2
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "comm_groups": [
    {
      "comm": "app_worker",
      "pids": 10,
      "cpu": "12.50%",
      "kernel": "45.20%",
      "event": "BOTTLENECK(M=0.92)"
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `comm` | string | 进程名 |
| `pids` | int | 该进程名下的进程数量 |
| `cpu` | string | 聚合 CPU 利用率（带 %） |
| `kernel` | string | 内核态占比（带 %） |
| `event` | string | 事件描述（诊断标签） |

**event 取值**:
- `BOTTLENECK(M=x.xx)` - 单点瓶颈（Monopoly 高）
- `STORM(x.x/s)` - 进程风暴（Spawn Rate 高）
- `UNBALANCED(CV=x.xx)` - 负载不均衡（CV 高）
- `normal` - 正常状态

**增强指标**（通过 `--include-metrics` 可在 Composite 层获取）:
- `cv` (float): 变异系数，检测负载不均衡
- `monopoly` (float): 核心独占率（0-1），识别单进程瓶颈
- `spawn_rate` (float): 进程产生速率（个/秒），检测进程风暴
- `impact_score` (float): 危害指数，综合排序依据

---

#### get-hotspots

热点函数排名。

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "热点函数 __lock_text_start 内核态占比 45.20%",
    "hint": "find-callers --target __lock_text_start",
    "patterns": ["HIGH_KERNEL_HOTSPOT"],
    "pending_targets": ["__lock_text_start"],
    "action_required": true
  },
  "summary": {
    "total_hotspots": 50,
    "shown_hotspots": 10
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "hotspots": [
    {
      "symbol": "func_name_[k]",
      "self": "15.23%",
      "inclusive": "45.67%"
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 函数名（规范化后的名称） |
| `self` | string | 自消耗 CPU 占比（带 %） |
| `inclusive` | string | 包含调用树的 CPU 占比（带 %） |

---

#### find-callers

调用链溯源。

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "目标函数 'xxx' 几乎无 CPU 活动",
    "hint": "检查目标函数名称是否正确",
    "patterns": ["LOW_TARGET_ACTIVITY"],
    "action_required": true
  },
  "summary": {
    "target": "pthread_mutex_lock",
    "target_cpu_util": "15.50%",
    "total_attributions": 5,
    "shown_attributions": 3
  },
  "attributions": [
    {
      "caller_stack": ["func_a", "func_b", "func_c"],
      "ratio_of_target_pct": "45.67%",
      "cpu_util": "0.00%"
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `caller_stack` | list | 调用链（从直接调用者到上层） |
| `ratio_of_target_pct` | string | 该调用链占总目标的比例（带 %） |
| `cpu_util` | string | CPU 利用率（保留字段） |

---

#### cluster-paths

调用路径聚类。

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "patterns": [],
    "pending_targets": [],
    "action_required": false
  },
  "summary": {
    "total_clusters": 15,
    "shown_clusters": 10,
    "clustered_weight": 85.5
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "path_clusters": [
    {
      "cluster_id": "c_001",
      "path_signature": "main→worker_loop→process_request",
      "weight": 45.67,
      "total_weight": 100.0,
      "duration": 1800
    }
  ]
}
```

**数据项字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `cluster_id` | string | 聚类 ID（如 c_001） |
| `path_signature` | string | 调用路径签名（→ 分隔） |
| `weight` | float | 该聚类的权重（core·s） |
| `total_weight` | float | 总权重 |
| `duration` | float | 时间窗口（秒） |

---

## Composite 层输出设计

### bottleneck-trace

瓶颈深度追踪（Composite 层命令）。通过多维度聚合分析定位 CPU 瓶颈根因。

#### 设计目标

1. **实体分布矩阵** - 进程维度的资源消耗全景
2. **收敛追踪** - Bottom-Up + Top-Down 双视角调用链分析
3. **关联标志** - 跨维度系统性问题检测
4. **数据摘要** - 诊断会话元数据

#### JSON 输出格式

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

#### 数据项说明

| 字段 | 类型 | 说明 | 来源 |
|------|------|------|------|
| `entity_distribution` | List[EntityDistribution] | 实体分布矩阵 | Composite 层聚合 |
| `entity_distribution[].comm` | str | 进程组名称 | get-comm-top |
| `entity_distribution[].count` | int | PID 数量 | get-comm-top |
| `entity_distribution[].incl_saliency` | float | Inclusive CPU 显著度 | get-hotspots |
| `entity_distribution[].excl_saliency` | float | Exclusive (Self) CPU 显著度 | get-hotspots |
| `entity_distribution[].core_affinity` | str | 核心亲缘性模式 | analyze-core-distribution |
| `entity_distribution[].throttle_rate` | float | 节流比例 | Core 层计算 |
| `common_hotspot` | str | 所有聚类共享的热点符号 | Composite 层聚合 |
| `common_hotspot_weight` | float | 共同热点占比 | Composite 层聚合 |
| `clusters` | List[CallPathCluster] | 调用路径聚类列表 | cluster-paths + find-callers |
| `clusters[].cluster_id` | str | 聚类标识 | Composite 层生成 |
| `clusters[].comm` | str | 所属进程 | cluster-paths |
| `clusters[].weight` | float | 占总样本比例 | cluster-paths |
| `clusters[].path` | List[str] | 调用链符号列表 | cluster-paths |
| `clusters[].hotspot` | str | 汇聚热点符号 | cluster-paths |
| `clusters[].characteristic` | str | 路径特征标签 | Composite 层分析 |
| `correlation_flags` | List[CorrelationFlag] | 跨维度关联标志 | Composite 层检测 |
| `correlation_flags[].flag_type` | str | Flag 类型 | Composite 层检测 |
| `correlation_flags[].target` | str | 目标符号/进程 | Composite 层检测 |
| `correlation_flags[].message` | str | 描述信息 | Composite 层生成 |
| `correlation_flags[].severity` | str | 严重程度 | Composite 层判定 |

#### CorrelationFlag 类型

| Flag | 检测条件 | 来源数据 | Severity | Attention Flag |
|------|----------|----------|----------|----------------|
| `GLOBAL_LOCK_CONTENTION` | 全局锁 inclusive% > 40% | get-hotspots | critical | `<X0>` |
| `SINGLE_CORE_SATURATION` | 单核利用率 > 90% 且 Monopoly > 0.8 | analyze-core-distribution | critical | `<X0>` |
| `THROTTLE_VICTIM` | Throttle_Rate > 50% | Core 层 + cgroup 分析 | critical | `<X0>` |
| `STORM_PATTERN` | Spawn_Rate > 100/s 或 PID_Count > 1000 | get-comm-top | warning | `<X1>` |
| `KERNEL_HEAVY` | 内核态占比 > 50% | get-hotspots | warning | `<X1>` |
| `UNBALANCED_LOAD` | CV > 1.5 且 Monopoly < 0.5 | get-comm-top | info | `<X2>` |

#### Path Characteristic 标签

| 标签 | 说明 | 触发条件 |
|------|------|----------|
| `High_Frequency_Exclusive_CPU` | 高频独占 CPU | Self% >> Inclusive% |
| `Inclusive_Latency_Victim` | 包容性延迟受害者 | 等待资源/锁 |
| `Syscall_Bound` | 系统调用密集 | 内核态占比 > 50% |
| `Lock_Contention` | 锁竞争 | 热点为 lock/mutex/spinlock |
| `IO_Wait_Dominant` | IO 等待主导 | io_schedule 高频 |

#### Core Affinity 判定规则

| 模式 | 判定条件 | 说明 |
|------|----------|------|
| Fixed | Entropy < 0.3, Monopoly > 0.8 | 单核心绑定 |
| Uniform | Entropy > 2.0, CV < 0.5 | 均匀分布到多核 |
| Scattered | 其他情况 | 分散无规律 |

---

### sys-audit

系统全景审计（Composite 层命令）。系统级全景扫描，自动识别真正的瓶颈（解决"A掩盖B"问题）。

#### 设计目标

1. **系统指纹** - 整体压力状态、PSI 指标
2. **竞争矩阵** - 资源需求 vs 限制分析
3. **专家锚点** - 自动识别的关键发现

#### JSON 输出格式

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

#### 触发条件与标签映射

| 场景 | 触发条件 | Risk Level | Attention Flag | Patterns |
|------|----------|------------|----------------|----------|
| 发现瓶颈 | 存在 BOTTLENECK 诊断 | critical | `<X0>` | BOTTLENECK_DETECTED |
| 进程风暴 | Spawn Rate > 10/s | warning | `<X1>` | PROCESS_STORM |
| CPU 竞争 | Demand > Limit | critical | `<X0>` | CPU_CONTENTION |
| Noisy Neighbor | 高 Count 进程影响其他 | critical | `<X0>` | NOISY_NEIGHBOR |
| Quota Victim | 被 Cgroup 限制的健康进程 | warning | `<X1>` | QUOTA_VICTIM |

---

## 快速开始指南

### 文件结构

```
scripts/perf_toolkit/core/
├── output_models.py       # 数据模型定义（ dataclass ）
├── output_adapter.py      # JSON 转换器
├── text_output_adapter.py # 文本输出转换器
├── output_builder.py      # 输出构建器
├── display_presets.py     # 显示配置预设
├── risk_mixin.py          # 风险信息标准化
├── format_utils.py        # 时间/格式工具
└── __init__.py            # 导出模块
```

### 数据项创建

#### ProcessItem（进程数据）

```python
from perf_toolkit.core import ProcessItem

item = ProcessItem.from_cpu_util("nginx", 12345, 45.5, 12.3)
# 输出: {"comm": "nginx", "pid": 12345, "total_cpu_util": "45.50%", "kernel_cpu_util": "12.30%"}
```

#### CommGroupItem（进程组数据）

```python
from perf_toolkit.core import CommGroupItem

item = CommGroupItem.from_stats(
    comm="worker",
    pid_count=100,
    aggregate_cpu=150.0,
    kernel_ratio=60.0,
    event_desc="HIGH_KERNEL: 60%"
)
# 输出: {"comm": "worker", "pids": 100, "cpu": "150.00%", "kernel": "60.00%", "event": "HIGH_KERNEL: 60%"}
```

#### HotspotItem（热点函数）

```python
from perf_toolkit.core import HotspotItem

item = HotspotItem.from_stats("func_name_[k]", 15.23, 45.67)
# 输出: {"symbol": "func_name_[k]", "self": "15.23%", "inclusive": "45.67%"}
```

#### PathClusterItem（路径聚类）

```python
from perf_toolkit.core import PathClusterItem

item = PathClusterItem.from_raw(
    cluster_id="c_001",
    path_signature="main→worker_loop→process_request",
    weight=45.67,
    total_weight=100.0,
    duration=1800
)
# 存储原始权重，百分比由模板计算
```

#### AnomalyItem（异常检测）

```python
from perf_toolkit.core import AnomalyItem

item = AnomalyItem.from_raw(
    type="SPIKE",
    cpu_id=5,
    start="2026-03-02T10:15:00",
    end="2026-03-02T10:16:00",
    prev=0.1,
    curr=0.85,
    next=0.15,
    z_score=2.8
)
```

### 输出构建流程

```python
from perf_toolkit.core import (
    OutputBuilder, create_risk_info,
    CommGroupItem, CommGroupSummary, CommTopOutput, TimeRange
)

# 1. 创建输出构建器
builder = OutputBuilder(engine, args)

# 2. 创建数据项
items = []
for group_data in groups_data:
    items.append(CommGroupItem.from_stats(
        comm=group_data["comm"],
        pid_count=group_data["pid_count"],
        aggregate_cpu=group_data["total_cpu"],
        kernel_ratio=group_data["kernel_ratio"],
        event_desc=group_data["event"]
    ))

# 3. 构建输出
output = CommTopOutput(
    _risk=create_risk_info(level="none"),
    comm_groups=items,
    summary=CommGroupSummary(total_comm_groups=10, shown_processes=5),
    time_range=TimeRange.from_timestamps(start_ts, end_ts)
)

# 4. 打印输出
builder.print_output(output)
```

### 类型注册表

```python
from perf_toolkit.core import OUTPUT_TYPE_MAP, get_output_classes

# 获取数据类型对应的类
item_cls, summary_cls, output_cls = get_output_classes('processes')
# 返回: (ProcessItem, ProcessSummary, ProcessTopOutput)

item_cls, summary_cls, output_cls = get_output_classes('comm_groups')
# 返回: (CommGroupItem, CommGroupSummary, CommTopOutput)

item_cls, summary_cls, output_cls = get_output_classes('hotspots')
# 返回: (HotspotItem, HotspotSummary, HotspotsOutput)
```

---

## 核心指标计算逻辑

### Monopoly (核心独占率)

**用途**: 识别单进程是否垄断该 comm 的 CPU 资源，检测单核瓶颈。

**计算公式**:
```
Monopoly = max(PID_cpu) / sum(all_PID_cpu)
```

**参数说明**:
- `PID_cpu`: 单个 PID 的 CPU 利用率 (%)
- `max(PID_cpu)`: 该 comm 下 CPU 利用率最高的 PID
- `sum(all_PID_cpu)`: 该 comm 下所有 PID 的 CPU 利用率之和

**阈值定义**:
```python
MONOPOLY_THRESHOLD = 0.8   # Monopoly > 0.8 认为单点瓶颈
SIGNIFICANT_MONOPOLY_THRESHOLD = 0.8
```

**诊断分级**:
| Monopoly 值 | 诊断 | 说明 |
|-------------|------|------|
| > 0.8 | BOTTLENECK | 单进程独占大部分 CPU，典型单核瓶颈 |
| ≤ 0.8 | - | 需结合 CV、SpawnRate 进一步判断 |

---

### CV (变异系数)

**用途**: 检测 PID 间的负载不均衡程度。

**计算公式**:
```
CV = σ / μ

其中:
  μ = sum(all_PID_cpu) / PID_count    # 平均 CPU
  σ = sqrt(sum((PID_cpu - μ)²) / PID_count)  # 标准差
```

**阈值定义**:
```python
CV_THRESHOLD = 1.0              # CV > 1.0 认为不均衡
SIGNIFICANT_CV_THRESHOLD = 1.0
```

**诊断分级**:
| CV 值 | 含义 | 说明 |
|-------|------|------|
| > 1.0 | UNBALANCED | PID 间负载严重不均衡 |
| ≤ 1.0 | - | 负载相对均衡 |

---

### Spawn Rate (进程产生速率)

**用途**: 检测进程风暴（短时间内大量进程创建）。

**计算公式**:
```
Spawn Rate = unique_PID_count / duration

其中:
  unique_PID_count: 时间窗口内出现的不同 PID 数量
  duration: 采样时间窗口（秒）
```

**阈值定义**:
```python
SPAWN_RATE_THRESHOLD = 10.0              # > 10/s 认为进程风暴
SIGNIFICANT_SPAWN_RATE_THRESHOLD = 10.0
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

---

### Impact Score (危害指数)

**用途**: 综合排序指标，解决"A掩盖B"问题（高 Count 进程掩盖真瓶颈）。

**计算公式**:
```
Impact Score = CPU*0.3 + CV*40 + Monopoly*50 + SpawnRate*5

权重设计原理:
  - CPU * 0.3:    绝对 CPU 利用率权重较低
  - CV * 40:      不均衡度权重高
  - Monopoly * 50: 独占率权重最高
  - SpawnRate * 5: 进程风暴权重中等
```

**排序策略**:
```python
groups.sort(key=lambda x: x.impact_score, reverse=True)
```

---

### Core Distribution (核心分布不均衡度)

**用途**: 检测系统级 CPU 负载不均衡。

**计算公式**:
```
Imbalance Ratio = max(core_util) / avg(core_util)

其中:
  max(core_util): 利用率最高的核心
  avg(core_util): 所有核心的平均利用率
```

**阈值定义**:
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

---

### 诊断分级逻辑

**综合诊断流程**:
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

### 自动降噪逻辑

**显著性判断**:
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

---

## 验证检查清单

工具输出必须通过以下检查：

- [ ] 输出包含 `_risk` 字段且位于最前
- [ ] `_risk.level` 为 critical/warning/info/none 之一
- [ ] `_risk.action_required` 在 level 为 critical/warning 时为 true
- [ ] 时间戳使用 ISO 8601 字符串格式
- [ ] JSON 嵌套不超过 3 层
- [ ] 百分比在 JSON 中使用字符串格式（带 %）
- [ ] 风险消息简洁明了（一句话）
- [ ] `hint` 字段包含可执行的命令建议

---

## 工具输出速查表

| 工具 | 主数据字段 | time_range | 典型 risk 场景 |
|------|-----------|------------|---------------|
| `analyze-core-distribution` | `cores` | ✅ | 单核饱和 |
| `detect-anomalies` | `anomalies` | ✅ | CPU 尖峰 |
| `get-comm-top` | `comm_groups` | ✅ | 高内核态、进程风暴 |
| `get-hotspots` | `hotspots` | ✅ | 高内核态热点 |
| `find-callers` | `attributions` | ❌ | 目标函数无活动 |
| `cluster-paths` | `path_clusters` | ✅ | - |
| `sys-audit` | `diagnosis`, `details` | ✅ | 综合瓶颈检测 |
| `bottleneck-trace` | `entity_distribution`, `clusters` | ✅ | 瓶颈确认 |

---

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 3.0 | 2026-03-04 | 合并 output-format-spec.md + output-system.md + output-design-composite.md |
| 2.0 | 2026-03-03 | 全面更新以匹配三层架构实现，补充所有工具的字段说明 |
| 1.1 | 2026-03-01 | 补充所有工具的具体输出格式，新增速查表 |
| 1.0 | 2026-02-28 | 初始版本，定义基础规范 |
