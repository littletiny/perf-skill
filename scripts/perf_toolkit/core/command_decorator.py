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
            from .output_builder import OutputBuilder

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
