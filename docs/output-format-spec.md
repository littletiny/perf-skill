# 工具输出格式规范

> 所有分析工具的 JSON 输出必须遵循的统一规范
> 版本: 1.0
> 创建时间: 2026-02-28

---

## 1. 设计原则

### 1.1 扁平优先
- JSON 嵌套不超过 3 层
- 优先使用字符串而非嵌套对象
- 数组元素保持简单结构

### 1.2 风险置顶
- 所有输出必须包含 `_risk` 字段
- `_risk` 放在输出顶部，第一时间可见
- 风险信息简洁明确，包含建议操作

### 1.3 时间字符串化
- 所有时间字段使用 ISO 8601 格式字符串
- 禁止使用时间戳数字
- 时区信息可选，但必须统一

---

## 2. 字段规范

### 2.1 `_risk` 字段（必须）

**⚠️ 强制性规则**: 当 `_risk.action_required=true` 时，**必须**将问题添加到 Trace

```bash
# 任何返回 action_required=true 的 tool 输出，必须执行：
spear trace add --desc "<_risk.message>" \
  --risk "<_risk.level>" --hint "<_risk.hint>"
```

**强制执行**: 分析流程中禁止忽略 `action_required=true` 的风险提示。未添加到 Trace 的风险视为分析不完整。

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

**示例**:

```json
{
  "_risk": {
    "level": "warning",
    "message": "发现 2 个高内核态进程未分析: containerd-shim, sh",
    "hint": "执行: cluster-symbols --comm containerd-shim",
    "patterns": ["MULTI_HIGH_KERNEL"],
    "pending_targets": ["containerd-shim", "sh"],
    "action_required": true
  }
}
```

### 2.2 时间字段规范（必须）

**格式**: ISO 8601 字符串

```
2026-02-28T14:30:00+08:00  # 带时区
2026-02-28T14:30:00Z       # UTC
2026-02-28T14:30:00        # 本地时间（推荐）
```

**字段命名**:

| 旧字段名 | 新字段名 | 示例 |
|---------|---------|------|
| `start` | `start_time` | `"2026-02-28T10:00:00"` |
| `end` | `end_time` | `"2026-02-28T10:30:00"` |
| `timestamp` | `timestamp` | `"2026-02-28T10:15:30"` |
| `ts` | `timestamp` | `"2026-02-28T10:15:30"` |
| `duration_sec` | `duration` | 保留数字，单位为秒 |

**转换示例**:

```python
# 之前（禁止）
{
  "time_range": {
    "start": 1677567600.123,  # 时间戳数字
    "end": 1677569400.456
  }
}

# 之后（规范）
{
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00",
    "duration": 1800  # 秒，数字
  }
}
```

### 2.3 数值字段规范

**百分比**: 使用字符串，带 % 符号

```json
{
  "cpu_utilization": "45.5%",  # 字符串
  "kernel_ratio": "89.9%"
}
```

**时间**: 使用字符串，带单位

```json
{
  "duration": 1800,           # 秒，数字（用于计算）
  "duration_readable": "30m"  # 可读字符串（可选）
}
```

**core/s 值**: 保留数字，4位小数

```json
{
  "core_seconds": 0.0526,
  "total_core_seconds": 123.4567
}
```

---

## 3. 各工具输出改造规范

### 3.1 check-cpu-bottleneck

**当前问题**:
- 无 `_risk` 字段
- 时间戳数字

**改造后**:

```json
{
  "_risk": {
    "level": "warning",
    "message": "单核满载，可能存在串行化瓶颈",
    "hint": "执行: analyze-core-distribution --pid <pid>",
    "patterns": ["SINGLE_CORE_SATURATION"],
    "action_required": true
  },
  "verdict": "SINGLE_CORE_SATURATION",
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00",
    "duration": 1800
  },
  "max_core_load": {
    "cpu_id": 5,
    "load": "95.2%"
  }
}
```

### 3.2 get-comm-top

**当前问题**:
- 字段过多，嵌套深
- 时间戳数字
- 无 `_risk`

**改造后**:

```json
{
  "_risk": {
    "level": "warning",
    "message": "发现 2 个高内核态进程组未分析",
    "hint": "建议并行分析: cluster-symbols --comm containerd-shim",
    "patterns": ["MULTI_HIGH_KERNEL"],
    "pending_targets": ["containerd-shim", "sh"],
    "action_required": true
  },
  "summary": {
    "total_comm_groups": 4,
    "high_kernel_groups": 2
  },
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00"
  },
  "comm_groups": [
    {
      "comm": "netstat",
      "pid_count": 2623,
      "cpu_pct": "243.87%",
      "kernel_pct": "94.7%"
    }
  ]
}
```

### 3.3 detect-anomalies

**当前问题**:
- 嵌套过深（5层）
- 时间戳数字
- `window` / `utilization` 嵌套对象

**改造后**:

```json
{
  "_risk": {
    "level": "warning",
    "message": "检测到 3 个 CPU 利用率异常尖峰",
    "hint": "分析 spike 时段热点: get-hotspots --start-time '2026-02-28T10:15:00' --end-time '2026-02-28T10:16:00'",
    "patterns": ["CPU_SPIKE"],
    "action_required": true
  },
  "summary": {
    "total_anomalies": 3,
    "spike_count": 2,
    "drop_count": 1
  },
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00"
  },
  "anomalies": [
    {
      "type": "SPIKE",
      "cpu_id": 5,
      "time_range": "2026-02-28T10:15:00 - 2026-02-28T10:16:00",
      "utilization_change": "10% -> 85% -> 15%",
      "severity": "high"
    }
  ]
}
```

### 3.4 analyze-core-distribution

**当前问题**:
- `cores` 数组元素复杂
- 时间戳数字
- `top_symbols` 嵌套

**改造后**:

```json
{
  "_risk": {
    "level": "critical",
    "message": "负载严重不均衡: 单核满载，其他核心空闲",
    "hint": "检查锁竞争: cluster-symbols --comm <target>",
    "patterns": ["SINGLE_CORE_SATURATION"],
    "action_required": true
  },
  "summary": {
    "imbalance_level": "CRITICAL",
    "max_utilization": "95.2%",
    "min_utilization": "2.1%",
    "saturated_cores": 1
  },
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00"
  },
  "cores": [
    {
      "cpu_id": 5,
      "utilization": "95.2%",
      "state": "saturated"
    }
  ]
}
```

### 3.5 cluster-symbols

**当前问题**:
- 相对简洁，但无 `_risk`
- 时间戳数字

**改造后**:

```json
{
  "_risk": {
    "level": "critical",
    "message": "锁竞争占比 79.84%，系统严重瓶颈",
    "hint": "溯源锁调用: find-callers --target <lock_func>",
    "patterns": ["HIGH_LOCK_CONTENTION"],
    "action_required": true
  },
  "summary": {
    "total_core_seconds": 123.4567
  },
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00"
  },
  "clusters": [
    {
      "cluster": "EVENT_LOCK_CONTENTION",
      "ratio_pct": "79.84%",
      "core_sec": 98.7654
    }
  ]
}
```

---

## 4. 实施清单

### 4.1 待改造文件

| 文件 | 优先级 | 主要改造点 |
|------|--------|-----------|
| `bottleneck.py` | P0 | 添加 `_risk`，时间字符串化 |
| `comm_top.py` | P0 | 添加 `_risk`，简化字段，时间字符串化 |
| `anomalies.py` | P0 | 扁平化结构，时间字符串化 |
| `core_distribution.py` | P0 | 简化 `cores`，时间字符串化 |
| `clusters.py` | P1 | 添加 `_risk`，时间字符串化 |
| `hotspots.py` | P1 | 添加 `_risk`，时间字符串化 |
| `trace.py` | P1 | 时间字符串化 |
| `cpu_usage.py` | P1 | 时间字符串化 |
| `process_top.py` | P1 | 时间字符串化 |
| `process_variety.py` | P1 | 时间字符串化 |
| `comm_clusters.py` | P2 | 时间字符串化 |
| `path_clusters.py` | P2 | 时间字符串化 |
| `flamegraph.py` | P2 | 时间字符串化 |
| `callgraph.py` | P2 | 时间字符串化 |

### 4.2 改造步骤

1. **创建 RiskMixin 基类** (`core/risk_mixin.py`)
2. **创建时间格式化工具** (`core/format_utils.py`)
3. **按优先级逐个改造**:
   - 添加 `_risk` 字段
   - 时间戳改为字符串
   - 简化嵌套结构
4. **更新测试用例**
5. **更新文档**

---

## 5. 辅助工具

### 5.1 时间格式化函数

```python
# core/format_utils.py
from datetime import datetime

def format_timestamp(ts: float) -> str:
    """Convert timestamp to ISO 8601 string"""
    return datetime.fromtimestamp(ts).isoformat()

def format_time_range(start_ts: float, end_ts: float) -> dict:
    """Format time range with readable string"""
    return {
        "start_time": format_timestamp(start_ts),
        "end_time": format_timestamp(end_ts),
        "duration": round(end_ts - start_ts, 2)
    }

def format_duration(seconds: float) -> str:
    """Format duration to readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"
```

### 5.2 RiskMixin 基类

```python
# core/risk_mixin.py

class RiskMixin:
    """Mixin for standardized risk hints in output"""

    RISK_LEVELS = ["critical", "warning", "info", "none"]

    def __init__(self):
        self.risks = []

    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: list = None, targets: list = None):
        """Add a risk hint"""
        if level not in self.RISK_LEVELS:
            level = "info"

        self.risks.append({
            "level": level,
            "message": message,
            "hint": hint,
            "patterns": patterns or [],
            "pending_targets": targets or []
        })

    def get_top_risk(self) -> dict:
        """Get the highest level risk"""
        priority = {"critical": 0, "warning": 1, "info": 2, "none": 3}

        if not self.risks:
            return {
                "level": "none",
                "message": "无风险",
                "hint": "",
                "patterns": [],
                "pending_targets": [],
                "action_required": False
            }

        top = min(self.risks, key=lambda r: priority.get(r["level"], 3))
        return {
            **top,
            "action_required": top["level"] in ["critical", "warning"]
        }

    def format_output(self, data: dict) -> dict:
        """Add _risk field to output"""
        return {
            "_risk": self.get_top_risk(),
            **data
        }
```

---

## 6. 验证检查清单

改造后的工具必须通过以下检查：

- [ ] 输出包含 `_risk` 字段
- [ ] `_risk.level` 为 critical/warning/info/none 之一
- [ ] 所有时间戳已转换为 ISO 8601 字符串
- [ ] JSON 嵌套不超过 3 层
- [ ] 百分比使用字符串格式（带 %）
- [ ] 风险消息简洁明了（一句话）
- [ ] hint 字段包含可执行的命令建议

---

## 7. 参考

- [Trace 设计](./design-rationale-trace-v1.md)
- [Trace 接口](./trace-interface.md)
- [CHANGES.md](../CHANGES.md)

---

## 4. 各工具具体输出格式

### 4.1 可视化工具之外的工具输出格式

#### 4.1.1 get-hotspots（热点函数排名）

**输出结构**:
```json
{
  "_risk": {
    "level": "warning | none",
    "message": "热点函数 xxx 内核态占比 yy.yy%",
    "hint": "find-callers --target xxx",
    "patterns": ["HIGH_KERNEL_HOTSPOT"],
    "action_required": true
  },
  "summary": {
    "total_hotspots": 50
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

**字段说明**:
- `symbol`: 函数名（规范化后的名称）
- `self`: 自消耗 CPU 占比（字符串，带 %）
- `inclusive`: 包含调用树的 CPU 占比（字符串，带 %）

---

#### 4.1.2 get-process-top（进程 CPU 排名）

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "action_required": false
  },
  "summary": {
    "total_processes": 50,
    "shown_processes": 10
  },
  "processes": [
    {
      "comm": "nginx",
      "pid": 12345,
      "cpu_pct": "45.5%",
      "kernel_pct": "12.3%"
    }
  ]
}
```

**字段说明**:
- `comm`: 进程名
- `pid`: 进程 ID
- `cpu_pct`: 总 CPU 使用率（字符串，带 %）
- `kernel_pct`: 内核态 CPU 占比（字符串，带 %）

---

#### 4.1.3 get-comm-top（按进程名聚合排名）

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "发现 2 个高内核态进程组未分析",
    "hint": "建议并行分析: cluster-symbols --comm containerd-shim",
    "patterns": ["MULTI_HIGH_KERNEL"],
    "pending_targets": ["containerd-shim", "sh"],
    "action_required": true
  },
  "summary": {
    "total_comm_groups": 4,
    "high_kernel_groups": 2
  },
  "comm_groups": [
    {
      "comm": "netstat",
      "pids": 2623,
      "cpu": "243.87%",
      "kernel": "94.7%",
      "event": "MANY_SMALL_PROCESSES: 2623个进程，每个仅消耗0.09% CPU"
    }
  ]
}
```

**字段说明**:
- `comm`: 进程名
- `pids`: 该进程名下的进程数量
- `cpu`: 聚合 CPU 使用率（字符串，带 %）
- `kernel`: 内核态占比（字符串，带 %）
- `event`: 事件描述（字符串，描述检测到的模式）

**event 取值**:
- `"MANY_SMALL_PROCESSES: {n}个进程，每个仅消耗{x}% CPU"` - 大量小进程模式
- `"HIGH_KERNEL: 内核态占比 {x}%"` - 高内核态模式
- `"normal"` - 正常模式

---

#### 4.1.4 cluster-symbols（专家规则聚类）

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "锁竞争占比 79.84%，系统严重瓶颈",
    "hint": "溯源锁调用: find-callers --target 'pthread_mutex_lock'",
    "patterns": ["HIGH_LOCK_CONTENTION"],
    "action_required": true
  },
  "summary": {
    "clusters_found": 5
  },
  "clusters": [
    {
      "cluster": "EVENT_LOCK_CONTENTION",
      "ratio_pct": "79.84%",
      "core_sec": 98.7654
    }
  ]
}
```

**字段说明**:
- `cluster`: 聚类名称（如 EVENT_IRQ_OFF, EVENT_SCHEDULER 等）
- `ratio_pct`: 该聚类占比（字符串，带 %）
- `core_sec`: core·s 值（数字，4位小数）

---

#### 4.1.5 cluster-comm（按进程名简单聚类）

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "action_required": false
  },
  "summary": {
    "total_comm_groups": 10
  },
  "comm_groups": [
    {
      "comm": "nginx",
      "unique_pids": 4,
      "cpu_pct": "45.5%",
      "kernel_pct": "12.3%"
    }
  ]
}
```

**字段说明**:
- `comm`: 进程名
- `unique_pids`: 唯一 PID 数量
- `cpu_pct`: 聚合 CPU 使用率（字符串，带 %）
- `kernel_pct`: 内核态占比（字符串，带 %）

---

#### 4.1.6 cluster-paths（按调用路径聚类）

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "action_required": false
  },
  "summary": {
    "total_clusters": 15
  },
  "clusters": [
    {
      "cluster_id": "c_001",
      "path_signature": "main→worker_loop→process_request",
      "ratio_pct": "45.67%",
      "core_sec": "1.2345 core·s"
    }
  ]
}
```

**字段说明**:
- `cluster_id`: 聚类 ID（如 c_001）
- `path_signature`: 调用路径签名（→ 分隔）
- `ratio_pct`: 占比（字符串，带 %）
- `core_sec`: core·s 值（字符串格式）

---

#### 4.1.7 find-callers（调用链溯源）

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
    "target_core_sec": "1.2345 core·s"
  },
  "attributions": [
    {
      "caller_stack": ["func_a", "func_b", "func_c"],
      "ratio_of_target_pct": "45.67%",
      "core_sec": "0.5678 core·s"
    }
  ]
}
```

**字段说明**:
- `target`: 目标函数名
- `target_core_sec`: 目标函数总 core·s（字符串格式）
- `caller_stack`: 调用链（从直接调用者到上层）
- `ratio_of_target_pct`: 该调用链占比（字符串，带 %）

---

#### 4.1.8 count-process-variety（进程风暴检测）

**输出结构**:
```json
{
  "_risk": {
    "level": "critical",
    "message": "检测到 3 个进程风暴（短生命周期进程）",
    "hint": "**必须立即执行**: 对每个进程名运行 'cluster-symbols --comm <comm>' 进行详细分析",
    "patterns": ["PROCESS_STORM"],
    "pending_targets": ["worker", "task"],
    "action_required": true
  },
  "summary": {
    "total_processes": 100,
    "storm_detected": true,
    "storm_count": 3
  },
  "process_variety": [
    {
      "comm": "worker",
      "unique_pids": 500,
      "total_core_sec": 12.34,
      "cpu_per_pid": 0.025,
      "behavior": "process_storm"
    }
  ]
}
```

**字段说明**:
- `comm`: 进程名
- `unique_pids`: 唯一 PID 数量
- `total_core_sec`: 总 core·s（数字）
- `cpu_per_pid`: 每 PID 平均 CPU（数字）
- `behavior`: 行为模式（`process_storm`, `short_lived_heavy`, `normal`）

---

#### 4.1.9 show-cpu-usage（CPU 利用率）

**输出结构**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "内核态 CPU 使用率 65.43% 异常高",
    "hint": "分析内核热点: cluster-symbols",
    "patterns": ["HIGH_KERNEL_USAGE"],
    "action_required": true
  },
  "target": "PID 12345",
  "cpu_utilization": {
    "total_pct": "78.9%",
    "user_pct": "23.5%",
    "kernel_pct": "55.4%"
  }
}
```

**字段说明**:
- `target`: 分析目标描述（如 "PID 12345", "comm=nginx", "System-wide"）
- `total_pct`: 总 CPU 使用率（字符串，带 %）
- `user_pct`: 用户态 CPU 占比（字符串，带 %）
- `kernel_pct`: 内核态 CPU 占比（字符串，带 %）

---

### 4.2 可视化工具输出格式

#### 4.2.1 generate-flamegraph（火焰图）

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "action_required": false
  },
  "data": {
    "format": "flamegraph",
    "content": "<svg>...</svg>",
    "content_type": "image/svg+xml"
  },
  "summary": {
    "total_samples": 10000,
    "unique_functions": 500
  }
}
```

---

#### 4.2.2 generate-callgraph（调用图）

**输出结构**:
```json
{
  "_risk": {
    "level": "none",
    "message": "",
    "hint": "",
    "action_required": false
  },
  "data": {
    "format": "dot",
    "content": "digraph { ... }",
    "content_type": "text/vnd.graphviz"
  },
  "summary": {
    "total_nodes": 50,
    "total_edges": 120
  }
}
```

---

## 5. 工具输出速查表

| 工具 | 主数据字段 | 有无 time_range | 典型 risk 场景 |
|------|-----------|----------------|--------------|
| `get-hotspots` | `hotspots` | 无 | 高内核态热点 |
| `get-process-top` | `processes` | 无 | - |
| `get-comm-top` | `comm_groups` | 无 | 多进程高内核态 |
| `cluster-symbols` | `clusters` | 无 | 高锁竞争 |
| `cluster-comm` | `comm_groups` | 无 | - |
| `cluster-paths` | `clusters` | 无 | - |
| `find-callers` | `attributions` | 无 | 目标函数无活动 |
| `count-process-variety` | `process_variety` | 无 | 进程风暴 |
| `show-cpu-usage` | `cpu_utilization` | 无 | 高内核态使用率 |
| `check-cpu-bottleneck` | `verdict`, `max_core_load` | **有** | 单核满载 |
| `detect-anomalies` | `anomalies` | **有** | CPU 尖峰 |
| `analyze-core-distribution` | `cores` | **有** | 负载不均衡 |
| `generate-flamegraph` | `data` (SVG) | 无 | - |
| `generate-callgraph` | `data` (DOT) | 无 | - |

---

## 6. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0 | 2026-02-28 | 初始版本，定义基础规范和 5 个 P0 工具 |
| 1.1 | 2026-03-01 | 补充所有工具的具体输出格式，新增速查表 |
