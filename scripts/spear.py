#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Perf Expert Diagnostic Toolkit - Analyze Linux performance data using SPEAR methodology

This is the main entry point for the perf toolkit. It has been refactored into a modular structure:

  scripts/perf_toolkit/
  ├── core/
  │   ├── engine.py          - PerfExpertEngine class and parsing logic
  │   └── reliability.py     - Sample reliability assessment (no freq parameter)
  └── analysis/
      ├── bottleneck.py      - CPU bottleneck detection
      ├── hotspots.py        - Hotspot function analysis
      ├── clusters.py        - Symbol clustering by expert rules
      ├── trace.py           - Call attribution tracing
      ├── anomalies.py       - CPU utilization anomaly detection
      ├── cpu_usage.py       - CPU utilization breakdown
      ├── process_top.py     - Top processes by CPU
      ├── comm_clusters.py   - Cluster by process name
      ├── path_clusters.py   - Cluster by call paths (Trie-based)
      └── process_variety.py - Process storm detection

Key Changes in v2.0:
  - Removed --freq parameter: Reliability is now assessed directly using CPU utilization
    from perf script output, not from sampling frequency
  - Fixed CPU utilization calculation: Uses total core-seconds / duration * 100
  - Modular architecture for better maintainability
"""

import sys
import argparse

# Import core components
from perf_toolkit.core import PerfExpertEngine

# Import analysis modules
from perf_toolkit.analysis.bottleneck import cmd_check_bottleneck, parse_cpu_quota
from perf_toolkit.analysis.hotspots import cmd_get_hotspots
from perf_toolkit.analysis.clusters import cmd_apply_cluster
from perf_toolkit.analysis.trace import cmd_trace_attribution, cmd_find_callers_auto
from perf_toolkit.analysis.anomalies import cmd_detect_anomalies
from perf_toolkit.analysis.cpu_usage import cmd_show_cpu_usage
from perf_toolkit.analysis.process_top import cmd_get_process_top
from perf_toolkit.analysis.comm_clusters import cmd_cluster_comm
from perf_toolkit.analysis.path_clusters import cmd_cluster_paths
from perf_toolkit.analysis.process_variety import cmd_count_process_variety
from perf_toolkit.analysis.core_distribution import cmd_analyze_core_distribution
from perf_toolkit.analysis.comm_top import cmd_get_comm_top

# Import trace commands (v2.0: auto add, manual complete)
from perf_toolkit.core.trace import (
    cmd_doc_init, cmd_doc_add, cmd_doc_complete, cmd_doc_timeline,
    cmd_doc_issues, cmd_doc_finalize, cmd_doc_export
)


class HelpOnErrorParser(argparse.ArgumentParser):
    """Custom parser that prints full help on error"""
    def error(self, message):
        import sys
        self.print_help(sys.stderr)
        self.exit(2, f'\n{self.prog}: error: {message}\n')


def main():
    parser = HelpOnErrorParser(
        description="SPEAR Diagnostic Toolkit",
        epilog="""Usage Examples:
  # Analyze hotspots in a specific process
  spear get-hotspots --data perf.data.txt --comm myapp --top-n 20

  # Check CPU bottleneck with cgroup limit
  spear check-cpu-bottleneck --data perf.data.txt --cpu-limit 0.5c

  # Find callers of a specific function
  spear find-callers --data perf.data.txt --target pthread_mutex_lock

  # Detect anomalies in a time window
  spear detect-anomalies --window-size 1.0

  # Analyze core distribution for load balancing issues
  spear analyze-core-distribution --comm myapp

Input Data Format:
  Supports two formats:
  1. SPEAR format: perf script output processed with CPU utilization values
  2. Raw perf format: standard perf script output (requires --freq parameter)

  Generate raw perf data with:
    perf record -F 19 -a -g -- sleep 30
    perf script > perf.data.txt

Note: For raw perf format, use --freq to specify sampling
frequency (default: 19Hz). For SPEAR format, the freq parameter is ignored.

Use '<command> --help' for detailed help on each subcommand."""
    )
    subparsers = parser.add_subparsers(dest="command")

    # check-cpu-bottleneck
    p1 = subparsers.add_parser('check-cpu-bottleneck',
                               help="Determine resource throttling and single-core saturation")
    p1.add_argument("--data", required=True, help="Path to perf script output file")
    p1.add_argument("--cpu-limit", type=parse_cpu_quota, default=0, dest="cpu_limit", metavar="LIMIT",
                    help="CPU limit in cores for cgroup environments. Examples: '0.1c' (0.1 core), "
                         "'2c' (2 cores), '0.5' (0.5 cores). Default: 0 (no limit check)")
    p1.add_argument("--threshold", type=float, default=80, metavar="PCT",
                    help="Threshold for single-core saturation detection (default: 80%%). "
                         "A core is considered saturated when its CPU usage exceeds this threshold.")
    p1.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p1.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601 (2024-01-15T10:30:00), datetime (2024-01-15 10:30:00), or date only")
    p1.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # get-hotspots
    p2 = subparsers.add_parser('get-hotspots',
                               help="Extract hotspot function rankings by self/inclusive time")
    p2.add_argument("--data", required=True, help="Path to perf script output file")
    p2.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p2.add_argument("--sort-by", choices=['inclusive', 'self'], default='inclusive',
                    help="Sort by 'inclusive' (total time in call chain) or 'self' (time in function only)")
    p2.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p2.add_argument("--top-n", type=int, default=10, help="Number of top hotspots to display (default: 10)")
    p2.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p2.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")
    p2.add_argument("--pid", type=int, help="Filter by process ID")
    p2.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p2.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # cluster-symbols
    p3 = subparsers.add_parser('cluster-symbols',
                               help="Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)")
    p3.add_argument("--data", required=True, help="Path to perf script output file")
    p3.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p3.add_argument("--custom-rules", metavar="RULES",
                    help="JSON format custom rules. Example: '{\"MyPattern\": [{\"pattern\": \"my_func_.*\", "
                         "\"weight\": 1.0}]}'. Rules are list of {pattern, weight} objects.")
    p3.add_argument("--rules-file", metavar="PATH",
                    help="Path to external rules file (JSON format). "
                         "Rules from file override built-in expert rules but can be overridden by --custom-rules.")
    p3.add_argument("--include-experts", action="store_true", default=True,
                    help="Include built-in expert rules (default: True)")
    p3.add_argument("--no-include-experts", action="store_true",
                    help="Exclude built-in expert rules")
    p3.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p3.add_argument("--top-n", type=int, default=10, help="Number of top clusters to display (default: 10)")
    p3.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p3.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")
    p3.add_argument("--pid", type=int, help="Filter by process ID")
    p3.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p3.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # find-callers
    p4 = subparsers.add_parser('find-callers',
                               help="Find and analyze callers of a specific function or auto-trace top hotspots")
    p4.add_argument("--data", required=True, help="Path to perf script output file")
    p4.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p4.add_argument("--target", metavar="FUNC",
                    help="Target function name to trace. Examples: 'pthread_mutex_lock', "
                         "'sched_yield', 'malloc'. Use with --min-ratio to filter significant callers. "
                         "If not provided, use --auto-target to trace top hotspots automatically")
    p4.add_argument("--auto-target", action="store_true",
                    help="Automatically trace top N hotspot functions")
    p4.add_argument("--top-n", type=int, default=10,
                    help="Number of top results to display (default: 10)")
    p4.add_argument("--min-cpu", type=float, default=3.0, metavar="PERCENT",
                    help="Minimum CPU utilization %% to display a hotspot (default: 3.0%%). "
                         "Hotspots below this threshold are hidden but counted.")
    p4.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p4.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p4.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")
    p4.add_argument("--pid", type=int, help="Filter by process ID")
    p4.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p4.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # detect-anomalies
    p5 = subparsers.add_parser('detect-anomalies',
                               help="Detect CPU utilization anomalies or export window data")
    p5.add_argument("--data", required=True, help="Path to perf script output file")
    p5.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p5.add_argument("--window-size", type=float, default=1.0, metavar="SECONDS",
                    help="Time window size in seconds for sliding window analysis. Smaller windows "
                         "detect rapid changes but may produce more noise. (default: 1.0)")
    p5.add_argument("--spike-threshold", type=float, default=0.5, metavar="RATIO",
                    help="Utilization change threshold for spike detection. A spike is detected when "
                         "CPU utilization changes by this ratio between consecutive windows. "
                         "Range: 0.0-1.0 (default: 0.5 = 50%% change)")
    p5.add_argument("--min-utilization", type=float, default=0.3, metavar="RATIO",
                    help="Minimum utilization to consider as significant. Windows with CPU utilization "
                         "below this threshold are excluded from anomaly detection. "
                         "Range: 0.0-1.0 (default: 0.3 = 30%%)")
    p5.add_argument("--cpu-id", type=int, help="Analyze specific CPU only")
    p5.add_argument("--top-n", type=int, default=10, help="Top N anomalies to report")
    p5.add_argument("--export-mode", action="store_true",
                    help="Export all window data instead of detecting anomalies")
    p5.add_argument("--export-samples", action="store_true",
                    help="Include detailed sample data in export mode")
    p5.add_argument("--detect-in-export", action="store_true",
                    help="Also detect anomalies when in export mode")
    p5.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p5.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # show-cpu-usage
    p8 = subparsers.add_parser('show-cpu-usage',
                               help="Show CPU utilization for OS or specific PID (user/kernel/total)")
    p8.add_argument("--data", required=True, help="Path to perf script output file")
    p8.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p8.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p8.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p8.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # get-process-top
    p9 = subparsers.add_parser('get-process-top',
                               help="Get top N processes by CPU utilization with user/kernel breakdown")
    p9.add_argument("--data", required=True, help="Path to perf script output file")
    p9.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p9.add_argument("--top-n", type=int, default=10, help="Number of top processes to display (default: 10)")
    p9.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p9.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p9.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # cluster-comm
    p10 = subparsers.add_parser('cluster-comm',
                                help="Cluster samples by process name (comm) to analyze process group CPU usage")
    p10.add_argument("--data", required=True, help="Path to perf script output file")
    p10.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p10.add_argument("--top-n", type=int, default=10, help="Number of top comm groups to display (default: 10)")
    p10.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p10.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p10.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # cluster-paths
    p11 = subparsers.add_parser('cluster-paths',
                                help="Cluster samples by common call path prefixes using Trie")
    p11.add_argument("--data", required=True, help="Path to perf script output file")
    p11.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p11.add_argument("--min-depth", type=int, default=2,
                     help="Minimum common prefix depth to form a cluster (default: 2)")
    p11.add_argument("--min-samples", type=int, default=5,
                     help="Minimum samples to form a cluster (default: 5)")
    p11.add_argument("--top-n", type=int, default=10,
                     help="Number of top clusters to display (default: 10)")
    p11.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p11.add_argument("--pid", type=int, help="Filter by process ID")
    p11.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p11.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p11.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p11.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # count-process-variety
    p12 = subparsers.add_parser('count-process-variety',
                                help="Count process variety to detect short-lived process storms")
    p12.add_argument("--data", required=True, help="Path to perf script output file")
    p12.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p12.add_argument("--top-n", type=int, default=20,
                     help="Number of top process names to display (default: 20)")
    p12.add_argument("--storm-pid-threshold", type=int, default=50, metavar="N",
                     help="PID count threshold for process storm detection. A storm is detected when "
                          "the number of unique PIDs for a process name exceeds this threshold. "
                          "Indicates short-lived process creation (fork-bomb style). (default: 50)")
    p12.add_argument("--storm-ratio-threshold", type=float, default=2.0, metavar="RATIO",
                     help="Samples per PID threshold for process storm detection. A storm is also "
                          "detected when samples_per_pid falls below this ratio. Low values indicate "
                          "processes with very short lifetime. (default: 2.0)")
    p12.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p12.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p12.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p12.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p12.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # analyze-core-distribution
    p13 = subparsers.add_parser('analyze-core-distribution',
                                help="Analyze per-core CPU utilization and thread states")
    p13.add_argument("--data", required=True, help="Path to perf script output file")
    p13.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p13.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p13.add_argument("--pid", type=int, help="Filter by process ID")
    p13.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p13.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p13.add_argument("--top-n", type=int, default=10, help="Number of top saturated cores to display (default: 10)")
    p13.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p13.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # get-comm-top
    p14 = subparsers.add_parser('get-comm-top',
                                help="Get top N comm groups by aggregated CPU (for many-small-processes analysis)")
    p14.add_argument("--data", required=True, help="Path to perf script output file")
    p14.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SPEAR format.")
    p14.add_argument("--top-n", type=int, default=10, help="Number of top comm groups to display (default: 10)")
    p14.add_argument("--sort-by-density", action="store_true",
                     help="Sort by density index (CPU per process) instead of aggregate CPU")
    p14.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p14.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p14.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p14.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # trace subcommands (v2.0: tracing diagnostic process)
    doc_parser = subparsers.add_parser('trace', help="Tracing diagnostic issues and timeline")
    doc_subparsers = doc_parser.add_subparsers(dest="doc_command")
    
    # doc init
    doc_init = doc_subparsers.add_parser('init', help="Initialize a new diagnosis document")
    doc_init.add_argument("--data", required=True, help="Path to perf data file")
    doc_init.add_argument("--path", default=".spear.json", help="Document storage path (default: .spear.json)")
    
    # doc add (自动生成 ID)
    doc_add = doc_subparsers.add_parser('add', help="Add a new issue to the document (auto-generate ID)")
    doc_add.add_argument("--desc", required=True, help="Issue description")
    doc_add.add_argument("--level", choices=['critical', 'warning', 'info'], default='warning', help="Risk level")
    doc_add.add_argument("--risk", default="", help="Risk of not handling this issue")
    doc_add.add_argument("--hint", default="", help="Recommended next action")
    
    # doc timeline (v2.0)
    doc_timeline = doc_subparsers.add_parser('timeline', help="Show diagnosis timeline")
    doc_timeline.add_argument("--format", choices=['text', 'json'], default='text', help="Output format")
    doc_timeline.add_argument('--risk-config', metavar='PATH', help='Risk display config file (JSON)')
    doc_timeline.add_argument('--risk-style', choices=['default', 'ci', 'compact'], help='Risk style preset')
    
    # doc issues (v2.0)
    doc_issues = doc_subparsers.add_parser('issues', help="List all issues")
    doc_issues.add_argument("--status", choices=['open', 'resolved', 'all'], default='all', help="Filter by status")
    doc_issues.add_argument('--risk-config', metavar='PATH', help='Risk display config file (JSON)')
    doc_issues.add_argument('--risk-style', choices=['default', 'ci', 'compact'], help='Risk style preset')
    
    # doc complete
    doc_complete = doc_subparsers.add_parser('complete', help="Mark an issue as completed")
    doc_complete.add_argument("--id", required=True, help="Issue identifier")
    doc_complete.add_argument("--result", required=True, help="Analysis result and conclusion")
    
    # doc finalize
    doc_finalize = doc_subparsers.add_parser('finalize', help="Final audit before generating report")
    doc_finalize.add_argument("--accept-risk", help="Reason for accepting remaining risks")
    doc_finalize.add_argument("--format", choices=['text', 'json'], default='text', help="Output format")
    doc_finalize.add_argument('--risk-config', metavar='PATH', help='Risk display config file (JSON)')
    doc_finalize.add_argument('--risk-style', choices=['default', 'ci', 'compact'], help='Risk style preset')
    
    # doc export
    doc_export = doc_subparsers.add_parser('export', help="Export document to other formats")
    doc_export.add_argument("--format", choices=['markdown', 'json'], default='markdown', help="Export format")
    doc_export.add_argument("--output", help="Output file path (default: stdout)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Handle perf-doc subcommands (doesn't require --data or engine)
    if args.command == "trace":
        if not args.doc_command:
            doc_parser.print_help()
            return
        
        doc_commands = {
            "init": cmd_doc_init,
            "add": cmd_doc_add,
            "timeline": cmd_doc_timeline,
            "issues": cmd_doc_issues,
            "complete": cmd_doc_complete,
            "finalize": cmd_doc_finalize,
            "export": cmd_doc_export
        }
        doc_commands[args.doc_command](args)
        return

    # Initialize engine for analysis commands (requires --data)
    # Get freq from args, default to 19Hz for raw perf format
    freq = getattr(args, 'freq', 19)
    engine = PerfExpertEngine(args.data, freq=freq)

    # Route find-callers to appropriate handler
    if args.command == "find-callers":
        if args.auto_target or not args.target:
            args.command = "find-callers-auto"

    # Command routing table
    commands = {
        "check-cpu-bottleneck": cmd_check_bottleneck,
        "get-hotspots": cmd_get_hotspots,
        "cluster-symbols": cmd_apply_cluster,
        "find-callers": cmd_trace_attribution,
        "find-callers-auto": cmd_find_callers_auto,
        "detect-anomalies": cmd_detect_anomalies,
        "show-cpu-usage": cmd_show_cpu_usage,
        "get-process-top": cmd_get_process_top,
        "cluster-comm": cmd_cluster_comm,
        "cluster-paths": cmd_cluster_paths,
        "count-process-variety": cmd_count_process_variety,
        "analyze-core-distribution": cmd_analyze_core_distribution,
        "get-comm-top": cmd_get_comm_top
    }

    # Execute analysis command
    if args.command in commands:
        commands[args.command](engine, args)


if __name__ == "__main__":
    main()
