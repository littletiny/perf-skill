# Symbol Rules 配置文档

## 配置文件位置

**唯一配置文件**: `config/symbol_rules.json`

## 配置文件结构

```json
{
  "description": "配置描述",
  "version": "版本号",
  "_doc": {
    "overview": "配置文件说明",
    "processing_order": "规则处理顺序",
    "commands_affected": "受影响的命令",
    "wildcard_support": "通配符支持说明"
  },
  "rules": {
    "hidden": {},      // 隐藏规则
    "merge_up": {},    // 向上合并规则
    "merge_down": {},  // 向下合并规则
    "collapse": {}     // 折叠组规则
  },
  "sampling": {},      // 采样策略配置
  "clustering": {}     // 聚类配置
}
```

## 规则详解

### 1. Hidden - 隐藏规则

完全从调用栈中移除指定符号。

```json
"hidden": {
  "_comment": "完全隐藏的符号 - 从调用栈中移除",
  "description": "Symbols to hide from callstack",
  "examples": ["__clone 会隐藏 __clone, __clone3 等"],
  "patterns": ["__clone", "start_thread", "..."]
}
```

**通配符支持**:
- `*`: 匹配任意字符序列
- `?`: 匹配单个字符
- `[seq]`: 匹配字符集中的任意字符

**效果示例**:
```
Before: [worker, execute_native_thread_routine, start_thread, __clone, main]
After:  [worker, main]
```

### 2. Merge Up - 向上合并

将符号合并到其调用者（caller，栈中上方）。

```json
"merge_up": {
  "_comment": "向上合并 - 将符号合并到其调用者",
  "description": "Symbols to merge into their caller",
  "examples": ["__libc_start_main -> main"],
  "patterns": ["__libc_start_main", "pthread_create*", "std::thread::_*"]
}
```

**效果示例**:
```
Before: [main, __libc_start_main]
After:  [main]  // __libc_start_main 合并到 main
```

### 3. Merge Down - 向下合并

将符号合并到其被调用者（callee，栈中下方）。

```json
"merge_down": {
  "_comment": "向下合并 - 将符号合并到其被调用者",
  "description": "Symbols to merge into their callee",
  "examples": ["syscall -> vfs_read"],
  "patterns": ["syscall", "__x64_sys_*", "__GI_*"]
}
```

**效果示例**:
```
Before: [read_data, syscall, __x64_sys_read, vfs_read]
After:  [read_data, vfs_read]  // 中间 syscall 层合并
```

### 4. Collapse - 折叠组

将连续的多个符号折叠为单一代表符号。

```json
"collapse": {
  "groups": [
    {
      "name": "pthread_runtime",
      "symbols": ["pthread_mutex_lock", "pthread_mutex_unlock", "..."],
      "display": "[pthread_sync]"
    }
  ]
}
```

**内置折叠组**:

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

**效果示例**:
```
Before: [business, pthread_mutex_lock, pthread_cond_wait, pthread_mutex_unlock, business2]
After:  [business, [pthread_sync], business2]
```

### 5. Normalize - 符号名规范化

自动截断长命名空间，保留 `ClassName::method` 格式。

```python
# 转换示例
tensorflow::grappler::MetaOptimizer::OptimizeGraph  ->  MetaOptimizer::OptimizeGraph
std::vector<std::string>::push_back                  ->  string>::push_back
plain_function                                        ->  plain_function
[syscall]                                             ->  [syscall]  # 折叠组不变
```

**默认启用**，可通过参数控制：
```python
processed = rules.process_stack(stack, normalize=False)  # 禁用
```

## 聚类配置 (Clustering)

控制 `cluster-paths` 命令的行为：

```json
"clustering": {
  "_comment": "cluster-paths 命令的聚类配置",
  "description": "Path clustering configuration",
  "enabled": true,
  "min_depth": 2,
  "min_samples": 5
}
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `enabled` | 是否启用 symbol processing | `true` |
| `min_depth` | 最小调用深度 | `2` |
| `min_samples` | 最小样本数 | `5` |

## 处理顺序

规则按以下顺序应用：

1. **Hidden** - 首先移除完全不需要的符号
2. **Merge Down** - 将包装器合并到实际函数
3. **Merge Up** - 将中间层合并到调用者
4. **Collapse** - 折叠连续的同类符号
5. **Normalize** - 截断长命名空间

## 命令影响

以下命令自动应用 symbol processing：

| 命令 | 应用位置 | 配置来源 |
|------|----------|----------|
| `find-callers` | 调用者栈处理 | `symbol_rules.json` |
| `cluster-paths` | 完整栈处理 + 聚类参数 | `symbol_rules.json` |
| `bottleneck-trace` | 调用链提取 | `symbol_rules.json` |

## 自定义配置示例

```json
{
  "rules": {
    "hidden": {
      "patterns": ["my_internal_*", "noise_function"]
    },
    "merge_up": {
      "patterns": ["wrapper_*"]
    },
    "collapse": {
      "groups": [
        {
          "name": "io_ops",
          "symbols": ["read", "write", "open", "close"],
          "display": "[io]"
        }
      ]
    }
  },
  "clustering": {
    "min_depth": 3,
    "min_samples": 10
  }
}
```

## 验证配置

```bash
# 测试配置文件加载
python3 -c "from config.defaults import get_symbol_rules; r = get_symbol_rules(); print('Config OK:', len(r.hidden), 'hidden rules')"

# 查看处理效果
python3 scripts/demo_symbol_processor.py

# 测试聚类配置
python3 -c "from config.defaults import get_symbol_rules; print(get_symbol_rules().clustering)"
```
