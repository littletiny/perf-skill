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
    """基础用法示例"""
    print("=== 基础标签用法 ===")
    
    # 阻塞级问题
    print(x0("检测到锁竞争: pthread_mutex_lock"))
    
    # 重要级提示
    print(x1("单核饱和度超过 80%"))
    
    # 一般提示
    print(x2("建议关注内存分配热点"))
    
    # 操作建议
    print(xa("执行 deep analysis", "bottleneck-trace --comm myapp"))
    print()


def example_conditional_tags():
    """条件标签示例"""
    print("=== 条件标签用法 ===")
    
    cpu_util = 85
    
    # 只在条件满足时添加标签
    message = x0_if(cpu_util > 80, f"CPU 利用率过高: {cpu_util}%")
    print(message)
    
    # 带 fallback 的条件标签
    kernel_ratio = 30
    msg = x1_if(
        kernel_ratio > 50,
        f"内核态占比异常: {kernel_ratio}%",
        fallback=f"系统状态正常 (内核态 {kernel_ratio}%)"
    )
    print(msg)
    print()


def example_prebuilt_alerts():
    """预置警报函数示例"""
    print("=== 预置警报函数 ===")
    
    print(alert_lock("pthread_mutex_lock"))
    print(alert_saturation(cpu_id=3, util=92.5, monopoly=0.85))
    print(hint_find_callers("malloc"))
    print()


def example_real_world():
    """实际诊断场景示例"""
    print("=== 实际诊断场景 ===")
    
    # 模拟分析结果
    issues = []
    
    # 检测锁竞争
    lock_hotspot = True
    if lock_hotspot:
        issues.append(x0("锁竞争: __pthread_mutex_lock 占用 45% CPU"))
    
    # 检测单核饱和
    cpu_saturation = True
    if cpu_saturation:
        issues.append(x0("单核饱和: CPU7 利用率 95%"))
    
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
