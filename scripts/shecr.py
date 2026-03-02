#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Perf Expert Diagnostic Toolkit - Analyze Linux performance data using SHECR methodology

This is the main entry point for the perf toolkit. It has been refactored into a modular structure:

  scripts/perf_toolkit/
  ├── core/
  │   ├── engine.py          - PerfExpertEngine class and parsing logic
  │   └── reliability.py     - Sample reliability assessment (no freq parameter)
  └── analysis/
      ├── hotspots.py        - Hotspot function analysis
      ├── trace.py           - Call attribution tracing
      ├── anomalies.py       - CPU utilization anomaly detection
      ├── path_clusters.py   - Cluster by call paths (Trie-based)
      ├── core_distribution.py - Core-level load distribution analysis
      └── comm_top.py        - Comm-level CPU analysis (with CV/Monopoly/SpawnRate)

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
from perf_toolkit.analysis.hotspots import cmd_get_hotspots
from perf_toolkit.analysis.trace import cmd_trace_attribution
from perf_toolkit.analysis.anomalies import cmd_detect_anomalies
from perf_toolkit.analysis.path_clusters import cmd_cluster_paths
from perf_toolkit.analysis.core_distribution import cmd_analyze_core_distribution, parse_cpu_quota
from perf_toolkit.analysis.comm_top import cmd_get_comm_top

# Import Composite commands
from perf_toolkit.composite.sys_audit import cmd_sys_audit
from perf_toolkit.composite.bottleneck_trace import cmd_bottleneck_trace

# Import trace commands (v2.0: auto add, manual complete)
from perf_toolkit.core.trace import (
    cmd_doc_init, cmd_doc_add, cmd_doc_complete, cmd_doc_timeline,
    cmd_doc_issues, cmd_doc_finalize, cmd_doc_export, cmd_doc_reopen,
    cmd_doc_audit
)


class HelpOnErrorParser(argparse.ArgumentParser):
    """Custom parser that prints full help on error"""
    def error(self, message):
        import sys
        self.print_help(sys.stderr)
        self.exit(2, f'\n{self.prog}: error: {message}\n')


def main():
    parser = HelpOnErrorParser(
        description="SHECR Diagnostic Toolkit",
        epilog="""Usage Examples:
  # Analyze hotspots in a specific process
  shecr get-hotspots --data perf.data.txt --comm myapp --top-n 20

  # Analyze core distribution (includes single-core saturation detection)
  shecr analyze-core-distribution --data perf.data.txt --cpu-limit 0.5c

  # Find callers of a specific function
  shecr find-callers --data perf.data.txt --target pthread_mutex_lock

  # Detect anomalies in a time window
  shecr detect-anomalies --data perf.data.txt --window-size 1.0

  # System audit - comprehensive analysis with auto noise reduction
  shecr sys-audit --data perf.data.txt
  
  # Bottleneck trace - deep analysis of bottleneck processes
  shecr bottleneck-trace --data perf.data.txt --comm myapp

Input Data Format:
  Supports two formats:
  1. SHECR format: perf script output processed with CPU utilization values
  2. Raw perf format: standard perf script output (requires --freq parameter)

  Generate raw perf data with:
    perf record -F 19 -a -g -- sleep 30
    perf script > perf.data.txt

Note: For raw perf format, use --freq to specify sampling
frequency (default: 19Hz). For SPEAR format, the freq parameter is ignored.

Use '<command> --help' for detailed help on each subcommand."""
    )
    subparsers = parser.add_subparsers(dest="command")

      # get-hotspots
    p2 = subparsers.add_parser('get-hotspots',
                               help="Extract hotspot function rankings by self/inclusive time")
    p2.add_argument("--data", required=True, help="Path to perf script output file")
    p2.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SHECR format.")
    p2.add_argument("--sort-by", choices=['inclusive', 'self'], default='inclusive',
                    help="Sort by 'inclusive' (total time in call chain) or 'self' (time in function only)")
    p2.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p2.add_argument("--top-n", "--limit", type=int, default=10, help="Number of top hotspots to display (default: 10)")
    p2.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p2.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")
    p2.add_argument("--pid", type=int, help="Filter by process ID")
    p2.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p2.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")

    # find-callers
    p4 = subparsers.add_parser('find-callers',
                               help="Find and analyze callers of a specific function or auto-trace top hotspots")
    p4.add_argument("--data", required=True, help="Path to perf script output file")
    p4.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SHECR format.")
    p4.add_argument("--target", metavar="FUNC",
                    help="Target function name to trace. Examples: 'pthread_mutex_lock', "
                         "'sched_yield', 'malloc'. Use with --min-ratio to filter significant callers. "
                         "If not provided, use --auto-target to trace top hotspots automatically")
    p4.add_argument("--auto-target", action="store_true",
                    help="Automatically trace top N hotspot functions")
    p4.add_argument("--top-n", "--limit", type=int, default=10,
                    help="Number of top results to display (default: 10)")
    p4.add_argument("--min-ratio", type=float, default=0.5, metavar="PERCENT",
                    dest="min_ratio",
                    help="Minimum ratio %% of total samples to display a caller (default: 0.5%%). "
                         "Callers below this threshold are hidden but counted.")
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
                         "Default: 19. Ignored for SHECR format.")
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
    p5.add_argument("--top-n", "--limit", type=int, default=10, help="Top N anomalies to report")
    p5.add_argument("--export-mode", action="store_true",
                    help="Export all window data instead of detecting anomalies")
    p5.add_argument("--export-samples", action="store_true",
                    help="Include detailed sample data in export mode")
    p5.add_argument("--detect-in-export", action="store_true",
                    help="Also detect anomalies when in export mode")
    p5.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p5.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # cluster-paths
    p11 = subparsers.add_parser('cluster-paths',
                                help="Cluster samples by common call path prefixes using Trie")
    p11.add_argument("--data", required=True, help="Path to perf script output file")
    p11.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SHECR format.")
    p11.add_argument("--min-depth", type=int, default=2,
                     help="Minimum common prefix depth to form a cluster (default: 2)")
    p11.add_argument("--min-samples", type=int, default=5,
                     help="Minimum samples to form a cluster (default: 5)")
    p11.add_argument("--top-n", "--limit", type=int, default=10,
                     help="Number of top clusters to display (default: 10)")
    p11.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p11.add_argument("--pid", type=int, help="Filter by process ID")
    p11.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p11.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p11.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p11.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # analyze-core-distribution
    p13 = subparsers.add_parser('analyze-core-distribution',
                                help="Analyze per-core CPU utilization and thread states")
    p13.add_argument("--data", required=True, help="Path to perf script output file")
    p13.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SHECR format.")
    p13.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p13.add_argument("--pid", type=int, help="Filter by process ID")
    p13.add_argument("--comm", type=str, help="Filter by process name (comm), supports multiple values separated by comma")
    p13.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p13.add_argument("--top-n", "--limit", type=int, default=10, help="Number of top saturated cores to display (default: 10)")
    p13.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p13.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # get-comm-top
    p14 = subparsers.add_parser('get-comm-top',
                                help="Get top N comm groups by aggregated CPU (for many-small-processes analysis)")
    p14.add_argument("--data", required=True, help="Path to perf script output file")
    p14.add_argument("--freq", type=int, default=19, metavar="HZ",
                    help="Sampling frequency in Hz for raw perf format. "
                         "Default: 19. Ignored for SHECR format.")
    p14.add_argument("--top-n", "--limit", type=int, default=10, help="Number of top comm groups to display (default: 10)")
    p14.add_argument("--sort-by-density", action="store_true",
                     help="Sort by density index (CPU per process) instead of aggregate CPU")
    p14.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p14.add_argument("--comm-regex", type=str, help="Filter by process name regex pattern")
    p14.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive). Formats: Unix timestamp, ISO 8601, datetime, or date")
    p14.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive). Same formats as --start-time")

    # =============================================================================
    # Composite Commands (三层架构)
    # =============================================================================
    
    # sys-audit
    p_comp1 = subparsers.add_parser('sys-audit',
                                    help="[Composite] System audit - auto orchestrate multiple analysis tools")
    p_comp1.add_argument("--data", required=True, help="Path to perf script output file")
    p_comp1.add_argument("--freq", type=int, default=19, metavar="HZ",
                        help="Sampling frequency in Hz for raw perf format. "
                             "Default: 19. Ignored for SHECR format.")
    p_comp1.add_argument("--top-n", "--limit", type=int, default=20, 
                        help="Number of top process groups to analyze (default: 20)")
    p_comp1.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p_comp1.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive)")
    p_comp1.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive)")
    
    # bottleneck-trace
    p_comp2 = subparsers.add_parser('bottleneck-trace',
                                    help="[Composite] Bottleneck trace - auto identify and deep analyze CPU bottlenecks")
    p_comp2.add_argument("--data", required=True, help="Path to perf script output file")
    p_comp2.add_argument("--freq", type=int, default=19, metavar="HZ",
                        help="Sampling frequency in Hz for raw perf format. "
                             "Default: 19. Ignored for SHECR format.")
    p_comp2.add_argument("--comm", type=str, help="Target process name (auto-detect if not specified)")
    p_comp2.add_argument("--top-n", "--limit", type=int, default=10,
                        help="Number of top hotspots to analyze (default: 10)")
    p_comp2.add_argument("--cpu-id", type=int, help="Filter by CPU ID")
    p_comp2.add_argument("--start-time", type=str, help="Filter samples after this time (inclusive)")
    p_comp2.add_argument("--end-time", type=str, help="Filter samples before this time (inclusive)")
    


    # trace subcommands (v2.0: tracing diagnostic process)
    doc_parser = subparsers.add_parser('trace', help="Tracing diagnostic issues and timeline")
    doc_subparsers = doc_parser.add_subparsers(dest="doc_command")

    # doc init
    doc_init = doc_subparsers.add_parser('init', help="Initialize a new diagnosis document")
    doc_init.add_argument("--data", required=True, help="Path to perf data file")
    doc_init.add_argument("--path", default=".shecr.json", help="Document storage path (default: .shecr.json)")

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

    # doc reopen
    doc_reopen = doc_subparsers.add_parser('reopen', help="Reopen a resolved issue")
    doc_reopen.add_argument("--id", help="Issue identifier")
    doc_reopen.add_argument("--all", action="store_true", help="Reopen all resolved issues")
    doc_reopen.add_argument("--reason", default="", help="Reason for reopening")

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

    # doc audit
    doc_audit = doc_subparsers.add_parser('audit', help="Audit resolved issues for quality")
    doc_audit.add_argument("--phase", choices=['all', 'structural', 'timeline', 'depth'], default='all', help="Audit phase to run")
    doc_audit.add_argument("--format", choices=['text', 'json'], default='text', help="Output format")
    doc_audit.add_argument("--output", help="Output file path (default: stdout)")
    doc_audit.add_argument("--no-fail", action="store_true", help="Don't exit with error code on failure")
    doc_audit.add_argument('--risk-config', metavar='PATH', help='Risk display config file (JSON)')
    doc_audit.add_argument('--risk-style', choices=['default', 'ci', 'compact'], help='Risk style preset')

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
            "reopen": cmd_doc_reopen,
            "finalize": cmd_doc_finalize,
            "export": cmd_doc_export,
            "audit": cmd_doc_audit
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
        "get-hotspots": cmd_get_hotspots,
        "find-callers": cmd_trace_attribution,
        "detect-anomalies": cmd_detect_anomalies,
        "cluster-paths": cmd_cluster_paths,
        "analyze-core-distribution": cmd_analyze_core_distribution,
        "get-comm-top": cmd_get_comm_top,
        # Composite commands
        "sys-audit": cmd_sys_audit,
        "bottleneck-trace": cmd_bottleneck_trace
    }

    # Execute analysis command
    if args.command in commands:
        commands[args.command](engine, args)


if __name__ == "__main__":
    main()
