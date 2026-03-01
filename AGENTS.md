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
│   ├── CHANGELOG.md       # 格式化的版本变更记录
│   ├── LESSONS.md         # 设计决策与经验教训（按主题组织）
│   ├── design-rationale-trace-v1.md  # Trace v1.0 设计意图 - 基于 netstat 案例的问题追踪机制
│   ├── design-rationale-trace-v2.md  # Trace v2.0 演进设计 - 从手动记录到全自动 Tracing
│   ├── output-format-spec.md         # 工具输出格式规范 - 统一 JSON 标准（_risk、时间格式等）
│   ├── output-system.md              # Output System 快速参考 - 统一数据结构与代码复用
│   └── trace-interface.md            # Trace 接口设计 - CLI 接口与技术规格
├── references/            # 参考资料
│   ├── workflow.md        # 分析流程指南（7个Phase）
│   ├── tools.md           # 工具命令参考
│   ├── heuristics.md      # 启发式规则手册
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
- 测试数据：`tests/perfdata/new_format/case_test.data`

**回归测试**：
```bash
python3 tests/perfdata/test_perfdata.py          # 测试所有格式
python3 tests/perfdata/test_perfdata.py -d new_format   # 特定格式
```

**CLI 测试**：
```bash
python3 tests/spear_wrap/test_spear_wrap.py
```

### 文档引用准则

SKILL.md 保持精简，详细内容放 references/ 目录：

| 内容类型 | 应放在 | 不应放在 |
|----------|--------|----------|
| 文档模板 | `references/templates.md` | SKILL.md 附录 |
| 分析流程 | `references/workflow.md` | SKILL.md 标准工作流 |
| 工具命令 | `references/tools.md` | SKILL.md 工具清单 |
| 启发式规则 | `references/heuristics.md` | SKILL.md 核心原则 |
| 数据格式 | `references/data-format.md` | SKILL.md 正文 |

引用格式示例：
```markdown
📗 **分析流程指南**: `references/workflow.md` - 标准工作流程
```

---

## 子命令清单

| 子命令 | 用途 | 所在文件 |
|--------|------|----------|
| `check-cpu-bottleneck` | 检查资源限制和单核饱和 | `scripts/perf_toolkit/analysis/bottleneck.py` |
| `get-hotspots` | 识别热点函数 | `scripts/perf_toolkit/analysis/hotspots.py` |
| `cluster-symbols` | 按专家规则聚类符号 | `scripts/perf_toolkit/analysis/clusters.py` |
| `find-callers` | 热点溯源，调用链分析 | `scripts/perf_toolkit/analysis/trace.py` |
| `detect-anomalies` | 检测时序异常 | `scripts/perf_toolkit/analysis/anomalies.py` |
| `show-cpu-usage` | 查看 CPU 利用率 | `scripts/perf_toolkit/analysis/cpu_usage.py` |
| `get-process-top` | 进程 CPU 排行 | `scripts/perf_toolkit/analysis/process_top.py` |
| `get-comm-top` | 按进程组统计 CPU | `scripts/perf_toolkit/analysis/comm_top.py` |
| `cluster-comm` | 按进程名聚类 | `scripts/perf_toolkit/analysis/comm_clusters.py` |
| `cluster-paths` | 按调用路径聚类 | `scripts/perf_toolkit/analysis/path_clusters.py` |
| `count-process-variety` | 检测进程风暴 | `scripts/perf_toolkit/analysis/process_variety.py` |
| `analyze-core-distribution` | 核心级负载分布分析 | `scripts/perf_toolkit/analysis/core_distribution.py` |

---

## 输入数据格式

详见 `references/data-format.md`
