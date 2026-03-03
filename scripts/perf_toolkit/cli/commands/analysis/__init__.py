#!/usr/bin/env python3
"""
Analysis 命令注册模块

注册 6 个分析命令：
- get-hotspots
- find-callers  
- detect-anomalies
- cluster-paths
- analyze-core-distribution
- get-comm-top
"""

from typing import Dict, Callable


# 命令到模块的映射（延迟导入）
COMMAND_MAP: Dict[str, str] = {
    'get-hotspots': 'perf_toolkit.cli.commands.analysis.hotspots',
    'find-callers': 'perf_toolkit.cli.commands.analysis.callers',
    'detect-anomalies': 'perf_toolkit.cli.commands.analysis.anomalies',
    'cluster-paths': 'perf_toolkit.cli.commands.analysis.path_clusters',
    'analyze-core-distribution': 'perf_toolkit.cli.commands.analysis.core_dist',
    'get-comm-top': 'perf_toolkit.cli.commands.analysis.comm_top',
}


def get_command_handler(command_name: str) -> Callable:
    """获取命令处理函数（延迟导入）"""
    module_path = COMMAND_MAP.get(command_name)
    if not module_path:
        raise ValueError(f"Unknown command: {command_name}")
    
    # 动态导入
    module = __import__(module_path, fromlist=[''])
    
    # 命令名到函数名的映射
    handler_map = {
        'get-hotspots': 'cmd_get_hotspots',
        'find-callers': 'cmd_trace_attribution',
        'detect-anomalies': 'cmd_detect_anomalies',
        'cluster-paths': 'cmd_cluster_paths',
        'analyze-core-distribution': 'cmd_analyze_core_distribution',
        'get-comm-top': 'cmd_get_comm_top',
    }
    
    handler_name = handler_map[command_name]
    return getattr(module, handler_name)


def register_commands(subparsers):
    """
    注册所有分析命令参数
    
    Args:
        subparsers: argparse subparsers 对象
    """
    # get-hotspots
    p = subparsers.add_parser('get-hotspots',
                              help="Extract hotspot function rankings by self/inclusive time")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz for raw perf format (default: 19)")
    p.add_argument("--sort-by", choices=['inclusive', 'self'], default='inclusive',
                   help="Sort by 'inclusive' or 'self'")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--top-n", "--limit", type=int, default=10, help="Number of top hotspots")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")
    p.add_argument("--pid", type=int, help="Filter by process ID")
    p.add_argument("--comm", type=str, help="Filter by process name")
    p.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # find-callers
    p = subparsers.add_parser('find-callers',
                              help="Find and analyze callers of a specific function")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--target", metavar="FUNC", help="Target function name to trace")
    p.add_argument("--auto-target", action="store_true",
                   help="Automatically trace top N hotspot functions")
    p.add_argument("--top-n", "--limit", type=int, default=10, help="Number of top results")
    p.add_argument("--min-ratio", type=float, default=0.5, metavar="PERCENT",
                   dest="min_ratio", help="Minimum ratio %% of total samples")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")
    p.add_argument("--pid", type=int, help="Filter by process ID")
    p.add_argument("--comm", type=str, help="Filter by process name")
    p.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # detect-anomalies
    p = subparsers.add_parser('detect-anomalies',
                              help="Detect CPU utilization anomalies")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--window-size", type=float, default=1.0, metavar="SECONDS",
                   help="Time window size in seconds")
    p.add_argument("--spike-threshold", type=float, default=0.5, metavar="RATIO",
                   help="Utilization change threshold for spike detection")
    p.add_argument("--min-utilization", type=float, default=0.3, metavar="RATIO",
                   help="Minimum utilization threshold")
    p.add_argument("--cpu-id", type=int, help="Analyze specific CPU only")
    p.add_argument("--top-n", "--limit", type=int, default=10, help="Top N anomalies")
    p.add_argument("--export-mode", action="store_true",
                   help="Export all window data")
    p.add_argument("--export-samples", action="store_true",
                   help="Include detailed sample data")
    p.add_argument("--detect-in-export", action="store_true",
                   help="Detect anomalies in export mode")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")

    # cluster-paths
    p = subparsers.add_parser('cluster-paths',
                              help="Cluster samples by common call path prefixes")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--min-depth", type=int, default=2,
                   help="Minimum common prefix depth")
    p.add_argument("--min-samples", type=int, default=5,
                   help="Minimum samples to form a cluster")
    p.add_argument("--top-n", "--limit", type=int, default=10,
                   help="Number of top clusters")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--pid", type=int, help="Filter by process ID")
    p.add_argument("--comm", type=str, help="Filter by process name")
    p.add_argument("--comm-regex", type=str, help="Filter by process name regex")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")

    # analyze-core-distribution
    p = subparsers.add_parser('analyze-core-distribution',
                              help="Analyze per-core CPU utilization")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--pid", type=int, help="Filter by process ID")
    p.add_argument("--comm", type=str, help="Filter by process name")
    p.add_argument("--comm-regex", type=str, help="Filter by process name regex")
    p.add_argument("--top-n", "--limit", type=int, default=10,
                   help="Number of top saturated cores")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")

    # get-comm-top
    p = subparsers.add_parser('get-comm-top',
                              help="Get top N comm groups by aggregated CPU")
    p.add_argument("--data", required=True, help="Path to perf script output file")
    p.add_argument("--freq", type=int, default=19, metavar="HZ",
                   help="Sampling frequency in Hz")
    p.add_argument("--top-n", "--limit", type=int, default=10,
                   help="Number of top comm groups")
    p.add_argument("--sort-by-density", action="store_true",
                   help="Sort by density index")
    p.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p.add_argument("--comm-regex", type=str, help="Filter by process name regex")
    p.add_argument("--start-time", type=str, help="Filter samples after this time")
    p.add_argument("--end-time", type=str, help="Filter samples before this time")
    p.add_argument("--include-metrics", action="store_true",
                   help="Include enhanced metrics (CV, Monopoly, SpawnRate, ImpactScore)")
