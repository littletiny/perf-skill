# 三层架构测试指南

本文档提供三层架构（Core-Analysis-Composite）测试的完整指南。

---

## 目录

1. [快速开始](#快速开始)
2. [测试脚本说明](#测试脚本说明)
3. [按开发阶段运行测试](#按开发阶段运行测试)
4. [理解测试结果](#理解测试结果)
5. [故障排除](#故障排除)

---

## 快速开始

### 方式一：一键测试（推荐）

```bash
# 运行完整的测试流程
./tests/three_tier/test.sh
```

### 方式二：Python 脚本

```bash
# 快速验证（~3秒）
python3 tests/three_tier/quick_test.py

# 完整测试（~10秒）
python3 tests/three_tier/run_all_tests.py

# 接口验证（~1秒）
python3 tests/three_tier/verify_interfaces.py
```

---

## 测试脚本说明

### 1. verify_interfaces.py - 接口验证

**用途**: 检查各层接口是否存在

**运行**: `python3 tests/three_tier/verify_interfaces.py`

**输出示例**:
```
Layer 1: Core层接口验证
  ✅ PerfExpertEngine
  ✅ Engine.get_process_lifecycle()
  ❌ Engine.get_pid_cpu_util()       # 待实现

Layer 2: Analysis层接口验证
  ✅ AnalysisFacade
  ✅   .analyze_comm_top()
```

**适用场景**: 
- 开发前查看需要实现哪些接口
- 实现后验证接口是否存在

---

### 2. quick_test.py - 快速测试

**用途**: 快速验证主要功能点

**运行**: `python3 tests/three_tier/quick_test.py`

**输出示例**:
```
测试结果
  ✅ 通过: 45
  ⚠️  跳过: 25 (依赖未实现模块)
  ❌ 失败: 0

状态: 可以开始集成测试
```

**适用场景**:
- 日常开发快速验证
- CI/CD 集成
- 提交前检查

---

### 3. run_all_tests.py - 完整测试

**用途**: 验证所有功能点

**运行**: 
```bash
# 简洁模式
python3 tests/three_tier/run_all_tests.py

# 详细模式
python3 tests/three_tier/run_all_tests.py -v

# 失败时停止
python3 tests/three_tier/run_all_tests.py -f
```

**适用场景**:
- 完整回归测试
- 发布前验证
- 详细问题定位

---

### 4. 单层测试

**Core 层测试**:
```bash
python3 tests/three_tier/test_core_interfaces.py -v
```

**Facade 测试**:
```bash
python3 tests/three_tier/test_facade_interfaces.py -v
```

**Composite 测试**:
```bash
python3 tests/three_tier/test_composite_commands.py -v
```

**Trace 边界测试**:
```bash
python3 tests/three_tier/test_trace_boundary.py -v
```

**Risk 集成测试**:
```bash
python3 tests/three_tier/test_risk_integration.py -v
```

---

## 按开发阶段运行测试

### Week 1: Core 层开发

```bash
# 1. 查看需要实现的接口
python3 tests/three_tier/verify_interfaces.py | grep "Engine."

# 2. 实现后验证
python3 tests/three_tier/verify_interfaces.py

# 3. 运行 Core 层测试
python3 tests/three_tier/test_core_interfaces.py -v
```

**预期结果**: Core 层接口 100% 通过

---

### Week 2-3: Analysis 层开发

```bash
# 1. 验证 Facade 接口
python3 tests/three_tier/verify_interfaces.py | grep "Facade"

# 2. 运行 Facade 测试
python3 tests/three_tier/test_facade_interfaces.py -v

# 3. 运行 Risk 集成测试
python3 tests/three_tier/test_risk_integration.py -v
```

**预期结果**: 
- Facade 接口 100% 通过
- Risk 识别和上报正确

---

### Week 4: Composite 层开发

```bash
# 1. 验证 Composite 命令
python3 tests/three_tier/verify_interfaces.py | grep "composite"

# 2. 运行 Composite 测试
python3 tests/three_tier/test_composite_commands.py -v

# 3. 运行 Trace 边界测试（关键）
python3 tests/three_tier/test_trace_boundary.py -v
```

**预期结果**:
- Composite 命令通过
- Trace 不被污染（无嵌套命令）
- Risk 聚合正确

---

### Week 5: 集成联调

```bash
# 1. 运行完整测试
python3 tests/three_tier/run_all_tests.py -v

# 2. 运行端到端测试
python3 tests/three_tier/test_three_tier_e2e.py -v

# 3. 一键验证
./tests/three_tier/test.sh
```

**预期结果**: 所有测试 95%+ 通过

---

## 理解测试结果

### 测试状态

| 状态 | 含义 | 处理建议 |
|-----|------|---------|
| ✅ 通过 | 测试通过 | 无需处理 |
| ⚠️ 跳过 | 依赖未实现 | 实现依赖模块后重试 |
| ❌ 失败 | 断言失败 | 检查实现逻辑 |
| 💥 错误 | 执行错误 | 检查代码语法/异常处理 |

### 跳过（Skip）的常见原因

```
⚠️ 跳过: AnalysisFacade尚未实现
```

**原因**: 被测试的模块尚未实现
**解决**: 实现对应模块后重新运行

---

## 故障排除

### 问题 1: "ModuleNotFoundError"

**现象**:
```
ImportError: cannot import name 'AnalysisFacade'
```

**原因**: 模块尚未实现

**解决**: 
1. 查看 `verify_interfaces.py` 确认哪些接口缺失
2. 实现缺失的接口
3. 重新运行测试

---

### 问题 2: "AssertionError"

**现象**:
```
AssertionError: 期望结果 != 实际结果
```

**原因**: 实现逻辑不符合预期

**解决**:
1. 运行详细模式查看具体差异: `-v`
2. 检查实现代码
3. 如果是测试本身的问题，更新测试用例

---

### 问题 3: 测试运行很慢

**现象**: 测试耗时超过 30 秒

**原因**: 可能加载了大量数据或陷入循环

**解决**:
1. 使用 Mock 数据代替真实数据
2. 检查是否有无限循环
3. 使用 `quick_test.py` 代替完整测试

---

### 问题 4: Trace 边界测试失败

**现象**:
```
FAILED: test_composite_does_not_pollute_timeline
```

**原因**: Composite 内部调用了记录 Trace 的方法

**解决**:
1. 确保 Analyzer 内部方法不操作 Trace
2. 确保 Facade 接口不自动记录 Trace
3. 只有 `@command` 装饰器才记录 Trace

---

## 测试覆盖矩阵

| 功能 | Core测试 | Facade测试 | Composite测试 | Trace测试 | Risk测试 | E2E测试 |
|-----|---------|-----------|--------------|----------|---------|---------|
| Engine接口 | ✅ | - | - | - | - | ✅ |
| Facade接口 | - | ✅ | - | - | - | ✅ |
| Composite命令 | - | - | ✅ | - | - | ✅ |
| Trace边界 | - | - | - | ✅ | - | ✅ |
| Risk流转 | - | - | - | - | ✅ | ✅ |
| CV/Monopoly计算 | ✅ | - | - | - | - | - |
| Risk聚合 | - | - | ✅ | - | ✅ | - |
| 数据流 | - | ✅ | - | - | - | ✅ |
| 错误处理 | ✅ | ✅ | ✅ | - | - | ✅ |

---

## 最佳实践

1. **先验证接口，再运行测试**
   ```bash
   python3 tests/three_tier/verify_interfaces.py
   ```

2. **日常开发使用快速测试**
   ```bash
   python3 tests/three_tier/quick_test.py
   ```

3. **提交前运行完整测试**
   ```bash
   python3 tests/three_tier/run_all_tests.py
   ```

4. **单独调试失败用例**
   ```bash
   python3 tests/three_tier/test_core_interfaces.py -v
   ```

---

## 相关文档

- [测试目录 README](./README.md) - 详细测试说明
- [快速开始指南](./QUICKSTART.md) - 一分钟上手
- [架构设计文档](../../docs/design-three-tier-architecture.md) - 架构设计
- [团队分工文档](../../docs/team-division-three-tier.md) - 开发分工

---

## 更新日志

| 日期 | 版本 | 变更 |
|-----|------|-----|
| 2026-03-03 | v1.0 | 初始版本 |
