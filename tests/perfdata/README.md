# Perfdata 测试

本目录包含 perf-hunter 工具集的数据格式兼容性测试。

## 目录结构

```
perfdata/
├── README.md              # 本文件
├── test_perfdata.py       # 回归测试套件（Python）
├── new_format/            # SPEAR 格式数据（带 core/s 值）
│   └── case_test.data
└── perf_format/           # 原始 perf script 格式
    └── case_test.data
```

## 快速开始

```bash
# 运行所有测试
python3 tests/perfdata/test_perfdata.py

# 详细输出
python3 tests/perfdata/test_perfdata.py -v

# 失败时停止
python3 tests/perfdata/test_perfdata.py -f

# 只测试指定格式
python3 tests/perfdata/test_perfdata.py -d new_format
python3 tests/perfdata/test_perfdata.py -d perf_format
```

## 测试覆盖

### 数据格式验证
- 数据文件存在性
- 格式标识检测（core/s: / cpu-clock）
- 数据信息统计（行数、采样数、进程类型数）

### 工具兼容性测试

| 工具 | 说明 |
|------|------|
| `check-cpu-bottleneck` | 检查资源限制和单核饱和 |
| `show-cpu-usage` | CPU 利用率概览 |
| `get-process-top` | 进程 CPU 排行 |
| `get-comm-top` | 进程组 CPU 排行 |
| `count-process-variety` | 进程风暴检测 |
| `cluster-comm` | 进程名聚类分析 |
| `get-hotspots` | 热点函数排名（self/inclusive） |
| `cluster-symbols` | 语义聚类分析 |
| `cluster-paths` | 调用路径聚类 |
| `analyze-core-distribution` | 核心负载分布分析 |
| `find-callers` | 热点函数溯源 |
| `detect-anomalies` | 时序异常检测 |
| `sys-audit` | 系统审计（Composite） |
| `bottleneck-trace` | 瓶颈追踪（Composite） |
| `storm-trace` | 风暴追踪（Composite） |

## 数据格式说明

### new_format（推荐）

SPEAR 处理后的格式，包含预计算的 core/s 值：

```
dbatman 2978356 [13] 0.000000: 0.1052 core/s:
    runtime.findObject (dbatman)
    runtime.scanobject (dbatman)
    ...
```

特点：
- 每行包含 `core/s:` 标识
- 已计算 CPU 利用率
- 更适合直接分析

### perf_format（原始）

直接从 `perf script` 输出的格式：

```
swapper 0 [000] 460661.461601: 250000 cpu-clock:ppp:
    ffff800080152a30 cpuidle_idle_call ([kernel.kallsyms])
    ...
```

特点：
- 原始时间戳和事件类型
- 需要 `--freq` 参数指定采样率
- 通用兼容性好

## 添加新数据格式

1. 创建新目录（如 `my_format/`）
2. 放入 `.data` 测试文件
3. 在 `test_perfdata.py` 的 `format_types` 中添加格式映射
4. 运行测试验证

## 测试开发

测试脚本使用纯 Python 标准库，无外部依赖：

```python
# 添加新测试工具
def test_tool_xxx(env, data_file):
    result = env.run_spear("xxx", data_file=data_file)
    assert "expected" in result.stdout

# 注册到 TEST_TOOLS
TEST_TOOLS.append(("xxx", test_tool_xxx))
```

## 故障排查

### 找不到 spear 脚本

```bash
export SKILL_DIR=/path/to/perf-hunter
python3 tests/perfdata/test_perfdata.py
```

### 测试失败

检查数据文件格式：
```bash
# new_format 检查
grep "core/s:" tests/perfdata/new_format/case_test.data | head -5

# perf_format 检查
grep "cpu-clock" tests/perfdata/perf_format/case_test.data | head -5
```

## 参考资料

- `$repo/references/data-format.md` - 数据格式规范
- `$repo/references/tools.md` - 工具命令详细说明
