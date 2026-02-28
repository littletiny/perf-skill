# SPEAR-perf-hunter 更新日志

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

## 更新日期: 2026-02-28

版本: v2.7

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

# 历史版本

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

## 2. 重构 tools.md

### 修改内容
1. **新增分析流程总览图**: 7 阶段 Top-Down + Bottom-Up 混合流程
2. **按分析阶段重组工具**: Phase 1→7 渐进式分析路径
3. **新增语义分析章节**: 符号名领域映射
4. **新增专家经验查缺补漏章节**: 关键信号检查清单和全局一致性检查
5. **新增典型分析模式**: 5 种快捷路径（含新增的大量小进程模式）

### 文件变更
- `references/tools.md`: 完全重构

---

更新日期: 2026-02-28
版本: v2.2

---

# 历史版本

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
  --custom-rules '{"SCHEDULING": "schedule|nanosleep"}'

# 方式 2: 列表格式 (自动转换)
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
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

## 3. 文档重构

### SKILL.md 改进

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

### tools.md 改进

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
   - 重构为规则驱动的泛化方法论
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

## v2.2 (2026-02-28)

### 重构 tools.md —— Top-Down + Bottom-Up 混合分析模式

#### 修改理由
原 tools.md 采用平铺式的工具列表组织方式，缺乏结构化的分析流程指导。实际性能分析需要结合：
1. **Top-Down 宏观切入**: 从系统级概览建立上下文
2. **Bottom-Up 微观溯源**: 从热点函数逐层深入

#### 修改内容
1. **新增分析流程总览图**: 清晰展示 7 个分析阶段及其关系
2. **按分析阶段重组工具**: Phase 1→7 的渐进式分析路径
3. **新增语义分析章节**: 根据符号名猜测 workload 和技术领域
4. **新增专家经验查缺补漏章节**: 关键信号检查清单和全局一致性检查
5. **新增典型分析模式**: 4 种快捷路径（单进程高 CPU、系统缓慢、进程风暴、负载不均衡）
6. **保留原有内容**: 内核函数规范化、CPU 利用率计算、可靠性评估、通用参数

#### 文件变更
- `references/tools.md`: 完全重构，从 392 行扩展为结构化文档

---

更新日期: 2026-02-28
版本: v2.2
