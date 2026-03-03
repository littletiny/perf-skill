# AGENTS.md - perf-hunter Skill 开发指南

## 项目简介

perf-hunter 是基于 **SHECR**（**S**ystematic **H**ypothesis **E**vidence-driven **C**ontrolled **R**easoning）方法论的性能诊断工具集，用于分析 Linux 性能数据。

---

## 核心原则

- **修改前确认**: 先简要说明方案，等确认后再修改
- **简单优先**: let it crash，不做复杂错误处理
- **AI 友好**: 输出格式便于人类/AI 阅读
- **先设计再编码, 强制静态类型，不使用python的动态类型**

### 输出设计原则

所有工具输出必须遵循以下原则，确保 AI 和人类都能快速理解：

**时间格式**
时间字段统一用 ISO 8601 字符串格式，如 "2026-03-02T10:30:00+08:00"。不要自定义格式。

**命名直接**
字段名用直白英文，如 symbol/comm/pid/util。不要用缩写或前缀，如 sym/c/p/util_pct 等。

---

## 项目结构

### 目录与接口文档

📁 **完整目录结构**: `docs/project-structure.md`

📁 **Pipeline 模块**: `pipeline/README.md`

简化版 Code Agent 流水线，支持 YAML 配置、变量替换、条件执行：

```yaml
pipeline: diagnose - audit - recheck

vars:
  WORK_DIR: "./output"

audit:
  agent:
    default_permissions: "read-only"
  vars:
    input.report: "{{diagnose.output.report}}"

recheck:
  when: "{{audit.status}} == 'failed'"
  vars:
    input.audit: "{{audit.output.report}}"
```

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
- 不要用regex
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

详见设计文档: `docs/design-attention-steering.md`

---

## 输入数据格式

详见 `references/data-format.md`
