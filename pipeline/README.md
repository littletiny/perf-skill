# Pipeline 模块（简化版）

基于 Code Agent 的多阶段流水线，使用 `{{var}}` 变量语法和条件执行。

---

## 目录结构

```
pipeline/
├── pipeline.py          # 简化版 Pipeline 运行器
├── template/            # 可复用模板（快速开始）
│   ├── config.yaml      # 模板配置
│   └── prompts/         # prompt 模板文件
│       ├── step1_system.md
│       ├── step1_input.txt
│       ├── step2_system.md
│       └── step2_input.txt
├── examples/            # 示例配置
│   ├── config.yaml      # 完整 pipeline 配置示例
│   └── prompts/         # prompt 模板文件
└── README.md            # 本文档
```

---

## 快速开始

### 方式一：使用模板（推荐）

复制模板目录，按需修改：

```bash
# 1. 复制模板
cp -r pipeline/template my_pipeline

# 2. 编辑配置文件
vim my_pipeline/config.yaml

# 3. 修改 prompt 模板
vim my_pipeline/prompts/step1_input.txt
vim my_pipeline/prompts/step2_input.txt

# 4. 运行
python pipeline/pipeline.py my_pipeline/config.yaml
```

### 方式二：从零创建

```bash
# 1. 创建目录结构
mkdir -p my_pipeline/prompts

# 2. 编写配置文件（参考 template/config.yaml）
vim my_pipeline/config.yaml

# 3. 编写 prompt 模板
vim my_pipeline/prompts/task.txt

# 4. 运行
python pipeline/pipeline.py my_pipeline/config.yaml
```

---

## 模板配置示例

```yaml
# config.yaml
pipeline: step1 - step2

vars:
  WORK_DIR: "./output"

agent:
  allowed_dirs:
    - "{{WORK_DIR}}"
  default_permissions: "read-write"
  timeout: 300

step1:
  vars:
    ROLE: "分析师"
    input.template: "prompts/step1_input.txt"
    output.result: "{{WORK_DIR}}/step1_result.txt"

step2:
  vars:
    ROLE: "报告员"
    input.template: "prompts/step2_input.txt"
    input.result: "{{step1.output.result}}"
    output.report: "{{WORK_DIR}}/final_report.md"
```

### 运行

```bash
python pipeline/pipeline.py my_pipeline/config.yaml
```

---

## 变量语法：`{{var}}`

### 基本用法

```yaml
vars:
  DATA_FILE: "/path/to/perf.data"
  WORK_DIR: "./output"

agent:
  allowed_dirs:
    - "{{WORK_DIR}}"          # → "./output"
    - "{{WORK_DIR}}/reports"  # → "./output/reports"
```

### 跨 Stage 引用

引用其他 stage 的输出：

```yaml
audit:
  vars:
    input.report: "{{diagnose.output.report}}"  # 引用 diagnose stage 的 output.report
```

引用 stage 执行状态：

```yaml
recheck:
  when: "{{audit.status}} == 'failed'"  # 根据 audit stage 的状态决定
```

### 可用的 Stage 状态变量

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{{stageName.status}}` | 执行状态 | `success`, `failed`, `skipped` |
| `{{stageName.exit_code}}` | 退出码 | `0`, `1` |
| `{{stageName.output.xxx}}` | 输出变量 | 取决于 vars 定义 |

---

## 执行条件：`when`

### 基本语法

```yaml
stage_name:
  when: "条件表达式"
  # ... 其他配置
```

### 支持的条件操作

| 操作 | 语法 | 示例 |
|------|------|------|
| 等于 | `==` | `{{audit.status}} == 'failed'` |
| 不等于 | `!=` | `{{audit.status}} != 'passed'` |
| 大于 | `>` | `{{diagnose.issue_count}} > 0` |
| 小于 | `<` | `{{diagnose.exit_code}} < 1` |
| 文件存在 | `exists()` | `exists({{audit.output.report}})` |
| 逻辑非 | `not()` | `not({{audit.passed}})` |
| 逻辑与 | `and` | `A and B` |
| 逻辑或 | `or` | `A or B` |

### 条件示例

```yaml
# 简单条件：仅当审计失败时执行复查
recheck:
  when: "{{audit.status}} == 'failed'"

# 文件存在检查
backup:
  when: "exists({{input.report}})"

# 数值比较
enhance:
  when: "{{diagnose.issue_count}} > 5"

# 逻辑组合
critical_review:
  when: "{{audit.status}} == 'failed' and {{diagnose.issue_count}} > 3"

# 复杂条件
final_check:
  when: "({{audit.status}} == 'failed' or not(exists({{audit.output.report}}))) and {{diagnose.exit_code}} == 0"

# 跳过条件（当上一阶段跳过时也跳过）
notify:
  when: "{{recheck.status}} != 'skipped'"
```

### 条件求值规则

- 如果 `when` 未指定，默认执行（相当于 `when: "true"`）
- 条件求值在变量解析之后进行，可以使用 `{{var}}` 语法
- Stage 执行后，其 `status` 会自动设置为 `success`、`failed` 或 `skipped`
- 被跳过的 stage 不会影响后续 stage 的执行（除非后续 stage 依赖其输出）

---

## 配置格式详解

### 顶层字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `pipeline` | 是 | Stage 定义，用 `-` 连接，如 `stage1 - stage2 - stage3` |
| `vars` | 否 | 全局变量，所有 stage 可用 |
| `agent` | 否 | 全局 Agent 配置，作为 stage 默认值 |

### Agent 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `system_prompt` | string | System prompt 文件路径 |
| `allowed_dirs` | list | 允许访问的目录列表（支持 `{{var}}` 变量） |
| `default_permissions` | string | 默认权限：`read-only` \| `read-write` \| `write-only` |
| `timeout` | int | 超时时间（秒） |
| `model` | string | 模型名称，默认 `kimi` |
| `working_dir` | string | 工作目录 |

### Stage 配置

```yaml
stage_name:
  when: "条件表达式"           # 可选：执行条件
  agent:                       # 可选：Stage 级 Agent 配置（覆盖全局）
    system_prompt: "..."
    timeout: 600
  vars:                        # Stage 变量（覆盖全局同名变量）
    ROLE: "专家"
    input.template: "prompts/input.txt"
    output.report: "{{WORK_DIR}}/report.md"
```

### 变量作用域

1. **全局变量**：定义在顶级 `vars` 中，所有 stage 可用
2. **Stage 变量**：定义在 stage 的 `vars` 中，覆盖全局同名变量
3. **变量引用**：变量值可以引用其他变量（递归解析）
4. **Stage 输出引用**：使用 `{{stageName.output.key}}` 引用其他 stage 输出

---

## 示例：三阶段诊断流水线

### 完整配置

```yaml
pipeline: diagnose - audit - recheck

vars:
  DATA_FILE: "./perf.data"
  WORK_DIR: "./output"

agent:
  system_prompt: "prompts/default_system.md"
  allowed_dirs:
    - "{{WORK_DIR}}"
  default_permissions: "read-write"

diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"
    timeout: 600
  vars:
    ROLE: "性能诊断专家"
    input.template: "prompts/diagnose_input.txt"
    output.report: "{{WORK_DIR}}/diagnose/report.md"

audit:
  agent:
    system_prompt: "prompts/audit_system.md"
    default_permissions: "read-only"
  vars:
    ROLE: "诊断审计员"
    input.template: "prompts/audit_input.txt"
    input.report: "{{diagnose.output.report}}"
    output.report: "{{WORK_DIR}}/audit/report.md"

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

### Input 模板示例

**diagnose_input.txt:**
```
你是{{ROLE}}，请分析数据文件 {{DATA_FILE}}。

输出诊断报告到：{{output.report}}

要求：
1. 识别所有性能瓶颈
2. 提供三候选假设验证
3. 进行调用链溯源
```

**audit_input.txt:**
```
你是{{ROLE}}，请审计以下诊断报告：

诊断报告：{{input.report}}

输出审计报告到：{{output.report}}

执行审计检查：
- 结构完整性
- Timeline 关联
- 分析深度
- 文档一致性
```

**recheck_input.txt:**
```
你是{{ROLE}}，请根据审计结果复查：

原始诊断：{{input.diagnose}}
审计报告：{{input.audit}}

以差异化视角补充分析，输出到：{{output.report}}
```

---

## 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│                     Pipeline 执行流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 解析 config.yaml                                        │
│     - 读取 pipeline 定义 (stage 列表)                        │
│     - 加载全局 vars 和 agent 配置                            │
│                                                              │
│  2. 对每个 stage：                                           │
│     a. 合并全局和 stage 级配置                               │
│     b. 解析所有变量（支持递归和跨 stage 引用）               │
│     c. 评估 when 条件，决定是否跳过                          │
│     d. 读取 input.template                                   │
│     e. 渲染模板（替换 {{var}} 变量）                         │
│     f. 构建 Agent 命令（含 system_prompt、权限等）           │
│     g. 执行 Agent                                            │
│     h. 记录结果到上下文（status, exit_code, outputs）        │
│                                                              │
│  3. 所有 stage 完成后，输出汇总报告                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 代码规范

- 变量语法：`{{var}}`（Jinja2 风格）
- 条件语法：支持比较、exists、not、and、or
- 强制静态类型（使用 dataclass）
- 配置文件使用 YAML 格式

---

## 命令行使用

```bash
# 基本用法
python pipeline/pipeline.py <config.yaml>

# 示例
python pipeline/pipeline.py pipeline/template/config.yaml
python pipeline/pipeline.py my_project/pipeline.yaml
```

---

## 创建自定义 Pipeline

### 步骤 1: 复制模板

```bash
cp -r pipeline/template my_pipeline
cd my_pipeline
```

### 步骤 2: 修改配置

编辑 `config.yaml`，修改：
- `pipeline`: stage 名称列表
- `vars`: 全局变量
- 每个 stage 的 `vars`: stage 特定变量

### 步骤 3: 编写 Prompt

在 `prompts/` 目录下创建/修改：
- `step1_input.txt`: 第一阶段任务描述
- `step2_input.txt`: 第二阶段任务描述

### 步骤 4: 运行

```bash
python pipeline/pipeline.py my_pipeline/config.yaml
```
