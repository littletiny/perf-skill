# perf-hunter 测试目录

本目录包含 perf-hunter 各模块的专项测试，各测试目录相互隔离，独立运行。

---

## 目录结构

```
tests/
├── README.md                        # 本文件 - 测试目录总览
├── test_issue_overflow_warning.py   # Issue Overflow Warning 功能测试
├── perfdata/                        # 性能数据格式测试
│   ├── README.md
│   ├── test_perfdata.py
│   ├── new_format/                  # SPEAR 格式数据样本
│   └── perf_format/                 # 原始 perf 格式数据样本
├── scenario/                        # 场景测试（人工验证用）
│   ├── netstat/                     # netstat 进程风暴场景
│   └── ps/                          # ps 进程分析场景
└── spear_wrap/                      # spear_wrap CLI 回归测试
    ├── test_spear_wrap.py
    └── README.md
```

---

## 测试分类

### 1. 根目录功能测试

直接在 `tests/` 根目录下的测试文件，测试特定功能模块。

| 测试文件 | 用途 | 运行方式 |
|---------|------|----------|
| `test_issue_overflow_warning.py` | Issue Overflow Warning 和 Risk Auto-Recording 测试 | `python3 tests/test_issue_overflow_warning.py` |

### 2. 数据格式测试 (`perfdata/`)

测试不同 perf 数据格式的兼容性。

| 目录 | 用途 | 运行方式 |
|------|------|----------|
| `perfdata/` | 数据格式兼容性测试 | `python3 tests/perfdata/test_perfdata.py` |

### 3. CLI 回归测试 (`spear_wrap/`)

测试 spear CLI 各子命令的功能。

| 目录 | 用途 | 运行方式 |
|------|------|----------|
| `spear_wrap/` | CLI 回归测试 | `python3 tests/spear_wrap/test_spear_wrap.py` |

### 4. 场景测试 (`scenario/`)

真实场景的案例分析，用于人工验证和演示。

| 场景 | 描述 |
|------|------|
| `scenario/netstat/` | netstat 进程风暴 + 内核锁竞争场景 |
| `scenario/ps/` | ps 进程分析场景 |

---

## 运行测试

### Issue Overflow Warning 测试

```bash
# 运行全部测试
python3 tests/test_issue_overflow_warning.py

# 详细输出
python3 tests/test_issue_overflow_warning.py -v
```

### 数据格式测试

```bash
# 运行所有格式测试
python3 tests/perfdata/test_perfdata.py

# 详细输出
python3 tests/perfdata/test_perfdata.py -v

# 只测试指定格式
python3 tests/perfdata/test_perfdata.py -d new_format
python3 tests/perfdata/test_perfdata.py -d perf_format
```

### CLI 回归测试

```bash
python3 tests/spear_wrap/test_spear_wrap.py
python3 tests/spear_wrap/test_spear_wrap.py -v
python3 tests/spear_wrap/test_spear_wrap.py -f
```

### 场景测试

```bash
# 查看场景列表
ls tests/scenario/

# 按场景文档执行
bash tests/scenario/run_tests.sh
```

---

## 测试原则

- **目录隔离**: 各专项测试独立目录，互不干扰
- **纯标准库**: 所有 Python 测试使用标准库，无外部依赖
- **自包含**: 测试能独立运行，不依赖其他测试的执行顺序
- **自动化**: 优先使用自动化测试，减少人工验证

---

## 添加新测试

### 在根目录添加功能测试

如果测试的是某个特定功能（如 Issue Overflow Warning），直接在 `tests/` 根目录创建：

```python
# tests/test_<feature>.py
import unittest

class TestFeature(unittest.TestCase):
    def test_<case>(self):
        pass

if __name__ == "__main__":
    unittest.main()
```

### 在子目录添加专项测试

如果测试属于某个特定领域（如数据格式、CLI），放入对应子目录：

1. **单元测试**: 在对应模块的专项目录下添加 Python 脚本
2. **数据样本**: 放入 `perfdata/` 下相应格式目录
3. **场景测试**: 放入 `scenario/<scenario_name>/` 目录，包含:
   - `case.data` - 测试数据
   - `input.txt` - 测试输入描述
   - `DONOT_READ_IT/expect.md` - 预期输出（人工验证用）

---

## 测试状态

| 测试套件 | 用例数 | 状态 |
|---------|--------|------|
| test_issue_overflow_warning | 10 | ✅ 通过 |
| test_rules_loading | 9 | ✅ 通过 |
| test_external_rules_integration | 12 | ✅ 通过 |
| spear_wrap | 14 | ✅ 通过 |
| perfdata (new_format) | 14 | ✅ 通过 |
| perfdata (perf_format) | 14 | ✅ 通过 |
