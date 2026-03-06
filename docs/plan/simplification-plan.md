# 符号处理机制简化计划

## 当前提交复杂度分析

最新提交 `532478f` 引入了一个"comprehensive symbol processing mechanism"，改动规模如下：

| 类别 | 新增代码行数 | 说明 |
|------|-------------|------|
| 核心代码 | ~2500行 | symbol.py, callchain_formatter.py, callchain_extractor.py, smart_callchain.py, defaults.py |
| 测试代码 | ~1920行 | 5个单元测试文件 |
| 设计文档 | ~1600行 | 4个设计/计划文档 |
| Demo脚本 | ~527行 | 2个demo文件 |
| 配置文件 | ~248行 | symbol_rules.json |
| **总计** | **~6800行** | 33个文件改动 |

## 主要问题

### 1. 功能重复
- `CallchainExtractor` 和 `SmartCallchainExtractor` 功能高度重叠
- 两者都实现了"智能提取调用链"，但实现方式不同
- 增加了维护成本和认知负担

### 2. 过度设计
- `SymbolRules` 支持 4 种规则类型：hidden/merge_up/merge_down/collapse
- `ProcessedStack` 记录了详细的操作历史（用于调试，但增加了复杂度）
- 支持通配符匹配（fnmatch），但大部分场景只需要精确匹配

### 3. 测试过度
- 1920行测试代码，许多测试是验证内部实现细节
- 存在大量 mock 代码（为开发阶段准备的 fallback）

### 4. 文档膨胀
- 1600+行设计文档，有些内容重复
- Demo 脚本体积过大

## 简化原则

遵循 AGENTS.md 的"简单优先"原则：
> **简单优先**: let it crash，不做复杂错误处理
> **禁止多版本共存**: 不要写 v1/v2 或多版本兼容代码

## 简化方案

### Phase 1: 核心精简（建议立即执行）

#### 1.1 合并调用链提取器
- **保留**: `SmartCallchainExtractor`（功能更完整）
- **移除**: `CallchainExtractor`
- **影响文件**: 
  - 删除 `scripts/perf_toolkit/analysis/callchain_extractor.py`
  - 更新 `callchain_formatter.py` 中的 fallback mock
  - 删除 `tests/unit/test_callchain_extractor.py`
- **预计减少**: ~735行代码

#### 1.2 简化 SymbolRules
- **保留**: 
  - `hidden`: 完全隐藏 runtime 函数（最常用）
  - `collapse`: 将 syscall 等折叠为组（用于聚类）
- **延迟实现**（后续按需添加）:
  - `merge_up`: 向上合并到 caller
  - `merge_down`: 向下合并到 callee
- **预计减少**: ~200行代码

#### 1.3 移除冗余 Mock 代码
- 多处 try/except ImportError + mock class 模式
- 如果模块不存在，直接让 import 失败
- **影响文件**: callchain_formatter.py, callchain_extractor.py（删除后无影响）
- **预计减少**: ~150行代码

### Phase 2: 测试精简

#### 2.1 移除重复测试
- `test_callchain_extractor.py`（删除，因为删除 CallchainExtractor）
- `test_kernel_awareness.py`（部分测试可以合并到 test_symbol_processor.py）
- **预计减少**: ~713行测试代码

#### 2.2 精简测试用例
- 每个功能保留核心测试，移除边界情况测试
- 从 435行 -> 200行
- 从 487行 -> 200行
- **预计减少**: ~500行测试代码

### Phase 3: 文档精简

#### 3.1 合并设计文档
- 将 `symbol-processing.md` 和 `symbol-rules-config.md` 合并为一篇
- **预计减少**: ~200行文档

#### 3.2 简化 Demo 脚本
- `demo_symbol_processor.py` 和 `demo_commands_with_symbol_processing.py` 合并
- 移除详细的示例说明，保留核心演示
- **预计减少**: ~300行代码

## 简化后规模估算

| 类别 | 简化前 | 简化后 | 减少 |
|------|--------|--------|------|
| 核心代码 | ~2500行 | ~1500行 | -40% |
| 测试代码 | ~1920行 | ~700行 | -63% |
| 设计文档 | ~1600行 | ~1000行 | -37% |
| Demo脚本 | ~527行 | ~200行 | -62% |
| **总计** | **~6800行** | **~3400行** | **-50%** |

## 分工建议（3-4人并行）

### 人员 A: 核心代码精简
**任务**: 清理重复的提取器和过度设计的功能
**涉及文件**:
- `scripts/perf_toolkit/analysis/callchain_extractor.py` (删除)
- `scripts/perf_toolkit/analysis/smart_callchain.py` (精简)
- `config/defaults.py` (简化 SymbolRules，移除 merge_up/merge_down)
- `config/symbol_rules.json` (简化配置)

**交付标准**:
- [ ] CallchainExtractor 完全移除
- [ ] SmartCallchainExtractor 保留核心功能
- [ ] SymbolRules 只保留 hidden + collapse
- [ ] ProcessedStack 移除 operation tracking（或改为可选）
- [ ] 所有单元测试通过

### 人员 B: 格式化器清理
**任务**: 清理 callchain_formatter 的复杂度
**涉及文件**:
- `scripts/perf_toolkit/core/callchain_formatter.py`
- `scripts/perf_toolkit/core/symbol.py` (清理 mock fallback)

**交付标准**:
- [ ] 移除所有 try/except ImportError + mock 模式
- [ ] LayeredCallchainFormatter 保留 compact 模式，detailed 模式改为可选
- [ ] 移除 format_callchain_for_bottleneck 中的 fallback 逻辑
- [ ] 所有单元测试通过

### 人员 C: 测试精简 + Demo 合并
**任务**: 精简测试代码，合并 demo 脚本
**涉及文件**:
- `tests/unit/test_callchain_extractor.py` (删除)
- `tests/unit/test_kernel_awareness.py` (合并到 test_symbol_processor.py)
- `tests/unit/test_symbol_processor.py` (精简)
- `tests/unit/test_callchain_formatter.py` (精简)
- `tests/unit/test_smart_callchain.py` (精简)
- `scripts/demo_symbol_processor.py` (合并)
- `scripts/demo_commands_with_symbol_processing.py` (合并)

**交付标准**:
- [ ] 删除 test_callchain_extractor.py
- [ ] 合并 test_kernel_awareness.py 到 test_symbol_processor.py
- [ ] 每个测试文件控制在 200行以内
- [ ] 两个 demo 脚本合并为一个 ~200行的 demo
- [ ] 所有测试通过

### 人员 D: 文档整理（可与 A/B/C 并行）
**任务**: 合并和精简设计文档
**涉及文件**:
- `docs/design/symbol-processing.md`
- `docs/design/symbol-rules-config.md`
- `docs/plan/plan-auto-hotspot-chain.md`
- `docs/plan/plan-fix-callchain-truncation.md`

**交付标准**:
- [x] symbol-processing.md 和 symbol-rules-config.md 合并为一篇 (~250行)
- [x] 删除 plan-fix-callchain-truncation.md 中的实现细节，保留设计思想 (~300行)
- [x] plan-auto-hotspot-chain.md 精简为计划概述 (~100行)
- [ ] 更新 docs/project-structure.md

## 执行顺序

```
Phase 1 (核心精简)
├── A: 开始 SymbolRules 简化
└── B: 开始 formatter 清理

Phase 2 (测试精简)
├── C: 等待 A 完成后，精简 symbol processor 测试
└── C: 等待 B 完成后，精简 formatter 测试

Phase 3 (集成验证)
├── A + B: 集成测试
└── C: 最终测试验证

并行: D 文档整理 (全程)
```

## 风险评估

### 低风险
- 删除 mock fallback 代码（这些本就不应该存在于生产代码）
- 合并 demo 脚本
- 精简文档

### 中风险
- 删除 CallchainExtractor（需要确认 facade.py 没有直接依赖）
- 简化 SymbolRules（可能影响已有的调用链输出格式）

### 缓解措施
- 每次修改前运行 `python3 tests/run_tests.py` 验证
- 保留简化前的分支 `git branch backup/symbol-processing-before-simplification`

## 验证清单

简化完成后，必须验证：

```bash
# 1. 运行所有测试
python3 tests/run_tests.py

# 2. 验证核心命令仍能工作
python3 -m scripts.perf_toolkit find-callers --help
python3 -m scripts.perf_toolkit cluster-paths --help
python3 -m scripts.perf_toolkit bottleneck-trace --help

# 3. 验证 demo 能运行
python3 scripts/demo_symbol_processor.py
```
