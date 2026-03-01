# TC-05: 列出所有问题（过滤测试）

## 目的
验证 `doc list` 的各种过滤选项

## 前置条件
- 已完成 TC-04（2 completed, 1 pending）

## 测试步骤

```bash
# Step 1: 列出所有问题
python ../../scripts/spear.py doc list --status all

# Step 2: 只列出 pending
python ../../scripts/spear.py doc list --status pending

# Step 3: 只列出 completed
python ../../scripts/spear.py doc list --status completed

# Step 4: JSON 格式输出
python ../../scripts/spear.py doc list --format json
```

## 预期结果

### Step 1 输出（同 TC-04 Step 4）
显示 completed 和 pending 两部分

### Step 2 输出（仅 pending）
```
============================================================
ISSUES  STATUS  (0 completed, 1 pending)
============================================================

⚠️  PENDING  ← 需处理
------------------------------------------------------------
ISS-003  sh 高内核态 86.8%
         ├─ 风险: 未知
         └─ 建议: cluster-symbols --comm sh

============================================================
```

### Step 3 输出（仅 completed）
```
============================================================
ISSUES  STATUS  (2 completed, 0 pending)
============================================================

✅ COMPLETED
------------------------------------------------------------
ISS-001  netstat 高内核态 94.7%
         └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

ISS-002  containerd-shim 高内核态 89.9%
         └─ 结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat

============================================================
```

### Step 4 输出（JSON 格式）
```json
{
  "pending_count": 1,
  "completed_count": 2,
  "can_converge": false,
  "pending": [
    {
      "id": "ISS-003",
      "desc": "sh 高内核态 86.8%",
      "status": "pending",
      "risk": "未知",
      "hint": "cluster-symbols --comm sh",
      "created_at": "2026-02-28T12:00:03Z"
    }
  ],
  "completed": [
    {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "status": "completed",
      "result": "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争",
      "completed_at": "2026-02-28T12:00:04Z"
    },
    {
      "id": "ISS-002",
      "desc": "containerd-shim 高内核态 89.9%",
      "status": "completed",
      "result": "LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat",
      "completed_at": "2026-02-28T12:00:05Z"
    }
  ]
}
```

### 验证点
- [ ] --status 过滤功能正常
- [ ] --format json 输出正确
- [ ] can_converge 字段正确反映状态（有 pending 时为 false）
