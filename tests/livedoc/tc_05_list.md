# TC-05: 列出所有问题（过滤测试）

## 目的
验证 `trace issues` 的各种过滤选项

## 前置条件
- 已完成 TC-04（2 resolved, 1 open）

## 测试步骤

```bash
# Step 1: 列出所有问题
python ../../scripts/spear trace issues

# Step 2: 只列出 open
python ../../scripts/spear trace issues --status open

# Step 3: 只列出 resolved
python ../../scripts/spear trace issues --status resolved
```

## 预期结果

### Step 1 输出（所有状态）
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

### Step 2 输出（仅 open）
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-003] sh 高内核态 86.8%
   └─ 建议: cluster-symbols --comm sh

用法: spear trace complete --id ISS-003 --result '分析结果'
```

### Step 3 输出（仅 resolved）
```
✅ RESOLVED ISSUES
-----------------------------------------------------------------
[ISS-001] netstat 高内核态 94.7%
   └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争

[ISS-002] containerd-shim 高内核态 89.9%
   └─ 结果: LOCK_CONTENTION 79.84%, 单进程锁竞争远超 netstat
```

### 验证点
- [ ] --status 过滤功能正常
- [ ] 默认显示所有状态
- [ ] open 问题显示建议
- [ ] resolved 问题显示结果
