#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHECR Diagnostic Toolkit - CLI Entry Point

This is the unified entry point for the perf toolkit.
All CLI logic has been moved to perf_toolkit/cli/ directory.

Architecture:
  scripts/perf_toolkit/
  ├── cli/
  │   ├── decorators.py      - @command decorator
  │   ├── builders.py        - OutputBuilder
  │   ├── main.py            - Argument parsing & routing
  │   └── commands/
  │       ├── analysis/      - Analysis commands (B负责)
  │       ├── composite/     - Composite commands (B负责)
  │       ├── trace/         - Trace commands (C负责)
  │       └── env/           - Environment commands (C负责)
"""

import sys
import os

# Add perf_toolkit to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from perf_toolkit.cli.main import main

if __name__ == "__main__":
    main()
