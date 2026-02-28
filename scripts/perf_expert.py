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
      ├── flamegraph.py      - FlameGraph format generation
      ├── callgraph.py       - Call graph DOT/JSON generation
      ├── cpu_usage.py       - CPU utilization breakdown
      ├── process_top.py     - Top processes by CPU
      ├── comm_clusters.py   - Cluster by process name
      ├── path_clusters.py   - Cluster by call paths (Trie-based)
      └── process_variety.py - Process storm detection

Key Changes in v2.0:
  - Removed --freq parameter: Reliability is now assessed directly using CPU utilization
    from core/s values in perf script output, not from sampling frequency
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
from perf_toolkit.analysis.flamegraph import cmd_generate_flamegraph
from perf_toolkit.analysis.callgraph import cmd_generate_callgraph
from perf_toolkit.analysis.cpu_usage import cmd_show_cpu_usage
from perf_toolkit.analysis.process_top import cmd_get_process_top
from perf_toolkit.analysis.comm_clusters import cmd_cluster_comm
from perf_toolkit.analysis.path_clusters import cmd_cluster_paths
from perf_toolkit.analysis.process_variety import cmd_count_process_variety
from perf_toolkit.analysis.core_distribution import cmd_analyze_core_distribution
from perf_toolkit.analysis.comm_top import cmd_get_comm_top


class HelpOnErrorParser(argparse.ArgumentParser):
    """Custom parser that prints full help on error"""
    def error(self, message):
        import sys
        self.print_help(sys.stderr)
        self.exit(2, f'\n{self.prog}: error: {message}\n')


def main():
    parser = HelpOnErrorParser(
        description="Perf Expert Diagnostic Toolkit - Analyze Linux performance data using SPEAR methodology",
        epilog="""Usage Examples:
  # Analyze hotspots in a specific process
  python perf_expert.py get-hotspots --data perf.data.txt --comm myapp --top-n 20

  # Check CPU bottleneck with cgroup limit
  python perf_expert.py check-cpu-bottleneck --data perf.data.txt --cpu-limit 0.5c

  # Find callers of a specific function
  python perf_expert.py find-callers --data perf.data.txt --target pthread_mutex_lock

  # Detect anomalies in a time window
  python perf_expert.py detect-anomalies --data perf.data.txt --window-size 1.0

  # Analyze core distribution for load balancing issues
  python perf_expert.py analyze-core-distribution --data perf.data.txt --comm myapp

Input Data Format:
  Requires 'perf script' output with core/s field. Generate with:
    perf record -F 19 -a -g -- sleep 30
    perf script > perf.data.txt

Note: The --freq parameter has been removed in v2.0. CPU utilization is now
calculated directly from perf script's core/s values, and reliability is assessed
based on actual CPU utilization rather than sampling frequency.

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
    # REMOVED: --freq parameter - now calculated from core/s values
    p1.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p1.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p1.add_argument("--pid", type=int, help="Filter by process ID")
    p1.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p1.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # get-hotspots
    p2 = subparsers.add_parser('get-hotspots',
                               help="Extract hotspot function rankings by self/inclusive time")
    p2.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p2.add_argument("--sort-by", choices=['inclusive', 'self'], default='inclusive',
                    help="Sort by 'inclusive' (total time in call chain) or 'self' (time in function only)")
    p2.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p2.add_argument("--top-n", type=int, default=10, help="Number of top hotspots to display (default: 10)")
    p2.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p2.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p2.add_argument("--pid", type=int, help="Filter by process ID")
    p2.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p2.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # cluster-symbols
    p3 = subparsers.add_parser('cluster-symbols',
                               help="Cluster samples by expert rules (scheduling, locks, memory, IRQ, etc.)")
    p3.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p3.add_argument("--custom-rules", metavar="RULES",
                    help="JSON format custom rules. Example: '{\"MyPattern\": [{\"pattern\": \"my_func_.*\", "
                         "\"weight\": 1.0}]}'. Rules are list of {pattern, weight} objects.")
    p3.add_argument("--include-experts", action="store_true", default=True,
                    help="Include built-in expert rules (default: True)")
    p3.add_argument("--no-include-experts", action="store_true",
                    help="Exclude built-in expert rules")
    p3.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p3.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p3.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p3.add_argument("--pid", type=int, help="Filter by process ID")
    p3.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p3.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # find-callers
    p4 = subparsers.add_parser('find-callers',
                               help="Find and analyze callers of a specific function or auto-trace top hotspots")
    p4.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p4.add_argument("--target", metavar="FUNC",
                    help="Target function name to trace. Examples: 'pthread_mutex_lock', "
                         "'sched_yield', 'malloc'. Use with --min-ratio to filter significant callers. "
                         "If not provided, use --auto-target to trace top hotspots automatically")
    p4.add_argument("--auto-target", action="store_true",
                    help="Automatically trace top N hotspot functions")
    p4.add_argument("--top-n", "--auto-target-top-n", type=int, default=5,
                    dest='auto_target_top_n',
                    help="Number of top hotspots to auto-trace (default: 5)")
    p4.add_argument("--min-ratio", type=float, default=0.5,
                    help="Minimum ratio (0-100) of target samples to include in results (default: 0.5%%)")
    p4.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p4.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p4.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p4.add_argument("--pid", type=int, help="Filter by process ID")
    p4.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p4.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # detect-anomalies
    p5 = subparsers.add_parser('detect-anomalies',
                               help="Detect CPU utilization anomalies or export window data")
    p5.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p5.add_argument("--window-size", type=float, default=0.5, metavar="SECONDS",
                    help="Time window size in seconds for sliding window analysis. Smaller windows "
                         "detect rapid changes but may produce more noise. (default: 0.5)")
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
    p5.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p5.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p5.add_argument("--pid", type=int, help="Filter by process ID")
    p5.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p5.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # generate-flamegraph
    p6 = subparsers.add_parser('generate-flamegraph',
                               help="Generate FlameGraph format for visualization")
    p6.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p6.add_argument("--format", choices=['folded', 'json'], default='folded',
                    help="Output format: 'folded' for FlameGraph/speedscope, 'json' for structured data")
    p6.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p6.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p6.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p6.add_argument("--pid", type=int, help="Filter by process ID")
    p6.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p6.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p6.add_argument("--top-n", type=int, default=1000,
                    help="Top N stacks to include in JSON format (default: 1000)")

    # generate-callgraph
    p7 = subparsers.add_parser('generate-callgraph',
                               help="Generate Call Graph in DOT/JSON format")
    p7.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p7.add_argument("--format", choices=['dot', 'json'], default='dot',
                    help="Output format: 'dot' for Graphviz visualization, 'json' for structured data")
    p7.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p7.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p7.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")
    p7.add_argument("--pid", type=int, help="Filter by process ID")
    p7.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p7.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p7.add_argument("--max-nodes", type=int, default=50,
                    help="Maximum nodes in graph, 0 for unlimited (default: 50)")
    p7.add_argument("--min-edge-count", type=int, default=1,
                    help="Minimum call edge count to include in output (default: 1)")

    # show-cpu-usage
    p8 = subparsers.add_parser('show-cpu-usage',
                               help="Show CPU utilization for OS or specific PID (user/kernel/total)")
    p8.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p8.add_argument("--pid", type=int, help="Process ID to analyze (default: all processes)")
    p8.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p8.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p8.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p8.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p8.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # get-process-top
    p9 = subparsers.add_parser('get-process-top',
                               help="Get top N processes by CPU utilization with user/kernel breakdown")
    p9.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p9.add_argument("--top-n", type=int, default=10, help="Number of top processes to display (default: 10)")
    p9.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p9.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p9.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # cluster-comm
    p10 = subparsers.add_parser('cluster-comm',
                                help="Cluster samples by process name (comm) to analyze process group CPU usage")
    p10.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
    p10.add_argument("--top-n", type=int, default=10, help="Number of top comm groups to display (default: 10)")
    p10.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p10.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p10.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # cluster-paths
    p11 = subparsers.add_parser('cluster-paths',
                                help="Cluster samples by common call path prefixes using Trie")
    p11.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
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
    p11.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p11.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # count-process-variety
    p12 = subparsers.add_parser('count-process-variety',
                                help="Count process variety to detect short-lived process storms")
    p12.add_argument("--data", required=True, help="Path to perf script output file")
    # REMOVED: --freq parameter
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
    p12.add_argument("--pid", type=int, help="Filter by process ID")
    p12.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p12.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p12.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p12.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # analyze-core-distribution
    p13 = subparsers.add_parser('analyze-core-distribution',
                                help="Analyze per-core CPU utilization and thread states")
    p13.add_argument("--data", required=True, help="Path to perf script output file")
    p13.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p13.add_argument("--pid", type=int, help="Filter by process ID")
    p13.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p13.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p13.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p13.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    # get-comm-top
    p14 = subparsers.add_parser('get-comm-top',
                                help="Get top N comm groups by aggregated CPU (for many-small-processes analysis)")
    p14.add_argument("--data", required=True, help="Path to perf script output file")
    p14.add_argument("--top-n", type=int, default=10, help="Number of top comm groups to display (default: 10)")
    p14.add_argument("--sort-by-density", action="store_true",
                     help="Sort by density index (CPU per process) instead of aggregate CPU")
    p14.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p14.add_argument("--pid", type=int, help="Filter by process ID")
    p14.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p14.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p14.add_argument("--start-time", type=float, help="Filter samples after this timestamp (inclusive)")
    p14.add_argument("--end-time", type=float, help="Filter samples before this timestamp (inclusive)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Initialize engine (no hz parameter needed anymore)
    engine = PerfExpertEngine(args.data)

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
        "generate-flamegraph": cmd_generate_flamegraph,
        "generate-callgraph": cmd_generate_callgraph,
        "show-cpu-usage": cmd_show_cpu_usage,
        "get-process-top": cmd_get_process_top,
        "cluster-comm": cmd_cluster_comm,
        "cluster-paths": cmd_cluster_paths,
        "count-process-variety": cmd_count_process_variety,
        "analyze-core-distribution": cmd_analyze_core_distribution,
        "get-comm-top": cmd_get_comm_top
    }

    commands[args.command](engine, args)


if __name__ == "__main__":
    main()
