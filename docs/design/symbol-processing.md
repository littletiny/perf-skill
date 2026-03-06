# Symbol Processing 机制设计文档

## 概述

Symbol Processing 是 perf-hunter 的核心功能，用于对调用栈进行智能清理和聚合，使用户能够专注于有意义的业务代码。

## 核心概念

### 调用栈方向

调用栈使用 **栈顶在上** 的表示方式（索引 0 是最顶层函数）：

```
[0] callee_function      <- 被调用的函数（当前执行点）
[1] caller_function      <- 调用者
[2] main                 <- 入口函数
```

### 五种处理规则

Symbol Processing 包含五种规则，按以下顺序应用：

1. **Hidden** - 隐藏指定符号
2. **Merge Down** - 向下合并到被调用者
3. **Merge Up** - 向上合并到调用者
4. **Collapse** - 折叠符号组
5. **Normalize** - 规范化符号名（默认启用）

#### 1. Hidden - 隐藏

完全从调用栈中移除指定符号。

**适用场景：**
- 线程运行时函数（`__clone`, `start_thread`）
- 程序启动桩（`_start`, `__start`）

**示例：**
```json
"hidden": ["__clone", "start_thread", "execute_native_thread_routine"]
```

**效果：**
```
Before:  [worker, execute_native_thread_routine, start_thread, __clone, main]
After:   [worker, main]
```

#### 2. Merge Up - 向上合并

将符号合并到其调用者（caller，栈中索引更小的位置）。

**适用场景：**
- libc 启动函数（`__libc_start_main`）
- pthread 创建函数（`pthread_create`）
- C++ std::thread 内部函数

**示例：**
```json
"merge_up": ["__libc_start_main", "pthread_create*", "std::thread::_*"]
```

**效果：**
```
Before:  [main, __libc_start_main]
After:   [main]  // __libc_start_main 的 weight 合并到 main
```

#### 3. Merge Down - 向下合并

将符号合并到其被调用者（callee，栈中索引更大的位置）。

**适用场景：**
- syscall 包装器（`syscall`, `__syscall`）
- 内核入口函数（`entry_SYSCALL_64`, `do_syscall_64`）
- glibc 内部包装器（`__GI_*`, `__libc_*`）

**示例：**
```json
"merge_down": ["syscall", "__x64_sys_*", "do_syscall_64", "entry_SYSCALL_*"]
```

**效果：**
```
Before:  [read_data, syscall, __x64_sys_read, vfs_read]
After:   [read_data, vfs_read]  // 中间 syscall 层合并到 vfs_read
```

#### 4. Collapse - 折叠组

将连续的多个符号折叠为单一代表符号。

**适用场景：**
- 锁操作（`pthread_mutex_lock/unlock`）
- 内存操作（`malloc/free/calloc`）
- 调度相关（`__schedule/schedule/finish_task_switch`）

**示例：**
```json
"collapse_groups": {
  "pthread_runtime": {
    "symbols": ["pthread_mutex_lock", "pthread_mutex_unlock", "pthread_cond_wait"],
    "display": "[pthread_sync]"
  }
}
```

**效果：**
```
Before:  [business, pthread_mutex_lock, pthread_cond_wait, pthread_mutex_unlock, business2]
After:   [business, [pthread_sync], business2]
```

## 通配符支持

所有规则支持 Unix shell 风格的通配符匹配：

| 通配符 | 含义 | 示例 |
|--------|------|------|
| `*` | 匹配任意字符序列 | `__clone*` 匹配 `__clone`, `__clone3` |
| `?` | 匹配单个字符 | `symbol_?` 匹配 `symbol_a`, `symbol_1` |
| `[seq]` | 匹配 seq 中的任意字符 | `[abc]` 匹配 `a`, `b`, 或 `c` |

## 处理顺序

规则按以下顺序应用：

1. **Hidden** - 首先移除完全不需要的符号
2. **Merge Down** - 将包装器合并到实际函数
3. **Merge Up** - 将中间层合并到调用者
4. **Collapse** - 折叠连续的同类符号

## API 使用

### 基本使用

```python
from config.defaults import get_symbol_rules, ProcessedStack

# 获取全局规则实例
rules = get_symbol_rules()

# 处理调用栈
stack = ["main", "__libc_start_main", "malloc", "syscall", "__clone"]
processed = rules.process_stack(stack)

print(processed.processed_stack)  # [main, [memory_ops]]
print(processed.get_summary())    # Applied: 2 hidden, 1 merged_up, 1 merged_down, 1 collapsed
```

### 自定义规则

```python
from config.defaults import SymbolRules

rules = SymbolRules(
    hidden=["*noise*"],
    merge_up=["wrapper_*"],
    merge_down=["syscall"],
    collapse_groups={
        "io_ops": {
            "symbols": ["read", "write", "open", "close"],
            "display": "[io]"
        }
    }
)

processed = rules.process_stack(my_stack)
```

## 配置示例

完整的配置文件见 `config/symbol_rules.json`，包含以下预定义组：

| 组名 | 包含符号 | 显示名 |
|------|----------|--------|
| pthread_runtime | mutex/cond/barrier 操作 | `[pthread_sync]` |
| memory_alloc | malloc/free/calloc/realloc/new/delete | `[memory_ops]` |
| syscall_entry | `__x64_sys_*`, `do_syscall_*` | `[syscall]` |
| scheduling | `__schedule`, `finish_task_switch`, `do_nanosleep` | `[scheduler]` |
| spinlock | `_raw_spin_lock/unlock` | `[spinlock]` |
| mutex | `mutex_lock/unlock` | `[mutex]` |
| rwsem | `rwsem_down/up_*` | `[rwsem]` |
| page_fault | `do_page_fault`, `handle_mm_fault` | `[page_fault]` |
| signal | `do_signal`, `get_signal` | `[signal]` |

## 与 Smart Callchain 集成

`SmartCallchainExtractor` 自动使用 `ProcessedStack` 处理调用栈：

```python
from scripts.perf_toolkit.analysis.smart_callchain import SmartCallchainExtractor

extractor = SmartCallchainExtractor(samples)
result = extractor.extract(stack, target_idx, target_symbol)

# 处理后的栈已自动应用所有规则
print(result.trajectory)
```

## Normalize - 符号名规范化

### 概述

Normalize 是默认启用的功能，将长命名空间的符号名截断为 `ClassName::method` 格式。

### 转换规则

| 原始符号名 | 规范化后 |
|-----------|---------|
| `std::vector<int>::push_back` | `vector<int>::push_back` |
| `MyClass::MyClass::method` | `MyClass::method` |
| `parameter_server::optimizer::AdamOptimizer::Optimize` | `AdamOptimizer::Optimize` |
| `plain_function` | `plain_function` (无变化) |
| `[syscall]` | `[syscall]` (折叠组标记不变) |

### 配置

Normalize 默认启用，可以通过参数控制：

```python
# 默认启用 normalize
processed = rules.process_stack(stack)  # normalize=True (默认)

# 禁用 normalize
processed = rules.process_stack(stack, normalize=False)
```

### 独立使用

```python
from config.defaults import SymbolRules

# 规范化单个符号
short_name = SymbolRules.normalize_symbol(
    "tensorflow::grappler::MetaOptimizer::OptimizeGraph"
)
print(short_name)  # "MetaOptimizer::OptimizeGraph"
```
