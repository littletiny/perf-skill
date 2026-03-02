#!/usr/bin/env python3
"""
三层架构集成测试包

使用方式:
    # 运行快速测试
    python3 -m tests.three_tier.quick_test
    
    # 运行完整测试
    python3 -m tests.three_tier.run_all_tests
"""

__version__ = "1.0.0"
__all__ = [
    'verify_interfaces',
    'quick_test',
    'run_all_tests',
]
