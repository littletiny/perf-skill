# TC-04: 标记问题完成

## 目的
验证 `trace complete` 命令能正确标记问题为 resolved 状态

## 前置条件
- 已完成 TC-03（有 3 个 open 问题）

## 测试步骤

```bash
# Step 1: 确认当前状态
python ../../scripts/spear trace issues

# Step 2: 标记 ISS-001 完成
python ../../scripts/spear trace complete \
  --id ISS-001 \
  --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"

# Step 3: 标记 ISS-002 完成（关键：发现比 netstat 更严重！）
python ../../scripts/spear trace complete \
  --id ISS-002 \
  --result "LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat"

# Step 4: 查看列表
python ../../scripts/spear trace issues
```

## 预期结果

### Step 2 输出
```
✓ 已完成: ISS-001
  结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

  剩余 2 个待处理 issue
```

### Step 3 输出
```
✓ 已完成: ISS-002
  结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat

  剩余 1 个待处理 issue
```

### Step 4 输出
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-003] sh 高内核态 86.8%
   └─ 建议: cluster-symbols --comm sh

✅ RESOLVED ISSUES
-----------------------------------------------------------------
[ISS-001] netstat 高内核态 94.7%
   └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

[ISS-002] containerd-shim 高内核态 89.9%
   └─ 结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat

用法: spear trace complete --id ISS-003 --result '分析结果'
```

### 验证点
- [ ] resolved 问题显示分析结果
- [ ] open 问题继续显示建议
- [ ] 显示剩余待处理数量
