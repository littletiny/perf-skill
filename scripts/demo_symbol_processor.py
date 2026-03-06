#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Processor Demo - 符号处理演示

功能演示：
1. hidden: 隐藏特定符号
2. collapse: 折叠符号组
3. normalize: 截断为 ClassName::method
4. 命令集成效果 (find-callers, cluster-paths)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.defaults import get_symbol_rules, ProcessedStack


def demo_basic_processing():
    """基本处理演示"""
    print("=" * 60)
    print("Demo 1: Basic Symbol Processing")
    print("=" * 60)
    
    stack = [
        "FindInTableWithLock", "InsertWithProb",
        "malloc", "__libc_malloc",
        "syscall", "__x64_sys_read",
        "pthread_mutex_lock", "start_thread", "__clone",
        "main", "__libc_start_main",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack:")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\n{processed.get_summary()}")


def demo_normalize():
    """规范化演示"""
    print("\n" + "=" * 60)
    print("Demo 2: Symbol Normalization")
    print("=" * 60)
    
    stack = [
        "parameter_server::optimizer::AdamOptimizer::ComputeGradient",
        "std::vector<std::string>::push_back",
        "tensorflow::Tensor::FromProto",
        "plain_function",
    ]
    
    print("\nOriginal:")
    for i, sym in enumerate(stack):
        print(f"  [{i}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nNormalized:")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i}] {sym}")


def demo_collapse_groups():
    """折叠组演示"""
    print("\n" + "=" * 60)
    print("Demo 3: Collapse Groups")
    print("=" * 60)
    
    stack = [
        "business_logic", "pthread_mutex_lock", "pthread_cond_wait",
        "malloc", "free", "business_logic_2"
    ]
    
    print("\nOriginal:")
    print(f"  {' -> '.join(stack)}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed:")
    print(f"  {' -> '.join(processed.processed_stack)}")


def demo_find_callers_effect():
    """find-callers 效果演示"""
    print("\n" + "=" * 60)
    print("Demo 4: find-callers Symbol Processing Effect")
    print("=" * 60)
    
    raw_call_stacks = [
        ["MyService::ProcessRequest", "ThreadPool::WorkerThread", 
         "std::thread::_M_run", "execute_native_thread_routine",
         "start_thread", "__clone", "main", "__libc_start_main"],
        ["MyService::ProcessRequest", "EventLoop::Wait", "__GI___epoll_wait",
         "syscall", "entry_SYSCALL_64", "do_syscall_64", "__x64_sys_epoll_wait"],
    ]
    
    rules = get_symbol_rules()
    
    print("\nRaw caller stacks:")
    for i, stack in enumerate(raw_call_stacks, 1):
        callers = stack[1:]
        print(f"  Stack {i}: {' <- '.join(callers[:4])}...")
    
    print("\nProcessed caller stacks:")
    for i, stack in enumerate(raw_call_stacks, 1):
        callers = stack[1:]
        processed = rules.process_stack(callers)
        print(f"  Stack {i}: {' <- '.join(processed.processed_stack)}")


def demo_cluster_paths_effect():
    """cluster-paths 效果演示"""
    print("\n" + "=" * 60)
    print("Demo 5: cluster-paths Symbol Processing Effect")
    print("=" * 60)
    
    raw_stacks = [
        ["business::Handler::Process", "ThreadPool::Execute",
         "std::thread::_M_run", "execute_native_thread_routine", "__clone"],
        ["business::Handler::Validate", "ThreadPool::Execute",
         "std::thread::_M_run", "execute_native_thread_routine", "__clone"],
        ["io::Handler::Read", "EventLoop::Poll",
         "__GI___epoll_wait", "syscall", "entry_SYSCALL_64"],
    ]
    
    rules = get_symbol_rules()
    
    print("\nRaw stacks:")
    for i, stack in enumerate(raw_stacks, 1):
        print(f"  Stack {i}: {' -> '.join(reversed(stack))}")
    
    print("\nProcessed stacks:")
    for i, stack in enumerate(raw_stacks, 1):
        processed = rules.process_stack(stack)
        print(f"  Stack {i}: {' -> '.join(reversed(processed.processed_stack))}")


def demo_comparison():
    """使用 vs 不使用对比"""
    print("\n" + "=" * 60)
    print("Demo 6: With vs Without Symbol Processing")
    print("=" * 60)
    
    test_stack = [
        "MyApp::Service::HandleRequest", "ThreadPool::WorkerLoop",
        "std::thread::_M_run", "execute_native_thread_routine",
        "start_thread", "__clone", "main", "__libc_start_main",
    ]
    
    rules = get_symbol_rules()
    
    print(f"\nOriginal ({len(test_stack[1:])} frames):")
    print(f"  {' <- '.join(test_stack[1:])}")
    
    processed = rules.process_stack(test_stack[1:])
    print(f"\nProcessed ({len(processed.processed_stack)} frames):")
    print(f"  {' <- '.join(processed.processed_stack)}")
    
    reduction = (1 - len(processed.processed_stack) / len(test_stack[1:])) * 100
    print(f"\n  Reduction: {reduction:.1f}% fewer frames")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Symbol Processor Demo")
    print("=" * 60)
    
    demo_basic_processing()
    demo_normalize()
    demo_collapse_groups()
    demo_find_callers_effect()
    demo_cluster_paths_effect()
    demo_comparison()
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)
