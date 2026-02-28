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

- [Live Document 设计](./design-rationale-live-doc.md)
- [Live Document 接口](./live-doc-interface.md)
- [CHANGES.md](../CHANGES.md)
