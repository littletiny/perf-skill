# Output Hints 示例文档

> 展示改进后的 output hints 效果

---

## sys-audit 输出示例

### 场景1：多个关键瓶颈

```
[RISK-CRITICAL] <X0> 发现 4 个关键性能瓶颈 | #1 netstat: 243.9% CPU ...
## [SYSTEM_AUDIT]
> 策略: 自动降噪 + 危害排序，识别真瓶颈

### 系统指纹 (System Fingerprint)

State: CRITICAL_CONTENTION

### 特殊事件检测 (Sensitive Events)

<X1> [NETWORK_TC] 流量控制(TC)活动 - 可能影响网络延迟
  检测到 1 个相关进程:
    - tc: 7.2% (sys: 7.1%)

### Top 进程 (按危害指数排序)

   1. <X0> netstat             : 243.87% (sys: 230.93%) pids: 2623 score: 406.7 [BOTTLENECK]
   2. <X0> python3             : 207.17% (sys:  72.87%) pids:  826 score: 261.9 [BOTTLENECK]
   3. <X0> containerd-shim     :  96.01% (sys:  86.33%) pids:  240 score: 217.1 [BOTTLENECK]
   4. <X0> kubelet             : 114.94% (sys:  16.46%) pids:   10 score: 175.6 [BOTTLENECK]
   5.        dbatman             : 147.94% (sys:  38.99%) pids:  311 score: 105.2 [HEALTHY]

  共显示 5 / 17 个进程
  未显示进程 CPU: 441.19% / 1251.11%

### 核心分布 (Core Distribution)

<X1> 负载不均衡:
  - Imbalance Level: MODERATE

<XA> 后续操作:
  1. <XA> bottleneck-analyze --comm netstat 深度分析
  2. <XA> trace issues 查看所有待处理 issue
```

**Hints 说明**:
- `<X0>` 标记所有 BOTTLENECK 进程（关键瓶颈）
- `<X1>` 标记特殊事件和核心不均衡
- `<XA>` 标记可执行的建议操作
- HEALTHY 进程没有标签

---

### 场景2：进程风暴

```
[RISK-WARNING] <X1> 发现进程风暴: lsof_scanner (spawn_rate: 59.3/s)
## [SYSTEM_AUDIT]

### Top 进程 (按危害指数排序)

   1. <X0> app_logic           : 85.20% (sys:  15.30%) pids:    5 score: 185.6 [BOTTLENECK]
   2. <X1> lsof_scanner        : 288.26% (sys:  45.50%) pids: 2000 score: 150.3 [STORM]
   3. <X1> health_check        :  45.80% (sys:  12.20%) pids:  500 score:  80.2 [STORM]
```

**Hints 说明**:
- `<X0>` 标记 BOTTLENECK（关键瓶颈）
- `<X1>` 标记 STORM（进程风暴）

---

## bottleneck-analyze 输出示例

### 场景1：锁竞争热点

```
## [BOTTLENECK_TRACE]
> 目标进程: netstat

### 瓶颈特征 (Bottleneck Profile)

<X0> 评估结果: 高占比热点 (Self=44.06%)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total CPU | 244.36% | <X1> 高负载 |
| Kernel Ratio | 230.9% | <X0> 高内核态 |
| PID Count | 2623 | Multi |
| Monopoly | 0.00 | Normal |
| CV | 0.00 | Balanced |

### 热点函数 (Hotspots)
> 排序: 按 Self CPU 占比

<X0> 高占比热点: established_get_first
  - Self: 44.06% | Inclusive: 85.17%
  - Resource Tag: COMPUTE

<X1> #2 _raw_spin_lock_bh: 33.27% (LOCK)
<X1> #3 native_queued_spin_lock_slowpath: 4.91% (LOCK)
#4 _IO_vfscanf: 2.02% (COMPUTE)
#5 listening_get_next: 1.84% (COMPUTE)

### 调用链溯源 (Call Chain Analysis)
> 目标: established_get_first

<X0> 聚合调用链:
  [User_Logic:netstat] → tcp_get_idx -> tcp_seq_start -> seq_read
  - 影响: 热点函数 established_get_first 的调用来源

Top Callers:
  #1 [45.87%] tcp_get_idx -> tcp_seq_start -> seq_read -> proc_reg_read -> vfs_read
  #2 [39.30%] tcp_seq_next -> seq_read -> proc_reg_read -> vfs_read -> ksys_read

### 根因分析 (Root Cause)

<X0> 第一推动力: netstat 单核瓶颈
  - 证据: Monopoly=0.00, 单进程独占 CPU
  - 机制: 单进程无法利用多核，导致串行化执行
  - 受害者: 业务请求处理延迟增加

<XA> 建议操作:
  1. <XA> 执行 sys-audit 查看系统全局状态
```

**Hints 说明**:
- `<X0>` 标记：高占比热点(>40%)、高内核态(>50%)、调用链聚合、根因分析
- `<X1>` 标记：高负载(>阈值)、次要热点(>20%)
- `<XA>` 标记：可执行的建议

---

### 场景2：单核饱和

```
## [BOTTLENECK_TRACE]
> 目标进程: kubelet

### 瓶颈特征 (Bottleneck Profile)

<X0> 评估结果: 单核饱和 (Monopoly=0.96)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total CPU | 114.94% | <X1> 高负载 |
| Kernel Ratio | 16.5% | Normal |
| PID Count | 10 | Multi |
| Monopoly | 0.96 | <X0> 单核独占 |
| CV | 0.15 | Balanced |

### 热点函数 (Hotspots)

<X0> 锁竞争热点: __mutex_lock
  - Self: 45.50% | Inclusive: 62.30%
  - Resource Tag: LOCK

### 根因分析 (Root Cause)

<X0> 第一推动力: kubelet 单核瓶颈
  - 证据: Monopoly=0.96, 单进程独占 CPU
  - 机制: 单进程无法利用多核，导致串行化执行
  - 受害者: 业务请求处理延迟增加

<XA> 建议操作:
  1. <XA> 执行 find-callers --target __mutex_lock 溯源热点
  2. <XA> 执行 sys-audit 查看系统全局状态
```

**Hints 说明**:
- `<X0>` 标记单核饱和（Monopoly>0.8）
- `<X0>` 标记锁竞争热点
- `<XA>` 标记溯源建议

---

## 标签使用速查表

### sys-audit

| 场景 | 标签 | 示例 |
|------|------|------|
| 发现关键瓶颈 | `<X0>` | `<X0> 发现 3 个关键性能瓶颈` |
| BOTTLENECK 进程 | `<X0>` | `<X0> kubelet ... [BOTTLENECK]` |
| STORM 进程 | `<X1>` | `<X1> lsof ... [STORM]` |
| UNBALANCED 进程 | `<X1>` | `<X1> worker ... [UNBALANCED]` |
| 核心严重不均衡 | `<X0>` | `<X0> Saturated Cores: [3, 5]` |
| 核心中度不均衡 | `<X1>` | `<X1> 负载不均衡` |
| 敏感事件 | `<X1>` | `<X1> [NETWORK_TC] ...` |
| 专家建议 | `<XA>` | `<XA> bottleneck-analyze --comm xxx` |

### bottleneck-analyze

| 场景 | 标签 | 示例 |
|------|------|------|
| 单核饱和 | `<X0>` | `<X0> 评估结果: 单核饱和` |
| 高内核态 | `<X0>` | `<X0> 评估结果: 高内核态` |
| 高占比热点(>40%) | `<X0>` | `<X0> 高占比热点: func_name` |
| 锁竞争热点 | `<X0>` | `<X0> 锁竞争热点: _raw_spin_lock` |
| 次要热点(>20%) | `<X1>` | `<X1> #2 func_name: 25.30%` |
| 调用链聚合 | `<X0>` | `<X0> 聚合调用链:` |
| 根因分析 | `<X0>` | `<X0> 第一推动力: ...` |
| 溯源建议 | `<XA>` | `<XA> 执行 find-callers ...` |

---

## 设计原则

1. **标签即权重**: `<X0>` 表示最关键，`<X1>` 表示重要，`<XA>` 表示可执行
2. **视觉层次**: 快速扫描时，`<X0>` 行应最先引起注意
3. **行动导向**: 所有 `<XA>` 标记的建议都应可直接执行
4. **一致性**: 同一类型的发现使用相同的标签
