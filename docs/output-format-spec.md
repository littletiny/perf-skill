# 工具输出格式规范

> 所有分析工具的 JSON 输出必须遵循的统一规范
> 版本: 2.0
> 更新时间: 2026-03-03

---

## 设计原则

### 风险置顶
- 所有输出必须包含 `_risk` 字段
- `_risk` 放在输出顶部，第一时间可见
- 风险信息简洁明确，包含建议操作

### 扁平结构
- JSON 嵌套不超过 2 层
- 优先使用简单列表而非嵌套对象
- 列表项使用平面对象，避免多级 children 嵌套

### 时间字符串化
- 所有时间字段使用 ISO 8601 格式字符串
- 禁止使用 Unix 时间戳数字
- 时区信息可选，但必须统一

### 数值原始
- 百分比存储为原始数字（如 0.15 表示 15%），格式化交给渲染层
- 时间存储为时间戳或 ISO 字符串，避免自定义格式

---

## 字段规范

### `_risk` 字段（必须）

```json
{
  "_risk": {
    "level": "critical | warning | info | none",
    "message": "简短的风险描述，一句话说明问题",
    "hint": "建议的下一步操作，可执行的命令",
    "patterns": ["检测到的模式名称"],
    "pending_targets": ["待处理的目标列表"],
    "action_required": true
  }
}
```

**Level 定义**:

| Level | 条件 | Agent 响应 |
|-------|------|-----------|
| `critical` | 严重问题，诊断可能不完整 | 立即处理，禁止收敛 |
| `warning` | 潜在问题，建议处理 | 优先处理，记录风险 |
| `info` | 值得关注的信息 | 了解即可 |
| `none` | 无风险 | 继续正常流程 |

**⚠️ 强制性规则**: 当 `_risk.action_required=true` 时，**必须**将问题添加到 Trace

```bash
# 任何返回 action_required=true 的 tool 输出，必须执行：
shecr trace add --desc "<_risk.message>" \
  --risk "<_risk.level>" --hint "<_risk.hint>"
```

### `summary` 字段

各命令的 summary 字段根据工具类型不同：

| 工具 | Summary 字段 |
|------|-------------|
| `get-hotspots` | `total_hotspots`, `shown_hotspots` |
| `get-comm-top` | `total_comm_groups`, `high_kernel_groups` |
| `cluster-paths` | `total_clusters`, `shown_clusters`, `clustered_weight` |
| `detect-anomalies` | `total_anomalies`, `spike_count`, `drop_count` |
| `find-callers` | `target`, `target_cpu_util`, `total_attributions`, `shown_attributions` |

### `time_range` 字段

包含时间范围的命令会输出：

```json
{
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  }
}
```

---

## 各工具具体输出格式

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

进程组分析（增强版，含 CV/Monopoly/SpawnRate）。

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

**增强指标**（V3 版本，通过 `--include-metrics` 可在 Composite 层获取）:
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

**注**: 渲染层会根据 `weight` / `total_weight` 计算百分比显示

---

### 组合诊断工具

#### sys-audit

系统全景审计（Composite 层命令）。

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "检测到 2 个关键性能问题",
    "hint": "执行 bottleneck-trace --comm app_worker 深度分析",
    "patterns": ["BOTTLENECK_DETECTED", "PROCESS_STORM"],
    "pending_targets": ["app_worker", "task_worker"],
    "action_required": true
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "diagnosis": {
    "primary_suspect": {
      "comm": "app_worker",
      "total_cpu": 12.5,
      "diagnosis": "BOTTLENECK",
      "monopoly": 0.92
    },
    "secondary_loads": [
      {"comm": "lsof", "total_cpu": 400.0, "diagnosis": "STORM"}
    ],
    "background_count": 24,
    "mutation_detected": true,
    "mutation_time": "2026-03-02T10:05:00",
    "saturated_cores": [7],
    "root_cause_analysis": "主要瓶颈: app_worker (BOTTLENECK); 检测到性能突变; 核心饱和: CPU 7"
  },
  "details": {
    "anomalies": {
      "anomalies_count": 3,
      "mutation_detected": true,
      "risks": [...]
    },
    "core_distribution": {
      "core_count": 8,
      "saturated_cores": [7],
      "imbalance_level": "CRITICAL",
      "risks": [...]
    },
    "comm_top": {
      "groups_count": 10,
      "folded_count": 5,
      "total_groups": 15,
      "risks": [...]
    }
  }
}
```

**诊断分级**:
- `primary_suspect`: 主要嫌疑人（BOTTLENECK 诊断的进程）
- `secondary_loads`: 次要负载（高 CPU 或 STORM/UNBALANCED 诊断）
- `background_noise`: 背景噪音（已折叠的低优先级组）

---

#### bottleneck-trace

瓶颈深度追踪（Composite 层命令）。通过多维度聚合分析定位 CPU 瓶颈根因。

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "发现关键瓶颈: app_B (Monopoly=0.96, Throttle=82.5%)",
    "hint": "查看 [CONVERGENCE_TRACE] 中的调用链分析",
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
    }
  ],
  "common_hotspot": "_raw_spin_lock",
  "common_hotspot_weight": 0.724,
  "clusters": [
    {
      "cluster_id": "c_001",
      "comm": "lsof",
      "weight": 0.68,
      "path": ["lsof", "vfs_read", "iterate_dir", "__d_lookup_rcu"],
      "hotspot": "_raw_spin_lock",
      "characteristic": "High_Frequency_Exclusive_CPU"
    }
  ],
  "correlation_flags": [
    {
      "flag_type": "GLOBAL_LOCK_CONTENTION",
      "target": "_raw_spin_lock",
      "message": "_raw_spin_lock usage exceeds 40% of sys time",
      "severity": "critical"
    }
  ],
  "total_pids": 2421,
  "total_sys_cpu": 165.2,
  "top_bottlenecks": ["_raw_spin_lock", "cgroup_try_mem_free", "futex_wait"],
  "duration_sec": 60.0,
  "sample_count": 31500,
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00"
  }
}
```

**数据项说明**:

| 字段 | 类型 | 说明 | 来源 |
|------|------|------|------|
| `entity_distribution` | List[EntityDistribution] | 实体分布矩阵 | Composite 层聚合 |
| `entity_distribution[].comm` | str | 进程组名称 | get-comm-top |
| `entity_distribution[].count` | int | PID 数量 | get-comm-top |
| `entity_distribution[].incl_saliency` | float | Inclusive CPU 显著度 | get-hotspots |
| `entity_distribution[].excl_saliency` | float | Exclusive (Self) CPU 显著度 | get-hotspots |
| `entity_distribution[].core_affinity` | str | 核心亲缘性模式 (Fixed/Uniform/Scattered) | analyze-core-distribution |
| `entity_distribution[].throttle_rate` | float | CPU 节流比例 | Core 层计算 |
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
| `correlation_flags[].severity` | str | 严重程度 (critical/warning/info) | Composite 层判定 |
| `total_pids` | int | 采样期间唯一 PID 数 | Core 层 |
| `total_sys_cpu` | float | 系统总 CPU 利用率(%) | Core 层 |
| `top_bottlenecks` | List[str] | 排名前三的热点符号 | Composite 层聚合 |
| `duration_sec` | float | 采样持续时间 | Core 层 |
| `sample_count` | int | 总样本数 | Core 层 |

**CorrelationFlag 类型**:

| Flag | 检测条件 | 来源数据 |
|------|----------|----------|
| `GLOBAL_LOCK_CONTENTION` | 全局锁符号 inclusive% > 40% | get-hotspots |
| `SINGLE_CORE_SATURATION` | 单核利用率 > 90% 且 Monopoly > 0.8 | analyze-core-distribution |
| `THROTTLE_VICTIM` | Throttle_Rate > 50% | Core 层 + cgroup 分析 |
| `STORM_PATTERN` | Spawn_Rate > 100/s 或 PID_Count > 1000 | get-comm-top |
| `KERNEL_HEAVY` | 内核态占比 > 50% | get-hotspots |
| `UNBALANCED_LOAD` | CV > 1.5 且 Monopoly < 0.5 | get-comm-top |

**Path_Characteristic 标签**:

| 标签 | 说明 | 触发条件 |
|------|------|----------|
| `High_Frequency_Exclusive_CPU` | 高频独占 CPU | Self% >> Inclusive% |
| `Inclusive_Latency_Victim` | 包容性延迟受害者 | 等待资源/锁 |
| `Syscall_Bound` | 系统调用密集 | 内核态占比 > 50% |
| `Lock_Contention` | 锁竞争 | 热点为 lock/mutex/spinlock |
| `IO_Wait_Dominant` | IO 等待主导 | io_schedule 高频 |

**Core_Affinity 判定规则**:

| 模式 | 判定条件 | 说明 |
|------|----------|------|
| Fixed | Entropy < 0.3, Monopoly > 0.8 | 单核心绑定 |
| Uniform | Entropy > 2.0, CV < 0.5 | 均匀分布到多核 |
| Scattered | 其他情况 | 分散无规律 |

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
| `bottleneck-trace` | `bottleneck_analysis`, `hotspots`, `callers` | ✅ | 瓶颈确认 |

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

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 2.0 | 2026-03-03 | 全面更新以匹配三层架构实现，补充所有工具的字段说明 |
| 1.1 | 2026-03-01 | 补充所有工具的具体输出格式，新增速查表 |
| 1.0 | 2026-02-28 | 初始版本，定义基础规范 |
