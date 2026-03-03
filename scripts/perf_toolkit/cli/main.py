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


def register_trace_commands(subparsers):
    """
    注册 trace 子命令组
    C 实现
    """
    from .commands.trace.init import register_init_parser
    from .commands.trace.add import register_add_parser
    from .commands.trace.timeline import register_timeline_parser
    from .commands.trace.issues import register_issues_parser
    from .commands.trace.complete import register_complete_parser
    from .commands.trace.reopen import register_reopen_parser
    from .commands.trace.finalize import register_finalize_parser
    from .commands.trace.export import register_export_parser
    from .commands.trace.audit import register_audit_parser
    
    trace_parser = subparsers.add_parser('trace', help='Tracing commands')
    trace_sub = trace_parser.add_subparsers(dest='trace_cmd')
    
    # 注册 9 个子命令
    register_init_parser(trace_sub)
    register_add_parser(trace_sub)
    register_timeline_parser(trace_sub)
    register_issues_parser(trace_sub)
    register_complete_parser(trace_sub)
    register_reopen_parser(trace_sub)
    register_finalize_parser(trace_sub)
    register_export_parser(trace_sub)
    register_audit_parser(trace_sub)
    
    return trace_parser


def register_env_commands(subparsers):
    """
    注册环境管理命令
    C 实现
    """
    from .commands.env.init import register_init_parser
    from .commands.env.use import register_use_parser
    from .commands.env.list import register_list_parser
    from .commands.env.status import register_status_parser
    
    register_init_parser(subparsers)
    register_use_parser(subparsers)
    register_list_parser(subparsers)
    register_status_parser(subparsers)


def handle_trace_command(args):
    """
    处理 trace 子命令
    C 实现
    """
    if not args.trace_cmd:
        # 显示 trace 帮助
        return
    
    handlers = {
        'init': 'perf_toolkit.cli.commands.trace.init',
        'add': 'perf_toolkit.cli.commands.trace.add',
        'timeline': 'perf_toolkit.cli.commands.trace.timeline',
        'issues': 'perf_toolkit.cli.commands.trace.issues',
        'complete': 'perf_toolkit.cli.commands.trace.complete',
        'reopen': 'perf_toolkit.cli.commands.trace.reopen',
        'finalize': 'perf_toolkit.cli.commands.trace.finalize',
        'export': 'perf_toolkit.cli.commands.trace.export',
        'audit': 'perf_toolkit.cli.commands.trace.audit',
    }
    
    module_path = handlers.get(args.trace_cmd)
    if module_path:
        import importlib
        module = importlib.import_module(module_path)
        handler_name = f'cmd_doc_{args.trace_cmd}'
        handler = getattr(module, handler_name)
        handler(args)


def handle_env_command(args):
    """
    处理环境命令
    C 实现
    """
    handlers = {
        'init': ('perf_toolkit.cli.commands.env.init', 'cmd_init'),
        'use': ('perf_toolkit.cli.commands.env.use', 'cmd_use'),
        'list': ('perf_toolkit.cli.commands.env.list', 'cmd_list'),
        'status': ('perf_toolkit.cli.commands.env.status', 'cmd_status'),
    }
    
    module_path, func_name = handlers.get(args.command)
    import importlib
    module = importlib.import_module(module_path)
    handler = getattr(module, func_name)
    
    # 部分命令需要 args 参数
    if args.command in ['init', 'use']:
        handler(args)
    else:
        handler()


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
    from .commands.analysis import register_commands as register_analysis_commands
    register_analysis_commands(subparsers)
    
    # =====================================================================
    # B 负责注册组合命令 (2个)
    # =====================================================================
    from .commands.composite import register_commands as register_composite_commands
    register_composite_commands(subparsers)
    
    # =====================================================================
    # C 负责注册 trace 命令
    # =====================================================================
    register_trace_commands(subparsers)
    
    # =====================================================================
    # C 负责注册环境命令
    # =====================================================================
    register_env_commands(subparsers)
    
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
    # TODO: B 填充具体命令映射
    # commands = {
    #     # Analysis commands (B)
    #     "get-hotspots": cmd_get_hotspots,
    #     "find-callers": cmd_find_callers,
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
    
    # C 负责处理环境命令（不需要 engine）
    if args.command in ['init', 'use', 'list', 'status']:
        handle_env_command(args)
        return
    
    # C 负责处理 Trace 子命令
    if args.command == 'trace':
        handle_trace_command(args)
        return
    
    # B 负责处理分析和组合命令（需要 engine）
    analysis_commands = ['get-hotspots', 'find-callers', 'detect-anomalies', 
                         'cluster-paths', 'analyze-core-distribution', 'get-comm-top']
    composite_commands = ['sys-audit', 'bottleneck-trace']
    
    if args.command in analysis_commands or args.command in composite_commands:
        try:
            if args.command in analysis_commands:
                from .commands.analysis import get_command_handler
            else:
                from .commands.composite import get_command_handler
            
            handler = get_command_handler(args.command)
            freq = getattr(args, 'freq', 19)
            engine = PerfExpertEngine(args.data, freq=freq)
            
            # 装饰器会处理 builder 和 samples 的创建
            handler(engine, args)
        except ValueError as e:
            print(f"Command error: {e}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            raise
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        parser.print_help()


if __name__ == "__main__":
    main()
