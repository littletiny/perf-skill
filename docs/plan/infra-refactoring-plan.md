# CLI 基础设施重构执行文档（人员 A）

> 角色: **基础设施负责人**  
> 工期: **Day 1**  
> 目标: 搭建 CLI 层骨架，为 B/C 提供基础设施

---

## 执行检查清单

- [ ] Task A1: 创建目录结构
- [ ] Task A2: 迁移 `@command` 装饰器
- [ ] Task A3: 迁移 `OutputBuilder`
- [ ] Task A4: 创建 `cli/main.py` 框架
- [ ] Task A5: 更新 `shecr.py`
- [ ] Task A6: 更新 `core/__init__.py`

---

## Task A1: 创建目录结构

### 执行命令

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts/perf_toolkit

# 创建目录结构
mkdir -p cli/commands/analysis
mkdir -p cli/commands/composite
mkdir -p cli/commands/trace
mkdir -p cli/commands/env

# 创建 __init__.py 文件
touch cli/__init__.py
touch cli/commands/__init__.py
touch cli/commands/analysis/__init__.py
touch cli/commands/composite/__init__.py
touch cli/commands/trace/__init__.py
touch cli/commands/env/__init__.py
```

### 验证

```bash
ls -la cli/
ls -la cli/commands/
```

预期输出结构:
```
cli/
├── __init__.py
├── decorators.py      (Task A2 创建)
├── builders.py        (Task A3 创建)
├── main.py            (Task A4 创建)
├── env.py             (C 负责)
└── commands/
    ├── __init__.py
    ├── analysis/
    │   └── __init__.py
    ├── composite/
    │   └── __init__.py
    ├── trace/
    │   └── __init__.py
    └── env/
        └── __init__.py
```

---

## Task A2: 迁移 @command 装饰器

### 创建 `cli/decorators.py`

**文件内容**（从 `core/command_decorator.py` 修改 import 路径）:

```python
#!/usr/bin/env python3
"""
极简命令装饰器 - 与 Trace v2.0 集成

使用方式:
    @command("get-hotspots")
    def cmd_get_hotspots(builder, engine, args, samples):
        # samples 已准备好，trace 自动记录
        ...
        return output

自定义过滤参数:
    @command("cluster-comm", filters=["start_time", "end_time", "cpu_id"])
    def cmd_cluster_comm(builder, engine, args, samples):
        # 只传递了这3个过滤参数
        ...
"""

from functools import wraps


def command(name: str, filters: list = None):
    """
    命令装饰器 - 统一处理样板代码和 Trace 记录

    Args:
        name: 命令名称（自动传给 builder.begin_command）
        filters: 过滤参数列表，None表示使用全部6个
    """
    # 默认的6个过滤参数
    ALL_FILTERS = ["start_time", "end_time", "cpu_id", "pid", "comm", "comm_regex"]

    def decorator(func):
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

            # 5. 空检查（自动处理输出，传递 filters 用于错误信息）
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

### 验证

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts
python3 -c "from perf_toolkit.cli.decorators import command; print('decorators.py OK')"
```

---

## Task A3: 迁移 OutputBuilder

### 创建 `cli/builders.py`

**文件内容**（从 `core/output_builder.py` 修改 import 路径）:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - 基于统一数据模型的输出构建器

与 output_models.py 配合使用，提供：
- 类型安全的输出构建
- 统一的数据结构管理
- 自动转换到 JSON
- Trace 自动记录 (v2.0)
"""

import os
import sys
from typing import List, Dict, Optional, Any, Type, TypeVar, Generic
from dataclasses import dataclass

# 注意: import 路径从 core 改为相对导入
from ..core.output_models import (
    RiskInfo, TimeRange, BaseSummary, BaseOutput,
    ProcessItem, CommGroupItem, HotspotItem, ClusterItem,
    ProcessSummary, CommGroupSummary, HotspotSummary, ClusterSummary,
    ProcessTopOutput, CommTopOutput, HotspotsOutput, ClustersOutput,
    ClusterCommOutput,
    # V2 新增模型
    BottleneckData, BottleneckSummary, BottleneckOutput,
    CPUUsageData, CPUUsageSummary, CPUUsageOutput,
    AnomalyItem, AnomalySummary, AnomaliesOutput,
    WindowItem, WindowSummary, WindowsOutput,
    AttributionItem, AttributionSummary, AttributionsOutput,
    TraceItem, TracesSummary, TracesOutput,
    PathClusterItem, PathClusterSummary, PathClustersOutput,
    ProcessVarietyItem, ProcessVarietySummary, ProcessVarietyOutput,
    CoreItem, CoreDistributionSummary, CoreDistributionOutput,
    # Dict Refactor 新增模型
    TraceSummary, ErrorData, QualityMetrics, IssueCategories,
)
from ..core.output_adapter import OutputAdapter, CompactOutputAdapter
from ..core.text_output_adapter import TextOutputAdapter
from ..core.risk_mixin import RiskAwareOutput
from ..core.format_utils import format_time_range, safe_time_range
from ..core.reliability import assess_data_quality
from ..core.trace import Trace


T = TypeVar('T', bound=BaseOutput)


class OutputBuilder:
    """
    基于统一数据模型的输出构建器 V2

    与 V1 版本的主要区别：
    - 使用 dataclass 定义的数据模型
    - 类型安全的输出构建
    - 通过 OutputAdapter 自动转换为 JSON
    - Trace 自动记录 (v2.0)
    """

    def __init__(self, engine, args, compact: bool = False, text_mode: bool = True):
        """
        初始化输出构建器

        Args:
            engine: PerfExpertEngine 实例
            args: argparse namespace
            compact: 是否使用紧凑模式输出
            text_mode: 是否使用人类可读的文本格式输出（默认True）
        """
        self.engine = engine
        self.args = args
        self.compact = compact
        self.text_mode = text_mode
        if text_mode:
            self.adapter = TextOutputAdapter()
        elif compact:
            self.adapter = CompactOutputAdapter()
        else:
            self.adapter = OutputAdapter()
        self._risk_output = RiskAwareOutput()
        self._quality_level = None
        self._quality_metrics = None
        self._samples = None

        # Trace v2.0 自动记录
        self._trace = None
        self._command_name = None
        self._auto_trace = getattr(args, 'trace', True)  # 默认开启

    # =====================================================================
    # Trace v2.0 - 自动记录 API
    # =====================================================================

    def begin_command(self, command_name: str):
        """
        命令开始时调用，自动初始化 Trace 并记录命令

        Args:
            command_name: 命令名称，如 "get-comm-top"
        """
        if not self._auto_trace:
            return

        self._command_name = command_name

        # 构建完整命令字符串
        cmd_parts = [command_name]
        data_file = getattr(self.args, 'data', None)
        if data_file:
            cmd_parts.append(f"--data {data_file}")

        # 添加其他常见参数
        for attr in ['comm', 'pid', 'cpu_id', 'start_time', 'end_time', 'top_n']:
            val = getattr(self.args, attr, None)
            if val is not None:
                cmd_parts.append(f"--{attr.replace('_', '-')} {val}")

        full_command = " ".join(cmd_parts)

        # 初始化 Trace
        try:
            self._trace = Trace()
            # 如果文档不存在，自动初始化
            if not self._trace.data.get('data_file') and data_file:
                self._trace.init(data_file)

            self._trace.begin_command(full_command)
        except Exception:
            # 自动记录失败不应影响主流程
            self._trace = None

    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """
        记录发现的风险，自动创建 issue

        Args:
            level: critical/warning/info
            desc: 风险描述
            hint: 建议操作

        Returns:
            issue_id: 创建的 issue ID（或空字符串）
        """
        if not self._auto_trace or not self._trace:
            return ""

        try:
            return self._trace.record_risk(level, desc, hint)
        except Exception:
            return ""

    def record_resolution(self, issue_id: str, result: str):
        """
        标记 issue 已解决

        Args:
            issue_id: 要解决的 issue ID
            result: 分析结果/结论
        """
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.record_resolution(issue_id, result)
        except Exception:
            pass

    def auto_resolve_by_command(self, comm: str = None, result: str = ""):
        """
        根据命令参数自动匹配并解决 issue

        例如: cluster-symbols --comm netstat 会自动匹配 netstat 相关的 open issue

        Args:
            comm: 进程名，用于匹配
            result: 分析结果
        """
        if not self._auto_trace or not self._trace:
            return

        try:
            # 从 args 获取 comm
            if comm is None:
                comm = getattr(self.args, 'comm', None)

            if not comm:
                return

            # 查找匹配的 open issue
            for issue_id, issue in self._trace.data['issues'].items():
                if issue['status'] == 'open' and comm in issue['desc']:
                    self._trace.record_resolution(issue_id, result)
                    break
        except Exception:
            pass

    def record_info(self, message: str):
        """记录一般信息"""
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.record_info(message)
        except Exception:
            pass

    def end_command(self):
        """命令结束时调用，保存 Trace"""
        if not self._auto_trace or not self._trace:
            return

        try:
            self._trace.end_command()
        except Exception:
            pass

    def get_trace_summary(self) -> TraceSummary:
        """获取 Trace 摘要（返回 TraceSummary dataclass）"""
        if not self._trace:
            return TraceSummary(enabled=False)

        summary = self._trace.get_summary()
        return TraceSummary(
            enabled=True,
            total_commands=summary.total_commands,
            open_issues=summary.open_issues,
            resolved_issues=summary.resolved_issues,
            can_finalize=summary.can_finalize
        )

    # =====================================================================
    # 数据质量评估（与 V1 兼容）
    # =====================================================================

    def check_empty_samples(self, samples: List[Dict], filters: Dict = None) -> bool:
        """检查样本是否为空"""
        if samples:
            self._samples = samples
            return False

        # 构建错误响应（使用 ErrorData dataclass）
        error_data = ErrorData(
            error="No samples found",
            message="未找到匹配过滤条件的样本数据",
            recovery_hint="检查过滤条件或扩大时间范围"
        )

        # 创建风险输出
        risk_output = RiskAwareOutput()
        risk_output.add_risk(
            "warning",
            "未找到样本数据",
            "[必须] 添加到 Trace: shecr trace add --desc '未找到样本数据' --hint '检查过滤条件'",
            patterns=["NO_SAMPLES"]
        )

        result = risk_output.build({
            "error": error_data.error,
            "message": error_data.message,
            "recovery_hint": error_data.recovery_hint,
            "time_range": format_time_range(
                getattr(self.args, 'start_time', None),
                getattr(self.args, 'end_time', None)
            ),
            "available_range": self.engine.get_time_range(),
            "filters": filters or {}
        })
        self.print_json(result)
        return True

    def assess_quality(self, samples: List[Dict] = None,
                       early_return: bool = False) -> Optional[str]:
        """评估数据质量（使用 QualityMetrics dataclass）"""
        if samples is None:
            samples = self._samples

        if not samples:
            self._quality_level = "CRITICAL"
            self._quality_metrics = QualityMetrics()
            return self._quality_level if not early_return else False

        duration = samples[-1].ts - samples[0].ts if len(samples) > 1 else 0
        record_count = len(samples)

        total_weight, _ = self.engine.get_total_core_per_sec(samples)
        quality_level, warning_msg, metrics = assess_data_quality(
            duration, total_weight=total_weight, record_count=record_count
        )

        # 使用 QualityMetrics dataclass
        self._quality_level = quality_level
        self._quality_metrics = QualityMetrics(
            total_samples=getattr(metrics, 'record_count', 0),
            time_range_seconds=getattr(metrics, 'duration_sec', 0.0),
            cpu_count=getattr(self.args, 'cpu_id', 0) or 0
        )

        # 早期返回处理
        if early_return:
            if quality_level == "CRITICAL":
                # 添加数据质量风险
                risk_output = RiskAwareOutput()
                risk_output.add_risk(
                    "critical",
                    "数据质量不足！分析结果完全不可信",
                    "[必须] 添加到 Trace: shecr trace add --desc '数据质量不足！分析结果完全不可信' --hint '使用更长的采样时间重新采集数据'",
                    patterns=["CRITICAL_DATA_QUALITY"]
                )

                result = risk_output.build({
                    "data_quality": {
                        "level": self._quality_metrics.level,
                        "warning": self._quality_metrics.warning,
                        "total_samples": self._quality_metrics.total_samples,
                        "time_range_seconds": self._quality_metrics.time_range_seconds,
                        "cpu_count": self._quality_metrics.cpu_count,
                    },
                    "error": "Insufficient data quality for analysis"
                })
                self.print_json(result)
                return True
            else:
                # 数据质量良好，不提前返回
                return False

        return quality_level

    # =====================================================================
    # 输出方法
    # =====================================================================

    def print_issue_overflow_warning(self):
        """
        检查 pending issues 并输出 overflow warning

        触发条件: open_issues >= 2
        输出格式: [!] {总数}问题未闭环: {分类统计} | {警告文案} | 现在执行: trace issues
        """
        try:
            # 如果没有 trace 实例，创建一个临时的
            trace = self._trace if self._trace else Trace()
            open_issues = trace.get_open_issues()

            if len(open_issues) < 2:
                return

            # 分类统计
            categories = self._categorize_issues(open_issues)
            category_str = ", ".join([f"{cat}x{count}" for cat, count in categories.items()]) if categories else "未知类型"

            # 固定警告文案
            warning = "⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状"

            # 输出
            print(f"[!] {len(open_issues)}问题未闭环: {category_str} | {warning} | 现在执行: trace issues")
            print()  # 空行分割
        except Exception:
            # 提示失败不应影响主流程
            pass

    def _categorize_issues(self, issues: List[Dict]) -> IssueCategories:
        """
        对 issues 进行分类统计（返回 IssueCategories dataclass）

        分类规则:
        - 内核异常: desc 包含 "内核" 或 "kernel"
        - 锁竞争: desc 包含 "锁竞争" 或 "LOCK_CONTENTION"
        - 进程风暴: desc 包含 "进程风暴" 或 "PROCESS_STORM"
        """
        categories = IssueCategories()

        for issue in issues:
            desc = issue.get('desc', '').lower()

            if '内核' in desc or 'kernel' in desc:
                categories.kernel_anomaly += 1
            elif '锁竞争' in desc or 'lock_contention' in desc:
                categories.lock_contention += 1
            elif '进程风暴' in desc or 'process_storm' in desc:
                categories.process_storm += 1

        return categories

    def _auto_record_risk_from_output(self, output: BaseOutput):
        """
        自动从 output 中提取 risk 信息并记录到 Trace

        支持两种 risk 格式:
        - output.risk: RiskInfo 对象 (V2 模型)
        - output._risk: dict (兼容 RiskMixin)
        """
        if not self._auto_trace:
            return

        # 确保 trace 已初始化（即使 begin_command 未被调用）
        if not self._trace:
            try:
                self._trace = Trace()
                data_file = getattr(self.args, 'data', None)
                if data_file and not self._trace.data.get('data_file'):
                    self._trace.init(data_file)
            except Exception:
                return

        try:
            risk = None

            # 尝试获取 risk 字段 (V2 模型)
            if hasattr(output, 'risk') and output.risk:
                risk = output.risk
            # 尝试获取 _risk 字段 (RiskMixin 兼容)
            elif hasattr(output, '_risk') and output._risk:
                risk = output._risk

            if not risk:
                return

            # 提取 risk 信息
            level = "warning"
            message = ""
            hint = ""

            if isinstance(risk, RiskInfo):
                level = risk.level
                message = risk.message
                hint = risk.hint
            elif isinstance(risk, dict):
                level = risk.get('level', 'warning')
                message = risk.get('message', '')
                hint = risk.get('hint', '')

            # 只记录 critical 和 warning 级别的 risk
            if level in ['critical', 'warning'] and message:
                # 生成简洁的 hint（如果 hint 太长或为空）
                if not hint:
                    hint = self._generate_hint_from_message(message)

                self.record_risk(level, message, hint)

        except Exception:
            # 自动记录失败不应影响主流程
            pass

    def _generate_hint_from_message(self, message: str) -> str:
        """从 message 生成默认 hint"""
        # 简单启发式：根据消息内容推断 hint
        message_lower = message.lower()
        if '内核' in message_lower or 'kernel' in message_lower:
            return "cluster-symbols --comm $COMM"
        elif '锁' in message_lower or 'lock' in message_lower or 'mutex' in message_lower:
            return "find-callers --target $FUNC"
        elif '进程' in message_lower or 'process' in message_lower:
            return "count-process-variety --comm $COMM"
        elif 'cpu' in message_lower or '瓶颈' in message_lower:
            return "check-cpu-bottleneck"
        else:
            return "trace issues"

    def print_output(self, output: BaseOutput, auto_end: bool = True):
        """
        打印输出对象

        Args:
            output: 继承自 BaseOutput 的输出对象
            auto_end: 是否自动结束命令记录（默认True）
        """
        # 自动记录 risk 到 Trace（全自动化）
        self._auto_record_risk_from_output(output)

        if self.text_mode:
            text_str = self.adapter.format_output(output)
            print(text_str)
        else:
            json_str = self.adapter.to_json(output)
            print(json_str)

        # 自动结束命令记录
        if auto_end:
            self.end_command()

    def print_json(self, data: Dict):
        """打印字典数据（兼容 V1，内部直接使用 dict，仅在输出时转 JSON）"""
        # 注意：这里只在最终输出时使用 JSON，内部处理均使用 Dict
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))

    def to_dict(self, output: BaseOutput) -> Dict:
        """将输出对象转换为字典"""
        return self.adapter.to_dict(output)


def create_risk_info(level: str, message: str, hint: str = "") -> RiskInfo:
    """创建 RiskInfo 对象的便捷函数"""
    return RiskInfo(
        level=level,
        message=message,
        hint=hint
    )
```

### 验证

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts
python3 -c "from perf_toolkit.cli.builders import OutputBuilder; print('builders.py OK')"
```

---

## Task A4: 创建 cli/main.py 框架

### 创建 `cli/main.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 主入口 - 参数解析与命令路由

B 和 C 将在此注册自己的命令
"""

import argparse
import sys
from ..core import PerfExpertEngine


class HelpOnErrorParser(argparse.ArgumentParser):
    """Custom parser that prints full help on error"""
    def error(self, message):
        import sys
        self.print_help(sys.stderr)
        self.exit(2, f'\n{self.prog}: error: {message}\n')


def create_parser() -> argparse.ArgumentParser:
    """
    创建参数解析器 - A 提供框架，B/C 填充子命令
    
    Returns:
        配置好的 ArgumentParser 实例
    """
    parser = HelpOnErrorParser(
        description="SHECR Diagnostic Toolkit",
        epilog="""Usage Examples:
  # Analyze hotspots in a specific process
  shecr get-hotspots --data perf.data.txt --comm myapp --top-n 20

  # Analyze core distribution (includes single-core saturation detection)
  shecr analyze-core-distribution --data perf.data.txt

  # Find callers of a specific function
  shecr find-callers --data perf.data.txt --target pthread_mutex_lock

  # Detect anomalies in a time window
  shecr detect-anomalies --data perf.data.txt --window-size 1.0

  # System audit - comprehensive analysis with auto noise reduction
  shecr sys-audit --data perf.data.txt
  
  # Bottleneck trace - deep analysis of bottleneck processes
  shecr bottleneck-trace --data perf.data.txt --comm myapp

Use '<command> --help' for detailed help on each subcommand."""
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # =====================================================================
    # B 负责注册分析命令 (6个)
    # =====================================================================
    # register_analysis_commands(subparsers)  # B 在 commands/analysis/__init__.py 实现
    
    # =====================================================================
    # C 负责注册 trace 命令
    # =====================================================================
    # register_trace_commands(subparsers)  # C 在 commands/trace/__init__.py 实现
    
    # =====================================================================
    # C 负责注册环境命令
    # =====================================================================
    # register_env_commands(subparsers)  # C 在 commands/env/__init__.py 实现
    
    return parser


def route_command(command_name: str, engine: PerfExpertEngine, args):
    """
    命令路由 - B/C 填充具体路由逻辑
    
    Args:
        command_name: 命令名称
        engine: PerfExpertEngine 实例
        args: argparse.Namespace
        
    Note:
        B 负责填充 analysis 命令路由
        C 负责填充 trace/env 命令路由
    """
    # TODO: B 和 C 填充具体命令映射
    # commands = {
    #     # Analysis commands (B)
    #     "get-hotspots": cmd_get_hotspots,
    #     "find-callers": cmd_find_callers,
    #     ...
    #     # Trace commands (C)
    #     "trace": handle_trace_command,
    #     # Env commands (C)
    #     "init": cmd_init,
    #     ...
    # }
    # 
    # if command_name in commands:
    #     commands[command_name](engine, args)
    # else:
    #     print(f"Unknown command: {command_name}", file=sys.stderr)
    pass


def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # TODO: C 负责处理环境命令（不需要 engine）
    # if args.command in ['init', 'use', 'list', 'status']:
    #     handle_env_command(args)
    #     return
    
    # TODO: C 负责处理 Trace 子命令
    # if args.command == 'trace':
    #     handle_trace_command(args)
    #     return
    
    # TODO: B 负责处理分析命令（需要 engine）
    # freq = getattr(args, 'freq', 19)
    # engine = PerfExpertEngine(args.data, freq=freq)
    # route_command(args.command, engine, args)
    
    # 临时：显示提示信息
    print(f"Command '{args.command}' registered but not implemented yet.")
    print("Waiting for B/C to fill in the command handlers.")


if __name__ == "__main__":
    main()
```

### 验证

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts
python3 -c "from perf_toolkit.cli.main import create_parser, main; print('main.py OK')"
```

---

## Task A5: 更新 shecr.py

### 备份原文件并重写

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts
cp shecr.py shecr.py.bak
```

### 重写 `shecr.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHECR Diagnostic Toolkit - CLI Entry Point

This is the unified entry point for the perf toolkit.
All CLI logic has been moved to perf_toolkit/cli/ directory.

Architecture:
  scripts/perf_toolkit/
  ├── cli/
  │   ├── decorators.py      - @command decorator
  │   ├── builders.py        - OutputBuilder
  │   ├── main.py            - Argument parsing & routing
  │   └── commands/
  │       ├── analysis/      - Analysis commands (B负责)
  │       ├── composite/     - Composite commands (B负责)
  │       ├── trace/         - Trace commands (C负责)
  │       └── env/           - Environment commands (C负责)
"""

import sys
import os

# Add perf_toolkit to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from perf_toolkit.cli.main import main

if __name__ == "__main__":
    main()
```

### 验证

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts
python3 shecr.py --help
```

预期输出:
```
usage: shecr.py [-h] ...

SHECR Diagnostic Toolkit

optional arguments:
  -h, --help  show this help message and exit

Use '<command> --help' for detailed help on each subcommand.
```

---

## Task A6: 更新 core/__init__.py

### 修改内容

保持 `command` 和 `OutputBuilder` 的导出，但改为从 cli 导入（为了向后兼容，暂时保留）:

```python
# 保留向后兼容的导入（重构完成后可删除）
from ..cli.builders import OutputBuilder, create_risk_info
from ..cli.decorators import command
```

**注意**: 先不要删除原文件 `core/command_decorator.py` 和 `core/output_builder.py`，
等 B/C 完成迁移后再删除（避免破坏现有代码）。

---

## Day 1 交付标准

### 验证命令

```bash
cd /home/tiny/.config/agents/skills/perf-hunter/scripts

# 1. 验证 import 成功
python3 -c "from perf_toolkit.cli import decorators, builders; print('OK')"

# 2. 验证 shecr.py 能运行
python3 shecr.py --help

# 3. 验证目录结构
ls -la perf_toolkit/cli/
```

### 必须通过的检查

- [ ] `python3 -c "from perf_toolkit.cli.decorators import command"` 不报错
- [ ] `python3 -c "from perf_toolkit.cli.builders import OutputBuilder"` 不报错
- [ ] `python3 shecr.py --help` 能运行（可能只有 help）
- [ ] 目录结构完整（包含所有 `__init__.py`）

---

## 提供给 B/C 的接口约定

### cli/decorators.py

```python
from functools import wraps

def command(name: str, filters: list = None):
    """
    命令装饰器 - 统一处理样板代码
    
    Args:
        name: 命令名称（如 'get-hotspots'）
        filters: 过滤参数列表，None 表示使用全部 6 个
    
    Usage:
        @command("get-hotspots")
        def cmd_get_hotspots(builder, engine, args, samples):
            ...
    """
    ...
```

### cli/builders.py

```python
from perf_toolkit.core.engine import PerfExpertEngine

class OutputBuilder:
    """
    输出构建器 - 基于统一数据模型
    
    Args:
        engine: PerfExpertEngine 实例
        args: argparse namespace
        compact: 是否使用紧凑模式
        text_mode: 是否使用文本格式（默认 True）
    """
    def __init__(self, engine: PerfExpertEngine, args, compact: bool = False, text_mode: bool = True):
        ...
    
    def begin_command(self, command_name: str):
        """命令开始时调用"""
        ...
    
    def check_empty_samples(self, samples, filters: dict = None) -> bool:
        """检查空样本，如为空则自动输出并返回 True"""
        ...
    
    def assess_quality(self, samples):
        """评估数据质量"""
        ...
    
    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """记录风险，返回 issue_id"""
        ...
    
    def print_output(self, output):
        """输出结果（自动选择 JSON 或文本格式）"""
        ...
```

### cli/main.py（框架）

```python
def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器 - A 提供框架，B/C 填充子命令"""
    ...

def route_command(command_name: str, engine: PerfExpertEngine, args):
    """
    命令路由 - B/C 填充具体路由逻辑
    
    Args:
        command_name: 命令名称
        engine: PerfExpertEngine 实例
        args: argparse.Namespace
    """
    ...
```

---

## 下一步（Day 2）

Day 1 完成后，通知 B 和 C 可以开始工作：

1. **B（分析命令负责人）**:
   - 从 `main.py` 中提取分析命令参数定义
   - 迁移 6 个分析命令到 `cli/commands/analysis/`
   - 清理 `analysis/*.py` 中的 CLI 代码

2. **C（Trace & 环境命令负责人）**:
   - 从 `core/trace.py` 提取 9 个 Trace 命令
   - 迁移 `shecr_wrap.py` 功能到 `cli/commands/env/`
   - 精简 `core/trace.py`

---

## Git 提交建议

```bash
cd /home/tiny/.config/agents/skills/perf-hunter

# 检查变更
git status

# 添加新文件
git add scripts/perf_toolkit/cli/
git add scripts/shecr.py
git add docs/infra-refactoring-plan.md

# 提交
git commit -m "feat(cli): Day 1 - 创建 CLI 基础设施框架

- 创建 cli/ 目录结构
- 迁移 @command 装饰器到 cli/decorators.py
- 迁移 OutputBuilder 到 cli/builders.py
- 重写 shecr.py 为简单入口
- 提供 B/C 协作接口

Part of CLI refactoring (Person A - Infrastructure)"
```
