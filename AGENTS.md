# AGENTS.md - perf-hunter Skill 开发指南

## 项目简介

perf-hunter 是基于 SPEAR (**S**ystematic **P**roblem **E**vidence-driven **A**nalysis & **R**easoning) 方法论的性能诊断工具集，用于分析 Linux 性能数据，适用于 Cgroup 约束、低频采样（19Hz）或复杂多线程环境。

---

## 核心原则

- **修改前确认**：先简要说明方案，等确认后再修改
- **简单优先**：let it crash，不做复杂错误处理
- **AI 友好**：输出格式便于人类/AI 阅读
- **数据文件规范**：只使用本工具读取 `.data` 文件，特殊情况一次最多读取 20 行

### 输出设计原则

所有工具输出必须遵循以下原则，确保 AI 和人类都能快速理解：

**风险置顶**
所有输出必须包含 _risk 字段，放在最前面。包含 level/message/hint/action_required 四个字段，不要有其他嵌套。

**扁平结构**
JSON 嵌套不超过 2 层。不要用深层嵌套对象，列表项用简单结构，避免多级 children 嵌套。

**时间格式**
时间字段统一用 ISO 8601 字符串格式，如 "2026-03-02T10:30:00+08:00"。不要自定义格式。

**简单列表**
列表输出用简单数组，每个元素是平面对象。不要用表格边框字符，不要用缩进对齐，不要加装饰性分隔线。

**命名直接**
字段名用直白英文，如 symbol/comm/pid/util。不要用缩写或前缀，如 sym/c/p/util_pct 等。

**数值原始**
数值字段存原始值，格式化交给渲染层。百分比存 0.15 而不是 "15%"，时间存时间戳而不是格式化字符串。

---

## 目录结构

```
├── AGENTS.md              # 本文件 - 开发指南
├── SKILL.md               # 用户入口文档
├── docs/                  # 设计文档（⚠️ 新增文档必须更新此处）
│   ├── CHANGELOG.md                          # 格式化的版本变更记录
│   ├── LESSONS.md                            # 设计决策与经验教训（按主题组织）
│   ├── agent-pipeline-design.md              # Agent 流水线架构设计 - 多轮诊断-审计-复查
│   ├── agent-pipeline-usage.md               # Agent 流水线使用指南
│   ├── audit-process.md                      # 审计流程 - 项目审计员验证 issues 分析质量指南
│   ├── command-design.md                     # 诊断命令设计文档 - 功能矩阵与场景选择决策
│   ├── design-rationale-consolidated-toolchain.md  # 工具链整合设计 - 从12个到6个核心工具的精简与增强
│   ├── design-rationale-trace-v1.md          # Trace v1.0 设计意图 - 基于 netstat 案例的问题追踪机制
│   ├── design-rationale-trace-v2.md          # Trace v2.0 演进设计 - 从手动记录到全自动 Tracing
│   ├── design-three-tier-architecture.md     # 三层架构设计 - Core/Analysis/Composite 分层架构与接口规范
│   ├── team-division-three-tier.md           # 团队分工文档 - 3-4人开发分工与协作流程
│   ├── output-format-spec.md                 # 工具输出格式规范 - 统一 JSON 标准（_risk、时间格式等）
│   ├── output-system.md                      # Output System 快速参考 - 统一数据结构与代码复用
│   ├── risk-display-customization.md         # Risk 消息展示自定义设计 - 可配置的 risk 输出格式与样式
│   └── trace-interface.md                    # Trace 接口设计 - CLI 接口与技术规格
├── pipeline/              # 多轮 Agent 流水线
│   ├── __init__.py        # 包入口
│   ├── controller.py      # 流水线控制器
│   ├── agents.py          # Agent 实现（Diagnose/Audit/Recheck）
│   └── cli.py             # 命令行接口
├── references/            # 参考资料
│   ├── methodology.md     # 分析方法论（三层架构驱动）
│   ├── tools.md           # 工具命令参考
│   ├── templates.md       # 文档模板
│   ├── data-format.md     # 数据格式说明
│   └── EVOLUTION.md       # 项目演进历史
├── scripts/
│   ├── spear.py           # 主入口 CLI
│   └── perf_toolkit/      # 核心工具包
│       ├── core/          # 基础库
│       │   ├── engine.py           # 核心引擎（PerfExpertEngine）
│       │   ├── reliability.py      # 样本可靠性评估
│       │   ├── symbol.py           # 符号处理
│       │   ├── trace.py            # 诊断追踪（LiveDoc）
│       │   ├── risk_mixin.py       # 风险信息标准化
│       │   ├── format_utils.py     # 时间/格式工具
│       │   ├── output_models.py    # 数据模型定义
│       │   ├── output_adapter.py   # JSON 输出转换
│       │   ├── text_output_adapter.py  # 文本输出转换
│       │   ├── output_builder.py   # 输出构建器
│       │   └── display_presets.py  # 显示配置预设
│       └── analysis/      # 分析模块（各子命令实现）
└── tests/                 # 测试数据与用例
```

---

## 开发约定

### 章节编号规范
- **禁止使用数字编号**（如 `### 1. xxx`），避免章节变动时连锁修改
- 统一使用标题文字本身作为标识

### 文档维护规范

**版本更新流程：**

1. 修改 `$repo/version` 文件
2. 更新 `docs/CHANGELOG.md`（Keep a Changelog 格式）
3. **如需要**，更新 `docs/LESSONS.md`（重大设计决策）
4. **如新增 `docs/` 文档**，更新「目录结构」章节中的文件清单
5. git commit

**CHANGELOG 格式：**
```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added/Changed/Fixed/Removed
- 一句话描述变更

**Changed files**: `file1`, `file2`
```

**重要原则：**
- 版本信息**不要**记录在 SKILL.md 或脚本中
- LESSONS.md 按**主题**组织（方法论、架构、踩坑记录），不按版本
- docs/ 下文件必须遵循「目录结构」中的文件清单格式

### 代码规范
- 尽量少用 regex，尤其避免在对外参数中使用
- 修改工具代码后**必须**同步更新相关文档

### 命令与文档同步规范
- **修改或新增 CLI 命令时，必须同步更新 SKILL.md 和 references/tools.md**
- 保持命令参数、输出格式与实际代码一致，避免用户阅读错误信息



### 测试相关

⚠️ **重要**: 添加新测试必须符合 `tests/` 目录结构，详见 `tests/README.md`

**测试路径规范**（必须放在正确位置）：

| 测试类型 | 正确路径 | 示例 |
|---------|---------|------|
| 系统级功能测试 | `tests/test_<feature>.py` | `tests/test_issue_overflow_warning.py` |
| 三层架构测试 | `tests/three_tier/` | `tests/three_tier/test_core_interfaces.py` |
| Risk 配置测试 | `tests/risk/` | `tests/risk/test_risk_display_config.py` |
| Rules 加载测试 | `tests/clusters/` | `tests/clusters/test_rules_loading.py` |
| 数据格式测试 | `tests/perfdata/` | `tests/perfdata/test_perfdata.py` |
| CLI 测试 | `tests/spear_wrap/` | `tests/spear_wrap/test_spear_wrap.py` |
| 场景测试 | `tests/scenario/<name>/` | `tests/scenario/netstat/` |

**测试数据**: `tests/perfdata/new_format/case_test.data`

**开发后必做**（添加新功能或修改功能后）：
```bash
# 运行所有自动化测试（不包括 scenario/ 人工验证）
python3 tests/test_issue_overflow_warning.py
python3 tests/risk/test_risk_display_config.py
python3 tests/clusters/test_rules_loading.py
python3 tests/clusters/test_external_rules_integration.py
python3 tests/perfdata/test_perfdata.py
python3 tests/spear_wrap/test_spear_wrap.py
```

**统一测试入口**：使用 `tests/run_tests.py` 运行所有自动化测试
```bash
# 运行所有测试
python3 tests/run_tests.py

# 详细输出
python3 tests/run_tests.py -v

# 失败时停止
python3 tests/run_tests.py -f
```

### 文档引用准则

SKILL.md 保持精简，详细内容放 references/ 目录：

| 内容类型 | 应放在 | 不应放在 |
|----------|--------|----------|
| 文档模板 | `references/templates.md` | SKILL.md 附录 |
| 分析方法论 | `references/methodology.md` | SKILL.md 标准工作流 |
| 分析模式 | `references/methodology.md#附录-a典型分析模式` | SKILL.md 场景详解 |
| 工具命令 | `references/tools.md` | SKILL.md 工具清单 |
| 数据格式 | `references/data-format.md` | SKILL.md 正文 |

引用格式示例：
```markdown
📗 **分析方法论**: `references/methodology.md` - 三层架构驱动的完整方法论
```

---

## 子命令清单

### 核心分析工具（6个）

| 子命令 | 层级 | 用途 | 所在文件 |
|--------|------|------|----------|
| `analyze-core-distribution` | 系统级 | 核心负载分析（整合原check-cpu-bottleneck） | `scripts/perf_toolkit/analysis/core_distribution.py` |
| `detect-anomalies` | 时间级 | 检测时序异常 | `scripts/perf_toolkit/analysis/anomalies.py` |
| `get-comm-top` | 实体级 | 进程组分析（增强版，整合原get-process-top + cluster-comm + count-process-variety） | `scripts/perf_toolkit/analysis/comm_top.py` |
| `get-hotspots` | 函数级 | 识别热点函数 | `scripts/perf_toolkit/analysis/hotspots.py` |
| `find-callers` | 关系级 | 热点溯源，调用链分析 | `scripts/perf_toolkit/analysis/trace.py` |
| `cluster-paths` | 模式级 | 调用路径聚类（整合原cluster-symbols） | `scripts/perf_toolkit/analysis/path_clusters.py` |

### 组合诊断工具（2个）

| 子命令 | 链式触发 | 用途 | 所在文件 |
|--------|----------|------|----------|
| `sys-audit` | anomalies→core-dist→comm-top | 系统全景扫描，自动降噪 | `scripts/perf_toolkit/composite/sys_audit.py` |
| `bottleneck-trace` | comm-top→hotspots→paths | 瓶颈深度追踪 | `scripts/perf_toolkit/composite/bottleneck_trace.py` |

### 工具整合说明

| 原工具 | 整合到 | 新能力 |
|--------|--------|--------|
| `check-cpu-bottleneck` | `analyze-core-distribution` | 单核饱和检测 |
| `show-cpu-usage` | `analyze-core-distribution` | CPU利用率展示 |
| `get-process-top` | `get-comm-top` | CV方差识别离群PID |
| `cluster-comm` | `get-comm-top` | 进程组聚合 |
| `count-process-variety` | `get-comm-top` | Spawn Rate检测 |
| `cluster-symbols` | `cluster-paths` | 语义聚类 |

---

## 输入数据格式

详见 `references/data-format.md`
