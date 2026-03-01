# TC-04: 标记问题完成

## 目的
验证 `doc complete` 命令能正确标记问题为 completed 状态

## 前置条件
- 已完成 TC-03（有 3 个 pending 问题）

## 测试步骤

```bash
# Step 1: 确认当前状态
python ../../scripts/spear.py doc list

# Step 2: 标记 ISS-001 完成
python ../../scripts/spear.py doc complete \
  --id ISS-001 \
  --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"

# Step 3: 标记 ISS-002 完成（关键：发现比 netstat 更严重！）
python ../../scripts/spear.py doc complete \
  --id ISS-002 \
  --result "LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat"

# Step 4: 查看列表
python ../../scripts/spear.py doc list
```

## 预期结果

### Step 2 输出
```
✓ 已完成: ISS-001
  结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争
```

### Step 3 输出
```
✓ 已完成: ISS-002
  结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat
```

### Step 4 输出
```
============================================================
ISSUES  STATUS  (2 completed, 1 pending)
============================================================

✅ COMPLETED
------------------------------------------------------------
ISS-001  netstat 高内核态 94.7%
         └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

ISS-002  containerd-shim 高内核态 89.9%
         └─ 结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat

⚠️  PENDING  ← 需处理
------------------------------------------------------------
ISS-003  sh 高内核态 86.8%
         ├─ 风险: 未知
         └─ 建议: cluster-symbols --comm sh

============================================================
```

### 验证点
- [ ] completed 问题显示分析结果
- [ ] pending 问题继续显示风险和建议
- [ ] 状态统计正确（2 completed, 1 pending）
- [ ] 明确提示还有 ISS-003 待处理
