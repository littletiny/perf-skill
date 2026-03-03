# perf-hunter 测试目录

本目录包含 perf-hunter 各模块的测试，按类型分层组织。

---

## 目录结构

```
tests/
├── README.md                 # 本文件 - 测试目录总览
├── run_tests.py              # 统一测试入口
├── unit/                     # 单元测试
│   ├── README.md
│   ├── test_risk_display_config.py
│   └── test_perfdata.py
├── functional/               # 功能测试
│   ├── README.md
│   ├── test_issue_overflow_warning.py
│   └── test_trace_audit.py
├── integration/              # 集成测试（三层架构）
│   ├── README.md
│   ├── run_all_tests.py
│   ├── test_core_interfaces.py
│   ├── test_facade_interfaces.py
│   ├── test_composite_commands.py
│   ├── test_trace_boundary.py
│   ├── test_risk_integration.py
│   ├── test_bottleneck_tracer.py
│   └── test_three_tier_e2e.py
├── cli/                      # CLI 回归测试
│   ├── README.md
│   └── test_shecr_wrap.py
├── data/                     # 测试数据
│   ├── README.md
│   ├── new_format/           # SPEAR 格式数据样本
│   └── perf_format/          # 原始 perf 格式数据样本
└── scenario/                 # 场景测试（人工验证用）
    ├── ns/                   # netstat 进程风暴场景
    ├── ps/                   # ps 进程分析场景
    └── run_tests.sh
```

---

## 测试分类

### 单元测试 (`unit/`)

测试单个模块的基础功能。

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `unit/test_risk_display_config.py` | Risk 显示配置加载与格式化测试 | `python3 tests/unit/test_risk_display_config.py` |
| `unit/test_perfdata.py` | 性能数据格式兼容性测试 | `python3 tests/unit/test_perfdata.py` |

### 功能测试 (`functional/`)

测试系统级功能模块。

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `functional/test_issue_overflow_warning.py` | Issue Overflow Warning 功能测试 | `python3 tests/functional/test_issue_overflow_warning.py` |
| `functional/test_trace_audit.py` | Trace Audit 功能测试 | `python3 tests/functional/test_trace_audit.py` |

### 集成测试 (`integration/`)

Core-Analysis-Composite 三层架构的集成测试。

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `integration/test_core_interfaces.py` | Core 层接口测试 | `python3 tests/integration/test_core_interfaces.py` |
| `integration/test_facade_interfaces.py` | Facade 接口测试 | `python3 tests/integration/test_facade_interfaces.py` |
| `integration/test_composite_commands.py` | Composite 命令测试 | `python3 tests/integration/test_composite_commands.py` |
| `integration/test_trace_boundary.py` | Trace 边界测试 | `python3 tests/integration/test_trace_boundary.py` |
| `integration/test_risk_integration.py` | Risk 集成测试 | `python3 tests/integration/test_risk_integration.py` |
| `integration/test_bottleneck_tracer.py` | 瓶颈追踪测试 | `python3 tests/integration/test_bottleneck_tracer.py` |
| `integration/test_three_tier_e2e.py` | 端到端测试 | `python3 tests/integration/test_three_tier_e2e.py` |

运行所有集成测试：
```bash
python3 tests/integration/run_all_tests.py
```

### CLI 测试 (`cli/`)

CLI 回归测试。

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `cli/test_shecr_wrap.py` | shecr CLI 功能测试 | `python3 tests/cli/test_shecr_wrap.py` |

### 场景测试 (`scenario/`)

真实场景的案例分析，用于人工验证和演示。

| 场景 | 描述 |
|------|------|
| `scenario/ns/` | netstat 进程风暴 + 内核锁竞争场景 |
| `scenario/ps/` | ps 进程分析场景 |

---

## 运行所有测试

### 统一测试入口

```bash
# 运行所有自动化测试
python3 tests/run_tests.py

# 详细输出
python3 tests/run_tests.py -v

# 失败时停止
python3 tests/run_tests.py -f

# 只列出测试文件
python3 tests/run_tests.py -l
```

---

## 测试原则

- **目录隔离**: 各专项测试独立目录，互不干扰
- **纯标准库**: 所有 Python 测试使用标准库，无外部依赖
- **自包含**: 测试能独立运行，不依赖其他测试的执行顺序
- **自动化**: 优先使用自动化测试，减少人工验证

---

## 添加新测试

### 单元测试

在 `tests/unit/` 目录下添加新的测试文件：

```python
# tests/unit/test_<module>.py
import unittest

class TestModule(unittest.TestCase):
    def test_<case>(self):
        pass

if __name__ == "__main__":
    unittest.main()
```

### 集成测试

在 `tests/integration/` 目录下添加新的测试文件，并更新 `README.md`。

### 功能测试

在 `tests/functional/` 目录下添加新的测试文件，并更新 `README.md`。

### 场景测试

在 `tests/scenario/<scenario_name>/` 目录下创建：
- `case.data` - 测试数据
- `input.txt` - 测试输入描述
- `expect/` - 预期输出（人工验证用）

---

## 测试状态

| 测试套件 | 用例数 | 状态 | 备注 |
|---------|--------|------|------|
| unit/test_risk_display_config | 13 | ✅ 通过 | |
| unit/test_perfdata | 14+14 | ✅ 通过 | 两种格式各14个 |
| functional/test_issue_overflow_warning | 8 | ✅ 通过 | 2个测试跳过（功能禁用） |
| functional/test_trace_audit | 5 | ✅ 通过 | |
| cli/test_shecr_wrap | 19 | ✅ 通过 | |
| integration/* | 70+ | ✅ 通过 | 部分测试跳过（依赖未实现） |

---

## 测试数据

测试数据存放在 `tests/data/`：

| 数据文件 | 格式 | 用途 |
|---------|------|------|
| `data/new_format/case_test.data` | SPEAR 格式 | 主测试数据 |
| `data/perf_format/case_test.data` | 原始 perf 格式 | 兼容性测试 |
