# 工具链整合与增强设计意图文档

记录从工具冗余问题到精简整合的完整思考过程  
创建时间: 2026-03-02  
核心问题: 工具冗余、A掩盖B现象、诊断效率低下

---

## 背景与问题发现 (What Happened)

### 原始工具链的问题

perf-hunter 原始提供了 12 个诊断工具：

```
系统资源层: check-cpu-bottleneck, show-cpu-usage, analyze-core-distribution
进程组层:   get-process-top, get-comm-top, cluster-comm
热点识别层: get-hotspots, find-callers
模式聚类层: cluster-symbols, cluster-paths, detect-anomalies, count-process-variety
```

**真实使用场景中的痛点**:

1. **工具选择困难**: 面对性能问题时，不知道先用哪个工具
2. **输出重复冗余**: `get-process-top` 和 `get-comm-top` 都显示进程信息，只是聚合维度不同
3. **信息噪音大**: `lsof` 有 2000 个进程但负载均匀，`app_B` 只有 10 个进程但锁死单核，前者会完全掩盖后者
4. **缺乏诊断引导**: 工具输出原始数据，没有给出下一步该做什么的建议

### 典型案例: A掩盖B现象

```
[场景]
系统 CPU 打满，存在两个嫌疑人:
- A (lsof): 2000 个进程，占 400% CPU，均匀分布在所有核心
- B (app_worker): 10 个进程，占 100% CPU，独占 Core #7

[传统工具输出]
COMM           CPU%    PIDs
lsof           400%    2000  ← 太亮眼，吸引所有注意力
app_worker     100%    10

[问题]
用户被 A 的 "2000" 这个数字吸引，花费大量时间分析 lsof，
却忽略了真正导致业务延迟的 B (单核饱和造成请求排队)。
```

### 造成的后果

- **诊断方向错误**: 被大数字误导，排查无关的进程
- **时间浪费**: 需要手动运行多个工具才能拼凑完整画面
- **结论不完整**: 修复了 A 后，系统仍然卡顿，需要二次诊断

---

## 问题分析 (Why It Happened)

### 根本原因: 工具设计过于"原子化"

原始设计将每个诊断维度拆分为独立工具：

```
想看进程排行 → get-process-top
想看进程组排行 → get-comm-top
想看进程风暴 → count-process-variety
想看异常进程 → cluster-comm
```

这种设计的弊端:
1. **视角割裂**: 无法在一个视图中看到 "Count大但CV小" 或 "Count小但Monopoly高" 的对比
2. **缺乏智能**: 工具只输出数据，不做判断，用户需要自己解读
3. **联动困难**: 发现异常后需要手动复制 PID 去跑下一个工具

### 排序逻辑缺陷: 信任"总量"

```python
# 传统排序方式 (有问题)
sorted(processes, key=lambda x: x.cpu_percent, reverse=True)

# 结果: A (400%) 排在 B (100%) 前面，尽管 B 才是瓶颈
```

问题在于:
- **总量 ≠ 危害**: A 的 400% 是均匀分布的，不影响响应延迟；B 的 100% 是独占单核，直接阻塞请求
- **缺乏上下文**: 单纯看 CPU% 无法区分 "正常负载" 和 "异常竞争"

### 输出缺乏"专家洞察"

传统工具输出:
```
PID    COMM        CPU%
1234   lsof        0.2%
1235   lsof        0.2%
... (2000 行类似输出)
```

专家需要的输出:
```
[DIAGNOSIS] lsof: 2000 processes, uniform distribution (CV=0.02)
           → Background noise, NOT the bottleneck
[CRITICAL]  app_worker: PID 5678 occupies Core #7 100%
           → Single-core saturation, latency killer
```

---

## 设计目标 (Design Goals)

### 核心目标

| 目标 | 描述 |
|------|------|
| **去冗增效** | 合并重复工具，减少用户选择负担 |
| **自动降噪** | 自动识别并折叠"平庸的大多数" |
| **危害优先** | 按"危害指数"而非"绝对数值"排序 |
| **智能引导** | 自动推荐下一步诊断命令 |

### 设计原则

1. **由面到点**: 先给全景，再引导深入
2. **异常驱动**: 只高亮异常，隐藏正常状态
3. **组合输出**: 一个命令给出诊断结论，而非原始数据堆砌

---

## 方案设计 (Solution Design)

### 工具精简: 从 12 个到 6 个分析 + 2 个组合

| 原工具 | 处理方式 | 说明 |
|--------|----------|------|
| check-cpu-bottleneck | 合并到 analyze-core-distribution | 核心分布已包含整体利用率 |
| show-cpu-usage | 合并到 analyze-core-distribution | 同上 |
| get-process-top | 合并到 get-comm-top | 通过方差分析识别离群PID |
| cluster-comm | 合并到 get-comm-top | 聚合能力已内置 |
| count-process-variety | 合并到 get-comm-top | 转化为 Spawn_Rate 指标 |
| cluster-symbols | 合并到 cluster-paths | 符号聚类功能已整合到路径聚类 |

**精简后工具链**:

```
分析层核心工具（6个）:
├── get-hotspots              # 热点函数识别
├── find-callers              # 调用链溯源
├── detect-anomalies          # 时序异常检测
├── cluster-paths             # 调用路径聚类（含原 cluster-symbols）
├── analyze-core-distribution # 核心级负载分布
└── get-comm-top              # 进程组CPU分析（整合版）

组合层工具（2个）:
├── sys-audit                 # 系统审计
└── bottleneck-trace          # 瓶颈追踪

环境命令（4个）:
├── init                      # 初始化分析环境
├── use                       # 切换/指定分析目标
├── list                      # 列出可用资源
└── status                    # 查看当前状态

Trace系统（9个子命令）:
├── init, add, timeline, issues, audit
├── complete, reopen, finalize, export
```

### Enhanced get-comm-top 设计

#### 三维分析模型

```
┌─────────────────────────────────────────────────────────────┐
│                    Enhanced get-comm-top                     │
├─────────────────────────────────────────────────────────────┤
│  纵向聚合 (Comm)  │  横向离群 (Instance)  │  时间动态 (Rate)  │
├─────────────────────────────────────────────────────────────┤
│  Total_CPU%       │  CV (变异系数)         │  Spawn_Rate       │
│  业务模块画像      │  Monopoly (独占率)     │  进程产生速率     │
│  发现高消耗模块    │  识别离群PID          │  检测进程风暴     │
└─────────────────────────────────────────────────────────────┘
```

#### 核心指标定义

**CV (变异系数)**:
```
CV = σ / μ
其中 σ 是组内各进程 CPU 的标准差，μ 是平均 CPU

CV < 0.3:  负载均衡 (Balanced)
CV 0.3-1.0: 轻微不均 (Mild Variance)  
CV > 1.0:   严重不均 (Unbalanced) - 可能存在离群进程
```

**Monopoly (核心独占率)**:
```
Monopoly = Max_PID_CPU / Total_Group_CPU

Monopoly → 0:  负载均匀分布在多个进程
Monopoly → 1:  单个进程独占几乎所有资源

阈值: Monopoly > 0.8 标记为 [BOTTLENECK]
```

**Spawn_Rate (进程产生速率)**:
```
Spawn_Rate = 采样期间新产生进程数 / 采样时长(秒)

Spawn_Rate < 1/s:  正常
Spawn_Rate 1-10/s: 活跃
Spawn_Rate > 10/s: 进程风暴 (Storm)
```

#### 危害指数评分 (Impact Score)

```python
def calculate_impact_score(group):
    score = (
        group.total_cpu * 0.3 +           # 基础权重
        group.cv * 40 +                   # 离群增益
        group.monopoly * 50 +             # 独占增益
        group.spawn_rate * 5 +            # 动态增益
        (1 if group.is_kernel_heavy else 0) * 20  # 内核竞争增益
    )
    return score
```

**排序策略**: 按 Impact Score 降序，而非单纯按 CPU% 排序

#### 自动降噪逻辑

```python
def should_display(group):
    """决定是否在主界面显示该进程组"""
    return (
        group.total_cpu > 5% or           # CPU总量显著
        group.cv > 1.0 or                 # 分布严重不均
        group.monopoly > 0.8 or           # 单点极端离群
        group.spawn_rate > 10             # 进程风暴
    )

def classify_group(group):
    """分类并标记状态"""
    if group.monopoly > 0.8:
        return "BOTTLENECK", "Single-core saturation detected"
    elif group.spawn_rate > 10:
        return "STORM", "High fork rate detected"
    elif group.cv > 1.0:
        return "UNBALANCED", f"Outlier PID: {group.outlier_pid}"
    elif group.cv < 0.3 and group.total_cpu < 10%:
        return "BACKGROUND", "Folded into Others"
    else:
        return "HEALTHY", "Balanced workload"
```

### 组合诊断流设计

为了进一步降低使用门槛，设计两个"超级诊断流"：

#### sys-audit (系统审计)

**用途**: 快速画出全景图，识别"谁在变"和"谁在占核"

**工具链**:
```
detect-anomalies → analyze-core-distribution → get-comm-top
```

**输出示例**:
```
🚀 系统审计报告 (sys-audit)
================================================================================
[异常发现]
系统 CPU 突增 80%，呈现"单核饱和"特征（Core #7）。
时间戳: 2026-03-02T14:30:00+08:00

[嫌疑人比对]
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔴 Primary Suspect (Impact: 95/100)                                         │
│    COMM: app_worker                                                         │
│    CPU: 12% | Count: 10 | Monopoly: 0.92                                    │
│    诊断: 独占 Core #7，单核饱和造成请求排队                                   │
│    建议: bottleneck-trace --comm app_worker                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 🟡 Secondary Load (Impact: 45/100)                                          │
│    COMM: lsof                                                               │
│    CPU: 400% | Count: 2000 | CV: 0.02                                       │
│    诊断: 均匀分布的背景负载，非性能瓶颈                                       │
│    建议: 监控即可，优先处理 Primary Suspect                                 │
└─────────────────────────────────────────────────────────────────────────────┘

[已折叠] 45 个背景任务，总计 5% CPU (使用 --all 查看)
================================================================================
```

#### bottleneck-trace (瓶颈追踪)

**用途**: 自动定位瓶颈进程并分析其行为

**工具链**:
```
get-comm-top → get-hotspots → cluster-paths
```

**自动触发条件**:
- 当 get-comm-top 发现 Monopoly > 0.8 或 CV > 1.0 时
- 自动对离群 PID 执行 get-hotspots
- 自动对热点函数执行 cluster-paths

**输出示例**:
```
🔍 瓶颈追踪报告 (bottleneck-trace --comm app_worker)
================================================================================
[进程画像]
PID: 5678 | CPU: 98% (Core #7) | Status: Running

[内核行为指纹]
┌────────────────────────────────────────────────────────────────┐
│ Symbol                    │ %     │ Resource Tag               │
├────────────────────────────────────────────────────────────────┤
│ _raw_spin_lock            │ 65.2% │ LOCK_CONTENTION            │
│ try_to_wake_up            │ 12.1% │ SCHEDULER_OVERHEAD         │
│ __switch_to               │ 8.5%  │ CONTEXT_SWITCH             │
└────────────────────────────────────────────────────────────────┘

[诊断结论]
进程 5678 正在经历严重的锁竞争 (Lock Contention)。
65.2% 的时间花在自旋锁上，表明可能存在:
1. 多个线程竞争同一资源
2. 临界区过大
3. 锁粒度太粗

[建议操作]
1. 使用 'find-callers -p 5678 -s _raw_spin_lock' 查看调用者
2. 考虑使用读写锁替代互斥锁
3. 检查是否可以将临界区拆分为更小的片段
================================================================================
```

---

## 输出规范 (Output Specification)

### JSON 输出格式

```json
{
  "_risk": {
    "level": "high",
    "message": "Single-core saturation detected on Core #7",
    "hint": "Process app_worker (PID 5678) is monopolizing a single core",
    "action_required": "Run 'bottleneck-trace --comm app_worker' for detailed analysis"
  },
  "groups": [
    {
      "comm": "app_worker",
      "total_cpu": 12.0,
      "count": 10,
      "count_status": "NORMAL",
      "spawn_rate": 0.1,
      "cv": 0.15,
      "monopoly": 0.92,
      "impact_score": 95,
      "outlier_pid": 5678,
      "outlier_cpu": 98.0,
      "diagnosis": "BOTTLENECK",
      "diagnosis_desc": "Single-core saturation (Core #7)",
      "suggestion": "bottleneck-trace --comm app_worker"
    },
    {
      "comm": "lsof",
      "total_cpu": 400.0,
      "count": 2000,
      "count_status": "SURGE",
      "spawn_rate": 85.0,
      "cv": 0.02,
      "monopoly": 0.01,
      "impact_score": 45,
      "diagnosis": "BACKGROUND",
      "diagnosis_desc": "Uniform distributed load, not a bottleneck",
      "suggestion": "Monitor only"
    }
  ],
  "folded": {
    "count": 45,
    "total_cpu": 5.0,
    "note": "Use --all to view folded groups"
  }
}
```

### 文本输出格式

```
[COMM GROUP RANKING]  Sorted by: Impact Score
================================================================================
COMM           CPU%   COUNT   SPAWN/s  CV      MONOPOLY  IMPACT  DIAGNOSIS
================================================================================
app_worker     12.0   10      0.1      0.15    0.92!!    95!!    [BOTTLENECK]
                                                                     └─> PID:5678 occupies Core #7
                                                                     └─> Suggest: bottleneck-trace --comm app_worker

lsof           400.0  2000↑   85.0!!   0.02    0.01      45      [BACKGROUND]
                                                                     └─> Uniform load, monitor only

nginx          150.0  16      0.1      0.05    0.06      60      [HEALTHY]
                                                                     └─> Balanced workload
================================================================================
Legend:
  !! = Critical  ↑ = Growing trend  (Use --all to view 45 folded groups)

[Risk Assessment]
Level: HIGH
Message: Single-core saturation detected on Core #7
Hint: Process app_worker (PID 5678) is monopolizing a single core
Action: Run 'bottleneck-trace --comm app_worker' for detailed analysis
```

---

## 实施路径 (Implementation Roadmap)

### Phase 1: Enhanced get-comm-top (1-2 周)

- [x] 添加 CV (变异系数) 计算
- [x] 添加 Monopoly (独占率) 计算
- [x] 添加 Spawn_Rate (产生速率) 计算
- [x] 添加 Impact Score 排序
- [x] 添加自动降噪逻辑
- [x] 添加诊断标签和推荐命令

### Phase 2: 组合命令 (1 周)

- [x] 实现 `sys-audit` 命令
- [x] 实现 `bottleneck-trace` 命令

### Phase 3: 环境命令与 Trace 系统 (1 周)

- [x] 实现 `init`, `use`, `list`, `status` 环境命令
- [x] 实现 Trace 系统（9个子命令）

### Phase 4: 文档与测试 (1 周)

- [ ] 更新 SKILL.md 和 references/tools.md
- [ ] 编写测试用例
- [ ] 编写用户指南

---

## 验证方式 (Validation)

### 功能验证

使用测试数据验证以下场景:

| 场景 | 输入特征 | 期望输出 |
|------|----------|----------|
| A掩盖B | A:2000PIDs/400%CPU均匀, B:10PIDs/100%单核 | B排在首位，标记为BOTTLENECK |
| 进程风暴 | 某COMM的Spawn_Rate=100/s | 标记为STORM |
| 负载均衡 | 8个nginx进程，CPU均匀分布 | 标记为HEALTHY，不输出详细PID |
| 单点离群 | 10个python进程，1个占90% | 标记为UNBALANCED，输出离群PID |

### 效果验证

对比传统工具链和整合后的诊断效率:

| 指标 | 传统工具链 | 整合后 |
|------|-----------|--------|
| 首次运行命令数 | 3-5个 | 1个 (sys-audit) |
| 发现真正瓶颈的时间 | 10-30分钟 | < 2分钟 |
| 误诊率 (被A误导) | 高 | 低 |

---

## 总结 (Summary)

本设计通过以下方式解决原始工具链的问题:

1. **精简工具**: 从 12 个工具减少到 6 个核心分析工具 + 2 个组合命令
2. **增强核心**: Enhanced get-comm-top 通过 CV、Monopoly、Spawn_Rate 实现三维分析
3. **危害优先**: 引入 Impact Score 评分，解决 A 掩盖 B 的问题
4. **自动降噪**: 自动折叠"平庸的大多数"，只显示值得关注的进程组
5. **智能引导**: 每个输出都包含诊断结论和下一步建议
6. **完善生态**: 添加环境命令 (init/use/list/status) 和 Trace 系统支持完整工作流

最终目标: 让性能诊断从"数据堆砌"进化为"专家洞察"。

---

## 附录: 命令整合对照表

| 已移除命令 | 整合目标 | 说明 |
|-----------|----------|------|
| check-cpu-bottleneck | analyze-core-distribution | 整体CPU利用率检测已包含在核心分布分析中 |
| show-cpu-usage | analyze-core-distribution | CPU使用率展示已包含在核心分布分析中 |
| get-process-top | get-comm-top | 进程排行功能通过离群PID识别实现 |
| cluster-comm | get-comm-top | 进程组聚合能力已内置 |
| count-process-variety | get-comm-top | 进程多样性统计转化为 Spawn_Rate 指标 |
| cluster-symbols | cluster-paths | 符号聚类功能已整合到调用路径聚类 |
