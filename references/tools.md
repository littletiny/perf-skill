# Perf Expert 工具命令参考

所有工具通过 `perf_expert.py` 统一入口调用：

```bash
python3 scripts/perf_expert.py <子命令> [选项]
```

每个子命令支持 `--help` 查看详细参数说明。

详细分析流程和方法论请参考 [workflow.md](./workflow.md)。

---

## 工具速查表

| 工具 | 分析阶段 | 核心用途 |
|------|---------|---------|
| `check-cpu-bottleneck` | 边界检查 | 资源限制判定 |
| `show-cpu-usage` | 宏观评估 | 资源消耗概览 |
| `detect-anomalies` | 宏观评估 | 时序异常定位 |
| `analyze-core-distribution` | 宏观评估 | 核心级负载均衡分析 |
| `get-process-top` | 敏感路径 | 高消耗**单进程**识别 |
| `get-comm-top` | 敏感路径 | 高消耗**进程组**识别（大量小进程场景） |
| `get-hotspots` | 敏感路径 | 热点函数排名 |
| `find-callers` | 敏感路径 | 热点函数溯源 |
| `cluster-paths` | 敏感路径 | 调用路径聚类 |
| `cluster-symbols` | 空间搜索 | 语义规则聚类 |
| `count-process-variety` | 领域定位 | 进程风暴检测 |
| `cluster-comm` | 领域定位 | 进程名聚类 |
| `generate-flamegraph` | 可视化 | FlameGraph 导出 |
| `generate-callgraph` | 可视化 | 调用图导出 |

---

## 宏观评估工具

### check-cpu-bottleneck

检查资源限制和单核饱和。

```bash
python3 scripts/perf_expert.py check-cpu-bottleneck \
  --data <perf.script.txt> \
  [--cpu-limit-threshold <ratio>]
```

### show-cpu-usage

查看 CPU 利用率 (user/kernel)。

```bash
python3 scripts/perf_expert.py show-cpu-usage \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>] \
  [--cpu-id <ID>]
```

**分析要点**:
- 总利用率与预期是否匹配？
- user/kernel 比例是否正常？（计算密集型 user 高，IO 型 kernel 可能高）
- 结合 cgroup limit 判断是否被压制

### detect-anomalies

时序异常检测与窗口定位。

```bash
python3 scripts/perf_expert.py detect-anomalies \
  --data <perf.script.txt> \
  [--window-size <sec>] \
  [--spike-threshold <ratio>] \
  [--min-utilization <ratio>] \
  [--cpu-id <ID>]
```

**检测类型**: `SPIKE` | `DROP` | `LEVEL_SHIFT` | `BURST`

**典型用途**:
- 定位异常发生的时间窗口
- 区分持续问题 vs 间歇性问题
- 为后续定向分析提供 `--start-time` / `--end-time` 参数

### analyze-core-distribution

核心级负载分布与均衡性分析。

```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data <perf.script.txt> \
  [--pid <PID>] \
  [--comm <name>] \
  [--comm-regex <pattern>]
```

**典型用途**:
- 是否存在单核瓶颈
- 是否存在负载不均匀

---

## 敏感路径识别工具

### get-process-top

识别高消耗**单个进程**。

```bash
python3 scripts/perf_expert.py get-process-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--cpu-id <ID>]
```

**用途**: 快速定位主要消耗单个进程，为后续 `--pid` 过滤提供目标

**局限**: 无法识别"大量同类进程各自消耗少，但聚合消耗高"的场景

### get-comm-top

识别高消耗**进程组**（大量小进程场景）。

```bash
python3 scripts/perf_expert.py get-comm-top \
  --data <perf.script.txt> \
  [--top-n <N>] \
  [--sort-by-density] \
  [--comm <name>]
```

**专门用于识别**: 大量同类进程吃满资源，但单个进程占用少的场景

**典型场景**:
- Worker pool 过度扩容（如 100 个 worker 每个只用 0.5% CPU，合计 50%）
- 连接风暴（每个连接一个进程/线程，连接数过多）
- 微服务实例过度分片
- 进程泄漏（不断创建新进程处理请求）

**与 `get-process-top` 的区别**:
- `get-process-top`: 找"单个高消耗进程"（如某个进程占 40% CPU）
- `get-comm-top`: 找"同类进程集体高消耗"（如 100 个 worker 各占 0.5% CPU，合计 50%）

### get-hotspots

识别热点函数。

```bash
python3 scripts/perf_expert.py get-hotspots \
  --data <perf.script.txt> \
  [--sort-by inclusive|self] \
  [--top-n <N>] \
  [--pid <PID>] \
  [--comm <name>]
```

**排序方式**:
- `inclusive`: 包含子调用的时间，反映整体影响
- `self`: 仅函数自身执行时间，反映直接消耗

**分析策略**:
- CPU 高但不知道热点 → `--sort-by self` 找直接消耗
- 已知入口函数想分析子调用 → `--sort-by inclusive`，强烈推荐后续使用 `find-callers`

### find-callers

热点函数溯源。

```bash
# 指定 target 模式
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --target <function> \
  [--min-ratio <pct>]

# 自动模式（不能过分依赖，用于启发思路，容易存在遗漏）
python3 scripts/perf_expert.py find-callers \
  --data <perf.script.txt> \
  --auto-target \
  [--auto-target-top-n <N>]
```

**关键检查点**:
- 发现调度函数 (`schedule`/`nanosleep`/`epoll_wait`) → **必须溯源**
  - 调用路径中有业务逻辑 → 主动休眠
  - 调用路径只有内核 → 被动抢占
- 发现锁函数 (`pthread_mutex_lock`/`spinlock`) → **评估粒度**
  - 调用频率高但持有时间短 → 可能正常
  - 调用频率低但持有时间长 → 粗粒度锁问题

### cluster-paths

调用路径聚类，识别共同前缀模式。

```bash
python3 scripts/perf_expert.py cluster-paths \
  --data <perf.script.txt> \
  [--min-depth <N>] \
  [--min-samples <N>] \
  [--top-n <N>] \
  [--pid <PID>]
```

**用途**:
- 从 top-down 视角审视 bottom-up 收集到的信息，避免过度关注细节，忽略整体
- 使用 Trie 识别共同的调用前缀
- 识别高频调用模式
- 发现"重复造轮子"的公共路径

---

## 空间搜索工具

### cluster-symbols

按专家规则语义聚类。

```bash
python3 scripts/perf_expert.py cluster-symbols \
  --data <perf.script.txt> \
  [--no-include-experts] \
  [--custom-rules <json>] \
  [--pid <PID>]
```

**内置规则分类**:
| 类别 | 匹配模式 | 含义 |
|------|---------|------|
| `EVENT_IRQ_OFF` | IRQ off, spin_unlock | 长临界区 |
| `EVENT_SCHEDULER` | schedule, yield | 调度器活动 |
| `EVENT_MEM_RECLAIM` | reclaim, TLB, page | 内存回收 |
| `EVENT_LOCK_CONTENTION` | mutex, spinlock, futex | 锁竞争 |
| `EVENT_SYNC_PRIMITIVE` | pthread_cond, barrier | 同步原语 |

**自定义规则**:
```bash
# 字符串格式
--custom-rules '{"MY_SCHEDULING": "schedule|nanosleep|epoll_wait"}'

# 列表格式
--custom-rules '{"MY_SCHEDULING": ["schedule", "nanosleep", "epoll_wait"]}'

# 领域特定规则
--custom-rules '{
  "RPC": "grpc|protobuf|thrift",
  "DB": "rocksdb|leveldb|sqlite",
  "ML": "tensorflow|torch|cudnn"
}'
```

---

## 领域定位工具

### count-process-variety

检测进程风暴/短生命周期进程。

```bash
python3 scripts/perf_expert.py count-process-variety \
  --data <perf.script.txt> \
  [--storm-pid-threshold <N>] \
  [--storm-cpu-threshold <core/s>]
```

**检测模式**:
| 模式 | 条件 | 含义 |
|------|------|------|
| `PROCESS_STORM` | PID ≥ 阈值 且 平均 CPU/PID ≤ 阈值 | 短生命周期进程风暴 |
| `SHORT_LIVED_HEAVY` | 单秒进程 > 80% 且 PID > 20 | 大量瞬时进程 |
| `LONG_RUNNING` | 单进程主导 | 正常长期运行进程 |

**注意**：由于数据按 1 秒聚合，检测基于 CPU 利用率（core/s）而非样本数量。

### cluster-comm

按进程名聚类分析进程组行为。

```bash
python3 scripts/perf_expert.py cluster-comm \
  --data <perf.script.txt> \
  [--top-n <N>]
```

**用途**:
- 识别同类型进程的资源消耗汇总
- 发现异常进程类型（如预期外的辅助进程）
- 评估进程间资源分配合理性

---

## 可视化工具

### generate-flamegraph

生成 FlameGraph 格式。

```bash
python3 scripts/perf_expert.py generate-flamegraph \
  --data <perf.script.txt> \
  [--output <path>] \
  [--pid <PID>] \
  [--comm <name>]
```

### generate-callgraph

生成调用图（DOT/JSON 格式）。

```bash
python3 scripts/perf_expert.py generate-callgraph \
  --data <perf.script.txt> \
  [--output <path>] \
  [--format dot|json] \
  [--target <function>]
```

---

## 通用参数

所有命令支持:

| 参数 | 说明 | 示例 |
|------|------|------|
| `--data <path>` | perf script 文件路径（必填） | `--data perf.txt` |
| `--cpu-id <ID>` | 仅分析指定 CPU | `--cpu-id 0` |
| `--pid <PID>` | 仅分析指定进程 | `--pid 1234` |
| `--comm <name>` | 按进程名过滤（逗号分隔多值） | `--comm nginx,php-fpm` |
| `--comm-regex <pattern>` | 按进程名正则匹配 | `--comm-regex 'java.*'` |
| `--start-time <ts>` | 起始时间戳（含） | `--start-time 1000.5` |
| `--end-time <ts>` | 结束时间戳（含） | `--end-time 1010.0` |

---

## 参考文档

- 📗 **分析流程指南**: [workflow.md](./workflow.md) - 标准工作流程、典型分析模式
- 📕 **启发式规则手册**: [heuristics.md](./heuristics.md) - 五大认知闭包、诊断规则
- 📋 **文档模板**: [templates.md](./templates.md) - 诊断报告格式
