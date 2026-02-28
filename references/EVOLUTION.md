# SPEAR-perf-hunter 演化记录

## 1. 方法论概述

### 1.1 SPEAR 核心原则

SPEAR (**S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning) 是系统化的 Linux 性能诊断方法论：

| 原则 | 说明 |
|------|------|
| **实证驱动** | 严禁无工具数据的空想推论，每个假设必须紧跟验证动作 |
| **搜索空间收敛** | 遵循漏斗模型：环境边界 → 热点主干 → 精准归因 |
| **交叉验证** | 系统层观察必须关联机制，评估可能性 |
| **竞争性假设** | 保持双线思考：主动消耗（代码低效）vs 被动压制（调度/资源限制） |
| **证伪反思** | 结论前审视证据链，排除其他可能性 |

### 1.2 诊断漏斗模型

```
Stage 1: 环境边界（Resource Boundary）
    ↓ 确定物理限制
Stage 2: 消耗归因（Consumption Attribution）
    ↓ 进程级/线程级/函数级分解
Stage 3: 路径识别（Path Identification）
    ↓ 调用模式聚类
Stage 4: 热点定位（Hotspot Localization）
    ↓ 具体函数/代码行
Stage 5: 根因确认（Root Cause Confirmation）
    ↓ 证据链闭合
```

---

## 2. 性能问题分类

### 2.1 按资源类型分类

| 分类 | 典型表现 | 诊断重点 |
|------|---------|---------|
| **CPU 瓶颈** | CPU 利用率接近上限 | 热点函数、调用路径、锁竞争 |
| **内存瓶颈** | 频繁 GC、OOM | 分配热点、内存泄漏、缓存效率 |
| **I/O 瓶颈** | 磁盘/网络等待 | I/O 模式、阻塞调用、缓冲策略 |
| **调度延迟** | 高负载下响应慢 | 上下文切换、runqueue、优先级 |

### 2.2 按表现形态分类

| 形态 | 特征 | 分析策略 |
|------|------|---------|
| **持续高耗** | 稳定的高 CPU/内存 | 热点函数分析、代码优化 |
| **突发尖峰** | 间歇性资源飙升 | 异常检测、时序分析、事件关联 |
| **长尾延迟** | P99 远高于均值 | 尾延迟分析、路径差异对比 |
| **资源压制** | Cgroup 限流触发 | 边界检查、配额分析 |

### 2.3 按层次分类

| 层次 | 问题域 | 工具关注点 |
|------|--------|-----------|
| **系统层** | 内核调度、中断、资源竞争 | `cluster-symbols` (EVENT_SCHEDULER, EVENT_IRQ_OFF) |
| **进程层** | 多进程协调、IPC | `cluster-comm`, `get-process-top` |
| **线程层** | 锁竞争、线程池效率 | `find-callers` 追溯同步原语 |
| **代码层** | 算法复杂度、数据结构 | `get-hotspots`, `cluster-paths` |

---

## 3. 感知手段与工具映射

### 3.1 感知手段全景

| 感知维度 | 原始数据 | 加工后信息 | 决策价值 |
|---------|---------|-----------|---------|
| **资源边界** | CPU quota, 利用率 | 瓶颈类型判定 | 确定优化天花板 |
| **时间分布** | 采样时间戳 | 异常模式识别 | 定位异常时刻 |
| **空间分布** | 调用栈 | 热点路径 | 识别性能主干 |
| **语义分类** | 函数名 | 业务模块归类 | 确定优化层级 |
| **进程视角** | PID/comm | 进程聚合统计 | 资源归属判定 |

### 3.2 工具与手段映射

| 感知手段 | 工具命令 | 补齐的能力 |
|---------|---------|-----------|
| 资源边界检测 | `check-cpu-bottleneck` | Cgroup 限流 vs 单核饱和判定 |
| CPU 消耗分解 | `show-cpu-usage` | user/kernel 态比例 |
| 进程排名 | `get-process-top` | TopN 进程及其混合比例 |
| 进程组聚合 | `cluster-comm` | 同类进程（如所有 nginx）总消耗 |
| 函数热点 | `get-hotspots` | self/inclusive 双视角 |
| 语义聚类 | `cluster-symbols` | 按 EVENT_XXX 规则自动归类 |
| 路径聚类 | `cluster-paths` | 无预设识别业务调用模式 |
| 热点溯源 | `find-callers` | 反向追溯热点调用链 |
| 时序异常 | `detect-anomalies` | SPIKE/DROP/LEVEL_SHIFT/BURST |
| 可视化导出 | `generate-flamegraph/callgraph` | 外部工具对接 |

---

## 4. 讨论演进记录

### 4.1 第一轮：功能需求评估

**问题描述**：给定 perf data，评估现有工具能否完成以下功能：
1. 判断单个进程在单核上存在 CPU 瓶颈
2. 单个 CPU 内核开销过高
3. 某一类进程消耗了太多 CPU 资源
4. 评估是否有内核热点路径和热点函数
5. 评估特定进程的 CPU 瓶颈在内核还是用户态

**目的**：确定工具集的覆盖度和缺口

**手段**：代码审查 + 文档分析

**评估详情**：

| 需求 | 支持状态 | 缺口分析 |
|------|---------|---------|
| 1. 单进程单核瓶颈 | ⚠️ 部分 | 有 `--pid` 但无 `--cpu-id` 组合检查瓶颈 |
| 2. 单核开销过高 | ✅ 支持 | `show-cpu-usage --cpu-id` 可行 |
| 3. 某类进程消耗 | ❌ 缺失 | 无按 comm 聚合功能 |
| 4. 内核热点路径 | ⚠️ 部分 | `cluster-symbols` 有内核规则但无路径视角 |
| 5. 进程级 user/kernel | ✅ 支持 | `show-cpu-usage --pid` 可满足 |

**结论**：缺口在于"按进程类型聚合"和"全局路径视角"

---

### 4.2 第二轮：功能补齐（comm 过滤 + 进程聚类）

**问题描述**：如何补齐"某一类进程消耗太多 CPU"的分析能力？

**目的**：支持按进程名（comm）进行聚合分析

**手段**：
1. 为所有命令添加 `--comm` 和 `--comm-regex` 过滤参数
2. 新增 `cluster-comm` 命令，按 comm 聚类统计

**评估详情**：

**实现方案**：
```python
# 1. 扩展 filter 接口
def get_filtered_samples(..., comm=None, comm_regex=None):
    if comm:
        comm_list = [c.strip() for c in comm.split(',')]
        filtered = [s for s in filtered if s['comm'] in comm_list]
    if comm_regex:
        pattern = re.compile(comm_regex)
        filtered = [s for s in filtered if pattern.search(s['comm'])]
```

**新增命令**：
- `cluster-comm`: 输出每个 comm 的 CPU 利用率、user/kernel 比例、实例数

**使用示例**：
```bash
# 分析所有 nginx 进程的总消耗
python3 scripts/perf_expert.py cluster-comm --data perf.txt

# 分析多个相关进程
python3 scripts/perf_expert.py show-cpu-usage --comm nginx,php-fpm
```

---

### 4.3 第三轮：stack samples 分析补充讨论

**问题描述**：站在 stack samples 分析角度，还有哪些点可以补充？

**目的**：识别现有工具链的盲区

**手段**：系统性分析 perf 数据的未挖掘维度

**评估详情**（提出 12 个候选功能）：

| 功能 | 价值 | 实现复杂度 | 是否实现 |
|------|------|-----------|---------|
| 差异分析 (diff) | 高（回归分析） | 中 | 否 |
| 调用栈深度分析 | 中（代码质量） | 低 | 否 |
| 线程级分析 | 高（多线程诊断） | 低 | 否（已有进程级） |
| 时间线模式分析 | 中（周期性检测） | 中 | 否（`detect-anomalies` 部分覆盖） |
| 锁竞争深度分析 | 高（高并发） | 中 | 否 |
| 函数趋势分析 | 中（时序追踪） | 中 | 否 |
| 跨进程热点关联 | 中（共享库） | 中 | 否 |
| **代码路径聚类** | **高（业务语义）** | **中** | **是（cluster-paths）** |
| 采样偏差检测 | 低（质量评估） | 低 | 否 |
| 尾延迟分析 | 中（P99 问题） | 高 | 否 |
| 循环/递归检测 | 低（优化建议） | 高 | 否 |

**关键决策**：优先实现 `cluster-paths`，填补"全局调用模式识别"空白

---

### 4.4 第四轮：cluster-paths vs find-callers 关系讨论

**问题描述**：`find-callers` 是否能解决 `cluster-paths` 要解决的问题？为什么它被"无视"？

**目的**：明确两个工具的分工边界

**手段**：对比分析两个工具的使用场景和输出

**评估详情**：

| 维度 | find-callers | cluster-paths |
|------|-------------|---------------|
| **起点** | 需要预设 `--target` | 无预设，全局自动 |
| **方向** | 从下往上追溯 | 从上往下聚合 |
| **输入依赖** | 需要已知热点函数 | 无需先验知识 |
| **输出** | 单个函数的调用来源 | 系统主要执行路径 |
| **使用时机** | 阶段 5（已知热点） | 阶段 3（探索模式） |

**关键洞察**：
- `find-callers` 要求用户已有明确假设（"我想知道 malloc 从哪里被调用"）
- 实际诊断中，用户往往需要先看到全局模式，才能决定深入分析哪个热点
- `cluster-paths` 填补的是"从全局到具体"的过渡环节

**结论**：两者是协作关系而非替代关系

---

### 4.5 第五轮：cluster-paths 和 find-callers --auto-target 实现

**问题描述**：如何实现 `cluster-paths`？`find-callers --auto-target` 是否好实现？

**目的**：实现两个功能的具体方案

**手段**：
1. cluster-paths：Trie 前缀树聚类
2. find-callers --auto-target：自动选取 TopN 热点并追溯

**评估详情**：

**cluster-paths 实现**：

```python
class PathCluster:
    def __init__(self, min_depth=2, min_samples=5):
        self.min_depth = min_depth
        self.min_samples = min_samples
        self.trie = {'_count': 0, '_samples': []}
    
    def add_sample(self, stack):
        # 从 root 到 leaf 构建 Trie
        node = self.trie
        for func in reversed(stack):
            if func not in node:
                node[func] = {'_count': 0, '_samples': []}
            node = node[func]
            node['_count'] += 1
    
    def extract_clusters(self):
        # 提取满足 min_depth 和 min_samples 的分支
        # 同时统计 leaf 函数分布
```

**输出示例**：
```json
{
  "cluster_id": "c_001",
  "path_signature": "main→handle_request",
  "ratio": "45.0%",
  "leaf_ratios": {
    "parse_json": "60%",
    "send_response": "40%"
  }
}
```

**find-callers --auto-target 实现**：

```python
# 1. 统计 self count 找热点
self_counts = defaultdict(int)
for s in samples:
    if s['stack']:
        self_counts[s['stack'][0]] += 1

# 2. 取 Top N
top_hotspots = sorted(self_counts.items(), key=lambda x: -x[1])[:n]

# 3. 对每个热点执行原有追溯逻辑
for target, count in top_hotspots:
    trace_attribution(target)
```

**实现结果**：两者均成功实现，复杂度均为"中"

---

### 4.6 第六轮：文档结构优化

**问题描述**：Expert Rules 的 `S*_xx P*_xxx` 前缀是否还有意义？文档信息密度是否太低？

**目的**：简化命名 + 提升文档信息密度

**手段**：
1. 统一前缀为 `EVENT_`
2. 重构文档：子功能清单表格 → 命令分类 → 典型工作流

**评估详情**：

**命名变更**：
```python
# 旧（数字前缀无明确语义）
S2_IRQ_OFF, S3_SCHEDULER, S4_MEM_RECLAIM, S5_LOCK_CONTENTION, P3_SYNC_PRIMITIVES

# 新（统一 EVENT_ 前缀）
EVENT_IRQ_OFF, EVENT_SCHEDULER, EVENT_MEM_RECLAIM, EVENT_LOCK_CONTENTION, EVENT_SYNC_PRIMITIVE
```

**文档结构优化**：

旧结构（信息密度低）：
```
- 每个命令详细描述返回值 JSON 字段
- 核心能力与命令分离
- 大量冗余文字
```

新结构（信息密度高）：
```
开头: 子功能清单表格（11个命令，3列）
中间: 按6大类别组织的命令详情（仅关键参数）
结尾: 通用参数表格 + 典型工作流
```

**改进效果**：
- 文档行数从 ~1000 行降至 ~560 行
- 关键信息查找时间减少
- 命名语义更清晰

---

## 5. 早期迭代: v1.0 反思与改进

### 5.1 触发事件: PID 2573405 案例分析

**背景**: 2026-02-28 的 parameter_server CPU 使用率不足分析案例，暴露了 Skill 文档的关键设计缺陷。

**问题症状**:
- 72 核心机器上进程分布广泛，但仅 1 个核心满载 (97.45%)
- `finish_task_switch` 自消耗 3.92%
- 初步分析误用 `grep "nanosleep"` 导致统计不可靠

**暴露的文档缺陷**:

| 缺陷 | 影响 | 改进 |
|-----|------|------|
| 工具孤立呈现 | 不知道热点后应追溯 | 建立 `get-hotspots` → `find-callers` 强制链路 |
| `--auto-target` 误导 | 非热点函数未被选中 | 文档强调 `--target` 针对性追溯 |
| 缺乏决策树 | 不知道看到 X 后做 Y | 新增 Step 1-6 条件分支流程 |
| 未强调扩展参数 | 不知道 `--custom-rules` | 增加使用场景说明 |

**关键洞察**:

1. **分析入口选择**: `finish_task_switch` 是调度问题的自然入口，而非 `nanosleep`
   ```bash
   # 最优路径
   find-callers --target finish_task_switch
   # → 66.67% 来自 nanosleep 路径，33.33% 来自 epoll_wait 路径
   ```

2. **工具链思维**: 建立明确的 A → B 工具流转
   ```
   环境边界 (check-cpu-bottleneck)
       ↓
   热点识别 (get-hotspots --sort-by self)
       ↓
   热点溯源 (find-callers --target <热点>)
       ↓
   深层归因 (find-callers --target <阻塞函数>)
   ```

3. **扩展能力挖掘**: `--custom-rules` 可解决默认规则未覆盖的场景
   ```bash
   cluster-symbols --custom-rules '{"EVENT_SLEEP":"nanosleep|usleep|sleep"}'
   # 结果: EVENT_SLEEP 13.73% (95% CI: 8.4%-21.7%), 样本数 14
   ```

### 5.2 v1 → v2 → v3 工作流演进

| 版本 | 核心新增 | 工作流 |
|-----|---------|--------|
| **v1** | 基础工具集 | `check-cpu-bottleneck → get-hotspots → find-callers --target <func>` |
| **v2** | 进程视角 (`cluster-comm`, `--comm`) | `check-cpu-bottleneck → get-process-top → cluster-comm → get-hotspots` |
| **v3** | 路径视角 (`cluster-paths`, `--auto-target`) | `check-cpu-bottleneck → get-process-top → cluster-paths → find-callers --auto-target` |

---

## 6. 最终工具集全景

### 6.1 工具清单

| 命令 | 添加版本 | 解决的核心问题 |
|------|---------|---------------|
| `check-cpu-bottleneck` | v1 | 资源边界判定 |
| `show-cpu-usage` | v1 | CPU 消耗分解 |
| `get-hotspots` | v1 | 热点函数识别 |
| `cluster-symbols` | v1 | 语义规则聚类 |
| `find-callers` | v1 | 热点调用追溯 |
| `detect-anomalies` | v1 | 时序异常检测 |
| `generate-flamegraph` | v1 | 可视化导出 |
| `generate-callgraph` | v1 | 调用图导出 |
| `get-process-top` | v2 | 进程级消耗排名 |
| `cluster-comm` | v2 | 进程组聚合分析 |
| `cluster-paths` | v3 | 调用路径模式识别 |
| `--comm` 过滤 | v2 | 按进程名过滤所有命令 |
| `--auto-target` | v3 | 自动热点追溯 |

### 6.2 诊断工作流演进

**v1 工作流（基础）**：
```
check-cpu-bottleneck → get-hotspots → find-callers --target <func>
```

**v2 工作流（增加进程视角）**：
```
check-cpu-bottleneck → get-process-top → cluster-comm → get-hotspots
```

**v3 工作流（增加路径视角）**：
```
check-cpu-bottleneck → get-process-top → cluster-paths → find-callers --auto-target
```

### 6.3 未实现功能清单（未来方向）

| 功能 | 价值 | 未实现原因 |
|------|------|-----------|
| 差异分析 (diff) | 高 | 需定义"路径指纹"匹配算法 |
| 锁竞争深度分析 | 高 | 需扩展采样事件（lock events） |
| 尾延迟分析 | 中 | 需 P99 统计方法设计 |
| 线程级分析 | 中 | TID 与 PID 关系复杂 |

---

## 7. 方法论验证

通过本轮演化，SPEAR 方法论的各项原则得到验证：

| 原则 | 验证点 |
|------|--------|
| **实证驱动** | 每个新增功能都有明确的工具数据需求 |
| **搜索空间收敛** | 从 `get-hotspots`（函数）→ `cluster-paths`（路径）→ `find-callers`（具体来源） |
| **竞争性假设** | `cluster-comm` 同时支持按 PID 和按 comm 聚合，对比验证 |
| **交叉验证** | `cluster-symbols` 与 `cluster-paths` 双视角确认热点归属 |

---
