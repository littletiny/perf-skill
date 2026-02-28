# SPEAR 系统性能诊断综合报告

- **状态**: 已定位 / 已验证
- **数据文件**: `netstat_perf.data` (59.77s, EXCELLENT 数据质量)
- **诊断者**: SPEAR Agent
- **最后更新**: 2026-03-01

---

## 一、问题演进记录

| 版本 | 问题描述 | 关键证据引用 |
|------|----------|-------------|
| V1 | 机器频繁卡顿，MySQL性能下降 | 用户反馈 |
| V2 | 发现严重进程风暴，netstat高频创建 | `count-process-variety`: 2623个netstat进程, CPU/PID=0.056 core/s, PROCESS_STORM |
| V3 | 确认双热点：内核锁竞争 + containerd-shim锁竞争 | `get-hotspots`: established_get_first=8.21%, _raw_spin_lock_bh=6.25%; `cluster-symbols`(containerd-shim): LOCK_CONTENTION=79.84% |
| V4 | 根因定位①：netstat读取/proc/net/tcp引发内核锁竞争 | `find-callers`: established_get_first ← seq_read; `cluster-symbols`(netstat): LOCK_CONTENTION=38.36% |
| V5 | 根因定位②：containerd-shim高频访问cgroup文件系统 | `find-callers`(containerd-shim): osq_lock ← kernfs_iop_permission/kernfs_dop_revalidate |

---

## 二、竞争性假设追踪

| 假设路径 | 机制评估 | 预期指纹 | 验证结果 | 状态 |
|---------|---------|---------|---------|------|
| **主动消耗**: MySQL自身计算密集型负载 | **机制**: SQL查询复杂度高<br>**副作用**: 用户态CPU高，mysqld进程热点在查询执行 | `show-cpu-usage`: user%高<br>`get-hotspots`: MySQL相关函数高 | MySQL进程未进入TOP消耗，user%=48.5%, kernel%=51.5% | ❌ 证伪 |
| **主动消耗**: 系统级进程风暴 | **机制**: 短生命周期进程频繁创建销毁，系统调用开销激增<br>**副作用**: 内核态消耗高，大量不同PID | `count-process-variety`: PROCESS_STORM检测<br>`cluster-comm`: 同类进程聚合消耗高 | netstat: 2623 PIDs, CPU/PID=0.056, storm_detected=true<br>netstat总消耗244%，内核态94.7% | ✅ 确认 |
| **被动压制**: 内核锁竞争 (netstat相关) | **机制**: 并发访问/proc/net/tcp触发tcp_hashinfo锁竞争<br>**副作用**: established_get_first和_raw_spin_lock_bh占比高 | `cluster-symbols`: LOCK_CONTENTION>10%<br>`find-callers`: 指向seq_read/proc_reg_read | LOCK_CONTENTION=14.43%(系统级), 38.36%(netstat)<br>调用链确认来自/proc/net/tcp读取 | ✅ 确认 |
| **被动压制**: cgroup文件系统锁竞争 (containerd-shim相关) | **机制**: 高频访问cgroup/kernfs触发mutex锁竞争<br>**副作用**: osq_lock和kernfs函数占比高 | `cluster-symbols`(containerd-shim): LOCK_CONTENTION>50%<br>`find-callers`: kernfs相关调用链 | LOCK_CONTENTION=79.84%(containerd-shim)<br>osq_lock=63.06%, 调用链指向kernfs_iop_permission | ✅ 确认 |
| **被动压制**: Cgroup CPU限流 | **机制**: CPU quota触发throttling<br>**副作用**: check-cpu-bottleneck报告CPU_LIMIT_SATURATION | `check-cpu-bottleneck`: verdict=CPU_LIMIT_SATURATION | verdict=HEALTHY, cpu_limit_detected=false | ❌ 证伪 |
| **被动压制**: 调度器问题 | **机制**: 调度延迟或过度抢占<br>**副作用**: SCHEDULER占比高 | `cluster-symbols`: EVENT_SCHEDULER>5% | EVENT_SCHEDULER=0.27%(系统级), 0.04%(netstat) | ❌ 证伪 |

---

## 三、深度审计记录

### 记录 1: 进程风暴检测 (netstat)

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

### 记录 2: 热点溯源 - netstat内核锁竞争

- **工具**: `find-callers --target established_get_first`
- **调用链**: 
  ```
  tcp_get_idx → tcp_seq_start → seq_read → proc_reg_read → vfs_read → ksys_read (53.88%)
  tcp_seq_next → seq_read → proc_reg_read → vfs_read → ksys_read (46.12%)
  ```
- **机制发现**: netstat通过read系统调用读取/proc/net/tcp文件，触发内核TCP连接表遍历。`established_get_first`在遍历过程中需要获取`raw_spin_lock_bh`锁，在高并发访问时产生锁竞争。
- **推论**: 进程风暴导致大量并发读取/proc/net/tcp，引发内核锁竞争。

### 记录 3: 语义聚类验证 - netstat锁竞争占比

- **工具**: `cluster-symbols` (netstat)
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
- **推论**: 存在系统性进程创建过度问题，netstat是最严重的单个贡献者，containerd-shim也有进程风暴特征。

### 记录 5: containerd-shim 深度分析 - cgroup文件系统锁竞争

- **工具**: `cluster-symbols` (containerd-shim)
- **关键输出**:
  ```json
  {
    "clusters": [
      {"cluster": "EVENT_LOCK_CONTENTION", "ratio_pct": 79.84},
      {"cluster": "EVENT_IRQ_OFF", "ratio_pct": 1.65},
      {"cluster": "EVENT_SYNC_PRIMITIVE", "ratio_pct": 0.46}
    ]
  }
  ```
- **热点函数**: `osq_lock` (63.06%), `native_queued_spin_lock_slowpath` (14.67%)
- **工具**: `find-callers --target osq_lock` (containerd-shim)
- **调用链分析**:
  ```
  41.53%: __mutex_lock → kernfs_iop_permission → inode_permission → link_path_walk → path_openat
  40.09%: __mutex_lock → kernfs_dop_revalidate → lookup_fast → walk_component → link_path_walk
   6.22%: __mutex_lock → kernfs_iop_permission → inode_permission → may_open → path_openat
   5.21%: __mutex_lock → kernfs_dop_revalidate → lookup_fast → path_openat → do_filp_open
  ```
- **机制发现**: containerd-shim 频繁访问 cgroup 文件系统（通过 kernfs），`kernfs_iop_permission` 和 `kernfs_dop_revalidate` 的 mutex 锁竞争导致 `osq_lock` 高消耗。240个实例集体消耗107% CPU，其中79.84%用于锁等待。
- **推论**: 存在高频的容器状态查询、cgroup文件读取或进程监控操作，需要排查相关监控工具配置。

### 记录 6: 各进程内核态占比排名

| 排名 | 进程 | 总CPU% | 内核态% | 内核态占比 | 评估 |
|------|------|--------|---------|-----------|------|
| 1 | **netstat** | 243.87% | 230.94% | **94.7%** | 🔴 极高异常 |
| 2 | **containerd-shim** | 107.27% | 96.46% | **89.9%** | 🔴 极高异常 |
| 3 | sh | 35.91% | 31.16% | 86.8% | 🟡 高（短生命周期正常） |
| 4 | grep | 23.06% | 16.11% | 69.9% | 🟡 高（短生命周期正常） |
| 5 | python3 | 207.35% | 134.42% | 72.93% | 35.2% | 🟢 正常 |
| 6 | dbatman | 148.07% | 109.05% | 39.02% | 26.4% | 🟢 正常 |
| 7 | telegraf | 63.78% | 34.89% | 28.89% | 45.3% | 🟢 正常 |
| 8 | kubelet | 115.10% | 98.62% | 16.48% | 14.3% | 🟢 正常 |
| 9 | ilogtail | 52.07% | 49.51% | 2.55% | 4.9% | 🟢 健康 |

---

## 四、全局审计 (Global Consistency Audit)

- [x] **是否解释了所有观察到的异常？**
  - ✅ 机器卡顿: 进程风暴+双锁竞争导致CPU打满(1308%)
  - ✅ MySQL性能下降: 系统级资源竞争，内核锁竞争占用14.43% CPU
  - ✅ 内核态51.5%: netstat 94.7%内核态 + containerd-shim 89.9%内核态，大量进程累积
  - ✅ 性能抖动: 进程创建/销毁的突发特性
  - ✅ containerd-shim高消耗: 79.84%锁竞争来自cgroup/kernfs访问
  
- [x] **证据链是否闭环？**
  - ✅ netstat链: 进程风暴检测(count-process-variety) → 热点识别(get-hotspots) → 调用溯源(find-callers) → 语义聚类(cluster-symbols)
  - ✅ containerd-shim链: 高内核态占比 → 语义聚类(cluster-symbols) → 调用溯源(find-callers) → kernfs锁竞争确认
  - ✅ 各工具结论相互印证，无矛盾
  
- [x] **是否存在无法解释的孤证？**
  - ✅ kubelet消耗114%属正常系统进程，无异常
  - ✅ python3(826 PIDs)虽有进程风暴但锁竞争仅1.10%，不影响主结论
  
- [x] **是否考虑过其他可能性？**
  - ✅ 已评估并证伪: Cgroup限流、MySQL自身问题、调度器问题
  - ✅ 已确认: netstat进程风暴+内核锁竞争、containerd-shim cgroup锁竞争

### 根因结论

系统存在**两个独立的严重性能问题**，共同导致机器卡顿和MySQL性能下降：

**问题① - netstat进程风暴（最高优先级）:**
监控脚本以过高频率(约44次/秒)循环调用`netstat`命令，59.77秒内创建2623个短生命周期进程。大量并发读取`/proc/net/tcp`触发内核`established_get_first`函数中的`raw_spin_lock_bh`锁竞争(系统级消耗14.43%，netstat专属38.36%)，浪费243.87% CPU。

**问题② - containerd-shim cgroup锁竞争（高优先级）:**
containerd-shim 高频访问 cgroup 文件系统（通过 kernfs），`kernfs_iop_permission` 和 `kernfs_dop_revalidate` 的 mutex 锁竞争导致 `osq_lock` 高消耗(63.06%)。240个实例集体消耗107% CPU，其中79.84%用于锁等待，是系统整体锁竞争的主要贡献者之一。

**综合影响**: 两个问题叠加导致系统CPU利用率飙升至1308%，表现为机器频繁卡顿和MySQL性能下降。

---

## 五、优化建议与验证方案

### 🔴🔴🔴 立即行动（最高优先级）

#### 1. 修复 netstat 监控脚本

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

**优化方案**:
- 使用`ss -s`替代`netstat`（内核接口更优，锁竞争更少）
- 使用`/proc/net/tcp`直接读取（缓存结果，减少系统调用）
- 添加缓存，避免每秒多次查询
- 降低监控频率(如从1秒改为30秒或更长)
- 合并监控脚本，减少进程创建开销

#### 2. 排查 containerd-shim 高频访问

```bash
# 检查是什么在频繁访问 cgroup 文件系统
strace -e trace=file -p $(pgrep -d',' containerd-shim | head -5) 2>&1 | head -50

# 检查 kubelet 或其他组件的容器状态查询频率
grep -r "cgroup" /var/log/containers/ 2>/dev/null | head -20

# 检查 cadvisor 或类似监控工具的采集频率
ps aux | grep -E "(cadvisor|kubelet)" | grep -v grep
```

**优化方案**:
- 检查 containerd-shim 的轮询频率，降低状态查询间隔
- 检查是否有监控工具（如cadvisor）高频访问 cgroup 文件系统
- 考虑升级 containerd 版本（新版本可能优化了 kernfs 访问）
- 检查是否有过多的容器创建/销毁操作
- 考虑使用 cgroup v2（相比 v1 有更好的性能）

### 🟢 中期优化

1. **系统级监控改进**
   - 设置 netstat 进程数量告警阈值（>100个/分钟需关注）
   - 设置 containerd-shim CPU 告警阈值（单实例 >5% 需关注）
   - 监控 `/sys/fs/cgroup` 访问频率

2. **架构优化**
   - 对监控脚本进行Cgroup资源限制
   - 考虑使用更高效的网络监控工具如`conntrack`
   - 将高频监控脚本迁移到独立节点或降低采集频率

### 验证方案

```bash
# 修复后重新采集perf数据
perf record -a -g -- sleep 60
perf script -F comm,pid,cpu,time,core,sym,dso > perf.script.fixed

# 验证1: netstat进程风暴是否消除
python3 $SKILL_DIR/scripts/perf_expert.py count-process-variety --data perf.script.fixed
# 预期: netstat PID数量<60(1个/秒)，无PROCESS_STORM告警

# 验证2: containerd-shim锁竞争是否降低
python3 $SKILL_DIR/scripts/perf_expert.py cluster-symbols --data perf.script.fixed --pid $(pgrep containerd-shim | head -1)
# 预期: EVENT_LOCK_CONTENTION<20%

# 验证3: 整体CPU利用率下降
python3 $SKILL_DIR/scripts/perf_expert.py show-cpu-usage --data perf.script.fixed
# 预期: 总CPU<500%，内核态比例<30%

# 验证4: 系统级锁竞争消除
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

**cluster-symbols (containerd-shim):**
```json
{
  "clusters": [
    {"cluster": "EVENT_LOCK_CONTENTION", "ratio_pct": 79.84},
    {"cluster": "EVENT_IRQ_OFF", "ratio_pct": 1.65},
    {"cluster": "EVENT_SYNC_PRIMITIVE", "ratio_pct": 0.46}
  ]
}
```

**osq_lock 调用链（containerd-shim）:**
```
41.53%: __mutex_lock → kernfs_iop_permission → inode_permission → link_path_walk
40.09%: __mutex_lock → kernfs_dop_revalidate → lookup_fast → walk_component
```

### 全系统锁竞争来源汇总

| 来源 | LOCK_CONTENTION 占比 | 说明 |
|------|---------------------|------|
| **containerd-shim** | 79.84% | cgroup/kernfs 文件访问锁竞争 |
| **netstat** | 38.36% | /proc/net/tcp 读取锁竞争 |
| **系统级** | 14.43% | 整体平均 |
| python3 | 1.10% | 健康 |
| kubelet | 1.76% | 健康 |
| dbatman | 1.07% | 健康 |
| telegraf | 3.83% | 可接受 |

### 关键内核热点函数（系统级）

| 函数 | self占比 | 主要来源进程 | 说明 |
|------|----------|-------------|------|
| `established_get_first` | 8.21% | netstat | TCP连接表遍历 |
| `_raw_spin_lock_bh` | 6.25% | netstat/containerd-shim | 内核spinlock竞争 |
| `osq_lock` | 4.77% | containerd-shim | mutex排队锁 |
| `native_queued_spin_lock_slowpath` | 2.19% | containerd-shim | spinlock慢路径 |

### 参考文档

- [SPEAR Skill](../../.config/agents/skills/perf-hunter/SKILL.md)
- [workflow.md](../../.config/agents/skills/perf-hunter/references/workflow.md)
- [tools.md](../../.config/agents/skills/perf-hunter/references/tools.md)
- [templates.md](../../.config/agents/skills/perf-hunter/references/templates.md)
