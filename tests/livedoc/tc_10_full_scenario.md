# TC-10: 完整场景 - netstat/containerd-shim 案例重演

## 目的
模拟真实的 netstat/containerd-shim 诊断案例，验证 Trace 能防止遗漏关键问题

## 场景描述
分析 `netstat_perf.data` 时发现：
- netstat: 2623 PIDs, 243.87% CPU, 94.7% kernel
- python3: 826 PIDs, 207.17% CPU, 35.2% kernel  
- dbatman: 311 PIDs, 147.94% CPU, 26.4% kernel
- containerd-shim: 240 PIDs, 96.01% CPU, 89.9% kernel ← 容易被遗漏

## 测试步骤

```bash
#!/bin/bash
# 完整诊断流程模拟

# ===== Phase 1: 初始化 =====
echo "=== Phase 1: 初始化 ==="
rm -f .spear.json
python ../../scripts/spear trace init --data netstat_perf.data

# ===== Phase 2: 信息收集，记录所有发现的问题 =====
echo ""
echo "=== Phase 2: 记录发现的所有问题 ==="

# 从 get-comm-top 输出发现 4 个高内核态进程
python ../../scripts/spear trace add \
  --desc "netstat: 2623 PIDs, 243.87% CPU, 94.7% kernel" \
  --hint "cluster-symbols --comm netstat"

python ../../scripts/spear trace add \
  --desc "python3: 826 PIDs, 207.17% CPU, 35.2% kernel" \
  --hint "cluster-symbols --comm python3"

python ../../scripts/spear trace add \
  --desc "dbatman: 311 PIDs, 147.94% CPU, 26.4% kernel" \
  --hint "cluster-symbols --comm dbatman"

# 关键：记录容易被遗漏的 containerd-shim
python ../../scripts/spear trace add \
  --desc "containerd-shim: 240 PIDs, 96.01% CPU, 89.9% kernel (高内核态，可能比netstat更严重)" \
  --hint "cluster-symbols --comm containerd-shim"

# 查看待办清单
echo ""
echo "=== 当前待办状态 ==="
python ../../scripts/spear trace issues

# ===== Phase 3: 并行分析（模拟） =====
echo ""
echo "=== Phase 3: 分析问题（模拟工具输出） ==="

# 分析 netstat
python ../../scripts/spear trace complete \
  --id ISS-001 \
  --result "LOCK_CONTENTION 38.36%, /proc/net/tcp 锁竞争是主因"

echo ""
echo "=== 分析完 netstat 后的状态 ==="
python ../../scripts/spear trace issues
# ^^^ 关键点：这里应该明确提示还有 3 个 open 问题！

# 分析 containerd-shim（被发现是关键问题）
python ../../scripts/spear trace complete \
  --id ISS-004 \
  --result "LOCK_CONTENTION 79.84% !!! 单进程锁竞争是netstat的2倍"

# 分析 python3
python ../../scripts/spear trace complete \
  --id ISS-002 \
  --result "NORMAL: CPU主要在用户态，符合预期"

# 分析 dbatman
python ../../scripts/spear trace complete \
  --id ISS-003 \
  --result "LOW_PRIORITY: 可延后处理"

# ===== Phase 4: 最终审计 =====
echo ""
echo "=== Phase 4: 最终审计 ==="
python ../../scripts/spear trace finalize

# ===== Phase 5: 生成报告 =====
echo ""
echo "=== Phase 5: 生成诊断报告 ==="
python ../../scripts/spear trace export --format markdown --output diagnosis_report.md
cat diagnosis_report.md
```

## 预期关键输出

### Phase 2 后的 issues
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-001] netstat: 2623 PIDs, 243.87% CPU, 94.7% kernel
   └─ 建议: cluster-symbols --comm netstat

🟡 [ISS-002] python3: 826 PIDs, 207.17% CPU, 35.2% kernel
   └─ 建议: cluster-symbols --comm python3

🟡 [ISS-003] dbatman: 311 PIDs, 147.94% CPU, 26.4% kernel
   └─ 建议: cluster-symbols --comm dbatman

🟡 [ISS-004] containerd-shim: 240 PIDs, 96.01% CPU, 89.9% kernel (高内核态，可能比netstat更严重)
   └─ 建议: cluster-symbols --comm containerd-shim

用法: spear trace complete --id ISS-001 --result '分析结果'
```

### Phase 3 中间状态（分析完 netstat 后）
```
⚠️  OPEN ISSUES (待处理)
-----------------------------------------------------------------
🟡 [ISS-002] python3: 826 PIDs, 207.17% CPU, 35.2% kernel
   └─ 建议: cluster-symbols --comm python3

🟡 [ISS-003] dbatman: 311 PIDs, 147.94% CPU, 26.4% kernel
   └─ 建议: cluster-symbols --comm dbatman

🟡 [ISS-004] containerd-shim: 240 PIDs, 96.01% CPU, 89.9% kernel (高内核态，可能比netstat更严重)
   └─ 建议: cluster-symbols --comm containerd-shim

✅ RESOLVED ISSUES
-----------------------------------------------------------------
[ISS-001] netstat: 2623 PIDs, 243.87% CPU, 94.7% kernel
   └─ 结果: LOCK_CONTENTION 38.36%, /proc/net/tcp 锁竞争是主因
```

**关键验证点**: 即使在分析完 netstat 后，系统明确提示还有 **3 个 open 问题**，特别是 ISS-004 (containerd-shim) 的高风险，不会被遗漏！

### Phase 4 Finalize
```
=================================================================
最终全局审计
=================================================================

✅ 所有问题已处理
   共解决 4 个问题

=================================================================
可以生成诊断报告
=================================================================
```

## 测试价值

此测试用例验证了 Trace 机制如何解决原始案例中的问题：

| 原始案例问题 | Trace 解决方案 |
|-------------|---------------|
| 被人脑记忆限制 | 所有问题写入文档，不会遗忘 |
| 被大数字(2623)吸引 | 所有问题平等列出，不被数字偏见影响 |
| 无客观审计 | `issues` 和 `finalize` 强制检查剩余风险 |
| 过早收敛 | 明确提示还有 open 问题未处理 |
| 遗漏 containerd-shim | 建议始终可见，直到处理完毕 |

## 验证点
- [ ] 4 个问题都被记录，自动生成 ID
- [ ] 分析完 netstat 后明确提示还有 3 个 open
- [ ] 最终报告包含所有问题的分析结果
- [ ] 关键发现（containerd-shim 锁竞争是 netstat 的 2 倍）被记录在案
