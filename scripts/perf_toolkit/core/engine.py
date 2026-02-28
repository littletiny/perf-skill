#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerfExpert Engine - Core parsing and data management

使用 Symbol 结构感知 kernel/user 符号差异：
- 原始数据中 kernel 函数带有 `_[k]` 后缀
- Symbol 类在解析时保留这一信息，提供准确的 is_kernel 属性
- 利用率计算基于 Symbol.is_kernel，而非启发式规则
"""

import json
import re
from collections import defaultdict
from .symbol import Symbol, SymbolStack


class PerfExpertEngine:
    """
    Main engine for parsing and analyzing perf script output.
    
    Parses perf script format with core/s values:
        <comm> <pid> [<cpu>] <timestamp>: <core_per_sec> core/s:
                           <symbol> (<module>)
                           ...
    
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
    
    def __init__(self, file_path):
        """
        Initialize engine with perf script file.
        
        Args:
            file_path: Path to perf script output file
        """
        self.file_path = file_path
        self.samples = []
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
        """Parse perf script standard output with core/s values"""
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
          {"data": "timestamp:comm:pid:cpuid;sym0;sym1... core/s\\n..."}
        
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
          - colon style: timestamp:comm:pid:cpuid;sym0;sym1... core/s
          - pipe style:  timestamp:comm|pid|cpuid;sym0;sym1... core/s
                         or timestamp|comm|pid|cpuid;sym0;sym1... core/s
        
        Note: comm may contain colons (e.g., "runc:[2:INIT]"), so we parse from right to left
        using the fact that pid and cpuid are pure numbers as anchors.
        """
        line = raw.strip()
        
        # Step 1: Extract core/s value (last space-separated number)
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
        
        return {
            "comm": comm,
            "tid": pid,
            "cpu": cpuid,
            "ts": timestamp,
            "core_per_sec": core_per_sec,
            "stack": stack
        }
    
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
        """Parse standard perf script output with core/s values"""
        current_sample = None
        
        with open(self.file_path, 'r') as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                
                # Parse header using space-based approach
                # Format: "comm tid [cpu] timestamp: [value unit:]"
                # Examples:
                #   "perf-exec  215053 [002] 368330.780793:     0.0526 core/s:"
                #   "containerd-shim  2350748 [0] 0.000000:     0.0526 core/s:"
                
                parts = line.strip().split()
                
                # Check if this is a header line (contains timestamp with colon)
                if len(parts) >= 4 and parts[3].endswith(':'):
                    # parts[0] = comm, parts[1] = tid, parts[2] = [cpu], parts[3] = timestamp:
                    if current_sample:
                        self.samples.append(current_sample)
                    
                    comm = parts[0]
                    tid = parts[1]
                    cpu = int(parts[2].strip('[]'))  # Remove [ and ]
                    ts = float(parts[3].rstrip(':'))  # Remove trailing :
                    
                    # Check if core/s value is present (parts[4] = value, parts[5] = "core/s:")
                    core_per_sec = None
                    if len(parts) >= 6 and parts[5] == 'core/s:':
                        core_per_sec = float(parts[4])
                    
                    current_sample = {
                        "comm": comm,
                        "tid": tid,
                        "cpu": cpu,
                        "ts": ts,
                        "core_per_sec": core_per_sec,
                        "stack": SymbolStack()  # Use SymbolStack instead of list
                    }
                elif current_sample and line.strip():
                    symbol = self._parse_stack_line(line)
                    if symbol:
                        current_sample["stack"].append(symbol)
            
            if current_sample:
                self.samples.append(current_sample)
    
    def get_duration(self):
        """Get total duration of samples"""
        if not self.samples:
            return 0
        return self.samples[-1]['ts'] - self.samples[0]['ts']
    
    def get_time_range(self):
        """Get the time range of all samples"""
        if not self.samples:
            return (0, 0)
        return (self.samples[0]['ts'], self.samples[-1]['ts'])
    
    def get_filtered_samples(self, start_time=None, end_time=None, cpu_id=None, pid=None, comm=None, comm_regex=None):
        """
        Get samples filtered by time range, CPU, PID, and/or comm.
        
        Args:
            start_time: Include samples with timestamp >= start_time
            end_time: Include samples with timestamp <= end_time
            cpu_id: Include samples from this CPU only
            pid: Include samples from this process ID only
            comm: Include samples with exact comm match (支持多值，逗号分隔)
            comm_regex: Include samples matching comm regex pattern
            
        Returns:
            Filtered list of samples
        """
        filtered = self.samples
        
        if start_time is not None:
            filtered = [s for s in filtered if s['ts'] >= start_time]
        
        if end_time is not None:
            filtered = [s for s in filtered if s['ts'] <= end_time]
        
        if cpu_id is not None:
            filtered = [s for s in filtered if s['cpu'] == cpu_id]
        
        if pid is not None:
            filtered = [s for s in filtered if int(s['tid']) == pid]
        
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
        Calculate total core/s from samples.
        
        Returns:
            tuple: (total_core_per_sec, count_with_core_data)
            total_core_per_sec: Sum of core/s values (represents CPU core-seconds consumed)
            count: Number of samples that have core/s data
        """
        if samples is None:
            samples = self.samples
        total = 0.0
        count = 0
        for s in samples:
            if s.get('core_per_sec') is not None:
                total += s['core_per_sec']
                count += 1
        return total, count
    
    def get_user_kernel_core_per_sec(self, samples=None):
        """
        Calculate user and kernel core/s separately from samples.
        
        基于 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
        - 如果栈顶符号（leaf）的 is_kernel=True，则该样本计入 kernel
        - 否则计入 user
        
        Returns:
            dict: {
                'user_core_sec': user mode core-seconds,
                'kernel_core_sec': kernel mode core-seconds,
                'total_core_sec': total core-seconds,
                'user_samples': number of user samples,
                'kernel_samples': number of kernel samples
            }
        """
        if samples is None:
            samples = self.samples
        
        user_core_sec = 0.0
        kernel_core_sec = 0.0
        user_samples = 0
        kernel_samples = 0
        
        for s in samples:
            core_val = s.get('core_per_sec') or 0
            stack = s.get('stack')
            
            # 使用 SymbolStack.is_leaf_kernel 准确判断
            if stack and stack.is_leaf_kernel:
                kernel_core_sec += core_val
                kernel_samples += 1
            else:
                user_core_sec += core_val
                user_samples += 1
        
        return {
            'user_core_sec': user_core_sec,
            'kernel_core_sec': kernel_core_sec,
            'total_core_sec': user_core_sec + kernel_core_sec,
            'user_samples': user_samples,
            'kernel_samples': kernel_samples
        }
    
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
    
    def get_cpu_utilization(self, samples=None):
        """
        Calculate overall CPU utilization percentage from samples.
        
        使用 Symbol.is_kernel 属性准确区分 user 和 kernel 时间：
        - User 时间：栈顶符号 is_kernel=False 的样本 core/s 之和
        - Kernel 时间：栈顶符号 is_kernel=True 的样本 core/s 之和
        
        Formula: (total_core_seconds / duration) * 100
        
        Returns:
            dict: {
                'total_pct': total CPU utilization %,
                'user_pct': user mode %,
                'kernel_pct': kernel mode %,
                'total_core_seconds': total core-seconds consumed,
                'user_core_seconds': user core-seconds,
                'kernel_core_seconds': kernel core-seconds,
                'duration': duration in seconds,
                'user_samples': user sample count,
                'kernel_samples': kernel sample count
            }
        """
        if samples is None:
            samples = self.samples
        
        if not samples:
            return {
                'total_pct': 0.0,
                'user_pct': 0.0,
                'kernel_pct': 0.0,
                'total_core_seconds': 0.0,
                'user_core_seconds': 0.0,
                'kernel_core_seconds': 0.0,
                'duration': 0.0,
                'user_samples': 0,
                'kernel_samples': 0
            }
        
        duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
        
        # 使用新的方法获取准确的 user/kernel 分解
        uk_stats = self.get_user_kernel_core_per_sec(samples)
        
        total_core_sec = uk_stats['total_core_sec']
        user_core_sec = uk_stats['user_core_sec']
        kernel_core_sec = uk_stats['kernel_core_sec']
        
        if duration > 0:
            total_pct = (total_core_sec / duration) * 100
            user_pct = (user_core_sec / duration) * 100
            kernel_pct = (kernel_core_sec / duration) * 100
        else:
            total_pct = user_pct = kernel_pct = 0.0
        
        return {
            'total_pct': round(total_pct, 2),
            'user_pct': round(user_pct, 2),
            'kernel_pct': round(kernel_pct, 2),
            'total_core_seconds': round(total_core_sec, 4),
            'user_core_seconds': round(user_core_sec, 4),
            'kernel_core_seconds': round(kernel_core_sec, 4),
            'duration': round(duration, 2),
            'user_samples': uk_stats['user_samples'],
            'kernel_samples': uk_stats['kernel_samples']
        }
