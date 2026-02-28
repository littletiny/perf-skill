#!/usr/bin/env python3
"""
Parse test2.data format:
  JSON with {"data": "timestamp:comm:pid:cpuid;sym0;sym1... core/s\n..."}
  
Sample format inside data field:
  123.15:containerd-shim:2350748:0;sym0;sym1... core/s
  
Fields:
  - timestamp (float)
  - comm (command name)
  - pid (process ID)
  - cpuid (CPU ID)
  - callstack (semicolon-separated symbols)
  - core_s (core/s value at the end)
"""

import json
import re
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Sample:
    """Single perf sample"""
    timestamp: float
    comm: str
    pid: int
    cpuid: int
    callstack: List[str]
    core_s: float
    
    def __repr__(self):
        return (f"Sample(ts={self.timestamp:.6f}, comm='{self.comm}', pid={self.pid}, "
                f"cpu={self.cpuid}, core_s={self.core_s}, stack_depth={len(self.callstack)})")


class Test2Parser:
    """Parser for test2.data JSON format"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.samples: List[Sample] = []
        self.raw_data: Optional[str] = None
        
    def load(self) -> 'Test2Parser':
        """Load and parse the JSON file"""
        with open(self.filepath, 'r') as f:
            data = json.load(f)
        self.raw_data = data.get('data', '')
        return self
    
    def parse(self) -> List[Sample]:
        """Parse all samples from the data field"""
        if self.raw_data is None:
            self.load()
            
        self.samples = []
        # Split by literal \n or actual newline
        raw_samples = re.split(r'\\n|\n', self.raw_data)
        
        for raw in raw_samples:
            raw = raw.strip()
            if not raw or raw == '...':
                continue
                
            sample = self._parse_sample(raw)
            if sample:
                self.samples.append(sample)
                
        return self.samples
    
    def _parse_sample(self, raw: str) -> Optional[Sample]:
        """Parse a single sample string"""
        # Format: timestamp:comm:pid:cpuid;sym0;sym1... core/s
        # core/s is at the end, separated by space
        
        match = re.match(r'^([\d.]+):([^:]+):(\d+):(\d+);(.+)\s+([\d.]+)$', raw.strip())
        if not match:
            return None
            
        timestamp = float(match.group(1))
        comm = match.group(2)
        pid = int(match.group(3))
        cpuid = int(match.group(4))
        
        # Split callstack by semicolon
        callstack_str = match.group(5)
        callstack = [s.strip() for s in callstack_str.split(';') if s.strip()]
        
        core_s = float(match.group(6))
        
        return Sample(
            timestamp=timestamp,
            comm=comm,
            pid=pid,
            cpuid=cpuid,
            callstack=callstack,
            core_s=core_s
        )
    
    def get_stats(self) -> dict:
        """Get summary statistics"""
        if not self.samples:
            self.parse()
            
        if not self.samples:
            return {}
            
        total_core_s = sum(s.core_s for s in self.samples)
        avg_core_s = total_core_s / len(self.samples)
        
        # Group by comm
        by_comm = {}
        by_pid = {}
        for s in self.samples:
            by_comm[s.comm] = by_comm.get(s.comm, 0) + s.core_s
            by_pid[s.pid] = by_pid.get(s.pid, 0) + s.core_s
            
        return {
            'total_records': len(self.samples),
            'total_core_s': total_core_s,
            'avg_core_s': avg_core_s,
            'min_core_s': min(s.core_s for s in self.samples),
            'max_core_s': max(s.core_s for s in self.samples),
            'unique_commands': len(by_comm),
            'unique_pids': len(by_pid),
            'by_comm': by_comm,
            'by_pid': by_pid,
        }
    
    def print_summary(self):
        """Print formatted summary"""
        stats = self.get_stats()
        if not stats:
            print("No samples found")
            return
            
        print("=" * 60)
        print("PERF DATA SUMMARY")
        print("=" * 60)
        print(f"Total Records:     {stats['total_records']}")
        print(f"Total core/s:      {stats['total_core_s']:.4f}")
        print(f"Average core/s:    {stats['avg_core_s']:.4f}")
        print(f"Min core/s:        {stats['min_core_s']:.4f}")
        print(f"Max core/s:        {stats['max_core_s']:.4f}")
        print(f"Unique Commands:   {stats['unique_commands']}")
        print(f"Unique PIDs:       {stats['unique_pids']}")
        print()
        print("core/s by Command:")
        print("-" * 40)
        for comm, core_s in sorted(stats['by_comm'].items(), key=lambda x: -x[1]):
            print(f"  {comm:<25} {core_s:>10.4f}")
        print()
        print("core/s by PID:")
        print("-" * 40)
        for pid, core_s in sorted(stats['by_pid'].items(), key=lambda x: -x[1]):
            print(f"  {pid:<10} {core_s:>10.4f}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <test2.data>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    parser = Test2Parser(filepath)
    parser.parse()
    parser.print_summary()
    
    # Optional: print first few samples
    print()
    print("=" * 60)
    print("FIRST 3 SAMPLES")
    print("=" * 60)
    for s in parser.samples[:3]:
        print(f"\n{s}")
        print(f"  Callstack ({len(s.callstack)} frames):")
        for i, sym in enumerate(s.callstack[:5]):
            print(f"    {i}: {sym}")
        if len(s.callstack) > 5:
            print(f"    ... and {len(s.callstack)-5} more")


if __name__ == '__main__':
    main()
