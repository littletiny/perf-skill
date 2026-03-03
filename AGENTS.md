# AGENTS.md - perf-hunter Skill 开发指南

## 项目简介

perf-hunter 是基于 **SHECR**（**S**ystematic **H**ypothesis **E**vidence-driven **C**ontrolled **R**easoning）方法论的性能诊断工具集，用于分析 Linux 性能数据，适用于 Cgroup 约束、低频采样（19Hz）或复杂多线程环境。

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

## 项目结构

### 目录与接口文档

📁 **完整目录结构**: `docs/project-structure.md`

📘 **分层接口规范**:
- `docs/interface-core.md` - Core Layer 接口
- `docs/interface-analysis.md` - Analysis Layer 接口  
- `docs/interface-composite.md` - Composite Layer 接口
- `docs/interface-cli.md` - CLI Layer 接口
- `docs/interface-consistency-report.md` - 接口一致性检查报告

> 开发前请先阅读上述文档，了解代码组织、文件命名和层间接口约定。
> 
> **重要原则**：禁止在层间传递裸 `dict`/`List[Dict]`，必须使用强类型 `dataclass`。

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
4. **如新增 `docs/` 文档**，同步更新 `docs/project-structure.md`
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
- docs/ 下文件清单维护在 `docs/project-structure.md`

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
| CLI 测试 | `tests/shecr_wrap/` | `tests/shecr_wrap/test_shecr_wrap.py` |
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
python3 tests/shecr_wrap/test_shecr_wrap.py
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

### Attention Steering (SHECR 核心机制)

本项目基于 **SHECR** 方法论使用 Attention Steering 机制防止诊断过程中的"信息权重衰减"：

| 缩写 | 原则 | 机制体现 |
|------|------|----------|
| **S** | Systematic | 三层架构（Core/Analysis/Composite） |
| **H** | Hypothesis | `<X0>` 必须追踪到根因才能收敛（延迟收敛）|
| **E** | Evidence-driven | `<XA>` 基于证据的行动建议 |
| **C** | Controlled | 多轮 Pipeline 控制收敛节奏 |
| **R** | Reasoning | 因果关系追踪与逻辑推理 |

- **定义位置**: `SKILL.md` 的 `SHECR Attention Flags` 章节
- **加载方式**: Skill 触发后自动进入 System Prompt
- **匹配机制**: Tool 输出的 `_risk.patterns` 字段触发 Flag 匹配
- **开发要求**: 新增工具时，如检测到关键线索，应在 `patterns` 中标记对应 Flag

详见设计文档: `docs/design-attention-steering.md`

---

## 输入数据格式

详见 `references/data-format.md`
