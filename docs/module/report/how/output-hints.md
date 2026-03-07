# Output Hints 设计文档

> 基于 SHECR Attention Steering 机制的统一输出提示规范
> 
> 版本: 1.0
> 更新日期: 2026-03-04

---

## 核心原则

### Label = Attention Weight

文本中出现的标签自动提升后续内容的处理优先级：

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<X0>` | Critical（阻塞级） | 锁竞争、单核饱和、高内核态，**必须追踪到根因** |
| `<X1>` | Major（重要级） | 进程风暴、负载不均衡、一般瓶颈 |
| `<X2>` | Minor（提示级） | 一般提示信息、背景噪音 |
| `<XA>` | Action（操作建议） | 具体的下一步操作命令 |

### 标签放置规则

1. **RISK 层**: `_risk.message` 必须包含最高优先级的 `<X0>` 标记
2. **数据行**: 进程/函数/核心行内嵌标签，便于快速扫描
3. **章节标题**: 重要发现章节前放置标签
4. **操作建议**: 所有可执行的建议前放置 `<XA>`

---

## sys-audit 输出 Hints 规范

### 1. Risk Message（必须包含）

```python
# 发现关键瓶颈时
risk.message = "<X0> 发现 3 个关键性能瓶颈: kubelet, netstat, python3"

# 仅发现次要问题时
risk.message = "<X1> 发现负载不均衡和进程风暴问题"

# 无严重问题时
risk.message = "<X2> 系统整体健康，未发现明显瓶颈"
```

### 2. 进程列表标记

```
### Top 进程 (按危害指数排序)

   1. <X0>kubelet             : 114.94% (sys:  16.46%) pids:   10 score: 175.6 [BOTTLENECK]
   2. <X1>netstat             : 243.87% (sys: 230.93%) pids: 2623 score: 406.7 [STORM]
   3. python3                 : 207.17% (sys:  72.87%) pids:  826 score: 261.9 [HEALTHY]
```

**标记规则**:
- `<X0>`: BOTTLENECK 诊断（Monopoly > 0.8）
- `<X1>`: STORM 诊断（Spawn Rate > 10/s）或 UNBALANCED 诊断
- 无标签: HEALTHY 诊断

### 3. 核心分布标记

```
### 核心分布 (Core Distribution)

<X0> 负载不均衡:
  - Imbalance Level: HIGH
  - Saturated Cores: [3, 5, 7]

<X0> Top Saturated:
  #1 CPU 3: 18522.36% (usr: 5612.83%)
  #2 CPU 5: 1122.57% (usr: 0.00%)
```

**标记规则**:
- `<X0>`: Imbalance Level 为 HIGH/CRITICAL 或存在 Saturated Cores
- `<X1>`: Imbalance Level 为 MODERATE

### 4. 特殊事件标记

```
### 特殊事件检测 (Sensitive Events)

<X1> [NETWORK_TC] 流量控制(TC)活动 - 可能影响网络延迟
  检测到 1 个相关进程:
    - tc: 7.2% (sys: 7.1%)
```

**标记规则**:
- `<X0>`: 严重影响性能的事件（如 MEMORY_OOM、CPU_THROTTLE）
- `<X1>`: 一般敏感事件（如 NETWORK_TC、DISK_IO）

### 5. 专家锚点标记

```
### 专家锚点 (Expert Anchors)

<X0> !! DETECTED_NOISY_NEIGHBOR: lsof_scanner !!
  - 2623 个进程高频活动，可能触发系统级资源竞争
  - 影响: 影响其他正常业务进程
  - 建议: 检查 lsof_scanner 的进程创建源头
```

**标记规则**:
- `<X0>`: NOISY_NEIGHBOR、QUOTA_VICTIM 等严重影响
- `<X1>`: 一般性专家发现

### 6. 后续操作标记

```
<XA> 后续操作:
  1. <XA> bottleneck-trace --comm kubelet 深度分析
  2. <XA> 检查 netstat 的进程创建源头
  3. <XA> trace issues 查看所有待处理 issue
```

---

## bottleneck-trace 输出 Hints 规范

### 1. Risk Message

```python
# 单核饱和时
risk.message = "<X0> netstat 单核饱和 (Monopoly=0.96, Throttle=82.5%)"

# 高内核态时
risk.message = "<X1> python3 高内核态占比 (kernel=65.3%)"
```

### 2. 瓶颈特征标记

```
### 瓶颈特征 (Bottleneck Profile)

<X0> 评估结果: 单核饱和 (Monopoly=0.96)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total CPU | 243.87% | <X0> 严重超载 |
| Kernel Ratio | 230.9% | <X0> 高内核态 |
| Monopoly | 0.96 | <X0> 单核独占 |
| CV | 0.00 | Balanced |
```

**标记规则**:
- `<X0>`: Monopoly > 0.8 或 Kernel Ratio > 50%
- `<X1>`: CV > 1.0 或 Spawn Rate > 10/s

### 3. 热点函数标记

```
### 热点函数 (Hotspots)

<X0> 锁竞争热点: _raw_spin_lock_bh
  - Self: 33.27% | Inclusive: 45.50%
  - Resource Tag: LOCK

#2 established_get_first: 44.06% (COMPUTE)
#3 native_queued_spin_lock_slowpath: 4.91% (LOCK)
```

**标记规则**:
- `<X0>`: 第一个热点是 LOCK 类型
- `<X0>`: 任何占比 > 40% 的热点
- `<X1>`: 占比 > 20% 的热点

### 4. 调用链标记

```
### 调用链溯源 (Call Chain Analysis)

<X0> 聚合调用链:
  [User_Logic:netstat] → tcp_get_idx -> tcp_seq_start -> seq_read
  - 影响: 热点函数 _raw_spin_lock_bh 的调用来源
```

**标记规则**:
- `<X0>`: 调用链分析发现明确的瓶颈路径
- `<X1>`: 一般调用链信息

### 5. 根因分析标记

```
### 根因分析 (Root Cause)

<X0> 第一推动力: netstat 单核瓶颈
  - 证据: Monopoly=0.96, 单进程独占 CPU
  - 机制: 单进程无法利用多核，导致串行化执行
  - 受害者: 业务请求处理延迟增加
```

**标记规则**:
- `<X0>`: 根因分析完成，第一推动力明确
- `<X1>`: 根因分析部分完成，需要更多信息

### 6. 建议操作标记

```
<XA> 建议操作:
  1. <XA> 执行 find-callers --target _raw_spin_lock_bh 溯源热点
  2. <XA> 执行 cluster-paths --comm netstat 分析内核调用
  3. <XA> 执行 sys-audit 查看系统全局状态
```

---

## 触发条件对照表

### sys-audit

| 场景 | 触发条件 | 标签 | 位置 |
|------|----------|------|------|
| 关键瓶颈发现 | 存在 BOTTLENECK 诊断 | `<X0>` | Risk message + 进程行 |
| 进程风暴 | Spawn Rate > 10/s | `<X1>` | 进程行 |
| 负载不均衡 | CV > 1.5 | `<X1>` | 进程行 |
| 核心饱和 | Imbalance Level = HIGH/CRITICAL | `<X0>` | 核心分布标题 |
| Noisy Neighbor | PID Count > 100 且影响其他 | `<X0>` | 专家锚点 |

### bottleneck-trace

| 场景 | 触发条件 | 标签 | 位置 |
|------|----------|------|------|
| 单核饱和 | Monopoly > 0.8 | `<X0>` | Risk message + 瓶颈特征 |
| 高内核态 | Kernel Ratio > 50% | `<X0>` | 瓶颈特征 |
| 锁竞争 | 热点为 LOCK 类型且排第一 | `<X0>` | 热点函数 |
| 负载不均衡 | CV > 1.5 | `<X1>` | 瓶颈特征 |
| 根因明确 | 诊断完成 | `<X0>` | 根因分析 |

---

## 代码实现要点

### 1. 标签常量（已存在）

```python
# config/defaults.py
class AttentionFlag:
    X0 = "<X0>"
    X1 = "<X1>"
    X2 = "<X2>"
    XA = "<XA>"
```

### 2. 辅助函数（已存在）

```python
# perf_toolkit/core/attention_tags.py
def x0(text: str) -> str:
    """添加 X0 标签"""
    return f"{AttentionFlag.X0} {text}"

def x1(text: str) -> str:
    """添加 X1 标签"""
    return f"{AttentionFlag.X1} {text}"

def xa(text: str, cmd: str = "") -> str:
    """添加 XA 标签"""
    if cmd:
        return f"{AttentionFlag.XA} {text}: {cmd}"
    return f"{AttentionFlag.XA} {text}"
```

### 3. 文本渲染器中的标签处理

```python
# perf_toolkit/core/text_output_adapter.py
# 确保标签与内容之间有空格，便于解析
lines.append(f"{AttentionFlag.X0} 单核饱和 (Monopoly={monopoly:.2f})")

# 进程行标签
lines.append(f"  {i:2d}. {attention_flag}{comm:20s}: {total:6.2f}% ...")
```

---

## 一致性检查清单

- [ ] Risk message 总是包含最优先级的标签
- [ ] `<X0>` 标记的内容在审计轮必须被检查
- [ ] `<XA>` 标记的操作建议必须可执行
- [ ] 标签与内容之间有一个空格
- [ ] 同一行不混合多个优先级标签
- [ ] 输出格式符合设计文档规范
