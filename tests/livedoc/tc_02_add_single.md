# TC-02: 添加单个问题

## 目的
验证 `doc add` 命令能正确添加问题到文档

## 前置条件
- 已完成 TC-01（文档已初始化）

## 测试步骤

```bash
# Step 1: 确保文档已初始化
python ../../scripts/perf_expert.py doc init --data perf.data.txt

# Step 2: 添加单个问题
python ../../scripts/perf_expert.py doc add \
  --id ISS-001 \
  --desc "netstat 高内核态 94.7%" \
  --risk "可能比表面看起来更严重" \
  --hint "cluster-symbols --comm netstat"

# Step 3: 验证内容
python ../../scripts/perf_expert.py doc list
```

## 预期结果

### Step 2 输出
```
✓ 已添加问题: ISS-001
  描述: netstat 高内核态 94.7%
```

### Step 3 输出
```
============================================================
ISSUES  STATUS  (0 completed, 1 pending)
============================================================

⚠️  PENDING  ← 需处理
------------------------------------------------------------
ISS-001  netstat 高内核态 94.7%
         ├─ 风险: 可能比表面看起来更严重
         └─ 建议: cluster-symbols --comm netstat

============================================================
```

### JSON 文件内容
```json
{
  "version": "1.0",
  "data_file": "perf.data.txt",
  "created_at": "2026-02-28T12:00:00Z",
  "updated_at": "2026-02-28T12:00:01Z",
  "issues": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "pending",
      "risk": "可能比表面看起来更严重",
      "hint": "cluster-symbols --comm netstat",
      "created_at": "2026-02-28T12:00:01Z"
    }
  ]
}
```

### 验证点
- [ ] 添加成功，状态为 pending
- [ ] risk 和 hint 字段正确保存
- [ ] list 命令显示风险和建议
