# TC-08: 导出报告

## 目的
验证 `trace export` 能正确导出 Markdown 和 JSON 格式

## 前置条件
- 有 resolved 的问题（TC-06 后）

## 测试步骤

```bash
# Step 1: 导出 Markdown 到 stdout
python ../../scripts/spear trace export --format markdown

# Step 2: 导出到文件
python ../../scripts/spear trace export --format markdown --output report.md
cat report.md

# Step 3: 导出 JSON
python ../../scripts/spear trace export --format json --output report.json
cat report.json
```

## 预期结果

### Step 1 输出（Markdown）
```markdown
# 性能诊断报告

**数据文件**: test.data
**创建时间**: 2026-02-28T12:00:00Z
**更新时间**: 2026-02-28T12:00:10Z

## 执行摘要
- 执行命令: 5 个
- 发现问题: 3 个
- 已解决: 3 个
- 待处理: 0 个

## 诊断时间线

### [1] 12:00:01  `get-comm-top --data test.data`
- ⚠️  **发现风险**: netstat 高内核态 94.7% (`ISS-001`)

...

## 已解决问题

### ISS-001: netstat 高内核态 94.7%
- 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

### ISS-002: containerd-shim 高内核态 89.9%
- 结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat

### ISS-003: sh 高内核态 86.8%
- 结果: NORMAL: 非关键路径，优先级低
```

### Step 3 输出（JSON）
```json
{
  "version": "2.0",
  "data_file": "test.data",
  "created_at": "2026-02-28T12:00:00Z",
  "updated_at": "2026-02-28T12:00:10Z",
  "timeline": [...],
  "issues": {
    "ISS-001": {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "resolved",
      "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争",
      ...
    },
    ...
  }
}
```

### 验证点
- [ ] Markdown 格式正确，包含时间线
- [ ] 文件导出功能正常
- [ ] JSON 包含完整数据结构（timeline + issues）
