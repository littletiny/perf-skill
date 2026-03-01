# TC-09: 重复 ID 检测

## 目的
验证系统能检测并拒绝重复的 issue ID

## 前置条件
- 文档已初始化，且有 ISS-001

## 测试步骤

```bash
# Step 1: 初始化并添加一个问题
rm -f .perf-doc.json
python ../../scripts/perf_expert.py doc init --data test.data
python ../../scripts/perf_expert.py doc add --id ISS-001 --desc "第一个问题"

# Step 2: 尝试添加相同 ID（应该失败）
python ../../scripts/perf_expert.py doc add --id ISS-001 --desc "重复的问题"

# Step 3: 验证只有一个问题
python ../../scripts/perf_expert.py doc list
```

## 预期结果

### Step 2 输出（错误）
```
✗ 错误: Duplicate issue ID: ISS-001
```

### Step 3 输出（只有一个问题）
```
============================================================
ISSUES  STATUS  (0 completed, 1 pending)
============================================================

⚠️  PENDING  ← 需处理
------------------------------------------------------------
ISS-001  第一个问题

============================================================
```

### 验证点
- [ ] 重复 ID 被正确拒绝
- [ ] 显示清晰的错误信息
- [ ] 原文档未被破坏
