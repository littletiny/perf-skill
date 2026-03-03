# CLI Layer 接口设计文档

> CLI Layer 是 perf-hunter 的三层架构中的最上层，负责参数解析、命令路由、Trace 记录触发和输出渲染。
>
> 版本: 1.0  
> 更新日期: 2026-03-03

---

## 1. 架构定位

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: CLI Layer (命令层)                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ cli/                                                    │    │
│  │   ├── main.py           (参数解析与命令路由)             │    │
│  │   ├── decorators.py     (@command 装饰器)               │    │
│  │   ├── builders.py       (OutputBuilder 包装)            │    │
│  │   └── commands/                                         │    │
│  │       ├── analysis/     (6个分析命令注册)                │    │
│  │       ├── composite/    (2个组合命令注册)                │    │
│  │       └── trace/        (9个trace命令注册)               │    │
│  └─────────────────────────────────────────────────────────┘    │
│  职责: 参数解析、命令路由、Trace触发、输出渲染                     │
│  原则: CLI层是Trace记录的唯一触发点                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ 调用下层接口
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Analysis / Composite (分析/组合层)                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ AnalysisFacade, SysAuditor, BottleneckTracer            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Core (核心层)                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ OutputBuilder, PerfExpertEngine, Trace                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 命令处理器类型定义

### 2.1 分析命令处理器

```python
from typing import Callable, List, Dict, Any
from argparse import Namespace

# 分析命令处理器类型
AnalysisCommandHandler = Callable[
    [
        'OutputBuilder',      # 输出构建器（已初始化，含Trace）
        'PerfExpertEngine',   # 数据引擎
        Namespace,            # 解析后的参数
        List[Dict[str, Any]]  # 过滤后的样本数据
    ],
    'BaseOutput'            # 返回输出对象
]
```

**说明**:
- 处理器接收 `builder`, `engine`, `args`, `samples` 四个参数
- `@command` 装饰器自动处理前三个参数的创建和传递
- 处理器只需关注业务逻辑和输出对象构建
- 返回的 `BaseOutput` 子类由装饰器自动渲染

### 2.2 组合命令处理器

```python
# 组合命令处理器类型（与分析命令同构）
CompositeCommandHandler = Callable[
    [
        'OutputBuilder',
        'PerfExpertEngine',
        Namespace,
        List[Dict[str, Any]]
    ],
    'BaseOutput'
]
```

**说明**:
- 组合命令处理器与分析命令处理器类型相同
- 差异在于内部实现：组合命令通过 `AnalysisFacade` 调用分析工具
- 组合命令的 Trace 只记录顶层命令，内部调用不记录

---

## 3. 命令注册接口

### 3.1 Analysis 层命令注册

**文件**: `cli/commands/analysis/__init__.py`

```python
from typing import Dict, Callable
from argparse import _SubParsersAction

# 命令到模块的映射（延迟导入）
COMMAND_MAP: Dict[str, str] = {
    'get-hotspots': 'perf_toolkit.cli.commands.analysis.hotspots',
    'find-callers': 'perf_toolkit.cli.commands.analysis.callers',
    'detect-anomalies': 'perf_toolkit.cli.commands.analysis.anomalies',
    'cluster-paths': 'perf_toolkit.cli.commands.analysis.path_clusters',
    'analyze-core-distribution': 'perf_toolkit.cli.commands.analysis.core_dist',
    'get-comm-top': 'perf_toolkit.cli.commands.analysis.comm_top',
}


def register_commands(subparsers: _SubParsersAction) -> None:
    """
    注册所有分析命令参数
    
    Args:
        subparsers: argparse subparsers 对象
        
    功能:
        - 为每个分析命令创建 ArgumentParser
        - 定义各命令的参数（--data, --top-n, --cpu-id 等）
    """
    pass


def get_command_handler(command_name: str) -> AnalysisCommandHandler:
    """
    获取命令处理函数（延迟导入）
    
    Args:
        command_name: 命令名称，如 'get-hotspots'
        
    Returns:
        对应命令的处理函数
        
    Raises:
        ValueError: 未知命令
        
    实现要点:
        - 根据 COMMAND_MAP 动态导入模块
        - 从模块中获取 cmd_xxx 函数
        - 返回的函数已被 @command 装饰器包装
    """
    pass
```

### 3.2 Composite 层命令注册

**文件**: `cli/commands/composite/__init__.py`

```python
from typing import Dict, Callable
from argparse import _SubParsersAction

# 组合命令映射
COMMAND_MAP: Dict[str, str] = {
    'sys-audit': 'perf_toolkit.cli.commands.composite.sys_audit',
    'bottleneck-trace': 'perf_toolkit.cli.commands.composite.bottleneck_trace',
}


def register_commands(subparsers: _SubParsersAction) -> None:
    """
    注册组合命令
    
    Args:
        subparsers: argparse subparsers 对象
    """
    pass


def get_command_handler(command_name: str) -> CompositeCommandHandler:
    """
    获取组合命令处理函数
    
    Args:
        command_name: 'sys-audit' 或 'bottleneck-trace'
        
    Returns:
        组合命令的处理函数
    """
    pass
```

---

## 4. @command 装饰器接口

**文件**: `cli/decorators.py`

```python
from functools import wraps
from typing import Callable, List, Optional

def command(
    name: str,
    filters: Optional[List[str]] = None
) -> Callable[[AnalysisCommandHandler], AnalysisCommandHandler]:
    """
    命令装饰器 - 统一处理样板代码和 Trace 记录
    
    这是 CLI Layer 的核心机制，封装了所有命令的共同逻辑：
    1. OutputBuilder 创建（集成 Trace auto_trace）
    2. 命令开始记录（自动记录到 timeline）
    3. 样本过滤参数提取
    4. 样本获取（调用 engine.get_filtered_samples）
    5. 空样本检查（自动输出错误信息）
    6. 数据质量评估
    7. 业务逻辑执行
    8. 自动输出渲染
    
    Args:
        name: 命令名称，如 "get-hotspots"，用于 Trace 记录
        filters: 过滤参数列表，None 表示使用全部6个
                 可选值: ["start_time", "end_time", "cpu_id", "pid", "comm", "comm_regex"]
    
    Returns:
        装饰后的函数，签名从 (builder, engine, args, samples) -> BaseOutput
        变为 (engine, args) -> BaseOutput
    
    使用示例:
        @command("get-hotspots")
        def cmd_get_hotspots(builder, engine, args, samples):
            # 业务逻辑
            hotspots = analyze_hotspots(samples)
            return HotspotsOutput(_risk=risk, hotspots=hotspots, summary=summary)
    
    自定义过滤参数:
        @command("cluster-paths", filters=["cpu_id", "pid", "comm"])
        def cmd_cluster_paths(builder, engine, args, samples):
            # 只传递 cpu_id, pid, comm 三个过滤参数
            ...
    """
    ALL_FILTERS = ["start_time", "end_time", "cpu_id", "pid", "comm", "comm_regex"]
    
    def decorator(func: AnalysisCommandHandler) -> AnalysisCommandHandler:
        @wraps(func)
        def wrapper(engine, args):
            from .builders import OutputBuilder
            
            # 1. 创建 builder（内部已集成 Trace auto_trace）
            builder = OutputBuilder(engine, args)
            
            # 2. 开始命令（自动记录到 timeline）
            builder.begin_command(name)
            
            # 3. 获取过滤参数
            effective_filters = filters if filters is not None else ALL_FILTERS
            kwargs = {f: getattr(args, f, None) for f in effective_filters}
            
            # 4. 获取样本
            samples = engine.get_filtered_samples(**kwargs)
            
            # 5. 空检查（自动处理输出）
            if builder.check_empty_samples(samples, filters=kwargs):
                return
            
            # 6. 质量评估
            builder.assess_quality(samples)
            
            # 7. 执行业务逻辑，返回 output
            output = func(builder, engine, args, samples)
            
            # 8. 自动输出（内部会调用 _auto_record_risk_from_output）
            if output is not None:
                builder.print_output(output)
            
            return output
        
        return wrapper
    return decorator
```

### 4.1 装饰器处理流程

```
用户执行: shecr get-comm-top --data xxx.data --top-n 20

┌─────────────────┐
│ 创建 parser     │
│ 解析参数        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 获取 handler    │
│ (已装饰的函数)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ @command 装饰器内部流程                 │
│                                         │
│ 1. OutputBuilder(engine, args)          │
│    └── 初始化 Trace (auto_trace=True)   │
│                                         │
│ 2. builder.begin_command("get-comm-top")│
│    └── Trace.begin_command()            │
│    └── 记录到 timeline                  │
│                                         │
│ 3. 提取过滤参数                         │
│    └── args.cpu_id, args.comm, ...      │
│                                         │
│ 4. engine.get_filtered_samples(**kwargs)│
│    └── 返回样本列表                     │
│                                         │
│ 5. builder.check_empty_samples()        │
│    └── 为空则输出错误并返回             │
│                                         │
│ 6. builder.assess_quality()             │
│    └── 评估数据质量                     │
│                                         │
│ 7. 执行业务逻辑函数 func()              │
│    └── 返回 BaseOutput 对象             │
│                                         │
│ 8. builder.print_output(output)         │
│    ├── 提取 output._risk                │
│    ├── 自动记录 risk 到 Trace           │
│    └── 渲染输出（JSON/Text）            │
└─────────────────────────────────────────┘
```

---

## 5. 输出类型与渲染流程

### 5.1 输出类型继承关系

```
BaseOutput (core/output_models.py)
├── _risk: RiskInfo              # 风险信息（必须）
├── summary: BaseSummary         # 摘要信息
├── time_range: TimeRange        # 时间范围
└── _template_config: TemplateConfig  # 渲染配置

    CommTopOutput                    # get-comm-top
    ├── comm_groups: List[CommGroupItem]

    HotspotsOutput                   # get-hotspots
    ├── hotspots: List[HotspotItem]

    AnomaliesOutput                  # detect-anomalies
    ├── anomalies: List[AnomalyItem]

    PathClustersOutput               # cluster-paths
    ├── path_clusters: List[PathClusterItem]

    CoreDistributionOutput           # analyze-core-distribution
    ├── cores: List[CoreItem]

    AttributionsOutput               # find-callers
    ├── attributions: List[AttributionItem]

    SysAuditOutput                   # sys-audit (Composite)
    ├── diagnosis: Dict
    └── details: Dict

    BottleneckTraceOutput            # bottleneck-trace (Composite)
    ├── target_comm: str
    ├── bottleneck_analysis: Dict
    ├── hotspots: Dict
    └── callers: Optional[Dict]
```

### 5.2 渲染流程

```python
# CLI Layer 不负责直接渲染，通过 OutputBuilder 触发

class OutputBuilder:
    def print_output(self, output: BaseOutput, auto_end: bool = True):
        """
        打印输出对象
        
        流程:
        1. 自动从 output._risk 提取并记录到 Trace
        2. 根据 text_mode 选择渲染器:
           - text_mode=True: 使用 TextOutputAdapter（人类可读）
           - text_mode=False: 使用 OutputAdapter（JSON）
        3. 调用 Adapter 渲染并打印
        4. 自动结束命令记录
        """
        # 1. 自动记录 risk
        self._auto_record_risk_from_output(output)
        
        # 2. 渲染输出
        if self.text_mode:
            text_str = self.adapter.format_output(output)
            print(text_str)
        else:
            json_str = self.adapter.to_json(output)
            print(json_str)
        
        # 3. 结束命令记录
        if auto_end:
            self.end_command()
```

### 5.3 输出模式

| 模式 | 适配器 | 用途 |
|------|--------|------|
| Text | `TextOutputAdapter` | 人类可读（默认） |
| JSON | `OutputAdapter` | 程序化解析 |
| Compact | `CompactOutputAdapter` | 压缩 JSON |

---

## 6. 命令清单与层级映射

### 6.1 分析命令（6个）

| 命令 | 层级 | 输出类型 | 所在文件 |
|------|------|----------|----------|
| `analyze-core-distribution` | 系统级 | `CoreDistributionOutput` | `cli/commands/analysis/core_dist.py` |
| `detect-anomalies` | 时间级 | `AnomaliesOutput` | `cli/commands/analysis/anomalies.py` |
| `get-comm-top` | 实体级 | `CommTopOutput` | `cli/commands/analysis/comm_top.py` |
| `get-hotspots` | 函数级 | `HotspotsOutput` | `cli/commands/analysis/hotspots.py` |
| `find-callers` | 关系级 | `AttributionsOutput` | `cli/commands/analysis/callers.py` |
| `cluster-paths` | 模式级 | `PathClustersOutput` | `cli/commands/analysis/path_clusters.py` |

### 6.2 组合命令（2个）

| 命令 | 链式触发 | 输出类型 | 所在文件 |
|------|----------|----------|----------|
| `sys-audit` | anomalies→core-dist→comm-top | `SysAuditOutput` | `cli/commands/composite/sys_audit.py` |
| `bottleneck-trace` | comm-top→hotspots→paths | `BottleneckTraceOutput` | `cli/commands/composite/bottleneck_trace.py` |

### 6.3 Trace 命令（9个）

| 命令 | 功能 | 所在文件 |
|------|------|----------|
| `trace init` | 初始化 Trace 文档 | `cli/commands/trace/init.py` |
| `trace add` | 添加 Issue | `cli/commands/trace/add.py` |
| `trace timeline` | 查看时间线 | `cli/commands/trace/timeline.py` |
| `trace issues` | 查看 Issues | `cli/commands/trace/issues.py` |
| `trace audit` | 审计 Issues | `cli/commands/trace/audit.py` |
| `trace complete` | 解决 Issue | `cli/commands/trace/complete.py` |
| `trace reopen` | 重新打开 Issue | `cli/commands/trace/reopen.py` |
| `trace finalize` | 完成诊断 | `cli/commands/trace/finalize.py` |
| `trace export` | 导出 Trace | `cli/commands/trace/export.py` |

---

## 7. Trace 记录触发机制

### 7.1 CLI 层作为 Trace 唯一触发点

```
用户命令执行
     │
     ▼
┌─────────────────┐
│ @command 装饰器  │◄── CLI Layer（触发点）
│                 │
│ begin_command() │───▶ Trace.begin_command()
│                 │
│ record_risk()   │───▶ Trace.add()
│                 │     （当 _risk.action_required=true）
│ end_command()   │───▶ Trace.end_command()
└─────────────────┘
```

### 7.2 Composite 层的 Trace 隔离

```python
# composite/sys_audit.py

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """
    系统审计组合命令 - 只记录顶层命令到 Trace
    """
    from ..analysis.facade import AnalysisFacade
    
    # 创建 facade（内部调用不触发 Trace）
    facade = AnalysisFacade(engine)
    
    # 以下调用不记录到 Trace（通过 facade 内部实现控制）
    anomalies = facade.detect_anomalies(samples)      # 不记录
    core_dist = facade.analyze_core_distribution(samples)  # 不记录
    comm_top = facade.analyze_comm_top(samples)       # 不记录
    
    # 综合分析结果
    diagnosis = _synthesize(anomalies, core_dist, comm_top)
    
    # 只记录综合诊断结果
    if diagnosis["primary_suspect"]:
        builder.record_risk(
            "critical",
            f"发现主要性能瓶颈: {diagnosis['primary_suspect']['comm']}",
            f"执行 bottleneck-trace --comm {diagnosis['primary_suspect']['comm']}"
        )
    
    return SysAuditOutput(_risk=risk, diagnosis=diagnosis, details=...)
```

**关键原则**:
- CLI Layer 是 Trace 记录的唯一触发点
- Analysis 层提供双接口：
  - CLI 接口（`@command` 装饰）：触发 Trace
  - 内部接口（`AnalysisFacade`）：不触发 Trace
- Composite 命令通过 `AnalysisFacade` 调用，避免 Trace 污染

---

## 8. 新增命令开发指南

### 8.1 开发分析命令

```python
# cli/commands/analysis/my_analysis.py

from ...cli.decorators import command
from ...core.output_models import RiskInfo, MyAnalysisOutput, MyAnalysisSummary
from ...analysis.facade import AnalysisFacade

@command("my-analysis")
def cmd_my_analysis(builder, engine, args, samples):
    """
    我的分析命令
    
    Args:
        builder: OutputBuilder 实例（已初始化）
        engine: PerfExpertEngine 实例
        args: argparse.Namespace
        samples: 过滤后的样本列表
    
    Returns:
        BaseOutput 子类实例
    """
    # 1. 调用 AnalysisFacade 进行分析
    facade = AnalysisFacade(engine)
    result = facade.my_analysis(samples, param=args.param)
    
    # 2. 构建 risk 信息
    risk = RiskInfo(
        level="warning" if result["has_issue"] else "none",
        message=result["message"],
        hint="建议执行的下一步命令",
        patterns=["DETECTED_PATTERN"],
        action_required=result["has_issue"]
    )
    
    # 3. 构建 summary
    summary = MyAnalysisSummary(
        total_items=result["count"],
        shown_items=len(result["items"])
    )
    
    # 4. 构建输出对象
    output = MyAnalysisOutput(
        _risk=risk,
        items=result["items"],
        summary=summary
    )
    
    return output
```

### 8.2 注册新命令

```python
# cli/commands/analysis/__init__.py

COMMAND_MAP = {
    # ... 现有命令 ...
    'my-analysis': 'perf_toolkit.cli.commands.analysis.my_analysis',
}

def register_commands(subparsers):
    # ... 现有命令注册 ...
    
    # my-analysis
    p = subparsers.add_parser('my-analysis', help='My analysis command')
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--param", type=int, default=10, help="My param")
    # ... 其他参数 ...


def get_command_handler(command_name: str):
    # ...
    handler_map = {
        # ... 现有映射 ...
        'my-analysis': 'cmd_my_analysis',
    }
    # ...
```

---

## 9. 接口验证清单

新增 CLI 命令时必须检查：

- [ ] 使用 `@command` 装饰器包装处理函数
- [ ] 返回 `BaseOutput` 的子类实例
- [ ] 包含 `_risk` 字段（RiskInfo）
- [ ] 在 `commands/analysis/__init__.py` 或 `commands/composite/__init__.py` 注册
- [ ] 如果返回 `action_required=true`，确保通过 builder 记录到 Trace
- [ ] Composite 命令通过 `AnalysisFacade` 调用，不直接调用 `@command` 装饰的函数
- [ ] 文档更新（SKILL.md, references/tools.md）

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-03-03 | 初始版本，定义 CLI Layer 完整接口规范 |
