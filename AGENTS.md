# AGENTS.md - perf-hunter Skill 开发指南

## ⚠️ 重要提醒（修改前必读）

> **每次修改本 skill 的任何文件，完成后必须立即执行 git 提交！**
> 
> **每次修改本 skill 的任何文件，完成后必须立即执行 git 提交！**
> 
> **每次修改本 skill 的任何文件，完成后必须立即执行 git 提交！**

**正确的工作流程**：
```
修改文件 → 验证结果 → git add → git commit → 告知用户提交完成
```

**禁止的做法**：
- ❌ 等待用户说"提交git"才提交
- ❌ 批量修改多个文件后只提交一次（除非它们属于同一变更）
- ❌ 修改后忘记提交

---

## 项目简介

perf-hunter 是一个基于 SPEAR (**S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning) 方法论的性能诊断工具集，用于分析 Linux 性能数据，特别适用于 Cgroup 约束、低频采样（19Hz）或复杂多线程应用环境。

---

## 目录结构

```
.
├── AGENTS.md              # 本文件 - 开发指南和约定
├── SKILL.md               # 技能文档 - 面向用户的性能诊断方法论（入口）
├── docs/
│   └── CHANGES.md         # 修改记录 - 每次修改的理由和详情
├── references/            # 参考资料
│   ├── workflow.md        # 分析流程指南（7个Phase、典型模式）
│   ├── tools.md           # 工具命令参考（命令、参数）
│   ├── heuristics.md      # 启发式规则手册（认知闭包、诊断规则）
│   ├── templates.md       # 文档模板（诊断报告格式）
│   ├── data-format.md     # 数据格式说明（perf script解析）
│   └── EVOLUTION.md       # 项目演进历史
├── scripts/
│   ├── perf_expert.py     # 主入口脚本 - 包含所有子命令的 CLI
│   ├── parse_test2.py     # 测试脚本
│   └── perf_toolkit/      # 核心工具包 (Python 包)
│       ├── __init__.py
│       ├── core/          # 核心引擎
│       │   ├── engine.py       # PerfExpertEngine 类和解析逻辑
│       │   └── reliability.py  # 样本可靠性评估
│       └── analysis/      # 分析模块
│           ├── anomalies.py      # CPU 利用率异常检测
│           ├── bottleneck.py     # CPU 瓶颈检测
│           ├── callgraph.py      # 调用图 DOT/JSON 生成
│           ├── clusters.py       # 符号聚类（专家规则）
│           ├── comm_clusters.py  # 按进程名聚类
│           ├── comm_top.py       # 按进程组统计 CPU
│           ├── core_distribution.py  # 核心级负载分布分析
│           ├── cpu_usage.py      # CPU 利用率分解
│           ├── flamegraph.py     # FlameGraph 格式生成
│           ├── hotspots.py       # 热点函数分析
│           ├── path_clusters.py  # 按调用路径聚类 (Trie)
│           ├── process_top.py    # 进程 CPU 排行
│           ├── process_variety.py # 进程风暴检测
│           └── trace.py          # 调用归因追踪
```

---

## 开发约定

### 1. 修改记录规范
- 每次修改 skill 都需要在 `docs/CHANGES.md` 中记录相关的修改信息和修改理由
- 版本变化信息**不要**记录在 skill 本体（SKILL.md 或脚本）里面

### 2. 代码规范
- 代码中尽量少使用 regex，尤其是对外参数
- 遵循现有的模块化架构，新功能添加到 `perf_toolkit/analysis/` 目录

### 3. 文档引用准则

SKILL.md 应保持精简，详细内容应放在 references/ 目录，通过引用方式组织：

| 内容类型 | 应放在 | 不应放在 |
|----------|--------|----------|
| 完整文档模板 | `references/templates.md` | SKILL.md 附录 |
| 详细分析流程 | `references/workflow.md` | SKILL.md 标准工作流 |
| 工具命令详情 | `references/tools.md` | SKILL.md 工具清单 |
| 启发式规则详情 | `references/heuristics.md` | SKILL.md 核心原则 |
| 数据格式说明 | `references/data-format.md` | SKILL.md 正文 |

**引用格式示例**:
```markdown
📗 **分析流程指南**: `references/workflow.md` - 标准工作流程
```

### 4. 版本控制（⚠️ 强制执行）

**🚨 铁律：每次修改 skill 都必须立即 git 提交！**

- 完成任何文件修改后，**立即**执行 `git add` 和 `git commit`
- 提交信息应清晰描述变更内容
- 不要等待用户提醒才提交
- 多个相关文件可以一起提交，但应在修改完成后立即进行

---

## 子命令清单

| 子命令 | 用途 | 所在模块 |
|--------|------|----------|
| `check-cpu-bottleneck` | 检查资源限制和单核饱和 | `bottleneck.py` |
| `get-hotspots` | 识别热点函数 | `hotspots.py` |
| `cluster-symbols` | 按专家规则聚类符号 | `clusters.py` |
| `find-callers` | 热点溯源，调用链分析 | `trace.py` |
| `detect-anomalies` | 检测时序异常 | `anomalies.py` |
| `generate-flamegraph` | 生成 FlameGraph 格式 | `flamegraph.py` |
| `generate-callgraph` | 生成调用图 | `callgraph.py` |
| `show-cpu-usage` | 查看 CPU 利用率 | `cpu_usage.py` |
| `get-process-top` | 进程 CPU 排行 | `process_top.py` |
| `cluster-comm` | 按进程名聚类 | `comm_clusters.py` |
| `cluster-paths` | 按调用路径聚类 | `path_clusters.py` |
| `count-process-variety` | 检测进程风暴 | `process_variety.py` |
| `analyze-core-distribution` | 核心级负载分布分析 | `core_distribution.py` |
| `get-comm-top` | 按进程组统计 CPU | `comm_top.py` |

---

## 输入数据格式

工具集接受 `perf script` 的输出作为输入，需要包含 `core/s` 字段：

```bash
# 录制 perf 数据（需要 -F 19 或其他频率）
perf record -F 19 -a -g -- sleep 30

# 生成脚本输出
perf script > perf.data.txt

# 使用工具分析
python scripts/perf_expert.py get-hotspots --data perf.data.txt
```

---

## 版本历史

- **v2.5** (2026-02-28): 新增问题边界判定规则和样本丢失评估规则
- **v2.4** (2026-02-28): 重构文档体系，SKILL.md 压缩 63%，新增 workflow.md/heuristics.md
- **v2.3** (2026-02-28): 完善 AGENTS.md 和 CLI 帮助信息
- **v2.1** (2026-02-28): 新增 `analyze-core-distribution` 工具，支持核心级负载分析
- **v2.0** (Previous): 移除 `--freq` 参数，直接从 core/s 计算 CPU 利用率

---

## ✅ 修改检查清单（完成修改后逐项确认）

在结束任何修改任务前，确认以下事项：

- [ ] 所有修改的文件已保存
- [ ] 修改记录在 `docs/CHANGES.md` 中（如适用）
- [ ] **已完成 `git add` 和 `git commit`**
- [ ] 已向用户告知提交结果

**⚠️ 未勾选最后一项，任务不算完成！**
