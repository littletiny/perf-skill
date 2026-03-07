# 开发导航 - Developer Navigation

> 📍 本文档是开发者的"地图"
>
> **原则：模糊正确 > 精确过时**

---

## 命令实现速查表

| 命令 | 类别 | 大概位置 | 查找提示 |
|------|------|----------|----------|
| get-hotspots | Analysis | `scripts/.../analysis/hotspots.py` | 函数搜 `cmd_get` |
| find-callers | Analysis | `scripts/.../analysis/callers.py` | 函数搜 `cmd_trace` |
| detect-anomalies | Analysis | `scripts/.../analysis/anomalies.py` | 函数搜 `cmd_detect` |
| cluster-paths | Analysis | `scripts/.../analysis/path_clusters.py` | 函数搜 `cmd_cluster` |
| analyze-core-distribution | Analysis | `scripts/.../analysis/core_dist.py` | 函数搜 `cmd_analyze` |
| get-comm-top | Analysis | `scripts/.../analysis/comm_top.py` | 函数搜 `cmd_get_comm` |
| sys-audit | Composite | `scripts/.../composite/sys_audit.py` | 函数搜 `cmd_sys` |
| bottleneck-analyze | Composite | `scripts/.../composite/bottleneck_analyze.py` | 函数搜 `cmd_bottleneck` |
| trace * | Trace | `scripts/.../trace/*.py` | 9个子命令分散在各文件 |

---

## 接口分层导航

| 层级 | 用途 | 入口文件 | 核心类 |
|------|------|----------|--------|
| Core | 数据存储/查询 | `scripts/.../core/engine.py` | `SampleEngine` |
| Analysis | 单维度分析 | `scripts/.../analysis/*.py` | 各分析器类 |
| Composite | 组合诊断 | `scripts/.../composite/*.py` | `*Analyzer` |
| CLI | 命令封装 | `scripts/.../cli/commands/` | `cmd_*` 函数 |

---

## 按任务查找

### 添加新命令

1. 分析层命令 → `scripts/.../cli/commands/analysis/`
2. 组合诊断命令 → `scripts/.../cli/commands/composite/`
3. trace 子命令 → `scripts/.../cli/commands/trace/`
4. 参考现有命令模式（搜 `cmd_*` 函数）

### 修改分析逻辑

1. 先定位 CLI 命令文件（见上表）
2. 分析器逻辑通常在 `scripts/.../analysis/` 或 `scripts/.../composite/`
3. 数据引擎在 `scripts/.../core/`

### 文档查找速查表

| 查找内容 | 去这里 |
|----------|--------|
| 接口规范 | `docs/interface/` |
| CLI 命令详情 | `references/cli-commands.md` |
| 数据格式 | `references/data-format.md` |
| 开发方法论 | `references/methodology.md` |
| 目录结构 | `docs/meta/project-structure.md` |

---

## 文件命名约定

| 模式 | 含义 | 示例 |
|------|------|------|
| `cmd_*.py` | CLI 命令实现 | `cmd_hotspots.py` |
| `*_analyzer.py` | Composite 分析器 | `bottleneck_analyzer.py` |
| `*_engine.py` | Core 层引擎 | `sample_engine.py` |
| `test_*.py` | 测试文件 | `test_hotspots.py` |
| `interface-*.md` | 接口规范 | `interface-core.md` |

---

## ⚠️ 重要提醒

- **不要**精确记忆路径，用 `find` 模糊查找
- **不要**依赖文档中的行号
- **代码即文档**: 实现细节以代码为准

```bash
# 模糊查找示例
find scripts -name "*hotspot*"
grep -r "cmd_get" scripts/
```
