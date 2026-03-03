#!/usr/bin/env python3
"""
命令装饰器 - 与 Trace v2.0 集成

使用方式:
    @command("get-hotspots")
    def cmd_get_hotspots(builder, engine, args, samples):
        # samples 已准备好，trace 自动记录
        ...
        return output  # BaseOutput 子类

自定义过滤参数:
    @command("cluster-paths", filters=["cpu_id", "pid", "comm"])
    def cmd_cluster_paths(builder, engine, args, samples):
        # 只传递这3个过滤参数
        ...
"""

from functools import wraps
from typing import Callable, List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.output_models import BaseOutput
    from ..core import PerfExpertEngine
    from argparse import Namespace


# 命令处理器类型定义
AnalysisCommandHandler = Callable[
    [
        'OutputBuilder',      # 输出构建器（已初始化，含Trace）
        'PerfExpertEngine',   # 数据引擎
        'Namespace',          # 解析后的参数
        List[Dict[str, Any]]  # 过滤后的样本数据
    ],
    Optional['BaseOutput']  # 返回输出对象（BaseOutput子类）
]


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
    # 默认的6个过滤参数
    ALL_FILTERS = ["start_time", "end_time", "cpu_id", "pid", "comm", "comm_regex"]

    def decorator(func: AnalysisCommandHandler) -> AnalysisCommandHandler:
        @wraps(func)
        def wrapper(engine: 'PerfExpertEngine', args: 'Namespace') -> Optional['BaseOutput']:
            from ..core.output_builder import OutputBuilder

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
                return None

            # 6. 质量评估
            builder.assess_quality(samples)

            # 7. 执行业务逻辑，返回 output（必须是 BaseOutput 子类）
            output = func(builder, engine, args, samples)

            # 8. 自动输出（内部会调用 _auto_record_risk_from_output）
            if output is not None:
                builder.print_output(output)

            return output

        return wrapper
    return decorator
