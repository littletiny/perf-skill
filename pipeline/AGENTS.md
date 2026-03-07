# pipeline/ - Agent 流水线

## 目录简介

简化版 Code Agent 流水线，支持 YAML 配置、变量替换、条件执行。

## 核心组件

- **pipeline.py** - 流水线引擎实现
- **pipeline.yaml** - 默认流水线配置示例
- **agents.yaml** - Agent 配置

## 子目录

- **examples/** - 流水线配置示例
- **prompts/** - Agent Prompt 模板
- **template/** - 报告模板

## 流水线配置示例

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

## 详细文档

详见 `pipeline/README.md`
