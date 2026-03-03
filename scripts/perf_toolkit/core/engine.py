#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerfExpert Engine - Core parsing and data management

使用 Symbol 结构感知 kernel/user 符号差异：
- 原始数据中 kernel 函数带有 `_[k]` 后缀
- Symbol 类在解析时保留这一信息，提供准确的 is_kernel 属性
- 利用率计算基于 Symbol.is_kernel，而非启发式规则

V2 版本：CPU 利用率计算收拢到 engine，统一对外提供利用率数据
"""

import json
import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Set
from .symbol import Symbol, SymbolStack
from .engine_types import (
    UserKernelStats, CPUUtilization, ProcessCPUInfo, PidCPUInfo, CommCPUInfo,
    CoreCPUInfo, SymbolCPUInfo, ProcessLifecycle, LifecycleEvent,
    LifecycleStats, CallerInfo, CallEdge, CallGraph, Sample
)


def parse_time_string(time_str):
    """
    Parse time string to Unix timestamp.

    Supports formats:
    - Unix timestamp (float): 1705312200.123
    - ISO 8601: 2024-01-15T10:30:00, 2024-01-15T10:30:00+08:00
    - Common date: 2024-01-15 10:30:00
    - Date only: 2024-01-15 (treated as 00:00:00)

    Args:
        time_str: Time string in various formats

    Returns:
        Unix timestamp as float

    Raises:
        ValueError: If format not recognized
    """
    if time_str is None:
        return None

    # If already a number, return as float
    try:
        return float(time_str)
    except ValueError:
        pass

    # Try various formats
    formats = [
        # ISO 8601 with timezone
        '%Y-%m-%dT%H:%M:%S%z',
        # ISO 8601 without timezone
        '%Y-%m-%dT%H:%M:%S',
        # Common datetime formats
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        # Date only
        '%Y-%m-%d',
        # Compact formats
        '%Y%m%d%H%M%S',
        '%Y%m%d',
    ]

    # Handle special case: ISO 8601 with colon in timezone (e.g., +08:00)
    time_str_normalized = time_str
    if len(time_str) > 6 and time_str[-3] == ':' and time_str[-6] in ['+', '-']:
        # Remove colon in timezone: +08:00 -> +0800
        time_str_normalized = time_str[:-3] + time_str[-2:]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str_normalized, fmt)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse time: '{time_str}'. Supported formats: "
                     f"Unix timestamp, ISO 8601 (2024-01-15T10:30:00), "
                     f"common datetime (2024-01-15 10:30:00), or date only (2024-01-15)")


class PerfExpertEngine:
    """
    Main engine for parsing and analyzing perf script output.

    Supports two data formats:
    1. SPEAR format: Pre-computed CPU utilization values
    2. Raw perf format: Requires freq parameter to calculate utilization

    Symbol handling:
    - Kernel symbols have `_[k]` suffix in raw data (e.g., `osq_lock_[k]`)
    - Symbol class preserves this info via `is_kernel` attribute
    - CPU utilization split (user/kernel) uses Symbol.is_kernel directly
    """

    # Expert knowledge base - symbol classification rules
    EXPERT_RULES = {
        "EVENT_IRQ_OFF": r"irqoff|spin_unlock_irqrestore|ksoftirqd",
        "EVENT_SCHEDULER": r"sched_|pick_next_task|load_balance|idle_balance|dequeue_task|enqueue_task",
        "EVENT_MEM_RECLAIM": r"direct_reclaim|try_to_free_pages|tlb_flush|tlb_shootdown",
        "EVENT_LOCK_CONTENTION": r"spin_lock|mutex_lock|rwsem_down|queued_spin_lock",
        "EVENT_SYNC_PRIMITIVE": r"pthread_mutex|pthread_cond|pthread_sig|futex_wait|futex_wake"
    }

    # Extended lock patterns for detailed lock contention analysis
    LOCK_PATTERNS = {
        "SPINLOCK": r"_raw_spin_lock|queued_spin_lock|spin_trylock",
        "MUTEX": r"__mutex_lock|mutex_trylock|ww_mutex_lock",
        "RWSEM": r"rwsem_down|down_read|down_write|up_read|up_write",
        "SPINLOCK_IRQ": r"_raw_spin_lock_irq|_raw_spin_lock_bh",
        "SEQLOCK": r"write_seqlock|read_seqlock|raw_seqlock"
    }

    def __init__(self, file_path, freq=19):
        """
        Initialize engine with perf script file.

        Args:
            file_path: Path to perf script output file
            freq: Sampling frequency in Hz (default: 19).
                  Only used for raw perf format, ignored for SPEAR format.
        """
        self.file_path = file_path
        self.freq = freq
        self.samples = []
        self._has_core_per_sec = None  # Will be auto-detected during parsing
        self._load_and_parse()

    @staticmethod
    def _is_hex_addr(s):
        """Check if string is a hex address (starts with 0x or is long hex)"""
        return (s.startswith('0x') and len(s) > 2) or (len(s) >= 8 and all(c in '0123456789abcdefABCDEF' for c in s))

    @staticmethod
    def _strip_parens(module):
        """Remove parentheses from module name"""
        return module.strip('()')

    def _parse_stack_line(self, line):
        """
        Parse a single stack line and extract Symbol.

        Supports multiple formats:
          1. "osq_lock_[k] (containerd-shim)" - symbol (module)
          2. "0x64c4b3(containerd-shim-runc-v2)" - address(module) - single token
          3. "ffff800080441754 zap_pte_range+0x2d4 ([kernel.kallsyms])" - address symbol+offset (module)
          4. "zap_pte_range+0x2d4 ([kernel.kallsyms])" - symbol+offset (module)
          5. "_IO_getline_info" - symbol only (no module)
          6. "_IO_getline_info+0x1f" - symbol+offset only (no module)
          7. "_IO_getline_info+0x1f (netstat)" - symbol+offset (module)

        Returns:
            Symbol object with accurate is_kernel information, or None if parsing fails
        """
        stripped = line.strip()
        parts = stripped.split()

        sym_str = None
        module = None

        if len(parts) >= 3 and self._is_hex_addr(parts[0]):
            # Format: "address symbol+offset (module)"
            # Example: "ffff800080441754 zap_pte_range+0x2d4 ([kernel.kallsyms])"
            sym_str = Symbol._strip_offset(parts[1])
            module = self._strip_parens(parts[2])
        elif len(parts) == 2:
            # Check if parts[1] looks like a module (wrapped in parentheses)
            if parts[1].startswith('(') and parts[1].endswith(')'):
                # Format: "symbol (module)" or "symbol+offset (module)"
                # Example: "osq_lock_[k] (containerd-shim)" or "_IO_getline_info+0x1f (netstat)"
                sym_str = Symbol._strip_offset(parts[0])
                module = self._strip_parens(parts[1])
            else:
                # Format: "address symbol" or other 2-token format
                # Try to interpret based on whether first part is hex address
                if self._is_hex_addr(parts[0]):
                    # "address symbol+offset" without module
                    sym_str = Symbol._strip_offset(parts[1])
                else:
                    # Could be "symbol something" - use first part as symbol
                    sym_str = Symbol._strip_offset(parts[0])
        elif len(parts) == 1:
            # Format: "address(module)" or "symbol" or "symbol+offset" (single token)
            # Example: "0x64c4b3(containerd-shim-runc-v2)" or "_IO_getline_info" or "_IO_getline_info+0x1f"
            token = parts[0]
            if '(' in token and token.endswith(')'):
                # Keep as-is, it's an address or symbol with module embedded
                sym_str = token
            else:
                # Pure symbol or symbol+offset (no module)
                sym_str = Symbol._strip_offset(token)

        if sym_str:
            # Create Symbol object - it will automatically detect kernel symbols
            return Symbol.parse(sym_str, module)

        return None

    def _detect_file_format(self):
        """
        Detect file format by reading first few bytes.

        Returns:
            'test2' for test2.data JSON format
            'perf_script' for standard perf script output
        """
        with open(self.file_path, 'r') as f:
            first_char = f.read(1)
            if first_char == '{':
                return 'test2'
            return 'perf_script'

    def _load_and_parse(self):
        """Parse perf script standard output"""
        # Detect file format and dispatch to appropriate parser
        file_format = self._detect_file_format()

        if file_format == 'test2':
            self._load_and_parse_test2()
        else:
            self._load_and_parse_perf_script()

    def _load_and_parse_test2(self):
        """
        Parse test2.data JSON format.

        Format:
          {"data": "timestamp:comm:pid:cpuid;sym0;sym1... weight\\n..."}

        Sample line inside data field:
          123.15:containerd-shim:2350748:0;0x64c4b3 [containerd-shim-runc-v2];osq_lock_[k] 0.0526
        """
        with open(self.file_path, 'r') as f:
            data = json.load(f)

        raw_data = data.get('data', '')
        # Split by literal \n or actual newline
        raw_samples = re.split(r'\\n|\n', raw_data)

        for raw in raw_samples:
            raw = raw.strip()
            if not raw or raw == '...':
                continue

            sample = self._parse_test2_sample(raw)
            if sample:
                self.samples.append(sample)

    def _parse_test2_sample(self, raw: str):
        """
        Parse a single test2.data sample string.

        Supports two delimiter styles:
          - colon style: timestamp:comm:pid:cpuid;sym0;sym1... weight
          - pipe style:  timestamp:comm|pid|cpuid;sym0;sym1... weight
                         or timestamp|comm|pid|cpuid;sym0;sym1... weight

        Note: comm may contain colons (e.g., "runc:[2:INIT]"), so we parse from right to left
        using the fact that pid and cpuid are pure numbers as anchors.
        """
        line = raw.strip()

        # Step 1: Extract weight value (last space-separated number)
        last_space_idx = line.rfind(' ')
        if last_space_idx == -1:
            return None

        try:
            core_per_sec = float(line[last_space_idx + 1:])
        except ValueError:
            return None

        prefix = line[:last_space_idx].strip()

        # Step 2: Split header and callstack at ';'
        semicolon_idx = prefix.find(';')
        if semicolon_idx == -1:
            return None

        header = prefix[:semicolon_idx]
        callstack_str = prefix[semicolon_idx + 1:]

        # Step 3: Detect delimiter style by checking for '|' in header
        # If '|' exists, use pipe style; otherwise use colon style
        if '|' in header:
            return self._parse_test2_header_with_delimiter(header, callstack_str, core_per_sec, '|')
        else:
            return self._parse_test2_header_with_delimiter(header, callstack_str, core_per_sec, ':')

    def _parse_test2_header_with_delimiter(self, header: str, callstack_str: str, core_per_sec: float, delim: str):
        """
        Parse header with specified delimiter.
        Format: timestamp{delim}comm{delim}pid{delim}cpuid
        """
        # Parse from right to left
        # Find cpuid (last delimiter, should be pure number)
        delim_idx = header.rfind(delim)
        if delim_idx == -1:
            return None

        cpuid_str = header[delim_idx + 1:]
        if not cpuid_str.isdigit():
            return None
        cpuid = int(cpuid_str)

        header = header[:delim_idx]

        # Find pid (second last delimiter, should be pure number)
        delim_idx = header.rfind(delim)
        if delim_idx == -1:
            return None

        pid = header[delim_idx + 1:]
        if not pid.isdigit():
            return None

        header = header[:delim_idx]

        # Find timestamp (first delimiter)
        delim_idx = header.find(delim)
        if delim_idx == -1:
            return None

        try:
            timestamp = float(header[:delim_idx])
        except ValueError:
            return None

        # Everything between first delimiter and pid delimiter is comm
        comm = header[delim_idx + 1:]

        # Step 4: Parse callstack - symbols are semicolon-separated
        stack = SymbolStack()
        symbols = [s.strip() for s in callstack_str.split(';') if s.strip()]

        for sym in symbols:
            symbol = self._parse_test2_symbol(sym)
            if symbol:
                stack.append(symbol)

        return Sample(
            comm=comm,
            pid=pid,
            cpu=cpuid,
            ts=timestamp,
            core_per_sec=core_per_sec,
            stack=stack
        )

    def _parse_test2_symbol(self, sym_str: str) -> Symbol:
        """
        Parse a symbol from test2.data format.

        Supports formats:
          - "symbol" - just symbol name (e.g., "osq_lock_[k]")
          - "symbol [module]" - symbol with module in brackets (e.g., "0x64c4b3 [containerd-shim-runc-v2]")
          - "0xaddr [module]" - address with module

        Note: Kernel symbols end with '_ [k]' (space before [k]), but the space might not be there.
        We need to distinguish between:
          - "osq_lock_[k]" - kernel symbol, no module (ends with _[k])
          - "0x64c4b3 [containerd-shim]" - address with module (space before [)
        """
        sym_str = sym_str.strip()

        # Check for "symbol [module]" format - look for " [" pattern
        # This distinguishes "0x64c4b3 [module]" from "osq_lock_[k]"
        space_bracket_idx = sym_str.find(' [')
        if space_bracket_idx != -1 and sym_str.endswith(']'):
            # Format: "symbol [module]" - space before [ indicates module separator
            symbol_part = sym_str[:space_bracket_idx].strip()
            module = sym_str[space_bracket_idx+2:-1].strip()  # Remove " [" and "]"

            # Strip offset if present (e.g., "symbol+0x10" -> "symbol")
            symbol_part = Symbol._strip_offset(symbol_part)
            return Symbol.parse(symbol_part, module)
        else:
            # Just symbol name, no module (e.g., "osq_lock_[k]")
            symbol_part = Symbol._strip_offset(sym_str)
            return Symbol.parse(symbol_part, None)

    def _load_and_parse_perf_script(self):
        """Parse standard perf script output"""
        current_sample = None
        detected_core_per_sec = False

        with open(self.file_path, 'r') as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue

                # Parse header using space-based approach
                # Format: "comm pid [cpu] timestamp: [value unit:]"
                # SPEAR format example:
                # SPEAR format example with weight value
                # Raw perf format example:
                #   "swapper     0 [001] 460661.461601:     250000 cpu-clock:ppp:"

                parts = line.strip().split()

                # Check if this is a header line (contains timestamp with colon)
                if len(parts) >= 4 and parts[3].endswith(':'):
                    # parts[0] = comm, parts[1] = pid, parts[2] = [cpu], parts[3] = timestamp:
                    if current_sample:
                        self.samples.append(current_sample)

                    comm = parts[0]
                    pid = parts[1]
                    cpu = int(parts[2].strip('[]'))  # Remove [ and ]
                    ts = float(parts[3].rstrip(':'))  # Remove trailing :

                    # Check if SPEAR format weight value is present
                    core_per_sec = None
                    if len(parts) >= 6 and parts[5] == 'core/s:':
                        core_per_sec = float(parts[4])
                        detected_core_per_sec = True
                    # Note: raw perf format has event name like "cpu-clock:ppp:" instead of "core/s:"

                    current_sample = Sample(
                        comm=comm,
                        pid=pid,
                        cpu=cpu,
                        ts=ts,
                        core_per_sec=core_per_sec,
                        stack=SymbolStack()  # Use SymbolStack instead of list
                    )
                elif current_sample and line.strip():
                    symbol = self._parse_stack_line(line)
                    if symbol:
                        current_sample.stack.append(symbol)

            if current_sample:
                self.samples.append(current_sample)

        # Set the detected flag after parsing all samples
        self._has_core_per_sec = detected_core_per_sec

    def get_time_range(self):
        """Get the time range of all samples"""
        if not self.samples:
            return (0, 0)
        return (self.samples[0].ts, self.samples[-1].ts)

    def get_filtered_samples(self, start_time=None, end_time=None, cpu_id=None, pid=None, comm=None, comm_regex=None):
        """
        Get samples filtered by time range, CPU, PID, and/or comm.

        Args:
            start_time: Include samples with timestamp >= start_time.
                       Supports: Unix timestamp, ISO 8601 (2024-01-15T10:30:00),
                       common datetime (2024-01-15 10:30:00), or date only.
            end_time: Include samples with timestamp <= end_time. Same formats as start_time.
            cpu_id: Include samples from this CPU only
            pid: Include samples from this process ID only
            comm: Include samples with exact comm match (支持多值，逗号分隔)
            comm_regex: Include samples matching comm regex pattern

        Returns:
            Filtered list of samples
        """
        filtered = self.samples

        # Parse time strings to timestamps
        start_ts = parse_time_string(start_time) if start_time is not None else None
        end_ts = parse_time_string(end_time) if end_time is not None else None

        if start_ts is not None:
            filtered = [s for s in filtered if s['ts'] >= start_ts]

        if end_ts is not None:
            filtered = [s for s in filtered if s['ts'] <= end_ts]

        if cpu_id is not None:
            filtered = [s for s in filtered if s['cpu'] == cpu_id]

        if pid is not None:
            filtered = [s for s in filtered if int(s['pid']) == pid]

        if comm is not None:
            # 支持多值，逗号分隔
            comm_list = [c.strip() for c in comm.split(',')]
            filtered = [s for s in filtered if s['comm'] in comm_list]

        if comm_regex is not None:
            pattern = re.compile(comm_regex)
            filtered = [s for s in filtered if pattern.search(s['comm'])]

        return filtered

    def get_total_core_per_sec(self, samples=None):
        """
        Calculate total CPU utilization from samples.

        Returns:
            tuple: (total_core_sec, sample_count)
            total_core_sec: Sum of sample weights
            sample_count: Number of samples processed
        """
        if samples is None:
            samples = self.samples
        total = 0.0
        count = 0
        for s in samples:
            total += self.get_sample_weight(s)
            count += 1
        return total, count

    def get_user_kernel_core_per_sec(self, samples=None) -> UserKernelStats:
        """
        Calculate user and kernel CPU utilization separately from samples.

        基于 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
        - 如果栈顶符号（leaf）的 is_kernel=True，则该样本计入 kernel
        - 否则计入 user

        Returns:
            UserKernelStats: 用户态/内核态 CPU 统计
        """
        if samples is None:
            samples = self.samples

        user_core_sec = 0.0
        kernel_core_sec = 0.0
        user_records = 0
        kernel_records = 0

        for s in samples:
            core_val = self.get_sample_weight(s)
            stack = s.get('stack')

            # 使用 SymbolStack.is_leaf_kernel 准确判断
            if stack and stack.is_leaf_kernel:
                kernel_core_sec += core_val
                kernel_records += 1
            else:
                user_core_sec += core_val
                user_records += 1

        return UserKernelStats(
            user_core_sec=user_core_sec,
            kernel_core_sec=kernel_core_sec,
            total_core_sec=user_core_sec + kernel_core_sec,
            user_records=user_records,
            kernel_records=kernel_records
        )

    def get_sample_weight(self, sample: Sample) -> float:
        """
        获取样本权重。

        Args:
            sample: Sample dataclass with 'core_per_sec' field

        Returns:
            float: Sample weight
        """
        if sample.core_per_sec is not None:
            return sample.core_per_sec
        # Raw perf format: each sample represents 1/freq weight
        return 1.0 / self.freq

    def has_core_per_sec_data(self):
        """
        检查数据是否为 SPEAR 格式

        Returns:
            bool: True if data is SPEAR format, False for raw perf format
        """
        if self._has_core_per_sec is None:
            # Auto-detect based on samples
            if self.samples:
                self._has_core_per_sec = any(
                    s.core_per_sec is not None for s in self.samples
                )
            else:
                self._has_core_per_sec = False
        return self._has_core_per_sec

    def is_kernel_symbol(self, symbol):
        """
        Check if a symbol is likely a kernel function.

        注意：此方法保留用于兼容性，新的代码应该直接使用 Symbol.is_kernel 属性。

        Args:
            symbol: Symbol object or string

        Returns:
            bool: True if kernel symbol
        """
        if isinstance(symbol, Symbol):
            return symbol.is_kernel
        if not symbol:
            return False
        # Fallback to old heuristic for string symbols
        return symbol.endswith('_[k]') or any(symbol.startswith(p) or p in symbol
                                               for p in ['_raw_', '__', 'do_', 'sys_', 'vfs_'])

    def get_cpu_utilization(self, samples=None) -> CPUUtilization:
        """
        Calculate overall CPU utilization percentage from samples.

        使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
        - User 时间：栈顶符号 is_kernel=False 的样本权重之和
        - Kernel 时间：栈顶符号 is_kernel=True 的样本权重之和

        Formula: (total_core_seconds / duration) * 100

        Returns:
            CPUUtilization: CPU 利用率结构
        """
        if samples is None:
            samples = self.samples

        if not samples:
            return CPUUtilization()

        duration = samples[-1].ts - samples[0].ts if len(samples) > 1 else 0

        # 使用新的方法获取准确的 user/kernel 分解
        uk_stats = self.get_user_kernel_core_per_sec(samples)

        total_core_sec = uk_stats.total_core_sec
        user_core_sec = uk_stats.user_core_sec
        kernel_core_sec = uk_stats.kernel_core_sec

        if duration > 0:
            total_pct = (total_core_sec / duration) * 100
            user_pct = (user_core_sec / duration) * 100
            kernel_pct = (kernel_core_sec / duration) * 100
        else:
            total_pct = user_pct = kernel_pct = 0.0

        return CPUUtilization(
            total_pct=round(total_pct, 2),
            user_pct=round(user_pct, 2),
            kernel_pct=round(kernel_pct, 2),
            total_core_seconds=round(total_core_sec, 4),
            user_core_seconds=round(user_core_sec, 4),
            kernel_core_seconds=round(kernel_core_sec, 4),
            duration=round(duration, 2),
            user_records=uk_stats.user_records,
            kernel_records=uk_stats.kernel_records
        )

    def get_duration(self, samples=None):
        """
        获取样本的时间跨度（秒）。

        Args:
            samples: 样本列表，默认使用 engine.samples

        Returns:
            float: 时间跨度（秒），如果样本不足则返回 0
        """
        if samples is None:
            samples = self.samples
        if len(samples) < 2:
            return 0.0
        return samples[-1]['ts'] - samples[0]['ts']

    def get_process_cpu_util(self, samples=None) -> Dict[tuple, ProcessCPUInfo]:
        """
        按进程聚合 CPU 利用率。

        Returns:
            Dict[(comm, pid), ProcessCPUInfo]: 进程 CPU 信息映射
        """
        if samples is None:
            samples = self.samples

        duration = self.get_duration(samples)
        if duration <= 0:
            return {}

        from collections import defaultdict
        stats = defaultdict(lambda: {'total': 0.0, 'user': 0.0, 'kernel': 0.0})

        for s in samples:
            key = (s.comm, s.pid)
            weight = self.get_sample_weight(s)
            stats[key]['total'] += weight

            stack = s.stack
            if stack and stack.is_leaf_kernel:
                stats[key]['kernel'] += weight
            else:
                stats[key]['user'] += weight

        # 转换为数据结构
        result = {}
        for key, val in stats.items():
            result[key] = ProcessCPUInfo(
                comm=key[0],
                pid=key[1],
                total_pct=(val['total'] / duration) * 100,
                user_pct=(val['user'] / duration) * 100,
                kernel_pct=(val['kernel'] / duration) * 100
            )
        return result

    def get_pid_cpu_util(self, samples=None) -> Dict[int, PidCPUInfo]:
        """
        按 PID 聚合 CPU 利用率（合并相同 PID 的不同 comm）。

        Args:
            samples: 样本列表，默认使用 engine.samples

        Returns:
            Dict[int, PidCPUInfo]: PID -> CPU 信息映射
        """
        if samples is None:
            samples = self.samples

        duration = self.get_duration(samples)
        if duration <= 0:
            return {}

        from collections import defaultdict
        stats = defaultdict(lambda: {
            'total': 0.0, 'user': 0.0, 'kernel': 0.0,
            'comm_counts': defaultdict(int), 'sample_count': 0
        })

        for s in samples:
            pid = int(s.pid)
            weight = self.get_sample_weight(s)
            stats[pid]['total'] += weight
            stats[pid]['comm_counts'][s.comm] += 1
            stats[pid]['sample_count'] += 1

            stack = s.stack
            if stack and stack.is_leaf_kernel:
                stats[pid]['kernel'] += weight
            else:
                stats[pid]['user'] += weight

        # 转换为数据结构
        result = {}
        for pid, val in stats.items():
            # 选择出现次数最多的 comm
            comm = max(val['comm_counts'].items(), key=lambda x: x[1])[0]
            result[pid] = PidCPUInfo(
                pid=pid,
                comm=comm,
                total_pct=(val['total'] / duration) * 100,
                user_pct=(val['user'] / duration) * 100,
                kernel_pct=(val['kernel'] / duration) * 100,
                sample_count=val['sample_count']
            )
        return result

    def get_comm_cpu_util(self, samples=None) -> Dict[str, CommCPUInfo]:
        """
        按进程名(comm)聚合 CPU 利用率。

        Returns:
            Dict[str, CommCPUInfo]: 进程组 CPU 信息映射
        """
        if samples is None:
            samples = self.samples

        duration = self.get_duration(samples)
        if duration <= 0:
            return {}

        from collections import defaultdict
        stats = defaultdict(lambda: {'total': 0.0, 'user': 0.0, 'kernel': 0.0, 'pids': set()})

        for s in samples:
            comm = s.comm
            stats[comm]['pids'].add(s.pid)
            weight = self.get_sample_weight(s)
            stats[comm]['total'] += weight

            stack = s.stack
            if stack and stack.is_leaf_kernel:
                stats[comm]['kernel'] += weight
            else:
                stats[comm]['user'] += weight

        # 转换为数据结构
        result = {}
        for comm, val in stats.items():
            result[comm] = CommCPUInfo(
                comm=comm,
                total_pct=(val['total'] / duration) * 100,
                user_pct=(val['user'] / duration) * 100,
                kernel_pct=(val['kernel'] / duration) * 100,
                pid_count=len(val['pids']),
                pids=val['pids']
            )
        return result

    def get_symbol_cpu_util(self, samples=None, comm: Optional[str] = None, pid: Optional[int] = None) -> SymbolCPUInfo:
        """
        按符号聚合 CPU 利用率（self 和 inclusive）。

        Args:
            samples: 样本列表，默认使用 engine.samples
            comm: 可选，按进程名过滤
            pid: 可选，按 PID 过滤

        Returns:
            SymbolCPUInfo: 符号级 CPU 信息
        """
        if samples is None:
            samples = self.samples

        # 应用过滤条件
        if comm:
            samples = [s for s in samples if s.comm == comm]
        if pid:
            samples = [s for s in samples if int(s.pid) == pid]

        from collections import defaultdict
        self_core_sec = defaultdict(float)
        incl_core_sec = defaultdict(float)

        for s in samples:
            stack = s.stack
            if not stack or len(stack) == 0:
                continue

            weight = self.get_sample_weight(s)
            normalized_names = stack.get_normalized_names()

            # Self: 栈顶符号
            self_core_sec[normalized_names[0]] += weight

            # Inclusive: 栈中所有唯一符号
            seen = set()
            for sym in normalized_names:
                if sym not in seen:
                    incl_core_sec[sym] += weight
                    seen.add(sym)

        total_self_core_sec = sum(self_core_sec.values())

        # 计算百分比（相对于 total_self，确保 inclusive >= self）
        self_pct = {}
        incl_pct = {}
        for sym in set(list(self_core_sec.keys()) + list(incl_core_sec.keys())):
            self_pct[sym] = (self_core_sec[sym] / total_self_core_sec * 100) if total_self_core_sec > 0 else 0
            incl_pct[sym] = (incl_core_sec[sym] / total_self_core_sec * 100) if total_self_core_sec > 0 else 0

        return SymbolCPUInfo(
            self_pct=self_pct,
            inclusive_pct=incl_pct,
            core_sec=dict(incl_core_sec),
            self_core_sec=dict(self_core_sec),
            total_core_sec=total_self_core_sec
        )

    def get_core_cpu_util(self, samples=None) -> Dict[int, CoreCPUInfo]:
        """
        按 CPU 核心聚合利用率。

        Returns:
            Dict[int, CoreCPUInfo]: 核心 CPU 信息映射
        """
        if samples is None:
            samples = self.samples

        duration = self.get_duration(samples)
        if duration <= 0:
            return {}

        from collections import defaultdict
        stats = defaultdict(lambda: {'total': 0.0, 'kernel': 0.0})

        for s in samples:
            cpu_id = s.cpu
            if cpu_id is None:
                continue
            weight = self.get_sample_weight(s)
            stats[cpu_id]['total'] += weight

            stack = s.stack
            if stack and stack.is_leaf_kernel:
                stats[cpu_id]['kernel'] += weight

        # 转换为数据结构
        result = {}
        for cpu_id, val in stats.items():
            total_pct = (val['total'] / duration) * 100
            kernel_pct = (val['kernel'] / duration) * 100
            result[cpu_id] = CoreCPUInfo(
                cpu_id=cpu_id,
                total_pct=total_pct,
                kernel_pct=kernel_pct,
                user_pct=total_pct - kernel_pct
            )
        return result

    # =============================================================================
    # Week 1 New Interfaces - Three Tier Architecture
    # =============================================================================

    def get_process_lifecycle(self, samples=None, comm=None) -> ProcessLifecycle:
        """
        获取进程生命周期信息。

        Args:
            samples: 样本列表，默认使用 engine.samples
            comm: 可选，指定进程名过滤

        Returns:
            ProcessLifecycle: 进程生命周期信息
        """
        if samples is None:
            samples = self.samples

        # 按 comm 过滤
        if comm:
            samples = [s for s in samples if s.comm == comm]

        if not samples:
            return ProcessLifecycle()

        # 按时间排序
        sorted_samples = sorted(samples, key=lambda s: s.ts)
        duration = self.get_duration(sorted_samples)

        # 追踪每个 PID 的出现和消失，同时记录首次出现时的调用栈
        pid_first_seen = {}
        pid_last_seen = {}
        pid_comm = {}
        pid_first_stack = {}  # 记录首次出现时的栈

        for s in sorted_samples:
            pid = s.pid
            ts = s.ts
            pid_comm[pid] = s.comm

            if pid not in pid_first_seen:
                pid_first_seen[pid] = ts
                # 记录首次出现时的调用栈
                stack = s.stack
                if stack:
                    pid_first_stack[pid] = stack.get_normalized_names()
                else:
                    pid_first_stack[pid] = []
            pid_last_seen[pid] = ts

        # 生成 spawn/exit 事件（使用 dict 表示，包含 stack 信息）
        spawn_events = [
            {
                "pid": pid,
                "comm": pid_comm[pid],
                "timestamp": first_ts,
                "type": "spawn",
                "stack": pid_first_stack.get(pid, [])
            }
            for pid, first_ts in pid_first_seen.items()
        ]

        exit_events = [
            {
                "pid": pid,
                "comm": pid_comm[pid],
                "timestamp": last_ts,
                "type": "exit",
                "stack": []  # exit 事件通常没有栈信息
            }
            for pid, last_ts in pid_last_seen.items()
        ]

        # 计算 spawn_rate（基于时间窗口内的不同PID数量）
        spawn_rate = len(pid_first_seen) / duration if duration > 0 else 0.0

        # 按时间排序事件
        spawn_events.sort(key=lambda e: e["timestamp"])
        exit_events.sort(key=lambda e: e["timestamp"])

        # 统计信息
        lifecycle_stats = LifecycleStats(
            total_unique_pids=len(pid_first_seen),
            duration_sec=duration,
            avg_lifetime_sec=duration / len(pid_first_seen) if pid_first_seen else 0.0
        )

        return ProcessLifecycle(
            spawn_events=spawn_events,
            exit_events=exit_events,
            spawn_rate=spawn_rate,
            lifecycle_stats=lifecycle_stats
        )

    def get_pid_cpu_distribution(self, samples=None, comm=None) -> Dict[int, float]:
        """
        获取指定 comm 下各 PID 的 CPU 分布。

        Args:
            samples: 样本列表，默认使用 engine.samples
            comm: 进程名，用于过滤样本

        Returns:
            {pid: cpu_percent, ...} 用于计算 CV 和 Monopoly
        """
        if samples is None:
            samples = self.samples

        # 按 comm 过滤
        if comm:
            samples = [s for s in samples if s.comm == comm]

        if not samples:
            return {}

        duration = self.get_duration(samples)
        if duration <= 0:
            return {}

        # 按 PID 聚合 CPU 时间
        from collections import defaultdict
        pid_cpu_time = defaultdict(float)

        for s in samples:
            pid = int(s.pid)
            weight = self.get_sample_weight(s)
            pid_cpu_time[pid] += weight

        # 转换为百分比
        result = {}
        for pid, cpu_time in pid_cpu_time.items():
            result[pid] = (cpu_time / duration) * 100

        return result

    def get_call_graph(self, samples=None, target_symbol=None, comm=None) -> CallGraph:
        """
        获取调用图。

        Args:
            samples: 样本列表，默认使用 engine.samples
            target_symbol: 目标符号名，用于过滤包含该符号的调用链
            comm: 可选，指定进程名过滤

        Returns:
            CallGraph: 调用图数据结构
        """
        if samples is None:
            samples = self.samples

        # 按 comm 过滤
        if comm:
            samples = [s for s in samples if s.comm == comm]

        if not samples:
            return CallGraph()

        from collections import defaultdict

        # 统计调用关系
        caller_counts = defaultdict(int)
        caller_weight = defaultdict(float)
        path_counts = defaultdict(int)

        for s in samples:
            stack = s.stack
            if not stack or len(stack) == 0:
                continue

            weight = self.get_sample_weight(s)
            normalized_names = stack.get_normalized_names()

            # 如果指定了目标符号，只处理包含该符号的调用链
            if target_symbol and target_symbol not in normalized_names:
                continue

            # 记录调用路径
            path_key = " -> ".join(normalized_names[:5])  # 最多5层
            path_counts[path_key] += 1

            # 记录调用关系（每个符号调用栈中它下面的符号）
            for i in range(len(normalized_names) - 1):
                caller = normalized_names[i + 1]
                callee = normalized_names[i]
                caller_counts[(caller, callee)] += 1
                caller_weight[(caller, callee)] += weight

        # 生成调用者列表
        callers = []
        seen_callers = set()
        for (caller, callee), count in caller_counts.items():
            if caller not in seen_callers:
                seen_callers.add(caller)
                callers.append(CallerInfo(
                    symbol=caller,
                    call_count=sum(c for (c, cal) in caller_counts.items() if c == caller),
                    total_weight=sum(w for (c, cal), w in caller_weight.items() if c == caller)
                ))

        # 按调用次数排序
        callers.sort(key=lambda x: x.call_count, reverse=True)

        # 生成调用图（邻接表形式）
        call_graph = defaultdict(list)
        for (caller, callee), count in caller_counts.items():
            call_graph[caller].append(CallEdge(
                callee=callee,
                count=count,
                weight=caller_weight[(caller, callee)]
            ))

        # 热点路径（出现频率最高的调用链）
        hot_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)
        hot_paths = [path for path, count in hot_paths[:10]]  # 前10条

        return CallGraph(
            callers=callers[:20],  # 最多返回20个调用者
            call_graph=dict(call_graph),
            hot_paths=hot_paths
        )
