# Pipeline 模块（简化版）

基于 Code Agent 的多阶段流水线，使用变量模板配置，支持灵活的 stage 定义。

---

## 目录结构

```
pipeline/
├── pipeline.py          # 简化版 Pipeline 运行器
├── examples/            # 示例配置
│   ├── config.yaml      # 完整 pipeline 配置示例
│   └── prompts/         # prompt 模板文件
│       ├── default_system.md
│       ├── diagnose_system.md
│       ├── audit_system.md
│       ├── recheck_system.md
│       ├── diagnose_input.txt
│       ├── audit_input.txt
│       └── recheck_input.txt
└── README.md            # 本文档
```

---

## 快速开始

### 1. 创建配置文件

```yaml
# config.yaml
pipeline: diagnose - audit - recheck

vars:
  DATA_FILE: "/path/to/perf.data"
  WORK_DIR: "./output"

agent:
  system_prompt: "prompts/system.md"
  allowed_dirs:
    - "${WORK_DIR}"
  default_permissions: "read-write"
  timeout: 300

diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"
    timeout: 600
  vars:
    ROLE: "诊断专家"
    input.template: "prompts/diagnose.txt"
    output.report: "${WORK_DIR}/diagnose/report.md"

audit:
  agent:
    default_permissions: "read-only"
  vars:
    ROLE: "审计员"
    input.template: "prompts/audit.txt"
    input.report: "${diagnose.output.report}"
    output.report: "${WORK_DIR}/audit/report.md"
```

### 2. 运行 Pipeline

```bash
python pipeline/pipeline.py examples/config.yaml
```

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
| `allowed_dirs` | list | 允许访问的目录列表（支持 `${var}` 变量） |
| `default_permissions` | string | 默认权限：`read-only` \| `read-write` \| `write-only` |
| `timeout` | int | 超时时间（秒） |
| `model` | string | 模型名称，默认 `kimi` |
| `working_dir` | string | 工作目录 |

### Stage 配置

每个 stage 是一个与 stage 名同名的顶级字段：

```yaml
stage_name:
  agent:          # Stage 级 Agent 配置（覆盖全局）
    system_prompt: "..."
    timeout: 600
  vars:           # Stage 变量（覆盖全局同名变量）
    ROLE: "专家"
    input.template: "prompts/input.txt"
    output.report: "${WORK_DIR}/report.md"
```

### 变量替换

支持两种变量语法：

| 语法 | 说明 | 示例 |
|------|------|------|
| `${var}` | 普通变量 | `${DATA_FILE}` → `/path/to/perf.data` |
| `${stage.output.xxx}` | 引用其他 stage 输出 | `${diagnose.output.report}` → `./output/diagnose/report.md` |

变量作用域：
1. Stage 变量覆盖全局变量
2. 变量值可以引用其他变量（递归解析）
3. 支持 stage 输出引用形成数据流

---

## 示例：三阶段诊断流水线

### 完整配置

```yaml
# diagnose - audit - recheck pipeline
pipeline: diagnose - audit - recheck

vars:
  DATA_FILE: "./perf.data"
  WORK_DIR: "./output"

agent:
  system_prompt: "prompts/default_system.md"
  allowed_dirs:
    - "${WORK_DIR}"
  default_permissions: "read-write"

diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"
    timeout: 600
  vars:
    ROLE: "性能诊断专家"
    input.template: "prompts/diagnose_input.txt"
    output.report: "${WORK_DIR}/diagnose/report.md"

audit:
  agent:
    system_prompt: "prompts/audit_system.md"
    default_permissions: "read-only"
  vars:
    ROLE: "诊断审计员"
    input.template: "prompts/audit_input.txt"
    input.report: "${diagnose.output.report}"
    output.report: "${WORK_DIR}/audit/report.md"

recheck:
  agent:
    system_prompt: "prompts/recheck_system.md"
    timeout: 600
  vars:
    ROLE: "复查专家"
    input.template: "prompts/recheck_input.txt"
    input.diagnose: "${diagnose.output.report}"
    input.audit: "${audit.output.report}"
    output.report: "${WORK_DIR}/recheck/final_report.md"
```

### Input 模板示例

**diagnose_input.txt:**
```
你是${ROLE}，请分析数据文件 ${DATA_FILE}。

输出诊断报告到：${output.report}

要求：
1. 识别所有性能瓶颈
2. 提供三候选假设验证
3. 进行调用链溯源
```

**audit_input.txt:**
```
你是${ROLE}，请审计以下诊断报告：

诊断报告：${input.report}

输出审计报告到：${output.report}
```

**recheck_input.txt:**
```
你是${ROLE}，请根据审计结果复查：

原始诊断：${input.diagnose}
审计报告：${input.audit}

以差异化视角补充分析，输出到：${output.report}
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
│     b. 解析所有变量（支持递归和跨 stage 引用）                │
│     c. 读取 input.template                                   │
│     d. 渲染模板（替换 ${var} 变量）                          │
│     e. 构建 Agent 命令（含 system_prompt、权限等）           │
│     f. 执行 Agent                                            │
│     g. 记录输出到上下文（供后续 stage 引用）                  │
│                                                              │
│  3. 所有 stage 完成后，输出完成信息                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 与旧版 Pipeline 对比

| 特性 | 旧版 Pipeline | 简化版 Pipeline |
|------|--------------|-----------------|
| Agent 实现 | 自定义 Agent 类 | Code Agent (coder subagent) |
| 配置方式 | 代码内定义 | YAML 配置文件 |
| 输入定义 | 复杂数据结构 | 模板文件 + 变量替换 |
| 权限控制 | 内置 | Agent 配置 (allowed_dirs, permissions) |
| 数据流 | 内部状态管理 | 文件 + 变量引用 |
| 灵活性 | 低 | 高（可任意定义 stage） |

---

## 代码规范

- 不使用 regex（除变量替换外）
- 错误处理简单（let it crash）
- 强制静态类型（使用 dataclass）
- 配置文件使用 YAML 格式
