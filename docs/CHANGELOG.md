# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.36] - 2026-03-03

### Added
- 新增 `references/methodology.md` 分析方法论文档（三层架构驱动）
- 新增"强制单根因"认知陷阱章节
- 新增"待验证假设"章节（突发限流、负载变化、链路抖动）

### Changed
- 重构 `references/workflow-patterns.md` 为附录形式，指向 methodology.md
- 更新 `SKILL.md`、`AGENTS.md`、`tools.md`、`templates.md` 文档引用
- 三候选假说扩充为代码/架构/环境三个维度，每维度3条可验证假说

### Removed
- 删除 `references/workflow-legacy.md`（使用已删除工具名）
- 删除 `references/workflow-core.md`（被 methodology.md 替代）
- 删除 `references/heuristics.md`（内容整合进 methodology.md）

**Changed files**: `version`, `references/methodology.md`, `references/workflow-patterns.md`, `references/tools.md`, `references/templates.md`, `SKILL.md`, `AGENTS.md`

---

## [2.35] - 2026-03-03

### Added
- 新增三层架构设计文档 `docs/design-three-tier-architecture.md`
- 新增团队分工文档 `docs/team-division-three-tier.md`
- 新增工具链整合设计文档 `docs/design-rationale-consolidated-toolchain.md`
- 新增命令设计文档 `docs/commands-three-tier.md`
- 新增分析层实现总结 `docs/analysis-implementation-summary.md`
- 新增三层架构分析层设计文档 `docs/analysis-layer-design.md`
- perfdata测试新增4个工具的测试：detect-anomalies、sys-audit、bottleneck-trace、storm-trace

### Fixed
- 修复 `storm_trace.py` 中生命周期数据访问方式（从字典改为对象属性）

### Changed
- 更新 `tests/perfdata/README.md` 添加新工具说明

**Changed files**: `version`, `docs/design-three-tier-architecture.md`, `docs/team-division-three-tier.md`, `docs/design-rationale-consolidated-toolchain.md`, `docs/commands-three-tier.md`, `docs/analysis-implementation-summary.md`, `docs/analysis-layer-design.md`, `scripts/perf_toolkit/composite/storm_trace.py`, `tests/perfdata/README.md`, `tests/perfdata/test_perfdata.py`

---

## [2.34] - 2026-03-03

### Added
- Core 层新增 `get_pid_cpu_util()` 方法，支持按 PID 聚合 CPU 利用率（合并相同 PID 的不同 comm）
- Core 层新增 `PidCPUInfo` 数据类
- Analysis Facade 新增 `analyze_callers()` 方法，支持调用链溯源分析（内部接口，不触发 Trace）
- 生命周期分析增强：记录进程首次出现时的调用栈，用于溯源分析

### Fixed
- Composite `sys_audit` 修复参数名错误：`threshold` → `spike_threshold`

**Changed files**: `scripts/perf_toolkit/core/engine.py`, `scripts/perf_toolkit/core/engine_types.py`, `scripts/perf_toolkit/analysis/facade.py`, `scripts/perf_toolkit/composite/sys_audit.py`, `version`

---

## [2.33] - 2026-03-02

### Added
- 新增 **多轮 Agent 流水线架构** (`pipeline/`)，实现诊断-审计-复查三轮协作
- 新增 `PipelineController` 控制器，管理流水线生命周期和状态
- 新增三个 Agent 实现：
  - `DiagnoseAgent`: 执行 SPEAR 诊断流程，自动记录 trace
  - `AuditAgent`: 四阶段审计（结构/关联/深度/文档），识别 gaps
  - `RecheckAgent`: 根据审计结果补充分析和验证
- 新增 Pipeline CLI (`pipeline/cli.py`)，支持 `run/diagnose/audit/recheck/status` 命令
- 新增设计文档 `docs/agent-pipeline-design.md`，详细说明架构设计
- 新增使用指南 `docs/agent-pipeline-usage.md`，提供完整使用示例
- 新增示例脚本 `pipeline/example.py`，演示各种使用场景
- 支持流水线状态保存和恢复（`save()` / `load()`）
- 支持分步执行和完整流水线两种模式
- 支持自定义 Agent 扩展

**Changed files**: `pipeline/*`, `docs/agent-pipeline-design.md`, `docs/agent-pipeline-usage.md`, `AGENTS.md`, `version`

---

## [2.32] - 2026-03-02

### Added
- 新增 `spear trace audit` 命令，用于**事后独立审计**诊断质量
- 审计流程文档 `docs/audit-process.md`，明确：
  - Audit 是**事后独立流程**，诊断完成后才进行
  - Audit 和 finalize **完全独立**，无交互依赖
  - Audit 结果用于**质量反馈和学习**，不阻塞诊断
- 支持三阶段审计：structural（结构完整性）、timeline（Timeline 关联）、depth（分析深度）
- 自动检测敷衍 result（如 "ok", "done", "fixed"）
- 自动检测 analysis gap（无分析命令即标记完成）
- 自动检测过短分析时间（<30秒）
- 新增测试 `tests/test_trace_audit.py` 验证审计功能

### Changed
- 重构 `docs/audit-process.md` 明确**完全独立的两个流程**：
  - 诊断流程：工程师独立完成诊断并 finalize
  - 审计流程：独立审计员事后检查，不阻塞、不 reopen
- 更新 SKILL.md 分离诊断流程和审计流程说明
- 更新 references/tools.md 明确 audit/finalize 的独立性
- `finalize` 输出改为 "FINALIZE"（避免与 audit 混淆）
- 更新 AGENTS.md 文档清单

**Changed files**: `scripts/perf_toolkit/core/trace.py`, `scripts/spear.py`, `docs/audit-process.md`, `SKILL.md`, `references/tools.md`, `AGENTS.md`, `version`, `tests/test_trace_audit.py`

---

## [2.31] - 2026-03-02

### Added
- 新增 `@command` 装饰器统一分析命令入口 (`scripts/perf_toolkit/core/command_decorator.py`)
- wrap 脚本支持 `--risk-config` 和 `--rules-file` 参数自动跟随 data 文件
- wrap `trace` 子命令自动注入 `--risk-config`
- wrap `cluster-symbols` 命令自动注入 `--rules-file`
- `spear status` 和 `spear list` 显示 Risk 和 Rules 配置
- 新增统一测试运行器 `tests/run_tests.py`

### Changed
- 重构 11 个分析命令使用 `@command` 装饰器，消除样板代码
- 统一命令入口：装饰器自动处理 builder、样本获取、空检查、质量评估、Trace 记录

### Fixed
- 移除 `spear.py` 中与装饰器重复的 `run_analysis_command` 函数

**Changed files**: `scripts/perf_toolkit/core/command_decorator.py`, `scripts/perf_toolkit/core/__init__.py`, `scripts/perf_toolkit/analysis/*.py` (11 files), `scripts/spear.py`, `scripts/spear_wrap.py`, `version`

---

## [2.30] - 2026-03-02

### Added
- wrap 脚本 `spear init` 支持 `--risk-config` 和 `--rules-file` 参数
- wrap 自动为 `trace` 子命令注入 `--risk-config`
- wrap 自动为 `cluster-symbols` 命令注入 `--rules-file`
- `spear status` 和 `spear list` 显示 Risk 和 Rules 配置

**Changed files**: `scripts/spear_wrap.py`, `SKILL.md`, `references/tools.md`

---

## [2.29] - 2026-03-02

### Changed
- 重写 AGENTS.md，优化目录结构和设计文档导航
- 补充 core/ 模块完整文件导航表格
- 新增「章节编号规范」和「命令与文档同步规范」

**Changed files**: `AGENTS.md`

---

## [2.28] - 2026-03-02

### Changed
- 统一变量命名：`core_sec` → `weight`（所有 analysis 模块）
- 数据模型字段统一：`clustered_core_sec` → `clustered_weight` 等
- 清理冗余注释（关于 core/s 的说明）

**Changed files**: `analysis/*.py`, `core/*.py` (14 files)

---

## [2.27] - 2026-03-02

### Changed
- 解耦命令与格式化逻辑：数据模型只存原始值，模板负责格式化
- `AnomalyItem` 存储原始时间戳而非格式化字符串
- `PathClusterItem` 存储原始 `core_sec` 而非百分比

**Changed files**: `output_models.py`, `text_output_adapter.py`, `anomalies.py`, `path_clusters.py`

---

## [2.26] - 2026-03-02

### Changed
- event 格式统一：`<EVENT:value>` → `EVENT(value)`

**Changed files**: `comm_clusters.py`, `comm_top.py`

---

## [2.25] - 2026-03-02

### Added
- 新建 `display_presets.py` 集中管理所有显示格式配置
- `TemplateConfig.from_preset()` 方法

### Changed
- 所有 Output 类通过 preset 引用配置，不再分散定义
- 统一截断提示逻辑

**Changed files**: `display_presets.py`, `output_models.py`, `text_output_adapter.py`

---

## [2.24] - 2026-03-02

### Added
- 模板化输出系统：`TemplateConfig` 配置类
- 5类模板渲染器：`simple_list`, `key_value`, `table`, `nested`, `custom`

### Changed
- `text_output_adapter.py` 从 ~400 行精简至 ~300 行
- 添加新命令只需在 model 中指定 template

**Changed files**: `output_models.py`, `text_output_adapter.py`, `display_presets.py`

---

## [2.23] - 2026-03-02

### Added
- engine 模块新增统一 CPU 利用率计算接口
- `get_process_cpu_util()`, `get_comm_cpu_util()`, `get_symbol_cpu_util()`, `get_core_cpu_util()`

### Changed
- 12 个 analysis 模块迁移到新接口
- 消除重复的 `*_core_sec` 计算逻辑

**Changed files**: `engine.py`, `analysis/*.py` (12 files)

---

## [2.22] - 2026-03-02

### Added
- 所有 list 输出接口支持截断提示
- `shown_*` 字段记录实际显示数量

**Changed files**: `output_models.py`, `text_output_adapter.py`, `analysis/*.py`

---

## [2.21] - 2026-03-02

### Added
- 所有 list 接口支持 `--top-n` 参数（默认 10）
- `find-callers` 统一使用 `--top-n`（移除 `--auto-target-top-n`）

### Changed
- `get-hotspots` 默认按 self 排序
- 列表输出添加 format header
- `find-callers` 箭头改为 `<-` 表示被调用关系

**Changed files**: `spear.py`, `hotspots.py`, `find-callers.py`, `text_output_adapter.py`

---

## [2.20] - 2026-03-02

### Changed
- `get-process-top` 输出格式：`comm pid=PID cpu=X%` → `comm(PID) total_util/kernel_util`
- 新增 header 行描述格式

**Changed files**: `process_top.py`, `text_output_adapter.py`

---

## [2.19] - 2026-03-01

### Added
- `wrap` 脚本 `scripts/perf`（后重命名为 `spear`）
- 支持 `.perf_env` 配置文件自动注入 `--data` 参数

### Changed
- 简化命令执行：初始化后无需重复指定路径

**Changed files**: `scripts/perf`, `CHANGES.md`

---

## [2.18] - 2026-03-01

### Changed
- `doc` 子命令重命名为 `trace`
- LiveDoc v2.0：只自动添加 issue，不自动解决
- `spear init` 顺带执行 `trace init`

**Changed files**: `spear.py`, `trace.py`, `SKILL.md`, `AGENTS.md`

---

## [2.17] - 2026-03-01

### Added
- V2 输出系统：`@dataclass` 替代字典，类型安全
- `output_models.py`, `output_adapter.py`, `output_builder.py`

### Removed
- `generate-flamegraph`, `generate-callgraph` 子命令（低频率使用）

**Changed files**: `core/*.py`, `analysis/*.py`, `spear.py` (13 个分析模块迁移)

---

## [2.16] - 2026-03-01

### Changed
- 强化 risk hint 语义：所有 hint 改为 `[必须] 添加到 Live Document`
- `output-format-spec.md` 新增 `_risk.action_required` 强制规则

**Changed files**: `output-format-spec.md`, `analysis/*.py` (13 个模块)

---

## [2.15] - 2026-03-01

### Added
- 5 层文档架构：入口层 → 场景模式层 → 核心流程层 → 参考层 → 规则层
- `workflow-patterns.md`：5 种典型分析模式专册
- 模式 E：高内核态分析

### Changed
- `SKILL.md` 压缩 67%：311 行 → 102 行
- `workflow.md` 拆分为 `workflow-core.md` + `workflow-patterns.md`

**Changed files**: `SKILL.md`, `workflow-core.md`, `workflow-patterns.md`, `tools.md`

---

## [2.14] - 2026-03-01

### Changed
- 强化 `add_risk` hint 语义描述（使用「强制性」「必须」等措辞）
- 改进进程风暴检测：基于 `samples_per_pid` ratio 而非绝对数量

**Changed files**: `risk_mixin.py`, `process_variety.py`

---

## [2.13] - 2026-03-01

### Changed
- 消除 risk hint 中的占位符（`<target>`, `<pid>`, `<lock_func>`）
- `bottleneck.py`：无 pid 时提供获取方法而非占位符
- `clusters.py`：自动使用最频繁的锁函数名

**Changed files**: `bottleneck.py`, `clusters.py`, `core_distribution.py`

---

## [2.12] - 2026-03-01

### Added
- Live Document 机制整合到 Skill 文档体系
- 强制审计规则：`doc list` 每 2-3 个工具后执行，`doc finalize` 生成报告前必须执行

### Changed
- `SKILL.md` 新增「Live Document 机制（强制执行）」章节
- `workflow.md` Phase 1/7 嵌入审计检查点

**Changed files**: `SKILL.md`, `workflow.md`, `CHANGES.md`

---

## [2.11] - 2026-03-01

### Added
- Live Document CLI 工具：`doc init/add/complete/list/finalize/export`
- 问题追踪流程：完整的问题生命周期管理

**Changed files**: `live_doc.py`, `spear.py`

---

## [2.10] - 2026-02-28

### Added
- 工具输出格式规范 v1.0
- 必须字段 `_risk`：风险置顶，包含 level/message/hint/patterns/targets
- 时间字段规范：ISO 8601 字符串格式

**Changed files**: `output-format-spec.md`, `risk_mixin.py`, `format_utils.py`

---

## [2.9] - 2026-02-28

### Added
- Live Document 机制：解决「搜索空间不足导致关键问题遗漏」
- 强制审计：生成报告前必须检查剩余风险
- 覆盖率阈值：达到 80% 或显式接受风险后才能收敛

**Changed files**: `SKILL.md`, `CHANGES.md`, `design-rationale-trace-v1.md`

---

## [2.8.1] - 2026-03-01

### Added
- 兼容 SPEAR 和原始 perf 两种数据格式
- `--freq` 参数支持原始 perf 格式 CPU 利用率计算
- 自动格式检测：`get_sample_weight()` 统一处理

**Changed files**: `engine.py`, `spear.py`

---

## [2.8] - 2026-02-28

### Changed
- 修复 `callgraph.py` 权重统计：使用 `core/s` 而非简单计数
- 统一字段命名：`user_samples` → `user_records`, `kernel_samples` → `kernel_records`

**Changed files**: `callgraph.py`, `engine.py`, `cpu_usage.py`, `parse_test2.py`

---

## [2.7] - 2026-02-28

### Added
- 建立「目标一致」核心准则：工具参数必须与目标问题一致
- 「目标范围界定」表格：特定进程/进程组/时段的参数要求

### Changed
- `SKILL.md` 关键检查点表格添加 `[--pid <PID>]` 提示
- `workflow.md` Phase 1.1 新增一致性检查清单

**Changed files**: `SKILL.md`, `workflow.md`

---

## [2.6] - 2026-02-28

### Fixed
- 数据格式解析：`tid` 字段统一修正为 `pid`
- 修复 12 个分析模块中的字段引用

**Changed files**: `engine.py`, `analysis/*.py` (6 个文件)

---

## [2.5] - 2026-02-28

### Added
- 启发式规则手册新增「问题边界判定规则」
- 「样本丢失评估规则」：丢点是系统问题指示器

**Changed files**: `heuristics.md`

---

## [2.4] - 2026-02-28

### Changed
- `SKILL.md` 压缩 63%：319 行 → 118 行
- 文档拆分：`tools.md` → `workflow.md` + `tools.md`
- 重命名：`methodology.md` → `heuristics.md`
- SPEAR 展开含义优化：`Systematic Problem Evidence-driven Analysis & Reasoning`

**Changed files**: `SKILL.md`, `workflow.md`, `tools.md`, `heuristics.md`

---

## [2.3] - 2026-02-28

### Added
- `AGENTS.md` 重构：完整目录结构、子命令清单、输入数据格式说明
- CLI 帮助增强：复杂参数详细说明和使用示例

**Changed files**: `AGENTS.md`, `spear.py`

---

## [2.2] - 2026-02-28

### Added
- `get-comm-top` 工具：按进程名聚合 CPU 消耗排名
- 「大量小进程」模式自动检测：`MANY_SMALL_PROCESSES`

**Changed files**: `comm_top.py`, `spear.py`, `tools.md`

---

## [2.1] - 2026-02-28

### Added
- `analyze-core-distribution` 工具：核心级负载分布分析
- `SINGLE_CORE_SATURATION` 模式检测

### Fixed
- `cluster-symbols --custom-rules` 支持列表格式规则

**Changed files**: `core_distribution.py`, `clusters.py`, `SKILL.md`, `tools.md`

---

## [2.0] - 2026-02-28

### Changed
- **架构级转折**：放弃严格线性 SOP，转向「多路径并行假设驱动」模式
- 废除决策树，改为规则驱动 + 启发式指导
- 竞争性假设并行验证：至少 3 条假设同时验证

**Changed files**: `SKILL.md`, `analyze-core-distribution.py`

---

## [0.8] - 2026-02-28

### Changed
- 从「严格 SOP」到「假设驱动」的核心转变
- 给 Agent 自由度：工具选择、分析顺序、收敛时机灵活化
- 关键检查点强制：finish_task_switch 必须溯源

**Changed files**: `SKILL.md`

---

## [0.7] - 2026-02-28

### Added
- Step 0: 业务领域理解（应用类型识别 → 激活领域知识 → 建立预期基准）
- 异常检测框架：每一步后的检查清单
- 结论校验机制：业务合理性、量化验证、架构合理性

### Changed
- PID 2573405 案例复盘：领域知识与工具联用割裂问题

**Changed files**: `SKILL.md`

---

## Template

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- 新增功能

### Changed
- 变更功能

### Fixed
- 修复问题

### Removed
- 移除功能

**Changed files**: `file1`, `file2`
```
