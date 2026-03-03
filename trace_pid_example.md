# bottleneck-trace --pid 示例输出

## 命令使用

```bash
# Trace 指定 PID 的性能瓶颈
$ perf-hunter composite bottleneck-trace --pid 3657995 --data case_test.data

# 或同时指定进程名和 PID
$ perf-hunter composite bottleneck-trace --comm python3 --pid 3657995 --data case_test.data
```

## 输出示例

```
================================================================================
                    Bottleneck Trace PID 示例 - PID 3657995
================================================================================

总样本数: 300
PID 3657995 的样本数: 7
第一个样本的 comm: python3

执行 trace...

## [BOTTLENECK_TRACE]

### 瓶颈特征 (Bottleneck Profile)
  进程: python3
  目标PID: 3657995
  总CPU: 5.26%
  内核占比: 0.0%
  Monopoly: 0.35
  CV: 0.00
  诊断: NORMAL

### 热点函数 (Hotspots)
  排序: 按 Self CPU 占比

  #1 _PyEval_EvalFrameDefault
      Self: 0.6% | Incl: 4.2% | Tag: COMPUTE
  #2 _PyFunction_FastCallKeywords
      Self: 0.4% | Incl: 1.8% | Tag: COMPUTE
  #3 _PyUnicodeWriter_Finish
      Self: 0.3% | Incl: 0.5% | Tag: COMPUTE
  #4 PyUnicode_FromFormatV
      Self: 0.2% | Incl: 0.4% | Tag: COMPUTE
  #5 PyErr_Format
      Self: 0.2% | Incl: 0.3% | Tag: COMPUTE

### 调用链溯源 (Call Chain Analysis)
  目标: _PyEval_EvalFrameDefault

  #1 [45.2%] _PyFunction_FastCallKeywords -> _PyEval_EvalCodeWithName
  #2 [28.1%] _PyFunction_FastCallDict -> _PyEval_EvalCodeWithName
  #3 [15.3%] _PyObject_FastCallKeywords -> _PyFunction_FastCallKeywords

### 根因分析 (Root Cause)
  [INFO] python3 分析完成，未发现严重问题
      Hint: 

### 关联标志 (Correlation Flags)
  未检测到显著的关联风险模式

================================================================================
```

## 多 PID 进程 Trace 对比

当一个进程名对应多个 PID 时，`--pid` 可以精确追踪单个实例：

```bash
# 查看所有 python3 进程
$ perf-hunter analysis comm-top --data case_test.data | grep python3
  python3(3657995)  5.26%  NORMAL
  python3(3614904)  3.75%  NORMAL
  python3(2776459)  2.15%  NORMAL

# Trace 特定 PID
$ perf-hunter composite bottleneck-trace --pid 3657995 --data case_test.data

# Trace 另一个 PID
$ perf-hunter composite bottleneck-trace --pid 3614904 --data case_test.data
```

## 技术实现细节

### 1. 样本过滤流程

```python
# 1. CLI 层接收 --pid 参数
target_pid = getattr(args, 'pid', None)

# 2. 自动推导 comm（如果未指定）
if target_pid and not target_comm:
    target_comm = _get_comm_by_pid(samples, target_pid)

# 3. Facade 层按 PID 过滤
filtered_samples = [s for s in samples if s.pid == target_pid]
hotspots_result = facade.analyze_hotspots(filtered_samples, pid=target_pid)
callers_result = facade.analyze_callers(filtered_samples, target_symbol=..., pid=target_pid)
```

### 2. 接口签名

```python
# Facade 接口
class AnalysisFacade:
    def analyze_hotspots(self, samples, comm=None, pid=None, top_n=20): ...
    def analyze_callers(self, samples, target_symbol, comm=None, pid=None): ...

# Composite 接口
class BottleneckTracer:
    def trace(self, samples, target_comm=None, target_pid=None): ...

# CLI 接口
$ bottleneck-trace [--comm NAME] [--pid PID]
```

### 3. 与 --comm 的区别

| 参数 | 作用 | 使用场景 |
|------|------|----------|
| `--comm` | 按进程名过滤 | 分析进程整体行为 |
| `--pid` | 按 PID 精确过滤 | 分析特定进程实例 |
| `--comm + --pid` | 同时指定 | 验证特定实例 |

## 实际应用场景

1. **多实例服务分析**: 当一个服务启动多个工作进程时，追踪特定 PID 找出异常实例
2. **短时进程追踪**: 追踪频繁创建销毁的进程中的特定实例
3. **对比分析**: 对比同一进程不同 PID 的性能差异
4. **问题定位**: 结合系统监控，对特定问题进程进行深度分析
