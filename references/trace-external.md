# Trace 外部审计命令参考

> 完整的 Trace 问题追踪系统命令参考，供外部审计和流程管理使用。
> 
> 诊断工程师日常使用请参考 [tools.md](./tools.md) 中的简化版 Trace 命令。

---

## Trace 系统概述

Trace 系统用于记录诊断过程中的发现、结论和问题追踪。所有 Analysis CLI 命令自动记录到 timeline。

---

## 完整命令列表

| 命令 | 用途 | 示例 |
|------|------|------|
| `trace init` | 初始化 Trace 文档 | `shecr trace init` |
| `trace add` | 添加问题记录 | `shecr trace add --desc "CPU异常" --level critical` |
| `trace timeline` | 查看诊断时间线 | `shecr trace timeline [--format text\|json]` |
| `trace issues` | 查看问题列表 | `shecr trace issues [--status open\|resolved\|all]` |
| `trace audit` | 审计问题质量 | `shecr trace audit [--phase structural\|timeline\|depth]` |
| `trace complete` | 标记问题完成 | `shecr trace complete --id ISS-001 --result "根因: ..."` |
| `trace reopen` | 重新打开问题 | `shecr trace reopen --id ISS-001 [--reason "原因"]` |
| `trace finalize` | 结束诊断 | `shecr trace finalize [--accept-risk "..."]` |
| `trace export` | 导出报告 | `shecr trace export [--format markdown\|json] --output report.md` |

---

## 命令详情

### trace init

初始化诊断追踪文档。

```bash
shecr trace init
```

**功能**:
- 创建 `.shecr.json` 配置文件
- 初始化 timeline 和 issues 数据结构

---

### trace add

添加问题记录（自动生成 ID）。

```bash
shecr trace add \
  --desc "问题描述" \
  [--level critical|warning|info] \
  [--risk "不处理的风险"] \
  [--hint "建议操作"]
```

**输出**: `✓ 已添加问题: ISS-001`

---

### trace timeline

查看诊断时间线。

```bash
shecr trace timeline [--format text|json]
```

**输出示例**:
```
=== 诊断时间线 ===

[1] 2024-01-15 10:30:00  sys-audit
    发现: CPU 利用率 85%, 主要消耗在 nginx

[2] 2024-01-15 10:35:00  bottleneck-trace --comm nginx
    发现: 热点函数为 ssl_encrypt
```

---

### trace issues

列出所有问题。

```bash
shecr trace issues [--status open|resolved|all]
```

---

### trace audit

事后独立审计，验证诊断质量。

```bash
# 完整审计
shecr trace audit

# 指定阶段
shecr trace audit --phase structural
shecr trace audit --phase timeline
shecr trace audit --phase depth

# JSON 输出
shecr trace audit --format json --output audit-report.json
```

**审计检查项**:
- **结构完整性**: timeline 非空，issues 有记录
- **时间线连续性**: 逻辑推导链条完整
- **深度充分性**: 有 hotspot + caller 组合

---

### trace complete

标记问题完成。

```bash
shecr trace complete \
  --id ISS-001 \
  --result "分析结果"
```

---

### trace reopen

重新打开已解决的问题。

```bash
shecr trace reopen \
  --id ISS-001 \
  [--reason "重新打开原因"]

# 重新打开所有已解决的问题
shecr trace reopen --all
```

---

### trace finalize

结束诊断。

```bash
shecr trace finalize
shecr trace finalize --accept-risk "与当前问题无关"
```

---

### trace export

导出报告。

```bash
shecr trace export \
  [--format markdown|json] \
  [--output <path>]
```

---

## 数据格式

### Trace 文档结构

`.shecr.json` 文件结构:

```json
{
  "version": "1.0",
  "timeline": [
    {
      "seq": 1,
      "timestamp": "2024-01-15T10:30:00+08:00",
      "command": "sys-audit",
      "findings": [...]
    }
  ],
  "issues": {
    "ISS-001": {
      "level": "critical",
      "description": "...",
      "status": "open",
      "created_by_seq": 1,
      "resolved_by_seq": null,
      "results": [],
      "reopen_history": []
    }
  }
}
```

---

## 诊断工程师简化版

诊断工程师日常使用的简化 Trace 命令：

| 命令 | 用途 |
|------|------|
| `trace add` | 添加问题记录 |
| `trace complete` | 标记问题完成 |
| `trace issues` | 查看问题列表 |
| `trace finalize` | 结束诊断 |

详见 [tools.md](./tools.md) 的 "Trace 基础命令" 章节。
