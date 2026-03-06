# Symbol Processing 机制设计文档

## 概述

Symbol Processing 是 perf-hunter 的核心功能，用于对调用栈进行智能清理和聚合，使用户能够专注于有意义的业务代码。

配置文件位置: `config/symbol_rules.json`

## 配置格式

```json
{
  "description": "配置描述",
  "version": "版本号",
  "rules": {
    "hidden": {},      // 隐藏规则
    "merge_up": {},    // 向上合并规则  
    "merge_down": {},  // 向下合并规则
    "collapse": {}     // 折叠组规则
  },
  "clustering": {}     // 聚类配置
}
```

## 规则类型

### Hidden - 隐藏规则

完全从调用栈中移除指定符号。

**适用场景:**
- 线程运行时函数（`__clone`, `start_thread`）
- 程序启动桩（`_start`, `__start`）

```json
"hidden": {
  "patterns": ["__clone", "start_thread", "execute_native_thread_routine"]
}
```

**效果:**
```
Before: [worker, execute_native_thread_routine, start_thread, __clone, main]
After:  [worker, main]
```

### Merge Up - 向上合并

将符号合并到其调用者（caller，栈中索引更小的位置）。

**适用场景:**
- libc 启动函数（`__libc_start_main`）
- pthread 创建函数（`pthread_create`）

```json
"merge_up": {
  "patterns": ["__libc_start_main", "pthread_create*"]
}
```

**效果:**
```
Before: [main, __libc_start_main]
After:  [main]  // __libc_start_main 合并到 main
```

### Merge Down - 向下合并

将符号合并到其被调用者（callee，栈中索引更大的位置）。

**适用场景:**
- syscall 包装器（`syscall`, `__syscall`）
- 内核入口函数（`entry_SYSCALL_64`, `do_syscall_64`）

```json
"merge_down": {
  "patterns": ["syscall", "__x64_sys_*", "__GI_*"]
}
```

**效果:**
```
Before: [read_data, syscall, __x64_sys_read, vfs_read]
After:  [read_data, vfs_read]  // 中间 syscall 层合并
```

### Collapse - 折叠组

将连续的多个符号折叠为单一代表符号。

```json
"collapse": {
  "groups": [
    {
      "name": "pthread_runtime",
      "symbols": ["pthread_mutex_lock", "pthread_mutex_unlock", "pthread_cond_wait"],
      "display": "[pthread_sync]"
    }
  ]
}
```

**效果:**
```
Before: [business, pthread_mutex_lock, pthread_cond_wait, pthread_mutex_unlock, business2]
After:  [business, [pthread_sync], business2]
```

### Normalize - 符号名规范化

自动截断长命名空间，保留 `ClassName::method` 格式。

```python
# 转换示例
tensorflow::grappler::MetaOptimizer::OptimizeGraph  ->  MetaOptimizer::OptimizeGraph
std::vector<std::string>::push_back                  ->  vector<string>::push_back
```

默认启用，可通过参数控制：
```python
processed = rules.process_stack(stack, normalize=False)  # 禁用
```

## 内置折叠组

| 组名 | 包含符号 | 显示名 |
|------|----------|--------|
| pthread_runtime | mutex/cond/barrier 操作 | `[pthread_sync]` |
| memory_alloc | malloc/free/calloc/realloc | `[memory_ops]` |
| syscall_entry | `__x64_sys_*`, `do_syscall_*` | `[syscall]` |
| scheduling | `__schedule`, `finish_task_switch` | `[scheduler]` |
| spinlock | `_raw_spin_lock/unlock` | `[spinlock]` |
| mutex | `mutex_lock/unlock` | `[mutex]` |
| rwsem | `rwsem_down/up_*` | `[rwsem]` |
| page_fault | `do_page_fault`, `handle_mm_fault` | `[page_fault]` |
| signal | `do_signal`, `get_signal` | `[signal]` |

## 处理顺序

规则按以下顺序应用：

1. **Hidden** - 首先移除完全不需要的符号
2. **Merge Down** - 将包装器合并到实际函数
3. **Merge Up** - 将中间层合并到调用者
4. **Collapse** - 折叠连续的同类符号
5. **Normalize** - 截断长命名空间

## 通配符支持

所有规则支持 Unix shell 风格的通配符匹配：

| 通配符 | 含义 | 示例 |
|--------|------|------|
| `*` | 匹配任意字符序列 | `__clone*` 匹配 `__clone`, `__clone3` |
| `?` | 匹配单个字符 | `symbol_?` 匹配 `symbol_a` |
| `[seq]` | 匹配 seq 中的任意字符 | `[abc]` 匹配 `a`, `b`, 或 `c` |

## 使用示例

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

### 与 Smart Callchain 集成

```python
from scripts.perf_toolkit.analysis.smart_callchain import SmartCallchainExtractor

extractor = SmartCallchainExtractor(samples)
result = extractor.extract(stack, target_idx, target_symbol)

# 处理后的栈已自动应用所有规则
print(result.trajectory)
```

## 命令影响

以下命令自动应用 symbol processing：

| 命令 | 应用位置 | 配置来源 |
|------|----------|----------|
| `find-callers` | 调用者栈处理 | `symbol_rules.json` |
| `cluster-paths` | 完整栈处理 + 聚类参数 | `symbol_rules.json` |
| `bottleneck-trace` | 调用链提取 | `symbol_rules.json` |

## 验证配置

```bash
# 测试配置文件加载
python3 -c "from config.defaults import get_symbol_rules; r = get_symbol_rules(); print('Config OK:', len(r.hidden), 'hidden rules')"

# 查看处理效果
python3 scripts/demo_symbol_processor.py

# 测试聚类配置
python3 -c "from config.defaults import get_symbol_rules; print(get_symbol_rules().clustering)"
```
