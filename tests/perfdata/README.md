# Perfdata 测试脚本说明

本目录包含用于验证 SPEAR perf-hunter 工具集的测试数据和脚本。

## 目录结构

```
perfdata/
├── README.md              # 本文件
├── run_tests.sh           # 主测试脚本（测试所有数据格式）
├── test_perf_format.sh    # perf_format 格式专项测试
├── test_new_format.sh     # new_format 格式专项测试
├── perf_format/           # perf script 原始格式数据
│   └── case_test.data
└── new_format/            # 处理后格式数据（带 core/s 值）
    └── case_test.data
```

## 快速开始

```bash
cd perfdata

# 运行所有格式测试
./run_tests.sh

# 或单独测试特定格式
./test_perf_format.sh    # 测试原始 perf 格式
./test_new_format.sh     # 测试 core/s 格式

# 指定 skill 目录（如果不在默认位置）
SKILL_DIR=/path/to/perf-hunter ./run_tests.sh
```

## 数据格式说明

### perf_format (原始 perf script 格式)

```
swapper       0 [000] 460661.461601:     250000 cpu-clock:ppp: 
	ffff800080152a30 cpuidle_idle_call+0xb8 ([kernel.kallsyms])
	...
```

特点：
- 直接从 `perf script` 命令输出
- 包含完整的时间戳、CPU ID、事件类型
- 包含内核和用户态调用栈

### new_format (处理后格式)

```
dbatman 2978356 [13] 0.000000: 0.1052 core/s:
                        runtime.findObject (dbatman)
                        runtime.scanobject (dbatman)
                        ...
```

特点：
- 每行包含计算好的 `core/s` 值
- 已进行一定程度的聚合处理
- 更适合直接分析热点

## 测试覆盖的工具

| 类别 | 工具名 | 说明 |
|------|--------|------|
| 环境评估 | `check-cpu-bottleneck` | 检查资源限制和单核饱和 |
| 环境评估 | `show-cpu-usage` | CPU 利用率概览 |
| 进程分析 | `get-process-top` | 高消耗单个进程识别 |
| 进程分析 | `get-comm-top` | 高消耗进程组识别 |
| 进程分析 | `count-process-variety` | 进程风暴检测 |
| 进程分析 | `cluster-comm` | 进程名聚类分析 |
| 热点分析 | `get-hotspots` | 热点函数排名 |
| 热点分析 | `find-callers` | 热点函数溯源 |
| 语义聚类 | `cluster-symbols` | 语义规则聚类 |
| 语义聚类 | `cluster-paths` | 调用路径聚类 |
| 负载分布 | `analyze-core-distribution` | 核心级负载分析 |

## 添加新测试数据

1. 在 `perfdata/` 下创建新目录（如 `my_format/`）
2. 将 `.data` 文件放入该目录
3. 运行 `./run_tests.sh`，脚本会自动发现并测试

## 故障排查

### 找不到 spear 脚本

确保设置了正确的 `SKILL_DIR`：

```bash
export SKILL_DIR=$HOME/.config/agents/skills/perf-hunter
```

### 测试失败

检查：
1. 数据文件格式是否正确
2. Python 3 是否可用
3. 数据文件是否包含有效的 perf 采样数据

## 参考资料

- `$repo/references/data-format.md` - 数据格式规范
- `$repo/references/tools.md` - 工具命令详细说明
- `$repo/docs/trace-interface.md` - livedoc 接口规范
