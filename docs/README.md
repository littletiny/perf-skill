# SHECR-perf-hunter 文档中心

> **SHECR**: **S**ystematic **H**ypothesis **E**vidence **C**ontrolled **R**easoning 性能诊断方法论

---

## 📖 文档地图

### 🚀 快速入门

| 文档 | 说明 |
|------|------|
| [SKILL.md](../SKILL.md) | **主入口** - 快速开始、核心原则、工具速查 |
| [../references/methodology.md](../references/methodology.md) | 三层架构驱动的完整分析方法论 |
| [../references/tools.md](../references/tools.md) | 命令参数完整参考 |
| [../references/templates.md](../references/templates.md) | 诊断报告模板 |

### 🏗️ 架构设计

| 文档 | 说明 |
|------|------|
| [design-three-tier-architecture.md](./design-three-tier-architecture.md) | 三层架构设计详解（系统→时间→实体→函数→模式） |
| [analysis-layer-design.md](./analysis-layer-design.md) | 分析层设计规范 |
| [design-rationale-consolidated-toolchain.md](./design-rationale-consolidated-toolchain.md) | 工具链整合设计原理 |
| [design-cli-refactoring.md](./design-cli-refactoring.md) | CLI 重构设计 |
| [component-interfaces.md](./component-interfaces.md) | 组件接口设计 |

### 🔌 接口规范

| 文档 | 说明 |
|------|------|
| [interface-cli.md](./interface-cli.md) | CLI 接口规范 |
| [interface-core.md](./interface-core.md) | 核心接口定义 |
| [interface-composite.md](./interface-composite.md) | 组合接口设计 |
| [interface-analysis.md](./interface-analysis.md) | 分析接口规范 |
| [trace-interface.md](./trace-interface.md) | Trace 系统接口 |

### 📊 命令与输出

| 文档 | 说明 |
|------|------|
| [commands-three-tier.md](./commands-three-tier.md) | 三层架构命令设计 |
| [interface-composite.md](./interface-composite.md) | 复合命令设计 |
| [output-format-spec.md](./output-format-spec.md) | 输出格式规范 |
| [output-design-composite.md](./output-design-composite.md) | 复合输出设计 |
| [output-system.md](./output-system.md) | 输出系统架构 |

### 🔍 专项工具设计

| 文档 | 说明 |
|------|------|
| [tool-bottleneck-trace.md](./tool-bottleneck-trace.md) | `bottleneck-trace` 工具设计 |
| [sys-audit-refactoring-report.md](./sys-audit-refactoring-report.md) | `sys-audit` 重构报告 |
| [plan-absorb-core-distribution.md](./plan-absorb-core-distribution.md) | 核心分布分析整合计划 |

### ⚙️ 工程实现

| 文档 | 说明 |
|------|------|
| [agent-pipeline-design.md](./agent-pipeline-design.md) | Agent 流水线设计 |
| [agent-pipeline-usage.md](./agent-pipeline-usage.md) | Agent 流水线使用指南 |
| [infra-refactoring-plan.md](./infra-refactoring-plan.md) | 基础设施重构计划 |
| [project-structure.md](./project-structure.md) | 项目结构说明 |
| [EVOLUTION.md](./EVOLUTION.md) | 版本演进记录 |
| [CHANGELOG.md](./CHANGELOG.md) | 变更日志 |

### 🧩 设计原理与决策

| 文档 | 说明 |
|------|------|
| [design-rationale-trace-v1.md](./design-rationale-trace-v1.md) | Trace 系统设计原理 v1 |
| [design-rationale-trace-v2.md](./design-rationale-trace-v2.md) | Trace 系统设计原理 v2 |
| [design-attention-steering.md](./design-attention-steering.md) | 注意力引导机制设计 |
| [design-analysis-directions.md](./design-analysis-directions.md) | 分析方向设计 |
| [design-issue-overflow-warning.md](./design-issue-overflow-warning.md) | 问题溢出警告设计 |
| [methodology-hierarchical-debugging.md](./methodology-hierarchical-debugging.md) | 分层调试方法论 |

### 🔧 重构与优化

| 文档 | 说明 |
|------|------|
| [refactoring-plan-redundancy.md](./refactoring-plan-redundancy.md) | 冗余消除重构计划 v1 |
| [refactoring-plan-redundancy-v2.md](./refactoring-plan-redundancy-v2.md) | 冗余消除重构计划 v2 |
| [analysis-implementation-summary.md](./analysis-implementation-summary.md) | 分析实现总结 |
| [interface-consistency-report.md](./interface-consistency-report.md) | 接口一致性报告 |
| [interface-implementation-report.md](./interface-implementation-report.md) | 接口实现报告 |
| [risk-display-customization.md](./risk-display-customization.md) | 风险展示定制 |

### 👥 团队协作

| 文档 | 说明 |
|------|------|
| [team-division-three-tier.md](./team-division-three-tier.md) | 三层架构团队分工 |
| [audit-process.md](./audit-process.md) | 审计流程规范 |
| [LESSONS.md](./LESSONS.md) | 经验教训总结 |

---

## 🎯 按场景导航

### 我想了解 SHECR 方法论
→ [SKILL.md](../SKILL.md) → [../references/methodology.md](../references/methodology.md)

### 我想查看可用命令
→ [../references/tools.md](../references/tools.md) → [commands-three-tier.md](./commands-three-tier.md)

### 我想理解架构设计
→ [design-three-tier-architecture.md](./design-three-tier-architecture.md) → [analysis-layer-design.md](./analysis-layer-design.md)

### 我想开发/扩展工具
→ [interface-core.md](./interface-core.md) → [component-interfaces.md](./component-interfaces.md) → [../references/data-format.md](../references/data-format.md)

### 我想写诊断报告
→ [../references/templates.md](../references/templates.md) → [../references/methodology.md](../references/methodology.md#附录-a典型分析模式)

---

## 📚 外部参考

- [../AGENTS.md](../AGENTS.md) - 项目 AGENTS.md（工作目录上下文说明）
- [../config/](../config/) - 配置文件目录
- [../pipeline/](../pipeline/) - 流水线实现目录
- [../scripts/](../scripts/) - 脚本工具目录
- [../tests/](../tests/) - 测试目录

---

*文档生成时间: 2026-03-04*
*版本: 见 [../version](../version)*
