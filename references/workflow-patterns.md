# SPEAR 典型分析模式（附录）

> 本文档为 [methodology.md](./methodology.md) 的附录 A 提取，供快速参考。
>
> **完整方法论**：详见 [methodology.md](./methodology.md)
> **工具详情**：详见 [tools.md](./tools.md)

---

## 模式 A：单进程 CPU 高

**场景**：用户明确反馈"某个 PID 的 CPU 异常高"
**关键**：所有命令携带一致的目标参数

```bash
# Step 1: 确认瓶颈性质
spear get-comm-top --comm <name>
# 关注: Monopoly 是否 >0.8（单点瓶颈）

# Step 2: 深度追踪
spear bottleneck-trace --comm <name>

# Step 3: 热点溯源（如建议）
spear find-callers --target <热点函数> --comm <name>
```

---

## 模式 B：系统整体缓慢

**场景**：整个系统响应慢，无明确目标

```bash
# Step 1: 系统全景扫描
spear sys-audit

# Step 2: 根据输出选择方向
# - 发现 Monopoly 高危 → bottleneck-trace
# - 发现异常窗口 → detect-anomalies 提取时段深入
# - 发现进程风暴 → get-comm-top 看 Spawn Rate
```

---

## 模式 C：进程风暴

**场景**：疑似短生命周期进程大量创建

```bash
# Step 1: 检测风暴
spear get-comm-top
# 关注: Spawn Rate 列，>10/s 为风暴

# Step 2: 溯源父进程
spear find-callers --target fork --comm <storm-comm>

# Step 3: 分析触发源
spear cluster-paths --comm <storm-comm>
```

---

## 模式 D：负载不均衡

**场景**：`analyze-core-distribution` 显示 `imbalance_level=HIGH/CRITICAL`

```bash
# Step 1: 确认单核瓶颈
spear analyze-core-distribution --comm <name>

# Step 2: 分析原因
# sleeping 多 → 主动休眠问题
# active 多 → 锁竞争问题

# Step 3: 定向溯源
spear find-callers --target <调度函数或锁函数> --comm <name>
```

---

## 模式 E：高内核态分析

**场景**：kernel% 占比高

```bash
# Step 1: 内核热点识别
spear get-hotspots --comm <name>
# 关注: 内核空间热点函数

# Step 2: 语义聚类
spear cluster-paths --comm <name>
# 关注: Scheduling/Lock/Memory 相关模式

# Step 3: 溯源
spear find-callers --target <内核热点函数> --comm <name>
```

---

## 参考文档

- 📗 **完整方法论**: [methodology.md](./methodology.md) - 三层架构驱动的分析方法论
- 📘 **工具命令参考**: [tools.md](./tools.md) - 详细命令、参数
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
