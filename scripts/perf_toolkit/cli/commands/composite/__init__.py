#!/usr/bin/env python3
"""
Composite 命令注册模块

注册 2 个组合命令：
- sys-audit
- bottleneck-trace
"""

from typing import Dict, Callable


COMMAND_MAP: Dict[str, str] = {
    'sys-audit': 'perf_toolkit.cli.commands.composite.sys_audit',
    'bottleneck-trace': 'perf_toolkit.cli.commands.composite.bottleneck_trace',
}


def get_command_handler(command_name: str) -> Callable:
    """获取命令处理函数"""
    module_path = COMMAND_MAP.get(command_name)
    if not module_path:
        raise ValueError(f"Unknown command: {command_name}")
    
    module = __import__(module_path, fromlist=[''])
    
    handler_map = {
        'sys-audit': 'cmd_sys_audit',
        'bottleneck-trace': 'cmd_bottleneck_trace',
    }
    
    handler_name = handler_map[command_name]
    return getattr(module, handler_name)


def register_commands(subparsers):
    """注册组合命令"""
    
    # sys-audit
    p = subparsers.add_parser('sys-audit',
                              help="[Composite] System audit - auto orchestrate analysis tools")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--top-n", "--limit", type=int, default=20,
                   help="Number of top process groups")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")
    
    # bottleneck-trace
    p = subparsers.add_parser('bottleneck-trace',
                              help="[Composite] Bottleneck trace - deep analysis of CPU bottlenecks")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--comm", type=str, help="Target process name")
    p.add_argument("--pid", type=int, default=None, help="Target process PID (optional)")
    p.add_argument("--top-n", "--limit", type=int, default=3,
                   help="Number of top paths to show in bidirectional view (rest aggregated)")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")
    p.add_argument("--detect-hot-locks", action="store_true",
                   help="Enable hot lock detection")
    p.add_argument("--lock-config", type=str, default=None,
                   help="Path to lock config file (default: ~/.config/shecr/lock-config.yaml)")
