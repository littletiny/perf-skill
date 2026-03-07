# 文档架构设计

> 本文档记录 perf-hunter 文档分层架构的设计决策。

---

## 分层原则

```
AGENTS.md (根)          <- 入口：必须立即知道的东西
    └── 引用 docs/meta/  <- 导航：去哪查详细信息
            └── 引用具体文档  <- 细节：实现时查阅
```

### 各层职责

| 文档 | 读者 | 内容 | 长度目标 |
|------|------|------|----------|
| `AGENTS.md` (根) | AI 开发者 | 项目简介、快速开始、核心约定、导航链接 | < 60 行 |
| `*/AGENTS.md` | AI 开发者 | 该目录的特定约定和工作流程 | 按需 |
| `SKILL.md` | 终端用户 | 使用指南、命令速查 | - |
| `docs/meta/navigation.md` | AI 开发者 | 代码位置模糊导航 | ~ 80 行 |
| `docs/interface/` | AI 开发者 | 接口规范 | - |
| `references/` | 终端用户 | 详细参考文档 | - |

---

## AGENTS.md 设计约定

### 包含什么（必须立即知道）

- 项目一句话简介
- 环境验证命令（如运行测试）
- 编码核心约定（3-5 条）
- 子目录 AGENTS.md 提示
- 导航链接

### 不包含什么（改为外链）

- 命令实现位置 → `docs/meta/navigation.md`
- 接口规范详情 → `docs/interface/`
- 目录结构详情 → `docs/meta/project-structure.md`
- 分析方法论 → `references/methodology.md`
- 数据格式 → `references/data-format.md`

---

## 历史决策

### 2026-03-07: 重构 AGENTS.md 导航架构

**问题**: 根 AGENTS.md 过于臃肿（192 行），包含过多细节

**方案**:
1. 拆分为根 AGENTS.md（入口）+ `docs/meta/navigation.md`（导航中枢）
2. 使用模糊路径减少维护压力（如 `scripts/.../analysis/`）
3. 根 AGENTS.md 行数目标 < 60 行

**结果**:
- 根 AGENTS.md: 192 行 → 约 55 行
- 新增 `docs/meta/navigation.md`: 85 行
- 子目录 AGENTS.md 提示合并到目录速览表

---

## 维护指南

**修改本文档时机**:
- 文档分层架构变更
- AGENTS.md 设计约定调整

**不修改本文档的情况**:
- 新增/删除具体命令（改 `navigation.md`）
- 接口变更（改 `docs/interface/`）
