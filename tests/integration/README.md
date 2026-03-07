# 三层架构集成测试

本目录包含 Core-Analysis-Composite 三层架构的集成测试，验证各层接口协作和 Trace 边界。

---

## 测试分类

| 测试文件 | 测试目标 | 验证点 | 预估用例数 |
|---------|---------|--------|-----------|
| `test_core_interfaces.py` | Core层接口 | Engine新接口正确性 | 15+ |
| `test_facade_interfaces.py` | Analysis Facade | 内部接口可用性、返回格式 | 12+ |
| `test_composite_commands.py` | Composite命令 | 组合诊断流程正确性 | 12+ |
| `test_trace_boundary.py` | Trace边界 | Composite调用不污染timeline | 10+ |
| `test_risk_integration.py` | Risk集成 | 三层risk流转与聚合 | 14+ |
| `test_three_tier_e2e.py` | 端到端测试 | 完整诊断流程 | 8+ |
| **总计** | | | **70+** |

---

## 快速开始

### 运行所有测试

```bash
# 使用统一入口
python3 tests/integration/run_all_tests.py

# 详细输出
python3 tests/integration/run_all_tests.py -v

# 失败时停止
python3 tests/integration/run_all_tests.py -f

# 只显示摘要
python3 tests/integration/run_all_tests.py -s
```

### 运行单个测试文件

```bash
# Core层接口测试
python3 tests/integration/test_core_interfaces.py

# Facade接口测试
python3 tests/integration/test_facade_interfaces.py

# Composite命令测试
python3 tests/integration/test_composite_commands.py

# Trace边界测试
python3 tests/integration/test_trace_boundary.py

# Risk集成测试
python3 tests/integration/test_risk_integration.py

# 端到端测试
python3 tests/integration/test_three_tier_e2e.py
```

### 详细输出模式

```bash
# 任何测试文件都支持 -v 参数
python3 tests/integration/test_core_interfaces.py -v
```

---

## 测试覆盖范围

### Core层接口测试 (`test_core_interfaces.py`)

**测试目标**: `core/engine.py` 新增接口

- `get_process_lifecycle()` - 进程生命周期分析
- `get_pid_cpu_distribution()` - PID级CPU分布
- `get_call_graph()` - 调用图分析
- CV/Monopoly计算工具函数
- 数据访问控制验证

### Facade接口测试 (`test_facade_interfaces.py`)

**测试目标**: `analysis/facade.py` AnalysisFacade

- 接口可用性: `analyze_comm_top`, `analyze_hotspots`, etc.
- 延迟加载机制
- 返回数据格式验证
- 错误处理
- 接口契约验证

### Composite命令测试 (`test_composite_commands.py`)

**测试目标**: `composite/*.py` 组合命令

- `sys-audit` 系统审计流程
- `bottleneck-analyze` 瓶颈追踪
- `storm-trace` 风暴溯源
- Risk聚合算法
- 输出格式验证

### Trace边界测试 (`test_trace_boundary.py`)

**测试目标**: Trace边界强制执行

- CLI调用触发Trace记录
- Composite内部调用不触发Trace
- Timeline纯净性验证
- Trace隔离性
- 违规检测

### Risk集成测试 (`test_risk_integration.py`)

**测试目标**: Risk三层流转

- Core层: `RiskMixin` 基础能力
- Analysis层: risk识别与上报
- Composite层: risk聚合算法
- 输出格式: `_risk` 字段
- 跨层流转验证

### 端到端测试 (`test_three_tier_e2e.py`)

**测试目标**: 完整诊断流程

- 数据加载 → 分析 → 输出
- 数据流验证
- Risk流验证
- Trace边界验证
- 错误处理

### 端到端测试 (`test_three_tier_e2e.py`)

**测试目标**: 完整诊断流程

- 瓶颈检测算法
- 调用链追踪
- 根因分析
- 报告生成

---

## 测试数据

测试使用 `tests/perfdata/` 下的样本数据：

| 数据文件 | 格式 | 用途 |
|---------|------|------|
| `new_format/case_test.data` | SPEAR格式 | 主测试数据 |
| `perf_format/case_test.data` | 原始perf格式 | 兼容性测试 |

测试数据不足时，测试会自动创建Mock数据。

---

## 测试原则

1. **层隔离**: Core测试不依赖Analysis/Composite实现
2. **接口契约**: Facade测试验证输入输出契约
3. **Trace纯净**: Trace边界测试验证无子命令污染
4. **Risk聚合**: Risk集成测试验证聚合算法正确性
5. **端到端**: E2E测试验证完整用户场景

---

## 理解测试结果

### 测试状态

| 状态 | 含义 | 处理建议 |
|-----|------|---------|
| ✅ 通过 | 测试通过 | 无需处理 |
| ⚠️ 跳过 | 依赖未实现 | 实现依赖模块后重试 |
| ❌ 失败 | 断言失败 | 检查实现逻辑 |
| 💥 错误 | 执行错误 | 检查代码语法/异常处理 |

### 常见故障排除

**ModuleNotFoundError**: 模块尚未实现，需实现对应接口后重试

**AssertionError**: 实现逻辑不符合预期，运行 `-v` 查看具体差异

**Trace边界测试失败**: Composite内部调用了记录Trace的方法，确保只有 `@command` 装饰器才记录Trace

---

## 调试技巧

```bash
# 运行单个测试用例
python3 -m unittest tests.integration.test_core_interfaces.TestCoreInterfaces.test_get_process_lifecycle_interface

# 查看跳过的测试
python3 tests/integration/test_facade_interfaces.py -v 2>&1 | grep SKIP

# 生成测试报告（需要安装unittest-xml-reporting）
python3 -m xmlrunner discover -s tests/integration -o reports/
```

---

## 持续集成建议

```bash
# 在CI中运行
python3 tests/integration/run_all_tests.py -v

# 或者按层并行运行
python3 tests/integration/test_core_interfaces.py &
python3 tests/integration/test_facade_interfaces.py &
python3 tests/integration/test_composite_commands.py &
wait
```

---

## 相关文档

- [架构设计文档](../../docs/design/design-three-tier-architecture.md) - 三层架构设计
- [接口规范](../../docs/interface/interface-core.md) - Core层接口规范
- [接口规范](../../docs/interface/interface-analysis.md) - Analysis层接口规范
- [接口规范](../../docs/interface/interface-composite.md) - Composite层接口规范
