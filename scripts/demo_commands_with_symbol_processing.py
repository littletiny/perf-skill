#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示 find-callers 和 cluster-paths 使用 Symbol Processing 的效果

此脚本展示命令如何自动应用：
- hidden: 隐藏运行时函数
- merge_up: 向上合并中间层
- merge_down: 向下合并 syscall 包装器
- collapse: 折叠符号组
- normalize: 截断为 classname::method
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.defaults import get_symbol_rules, ProcessedStack


def demo_find_callers_effect():
    """演示 find-callers 的 symbol processing 效果"""
    print("=" * 70)
    print("Demo: find-callers Symbol Processing Effect")
    print("=" * 70)
    
    # 模拟 find-callers 会处理的调用栈
    # 目标函数: MyService::ProcessRequest
    raw_call_stacks = [
        # 调用栈1: 通过线程池
        [
            "MyService::ProcessRequest",
            "ThreadPool::WorkerThread",
            "std::thread::_State_impl::_M_run",
            "execute_native_thread_routine",
            "start_thread",
            "__clone",
            "main",
            "__libc_start_main",
        ],
        # 调用栈2: 通过 epoll_wait
        [
            "MyService::ProcessRequest",
            "EventLoop::Wait",
            "__GI___epoll_wait",
            "syscall",
            "entry_SYSCALL_64",
            "do_syscall_64",
            "__x64_sys_epoll_wait",
            "main",
            "__libc_start_main",
        ],
        # 调用栈3: 使用 mutex
        [
            "MyService::ProcessRequest",
            "DataCache::Get",
            "pthread_mutex_lock",
            "pthread_mutex_unlock",
            "malloc",
            "free",
            "main",
        ],
    ]
    
    rules = get_symbol_rules()
    
    print("\nRaw caller stacks (before processing):")
    for i, stack in enumerate(raw_call_stacks, 1):
        # 跳过目标函数，只显示调用者
        callers = stack[1:]
        print(f"  Stack {i}: {' <- '.join(callers[:5])}...")
    
    print("\nProcessed caller stacks (after symbol processing):")
    for i, stack in enumerate(raw_call_stacks, 1):
        # 跳过目标函数，只显示调用者
        callers = stack[1:]
        processed = rules.process_stack(callers)
        print(f"  Stack {i}: {' <- '.join(processed.processed_stack)}")
        print(f"           ({processed.get_summary()})")
    
    print("\nBenefits for find-callers:")
    print("  - Hidden runtime functions (start_thread, __clone) are removed")
    print("  - Syscall wrappers are merged into actual syscalls")
    print("  - pthread/malloc operations are collapsed into groups")
    print("  - Long C++ namespaces are normalized to Class::method")
    print()


def demo_cluster_paths_effect():
    """演示 cluster-paths 的 symbol processing 效果"""
    print("=" * 70)
    print("Demo: cluster-paths Symbol Processing Effect")
    print("=" * 70)
    
    # 模拟 cluster-paths 会处理的多个调用栈
    raw_stacks = [
        [
            "business::Handler::Process",
            "ThreadPool::Execute",
            "std::thread::_M_run",
            "execute_native_thread_routine",
            "start_thread",
            "__clone",
        ],
        [
            "business::Handler::Validate",
            "ThreadPool::Execute", 
            "std::thread::_M_run",
            "execute_native_thread_routine",
            "start_thread",
            "__clone",
        ],
        [
            "business::Handler::Process",
            "ThreadPool::Execute",
            "std::thread::_M_run",
            "execute_native_thread_routine",
            "start_thread",
            "__clone",
        ],
        [
            "io::Handler::Read",
            "EventLoop::Poll",
            "__GI___epoll_wait",
            "syscall",
            "entry_SYSCALL_64",
            "do_syscall_64",
        ],
        [
            "io::Handler::Write",
            "EventLoop::Poll",
            "__GI___epoll_wait",
            "syscall",
            "entry_SYSCALL_64",
            "do_syscall_64",
        ],
    ]
    
    rules = get_symbol_rules()
    
    print("\nRaw stacks for clustering:")
    for i, stack in enumerate(raw_stacks, 1):
        print(f"  Stack {i}: {' -> '.join(reversed(stack))}")
    
    print("\nProcessed stacks (after symbol processing):")
    processed_stacks = []
    for i, stack in enumerate(raw_stacks, 1):
        processed = rules.process_stack(stack)
        processed_stacks.append(processed.processed_stack)
        print(f"  Stack {i}: {' -> '.join(reversed(processed.processed_stack))}")
    
    # 手动模拟聚类效果
    print("\nClustering result (with symbol processing):")
    # Stack 1, 2, 3 应该聚为一类（都经过 ThreadPool::Execute）
    # Stack 4, 5 应该聚为一类（都经过 EventLoop::Poll）
    print("  Cluster 1: business::Handler::{Process,Validate} -> ThreadPool::Execute")
    print("             (3 samples, hidden: 3, merged_up: 2)")
    print("  Cluster 2: io::Handler::{Read,Write} -> EventLoop::Poll")
    print("             (2 samples, merged_down: 4)")
    
    print("\nBenefits for cluster-paths:")
    print("  - Runtime noise is filtered out, revealing true business patterns")
    print("  - Syscall paths are simplified, grouping by actual I/O operations")
    print("  - More accurate clustering due to normalized symbol names")
    print()


def demo_comparison():
    """对比使用和不使用 symbol processing 的差异"""
    print("=" * 70)
    print("Demo: With vs Without Symbol Processing")
    print("=" * 70)
    
    test_stack = [
        "MyApp::Service::HandleRequest",
        "ThreadPool::WorkerLoop",
        "std::thread::_State_impl::_M_run",
        "execute_native_thread_routine",
        "start_thread",
        "__clone",
        "main",
        "__libc_start_main",
    ]
    
    rules = get_symbol_rules()
    
    print("\nOriginal stack:")
    print(f"  {' <- '.join(test_stack)}")
    
    # 不使用 symbol processing
    print("\nWithout symbol processing:")
    print(f"  Target: {test_stack[0]}")
    print(f"  Callers: {' <- '.join(test_stack[1:])}")
    print(f"  Length: {len(test_stack[1:])} frames")
    
    # 使用 symbol processing
    processed = rules.process_stack(test_stack[1:])  # 跳过目标函数
    print("\nWith symbol processing:")
    print(f"  Target: {test_stack[0]}")  # 目标函数不变
    print(f"  Callers: {' <- '.join(processed.processed_stack)}")
    print(f"  Length: {len(processed.processed_stack)} frames")
    print(f"  Summary: {processed.get_summary()}")
    
    reduction = (1 - len(processed.processed_stack) / len(test_stack[1:])) * 100
    print(f"\n  Reduction: {reduction:.1f}% fewer frames to analyze")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Command Symbol Processing Demo")
    print("Shows how find-callers and cluster-paths benefit from symbol processing")
    print("=" * 70 + "\n")
    
    demo_find_callers_effect()
    demo_cluster_paths_effect()
    demo_comparison()
    
    print("\n" + "=" * 70)
    print("Demo completed!")
    print("All commands now automatically apply symbol processing rules.")
    print("=" * 70)
