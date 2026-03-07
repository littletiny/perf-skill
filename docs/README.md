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

---

### 🏗️ design/ - 架构与机制设计

| 文档 | 说明 |
|------|------|
| [design/design-three-tier-architecture.md](./design/design-three-tier-architecture.md) | 三层架构设计详解（系统→时间→实体→函数→模式） |
| [design/design-output.md](./design/design-output.md) | 输出系统设计 - 格式规范、核心指标计算 |
| [design/analysis-layer-design.md](./design/analysis-layer-design.md) | 分析层设计规范 |
| [module/core/how/trace-mechanism.md](./module/core/how/trace-mechanism.md) | Trace 机制设计 - 数据格式、CLI接口、自动记录 |
| [design/design-attention-steering.md](./design/design-attention-steering.md) | 注意力引导机制设计（`<X0>`/`<X1>`/`<XA>`） |
| [design/design-analysis-directions.md](./design/design-analysis-directions.md) | 分析方向设计 - Top-Down vs Bottom-Up |
| [design/design-cli-refactoring.md](./design/design-cli-refactoring.md) | CLI 重构设计 |
| [design/design-rationale-consolidated-toolchain.md](./design/design-rationale-consolidated-toolchain.md) | 工具链整合设计原理 |
| [design/design-issue-overflow-warning.md](./design/design-issue-overflow-warning.md) | Issue 溢出警告设计 |

---

### 🔌 interface/ - 接口规范

| 文档 | 说明 |
|------|------|
| [interface/interface-core.md](./interface/interface-core.md) | Core Layer 接口规范 |
| [interface/interface-analysis.md](./interface/interface-analysis.md) | Analysis Layer 接口规范 |
| [interface/interface-composite.md](./interface/interface-composite.md) | Composite Layer 接口规范 |
| [interface/interface-cli.md](./interface/interface-cli.md) | CLI Layer 接口规范 |
| [interface/component-interfaces.md](./interface/component-interfaces.md) | 组件接口总览 - 三层架构接口全景 |

---

### 📋 process/ - 流程与方法论

| 文档 | 说明 |
|------|------|
| [process/commands-three-tier.md](./process/commands-three-tier.md) | 三层架构命令设计 |
| [process/audit-process.md](./process/audit-process.md) | 审计流程规范 |
| [process/team-division-three-tier.md](./process/team-division-three-tier.md) | 三层架构团队分工 |
| [process/methodology-hierarchical-debugging.md](./process/methodology-hierarchical-debugging.md) | 分层调试方法论 |

---

### 📊 report/ - 报告与工具设计

| 文档 | 说明 |
|------|------|
| [report/report-interface.md](./report/report-interface.md) | 接口一致性检查与改造报告 |
| [module/composite/what/bottleneck-analyze-tool.md](./module/composite/what/bottleneck-analyze-tool.md) | `bottleneck-analyze` 工具设计 |
| [report/sys-audit-refactoring-report.md](./report/sys-audit-refactoring-report.md) | `sys-audit` 重构报告 |
| [report/analysis-implementation-summary.md](./report/analysis-implementation-summary.md) | 分析层实现总结 |
| [report/risk-display-customization.md](./report/risk-display-customization.md) | 风险展示定制设计 |

---

### 📅 plan/ - 计划与重构

| 文档 | 说明 |
|------|------|
| [plan/plan-refactoring.md](./plan/plan-refactoring.md) | 代码冗余消除重构计划 |
| [plan/infra-refactoring-plan.md](./plan/infra-refactoring-plan.md) | 基础设施重构计划 |
| [plan/plan-absorb-core-distribution.md](./plan/plan-absorb-core-distribution.md) | 核心分布分析整合计划 |

---

### ⚙️ pipeline/ - Agent 流水线

| 文档 | 说明 |
|------|------|
| [pipeline/agent-pipeline-design.md](./pipeline/agent-pipeline-design.md) | Agent 流水线架构设计 |
| [pipeline/agent-pipeline-usage.md](./pipeline/agent-pipeline-usage.md) | Agent 流水线使用指南 |

---

### 📁 项目维护

| 文档 | 说明 |
|------|------|
| [CHANGELOG.md](./CHANGELOG.md) | 版本变更记录 |
| [LESSONS.md](./LESSONS.md) | 设计决策与经验教训 |
| [project-structure.md](./project-structure.md) | 项目结构说明 |
| [agents.md](./agents.md) | Agent 工作指南 |

---

## 🎯 按场景导航

### 我想了解 SHECR 方法论
→ [SKILL.md](../SKILL.md) → [../references/methodology.md](../references/methodology.md)

### 我想查看可用命令
→ [../references/tools.md](../references/tools.md) → [process/commands-three-tier.md](./process/commands-three-tier.md)

### 我想理解架构设计
→ [design/design-three-tier-architecture.md](./design/design-three-tier-architecture.md) → [design/design-output.md](./design/design-output.md)

### 我想开发/扩展工具
→ [interface/interface-core.md](./interface/interface-core.md) → [interface/component-interfaces.md](./interface/component-interfaces.md) → [../references/data-format.md](../references/data-format.md)

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
