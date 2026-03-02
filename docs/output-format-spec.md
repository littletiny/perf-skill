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
spear trace add --desc "<_risk.message>" \
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

瓶颈深度追踪（Composite 层命令）。

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "app_worker 存在明显瓶颈",
    "hint": "查看 hotspots 和 callers 分析结果",
    "patterns": ["BOTTLENECK_CONFIRMED"],
    "action_required": true
  },
  "time_range": {
    "start_time": "2026-03-02T10:00:00",
    "end_time": "2026-03-02T10:30:00",
    "duration": 1800
  },
  "target_comm": "app_worker",
  "bottleneck_analysis": {
    "monopoly": 0.92,
    "diagnosis": "BOTTLENECK",
    "impact_score": 85.5
  },
  "hotspots": {
    "top_symbol": "pthread_mutex_lock",
    "kernel_ratio": 65.3,
    "items": [...]
  },
  "callers": {
    "target": "pthread_mutex_lock",
    "attributions": [...]
  }
}
```

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
