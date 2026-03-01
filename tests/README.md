# perf-hunter 测试目录

本目录包含 perf-hunter 各模块的专项测试，各测试目录相互隔离，独立运行。

## 目录结构

```
tests/
├── README.md              # 本文件 - 测试目录总览
├── perfdata/              # 性能数据格式测试
│   ├── README.md          # perfdata 测试文档
│   ├── test_perfdata.py   # 数据格式兼容性测试
│   ├── new_format/        # SPEAR 格式数据样本
│   └── perf_format/       # 原始 perf 格式数据样本
├── scenario/              # 场景测试（人工验证用）
└── spear_wrap/            # spear_wrap CLI 回归测试
    ├── test_spear_wrap.py # 自动化测试套件
    └── README.md          # 测试文档
```

## 专项测试目录

| 目录 | 用途 | 运行方式 |
|------|------|----------|
| `perfdata/` | 数据格式兼容性测试 | `python3 tests/perfdata/test_perfdata.py` |
| `scenario/` | 场景化测试用例（人工验证） | 按场景文档执行 |
| `spear_wrap/` | CLI 回归测试 | `python3 tests/spear_wrap/test_spear_wrap.py` |

## 运行测试

### spear_wrap 回归测试

```bash
python3 tests/spear_wrap/test_spear_wrap.py
python3 tests/spear_wrap/test_spear_wrap.py -v
python3 tests/spear_wrap/test_spear_wrap.py -f
```

### perfdata 格式测试

```bash
# 运行所有格式测试
python3 tests/perfdata/test_perfdata.py

# 详细输出
python3 tests/perfdata/test_perfdata.py -v

# 只测试指定格式
python3 tests/perfdata/test_perfdata.py -d new_format
python3 tests/perfdata/test_perfdata.py -d perf_format
```

### 场景测试

```bash
# 查看场景列表
ls tests/scenario/

# 按场景文档执行
bash tests/scenario/run_tests.sh
```

## 测试原则

- **目录隔离**: 各专项测试独立目录，互不干扰
- **纯标准库**: 所有 Python 测试使用标准库，无外部依赖
- **自包含**: 测试能独立运行，不依赖其他测试的执行顺序

## 添加新测试

1. **单元测试**: 在对应模块的专项目录下添加 Python 脚本
2. **数据样本**: 放入 `perfdata/` 下相应格式目录
3. **场景测试**: 放入 `scenario/` 目录

## 测试状态

| 测试套件 | 用例数 | 状态 |
|---------|--------|------|
| spear_wrap | 14 | ✅ 通过 |
| perfdata (new_format) | 14 | ✅ 通过 |
| perfdata (perf_format) | 14 | ✅ 通过 |
