# Developer Guide - 开发者快速查找指南

> 本文档面向开发者，提供快速定位代码和文档的指引。
> 
> 用户指南请查阅 [SKILL.md](../SKILL.md)。

---

## 快速决策表

| 你要找什么 | 第一步查这个 | 备选/补充 |
|-----------|-------------|----------|
| **命令实现文件** | [`cli-commands.md`](./cli-commands.md) | - |
| **命令参数/示例** | [`cli-commands.md`](./cli-commands.md) | - |
| **整体项目结构** | [`docs/meta/project-structure.md`](../docs/meta/project-structure.md) | - |
| **分层接口定义** | [`docs/interface/`](../docs/interface/) | - |
| **分析方法论** | [`methodology.md`](./methodology.md) | - |
| **数据格式规范** | [`data-format.md`](./data-format.md) | - |

---

## 详细指引

### 场景1：查找命令实现文件

**目标**：`xxx-xxx` 命令在哪个文件实现？

**推荐做法**：
```bash
# 直接查阅 cli-commands.md，搜索命令名
# 例如搜索 "### bottleneck-analyze"
```

**为什么不是 project-structure.md？**
- `cli-commands.md` 提供：精确文件路径 + 函数名 + 参数
- `project-structure.md` 仅提供：文件路径（无函数名，无参数）

**示例**：
| 命令 | cli-commands.md 提供 | project-structure.md 提供 |
|------|---------------------|--------------------------|
| `bottleneck-analyze` | 文件 + 函数 `cmd_bottleneck_analyze` + 完整参数 | 仅文件名 |

---

### 场景2：了解模块架构

**目标**：某模块包含哪些文件？它们之间的关系？

**推荐**：查阅 [`docs/meta/project-structure.md`](../docs/meta/project-structure.md)

---

### 场景3：修改接口/添加新功能

**目标**：需要了解分层接口约定

**推荐**：查阅 [`docs/interface/`](../docs/interface/)
- `interface-core.md` - Core Layer
- `interface-analysis.md` - Analysis Layer
- `interface-composite.md` - Composite Layer
- `interface-cli.md` - CLI Layer

---

## 常见误区

### ❌ 误区1：混淆 "Trace 机制" 和 "bottleneck-analyze 命令"

| 概念 | 说明 | 相关文档 |
|------|------|----------|
| `trace` 子命令系统 | 诊断追踪（`trace init/add/timeline/complete` 等） | `cli-commands.md` 第347-589行 |
| `bottleneck-analyze` | Composite 组合命令 | `cli-commands.md` 第311-344行 |

**注意**：`docs/module/core/how/trace-mechanism.md` 描述的是 `trace` 子命令系统（诊断追踪机制），而非 `bottleneck-analyze` 命令。

### ❌ 误区2：过度依赖 project-structure.md 查找实现

虽然 `project-structure.md` 包含文件列表，但它：
- 无函数级信息
- 无参数说明
- 无调用示例

**结论**：查找命令实现 → 用 `cli-commands.md`

---

## 文档索引速查

### references/ 目录

| 文件 | 用途 |
|------|------|
| `cli-commands.md` | **命令实现、参数、示例** |
| `methodology.md` | 分析方法论 |
| `tools.md` | 工具速查 |
| `data-format.md` | 数据格式规范 |
| `templates.md` | 文档模板 |

### docs/meta/ 目录

| 文件 | 用途 |
|------|------|
| `project-structure.md` | 完整目录结构、文件组织 |

### docs/interface/ 目录

| 文件 | 用途 |
|------|------|
| `interface-*.md` | 分层接口规范 |

---

## 修改本文档

当新增以下类型文档时，更新本文档：
- 新的命令类别
- 新的分层接口
- 影响文件查找路径的重构
