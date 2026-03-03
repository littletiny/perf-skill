# Pipeline 模块

perf-hunter 的 pipeline 模块提供结构化的输出格式化和 CLI 命令实现。

## 目录结构

```
pipeline/
├── output/                    # 输出格式化模块
│   ├── __init__.py
│   ├── bottleneck_trace_builder.py   # BottleneckTraceOutputBuilder
│   └── example_usage.py       # 使用示例
│
└── cli/
    └── commands/
        ├── __init__.py
        └── bottleneck_trace_cmd.py     # bottleneck-trace CLI 命令
```

## 模块说明

### 1. bottleneck_trace_builder.py

`BottleneckTraceOutputBuilder` 类实现 bottleneck-trace 工具的四段式输出格式化。

#### 数据结构字段名

**EntityDistribution:**
- `comm`: str - 进程组名称
- `count`: int - PID 数量
- `incl_saliency`: float - Inclusive CPU 显著度 (0-1)
- `excl_saliency`: float - Exclusive CPU 显著度 (0-1)
- `core_affinity`: str - 核心亲缘性模式 (Fixed/Uniform/Scattered)
- `throttle_rate`: float - 节流比例 (%)

**CallPathCluster:**
- `cluster_id`: str - 聚类标识
- `comm`: str - 所属进程
- `weight`: float - 占总样本比例 (%)
- `path`: List[str] - 调用链路径
- `hotspot`: str - 汇聚热点符号
- `characteristic`: str - 路径特征标签

**CorrelationFlag:**
- `flag_type`: str - 标志类型
- `target`: str - 目标符号/进程
- `message`: str - 描述信息
- `severity`: str - 严重程度 (critical/warning/info)

**BottleneckTraceResult:**
- `_risk`: RiskInfo - 风险信息
- `entity_distribution`: List[EntityDistribution] - 实体分布矩阵
- `common_hotspot`: str - 共享热点符号
- `common_hotspot_weight`: float - 热点权重
- `clusters`: List[CallPathCluster] - 调用路径聚类
- `correlation_flags`: List[CorrelationFlag] - 关联标志
- `total_pids`: int - PID 总数
- `total_sys_cpu`: float - 系统总 CPU
- `top_bottlenecks`: List[str] - 前三热点符号
- `duration_sec`: float - 持续时间
- `sample_count`: int - 样本数
- `time_range`: TimeRange - 时间范围

#### 输出格式

**[ENTITY_DISTRIBUTION_MATRIX]**
- Markdown 表格格式
- 列：Comm_Group | Count | Incl_Saliency | Excl_Saliency | Core_Affinity | Throttle_Rate
- 瓶颈进程行用 **粗体** 标注

**[CONVERGENCE_TRACE]**
- COMMON_HOTSPOT: 共享热点符号展示
- 每个 Cluster 的路径展示：`comm` -> `func1` -> `func2` -> **[HOTSPOT]**
- 显示 Characteristic 标签和 Weight

**[CORRELATION_FLAGS]**
- 根据 severity 显示不同样式：
  - critical=🔴
  - warning=🟡
  - info=🟢
- 格式：`[FLAG: TYPE] : target message`

**[DATA_SUMMARY]**
- YAML 格式
- 字段：total_pids, total_sys_cpu, top_bottleneck, duration_sec, sample_count, data_quality

#### 使用示例

```python
from output.bottleneck_trace_builder import (
    BottleneckTraceOutputBuilder,
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
)
from perf_toolkit.core.models import RiskInfo, TimeRange

# 构建数据
result = BottleneckTraceResult(
    _risk=RiskInfo(level="critical", message="发现瓶颈"),
    entity_distribution=[
        EntityDistribution(
            comm="app_B",
            count=1,
            incl_saliency=0.96,
            excl_saliency=0.12,
            core_affinity="Fixed: [Core_4]",
            throttle_rate=82.5
        ),
    ],
    common_hotspot="_raw_spin_lock",
    common_hotspot_weight=72.4,
    clusters=[
        CallPathCluster(
            cluster_id="appB Cluster 68%",
            comm="app_B",
            weight=68.0,
            path=["app_B", "handle_request"],
            hotspot="_raw_spin_lock",
            characteristic="Inclusive_Latency_Victim"
        ),
    ],
    correlation_flags=[
        CorrelationFlag(
            flag_type="GLOBAL_LOCK_CONTENTION",
            target="_raw_spin_lock",
            message="usage exceeds 40%",
            severity="critical"
        ),
    ],
    total_pids=2421,
    total_sys_cpu=165.2,
    top_bottlenecks=["_raw_spin_lock"],
    duration_sec=60.0,
    sample_count=31500,
    time_range=TimeRange()
)

# 生成输出
builder = BottleneckTraceOutputBuilder(result)
output = builder.build()
print(output)
```

### 2. bottleneck_trace_cmd.py

`cmd_bottleneck_trace` 函数实现 `shecr bottleneck-trace` CLI 命令。

#### 命令参数

```
--data FILE            # 数据文件路径（必需）
--auto-detect          # 自动检测瓶颈进程
--comm COMM            # 分析指定进程
--pid PID              # 分析指定 PID
--start-time TIME      # 开始时间（ISO 8601）
--end-time TIME        # 结束时间
--hotspots-limit N     # 热点分析数量（默认 20）
--callers-limit N      # 调用链数量（默认 10）
--max-depth N          # 最大调用深度（默认 5）
--verbose              # 详细输出
```

#### 命令逻辑

1. 解析参数（通过 @command 装饰器）
2. 加载 samples 数据
3. 调用 `BottleneckTracer.trace()` 执行分析
4. 转换结果为 `BottleneckTraceResult`
5. 使用 `BottleneckTraceOutputBuilder` 格式化输出
6. 打印结果并记录风险到 Trace

#### 使用示例

```bash
# 自动检测并分析瓶颈进程
shecr bottleneck-trace --data perf.data --auto-detect

# 分析指定进程
shecr bottleneck-trace --data perf.data --comm app_B

# 分析指定 PID
shecr bottleneck-trace --data perf.data --pid 1234

# 时间范围限定
shecr bottleneck-trace --data perf.data --comm app_B \
    --start-time "2026-03-01T10:00:00" \
    --end-time "2026-03-01T10:05:00"

# 调整热点分析数量
shecr bottleneck-trace --data perf.data --comm app_B --hotspots-limit 30

# 详细输出
shecr bottleneck-trace --data perf.data --comm app_B --verbose
```

## 依赖关系

```
pipeline/output/bottleneck_trace_builder.py
    ├── perf_toolkit/core/models.py (RiskInfo, TimeRange)
    └── dataclasses

pipeline/cli/commands/bottleneck_trace_cmd.py
    ├── perf_toolkit/cli/decorators.py (@command)
    ├── perf_toolkit/core/models.py (RiskInfo, TimeRange)
    ├── perf_toolkit/analysis/facade.py (AnalysisFacade)
    ├── perf_toolkit/composite/bottleneck_trace.py (BottleneckTracer)
    └── pipeline/output/bottleneck_trace_builder.py
```

## 代码规范

- 不使用 regex
- 错误处理简单（let it crash）
- 输出格式 AI 友好
- 强制静态类型（使用 dataclass）
- 时间格式使用 ISO 8601
