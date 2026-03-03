# 项目目录结构

本文档记录 perf-hunter 项目的完整目录结构，按模块组织。

---

## 根目录

```
├── AGENTS.md              # Agent 开发指南
├── SKILL.md               # 用户入口文档
├── version                # 版本号文件
├── config/                # 配置文件
├── docs/                  # 设计文档
├── pipeline/              # 多轮 Agent 流水线
├── references/            # 参考资料
├── scripts/               # 主脚本和核心代码
└── tests/                 # 测试数据与用例
```

---

## config/ - 配置文件

| 文件 | 说明 |
|------|------|
| `defaults.py` | 默认配置（Python 常量定义） |
| `perf-hunter.json` | Perf Hunter 主配置 |
| `default-rules.json` | 默认规则配置 |
| `risk-default.json` | 默认 Risk 显示配置 |

---

## docs/ - 设计文档

### 架构设计
| 文件 | 说明 |
|------|------|
| `design-three-tier-architecture.md` | 三层架构设计 - Core/Analysis/Composite 分层架构 |
| `interface-core.md` | Core Layer 接口设计 - 强类型 dataclass 接口规范 |
| `design-analysis-directions.md` | 分析方向性设计 - Top-Down vs Bottom-Up |
| `design-attention-steering.md` | Attention Steering 设计 - 基于 Flag 的诊断关注点引导 |
| `design-cli-refactoring.md` | CLI 重构设计文档 |
| `agent-pipeline-design.md` | Agent 流水线架构设计 - 多轮诊断-审计-复查 |
| `commands-three-tier.md` | 三层架构命令设计 |
| `analysis-layer-design.md` | 分析层设计文档 |

### Trace 相关
| 文件 | 说明 |
|------|------|
| `design-rationale-trace-v1.md` | Trace v1.0 设计意图 - 基于 netstat 案例的问题追踪 |
| `design-rationale-trace-v2.md` | Trace v2.0 演进设计 - 从手动记录到全自动 Tracing |
| `trace-interface.md` | Trace 接口设计 - CLI 接口与技术规格 |
| `design-issue-overflow-warning.md` | Issue 溢出警告设计 |

### 工具链与输出
| 文件 | 说明 |
|------|------|
| `design-rationale-consolidated-toolchain.md` | 工具链整合设计 - 从12个到6个核心工具 |
| `output-format-spec.md` | 工具输出格式规范 - 统一 JSON 标准 |
| `output-system.md` | Output System 快速参考 |
| `output-design-composite.md` | 组合层输出设计 |
| `risk-display-customization.md` | Risk 消息展示自定义设计 |
| `analysis-implementation-summary.md` | 分析层实现总结 |

### 流程与团队
| 文件 | 说明 |
|------|------|
| `audit-process.md` | 审计流程 - 项目审计员验证 issues 分析质量指南 |
| `agent-pipeline-usage.md` | Agent 流水线使用指南 |
| `team-division-three-tier.md` | 团队分工文档 - 3-4人开发分工与协作流程 |
| `methodology-hierarchical-debugging.md` | 分层调试方法论 |
| `infra-refactoring-plan.md` | 基础设施重构计划 |

### 接口规范
| 文件 | 说明 |
|------|------|
| `interface-core.md` | Core Layer 接口规范 - Engine、数据模型、Risk 结构 |
| `interface-analysis.md` | Analysis Layer 接口规范 - Analyzer、Facade、分析结果类型 |
| `interface-composite.md` | Composite Layer 接口规范 - 聚合器、诊断器、报告结构 |
| `interface-cli.md` | CLI Layer 接口规范 - 命令处理器、装饰器 |
| `interface-consistency-report.md` | 接口一致性检查报告 |
| `interface-implementation-report.md` | 接口实现报告 |
| `component-interfaces.md` | 组件接口总览 - 三层架构接口全景 |

### 项目维护
| 文件 | 说明 |
|------|------|
| `CHANGELOG.md` | 版本变更记录 |
| `LESSONS.md` | 设计决策与经验教训 |
| `EVOLUTION.md` | 项目演进历史 |
| `project-structure.md` | 项目目录结构（本文档） |

### 重构与计划
| 文件 | 说明 |
|------|------|
| `plan-absorb-core-distribution.md` | 吸收 core-distribution 功能计划 |
| `refactoring-plan-redundancy.md` | 冗余代码重构计划 |
| `refactoring-plan-redundancy-v2.md` | 冗余代码重构计划 v2 |
| `sys-audit-refactoring-report.md` | sys-audit 重构报告 |
| `tool-bottleneck-trace.md` | bottleneck-trace 工具文档 |

---

## pipeline/ - 多轮 Agent 流水线

```
pipeline/
├── prompts/               # Prompt 模板
│   ├── auditer.md         # 审计 Agent Prompt
│   ├── prompt.md          # 主诊断 Agent Prompt
│   └── rediagnose.md      # 复查 Agent Prompt
├── agents.yaml            # Agent 配置定义
├── pipeline.py            # 流水线核心实现
└── pipeline.yaml          # 流水线配置
```

---

## references/ - 参考资料

| 文件 | 说明 |
|------|------|
| `methodology.md` | 分析方法论（三层架构驱动） |
| `tools.md` | 工具命令参考 |
| `templates.md` | 文档模板 |
| `data-format.md` | 数据格式说明 |
| `example-rules.json` | 规则示例 |

---

## scripts/ - 主脚本和核心代码

### 入口脚本
| 文件 | 说明 |
|------|------|
| `shecr.py` | 主入口 CLI |
| `shecr_wrap.py` | Shell 包装脚本 |
| `shecr` | 可执行入口（软链接或包装） |

### perf_toolkit/ - 核心工具包

#### cli/ - 命令行接口层
```
cli/
├── main.py                # CLI 主入口
├── env.py                 # 环境管理
├── decorators.py          # 命令装饰器
├── builders.py            # 输出构建器
├── commands/              # 命令实现
│   ├── analysis/          # 分析命令 (6个)
│   │   ├── __init__.py
│   │   ├── anomalies.py   # detect-anomalies
│   │   ├── callers.py     # find-callers
│   │   ├── comm_top.py    # get-comm-top
│   │   ├── core_dist.py   # analyze-core-distribution
│   │   ├── hotspots.py    # get-hotspots
│   │   └── path_clusters.py # cluster-paths
│   ├── composite/         # 组合命令 (2个)
│   │   ├── __init__.py
│   │   ├── sys_audit.py   # sys-audit
│   │   └── bottleneck_trace.py # bottleneck-trace
│   ├── env/               # 环境命令 (4个)
│   │   ├── __init__.py
│   │   ├── init.py        # env init
│   │   ├── list.py        # env list
│   │   ├── status.py      # env status
│   │   └── use.py         # env use
│   └── trace/             # Trace 命令 (9个)
│       ├── __init__.py
│       ├── add.py         # trace add
│       ├── audit.py       # trace audit
│       ├── complete.py    # trace complete
│       ├── export.py      # trace export
│       ├── finalize.py    # trace finalize
│       ├── init.py        # trace init
│       ├── issues.py      # trace issues
│       ├── reopen.py      # trace reopen
│       └── timeline.py    # trace timeline
```

#### core/ - 基础核心层
| 文件 | 说明 |
|------|------|
| `engine.py` | 核心引擎（PerfExpertEngine） |
| `engine_types.py` | 引擎类型定义 |
| `models.py` | 核心数据模型 |
| `symbol.py` | 符号处理 |
| `trace.py` | 诊断追踪（LiveDoc） |
| `reliability.py` | 样本可靠性评估 |
| `attention_tags.py` | Attention Tags 定义 |
| `attention_tags_examples.py` | Attention Tags 示例 |
| `risk_config.py` | Risk 配置管理 |
| `command_decorator.py` | 命令装饰器 |
| `config_loader.py` | 配置加载器 |
| `core_distribution_builder.py` | Core 分布构建器 |
| `output_models.py` | 输出数据模型定义 |
| `output_builder.py` | 输出构建器 |
| `output_adapter.py` | JSON 输出转换 |
| `text_output_adapter.py` | 文本输出转换 |
| `display_presets.py` | 显示配置预设 |
| `format_utils.py` | 时间/格式工具 |

#### analysis/ - 分析实现层
| 文件 | 说明 |
|------|------|
| `base.py` | 分析器基类 |
| `interfaces.py` | 分析接口定义 |
| `facade.py` | 分析门面接口 |
| `models.py` | 分析数据模型 |
| `anomalies.py` | 异常检测实现 |
| `core_distribution.py` | 核心负载分布分析 |
| `comm_top.py` | 进程组分析 |
| `hotspots.py` | 热点函数识别 |
| `trace.py` | 调用链分析 |
| `path_clusters.py` | 调用路径聚类 |

#### composite/ - 组合诊断层
| 文件 | 说明 |
|------|------|
| `sys_audit.py` | 系统全景扫描 |
| `bottleneck_trace.py` | 瓶颈深度追踪 |
| `bottleneck_tracer.py` | 瓶颈追踪器实现 |
| `risk_aggregator.py` | Risk 聚合器 |
| `models.py` | 组合诊断数据模型 |

---

## tests/ - 测试数据与用例

```
tests/
├── perfdata/              # 性能数据测试
│   ├── new_format/        # 新格式数据
│   │   ├── case_test.data
│   │   └── case_huge_samples.data
│   ├── perf_format/       # perf 格式数据
│   │   └── case_test.data
│   ├── test_perfdata.py   # 数据格式测试
│   └── ...                # 其他测试数据文件
├── three_tier/            # 三层架构测试
│   ├── __init__.py
│   ├── QUICKSTART.md      # 快速开始指南
│   ├── TEST_GUIDE.md      # 测试指南
│   ├── quick_test.py      # 快速测试
│   ├── run_all_tests.py   # 运行所有测试
│   ├── verify_interfaces.py # 接口验证
│   ├── test_core_interfaces.py
│   ├── test_facade_interfaces.py
│   ├── test_composite_commands.py
│   ├── test_three_tier_e2e.py
│   ├── test_risk_integration.py
│   ├── test_trace_boundary.py
│   └── test_bottleneck_tracer.py
├── risk/                  # Risk 配置测试
│   └── test_risk_display_config.py
├── shecr_wrap/            # CLI 包装测试
│   └── test_shecr_wrap.py
├── scenario/              # 场景测试
│   ├── expect/            # 预期结果
│   ├── run_tests.sh       # 场景测试运行脚本
│   ├── ns/                # netstat 场景
│   └── ps/                # 进程场景
├── test_issue_overflow_warning.py  # Issue 溢出警告测试
├── test_trace_audit.py    # Trace 审计测试
└── run_tests.py           # 统一测试入口
```

### 测试分类说明

| 测试目录 | 说明 |
|----------|------|
| `tests/perfdata/` | 数据格式解析测试 |
| `tests/three_tier/` | 三层架构接口与 E2E 测试 |
| `tests/risk/` | Risk 显示配置测试 |
| `tests/shecr_wrap/` | CLI 包装脚本测试 |
| `tests/scenario/` | 真实场景测试（人工验证） |

---

## 三层架构对应关系

```
┌─────────────────────────────────────────────────────────┐
│  Composite Layer (组合诊断层)                              │
│  scripts/perf_toolkit/composite/                         │
│  - sys_audit.py                                          │
│  - bottleneck_trace.py                                   │
│  - bottleneck_tracer.py                                  │
├─────────────────────────────────────────────────────────┤
│  Analysis Layer (分析层)                                   │
│  scripts/perf_toolkit/analysis/                          │
│  - anomalies.py, core_distribution.py                    │
│  - comm_top.py, hotspots.py                              │
│  - trace.py, path_clusters.py                            │
├─────────────────────────────────────────────────────────┤
│  Core Layer (核心层)                                       │
│  scripts/perf_toolkit/core/                              │
│  - engine.py, models.py, symbol.py, trace.py             │
│  - output_*.py, risk_config.py                           │
│  - config_loader.py, core_distribution_builder.py        │
└─────────────────────────────────────────────────────────┘
```

---

## 接口设计文档

### 分层接口规范

| 文档 | 层级 | 说明 |
|------|------|------|
| `docs/interface-core.md` | Core Layer | Engine、OutputBuilder、数据模型接口 |
| `docs/interface-analysis.md` | Analysis Layer | Analyzer、Facade、分析结果类型 |
| `docs/interface-composite.md` | Composite Layer | RiskAggregator、诊断器、报告结构 |
| `docs/interface-cli.md` | CLI Layer | 命令处理器、装饰器、输出渲染 |
| `docs/interface-consistency-report.md` | 跨层 | 接口一致性检查报告 |

### 总体接口规范
📘 **组件接口总览**: `docs/component-interfaces.md` - 三层架构接口总览

---

## 文件命名约定

| 类型 | 命名模式 | 示例 |
|------|----------|------|
| Python 模块 | 下划线命名 | `core_distribution.py` |
| 测试文件 | `test_<feature>.py` | `test_perfdata.py` |
| 设计文档 | `design-<topic>.md` | `design-three-tier-architecture.md` |
| 参考文档 | `<topic>.md` | `methodology.md`, `tools.md` |
| 配置数据 | `*.json` | `default-rules.json` |
