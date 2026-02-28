# SPEAR 性能诊断文档模板

创建新的性能诊断文档时，复制以下内容作为起始模板。

---

````markdown
# SPEAR 诊断报告: [简短的问题描述]

- **状态**: [进行中 / 已定位 / 已验证 / 已关闭]
- **数据文件**: `perf.script` (6.48s, 6479样本, EXCELLENT可靠性)
- **诊断者**: [Name]
- **最后更新**: [Date]

---

## 一、问题演进记录

记录问题定义随证据变化的迭代过程。

| 版本 | 问题描述 | 关键证据引用 (工具/数据) |
|------|----------|------------------------|
| V1 | [原始现象描述] | [工具名]: [关键指标] ([可靠性]) |
| V2 | [更新后的描述] | [工具名]: [新发现] |
| V3 | [精确定位] | [工具名]: [根因证据] |

### 示例填充

| 版本 | 问题描述 | 关键证据引用 |
|------|----------|-------------|
| V1 | 用户反馈系统性能抖动 | `show-cpu-usage`: 系统CPU 6276.51%, 内核态50.4% (6479样本/EXCELLENT) |
| V2 | 发现单核饱和，用户态/内核态异常均衡 | `check-cpu-bottleneck`: SINGLE_CORE_SATURATION, max_load=6276%@cpu0 |
| V3 | 存在严重进程风暴，netstat高频创建 | `count-process-variety`: 1308个netstat进程, 样本/PID=1.05, 判定=PROCESS_STORM |
| V4 | netstat读取/proc/net/tcp引发内核锁竞争 | `cluster-symbols`: EVENT_LOCK_CONTENTION 16.01%, `find-callers`: established_get_first ← seq_read |

---

## 二、竞争性假设追踪

SPEAR 要求保持**竞争性假设**，并行追踪多条路径直至证伪。

| 假设路径 | 机制评估 | 预期指纹 | 验证结果 | 状态 |
|---------|---------|---------|---------|------|
| **主动消耗**: [假设1描述] | **机制**: [内核/应用运行机制]<br>**副作用**: [可能的副作用] | [工具应观测到的现象] | [实际工具输出] | [待验证/已证伪/确认] |
| **被动压制**: [假设2描述] | **机制**: [限制/调度机制]<br>**副作用**: [观测特征] | [预期现象] | [实际结果] | [待验证/已证伪/确认] |

### 示例填充

| 假设路径 | 机制评估 | 预期指纹 | 验证结果 | 状态 |
|---------|---------|---------|---------|------|
| **主动消耗**: 业务代码计算密集型 | **机制**: 用户态CPU占用主导<br>**副作用**: 内核态比例<30% | `show-cpu-usage`: user% > 60% | user%=49.6%, kernel%=50.4% | ❌ 证伪 |
| **被动压制**: Cgroup CPU限流 | **机制**: throttling触发调度延迟<br>**副作用**: check-cpu-bottleneck报告CPU_LIMIT_SATURATION | `check-cpu-bottleneck`: verdict=CPU_LIMIT_SATURATION | verdict=SINGLE_CORE_SATURATION, cpu_limit_detected=false | ❌ 证伪 |
| **被动压制**: 内核瓶颈(调度/锁/IRQ) | **机制**: 内核态消耗高，调度器/锁竞争事件占比>10%<br>**副作用**: cluster-symbols报告高比例EVENT_SCHEDULER/EVENT_LOCK_CONTENTION | `cluster-symbols`: EVENT_SCHEDULER>10% 或 EVENT_LOCK_CONTENTION显著 | EVENT_LOCK_CONTENTION=16.01%, 调度器=0.31% | ⚠️ 部分匹配 |
| **主动消耗**: 进程风暴导致频繁系统调用 | **机制**: 短生命周期进程大量创建/销毁，系统调用开销激增<br>**副作用**: 进程多样性高，netstat/grep/awk等组合出现 | `count-process-variety`: PROCESS_STORM检测<br>`cluster-comm`: 同类进程聚合消耗高 | netstat: 1308 PIDs, ratio=1.05, storm_detected=true<br>netstat总消耗1117%, 内核态94% | ✅ 确认 |

---

## 三、深度审计记录

### 记录 1: [关键发现标题]

- **工具**: `count-process-variety`
- **关键输出**:
  ```json
  {
    "netstat": {
      "unique_pids": 1308,
      "samples_per_pid": 1.05,
      "behavior": "process_storm",
      "alert": {
        "type": "BEHAVIOR_PROCESS_STORM",
        "severity": "HIGH"
      }
    }
  }
  ```
- **机制发现**: 6.48秒内创建1308个netstat进程，平均每个进程仅1.05个样本，符合短生命周期进程特征。结合`grep`/`awk`/`xargs`/`sh`等进程同时出现，推断为监控脚本循环执行。
- **推论**: 存在监控脚本以过高频率调用netstat命令，需进一步确认其调用来源和目的。

### 记录 2: [热点溯源]

- **工具**: `find-callers --target established_get_first`
- **调用链**: 
  ```
  tcp_get_idx → tcp_seq_start → seq_read → proc_reg_read → vfs_read → ksys_read
  ```
- **机制发现**: netstat通过read系统调用读取/proc/net/tcp文件，触发内核TCP连接表遍历。`established_get_first`遍历过程中需要获取`raw_spin_lock_bh`锁，在高并发访问时产生锁竞争。
- **推论**: 进程风暴导致大量并发读取/proc/net/tcp，引发内核锁竞争（16.01% CPU消耗），进一步放大性能影响。

### 记录 3: [语义聚类验证]

- **工具**: `cluster-symbols`
- **关键输出**:
  | 事件类型 | 占比 | 评估 |
  |---------|------|------|
  | EVENT_LOCK_CONTENTION | 16.01% | 🔴 严重 |
  | EVENT_IRQ_OFF | 2.59% | 正常 |
  | EVENT_SCHEDULER | 0.31% | 正常 |
- **机制发现**: 锁竞争占16.01%是主要瓶颈，调度器开销0.31%说明系统未过载，排除调度问题。
- **推论**: 瓶颈明确为并发访问/proc/net/tcp引发的锁竞争，与进程风暴假设形成完整证据链。

---

## 四、全局审计 (Global Consistency Audit)

最终结论前，强制检查以下项目：

- [x] **是否解释了所有观察到的异常？**
  - ✅ 单核饱和: 进程风暴+锁竞争导致CPU打满
  - ✅ 内核态50%: netstat 94%内核态，大量进程累积
  - ✅ 性能抖动: 进程创建/销毁的突发特性
  
- [x] **证据链是否闭环？**
  - ✅ 进程风暴检测(count-process-variety) → 热点识别(get-hotspots) → 调用溯源(find-callers) → 语义聚类(cluster-symbols)
  - ✅ 各工具结论相互印证，无矛盾
  
- [x] **是否存在无法解释的孤证？**
  - ✅ containerd-shim也有锁竞争(2.41%)，但消耗相对较小，不影响主结论
  - ✅ 异常检测发现的SPIKE/DROP与进程风暴的突发特性一致
  
- [x] **是否考虑过其他可能性？**
  - ✅ 已评估并证伪: Cgroup限流、业务代码低效、调度器问题
  - ✅ 已确认: 进程风暴+内核锁竞争

**根因结论**: 

监控脚本以过高频率(约200次/秒)循环调用`netstat`命令，6.48秒内创建1308个短生命周期进程。大量并发读取`/proc/net/tcp`触发内核`established_get_first`函数中的`raw_spin_lock_bh`锁竞争(消耗16.01% CPU)，导致系统CPU利用率飙升至6276%，表现为性能抖动。

---

## 五、优化建议与验证方案

### 立即行动

1. **定位并修复监控脚本**
   ```bash
   # 查找频繁调用netstat的进程
   ps aux | grep -E "(netstat|grep|awk|xargs)"
   ls -la /proc/$(pgrep -o netstat)/exe 2>/dev/null || echo "进程已退出，检查crontab"
   crontab -l | grep -i netstat
   ```

2. **优化监控方式**
   - 使用`ss -s`替代`netstat`（内核接口更优）
   - 添加缓存，避免每秒多次查询
   - 降低监控频率(如从1秒改为30秒)

### 验证方案

```bash
# 修复后重新采集perf数据
perf record -a -g -- sleep 10
perf script -F comm,pid,cpu,time,core,sym,dso > perf.script.fixed

# 验证进程风暴是否消除
python3 scripts/perf_expert.py count-process-variety --data perf.script.fixed
# 预期: netstat PID数量<10，无PROCESS_STORM告警

# 验证CPU利用率下降
python3 scripts/perf_expert.py show-cpu-usage --data perf.script.fixed
# 预期: 总CPU<1000%，内核态比例<30%

# 验证锁竞争消除
python3 scripts/perf_expert.py cluster-symbols --data perf.script.fixed
# 预期: EVENT_LOCK_CONTENTION<5%
```

---

## 附录

### 关键工具输出存档

```
[在此处粘贴关键工具的完整输出，用于复盘和审计]
```

### 参考文档

- [heuristics.md](references/heuristics.md): SPEAR 启发式规则（五大认知闭包、领域诊断规则）
- [workflow.md](references/workflow.md): 分析流程指南与典型模式
- [tools.md](references/tools.md): 工具命令详细说明
- [data-format.md](references/data-format.md): perf script 格式说明

````

---

## 模板使用指南

### 何时创建文档

在开始任何性能诊断之前，**立即**创建 `debug/[问题描述].md` 文档。

### 更新频率

- **问题演进记录**: 每次工具发现改变问题认知的证据后立即更新
- **竞争性假设追踪**: 每个假设验证后更新"验证结果"和"状态"
- **深度审计**: 在热点溯源阶段，每发现关键调用链就记录一条

### 状态流转

```
进行中 → 已定位 → 已验证 → 已关闭
   ↑        ↑         ↑
  发现    根因确认   修复验证
  新证据   主路径确认  全局审计
          通过
```

### 填写技巧

1. **竞争性假设追踪最少3条假设**: 避免搜索范围过窄，必须包含主动消耗和被动压制两类
2. **机制评估要具体**: 不要写"可能有锁竞争"，要写"读取/proc/net/tcp需要获取tcp_hashinfo锁"
3. **保留证伪记录**: 即使假设被推翻，也不要删除，标注❌并写明证伪原因和证据
4. **引用要精确**: 写明工具名、关键指标数值、可靠性等级，方便他人复验
