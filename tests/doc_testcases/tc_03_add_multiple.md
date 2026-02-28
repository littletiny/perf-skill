# TC-03: 添加多个问题

## 目的
验证能正确添加多个问题，模拟真实诊断场景

## 前置条件
- 文档已初始化

## 测试步骤

```bash
# Step 1: 初始化
rm -f .perf-doc.json
python ../../scripts/perf_expert.py doc init --data netstat_perf.data

# Step 2: 添加 netstat 问题
python ../../scripts/perf_expert.py doc add \
  --id ISS-001 \
  --desc "netstat 高内核态 94.7%" \
  --risk "进程风暴，2623 PIDs" \
  --hint "cluster-symbols --comm netstat"

# Step 3: 添加 containerd-shim 问题（容易被遗漏的关键问题）
python ../../scripts/perf_expert.py doc add \
  --id ISS-002 \
  --desc "containerd-shim 高内核态 89.9%" \
  --risk "锁竞争可能比 netstat 更严重，单进程影响大" \
  --hint "cluster-symbols --comm containerd-shim"

# Step 4: 添加 sh 问题
python ../../scripts/perf_expert.py doc add \
  --id ISS-003 \
  --desc "sh 高内核态 86.8%" \
  --risk "未知" \
  --hint "cluster-symbols --comm sh"

# Step 5: 查看列表
python ../../scripts/perf_expert.py doc list
```

## 预期结果

### Step 5 输出
```
============================================================
ISSUES  STATUS  (0 completed, 3 pending)
============================================================

⚠️  PENDING  ← 需处理
------------------------------------------------------------
ISS-001  netstat 高内核态 94.7%
         ├─ 风险: 进程风暴，2623 PIDs
         └─ 建议: cluster-symbols --comm netstat

ISS-002  containerd-shim 高内核态 89.9%
         ├─ 风险: 锁竞争可能比 netstat 更严重，单进程影响大
         └─ 建议: cluster-symbols --comm containerd-shim

ISS-003  sh 高内核态 86.8%
         ├─ 风险: 未知
         └─ 建议: cluster-symbols --comm sh

============================================================
```

### 验证点
- [ ] 3 个问题都成功添加
- [ ] 所有 pending 问题都显示风险和建议
- [ ] 问题按添加顺序排列
