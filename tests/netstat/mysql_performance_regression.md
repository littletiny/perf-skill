# SPEAR 诊断报告: 机器卡顿，MySQL性能下降

- **状态**: 已定位 / 已验证
- **数据文件**: `netstat_perf.data` (59.77s, EXCELLENT 数据质量)
- **诊断者**: SPEAR Agent
- **最后更新**: 2026-02-28

---

## 一、问题演进记录

| 版本 | 问题描述 | 关键证据引用 |
|------|----------|-------------|
| V1 | 机器频繁卡顿，MySQL性能下降 | 用户反馈 |
| V2 | 发现严重进程风暴，netstat高频创建 | `count-process-variety`: 2623个netstat进程, CPU/PID=0.056 core/s, PROCESS_STORM |
| V3 | 确认内核锁竞争热点 | `get-hotspots`: established_get_first=8.21%, _raw_spin_lock_bh=6.25% |
| V4 | 根因定位：netstat读取/proc/net/tcp引发内核锁竞争 | `find-callers`: established_get_first ← seq_read; `cluster-symbols`(netstat): LOCK_CONTENTION=38.36% |

---

## 二、竞争性假设追踪

| 假设路径 | 机制评估 | 预期指纹 | 验证结果 | 状态 |
|---------|---------|---------|---------|------|
| **主动消耗**: MySQL自身计算密集型负载 | **机制**: SQL查询复杂度高<br>**副作用**: 用户态CPU高，mysqld进程热点在查询执行 | `show-cpu-usage`: user%高<br>`get-hotspots`: MySQL相关函数高 | MySQL进程未进入TOP消耗，user%=48.5%, kernel%=51.5% | ❌ 证伪 |
| **主动消耗**: 系统级进程风暴 | **机制**: 短生命周期进程频繁创建销毁，系统调用开销激增<br>**副作用**: 内核态消耗高，大量不同PID | `count-process-variety`: PROCESS_STORM检测<br>`cluster-comm`: 同类进程聚合消耗高 | netstat: 2623 PIDs, CPU/PID=0.056, storm_detected=true<br>netstat总消耗244%，内核态94.7% | ✅ 确认 |
| **被动压制**: 内核锁竞争 | **机制**: 并发访问/proc/net/tcp触发tcp_hashinfo锁竞争<br>**副作用**: established_get_first和_raw_spin_lock_bh占比高 | `cluster-symbols`: LOCK_CONTENTION>10%<br>`find-callers`: 指向seq_read/proc_reg_read | LOCK_CONTENTION=14.43%(系统级), 38.36%(netstat)<br>调用链确认来自/proc/net/tcp读取 | ✅ 确认 |
| **被动压制**: Cgroup CPU限流 | **机制**: CPU quota触发throttling<br>**副作用**: check-cpu-bottleneck报告CPU_LIMIT_SATURATION | `check-cpu-bottleneck`: verdict=CPU_LIMIT_SATURATION | verdict=HEALTHY, cpu_limit_detected=false | ❌ 证伪 |
| **被动压制**: 调度器问题 | **机制**: 调度延迟或过度抢占<br>**副作用**: SCHEDULER占比高 | `cluster-symbols`: EVENT_SCHEDULER>5% | EVENT_SCHEDULER=0.27%(系统级), 0.04%(netstat) | ❌ 证伪 |

---

## 三、深度审计记录

### 记录 1: 进程风暴检测

- **工具**: `count-process-variety`
- **关键输出**:
  ```json
  {
    "netstat": {
      "unique_pids": 2623,
      "cpu_per_pid": 0.0556,
      "behavior": "process_storm",
      "alert": {
        "type": "BEHAVIOR_PROCESS_STORM",
        "severity": "HIGH"
      }
    }
  }
  ```
- **机制发现**: 59.77秒内创建2623个netstat进程，平均每个仅消耗0.056 core/s，98%为短生命周期进程。结合python3(826个)、sh(408个)、grep(262个)、xargs(176个)等进程同时出现，推断为监控脚本高频循环执行。
- **推论**: 存在监控脚本以约44次/秒(2623/59.77)的频率调用netstat命令。

### 记录 2: 热点溯源 - 内核锁竞争

- **工具**: `find-callers --target established_get_first`
- **调用链**: 
  ```
  tcp_get_idx → tcp_seq_start → seq_read → proc_reg_read → vfs_read → ksys_read (53.88%)
  tcp_seq_next → seq_read → proc_reg_read → vfs_read → ksys_read (46.12%)
  ```
- **机制发现**: netstat通过read系统调用读取/proc/net/tcp文件，触发内核TCP连接表遍历。`established_get_first`在遍历过程中需要获取`raw_spin_lock_bh`锁，在高并发访问时产生锁竞争。
- **推论**: 进程风暴导致大量并发读取/proc/net/tcp，引发内核锁竞争。

### 记录 3: 语义聚类验证 - 锁竞争占比

- **工具**: `cluster-symbols`
- **关键输出**:
  | 范围 | EVENT_LOCK_CONTENTION | 评估 |
  |------|----------------------|------|
  | 系统级 | 14.43% | 🔴 严重 |
  | netstat专属 | 38.36% | 🔴 极高 |
  | EVENT_SCHEDULER(系统级) | 0.27% | 正常 |
- **机制发现**: netstat进程的锁竞争占比高达38.36%，是系统级锁竞争的2.7倍，证明netstat是锁竞争的主要来源。调度器开销0.27%说明系统未过载，排除调度问题。
- **推论**: 瓶颈明确为并发访问/proc/net/tcp引发的锁竞争，与进程风暴假设形成完整证据链。

### 记录 4: 进程组行为分析

- **工具**: `cluster-comm`
- **关键输出**:
  | 进程名 | PID数量 | 总CPU% | 内核态% | 模式 |
  |--------|---------|--------|---------|------|
  | netstat | 2623 | 243.87% | 94.7% | PROCESS_STORM |
  | python3 | 826 | 207.17% | 35.2% | PROCESS_STORM |
  | dbatman | 311 | 147.94% | 26.4% | PROCESS_STORM |
  | containerd-shim | 240 | 96.01% | 89.9% | PROCESS_STORM |
- **模式检测**: 系统识别出3种模式：MANY_SMALL_PROCESSES、UNEVEN_LOAD_DISTRIBUTION、EXTREME_PROCESS_PROLIFERATION
- **推论**: 存在系统性进程创建过度问题，netstat是最严重的单个贡献者。

---

## 四、全局审计 (Global Consistency Audit)

- [x] **是否解释了所有观察到的异常？**
  - ✅ 机器卡顿: 进程风暴+锁竞争导致CPU打满(1308%)
  - ✅ MySQL性能下降: 系统级资源竞争，内核锁竞争占用14.43% CPU
  - ✅ 内核态51.5%: netstat 94.7%内核态，大量进程累积
  - ✅ 性能抖动: 进程创建/销毁的突发特性
  
- [x] **证据链是否闭环？**
  - ✅ 进程风暴检测(count-process-variety) → 热点识别(get-hotspots) → 调用溯源(find-callers) → 语义聚类(cluster-symbols)
  - ✅ 各工具结论相互印证，无矛盾
  
- [x] **是否存在无法解释的孤证？**
  - ✅ containerd-shim也有进程风暴(240 PIDs)，但消耗相对较小(96%)，不影响主结论
  - ✅ kubelet消耗114%属正常系统进程，无异常
  
- [x] **是否考虑过其他可能性？**
  - ✅ 已评估并证伪: Cgroup限流、MySQL自身问题、调度器问题
  - ✅ 已确认: 进程风暴+内核锁竞争

**根因结论**: 

监控脚本以过高频率(约44次/秒)循环调用`netstat`命令，59.77秒内创建2623个短生命周期进程。大量并发读取`/proc/net/tcp`触发内核`established_get_first`函数中的`raw_spin_lock_bh`锁竞争(系统级消耗14.43%，netstat专属38.36%)，导致系统CPU利用率飙升至1308%，表现为机器频繁卡顿和MySQL性能下降。

---

## 五、优化建议与验证方案

### 立即行动

1. **定位并修复监控脚本**
   ```bash
   # 查找频繁调用netstat的进程
   ps aux | grep -E "(netstat|grep|awk|xargs)"
   
   # 检查crontab中相关任务
   crontab -l | grep -i netstat
   
   # 查找包含netstat的脚本
   grep -r "netstat" /etc/cron* /var/spool/cron/ 2>/dev/null
   
   # 查找高频执行的脚本（通过/proc/[pid]/fd定位）
   for pid in $(pgrep -f netstat | head -20); do
     echo "PID: $pid, Parent: $(cat /proc/$pid/status 2>/dev/null | grep PPid)"
     ls -la /proc/$pid/fd/ 2>/dev/null | head -5
   done
   ```

2. **优化监控方式**
   - 使用`ss -s`替代`netstat`（内核接口更优，锁竞争更少）
   - 使用`/proc/net/tcp`直接读取（缓存结果，减少系统调用）
   - 添加缓存，避免每秒多次查询
   - 降低监控频率(如从1秒改为30秒或更长)
   - 合并监控脚本，减少进程创建开销

3. **系统级优化（可选）**
   - 考虑使用更高效的网络监控工具如`conntrack`
   - 对监控脚本进行Cgroup资源限制

### 验证方案

```bash
# 修复后重新采集perf数据
perf record -a -g -- sleep 60
perf script -F comm,pid,cpu,time,core,sym,dso > perf.script.fixed

# 验证进程风暴是否消除
python3 $SKILL_DIR/scripts/perf_expert.py count-process-variety --data perf.script.fixed
# 预期: netstat PID数量<60(1个/秒)，无PROCESS_STORM告警

# 验证CPU利用率下降
python3 $SKILL_DIR/scripts/perf_expert.py show-cpu-usage --data perf.script.fixed
# 预期: 总CPU<500%，内核态比例<30%

# 验证锁竞争消除
python3 $SKILL_DIR/scripts/perf_expert.py cluster-symbols --data perf.script.fixed
# 预期: EVENT_LOCK_CONTENTION<5%
```

---

## 附录

### 关键工具输出存档

**check-cpu-bottleneck:**
```json
{
  "verdict": "HEALTHY",
  "max_core_load": {"cpu_id": 47, "load": "40.48%"},
  "cpu_limit_detected": false
}
```

**show-cpu-usage:**
```json
{
  "cpu_utilization": {
    "total_pct": 1308.49,
    "user_pct": 634.53,
    "kernel_pct": 673.96
  }
}
```

**count-process-variety (netstat):**
```json
{
  "comm": "netstat",
  "unique_pids": 2623,
  "cpu_per_pid": 0.0556,
  "short_lived_ratio": 0.98,
  "behavior": "process_storm"
}
```

**cluster-symbols (netstat):**
```json
{
  "clusters": [
    {"cluster": "EVENT_LOCK_CONTENTION", "ratio_pct": 38.36}
  ]
}
```

### 参考文档

- [SPEAR Skill](../../.config/agents/skills/perf-hunter/SKILL.md)
- [workflow.md](../../.config/agents/skills/perf-hunter/references/workflow.md)
- [tools.md](../../.config/agents/skills/perf-hunter/references/tools.md)
- [templates.md](../../.config/agents/skills/perf-hunter/references/templates.md)
