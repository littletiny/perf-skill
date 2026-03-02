# 三层架构测试快速开始指南

> 本文档帮助开发者快速运行测试，验证 Core-Analysis-Composite 三层架构实现。

---

## 一分钟快速测试

### 1. 验证接口是否就绪

```bash
python3 tests/three_tier/verify_interfaces.py
```

**预期输出**：
- ✅ 表示接口已实现
- ❌ 表示接口待实现

### 2. 运行核心测试

```bash
# 方式一：使用统一入口（推荐）
python3 tests/three_tier/run_all_tests.py

# 方式二：使用简化入口（只显示结果摘要）
python3 tests/three_tier/quick_test.py
```

### 3. 查看结果

```
✅ 通过: 45
⚠️  跳过: 25 (依赖未实现模块)
❌ 失败: 0

状态: 可以开始集成测试
```

---

## 测试分类说明

| 测试类型 | 命令 | 用途 | 运行时间 |
|---------|------|------|---------|
| **接口验证** | `verify_interfaces.py` | 检查接口是否存在 | < 1s |
| **核心测试** | `quick_test.py` | 快速验证主要功能 | ~3s |
| **完整测试** | `run_all_tests.py` | 验证所有功能点 | ~10s |
| **单层测试** | `test_xxx.py` | 验证特定层 | ~2s |

---

## 开发 workflow

### Step 1: 实现 Core 层接口

```bash
# 实现后验证
python3 tests/three_tier/verify_interfaces.py | grep "Engine."

# 预期看到
# ✅ Engine.get_process_lifecycle()
# ✅ Engine.get_pid_cpu_distribution()
```

### Step 2: 运行 Core 层测试

```bash
python3 tests/three_tier/test_core_interfaces.py -v
```

### Step 3: 实现 Analysis Facade

```bash
# 实现后验证
python3 tests/three_tier/verify_interfaces.py | grep "Facade"

# 预期看到
# ✅ AnalysisFacade
# ✅   .analyze_comm_top()
```

### Step 4: 运行 Facade 测试

```bash
python3 tests/three_tier/test_facade_interfaces.py -v
```

### Step 5: 实现 Composite

```bash
# 实现后验证
python3 tests/three_tier/verify_interfaces.py | grep "composite"
```

### Step 6: 运行完整测试

```bash
python3 tests/three_tier/run_all_tests.py -v
```

---

## 常见问题

### Q: 测试报告 "ModuleNotFoundError"

**原因**: 被测试的模块尚未实现

**解决**: 这是正常的，实现对应模块后重新运行即可

```bash
# 例如 Facade 未实现时会报错
python3 tests/three_tier/test_facade_interfaces.py
# ImportError: AnalysisFacade 尚未实现

# 实现后再次运行即可通过
```

### Q: 如何只测试已实现的部分？

```bash
# 使用快速测试脚本，自动跳过未实现部分
python3 tests/three_tier/quick_test.py
```

### Q: 测试失败如何调试？

```bash
# 1. 运行单个测试文件，查看详细错误
python3 tests/three_tier/test_core_interfaces.py -v

# 2. 运行单个测试用例
python3 -m unittest tests.three_tier.test_core_interfaces.TestCoreInterfaces.test_get_process_lifecycle_interface

# 3. 查看跳过的测试
python3 tests/three_tier/test_facade_interfaces.py 2>&1 | grep SKIP
```

### Q: 如何验证 Trace 边界？

```bash
# 运行专门的 Trace 边界测试
python3 tests/three_tier/test_trace_boundary.py -v

# 关键验证点
# - test_composite_does_not_pollute_timeline
# - test_analyzer_internal_method_does_not_record_trace
```

---

## 测试数据

测试使用以下数据文件（自动检测）：

| 数据文件 | 用途 |
|---------|------|
| `tests/perfdata/new_format/case_test.data` | 主测试数据 |
| `tests/perfdata/perf_format/case_test.data` | 格式兼容性测试 |
| 自动生成 Mock 数据 | 数据不存在时使用 |

---

## 预期开发节奏

| 周次 | 任务 | 验证命令 | 预期通过率 |
|------|------|---------|-----------|
| Week 1 | Core 层实现 | `verify_interfaces.py` | 30% |
| Week 2 | Analysis Facade | `test_facade_interfaces.py` | 50% |
| Week 3 | Analyzer 重构 | `test_core_interfaces.py` | 70% |
| Week 4 | Composite 实现 | `test_composite_commands.py` | 85% |
| Week 5 | 集成联调 | `run_all_tests.py` | 95%+ |

---

## 一键测试脚本

创建 `test.sh`：

```bash
#!/bin/bash
echo "=== 三层架构快速测试 ==="
echo ""
echo "[1/3] 验证接口..."
python3 tests/three_tier/verify_interfaces.py | grep -E "(✅|❌)"
echo ""
echo "[2/3] 运行核心测试..."
python3 tests/three_tier/quick_test.py
echo ""
echo "[3/3] 完成"
```

运行：
```bash
chmod +x test.sh && ./test.sh
```

---

## 联系与支持

- 测试相关问题：查看 `tests/three_tier/README.md`
- 架构设计问题：查看 `docs/design-three-tier-architecture.md`
- 分工问题：查看 `docs/team-division-three-tier.md`
