# Output Hints 实现总结

> 基于 SHECR Attention Steering 机制的输出提示改进

---

## 修改概述

本次改进基于 `docs/design/design-attention-steering.md` 中定义的 Attention Steering 机制，为 `sys-audit` 和 `bottleneck-trace` 命令设计了合理的 output hints。

### 核心标签定义

| 标签 | 含义 | 使用场景 |
|------|------|----------|
| `<X0>` | Critical（阻塞级） | 关键瓶颈、锁竞争、单核饱和、高内核态 |
| `<X1>` | Major（重要级） | 进程风暴、负载不均衡、次要热点 |
| `<X2>` | Minor（提示级） | 一般提示信息 |
| `<XA>` | Action（操作建议） | 可执行的建议命令 |

---

## 文件修改列表

### 1. `scripts/perf_toolkit/core/text_output_adapter.py`

#### 修改1: `_format_risk` 函数
- **位置**: 第 1008-1045 行
- **修改内容**: 确保 risk message 自动添加 attention tags
  - `critical` level 自动添加 `<X0>`（如果未包含）
  - `warning` level 自动添加 `<X1>`（如果未包含）
  - hint 自动添加 `<XA>`（如果未包含）

#### 修改2: `_render_bottleneck_trace_v2` - 瓶颈特征
- **位置**: 第 586-643 行
- **修改内容**: 
  - 添加评估结果标签（单核饱和/高内核态/负载不均衡）
  - 高内核态 (>50%) 标记为 `<X0>`
  - 高负载 (>阈值) 标记为 `<X1>`

#### 修改3: `_render_bottleneck_trace_v2` - 热点函数
- **位置**: 第 645-680 行
- **修改内容**:
  - 高占比热点 (>40%) 标记为 `<X0>`
  - 锁竞争热点标记为 `<X0>`
  - 次要热点 (>20%) 标记为 `<X1>`

#### 修改4: `_render_sys_audit_v2` - 进程列表
- **位置**: 第 808-870 行
- **修改内容**:
  - 新增 `_get_attention_flag` 辅助函数
  - BOTTLENECK 诊断 → `<X0>`
  - STORM 诊断 → `<X1>`
  - UNBALANCED 诊断 → `<X1>`

#### 修改5: `_render_sys_audit_v2` - 核心分布
- **位置**: 第 872-890 行
- **修改内容**:
  - HIGH/CRITICAL 不均衡 → `<X0>`
  - MODERATE 不均衡 → `<X1>`

#### 修改6: `_render_sys_audit_v2` - 专家锚点
- **位置**: 第 902-920 行
- **修改内容**:
  - NOISY_NEIGHBOR/QUOTA_VICTIM → `<X0>`
  - 其他锚点 → `<X1>`
  - 建议添加 `<XA>` 标签

---

## 输出效果对比

### sys-audit 改进前
```
   1. netstat             : 243.87% ... [BOTTLENECK]
   2. python3             : 207.17% ... [BOTTLENECK]
   3. kubelet             : 114.94% ... [BOTTLENECK]
```

### sys-audit 改进后
```
   1. <X0> netstat         : 243.87% ... [BOTTLENECK]
   2. <X0> python3         : 207.17% ... [BOTTLENECK]
   3. <X0> kubelet         : 114.94% ... [BOTTLENECK]
```

### bottleneck-trace 改进前
```
### 热点函数
#1 established_get_first: 44.06% (COMPUTE)
#2 _raw_spin_lock_bh: 33.27% (LOCK)
```

### bottleneck-trace 改进后
```
### 热点函数
<X0> 高占比热点: established_get_first
<X1> #2 _raw_spin_lock_bh: 33.27% (LOCK)
```

---

## 触发条件对照表

### sys-audit

| 场景 | 标签 | 触发条件 |
|------|------|----------|
| 关键瓶颈发现 | `<X0>` | Risk level = critical |
| BOTTLENECK 进程 | `<X0>` | diagnosis == BOTTLENECK |
| STORM 进程 | `<X1>` | diagnosis == STORM |
| UNBALANCED 进程 | `<X1>` | diagnosis == UNBALANCED |
| 核心严重不均衡 | `<X0>` | Imbalance Level = HIGH/CRITICAL |
| 核心中度不均衡 | `<X1>` | Imbalance Level = MODERATE |
| 敏感事件 | `<X1>` | 敏感进程活动 |
| 专家建议 | `<XA>` | 所有可执行建议 |

### bottleneck-trace

| 场景 | 标签 | 触发条件 |
|------|------|----------|
| 单核饱和 | `<X0>` | Monopoly > 0.8 |
| 高内核态 | `<X0>` | Kernel Ratio > 50% |
| 高占比热点 | `<X0>` | Self% > 40% |
| 锁竞争热点 | `<X0>` | Resource Tag = LOCK |
| 次要热点 | `<X1>` | Self% > 20% |
| 调用链聚合 | `<X0>` | 调用链分析完成 |
| 根因分析 | `<X0>` | 第一推动力明确 |
| 溯源建议 | `<XA>` | 可执行命令 |

---

## 设计原则

1. **标签即权重**: 看到 `<X0>` 就知道是关键问题
2. **分层标记**: Risk 层、数据行、章节标题都有标签
3. **行动导向**: `<XA>` 标记的都是可执行命令
4. **视觉层次**: 快速扫描时能立即发现关键问题

---

## 后续优化建议

1. **颜色支持**: 终端支持时，`<X0>` 显示红色，`<X1>` 显示黄色
2. **JSON 输出**: 在 JSON 格式中保留 attention_flag 字段
3. **可配置阈值**: 允许用户自定义标签触发阈值
4. **更多工具**: 将 output hints 扩展到其他分析工具
