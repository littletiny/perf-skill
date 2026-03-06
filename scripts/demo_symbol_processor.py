#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Symbol Processor Demo - 展示增强的 symbol 处理机制

此脚本演示新的 symbol 处理功能：
1. hidden: 隐藏特定符号
2. merge_up: 向上合并到调用者
3. merge_down: 向下合并到被调用者
4. collapse: 折叠符号组
5. normalize: 截断为 classname::method 格式（默认启用）
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.defaults import SymbolRules, ProcessedStack, get_symbol_rules


def demo_basic_rules():
    """演示基本规则处理"""
    print("=" * 70)
    print("Demo 1: Basic Symbol Processing")
    print("=" * 70)
    
    # 创建一个包含各种场景的调用栈
    stack = [
        # 业务代码
        "FindInTableWithLock",
        "InsertWithProb",
        # 内存分配
        "malloc",
        "__libc_malloc",
        # syscall 路径
        "syscall",
        "__x64_sys_read",
        "do_syscall_64",
        "entry_SYSCALL_64",
        # 运行时函数
        "pthread_mutex_lock",
        "start_thread",
        "__clone",
        "main",
        "__libc_start_main",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    # 加载默认规则并处理（默认启用 normalize）
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack (with normalize):")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\n{processed.get_summary()}")
    print()


def demo_normalize():
    """演示 classname::method 规范化"""
    print("=" * 70)
    print("Demo 2: Symbol Name Normalization (classname::method)")
    print("=" * 70)
    
    # 包含长命名空间的 C++ 符号
    stack = [
        "parameter_server::optimizer::AdamOptimizer::ComputeGradient",
        "parameter_server::optimizer::SGDOptimizer::UpdateWeights",
        "std::vector<std::string>::push_back",
        "std::map<int, std::string>::operator[]",
        "tensorflow::Tensor::FromProto",
        "my_namespace::inner::MyClass::method",
        "plain_function",
        "AnotherClass::staticMethod",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    # 使用默认 normalize=True
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack (normalize=True, default):")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    # 禁用 normalize 对比
    processed_no_norm = rules.process_stack(stack, normalize=False)
    
    print(f"\nProcessed Stack (normalize=False):")
    for i, sym in enumerate(processed_no_norm.processed_stack):
        print(f"  [{i:2d}] {sym}")
    print()


def demo_collapse_groups():
    """演示 collapse 组折叠"""
    print("=" * 70)
    print("Demo 3: Collapse Groups")
    print("=" * 70)
    
    stack = [
        "business_logic",
        "pthread_mutex_lock",
        "pthread_cond_wait",
        "pthread_mutex_unlock",
        "malloc",
        "free",
        "calloc",
        "business_logic_2",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack (with collapse groups):")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\nOperations detail:")
    for op in processed.operations:
        if op.operation == "collapse":
            print(f"  - {op.original_symbol} -> {op.new_symbol}: {op.reason}")
    print()


def demo_syscall_path():
    """演示 syscall 路径合并"""
    print("=" * 70)
    print("Demo 4: Syscall Path Aggregation")
    print("=" * 70)
    
    # 模拟一个常见的 syscall 调用路径
    stack = [
        "read_data",
        "__GI___read",
        "syscall",
        "entry_SYSCALL_64_after_hwframe",
        "do_syscall_64",
        "__x64_sys_read",
        "vfs_read",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack:")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\nOperations detail:")
    for op in processed.operations:
        print(f"  - [{op.operation:12s}] {op.original_symbol:30s} -> {op.new_symbol or '(removed)':20s}")
    print()


def demo_thread_creation():
    """演示线程创建路径"""
    print("=" * 70)
    print("Demo 5: Thread Creation Path")
    print("=" * 70)
    
    stack = [
        "worker_thread",
        "execute_native_thread_routine",
        "start_thread",
        "pthread_create",
        "main",
        "__libc_start_main",
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
    print()


def demo_complex_real_world():
    """演示复杂真实场景"""
    print("=" * 70)
    print("Demo 6: Complex Real-World Stack")
    print("=" * 70)
    
    # 模拟一个真实的复杂调用栈
    stack = [
        # 热点函数
        "finish_task_switch_[k]",
        "__schedule_[k]",
        "schedule_[k]",
        "do_nanosleep_[k]",
        "hrtimer_nanosleep_[k]",
        "__x64_sys_nanosleep_[k]",
        "do_syscall_64_[k]",
        "entry_SYSCALL_64_after_hwframe_[k]",
        "__GI___nanosleep",
        "std::this_thread::__sleep_for",
        "std::this_thread::sleep_for",
        "MyService::BackgroundWorker",
        "MyService::RunWorkerThread",
        "std::thread::_State_impl::_M_run",
        "execute_native_thread_routine",
        "start_thread",
        "pthread_create",
        "main",
        "__libc_start_main",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack (clean):")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\n{processed.get_summary()}")
    print()


def demo_cpp_namespace():
    """演示 C++ 长命名空间处理"""
    print("=" * 70)
    print("Demo 7: C++ Long Namespace Handling")
    print("=" * 70)
    
    # 真实 C++ 项目中常见的长命名空间
    stack = [
        "MyApplication::Core::Engine::RenderSystem::GraphicsDevice::Present",
        "MyApplication::Core::Engine::RenderSystem::SwapChain::Present",
        "std::__1::__function::__func<...>::operator()",
        "tbb::detail::d1::task_arena_base::execute",
        "tensorflow::grappler::MetaOptimizer::OptimizeGraph",
        "Eigen::Matrix<float, 3, 3>::operator*",
        "thrust::cuda_cub::detail::DispatchReduce<...>::Reduce",
        "c10::TensorImpl::set_contiguous",
        "at::native::add_kernel_cuda",
        "main",
    ]
    
    print("\nOriginal Stack:")
    for i, sym in enumerate(stack):
        print(f"  [{i:2d}] {sym}")
    
    rules = get_symbol_rules()
    processed = rules.process_stack(stack)
    
    print(f"\nProcessed Stack (normalize):")
    for i, sym in enumerate(processed.processed_stack):
        print(f"  [{i:2d}] {sym}")
    
    print(f"\nComparison:")
    for orig, proc in zip(stack, processed.processed_stack):
        if orig != proc:
            print(f"  {orig[:40]:40s} -> {proc}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Symbol Processor Demo - Enhanced Symbol Processing Mechanism")
    print("Features: hidden | merge_up | merge_down | collapse | normalize")
    print("=" * 70 + "\n")
    
    demo_basic_rules()
    demo_normalize()
    demo_collapse_groups()
    demo_syscall_path()
    demo_thread_creation()
    demo_complex_real_world()
    demo_cpp_namespace()
    
    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)
