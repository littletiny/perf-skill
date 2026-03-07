# tests/ - 测试目录

## 目录简介

perf-hunter 的测试套件，包含单元测试、功能测试、集成测试和场景测试。

## 测试分类

| 类型 | 路径 | 说明 |
|------|------|------|
| 单元测试 | `unit/` | 单个模块/函数的测试 |
| 功能测试 | `functional/` | 功能特性测试 |
| 集成测试 | `integration/` | 模块间集成测试 |
| CLI 测试 | `cli/` | 命令行接口测试 |
| 场景测试 | `scenario/<name>/` | 特定场景验证 |

## 测试数据

- `data/` - 测试用例数据文件

## 运行测试

```bash
# 运行所有测试
python3 tests/run_tests.py

# 详细输出
python3 tests/run_tests.py -v

# 失败时停止
python3 tests/run_tests.py -f
```

## 添加新测试

1. 根据测试类型选择正确的子目录
2. 遵循现有测试命名规范
3. 复杂测试需提供说明文档
