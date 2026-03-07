# SHECR Agent Pipeline 设计

> 设计文档：基于 Code Agent 的简化流水线架构
> 版本: 2.0
> 更新: 2026-03-04

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SHECR Agent Pipeline v2.0                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │  diagnose    │ ──→ │    audit     │ ──→ │   recheck    │             │
│  │  (coder)     │     │   (coder)    │     │   (coder)    │             │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘             │
│         │                    │                    │                     │
│    input: template      input: template      input: template            │
│         ↓                    ↓                    ↓                     │
│    vars: {{DATA}}       vars: {{diagnose.      vars: {{audit.           │
│         {{output.xxx}}        output.report}}        output.report}}    │
│         ↓                    ↓                    ↓                     │
│    output: report       output: report       output: report             │
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════    │
│  条件执行: when: "{{audit.status}} == 'failed'"                          │
│  变量语法: {{var}} 或 {{stage.output.key}}                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 核心概念

### Stage

每个 stage 是一个独立的 Code Agent 执行单元：

```yaml
stage_name:
  when: "执行条件"           # 可选，条件满足时才执行
  agent:                     # Agent 配置
    system_prompt: "..."
    allowed_dirs: ["..."]
    default_permissions: "read-write"
  vars:                      # Stage 变量
    input.template: "prompts/input.txt"
    output.report: "{{WORK_DIR}}/report.md"
```

### 变量系统

支持 `{{var}}` 语法（Jinja2 风格）：

| 类型 | 语法 | 示例 |
|------|------|------|
| 普通变量 | `{{VAR_NAME}}` | `{{WORK_DIR}}` → `./output` |
| Stage 输出 | `{{stage.output.key}}` | `{{diagnose.output.report}}` |
| Stage 状态 | `{{stage.status}}` | `{{audit.status}}` → `failed` |
| Stage 退出码 | `{{stage.exit_code}}` | `{{diagnose.exit_code}}` → `0` |

### 执行条件

使用 `when` 字段控制 stage 是否执行：

```yaml
recheck:
  when: "{{audit.status}} == 'failed'"
```

支持的操作：
- 比较：`==`, `!=`, `>`, `<`, `>=`, `<=`
- 存在检查：`exists({{file}})`
- 逻辑：`not()`, `and`, `or`

---

## 数据流

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Config + Templates                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ config.yaml │  │ diagnose_   │  │ audit_      │  │ recheck_    │   │
│  │             │  │ input.txt   │  │ input.txt   │  │ input.txt   │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │          │
│         └────────────────┴────────────────┴────────────────┘          │
│                          ↓                                             │
│                   ┌─────────────┐                                      │
│                   │  Pipeline   │                                      │
│                   │  Runner     │                                      │
│                   └──────┬──────┘                                      │
│                          ↓                                             │
│         ┌────────────────┼────────────────┐                           │
│         ↓                ↓                ↓                           │
│    ┌─────────┐     ┌─────────┐     ┌─────────┐                       │
│    │ Stage 1 │ ──→ │ Stage 2 │ ──→ │ Stage 3 │                       │
│    │(render  │     │(render  │     │(render  │                       │
│    │ template│     │ template│     │ template│                       │
│    │ + vars) │     │ + vars) │     │ + vars) │                       │
│    └────┬────┘     └────┬────┘     └────┬────┘                       │
│         ↓                ↓                ↓                           │
│    ┌─────────┐     ┌─────────┐     ┌─────────┐                       │
│    │ output/ │     │ output/ │     │ output/ │                       │
│    │diagnose │     │ audit   │     │ recheck │                       │
│    └─────────┘     └─────────┘     └─────────┘                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 配置文件格式

### 完整示例

```yaml
# Pipeline 定义：stage 名称用 " - " 连接
pipeline: diagnose - audit - recheck

# 全局变量（所有 stage 可用，stage 可覆盖）
vars:
  DATA_FILE: "/path/to/perf.data"
  WORK_DIR: "./output"
  DATA_DIR: "./data"
  SYMPTOM: "系统响应慢，CPU使用率100%"

# 全局 Agent 配置（作为 stage 的默认值）
agent:
  system_prompt: "prompts/default_system.md"
  allowed_dirs:
    - "{{WORK_DIR}}"
    - "{{DATA_DIR}}"
  default_permissions: "read-write"
  timeout: 300
  model: "kimi"
  working_dir: "{{WORK_DIR}}"

# Stage 1: 诊断
diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"
    allowed_dirs:
      - "{{WORK_DIR}}/diagnose"
      - "{{DATA_DIR}}"
    timeout: 600
  vars:
    ROLE: "性能诊断专家"
    input.template: "prompts/diagnose_input.txt"
    output.report: "{{WORK_DIR}}/diagnose/report.md"

# Stage 2: 审计
audit:
  agent:
    system_prompt: "prompts/audit_system.md"
    default_permissions: "read-only"
  vars:
    ROLE: "诊断审计员"
    input.template: "prompts/audit_input.txt"
    input.report: "{{diagnose.output.report}}"  # 引用 diagnose 的输出
    output.report: "{{WORK_DIR}}/audit/report.md"

# Stage 3: 复查（仅在审计失败时执行）
recheck:
  when: "{{audit.status}} == 'failed'"
  agent:
    system_prompt: "prompts/recheck_system.md"
    timeout: 600
  vars:
    ROLE: "复查专家"
    input.template: "prompts/recheck_input.txt"
    input.diagnose: "{{diagnose.output.report}}"
    input.audit: "{{audit.output.report}}"
    output.report: "{{WORK_DIR}}/recheck/final_report.md"
```

### 配置字段说明

#### 顶层字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `pipeline` | 是 | Stage 定义，用 `-` 连接 |
| `vars` | 否 | 全局变量 |
| `agent` | 否 | 全局 Agent 配置 |

#### Agent 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `system_prompt` | string | - | System prompt 文件路径 |
| `allowed_dirs` | list | [] | 允许访问的目录列表 |
| `default_permissions` | string | read-write | read-only/read-write/write-only |
| `timeout` | int | 300 | 超时时间（秒） |
| `model` | string | kimi | 模型名称 |
| `working_dir` | string | - | 工作目录 |

#### Stage 配置

| 字段 | 必需 | 说明 |
|------|------|------|
| `when` | 否 | 执行条件 |
| `agent` | 否 | Stage 级 Agent 配置（覆盖全局） |
| `vars` | 否 | Stage 变量（覆盖全局同名变量） |

### Input 模板

**diagnose_input.txt:**
```
你是{{ROLE}}，请分析数据文件 {{DATA_FILE}}。

症状描述：{{SYMPTOM}}

输出诊断报告到：{{output.report}}

要求：
1. 识别所有性能瓶颈
2. 提供三候选假设验证
3. 进行调用链溯源
```

---

## 执行流程

### 变量解析流程

```
1. 合并变量（全局 + Stage）
   ↓
2. 递归解析变量引用（{{var}} → 值）
   ↓
3. 解析 Stage 输出引用（{{stage.output.xxx}}）
   ↓
4. 替换 input.template 中的变量
   ↓
5. 生成最终任务文件
```

### Stage 执行流程

```
1. 评估 when 条件
   - 条件不满足 → 跳过 stage（status=skipped）
   - 条件满足 → 继续执行
   
2. 读取 input.template
   ↓
3. 渲染模板（变量替换）
   ↓
4. 构建 Agent Prompt
   - 添加 system_prompt
   - 添加环境信息（permissions, allowed_dirs）
   - 添加渲染后的任务内容
   ↓
5. 调用 Code Agent（coder subagent）
   ↓
6. 记录执行结果
   - status: success/failed/skipped
   - exit_code
   - outputs（所有 output.* 变量）
```

---

## Python 实现

### 核心类

```python
# pipeline/pipeline.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentConfig:
    """Agent 配置"""
    system_prompt: Optional[str] = None
    allowed_dirs: List[str] = field(default_factory=list)
    default_permissions: str = "read-write"
    timeout: int = 300
    model: str = "kimi"
    working_dir: Optional[str] = None


@dataclass
class StageConfig:
    """Stage 配置"""
    name: str
    agent: AgentConfig
    vars: Dict[str, str] = field(default_factory=dict)
    when: Optional[str] = None


@dataclass
class StageResult:
    """Stage 执行结果"""
    status: str  # success / failed / skipped
    exit_code: int
    outputs: Dict[str, str] = field(default_factory=dict)


class PipelineRunner:
    """Pipeline 运行器"""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.results: Dict[str, StageResult] = {}
    
    def _replace_vars(self, content: str, vars_dict: Dict[str, str]) -> str:
        """替换 {{var}} 变量"""
        ...
    
    def _check_condition(self, condition: str) -> bool:
        """评估 when 条件"""
        ...
    
    def _run_stage(self, stage_name: str, stage_config: StageConfig) -> StageResult:
        """执行单个 stage"""
        ...
    
    def run(self):
        """运行完整 pipeline"""
        ...
```

---

## 使用示例

### CLI 使用

```bash
# 运行 pipeline
python pipeline/pipeline.py config.yaml

# 输出示例:
# Pipeline: diagnose -> audit -> recheck
#
# [STAGE] diagnose
#   Agent: kimi
#   Permissions: read-write
#   Task file: ./output/.pipeline_diagnose_task.txt
#   Running agent...
#   Agent completed
#   Output: output.report -> ./output/diagnose/report.md
#
# [STAGE] audit
#   Agent: kimi
#   Permissions: read-only
#   ...
#
# [STAGE] recheck
#   SKIPPED (condition: {{audit.status}} == 'failed')
#
# ============================================================
# Pipeline Summary:
#   ✓ diagnose: success
#   ✓ audit: success
#   ○ recheck: skipped
#
# [COMPLETE] Pipeline 'diagnose - audit - recheck' finished successfully
```

### 条件执行示例

```yaml
# 复杂条件示例
recheck:
  when: "{{audit.status}} == 'failed' and {{diagnose.issue_count}} > 0"

# 文件存在检查
enhance:
  when: "exists({{audit.output.gaps_file}})"

# 逻辑组合
critical_review:
  when: "({{audit.failed_count}} > 3) or ({{diagnose.exit_code}} != 0)"
```

---

## 与旧版对比

| 特性 | 旧版 Pipeline (v1.0) | 新版 Pipeline (v2.0) |
|------|---------------------|---------------------|
| Agent 实现 | 自定义 Python 类 | Code Agent (coder subagent) |
| 配置方式 | 代码内定义 | YAML 配置文件 |
| 输入方式 | 复杂数据结构 | 模板文件 + 变量替换 |
| 变量语法 | 无 | `{{var}}` (Jinja2 风格) |
| 条件执行 | 内置逻辑 | `when` 字段显式配置 |
| 权限控制 | 内置 | Agent 配置 (allowed_dirs, permissions) |
| 灵活性 | 低（固定流程） | 高（任意 stage 定义） |

---

## 参考

- [agent-pipeline-usage.md](./agent-pipeline-usage.md) - 使用指南
- [../pipeline/README.md](../pipeline/README.md) - 实现文档
- [../SKILL.md](../SKILL.md) - SHECR 方法论
