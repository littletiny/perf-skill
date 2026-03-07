# SHECR 配置指南

> perf-hunter 配置系统完整说明
> 
> 版本: 1.0
> 更新日期: 2026-03-04

---

## 配置系统概览

SHECR 采用分层配置架构，所有配置分为三类：

| 配置类型 | 文件位置 | 用途 | 修改方式 |
|---------|---------|------|---------|
| **代码常量** | `config/defaults.py` | 阈值、枚举值、模板常量 | 修改源码 |
| **Risk 显示** | `config/risk-default.json` | Risk 消息样式、颜色、模板 | JSON 配置 |
| **分析规则** | `config/default-rules.json` | 符号分类规则 | JSON 配置 |

---

## 代码常量配置 (config/defaults.py)

Python 模块定义所有分析阈值和显示常量，**修改需重启工具生效**。

### 1. Attention Flags (SHECR 优先级标签)

```python
class AttentionFlag:
    X0 = "<X0>"   # 阻塞级 (Critical/Blocker) - 立即处理
    X1 = "<X1>"   # 重要级 (High/Major) - 优先关注
    X2 = "<X2>"   # 提示级 (Medium/Minor) - 辅助信息
    XA = "<XA>"   # 操作建议 (Action) - 必须执行的操作
```

### 2. 诊断类型常量

```python
class DiagnosisType:
    BOTTLENECK = "BOTTLENECK"       # 单进程瓶颈
    STORM = "STORM"                 # 进程风暴
    UNBALANCED = "UNBALANCED"       # 负载不均衡
    NORMAL = "NORMAL"               # 正常
    HEALTHY = "HEALTHY"             # 健康
```

### 3. 严重级别

```python
class SeverityLevel:
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
```

### 4. 分析阈值 (Thresholds)

```python
class Thresholds:
    # Bottleneck Detection
    MONOPOLY_HIGH = 0.8             # 高 Monopoly 阈值 (80%)
    MONOPOLY_CRITICAL = 0.9         # 严重 Monopoly 阈值 (90%)
    
    CV_UNBALANCED = 1.0             # 不均衡变异系数阈值
    CV_HIGH = 2.0                   # 高变异系数阈值
    
    IMPACT_SCORE_LOW = 10.0         # 低影响分数
    IMPACT_SCORE_MEDIUM = 20.0      # 中等影响分数
    IMPACT_SCORE_HIGH = 50.0        # 高影响分数
    
    # CPU Utilization
    CPU_UTIL_LOW = 30.0             # 低 CPU 利用率 (%)
    CPU_UTIL_MEDIUM = 50.0          # 中等 CPU 利用率 (%)
    CPU_UTIL_HIGH = 80.0            # 高 CPU 利用率 (%)
    CPU_UTIL_CRITICAL = 100.0       # 严重 CPU 利用率 (%)
    
    # Kernel Ratio
    KERNEL_RATIO_HIGH = 50.0        # 高内核态比例 (%)
    KERNEL_RATIO_CRITICAL = 70.0    # 严重内核态比例 (%)
    
    # Core Distribution
    IMBALANCE_RATIO_CRITICAL = 10.0  # 极不均衡比例
    CORE_SATURATED_THRESHOLD = 50.0  # 核心饱和阈值 (%)
    
    # Z-Score (Anomaly Detection)
    Z_SCORE_MEDIUM = 2.0            # 中等异常 Z-Score
    Z_SCORE_HIGH = 2.5              # 高异常 Z-Score
```

### 5. 采样默认值

```python
class SamplingDefaults:
    DEFAULT_FREQ = 19               # 默认采样频率 (Hz)
    DEFAULT_WINDOW_SIZE = 1.0       # 默认窗口大小 (秒)
    DEFAULT_SPIKE_THRESHOLD = 0.5   # 默认突变阈值
    DEFAULT_MIN_UTILIZATION = 0.3   # 默认最小利用率
```

### 6. Composite 分析默认值

```python
class CompositeDefaults:
    # Bottleneck Trace
    DEFAULT_TOP_N = 10
    DEFAULT_TOP_HOTSPOTS = 5
    DEFAULT_TOP_CALLERS = 3
    
    # Sys Audit
    DEFAULT_SYS_AUDIT_TOP_N = 20
    DEFAULT_SECONDARY_LOADS_LIMIT = 3
    DEFAULT_EXPERT_ANCHORS_LIMIT = 2
    DEFAULT_SATURATED_CORES_LIMIT = 5
    
    # CPU Quota Assumption
    DEFAULT_CPU_QUOTA_LIMIT = 200.0  # 假设 2 cores (200%)
```

---

## Risk 显示配置 (config/risk-default.json)

控制 Risk 消息的**显示样式**，支持运行时加载不同配置。

### 配置加载优先级（从高到低）

```
1. 命令行参数   --risk-config PATH
2. 环境变量     SPEAR_RISK_CONFIG
3. 项目目录     .shecr/risk.json
4. 用户目录     ~/.config/shecr/risk.json
5. 内置默认     config/risk-default.json
```

### 配置文件格式

```json
{
  "_comment": "Default risk display configuration for SHECR - 无图标、无缩进、极简设计",
  "risk": {
    "colors": {
      "critical": "\u001b[91m",    // 红色
      "warning": "\u001b[93m",     // 黄色
      "info": "\u001b[94m",        // 蓝色
      "reset": "\u001b[0m"         // 重置
    },
    "templates": {
      "issue_open": "[OPEN] [{id}] [{level}] {desc}",
      "issue_resolved": "[RESOLVED] [{id}] [{level}] {desc}",
      "hint": "→ {hint}",
      "result": "→ {result}",
      "list_header_open": "[OPEN] {count} issues pending",
      "list_header_resolved": "[RESOLVED] {count} issues",
      "list_header_all": "[ALL] {open_count} open, {resolved_count} resolved",
      "timeline_command": "[{seq}] {time} {command}",
      "timeline_finding_created": "[{level}] {issue_id}: {desc}",
      "timeline_finding_resolved": "[RESOLVED] {issue_id}: {result}",
      "timeline_info": "[INFO] {message}"
    },
    "show": {
      "hint": true,      // 是否显示 hint
      "result": true     // 是否显示 result
    }
  },
  "modes": {
    "ci": {
      "colors": {
        "critical": "",
        "warning": "",
        "info": "",
        "reset": ""
      }
    },
    "compact": {
      "templates": {
        "issue_open": "[OPEN] {id} [{level}] {desc}",
        "issue_resolved": "[RESOLVED] {id} [{level}] {desc}"
      },
      "show": {
        "hint": false,
        "result": false
      }
    }
  }
}
```

### 模板变量

| 变量 | 说明 | 可用模板 |
|------|------|---------|
| `{id}` | Issue ID | issue_open, issue_resolved |
| `{level}` | Risk 级别 | issue_open, issue_resolved, timeline_finding_created |
| `{desc}` | Issue 描述 | issue_open, issue_resolved, timeline_finding_created |
| `{hint}` | 提示信息 | hint |
| `{result}` | 解决结果 | result, timeline_finding_resolved |
| `{count}` | Issue 数量 | list_header_open, list_header_resolved |
| `{open_count}` | 未解决数量 | list_header_all |
| `{resolved_count}` | 已解决数量 | list_header_all |
| `{seq}` | 序号 | timeline_command |
| `{time}` | 时间 | timeline_command |
| `{command}` | 命令 | timeline_command |
| `{issue_id}` | Issue ID | timeline_finding_created, timeline_finding_resolved |
| `{message}` | 信息 | timeline_info |

### 使用示例

**创建 CI 模式配置**（无颜色）：

```bash
# 创建配置文件
cat > .shecr/risk-ci.json << 'EOF'
{
  "risk": {
    "colors": {
      "critical": "",
      "warning": "",
      "info": "",
      "reset": ""
    }
  }
}
EOF

# 使用配置
shecr trace issues --risk-config .shecr/risk-ci.json
```

**通过环境变量指定**：

```bash
export SPEAR_RISK_CONFIG=~/.config/shecr/risk-compact.json
shecr trace timeline
```

---

## 分析规则配置 (config/default-rules.json)

定义符号分类规则，用于 `cluster-symbols` 等命令的自动分类。

### 配置文件格式

```json
{
  "_comment": "perf-hunter 统一规则配置",
  "_description": "集中管理所有分析规则，避免散落在代码中",
  "_version": "1.1",

  "expert_rules": {
    "_comment": "符号分类规则 - 用于 cluster-symbols 等命令",
    "EVENT_IRQ_OFF": "irqoff|spin_unlock_irqrestore|ksoftirqd",
    "EVENT_SCHEDULER": "sched_|pick_next_task|load_balance|idle_balance|dequeue_task|enqueue_task",
    "EVENT_MEM_RECLAIM": "direct_reclaim|try_to_free_pages|tlb_flush|tlb_shootdown",
    "EVENT_LOCK_CONTENTION": "spin_lock|mutex_lock|rwsem_down|queued_spin_lock",
    "EVENT_SYNC_PRIMITIVE": "pthread_mutex|pthread_cond|pthread_sig|futex_wait|futex_wake"
  },

  "idle_detection": {
    "_comment": "Idle 进程检测规则 - PID=0 是 Linux idle 进程的标准特征",
    "enabled": true,
    "pid_zero": true
  }
}
```

### 符号分类规则

| 规则名 | 匹配模式 | 说明 |
|--------|---------|------|
| `EVENT_IRQ_OFF` | `irqoff\|spin_unlock_irqrestore\|ksoftirqd` | 中断关闭相关 |
| `EVENT_SCHEDULER` | `sched_\|pick_next_task\|load_balance\|...` | 调度器相关 |
| `EVENT_MEM_RECLAIM` | `direct_reclaim\|try_to_free_pages\|...` | 内存回收相关 |
| `EVENT_LOCK_CONTENTION` | `spin_lock\|mutex_lock\|rwsem_down\|...` | 锁竞争相关 |
| `EVENT_SYNC_PRIMITIVE` | `pthread_mutex\|pthread_cond\|...` | 同步原语相关 |

### 规则语法

- `|` 表示或（匹配任一模式）
- 支持正则表达式
- 匹配函数名（symbol）

---

## wrap 脚本配置 (.shecr.json)

项目级配置文件，由 `shecr init` 生成。

### 文件格式

```json
{
  "data_path": "path/to/perf.data",
  "script_path": "scripts/perf_toolkit",
  "freq": 19,
  "risk_config": "config/risk-default.json",
  "rules_file": "config/default-rules.json"
}
```

### 配置项说明

| 配置项 | 类型 | 说明 | 必需 |
|--------|------|------|------|
| `data_path` | string | perf.data 文件路径 | 是 |
| `script_path` | string | 脚本目录路径 | 否 |
| `freq` | int | 采样频率 (Hz) | 否 |
| `risk_config` | string | Risk 配置文件路径 | 否 |
| `rules_file` | string | 规则配置文件路径 | 否 |

### 初始化命令

```bash
# 基本初始化
shecr init --data-path ./perf.data

# 完整初始化
shecr init --data-path ./perf.data \
           --script-path ./scripts \
           --freq 99 \
           --risk-config ./custom-risk.json \
           --rules-file ./custom-rules.json
```

---

## 环境变量配置 (.shecr_env)

环境变量文件，用于 wrap 脚本。

### 示例内容

```bash
# SHECR 环境配置
# 生成时间: 2026-03-04T02:40:00+08:00

# 数据文件路径
SHECR_DATA_PATH=/path/to/perf.data

# 脚本路径
SHECR_SCRIPT_PATH=scripts/perf_toolkit

# 采样频率
SHECR_FREQ=19

# Risk 配置
SHECR_RISK_CONFIG=config/risk-default.json

# 规则文件
SHECR_RULES_FILE=config/default-rules.json
```

---

## 完整配置示例

### 场景：自定义阈值和 Risk 样式

**1. 修改阈值（config/defaults.py）**

```python
class Thresholds:
    # 将严重 Monopoly 阈值从 90% 调整为 85%
    MONOPOLY_CRITICAL = 0.85
    
    # 降低核心饱和阈值
    CORE_SATURATED_THRESHOLD = 40.0
```

**2. 创建自定义 Risk 配置（.shecr/risk-custom.json）**

```json
{
  "risk": {
    "colors": {
      "critical": "\u001b[95m",
      "warning": "\u001b[33m",
      "info": "\u001b[36m",
      "reset": "\u001b[0m"
    },
    "templates": {
      "issue_open": "🚨 [{id}] {level}: {desc}",
      "hint": "💡 {hint}",
      "result": "✅ {result}"
    },
    "show": {
      "hint": true,
      "result": true
    }
  },
  "modes": {
    "minimal": {
      "show": {
        "hint": false,
        "result": false
      }
    }
  }
}
```

**3. 使用配置**

```bash
# 初始化项目
shecr init --data-path ./perf.data --risk-config ./.shecr/risk-custom.json

# 查看状态（显示 Risk 配置）
shecr status

# 运行分析
shecr trace issues
```

---

## 配置调试

### 查看当前配置

```bash
# 查看 wrap 配置状态
shecr status

# 输出示例:
# Data:   ./perf.data
# Script: scripts/perf_toolkit
# Freq:   19 Hz
# Risk:   config/risk-default.json
# Rules:  config/default-rules.json
```

### 验证 Risk 配置

```bash
# 测试不同模式
shecr trace issues --risk-config config/risk-default.json
shecr trace issues  # 使用默认配置
```

### 单元测试

```bash
# 运行 Risk 配置测试
python3 tests/unit/test_risk_display_config.py
```

---

## 配置变更记录

| 版本 | 变更内容 |
|------|---------|
| 3.3 | 新增 Attention Flags (X0/X1/X2/XA) 到 defaults.py |
| 3.2 | 重构为 dataclass 架构，添加 DisplayPresets |
| 3.0 | 新增 RiskDisplayConfig 配置系统 |
| 2.30 | wrap 脚本支持 `--risk-config` 和 `--rules-file` 参数 |

---

## 参考文档

| 文档 | 说明 |
|------|------|
| `docs/report/risk-display-customization.md` | Risk 显示自定义设计详解 |
| `docs/design/design-output.md` | 输出系统设计 |
| `docs/module/core/how/trace-mechanism.md` | Trace 机制设计 |
| `docs/process/commands-three-tier.md` | 命令行参数说明 |
