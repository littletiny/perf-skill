# AGENTS.md - perf-hunter Skill 开发指南

## 项目简介

perf-hunter 是一个基于 SPEAR (Systematic Performance Empirical Analysis & Reflection) 方法论的性能诊断工具集，用于分析 Linux 性能数据，特别适用于 Cgroup 约束、低频采样（19Hz）或复杂多线程应用环境。

---

## 目录结构

```
.
├── AGENTS.md              # 本文件 - 开发指南和约定
├── SKILL.md               # 技能文档 - 面向用户的性能诊断方法论
├── docs/
│   └── CHANGES.md         # 修改记录 - 每次修改的理由和详情
├── references/            # 参考资料
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
- 这些信息**不要**记录在 skill 本体（SKILL.md 或脚本）里面

### 2. 代码规范
- 代码中尽量少使用 regex，尤其是对外参数
- 遵循现有的模块化架构，新功能添加到 `perf_toolkit/analysis/` 目录

### 3. 版本控制
- 每次修改 skill 都需要通过 git 来提交变更，做到历史改动可追溯

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

- **v2.1** (2026-02-28): 新增 `analyze-core-distribution` 工具，支持核心级负载分析
- **v2.0** (Previous): 移除 `--freq` 参数，直接从 core/s 计算 CPU 利用率
