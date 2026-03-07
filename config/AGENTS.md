# config/ - 配置文件目录

## 目录简介

perf-hunter 的配置文件和默认规则定义。

## 配置文件

| 文件 | 说明 |
|------|------|
| `defaults.py` | 默认配置值（Python 格式） |
| `perf-hunter.json` | 主配置文件 |
| `default-rules.json` | 默认分析规则 |
| `risk-default.json` | 风险评级默认配置 |
| `symbol_rules.json` | 符号分析规则 |

## 配置规范

- JSON 配置文件需保持有效格式
- 配置项变更需同步更新文档
- 禁止硬编码，优先使用配置文件
