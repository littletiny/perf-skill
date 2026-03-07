# Agent Pipeline 使用指南

> SHECR Code Agent 流水线使用示例
> 版本: 2.0
> 更新: 2026-03-04

---

## 快速开始

### 创建第一个 Pipeline

```bash
# 创建工作目录
mkdir my_pipeline && cd my_pipeline

# 创建配置文件
cat > config.yaml << 'EOF'
pipeline: analyze - report

vars:
  DATA_FILE: "./data/input.txt"
  WORK_DIR: "./output"

agent:
  allowed_dirs:
    - "{{WORK_DIR}}"
  default_permissions: "read-write"

analyze:
  vars:
    ROLE: "数据分析师"
    input.template: "prompts/analyze.txt"
    output.result: "{{WORK_DIR}}/analyze/result.json"

report:
  when: "{{analyze.status}} == 'success'"
  vars:
    ROLE: "报告撰写员"
    input.template: "prompts/report.txt"
    input.data: "{{analyze.output.result}}"
    output.report: "{{WORK_DIR}}/report/summary.md"
EOF

# 创建 prompt 模板
mkdir -p prompts
cat > prompts/analyze.txt << 'EOF'
你是{{ROLE}}，请分析文件：{{DATA_FILE}}

将分析结果保存到：{{output.result}}
EOF

cat > prompts/report.txt << 'EOF'
你是{{ROLE}}，请基于分析结果生成报告。

输入数据：{{input.data}}
输出报告：{{output.report}}
EOF

# 运行 pipeline
python /path/to/perf-hunter/pipeline/pipeline.py config.yaml
```

---

## 配置详解

### 基础配置

```yaml
# 最简单的 pipeline
pipeline: stage1 - stage2

vars:
  WORK_DIR: "./output"

stage1:
  vars:
    input.template: "prompts/input1.txt"
    output.file: "{{WORK_DIR}}/stage1/out.txt"

stage2:
  vars:
    input.template: "prompts/input2.txt"
    input.prev: "{{stage1.output.file}}"
    output.file: "{{WORK_DIR}}/stage2/out.txt"
```

### 变量系统

#### 全局变量

```yaml
vars:
  DATA_FILE: "./perf.data"
  SYMPTOM: "CPU使用率100%"
  WORK_DIR: "./output"
```

所有 stage 都可以使用 `{{DATA_FILE}}`、`{{SYMPTOM}}` 等变量。

#### Stage 变量

```yaml
diagnose:
  vars:
    ROLE: "诊断专家"                    # 新变量
    WORK_DIR: "./custom_output"         # 覆盖全局变量
    output.report: "{{WORK_DIR}}/report.md"
```

#### 跨 Stage 引用

```yaml
audit:
  vars:
    input.report: "{{diagnose.output.report}}"  # 引用 diagnose stage 的输出
```

可用的 stage 状态变量：
- `{{stageName.status}}` - `success` / `failed` / `skipped`
- `{{stageName.exit_code}}` - 退出码（0/1）
- `{{stageName.output.xxx}}` - stage 定义的 output.xxx 变量

### 执行条件

#### 基本语法

```yaml
stage_name:
  when: "条件表达式"
```

#### 比较操作

```yaml
# 等于
recheck:
  when: "{{audit.status}} == 'failed'"

# 不等于
notify:
  when: "{{audit.status}} != 'skipped'"

# 数值比较
enhance:
  when: "{{diagnose.issue_count}} > 5"

# 退出码检查
cleanup:
  when: "{{analyze.exit_code}} == 0"
```

#### 文件存在检查

```yaml
backup:
  when: "exists({{output.report}})"

# 检查 stage 输出文件
review:
  when: "exists({{audit.output.report}})"
```

#### 逻辑组合

```yaml
# 逻辑与
recheck:
  when: "{{audit.status}} == 'failed' and {{diagnose.issue_count}} > 0"

# 逻辑或
notify:
  when: "{{audit.status}} == 'failed' or {{diagnose.status}} == 'failed'"

# 逻辑非
skip:
  when: "not(exists({{input.data}}))"

# 复杂组合
critical_review:
  when: "({{audit.failed_count}} > 3) or (not({{diagnose.exit_code}} == 0) and exists({{audit.output.gaps}}))"
```

### Agent 配置

#### 全局配置

```yaml
agent:
  system_prompt: "prompts/default_system.md"
  allowed_dirs:
    - "{{WORK_DIR}}"
    - "{{DATA_DIR}}"
  default_permissions: "read-write"
  timeout: 300
  model: "kimi"
  working_dir: "{{WORK_DIR}}"
```

#### Stage 级配置（覆盖全局）

```yaml
diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"  # 覆盖默认
    timeout: 600                                 # 覆盖 300
    allowed_dirs:
      - "{{WORK_DIR}}/diagnose"                  # 完全覆盖 allowed_dirs
  vars:
    ...
```

#### 权限控制

```yaml
# 只读（审计场景）
audit:
  agent:
    default_permissions: "read-only"

# 只写（生成报告场景）
report:
  agent:
    default_permissions: "write-only"
    allowed_dirs:
      - "{{WORK_DIR}}/reports"

# 读写（默认）
diagnose:
  agent:
    default_permissions: "read-write"
```

---

## 完整示例：诊断-审计-复查

### 目录结构

```
my_diagnosis/
├── config.yaml
├── prompts/
│   ├── default_system.md
│   ├── diagnose_system.md
│   ├── audit_system.md
│   ├── recheck_system.md
│   ├── diagnose_input.txt
│   ├── audit_input.txt
│   └── recheck_input.txt
└── data/
    └── perf.data
```

### config.yaml

```yaml
pipeline: diagnose - audit - recheck

vars:
  DATA_FILE: "./data/perf.data"
  WORK_DIR: "./output"
  SYMPTOM: "系统响应慢，CPU使用率100%"

agent:
  system_prompt: "prompts/default_system.md"
  allowed_dirs:
    - "{{WORK_DIR}}"
  default_permissions: "read-write"
  timeout: 300

diagnose:
  agent:
    system_prompt: "prompts/diagnose_system.md"
    allowed_dirs:
      - "{{WORK_DIR}}/diagnose"
      - "./data"
    timeout: 600
  vars:
    ROLE: "性能诊断专家"
    input.template: "prompts/diagnose_input.txt"
    output.report: "{{WORK_DIR}}/diagnose/report.md"
    output.trace: "{{WORK_DIR}}/diagnose/.shecr.json"

audit:
  agent:
    system_prompt: "prompts/audit_system.md"
    allowed_dirs:
      - "{{WORK_DIR}}"  # 需要读取 diagnose 的输出
    default_permissions: "read-only"
  vars:
    ROLE: "诊断审计员"
    input.template: "prompts/audit_input.txt"
    input.report: "{{diagnose.output.report}}"
    input.trace: "{{diagnose.output.trace}}"
    output.report: "{{WORK_DIR}}/audit/report.md"
    output.status: "{{WORK_DIR}}/audit/status.txt"

recheck:
  when: "{{audit.status}} == 'failed'"
  agent:
    system_prompt: "prompts/recheck_system.md"
    allowed_dirs:
      - "{{WORK_DIR}}/recheck"
      - "{{WORK_DIR}}/diagnose"
      - "{{WORK_DIR}}/audit"
    timeout: 600
  vars:
    ROLE: "复查专家"
    input.template: "prompts/recheck_input.txt"
    input.diagnose: "{{diagnose.output.report}}"
    input.audit: "{{audit.output.report}}"
    output.report: "{{WORK_DIR}}/recheck/final_report.md"
```

### Prompt 模板

**prompts/diagnose_input.txt:**
```
你是{{ROLE}}，请执行性能诊断任务。

## 输入
- 数据文件：{{DATA_FILE}}
- 症状描述：{{SYMPTOM}}

## 输出
- 诊断报告：{{output.report}}
- Trace 文件：{{output.trace}}

## 任务
1. 读取数据文件 {{DATA_FILE}}
2. 根据症状进行系统性分析
3. 按照 SHECR 方法论诊断问题
4. 生成诊断报告和 trace 文件

## 要求
- 识别所有性能瓶颈
- 提供根因分析（三候选假设法）
- 包含调用链溯源
```

**prompts/audit_input.txt:**
```
你是{{ROLE}}，请审计以下诊断报告。

## 输入
- 诊断报告：{{input.report}}
- Trace 文件：{{input.trace}}

## 输出
- 审计报告：{{output.report}}
- 状态文件：{{output.status}}（写入 passed 或 failed）

## 审计维度
1. 结构完整性：result 非空、非敷衍
2. Timeline 关联：有分析命令支撑
3. 分析深度：三候选假设、驱动力、溯源
4. 文档一致性：debug/*.md 完整

根据审计结果，将状态写入 {{output.status}}。
```

**prompts/recheck_input.txt:**
```
你是{{ROLE}}，请根据审计结果进行复查。

## 核心原则
**必须有差异化视角，不简单复制原始诊断！**

## 输入
- 原始诊断：{{input.diagnose}}
- 审计报告：{{input.audit}}

## 输出
- 最终报告：{{output.report}}

## 任务
1. 分析审计发现的 gaps
2. 以批判性视角重新审视诊断
3. 补充缺失的分析
4. 生成最终报告

## 禁止
- 使用"足够"、"显然"等模糊词汇
- 简单复制原始诊断结论
```

### 运行

```bash
cd my_diagnosis
python /path/to/perf-hunter/pipeline/pipeline.py config.yaml
```

---

## 高级用法

### 动态变量

```yaml
vars:
  TIMESTAMP: "2024-03-04"  # 静态值
  OUTPUT_DIR: "{{WORK_DIR}}/{{TIMESTAMP}}"  # 引用其他变量

stage1:
  vars:
    output.file: "{{OUTPUT_DIR}}/result.txt"  # 最终: "./output/2024-03-04/result.txt"
```

### 条件链

```yaml
pipeline: build - test - deploy

build:
  vars:
    output.status: "{{WORK_DIR}}/build/status.txt"

test:
  when: "{{build.status}} == 'success'"
  vars:
    output.status: "{{WORK_DIR}}/test/status.txt"

deploy:
  when: "{{build.status}} == 'success' and {{test.status}} == 'success'"
```

### 错误处理

```yaml
pipeline: analyze - fallback - report

analyze:
  vars:
    output.result: "{{WORK_DIR}}/analyze/result.json"

fallback:
  when: "{{analyze.status}} == 'failed'"
  vars:
    ROLE: "故障处理专家"
    input.template: "prompts/fallback.txt"
    output.result: "{{WORK_DIR}}/fallback/result.json"

report:
  # 无论 analyze 还是 fallback 成功，都生成报告
  when: "{{analyze.status}} == 'success' or {{fallback.status}} == 'success'"
  vars:
    input.data: "{{analyze.output.result if analyze.status == 'success' else fallback.output.result}}"
```

---

## 调试技巧

### 查看变量解析结果

```bash
# 添加调试输出（pipeline 会自动打印）
python pipeline/pipeline.py config.yaml

# 输出示例：
# Pipeline: diagnose -> audit -> recheck
#
# [STAGE] diagnose
#   Agent: kimi
#   Permissions: read-write
#   Task file: ./output/.pipeline_diagnose_task.txt
#   ...
```

### 检查条件求值

```yaml
# 临时添加 debug stage
debug_vars:
  when: "true"  # 始终执行
  vars:
    ROLE: "调试"
    input.template: "prompts/debug.txt"

# prompts/debug.txt
变量检查：
- diagnose.status = {{diagnose.status}}
- diagnose.exit_code = {{diagnose.exit_code}}
- audit.status = {{audit.status}}
```

### 手动执行单个 Stage

```bash
# 直接调用 coder subagent
cat prompts/diagnose_input.txt | sed 's/{{DATA_FILE}}/..\/data\/perf.data/g' > task.txt
kimi --yolo -p "$(cat task.txt)"
```

---

## 常见问题

### 变量未替换

**问题**：`{{VAR}}` 原样出现在输出中

**检查**：
1. 变量是否在 `vars` 中定义
2. 变量名是否正确（大小写敏感）
3. 语法是否正确（双大括号 `{{}}`）

### Stage 引用失败

**问题**：`{{diagnose.output.report}}` 为空

**检查**：
1. diagnose stage 是否成功执行（status=success）
2. diagnose 是否定义了 `output.report` 变量
3. 引用语法是否正确：`{{stageName.output.key}}`

### 条件不生效

**问题**：`when` 条件未按预期执行

**检查**：
1. 条件语法是否正确
2. 字符串值是否用引号：`'failed'` 而非 `failed`
3. Stage 状态是否如预期（检查 Pipeline Summary）

---

## 参考

- [agent-pipeline-design.md](./agent-pipeline-design.md) - 架构设计文档
- [../pipeline/README.md](../pipeline/README.md) - 完整实现文档
- [../SKILL.md](../SKILL.md) - SHECR 方法论
