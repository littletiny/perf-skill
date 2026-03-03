# 单元测试

本目录包含 perf-hunter 各模块的单元测试。

## 目录结构

```
tests/unit/
├── README.md                   # 本文件
├── test_risk_display_config.py # Risk 显示配置测试
└── test_perfdata.py            # 性能数据格式测试
```

## 测试列表

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `test_risk_display_config.py` | Risk 显示配置加载与格式化测试 | `python3 tests/unit/test_risk_display_config.py` |
| `test_perfdata.py` | 性能数据格式兼容性测试 | `python3 tests/unit/test_perfdata.py` |

## 运行测试

```bash
# 运行所有单元测试
python3 tests/unit/test_risk_display_config.py
python3 tests/unit/test_perfdata.py

# 详细输出
python3 tests/unit/test_perfdata.py -v

# 只测试指定格式
python3 tests/unit/test_perfdata.py -d new_format
python3 tests/unit/test_perfdata.py -d perf_format
```

## 测试原则

- **目录隔离**: 各专项测试独立，互不干扰
- **纯标准库**: 所有 Python 测试使用标准库，无外部依赖
- **自包含**: 测试能独立运行，不依赖其他测试的执行顺序
