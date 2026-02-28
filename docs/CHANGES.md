# SPEAR-perf-hunter 更新日志

> **格式说明**: 本文件按**时间顺序（从旧到新）**组织，便于从头到尾审视项目的演进过程。
>
> 阅读建议：从最早的版本开始，逐步了解每个版本的改进如何建立在之前的基础上。

---

# SPEAR-perf-hunter v0.7 更新日志

## 更新概览

本次更新针对 **PID 2573405 案例分析中暴露的"领域知识与工具联用割裂"** 问题进行深度反思和 Skill 重构。

**核心问题**: Agent 机械执行工具分析，完全割裂了领域知识（参数服务器应支持高并发），导致得出错误的初步结论。

---

## 1. 问题复盘：领域知识被遗忘

### 1.1 现象

**应有的领域知识**:
- 参数服务器是分布式训练核心组件，应支持高并发参数访问
- 应能水平扩展到多核（预期 800%+ CPU）
- 业界实现（PS-Lite, TensorFlow PS）都是并行架构

**实际的错误分析**:
```
看到数据: 144% CPU, 单核满载
↓
工具分析: find-in-table-with-lock 是热点
↓
得出结论: 锁竞争导致串行化
↓
建议优化: 优化锁结构
```

**缺失的关键质疑**: "为什么参数服务器会设计成单核瓶颈？"

### 1.2 根本原因

| 原因 | 说明 |
|------|------|
| "数据驱动"异化 | 误解"实证驱动"为"只看数据，不带先入之见" |
| 缺少领域知识激活 | Skill 从 Step 1 直接开始工具执行，没有业务背景识别 |
| 分析视角倒置 | 没有使用"预期 vs 现实"框架发现异常 |

---

## 2. Skill 重构：领域知识驱动框架

### 2.1 新增 Step 0: 业务领域理解

在启动任何工具分析之前，先完成：

```yaml
1. 应用类型识别
   - 进程名: parameter_serve
   - 推断: 参数服务器 (Parameter Server)
   - 确认: 查看调用栈中的 Thrift RPC 框架

2. 领域知识激活
   参数服务器的特征:
   - 用途: 分布式训练中的参数聚合与分发
   - 典型架构: 多线程/多进程，支持高并发访问
   - 预期性能: 800-1600% CPU (8-16 核并行)
   - 常见瓶颈: 网络 I/O、锁竞争、内存带宽

3. 建立预期基准
   - 预期 CPU: 800-1600%
   - 预期负载: 相对均衡分布在多核
   - 预期热点: 参数查找、梯度计算、网络序列化

4. 异常检测准备
   - 如果 CPU < 400%: 可能存在问题
   - 如果单核满载: 可能存在问题
```

### 2.2 改写工具联动：服务于假设验证

**从**: "get-hotspots → 识别自消耗热点"

**到**: "验证假设 → 使用工具检验领域预期"

**工具使用目的转变**:
- 不是为了"找热点"
- 而是为了"验证为什么达不到预期"

**示例改写**:
```yaml
# 验证负载分布是否符合预期
python3 scripts/perf_expert.py analyze-core-distribution \
  --pid 2573405 \
  --expected-balance "uniform"

思考: "72 核分布但 1 核满载，严重不符合参数服务器预期"
```

### 2.3 新增异常检测框架

**每一步后的检查清单**:

| 执行步骤 | 检查项 | 对比领域预期 | 异常判定 |
|---------|--------|-------------|---------|
| check-cpu-bottleneck | SINGLE_CORE_SATURATION? | 参数服务器应扩展到多核 | ⚠️ 严重异常 |
| get-hotspots | finish_task_switch 出现 | 不应是主要开销 | ⚠️ 异常 |
| find-callers | 看到 nanosleep | 应看到并发参数访问 | ⚠️ 严重异常 |

**规则**: 2+ 维度异常 → 必须深入挖掘根因

### 2.4 新增结论校验机制

**形成结论前必须回答**:

1. **业务合理性检查**
   - 结论是否符合该应用类型的应有表现？
   - 优化后是否能达到同类型应用的典型性能？

2. **量化验证**
   - 当前性能: 144% CPU
   - 优化后预期: ?
   - 领域基准: 800%+ (PS-Lite)
   - 差距是否完全消除？

3. **架构合理性检查**
   - 当前实现是否符合该应用类型的典型架构？
   - 建议的优化是否符合最佳实践？

### 2.5 新增领域知识库（附录）

```yaml
## 常见应用类型领域知识

### 参数服务器 (Parameter Server)
典型进程名: parameter_serve, ps_server
预期特征:
  CPU: 应能扩展到 800%+
  负载分布: 相对均衡
  热点: 参数查找、梯度计算、序列化
常见瓶颈:
  - 全局锁 (不符合设计预期)
  - 网络 I/O
  - 内存带宽

### Web 服务器
典型进程名: nginx, httpd
预期特征:
  CPU: 多核均衡负载
常见瓶颈:
  - worker_processes 配置不足
  - 阻塞操作

### 数据库
典型进程名: mysqld, postgres, redis-server
常见瓶颈:
  - 锁竞争
  - 慢查询
  - WAL/Redo 日志刷盘
```

---

## 3. 经验教训

### 对个人执行

1. **工具是手段，领域知识才是灵魂**
   - 不要机械执行工具
   - 始终带着"这是否符合应有表现"的质疑

2. **建立"预期 vs 现实"框架**
   - 分析前建立领域预期
   - 每一步对比工具输出与预期
   - 发现异常立即深入

3. **前置领域知识激活**
   - 识别应用类型
   - 激活应有特征
   - 建立性能基线

### 对 Skill 设计

1. **增加 Step 0: 领域知识激活**
   ```
   识别应用类型 → 激活领域知识 → 建立预期基准 → 带着预期分析数据
   ```

2. **改写工具描述**
   ```
   从: "get-hotspots: 识别热点"
   到: "get-hotspots: 验证实际热点是否符合领域预期"
   ```

3. **增加结论校验**
   - 是否符合该应用类型的应有表现？
   - 优化后是否能达到同类型应用的典型性能？

---

## 4. 如果重来 - 正确的分析流程

```
Phase 0: 领域知识激活
  ↓ 识别 parameter_serve → 激活参数服务器知识 → 建立 800%+ CPU 预期

Phase 1: 假设形成
  ↓ 假设1: 配置问题 / 假设2: 架构缺陷 / 假设3: 调度问题 / 假设4: 资源限制

Phase 2: 工具联动验证假设
  ↓ get-hotspots → find-callers → analyze-core-distribution

Phase 3: 综合分析
  ↓ 全局锁 + 主动休眠 = 架构级缺陷，不符合参数服务器定位

Phase 4: 结论形成
  ↓ "当前实现存在架构级缺陷，需要的不是微调优化，而是架构重构"
```

---

更新日期: 2026-02-28

版本: v0.7

反思深度: 极高

教训: 工具是手段，领域知识才是灵魂

---
# v2.0 之前的早期迭代

## v1.0 → v2.0 演进背景

### 触发事件: PID 2573405 案例分析 (2026-02-28)

**原始问题**: 某台机器上 parameter_server 进程 CPU 使用率不够高，但其他实例正常。

**暴露的 Skill 设计缺陷**:

| 缺陷类型 | 问题描述 | 改进方案 |
|---------|---------|---------|
| 工具孤立呈现 | 工具被列举为表格，未作为工作流环节 | 建立 Step 1→6 的流程链路 |
| 关键链接缺失 | `get-hotspots` → `find-callers` 关联不明确 | 增加"发现调度类热点必须追溯"的强制链路 |
| `--auto-target` 副作用 | 便利功能掩盖针对性追溯价值 | 文档强调 `--target` 在特定场景的必要性 |
| 诊断决策树缺失 | 只有工具列表，没有条件分支 | 新增约 180 行诊断决策树 |

### 关键改进实施

#### 1. 诊断决策树新增

**内容**: 约 180 行的 Step 1-6 流程图

```
Step 3: 热点识别 (get-hotspots --sort-by self)
    ├── 发现: 调度类函数高占比 → Step 4-a: 调度开销溯源
    ├── 发现: 内存操作类函数高占比 → Step 4-b: 内存开销溯源
    └── ...

Step 4-a: 调度开销溯源 (find-callers --target <调度函数>)
    ├── 发现: 定时器睡眠类 → 追溯睡眠触发点
    ├── 发现: IO等待类 → 检查IO并发配置
    └── 发现: 同步原语等待类 → 追溯锁持有者
```

**文件变更**: `SKILL.md` - 新增"诊断决策树"章节

#### 2. 工具链关联明确化

**核心链路建立**:
- 明确 `get-hotspots --sort-by self` → `find-callers --target <热点>` 的分析链路
- 使用类别描述（调度类、内存操作类）而非具体函数名
- 提供条件触发的工具选择指南

#### 3. `--auto-target` 警示

**新增文档提示**:
> "`--auto-target` 适用于初步探索。当发现特定类别热点（如调度、内存）时，**必须**使用 `--target` 针对性追溯。"

**原因**: PID 2573405 案例中，`nanosleep` 不是热点（self 低），未被 `--auto-target` 选中，导致误以为 `find-callers` 无法解决而转向 `grep`。

#### 4. 从错误方法到最优路径

**原错误方法**:
```bash
check-cpu-bottleneck → show-cpu-usage → get-hotspots --sort-by self
grep "nanosleep"  # ❌ 违反"工具优先"原则，无统计置信度
```

**改进后的最优化路径**:
```bash
# Step 1: 环境边界
check-cpu-bottleneck --pid 2573405

# Step 2: 热点识别（自消耗视角）
get-hotspots --sort-by self
# 输出: finish_task_switch 3.92% self (调度切换开销)

# Step 3: 热点溯源（关键改进！）
find-callers --target finish_task_switch
# 输出: 66.67% 来自 nanosleep 路径，33.33% 来自 epoll_wait 路径

# Step 4: 深层归因
find-callers --target __GI___nanosleep
# 输出: 追溯到 DoubleHash::FindInTableWithLock (57.14%)
```

### 经验教训总结

**对个人执行**:
1. 工具优先原则: 遇到缺口先质疑工具配置，再考虑裸命令
2. 穷尽工具能力: 尝试 `--target`, `--custom-rules` 等扩展参数
3. 建立链路思维: 明确 A 工具输出 → B 工具输入的关联
4. 选择正确入口: `finish_task_switch` 是调度问题的自然入口

**对 Skill 设计**:
1. 工具不应孤立呈现: 应作为工作流环节，明确前置条件和输出
2. 必须提供决策树: "如果看到 X，就做 Y" 的条件指引
3. 便利功能需警示: `--auto-target` 应提示其局限性

---
# SPEAR-perf-hunter v2.0 更新日志

## 更新概览

**本次更新是一个架构级转折点：彻底放弃严格的线性 SOP 流程，转向"多路径并行假设驱动"模式。**

在 v0.7 尝试通过增加 Step 0（领域知识激活）来解决问题后，分析仍然失败了。根本原因是：**过于严格的线性决策树（Step 1→2→3→4→5）限制了分析灵活性**，导致：
- 过早收敛：看到 FindInTableWithLock 就认定是锁竞争
- 遗漏线索：看到 finish_task_switch 却没有溯源
- 无法并行验证多条假设

**核心转变**: 从"流程驱动"转向"假设驱动"，给 Agent 足够的自由度。

---

## 1. 为什么放弃严格 SOP？

### 1.1 严格 SOP 的问题

**原来的线性决策树**:
```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5
(单一串联路径)
```

**实际需要的分析**:
```
Step 1: 环境边界判定
    ↓
启动多条假设路径并行验证
    ├─→ 路径 A: 锁竞争假设
    │       tools: [get-hotspots, find-callers]
    │       falsify_condition: 热点中无锁函数
    │
    ├─→ 路径 B: 调度问题假设
    │       tools: [analyze-core-distribution, find-callers finish_task_switch]
    │       falsify_condition: finish_task_switch 来自抢占而非休眠
    │
    └─→ 路径 C: 配置问题假设
            tools: [检查 ThreadManager 配置]
            falsify_condition: 线程数配置合理
    ↓
对比证据强度 → 收敛结论
```

### 1.2 关键失败点复盘

| 时间点 | 决策 | 结果 | 原因 |
|--------|------|------|------|
| T4 | 看到 finish_task_switch 3.92% | **没有溯源** | 决策树没有强调"调度函数必须追溯" |
| T5 | 选择 find-callers targets | **遗漏 finish_task_switch** | 过早收敛到锁竞争假设 |
| T6 | cluster-symbols --custom-rules 报错 | **转向 grep** | 没有 workaround，流程中断 |

**根本问题**: 线性决策树无法支持"竞争性假设并行验证"。

---

## 2. 架构重构：从 SOP 到假设驱动

### 2.1 放弃线性决策树

**废除**:
```yaml
# 废除的线性流程
Step 1: 环境边界判定 → Step 2: 进程行为检查 → Step 3: 热点识别 → ...
```

**改为**:
```yaml
# 新的假设驱动流程
Phase 1: 信息收集（快速扫描）
Phase 2: 假设生成（发散，至少 3 条竞争性假设）
Phase 3: 并行验证（多条路径同时推进）
Phase 4: 证据对比（对比各假设的证据强度）
Phase 5: 收敛结论（证伪 N-1 条后才确认）
```

### 2.2 给 Agent 的自由度

| 维度 | 原来 (SOP) | 现在 (假设驱动) |
|------|-----------|----------------|
| 工具选择 | 严格按 Step 选择 | 根据假设需要灵活选择 |
| 分析顺序 | 固定 1→2→3→4→5 | 多条路径并行 |
| 收敛时机 | 发现热点后立即深入 | 至少验证 3 条假设后才能收敛 |
| 工具组合 | 预设组合 | 根据假设自定义组合 |

### 2.3 竞争性假设执行指南（新增）

```markdown
## 如何执行竞争性假设

当发现 SINGLE_CORE_SATURATION 时:

1. **列出所有可能假设** (至少 3 条)
   - 假设 A: 锁竞争导致串行化
   - 假设 B: 调度压制导致无法运行
   - 假设 C: 配置问题导致线程数不足

2. **为每条假设设计验证实验**
   - 假设 A: get-hotspots → find-callers 追溯锁函数
   - 假设 B: analyze-core-distribution → find-callers finish_task_switch
   - 假设 C: 检查 ThreadManager 配置

3. **并行执行所有验证**
   - 不要等一条路径走完再走另一条
   - 同时收集各路径的证据

4. **记录每条假设的证据强度**
   - 假设 A 证据: FindInTableWithLock 占比 X%
   - 假设 B 证据: finish_task_switch 来自 nanosleep 占 Y%
   - 假设 C 证据: 线程配置为 Z

5. **证伪后再收敛**
   - 只有当 N-1 条假设被证伪后，才能确认第 N 条
   - 如果多条假设都有证据，需要综合优化

**不要**:
- 看到一条证据就立即收敛
- 忽略与主假设矛盾的证据
- 机械执行预设流程
```

---

## 3. 关键工具增强

### 3.1 新增 analyze-core-distribution

**用途**: 解决"单核饱和 + 负载不均衡"场景的工具缺失问题

```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --pid 2573405 \
  --show-sleep-reasons
```

**解决什么问题**:
- 按核心分析负载分布
- 区分锁竞争 vs 主动休眠
- 自动检测 SINGLE_CORE_SATURATION 模式

### 3.2 修复 cluster-symbols --custom-rules

**问题**: TypeError: unhashable type: 'list'

**修复**: 支持 pattern 为列表或字符串格式

```python
# 支持 pattern 为列表或字符串
if isinstance(pattern, list):
    pattern_str = '|'.join(pattern)
else:
    pattern_str = pattern
```

### 3.3 完善关键决策原则表

**新增条目**:

| 观察症状 | 必选工具链 | 验证目标 |
|---------|-----------|---------|
| SINGLE_CORE_SATURATION | **同时执行** A/B/C 三条路径 | 区分锁/调度/配置问题 |
| finish_task_switch 出现 | `find-callers finish_task_switch` | 主动休眠 vs 被动抢占 |
| 72 核分布但 1 核满载 | `analyze-core-distribution` | 锁竞争 vs 主动退避 |

---

## 4. 新旧模式对比

### 4.1 同一个案例的不同分析方式

**案例**: PID 2573405, SINGLE_CORE_SATURATION, finish_task_switch 出现

**旧模式 (失败)**:
```
check-cpu-bottleneck → count-process-variety → get-hotspots → find-callers FindInTableWithLock
↓
过早收敛: "锁竞争导致串行化"
```

**新模式 (正确)**:
```
check-cpu-bottleneck
    ↓
启动三条假设路径:
  ├─→ 路径 A (锁竞争): get-hotspots → find-callers FindInTableWithLock
  ├─→ 路径 B (调度问题): analyze-core-distribution → find-callers finish_task_switch
  └─→ 路径 C (配置问题): 检查 ThreadManager 配置
    ↓
证据对比:
  - 路径 A: FindInTableWithLock 确实高，但只能解释部分问题
  - 路径 B: **发现 finish_task_switch 66.67% 来自 nanosleep！**
  - 路径 C: 线程配置正常
    ↓
综合结论:
  "全局锁 + 应用层主动休眠 叠加导致伪单线程，需要架构重构"
```

### 4.2 责任分配反思

| 问题 | 旧模式责任 | 新模式改进 |
|------|-----------|-----------|
| 过早收敛 | 40% 决策树引导 | 竞争性假设强制并行验证 |
| 遗漏调度线索 | 50% 决策原则缺失 | 关键症状→必选工具链映射 |
| 过度使用 grep | 70% 工具缺失/bug | 新增专用工具 |

---

## 5. 经验教训

### 对 Skill 设计的核心认知转变

1. **流程是手段，不是目的**
   - SOP 的目的是确保不遗漏关键步骤
   - 但过于严格的 SOP 会抑制灵活思考

2. **假设驱动优于流程驱动**
   - 不要问"Step 3 应该用什么工具"
   - 要问"验证这个假设需要什么证据"

3. **给 Agent 自由度 ≠ 放弃规范**
   - 关键检查点仍然强制（如 finish_task_switch 必须溯源）
   - 但工具组合和顺序由 Agent 根据假设决定

4. **竞争性假设需要执行指南**
   - 不只是说"保持双线思考"
   - 要提供"如何启动多条路径"的具体方法

---

更新日期: 2026-02-28

版本: v0.8

核心转变: 从"严格 SOP"到"假设驱动"

---

# 历史版本（v2.1 及之前）

## 更新概览

本次更新包含以下改进：
1. **Bug 修复**: `cluster-symbols --custom-rules` 现在支持列表格式的规则
2. **新功能**: 新增 `analyze-core-distribution` 工具，支持核心级负载分布分析
3. **文档更新**: 重构 SKILL.md 为规则驱动的泛化方法论

---

## 1. Bug 修复: cluster-symbols --custom-rules

### 问题
当使用 `--custom-rules` 参数传入 JSON 对象，且值为列表时会报错：
```bash
TypeError: unhashable type: 'list'
```

### 修复
修改文件: `scripts/perf_toolkit/analysis/clusters.py`

修复内容: 支持 pattern 为列表或字符串格式
```python
# 支持 pattern 为列表或字符串
if isinstance(pattern, list):
    pattern_str = '|'.join(pattern)
else:
    pattern_str = pattern
if re.search(pattern_str, sym):
    matched_groups.add(group)
```

### 使用方式
```bash
# 方式 1: 字符串格式 (正则表达式)
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --pid 2573405 \
  --custom-rules '{"SCHEDULING": "schedule|nanosleep"}'

# 方式 2: 列表格式 (自动转换)
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --pid 2573405 \
  --custom-rules '{"SCHEDULING": ["schedule", "nanosleep"]}'
```

---

## 2. 新功能: analyze-core-distribution

### 用途
分析进程在各 CPU 核心的负载分布，识别：
- 负载不均衡程度 (单核饱和 vs 均衡分布)
- 线程状态分布 (active vs sleeping)
- 各核心热点函数

### 典型场景
解决 PID 2573405 案例中暴露的问题：
- 72 个核心都有线程分布，但 1 个核心满载，其他几乎空闲
- 需要区分"锁竞争"vs"主动休眠"导致的瓶颈

### 使用方法
```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data perf.script \
  --pid 2573405
```

### 输出示例
```json
{
  "summary": {
    "total_cores_with_activity": 72,
    "max_utilization_pct": 97.45,
    "min_utilization_pct": 0.21,
    "avg_utilization_pct": 2.0,
    "imbalance_level": "CRITICAL",
    "imbalance_description": "单核满载，其他核心几乎空闲"
  },
  "cores": [
    {
      "cpu_id": 40,
      "utilization_pct": 97.45,
      "states": {"active": 2}
    },
    {
      "cpu_id": 81,
      "utilization_pct": 9.06,
      "states": {"sleeping": 1, "active": 1}
    }
  ],
  "patterns": [
    {
      "type": "SINGLE_CORE_SATURATION",
      "suggestion": "检查锁竞争、CPU亲和性绑定或应用层主动休眠"
    }
  ]
}
```

### 关键指标
- `imbalance_level`: LOW/MEDIUM/HIGH/CRITICAL
- `imbalance_ratio`: 最大利用率 / 平均利用率
- `states`: sleeping (休眠) / active (活跃)
- `patterns`: 自动检测到的异常模式

---

## 3. 文档重构 —— 从决策树到规则驱动的方法论

### 3.1 SKILL.md 改进

**从**: 决策树驱动的步骤指南 (Step 1→2→3→4→5)

**到**: 规则驱动的方法论框架

**核心变化**:
1. **前置领域知识激活** (Step 0)
   - 强调先建立预期，再验证差距
   - 应用类型识别 → 建立性能基线 → 对比现实

2. **竞争性假设并行验证**
   - 至少同时维护 3 条假设
   - 发散→探索→收敛的循环

3. **异常驱动分析**
   - 只有"预期 vs 现实"有差距才深入
   - 工具服务于假设验证

4. **关键检查点**
   - 发现调度函数 → 必须溯源
   - 发现负载不均衡 → 必须用 `analyze-core-distribution`
   - 发现锁函数 → 必须评估粒度

### 3.2 决策树取消说明

**取消原因**:
- **过于死板**: 决策树的严格分支结构（"如果 A 则做 B"）导致模型灵活度严重受限
- **难以应对复杂场景**: 实际性能问题往往是多因素交织，难以用简单的条件分支覆盖
- **抑制探索性思维**: 固定的流程限制了 Agent 根据具体场景灵活调整分析策略的能力

**替代方案**:
- 采用**规则驱动 + 启发式指导**的柔性框架
- 保留关键检查点作为"必须遵守的约束"
- 提供典型分析模式作为参考而非强制路径
- 强调"发散→探索→收敛"的循环思维

### 3.3 tools.md 改进

1. **新增工具**: `analyze-core-distribution` 详细说明
2. **新增模式**: "负载不均衡分析"工作流
3. **修复说明**: `--custom-rules` 支持列表格式

---

## 工具联动改进

### 原有模式
```
# 模式 1: 探索式诊断
check-cpu-bottleneck → cluster-paths → find-callers --auto-target

# 模式 2: 定向分析
get-hotspots → find-callers --target <func>
```

### 新增模式
```
# 模式 4: 负载不均衡分析
check-cpu-bottleneck → analyze-core-distribution → find-callers --target <调度函数>
```

---

## 文件变更清单

### 修改的文件
1. `scripts/perf_toolkit/analysis/clusters.py`
   - 修复 `--custom-rules` 列表格式支持

2. `scripts/perf_expert.py`
   - 导入 `cmd_analyze_core_distribution`
   - 添加 `analyze-core-distribution` 子命令
   - 添加命令映射

3. `SKILL.md`
   - **重构为规则驱动的泛化方法论**（取消决策树）
   - 添加 `analyze-core-distribution` 说明
   - 添加工具参考附录

4. `references/tools.md`
   - 添加 `analyze-core-distribution` 详细说明
   - 添加 `--custom-rules` 使用示例
   - 更新工具清单和工作流

### 新增的文件
1. `scripts/perf_toolkit/analysis/core_distribution.py`
   - 新工具实现

2. `CHANGES.md` (本文件)
   - 变更日志

---

## 验证测试

### cluster-symbols 修复验证
```bash
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --pid 2573405 \
  --custom-rules '{"SCHEDULING": ["schedule", "nanosleep"]}'
# 输出正常，无 TypeError
```

### analyze-core-distribution 功能验证
```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data perf.script \
  --pid 2573405
# 正确识别 SINGLE_CORE_SATURATION 和 WIDE_DISTRIBUTION_LOW_UTIL 模式
```

---

## 使用建议

### 对于单核瓶颈场景
1. 使用 `check-cpu-bottleneck` 确认瓶颈类型
2. 使用 `analyze-core-distribution` 分析负载分布
   - 如果 `imbalance_level` = CRITICAL → 检查调度/休眠问题
   - 如果多核都有负载但低 → 检查锁竞争
3. 使用 `find-callers` 溯源热点函数

### 对于负载不均衡场景
1. 使用 `analyze-core-distribution` 获取全貌
2. 关注 `patterns` 字段的自动检测
3. 结合 `cluster-symbols` 分析调度行为
4. 使用 `--custom-rules` 自定义关注特定模式

---

更新日期: 2026-02-28

版本: v2.1

---

# SPEAR-perf-hunter v2.2 更新日志

## 更新概览

本次更新包含以下改进：
1. **新功能**: 新增 `get-comm-top` 工具，专门用于识别"大量同类进程吃满资源，但单个进程占用少"的场景
2. **重构 tools.md**: 采用 Top-Down + Bottom-Up 混合分析流程组织文档

---

## 1. 新功能: get-comm-top

### 用途
分析按进程名（comm）聚合的 CPU 消耗排名，专门识别以下场景：
- Worker pool 过度扩容（大量 worker 每个消耗少量 CPU）
- 连接风暴（每个连接一个进程/线程）
- 微服务实例过度分片
- 进程泄漏（不断创建新进程）

### 与现有工具的区别
| 工具 | 分析维度 | 适用场景 |
|------|---------|---------|
| `get-process-top` | 单个进程 | 找单个高消耗进程 |
| `cluster-comm` | 进程组汇总 | 简单聚类，无排名 |
| `get-comm-top` | 进程组排名 + 密度分析 | **大量小进程集体高消耗** |

### 核心指标
- `pid_count`: 该 comm 的进程数量
- `aggregate_cpu_utilization_pct`: 聚合 CPU 利用率
- `avg_cpu_per_process_pct`: 单进程平均 CPU
- `density_index`: 密度指数（总CPU / 进程数），**越小表示过度分片越严重**
- `is_many_small_pattern`: 是否符合"大量小进程"模式

### 自动检测模式
- `MANY_SMALL_PROCESSES`: 聚合>10% 且 单进程<1% 且 进程数≥5
- `UNEVEN_LOAD_DISTRIBUTION`: 同类型进程间负载不均
- `EXTREME_PROCESS_PROLIFERATION`: 进程数极多但单进程贡献极低

### 使用方法
```bash
# 基本使用
python3 scripts/perf_expert.py get-comm-top --data perf.script

# 按密度指数排序（找过度分片最严重的）
python3 scripts/perf_expert.py get-comm-top --data perf.script --sort-by-density

# 过滤特定进程名
python3 scripts/perf_expert.py get-comm-top --data perf.script --comm worker
```

### 文件变更
1. `scripts/perf_toolkit/analysis/comm_top.py` - 新工具实现
2. `scripts/perf_expert.py` - 添加子命令和参数解析
3. `references/tools.md` - 添加工具说明和使用模式

---

## 2. 重构 tools.md —— Top-Down + Bottom-Up 混合分析模式

### 修改理由
原 tools.md 采用平铺式的工具列表组织方式，缺乏结构化的分析流程指导。实际性能分析需要结合：
1. **Top-Down 宏观切入**: 从系统级概览建立上下文
2. **Bottom-Up 微观溯源**: 从热点函数逐层深入

### 修改内容
1. **新增分析流程总览图**: 清晰展示 7 个分析阶段及其关系
2. **按分析阶段重组工具**: Phase 1→7 的渐进式分析路径
3. **新增语义分析章节**: 根据符号名猜测 workload 和技术领域
4. **新增专家经验查缺补漏章节**: 关键信号检查清单和全局一致性检查
5. **新增典型分析模式**: 4 种快捷路径（单进程高 CPU、系统缓慢、进程风暴、负载不均衡）
6. **保留原有内容**: 内核函数规范化、CPU 利用率计算、可靠性评估、通用参数

### 文件变更
- `references/tools.md`: 完全重构，从 392 行扩展为结构化文档

---

更新日期: 2026-02-28

版本: v2.2

---

# SPEAR-perf-hunter v2.3 更新日志

## 更新概览

本次更新包含以下改进：
1. **文档完善**: 重构 AGENTS.md，添加完整的目录结构说明
2. **CLI 帮助增强**: 为所有子命令的复杂参数添加详细说明和使用示例

---

## 1. 重构 AGENTS.md

### 修改理由
原 AGENTS.md 仅包含简单的开发约定，缺乏项目结构说明，新开发者难以快速理解代码组织。

### 修改内容
1. **添加项目简介**: 说明 perf-hunter 的用途和核心特性
2. **添加目录结构**: 完整的树状目录说明，标注每个文件的用途
3. **添加子命令清单**: 表格形式列出所有 14 个子命令及其用途
4. **添加输入数据格式说明**: 如何生成 perf script 输出
5. **保留原有开发约定**: 修改记录规范、代码规范、版本控制

### 文件变更
- `AGENTS.md`: 完全重构，从 3 行扩展到结构化文档

---

## 2. CLI 帮助信息增强

### 修改理由
原 --help 输出对复杂参数缺乏详细说明，用户难以理解：
- `--cpu-limit` 的格式不明确
- `--custom-rules` 的 JSON 格式没有示例
- `--target` 不知道可以指定哪些函数
- `--spike-threshold`、`--storm-pid-threshold` 等阈值参数的意义不清楚

### 修改内容

#### 2.1 主命令 epilog 增强
添加使用示例和输入数据格式说明：
- 5 个典型使用示例（hotspots、bottleneck、find-callers、anomalies、core-distribution）
- 输入数据生成方法（perf record / perf script）
- v2.0 移除 --freq 参数的说明

#### 2.2 check-cpu-bottleneck 的 --cpu-limit
原："CPU limit in cores (e.g., '0.1c', '2c', '0.5' for 0.5 cores)"

新："CPU limit in cores for cgroup environments. Examples: '0.1c' (0.1 core), '2c' (2 cores), '0.5' (0.5 cores). Default: 0 (no limit check)"

#### 2.3 cluster-symbols 的 --custom-rules
原："JSON format regex rules"

新："JSON format custom rules. Example: '{"MyPattern": [{"pattern": "my_func_.*", "weight": 1.0}]}'. Rules are list of {pattern, weight} objects."

#### 2.4 find-callers 的 --target
原："Target function name to trace (e.g., 'pthread_mutex_lock'). If not provided, use --auto-target"

新："Target function name to trace. Examples: 'pthread_mutex_lock', 'sched_yield', 'malloc'. Use with --min-ratio to filter significant callers. If not provided, use --auto-target to trace top hotspots automatically"

#### 2.5 detect-anomalies 的阈值参数
- `--window-size`: 添加滑动窗口分析说明，解释窗口大小对检测的影响
- `--spike-threshold`: 解释 spike 检测机制，说明变化比率范围
- `--min-utilization`: 解释最小利用率阈值的作用

#### 2.6 count-process-variety 的 storm 阈值
- `--storm-pid-threshold`: 解释进程风暴检测机制，说明 PID 数量的意义
- `--storm-ratio-threshold`: 解释 samples_per_pid 比率的意义，低值表示短生命周期

### 文件变更
- `scripts/perf_expert.py`:
  - 更新主 parser 的 epilog
  - 更新 6 个子命令的参数 help 文本
  - 为复杂参数添加 metaclass 以改善显示

---

## 验证测试

### AGENTS.md 验证
```bash
cat AGENTS.md
# 输出包含完整的目录结构和说明
```

### CLI 帮助验证
```bash
# 主命令帮助包含示例
python scripts/perf_expert.py --help

# 各子命令参数有详细说明
python scripts/perf_expert.py check-cpu-bottleneck --help
python scripts/perf_expert.py cluster-symbols --help
python scripts/perf_expert.py find-callers --help
python scripts/perf_expert.py detect-anomalies --help
python scripts/perf_expert.py count-process-variety --help
```

---

更新日期: 2026-02-28

版本: v2.3

---

# SPEAR-perf-hunter v2.4 更新日志

## 更新概览

本次更新是文档体系的大规模重构，核心目标是**提升信息密度、消除冗余、优化命名**：

1. **SKILL.md 压缩**: 从 319 行精简至 118 行（-63%），保留核心方法论
2. **文档拆分**: 将 tools.md 拆分为 workflow.md（方法论）和 tools.md（命令参考）
3. **命名优化**: methodology.md → heuristics.md，优化 SPEAR 展开含义
4. **内容整合**: 将 EVOLUTION.md 有价值内容合并到 workflow.md

---

## 1. SKILL.md 压缩重构

### 修改理由
原 SKILL.md 存在冗余：
- 5 个 Step 的详细描述与 workflow.md 重复
- 附录包含完整的文档模板（70+行），应引用 templates.md
- 典型陷阱使用冗长的段落格式，可表格化
- 工具清单与 tools.md 重复

### 修改内容
1. **合并导语和工具介绍**: 简化开篇，使用表格展示参考文档
2. **Step 详情表格化**: 5 个 Step 转为流程图 + 要点表格
3. **删除附录模板**: 改为引用 templates.md
4. **陷阱表格化**: 5 段描述 → 1 个表格
5. **精简工具清单**: 保留核心 8 个工具速查

### 变更统计
- 行数: 319 → 118 (-63%)
- 文件大小: ~11KB → ~5KB (-55%)

### 文件变更
- `SKILL.md`: 完全重构

---

## 2. 文档体系重构

### 2.1 拆分 tools.md

**问题**: 原 tools.md (526 行) 同时包含方法论和命令参考，职责不清

**解决方案**:
- **workflow.md** (新增): 分析流程、7 个 Phase、典型模式、数据可靠性评估
- **tools.md** (重写): 纯命令参考，仅包含命令、参数、使用示例

**workflow.md 内容**:
- 性能问题分类（按形态/层次）
- 7 Phase 分析流程
- 感知手段框架（5 维度）
- 典型分析模式 A/B/C/D
- 数据可靠性评估表

**tools.md 内容**:
- 工具速查表
- 各工具命令和参数
- 通用参数表

### 2.2 重命名 methodology.md → heuristics.md

**问题**: methodology 与 SKILL.md 的"方法论"概念重叠，名称不准确

**新定位**: 专家经验手册，包含：
- SPEAR 方法论命名解释
- 五大认知闭包
- 领域诊断规则（进程级/系统级）
- 工具使用铁律

### 2.3 更新 templates.md

**问题**: "Table A/B" 等命名不清晰

**修改**:
- Table A → "问题演进记录"
- Table B → "竞争性假设追踪"
- 添加 workflow.md 引用

### 文件变更
- `references/workflow.md`: 新增 (429 行)
- `references/tools.md`: 重写 (339 行)
- `references/heuristics.md`: 新增，替代 methodology.md (76 行)
- `references/methodology.md`: 删除
- `references/templates.md`: 优化命名 (216 行)

---

## 3. 优化 SPEAR 展开含义

### 修改理由
原展开存在冗余和歧义：
- **P**erformance 与 **A**nalysis 重复
- **E**mpirical 过于学术
- **R**eflection 易被误解为"反射"

### 新展开
**SPEAR** = **S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning

（系统化问题证据驱动分析与推理）

### 文件变更
- `SKILL.md`: 更新描述和标题
- `AGENTS.md`: 更新项目简介
- `references/EVOLUTION.md`: 更新方法论定义

---

## 4. 整合 EVOLUTION.md 内容

### 修改理由
EVOLUTION.md 包含独特的性能问题分类和感知手段框架，但分散在独立文件中

### 整合内容到 workflow.md
1. **性能问题分类** (2.1-2.3 节)
   - 按表现形态: 持续高耗/突发尖峰/长尾延迟/资源压制
   - 按系统层次: 系统/进程/线程/代码

2. **感知手段框架** (3.1 节)
   - 资源边界 → 瓶颈判定 → 优化天花板
   - 时间分布 → 异常识别 → 定位时刻
   - 空间分布 → 热点路径 → 性能主干
   - 语义分类 → 模块归类 → 优化层级
   - 进程视角 → 聚合统计 → 资源归属

### 文件变更
- `references/workflow.md`: 新增"性能问题分类"章节
- `references/EVOLUTION.md`: 保留作为项目历史档案

---

## 参考文档索引

重构后的文档体系：

| 文档 | 用途 | 大小 |
|------|------|------|
| `SKILL.md` | 入口，核心方法论 | 118 行 |
| `references/workflow.md` | 分析流程指南 | 429 行 |
| `references/tools.md` | 工具命令参考 | 339 行 |
| `references/heuristics.md` | 启发式规则 | 76 行 |
| `references/templates.md` | 文档模板 | 216 行 |
| `references/data-format.md` | 数据格式说明 | 82 行 |
| `references/EVOLUTION.md` | 项目演进历史 | 388 行 |

---

更新日期: 2026-02-28

---

# SPEAR-perf-hunter v2.5 更新日志

## 更新概览

本次更新在启发式规则手册中新增两条专家规则：

1. **问题边界判定规则**: 通过行为相似性和共同依赖路径判定系统问题 vs 单体问题
2. **样本丢失评估规则**: 明确丢点是系统问题指示器

---

## 1. 新增问题边界判定规则

### 修改理由
原 heuristics.md 缺乏明确的问题边界判定方法，分析时难以区分系统级问题与单体应用问题。

### 修改内容
在 `references/heuristics.md` 新增 "问题边界判定规则" 章节：

| 判定维度 | 系统问题 | 单体问题 |
|----------|----------|----------|
| 行为相似性 | 多进程相似症状 | 单进程独有异常 |
| 共同依赖路径 | 共享依赖（内核/库/基础设施） | 进程私有代码路径 |
| 影响范围 | 跨进程/跨用户/全局 | 特定进程实例 |

**判定逻辑**:
```
IF (多进程相似症状) AND (共享共同依赖路径):
    → 系统问题
ELSE IF (单进程症状) OR (无共同依赖):
    → 单体问题
```

### 文件变更
- `references/heuristics.md`: 新增 "问题边界判定规则" 章节

---

## 2. 新增样本丢失评估规则

### 修改理由
明确丢点（样本丢失）的责任归属和评估逻辑，丢点反映系统层面的观测能力受限。

### 修改内容
在 `references/heuristics.md` 新增 "样本丢失（丢点）评估规则" 章节：

**核心原则**: 样本丢失本身是**系统问题**的指示器

| 评估维度 | 说明 |
|----------|------|
| 丢点本质 | perf 采样依赖中断，中断被抑制则产生丢点 |
| 责任归属 | 系统层面采样基础设施失效 |
| 关联症状 | 高内核态 CPU、调度延迟、中断堆积 |

### 文件变更
- `references/heuristics.md`: 新增 "样本丢失（丢点）评估规则" 章节

---

# SPEAR-perf-hunter v2.6 更新日志

## 更新概览

本次更新修复数据格式解析问题，将字段名从 `tid` 统一修正为 `pid`：

- **问题**: 根据 `references/data-format.md`，perf script 格式中只有 `pid`（进程 ID），没有 `tid`（线程 ID）
- **修复**: 统一将代码中的 `tid` 字段改为 `pid`，与实际数据格式保持一致

### 修改内容

#### 修改理由
原代码中多处将 `pid` 存储为 `tid` 字段名，与实际数据格式不符：

```
# 实际数据格式（data-format.md）
<comm> <pid> [<cpu>] <timestamp>: <core_per_sec> core/s:
```

#### 文件变更
1. `scripts/perf_toolkit/core/engine.py`:
   - 修改 test2 格式解析： `"tid": pid` → `"pid": pid`
   - 修改 perf_script 格式解析： `"tid": tid` → `"pid": pid`
   - 修改过滤函数：`s['tid']` → `s['pid']`
   - 更新注释：说明格式为 `comm pid [cpu]` 而非 `comm tid [cpu]`

2. `scripts/perf_toolkit/analysis/comm_clusters.py`: `s['tid']` → `s['pid']`
3. `scripts/perf_toolkit/analysis/process_variety.py`: `s['tid']` → `s['pid']`
4. `scripts/perf_toolkit/analysis/process_top.py`: `s['tid']` → `s['pid']`
5. `scripts/perf_toolkit/analysis/comm_top.py`: `s['tid']` → `s['pid']`
6. `scripts/perf_toolkit/analysis/anomalies.py`: `s["tid"]` → `s["pid"]`

---

# SPEAR-perf-hunter v2.7 更新日志

## 更新概览

本次更新针对 Agent 使用 skill 时暴露的"目标不一致"问题，建立明确的**目标范围界定**准则，并在 workflow 中引入具体场景指导。

**⚠️ v2.7 修正 1**: 初始版本过分强调 `--pid` 参数，忽略了全局瓶颈（内核全局锁、系统调度问题）需要全系统分析的场景。已修正：
1. 在"目标范围界定"表格中新增"系统级瓶颈"行
2. 在关键检查点表格中添加"参数策略"列，区分"必须加"、"用户指定加"、"不加"三种情况
3. 在模式 D 中拆分"用户指定 PID"和"系统级分析"两个场景
4. 新增"系统整体缓慢"检查点，明确不加 `--pid` 的策略

**⚠️ v2.7 修正 2**: 发现 `templates.md` 被 Agent 忽略的问题——虽然文档规范要求创建 `debug/*.md`，但没有明确引用 `templates.md` 作为模板。已修正：
1. SKILL.md "文档规范"章节重写为"文档规范（⚠️ 分析前必读）"
2. 明确强调"使用 `references/templates.md` 中的模板创建文档"
3. 在 workflow.md Phase 1 顶部添加醒目的创建文档提示
4. 说明模板包含的完整结构（问题演进、假设追踪、深度审计、全局审计等）

---

## 1. 建立"目标一致"核心准则

### 修改理由
Agent 在使用 `find-callers` 分析特定进程时遗漏 `--pid` 参数，导致分析全系统数据而非目标进程，得出错误结论。根本原因是缺乏明确的"目标问题与工具参数必须一致"准则。

### 修改内容

#### 1.1 SKILL.md 改进

**新增快速开始章节**:
- 提供完整工具路径：`/home/tiny/.config/agents/skills/perf-hunter/scripts/perf_expert.py`
- 明确使用示例

**更新关键检查点表格**:
- 所有涉及 `find-callers`、`analyze-core-distribution`、`cluster-symbols`、`get-hotspots` 的示例
- 添加 `[--pid <PID>]` 提示，强调目标一致性

#### 1.2 workflow.md 改进

**新增"目标范围界定"小节** (Phase 1.1):

| 目标类型 | 用户描述示例 | 必须添加的参数 | 错误后果 |
|---------|-------------|---------------|---------|
| **特定进程** | "PID 12345 的 CPU 上不去" | `--pid 12345` | 分析全系统数据，得出错误结论 |
| **特定进程组** | "worker 进程集体高消耗" | `--comm worker` | 混入其他进程数据，稀释信号 |
| **特定时段** | "每天晚上 8 点卡顿" | `--start-time/--end-time` | 被其他时段数据干扰 |

**新增一致性检查清单**:
- [ ] 用户是否指定了具体 PID？→ 所有命令加 `--pid`
- [ ] 用户是否提及进程名/服务名？→ 考虑加 `--comm`
- [ ] 问题是否有明确时间特征？→ 考虑加 `--start-time/--end-time`

**更新 Phase 7.1 关键信号检查清单**:
- 所有工具示例添加 `[--pid <PID>]` 提示

**改进典型分析模式**:

1. **模式 A (单进程 CPU 高)**:
   - 添加场景描述
   - 强调"所有命令必须携带 `--pid`"
   - 添加 `find-callers` 处注释 `❌ 不要遗漏 --pid`
   - 新增"⚠️ 常见错误"提示框

2. **模式 D (负载不均衡)**:
   - 添加场景描述
   - 强调"溯源时必须携带 `--pid`"
   - 新增"⚠️ 常见错误"提示框，说明不带 `--pid` 的后果

### 文件变更
- `SKILL.md`:
  - 新增"快速开始"章节（工具路径）
  - 更新关键检查点表格
- `workflow.md`:
  - 新增 Phase 1.1 "目标范围界定"小节
  - 更新 Phase 7.1 关键信号检查清单
  - 改进模式 A 和模式 D 的场景描述和警告提示

---

## 2. 修复 templates.md 被忽略的问题

### 问题分析

Agent 在分析时没有创建诊断文档，或创建的文档结构不完整，原因是：
1. SKILL.md "文档规范"部分只描述了双表结构，**没有明确引用 `templates.md`**
2. `templates.md` 虽然在参考文档表格中列出，但位置不突出，容易被忽略
3. 没有强调创建诊断文档是**分析前必须做的第一步**

### 修改内容

#### 2.1 SKILL.md "文档规范"章节重写

**原标题**: `## 文档规范`

**新标题**: `## 文档规范（⚠️ 分析前必读）`

**新增内容**:
- 明确说明"使用 `references/templates.md` 中的模板创建文档"
- 详细列出模板包含的完整结构：
  - 问题演进记录（双表结构之一）
  - 竞争性假设追踪（双表结构之二）
  - 深度审计记录
  - 全局审计检查清单
  - 优化建议与验证方案

#### 2.2 workflow.md Phase 1 强调

在 Phase 1 顶部添加醒目的提示框：

```markdown
> ⚠️ **Phase 1 第一步**: 创建诊断文档
>
> 在开始任何分析之前，立即使用 [`templates.md`](./templates.md) 中的模板创建 `debug/[问题描述].md` 文档。
> 这是强制要求，用于维护问题演进记录和竞争性假设追踪。
```

### 文件变更
- `SKILL.md`: 重写"文档规范"章节，明确引用 templates.md
- `workflow.md`: 在 Phase 1 顶部添加创建文档的强制提示

---

## 3. 引入具体场景指导

### 修改理由
原 workflow 的"典型分析模式"缺乏场景描述，Agent 难以理解何时选择何种模式，以及模式内的关键注意事项。

### 修改内容

在每个典型分析模式前添加：
- **场景**: 描述适用的问题描述特征
- **关键**: 执行该模式时的核心注意事项
- **⚠️ 常见错误**: 该模式下最易犯的错误及其后果

**模式 A 场景**:
- 用户明确反馈"某个 PID 的 CPU 上不去/异常高"
- 关键：所有命令必须携带 `--pid`
- 常见错误：`find-callers` 遗漏 `--pid`，分析全系统数据

**模式 D 场景**:
- `analyze-core-distribution` 显示 `imbalance_level=HIGH/CRITICAL`
- 关键：溯源时必须携带 `--pid`
- 常见错误：不带 `--pid` 得到全系统的 `futex_wait` 等调度函数调用

---

更新日期: 2026-02-28

版本: v2.7

---


# SPEAR-perf-hunter v2.8 更新日志

## 更新概览

本次更新修复代码中关于数据权重和字段命名的一致性问题：

1. **修复 `callgraph.py` 权重统计**: 改为使用 `core/s` 作为权重，而非简单计数
2. **统一字段命名**: 将 `user_samples` / `kernel_samples` 改为 `user_records` / `kernel_records`，避免与原始采样混淆

---

## 1. 修复 `generate-callgraph` 权重统计

### 问题
`callgraph.py` 使用简单计数（`+= 1`）统计节点和边，未遵循 "基于 core/s 权重" 的约定。

### 修复内容
- 使用 `core_per_sec` 作为权重累加节点和边
- DOT 格式：节点标签显示 core/s 值（如 `function (0.0526)`）
- JSON 格式：字段从 `count` 改为 `core_sec`
- 输出字段：`total_samples` → `total_records`，新增 `total_core_seconds`

### 文件变更
- `scripts/perf_toolkit/analysis/callgraph.py`

---

## 2. 统一字段命名

### 问题
代码中使用 `user_samples` / `kernel_samples` 容易与原始 perf 采样混淆（数据已按 1 秒聚合，"样本数"概念不适用）。

### 修复内容
| 原字段名 | 新字段名 | 说明 |
|---------|---------|------|
| `user_samples` | `user_records` | 用户态模式的聚合记录数 |
| `kernel_samples` | `kernel_records` | 内核态模式的聚合记录数 |
| `total_samples` | `total_records` | 总聚合记录数 |

### 文件变更
- `scripts/perf_toolkit/core/engine.py`: 修改 `get_user_kernel_core_per_sec()` 和 `get_cpu_utilization()` 返回值
- `scripts/perf_toolkit/analysis/cpu_usage.py`: 更新字段引用
- `scripts/parse_test2.py`: 测试脚本一致性更新

---

## 验证检查清单

- [x] 所有统计模块使用 `core/s` 作为权重
- [x] 字段命名统一为 `records` 而非 `samples`
- [x] 文档字符串说明 "数据已按 1 秒聚合，记录数量无参考价值"

---

更新日期: 2026-02-28

版本: v2.8

---


# SPEAR-perf-hunter v2.9 更新日志

## 更新概览

本次更新引入 **Live Document（实时诊断文档）** 机制，解决 netstat/containerd-shim 案例中暴露的"搜索空间不足导致关键问题遗漏"问题。

**核心问题**: Agent 分析过程中，人脑记忆无法跟踪多个并行的待验证目标，导致搜索覆盖率不足（25%），遗漏了同样严重的 containerd-shim 问题。

**解决方案**: 
1. 结构化记录所有发现的问题（`perf-doc add`）
2. 标记已完成分析的问题（`perf-doc complete`）
3. 强制审计剩余风险（`perf-doc list` / `perf-doc finalize`）
4. 达到覆盖率阈值后才能生成报告

---

## 1. 问题复盘：搜索空间不足导致遗漏

### 1.1 真实案例

分析 `netstat_perf.data` 时：

```
get-comm-top 发现 4 个高内核态进程:
  netstat:          2623 PIDs, 94.7% kernel  ← 分析 ✓
  containerd-shim:   240 PIDs, 89.9% kernel  ← 遗漏 ✗
  sh:                 45 PIDs, 86.8% kernel  ← 遗漏 ✗
  python3:           826 PIDs, 82.3% kernel  ← 遗漏 ✗
```

**实际执行**: 只分析了 netstat（覆盖率 25%）
**事后发现**: containerd-shim 锁竞争 79.84%，是 netstat（38.36%）的 2 倍

### 1.2 根本原因

| 原因 | 说明 |
|------|------|
| 人脑记忆有限 | 工具输出后无持久化，信息必然淹没 |
| 数字偏见 | 2623 vs 240，被大数字吸引 |
| 无客观审计 | 没有机制检查"还有哪些没分析" |
| 缺乏强制收敛检查 | 找到根因后无机制阻止提前收敛 |

---

## 2. Live Document 机制设计

### 2.1 核心理念

- **状态化诊断**: 所有问题记录在结构化文档中，不依赖人脑记忆
- **强制审计**: 生成报告前必须检查剩余风险
- **覆盖率阈值**: 达到 80% 覆盖率或显式接受风险后才能收敛

### 2.2 数据结构（极简扁平）

```json
{
  "version": "1.0",
  "data_file": "netstat_perf.data",
  "issues": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "completed",
      "result": "LOCK_CONTENTION 38.36%",
      "completed_at": "2026-02-28T11:00:00Z"
    },
    {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "status": "pending",
      "risk": "可能比 netstat 更严重",
      "hint": "cluster-symbols --comm containerd-shim"
    }
  ]
}
```

**设计原则**: 
- 最多 2 层嵌套
- 仅两种状态: `pending` / `completed`
- 字符串字段为主，对 agent 友好

### 2.3 核心命令

```bash
# 初始化
perf-doc init --data <file>

# 发现问题时记录
perf-doc add --id <id> --desc <desc> [--risk <risk>] [--hint <hint>]

# 分析完成后标记
perf-doc complete --id <id> --result <result>

# 查看剩余风险（强制检查点）
perf-doc list

# 最终审计（生成报告前必须执行）
perf-doc finalize
```

### 2.4 输出格式（人类可读）

```markdown
═══════════════════════════════════════════════════════════════════
ISSUES  STATUS  (1 completed, 1 pending)
═══════════════════════════════════════════════════════════════════

✅ COMPLETED
───────────────────────────────────────────────────────────────────
ISS-001  netstat 高内核态 94.7%
         └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

⚠️  PENDING  ← 需处理
───────────────────────────────────────────────────────────────────
ISS-002  containerd-shim 高内核态 89.9%
         ├─ 风险: 可能比 netstat 更严重，单进程影响大
         └─ 建议: cluster-symbols --comm containerd-shim

═══════════════════════════════════════════════════════════════════
```

### 2.5 强制审计机制

```bash
$ perf-doc finalize

⚠️  剩余风险确认
───────────────────────────────────────────────────────────────────
以下问题尚未处理：

ISS-002  containerd-shim 高内核态 89.9%
  - 状态: 完全未分析
  - 风险: 锁竞争可能 >50%，单进程影响大于 netstat

强制选择:
[A] 继续分析剩余问题（推荐）
[B] 接受风险，生成报告（必须提供理由）
[C] 标记为无需处理（必须提供证据）
```

---

## 3. 与 Skill 文档的整合

### 3.1 SKILL.md 更新

新增"Live Document 机制"章节，明确：
- 发现风险时 **必须** 执行 `perf-doc add`
- 每 2-3 个工具后 **必须** 执行 `perf-doc list`
- 生成报告前 **必须** 执行 `perf-doc finalize`

**禁止行为**:
- ❌ 未记录问题直接分析
- ❌ `pending` 列表不为空时生成报告
- ❌ 未执行 `finalize` 结束诊断

### 3.2 双 Table 机制演进

传统方式（手工维护）:
- Table 1: 问题演进记录（markdown）
- Table 2: 假设验证状态（markdown）

新方式（自动维护）:
- Table 1 → Live Doc 的 `issues` 列表
- Table 2 → 每个 issue 的 `desc`, `result`, `risk` 字段

**优势**: 从"手工维护"变为"工具自动维护"

---

## 4. 设计讨论记录

### 4.1 为什么不要奖励机制？

**第一轮方案**: 进度条、徽章、积分、成就系统

**反馈**: "不要玩那么多奖励机制，太复杂了，直接点"

**决策**: 
- 去掉所有激励元素
- 直接展示剩余风险
- 用 SKILL 规范强制要求

### 4.2 为什么扁平结构？

**第一轮方案**: 嵌套结构，按 phase 组织

```json
{
  "phases": {
    "phase_2": {
      "critical_findings": {...}
    }
  }
}
```

**问题**: 3 层嵌套，解析复杂

**决策**: 扁平化为 `issues` 列表，最多 2 层

### 4.3 为什么只有两种状态？

**讨论**: 是否需要 `in_progress` / `verified` / `wontfix`？

**决策**: 只有 `pending` / `completed`，简化认知负担

---

## 5. 参考文档

- [Live Doc 设计意图文档](./design-rationale-live-doc.md)
- [Live Doc 接口设计文档](./live-doc-interface.md)

---

更新日期: 2026-02-28

版本: v2.9

---


# SPEAR-perf-hunter v2.10 更新日志

## 更新概览

本次更新建立**工具输出格式规范**，解决现有输出格式不一致、嵌套过深、缺乏风险提示等问题。

**核心改进**:
1. **风险置顶**: 所有输出必须包含 `_risk` 字段，第一时间提示关键问题
2. **时间字符串化**: 所有时间字段使用 ISO 8601 格式，禁止使用数字时间戳
3. **扁平化结构**: JSON 嵌套不超过 3 层，简化 Agent 解析

---

## 1. 问题背景

### 1.1 现有输出格式问题

**问题 1: 嵌套过深**

```json
// anomalies.py - 5层嵌套
{
  "anomalies": [{
    "window": {
      "start": 1234567890.123  // 第4层
    },
    "utilization": {
      "before": "10.0%"       // 第4层
    }
  }]
}
```

**问题 2: 时间戳数字**

```json
// 不规范的时间表示
{
  "time_range": {
    "start": 1677567600.123,  // 数字时间戳，难以阅读
    "end": 1677569400.456
  }
}
```

**问题 3: 缺乏统一风险提示**

不同工具使用不同方式提示风险：
- `bottleneck.py`: 使用 `verdict` 字段
- `core_distribution.py`: 使用 `imbalance_level` 字段
- `clusters.py`: 无风险字段

Agent 难以统一识别关键信息。

---

## 2. 输出格式规范 v1.0

### 2.1 必须字段: `_risk`

所有工具输出必须包含 `_risk` 字段，放在输出顶部：

```json
{
  "_risk": {
    "level": "critical | warning | info | none",
    "message": "简短的风险描述",
    "hint": "建议的下一步操作",
    "patterns": ["检测到的模式"],
    "pending_targets": ["待处理目标"],
    "action_required": true
  }
}
```

**Level 定义**:

| Level | 场景 | Agent 响应 |
|-------|------|-----------|
| `critical` | 严重问题，必须处理 | 立即停止，按 hint 执行 |
| `warning` | 潜在问题，建议处理 | 优先处理，记录风险 |
| `info` | 值得关注 | 了解即可 |
| `none` | 无风险 | 正常流程 |

### 2.2 时间字段规范

**格式**: ISO 8601 字符串

```json
{
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00",
    "duration": 1800  // 秒，保留数字
  }
}
```

**禁止**: 时间戳数字、嵌套时间对象

### 2.3 数值规范

**百分比**: 字符串，带 % 符号

```json
{
  "cpu_utilization": "45.5%",
  "kernel_ratio": "89.9%"
}
```

**core/s**: 数字，4位小数

```json
{
  "core_seconds": 0.0526
}
```

---

## 3. 各工具改造计划

### 3.1 P0 优先级（高优先级）

| 工具 | 主要改造点 |
|------|-----------|
| `bottleneck.py` | 添加 `_risk`，时间字符串化 |
| `comm_top.py` | 添加 `_risk`，简化字段，时间字符串化 |
| `anomalies.py` | 扁平化结构（5层→3层），时间字符串化 |
| `core_distribution.py` | 简化 `cores`，时间字符串化 |

### 3.2 P1 优先级

| 工具 | 主要改造点 |
|------|-----------|
| `clusters.py` | 添加 `_risk`，时间字符串化 |
| `hotspots.py` | 添加 `_risk`，时间字符串化 |
| `trace.py` | 时间字符串化 |
| `cpu_usage.py` | 时间字符串化 |
| `process_top.py` | 时间字符串化 |
| `process_variety.py` | 时间字符串化 |

### 3.3 P2 优先级

| 工具 | 主要改造点 |
|------|-----------|
| `comm_clusters.py` | 时间字符串化 |
| `path_clusters.py` | 时间字符串化 |
| `flamegraph.py` | 时间字符串化 |
| `callgraph.py` | 时间字符串化 |

---

## 4. 改造示例

### 4.1 anomalies.py 改造

**改造前**:
```json
{
  "anomalies": [{
    "type": "SPIKE",
    "window": {
      "start": 1234567890.123,
      "end": 1234567890.623
    },
    "utilization": {
      "before": "10.0%",
      "during": "85.0%",
      "after": "15.0%"
    },
    "z_score": 3.5,
    "change_magnitude": 0.75
  }]
}
```

**改造后**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "检测到 3 个 CPU 利用率异常尖峰",
    "hint": "分析 spike 时段: get-hotspots --start-time '2026-02-28T10:15:00'",
    "action_required": true
  },
  "summary": {
    "total_anomalies": 3,
    "spike_count": 2
  },
  "time_range": {
    "start_time": "2026-02-28T10:00:00",
    "end_time": "2026-02-28T10:30:00"
  },
  "anomalies": [{
    "type": "SPIKE",
    "time_range": "2026-02-28T10:15:00 - 2026-02-28T10:16:00",
    "utilization_change": "10% -> 85% -> 15%",
    "severity": "high"
  }]
}
```

### 4.2 comm_top.py 改造

**改造前**:
```json
{
  "comm_groups": [{
    "comm": "netstat",
    "pid_count": 2623,
    "aggregate_cpu_utilization_pct": 243.87,
    "kernel_ratio_pct": 94.7,
    "density_index": 0.093,
    "avg_core_sec_per_process": 0.0012
  }]
}
```

**改造后**:
```json
{
  "_risk": {
    "level": "warning",
    "message": "发现 2 个高内核态进程组未分析",
    "hint": "建议并行分析: cluster-symbols --comm containerd-shim",
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
  "comm_groups": [{
    "comm": "netstat",
    "pid_count": 2623,
    "cpu_pct": "243.87%",
    "kernel_pct": "94.7%"
  }]
}
```

---

## 5. 辅助工具

### 5.1 RiskMixin 基类

```python
# core/risk_mixin.py
class RiskMixin:
    """标准化风险提示"""
    
    def add_risk(self, level, message, hint="", patterns=None, targets=None):
        # 添加风险记录
        pass
    
    def format_output(self, data):
        # 添加 _risk 字段到输出
        return {"_risk": self.get_top_risk(), **data}
```

### 5.2 时间格式化工具

```python
# core/format_utils.py
from datetime import datetime

def format_timestamp(ts: float) -> str:
    """时间戳转 ISO 8601 字符串"""
    return datetime.fromtimestamp(ts).isoformat()

def format_time_range(start_ts, end_ts):
    """格式化时间范围"""
    return {
        "start_time": format_timestamp(start_ts),
        "end_time": format_timestamp(end_ts),
        "duration": round(end_ts - start_ts, 2)
    }
```

---

## 6. 验证检查清单

改造后的工具必须满足：

- [ ] 输出包含 `_risk` 字段且置顶
- [ ] `_risk.level` 为有效值 (critical/warning/info/none)
- [ ] 所有时间戳转换为 ISO 8601 字符串
- [ ] JSON 嵌套不超过 3 层
- [ ] 百分比使用字符串格式（带 %）
- [ ] 风险消息简洁（一句话）
- [ ] hint 包含可执行命令建议

---

## 7. 参考文档

- [输出格式规范](./output-format-spec.md)
- [Live Document 设计](./design-rationale-live-doc.md)

---

更新日期: 2026-02-28

版本: v2.10

---
---

# SPEAR-perf-hunter v2.11 更新日志

## 更新概览

本次更新实现 Live Document（perf-doc）CLI 工具，用于跟踪诊断过程中的问题记录：

1. **新增 perf-doc 工具**: 6 个核心命令（init/add/complete/list/finalize/export）
2. **集成到 perf_expert.py**: 通过 `perf_expert.py doc <command>` 调用
3. **问题追踪流程**: 完整的问题生命周期管理

---

## 1. Live Document 功能

### 1.1 设计目标

解决诊断过程中问题追踪的痛点：
- 多个问题并行分析时的状态管理
- 最终审计前的强制检查点
- 诊断报告的自动生成

### 1.2 核心命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `doc init` | 初始化诊断文档 | `doc init --data perf.data` |
| `doc add` | 添加问题记录 | `doc add --id ISS-001 --desc "高内核态"` |
| `doc complete` | 标记问题完成 | `doc complete --id ISS-001 --result "锁竞争"` |
| `doc list` | 列出所有问题 | `doc list --format text` |
| `doc finalize` | 最终审计 | `doc finalize --accept-risk "低风险"` |
| `doc export` | 导出报告 | `doc export --format markdown` |

### 1.3 文档格式

```json
{
  "version": "1.0",
  "data_file": "perf.data",
  "created_at": "2026-02-28T10:00:00Z",
  "updated_at": "2026-02-28T11:30:00Z",
  "issues": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "completed",
      "risk": "进程风暴",
      "hint": "cluster-symbols --comm netstat",
      "result": "LOCK_CONTENTION 38.36%",
      "created_at": "2026-02-28T10:05:00Z",
      "completed_at": "2026-02-28T11:00:00Z"
    }
  ]
}
```

---

## 2. 文件变更

### 新增文件
1. `scripts/perf_toolkit/core/live_doc.py` - LiveDoc 类实现
   - `init()`: 初始化 `.perf-doc.json`
   - `add()`: 添加问题
   - `complete()`: 标记完成
   - `list()`: 列出问题
   - `finalize()`: 最终审计
   - `export_markdown()`: 导出 Markdown 报告

### 修改文件
1. `scripts/perf_expert.py`
   - 导入 live_doc 命令
   - 添加 `doc` 子命令及 6 个子命令解析
   - 添加命令路由

2. `scripts/perf_toolkit/core/__init__.py`
   - 导出 `LiveDoc` 类

---

## 3. 使用流程示例

```bash
# 1. 初始化文档
perf-expert.py doc init --data netstat_perf.data

# 2. 发现问题并记录
perf-expert.py get-comm-top --data netstat_perf.data
# 发现: 4 个高内核态进程组

perf-expert.py doc add --id ISS-001 \
  --desc "netstat 高内核态 94.7%" \
  --risk "进程风暴" \
  --hint "cluster-symbols --comm netstat"

# 3. 分析问题并记录结果
perf-expert.py cluster-symbols --comm netstat --data netstat_perf.data
perf-expert.py doc complete --id ISS-001 \
  --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"

# 4. 检查待办
perf-expert.py doc list

# 5. 最终审计
perf-expert.py doc finalize
# 输出: ✅ 所有问题已处理

# 6. 导出报告
perf-expert.py doc export --format markdown --output report.md
```

---

## 4. 验证测试

```bash
# 完整流程测试
cd /tmp
rm -f .perf-doc.json

# 初始化
python /path/to/perf_expert.py doc init --data test.data

# 添加问题
python /path/to/perf_expert.py doc add --id ISS-001 \
  --desc "测试问题" --risk "高风险" --hint "执行分析"

# 列出问题
python /path/to/perf_expert.py doc list

# 完成问题
python /path/to/perf_expert.py doc complete --id ISS-001 --result "已解决"

# 最终审计
python /path/to/perf_expert.py doc finalize

# 导出报告
python /path/to/perf_expert.py doc export --format markdown
```

---

更新日期: 2026-02-28

版本: v2.11

---
