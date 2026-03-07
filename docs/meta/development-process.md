# 多人协同开发流程

> 通用方法论：从需求到代码的七步流程

---

## 概述

本流程适用于需要多人协作的中大型功能开发，核心思想：

- **先设计后编码**：文档先行，接口先行
- **接口契约**：通过接口文档解耦多人开发
- **并行开发**：横向/纵向拆分，最大化并行度
- **测试驱动**：E2E 先行定义验收标准，单元测试保障质量

---

## 七步流程

```
Step 1: 原始需求
    ↓
Step 2: 设计文档 + 设计意图
    ↓ (确认)
Step 3: 协同拆分 = 横向模块 + 纵向链路 + 接口契约 + E2E测试
    ↓
Step 4: 并行开发 (SubAgent) + 单元测试
    ↓
Step 5: 回归测试
    ↓
Step 6: 文档同步检查
    ↓
Step 7: Commit 拆分
```

---

## Step 1: 原始需求

**输入**: 用户编写 `docs/requirements/<feature>-requirements.md`

**内容要求**:
- 问题陈述：要解决什么问题
- 业务场景：谁会使用，如何使用
- 验收标准：什么样的结果算完成
- 非功能性需求：性能、安全、兼容性等约束

**示例结构**:
```markdown
# 需求：性能分析器增强

## 问题
当前无法分析多进程间的资源竞争

## 场景
用户运行微服务架构，需要识别跨进程瓶颈

## 验收标准
- [ ] 支持多进程聚合分析
- [ ] 输出包含进程间依赖关系
- [ ] 分析时间 < 30s (1GB 数据)

## 约束
- 不修改现有单进程分析 API
```

---

## Step 2: 设计拆分

**Agent 任务**: 读取原始需求，产出两份文档

### 2.1 设计文档 `docs/design/<feature>-design.md`

描述"做什么"和"怎么做"：
- 架构图/数据流图
- 核心数据结构
- 关键算法/逻辑
- 外部依赖

### 2.2 设计意图文档 `docs/design/<feature>-rationale.md`

描述"为什么这么做"：
- 方案对比（为什么选 A 不选 B）
- 权衡考虑
- 潜在风险及缓解措施

**确认检查点**: 
- [ ] 用户确认设计满足需求
- [ ] 技术方案评审通过
- [ ] 不通过则返回 Step 1 或 Step 2

---

## Step 3: 协同拆分（关键步骤）

**目标**: 将设计拆分为可并行开发的独立任务

### 3.1 拆分维度

**横向（按模块）**:
```
模块 A: 数据采集层
模块 B: 分析引擎层  
模块 C: 输出渲染层
```

**纵向（按数据流）**:
```
链路 1: 原始数据 → 清洗 → 存储
链路 2: 查询 → 分析 → 结果生成
链路 3: 结果 → 格式化 → 输出
```

**混合拆分示例**:
| 开发者 | 职责 | 交付物 |
|--------|------|--------|
| A | 接口定义者 | `interface.py` + 接口文档 |
| B | 数据层实现 | `data_*.py` + 单元测试 |
| C | 分析层实现 | `analyzer_*.py` + 单元测试 |
| D | 集成者 | 组装 + E2E 测试 |

### 3.2 接口契约文档

`docs/design/<feature>-interfaces.md` 示例内容：

    ## 模块间接口

    ### DataCollector → Analyzer
    ```python
    @dataclass
    class RawData:
        samples: List[Sample]
        metadata: DataMeta

    class DataCollector:
        def collect(self, source: str) -> RawData: ...
    ```

    ### Analyzer → Formatter
    ```python
    @dataclass  
    class AnalysisResult:
        hotspots: List[HotSpot]
        score: float

    class Analyzer:
        def analyze(self, data: RawData) -> AnalysisResult: ...
    ```

### 3.3 公共基础库

`docs/design/<feature>-shared.md`:
- 公共数据结构
- 工具函数
- 常量定义
- 错误处理规范

### 3.4 E2E 测试先行

`tests/e2e/test_<feature>.py`:
```python
def test_multi_process_analysis():
    """验收标准：多进程分析完整链路"""
    # Given: 模拟多进程 perf 数据
    input_data = generate_mock_data(processes=5)
    
    # When: 执行分析
    result = analyzer.run(input_data)
    
    # Then: 验证结果
    assert result.process_count == 5
    assert result.cross_process_deps is not None
    assert result.duration < 30  # 性能约束
```

**确认检查点**:
- [ ] 拆分后任务无循环依赖
- [ ] 每个任务有明确输入/输出
- [ ] E2E 测试覆盖所有验收标准

---

## Step 4: 并行开发

**策略**: 每个子任务启动独立 SubAgent

### 4.1 开发顺序

**第一波（可完全并行）**:
- 公共基础库开发者
- 各模块接口定义者

**第二波（依赖第一波）**:
- 各模块实现者（基于已定义的接口）

**第三波（依赖第二波）**:
- 集成者（组装各模块）

### 4.2 SubAgent 任务模板

```
任务: 实现 [模块名]

输入:
- 设计文档: docs/design/<feature>-design.md
- 接口文档: docs/design/<feature>-interfaces.md
- 公共库: [路径]

要求:
1. 实现接口定义的所有方法
2. 编写单元测试，覆盖率 > 80%
3. 遵循项目编码规范
4. 输出: [文件列表] + 测试通过证明

禁止:
- 修改接口定义（如需修改，发起变更请求）
- 依赖未完成的模块（使用 Mock）
```

### 4.3 单元测试要求

每个模块必须有:
- `tests/unit/test_<module>.py`
- 覆盖正常路径 + 边界条件 + 错误处理
- Mock 外部依赖

---

## Step 5: 回归测试

**目标**: 验证集成功能符合预期

### 5.1 测试层级

```
单元测试（Step 4 已完成）
    ↓
集成测试: 模块间接口调用
    ↓
E2E 测试（Step 3 已定义）
    ↓
性能测试: 验证性能约束
```

### 5.2 回归清单

- [ ] 所有单元测试通过
- [ ] 集成测试通过
- [ ] E2E 测试通过（验证验收标准）
- [ ] 性能测试通过（如有时）
- [ ] 无回归：原有功能测试全部通过

**失败处理**:
- 单元测试失败 → 返回对应开发者修复
- 集成/E2E 失败 → 检查接口契约是否被违反
- 性能不达标 → 返回 Step 3 优化设计

---

## Step 6: 文档同步检查

**目标**: 确保文档与代码一致

### 6.1 检查项

| 文档类型 | 检查内容 | 更新责任 |
|----------|----------|----------|
| 设计文档 | 实现是否与设计一致 | 如有偏差，更新设计文档或回滚代码 |
| 接口文档 | 实际接口是否与定义一致 | 代码为准，更新接口文档 |
| 用户文档 | 新功能是否已记录 | 补充到 references/ 或 SKILL.md |
| AGENTS.md | 如有架构变更，是否更新 | 更新架构说明 |

### 6.2 不一致处理

**原则**: 代码优先，文档跟进

1. 接口与实现不符 → 以代码为准，更新接口文档
2. 设计被调整 → 记录变更原因，更新设计文档
3. 新增依赖 → 更新项目结构文档

---

## Step 7: Commit 拆分

**目标**: 提交历史清晰，便于回滚和审查

### 7.1 拆分原则

| 类型 | 是否单独 commit | 示例 |
|------|----------------|------|
| 接口定义 | ✅ 单独 | `feat: define analyzer interfaces` |
| 公共库 | ✅ 单独 | `feat: add shared data structures` |
| 模块实现 | ✅ 每个模块单独 | `feat: implement data collector` |
| 单元测试 | ✅ 随模块一起 | 或 `test: add tests for data collector` |
| 集成代码 | ✅ 单独 | `feat: integrate multi-process analyzer` |
| 文档更新 | ✅ 单独 | `docs: update interface documentation` |
| Bug 修复 | ✅ 单独 | `fix: handle empty input in collector` |

### 7.2 Commit 顺序

```
1. 接口定义 + 文档
2. 公共基础库
3. 模块 A 实现 + 测试
4. 模块 B 实现 + 测试
5. 模块 C 实现 + 测试
6. 集成代码 + E2E 测试
7. 文档更新（用户文档、接口文档）
```

### 7.3 Commit Message 规范

```
<type>(<scope>): <subject>

<body>

Refs: #<issue-number>
```

**Type 定义**:
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档
- `test`: 测试
- `refactor`: 重构
- `chore`: 构建/工具

---

## 快速决策表

| 场景 | 处理建议 |
|------|----------|
| 需求不明确 | 拒绝进入 Step 2，返回补充需求 |
| 设计评审不通过 | 返回 Step 2 修改设计或 Step 1 调整需求 |
| 拆分后发现循环依赖 | 返回 Step 3 重新设计接口，打破循环 |
| 开发中发现接口不合理 | 发起变更请求，冻结依赖方，更新接口文档 |
| E2E 测试失败 | 检查是集成问题（回 Step 4）还是设计问题（回 Step 3）|
| 文档与代码不一致 | 以代码为准，更新文档（除非设计被违反）|
| Commit 过大 | 拆分：接口/实现/测试/文档分离 |

---

## 相关文档

- 代码位置导航: [navigation.md](navigation.md)
- 文档架构设计: [documentation-architecture.md](documentation-architecture.md)
- 接口规范: [../interface/](../interface/)
