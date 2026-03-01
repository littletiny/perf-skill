# TC-03: 添加多个问题

## 目的
验证能正确添加多个问题，模拟真实诊断场景（自动生成 ID）

## 前置条件
- 文档已初始化

## 测试步骤

```bash
# Step 1: 初始化
rm -f .spear.json
python ../../scripts/spear trace init --data netstat_perf.data

# Step 2: 添加 netstat 问题
python ../../scripts/spear trace add \
  --desc "netstat 高内核态 94.7%" \
  --hint "cluster-symbols --comm netstat"

# Step 3: 添加 containerd-shim 问题（容易被遗漏的关键问题）
python ../../scripts/spear trace add \
  --desc "containerd-shim 高内核态 89.9%" \
  --hint "cluster-symbols --comm containerd-shim"

# Step 4: 添加 sh 问题
python ../../scripts/spear trace add \
  --desc "sh 高内核态 86.8%" \
  --hint "cluster-symbols --comm sh"

# Step 5: 查看列表
python ../../scripts/spear trace issues
```

## 预期结果

### Step 5 输出
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-001] netstat 高内核态 94.7%
   └─ 建议: cluster-symbols --comm netstat

🟡 [ISS-002] containerd-shim 高内核态 89.9%
   └─ 建议: cluster-symbols --comm containerd-shim

🟡 [ISS-003] sh 高内核态 86.8%
   └─ 建议: cluster-symbols --comm sh

用法: spear trace complete --id ISS-001 --result '分析结果'
```

### 验证点
- [ ] 3 个问题都成功添加，自动生成 ISS-001/002/003
- [ ] 所有 open 问题都显示建议
- [ ] ID 按添加顺序递增
