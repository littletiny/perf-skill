# TC-07: 最终审计 - 有遗留问题（强制审计机制）

## 目的
验证当有 pending 问题时，`finalize` 会阻止报告生成并提示风险

## 前置条件
- 重置状态：有 2 completed, 1 pending

## 测试步骤

```bash
# Step 1: 重置环境，创建有 pending 的状态
rm -f .perf-doc.json
python ../../scripts/perf_expert.py doc init --data test.data

# 添加并部分完成
python ../../scripts/perf_expert.py doc add --id ISS-001 --desc "问题A" --risk "高"
python ../../scripts/perf_expert.py doc add --id ISS-002 --desc "问题B" --risk "中"
python ../../scripts/perf_expert.py doc complete --id ISS-001 --result "已解决"

# Step 2: 尝试 finalize（会被阻止）
python ../../scripts/perf_expert.py doc finalize

# Step 3: 使用 --accept-risk 强制通过
echo "问题B影响范围小，可接受风险" > /tmp/risk_reason.txt
python ../../scripts/perf_expert.py doc finalize --accept-risk "问题B影响范围小，可接受风险"
```

## 预期结果

### Step 2 输出（被阻止）
```
============================================================
最终全局审计
============================================================

⚠️  剩余风险确认
------------------------------------------------------------
以下问题尚未处理：

ISS-002  问题B
  - 建议: 

------------------------------------------------------------
强制选择
------------------------------------------------------------

[A] 继续分析剩余问题（推荐）
    执行: cluster-symbols --comm <target>

[B] 接受风险，生成报告
    必须提供理由（使用 --accept-risk）

[C] 标记为无需处理
    执行: perf-doc complete --id <id> --result 'wontfix: <理由>'

============================================================
ERROR: 存在未处理问题，无法直接生成报告
请选择 [A/B/C] 或提供 --accept-risk
```

### Step 3 输出（强制通过）
```
============================================================
最终全局审计
============================================================

⚠️  已接受风险: 问题B影响范围小，可接受风险

============================================================
✓ 可以生成诊断报告
============================================================
```

### 验证点
- [ ] 有 pending 时 finalize 显示错误信息
- [ ] 明确列出剩余问题和建议
- [ ] 提供 A/B/C 三种选择
- [ ] 使用 --accept-risk 后可以通过
- [ ] Step 2 的 exit code 非 0
