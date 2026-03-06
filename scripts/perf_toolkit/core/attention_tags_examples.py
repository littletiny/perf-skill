#!/usr/bin/env python3
"""
Attention Tags 使用示例

展示如何在诊断输出中使用 X0/X1/X2/XA 标签系统。
"""

from perf_toolkit.core.attention_tags import (
    x0, x1, x2, xa,
    x0_if, x1_if, xa_if,
    alert_lock, alert_saturation, hint_find_callers,
)


def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Tag Usage ===")
    
    # Critical issue
    print(x0("Lock contention detected: pthread_mutex_lock"))
    
    # Important hint
    print(x1("Single-core saturation exceeds 80%"))
    
    # General hint
    print(x2("Consider monitoring memory allocation hotspots"))
    
    # Action suggestion
    print(xa("Execute deep analysis", "bottleneck-trace --comm myapp"))
    print()


def example_conditional_tags():
    """Conditional tag example"""
    print("=== Conditional Tag Usage ===")
    
    cpu_util = 85
    
    # Only add tag when condition is met
    message = x0_if(cpu_util > 80, f"High CPU utilization: {cpu_util}%")
    print(message)
    
    # Conditional tag with fallback
    kernel_ratio = 30
    msg = x1_if(
        kernel_ratio > 50,
        f"Abnormal kernel ratio: {kernel_ratio}%",
        fallback=f"System normal (kernel ratio {kernel_ratio}%)"
    )
    print(msg)
    print()


def example_prebuilt_alerts():
    """Prebuilt alert functions example"""
    print("=== Prebuilt Alert Functions ===")
    
    print(alert_lock("pthread_mutex_lock"))
    print(alert_saturation(cpu_id=3, util=92.5, monopoly=0.85))
    print(hint_find_callers("malloc"))
    print()


def example_real_world():
    """Real-world diagnostic scenario example"""
    print("=== Real-World Diagnostic Scenarios ===")
    
    # Simulated analysis results
    issues = []
    
    # Detect lock contention
    lock_hotspot = True
    if lock_hotspot:
        issues.append(x0("Lock contention: __pthread_mutex_lock uses 45% CPU"))
    
    # Detect single-core saturation
    cpu_saturation = True
    if cpu_saturation:
        issues.append(x0("Single-core saturation: CPU7 utilization 95%"))
    
    # 检测内存分配热点
    mem_alloc_heavy = True
    if mem_alloc_heavy:
        issues.append(x1("内存分配热点: malloc 进入 Top 10"))
        issues.append(xa("建议执行", "find-callers --target malloc"))
    
    for issue in issues:
        print(issue)


if __name__ == "__main__":
    example_basic_usage()
    example_conditional_tags()
    example_prebuilt_alerts()
    example_real_world()
