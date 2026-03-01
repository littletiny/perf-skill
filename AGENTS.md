# AGENTS.md - perf-hunter Skill 开发指南

---

## 项目简介

perf-hunter 是一个基于 SPEAR (**S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning) 方法论的性能诊断工具集，用于分析 Linux 性能数据，特别适用于 Cgroup 约束、低频采样（19Hz）或复杂多线程应用环境。

---

## 重要
- **修改代码之前先着急做，几句话和我确认方案，等我确认再改**
- **修改代码之前先着急做，几句话和我确认方案，等我确认再改**
- **各种代码的实现要尽可能简单，let it crash，不要做复杂的错误处理**
- **各种代码的实现要尽可能简单，let it crash，不要做复杂的错误处理**
- 本工具的输出用来给人类/AI阅读，**输出对AI友好**
- 本工具的输出用来给人类/AI阅读，**输出对AI友好**
- **数据文件一般是xxx.data，只用本skill工具读取他**
- **不要用本skill工具之外的工具读取数据文件，除非工具集解析数据出错了**
- **如果一定要用其他工具读数据文件，一次最多只能读取20行**

---

## 目录结构

```
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
- 每次完成修改skilk后都需要提交git commit，不需要我强调
- 每次完成修改skilk后都需要提交git commit，不需要我强调
- **只有用户提示要更新版本**，更新版本号文件$repo/version, 并在`docs/changelog/$version.md` 中记录相关的修改信息和修改理由
- 每当用户提示要更新版本或者push的时候，更新版本号文件$repo/version, 并在`docs/changelog/$version.md` 中记录相关的修改信息和修改理由
- 版本变化信息**不要**记录在 skill 本体（SKILL.md 或脚本）里面

### 2. 代码规范
- 代码中尽量少使用 regex，尤其是对外参数
- 遵循现有的模块化架构
- **对skill中所有文档的描述要尽可能最小修改，修改了工具代码以后都需要同步更新文档**

### 3. 测试相关
$repo/tests/perfdata/new_format/case_test.data 可以用来做测试

### 4. 文档引用准则

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

---

## 子命令清单

| 子命令 | 用途 | 所在模块 |
|--------|------|----------|
| `check-cpu-bottleneck` | 检查资源限制和单核饱和 | `bottleneck.py` |
| `get-hotspots` | 识别热点函数 | `hotspots.py` |
| `cluster-symbols` | 按专家规则聚类符号 | `clusters.py` |
| `find-callers` | 热点溯源，调用链分析 | `trace.py` |
| `detect-anomalies` | 检测时序异常 | `anomalies.py` |
| `show-cpu-usage` | 查看 CPU 利用率 | `cpu_usage.py` |
| `get-process-top` | 进程 CPU 排行 | `process_top.py` |
| `cluster-comm` | 按进程名聚类 | `comm_clusters.py` |
| `cluster-paths` | 按调用路径聚类 | `path_clusters.py` |
| `count-process-variety` | 检测进程风暴 | `process_variety.py` |
| `analyze-core-distribution` | 核心级负载分布分析 | `core_distribution.py` |
| `get-comm-top` | 按进程组统计 CPU | `comm_top.py` |

## 已移除的子命令

| 子命令 | 移除原因 |
|--------|----------|
| `generate-flamegraph` | 功能维护成本高，使用频率低 |
| `generate-callgraph` | 功能维护成本高，使用频率低 |

---

## 输入数据格式
数据格式参考/home/tiny/.config/agents/skills/perf-hunter/references/data-format.md

---
