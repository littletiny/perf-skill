# 设计决策与经验教训

> 记录关键设计决策背后的思考、踩坑经历和架构演进教训。
>
> 按主题组织，便于查阅特定领域的经验。

---

## 目录

- [诊断流程反思](#诊断流程反思)
- [方法论演进](#方法论演进)
- [工具设计教训](#工具设计教训)
- [输出系统演进](#输出系统演进)
- [文档体系演进](#文档体系演进)
- [通用设计原则](#通用设计原则)
- [参考](#参考)

---

## 诊断流程反思

### 领域知识被遗忘 (v0.7)

**案例**: PID 2573405 parameter_server 分析

**错误路径**
```
看到数据: 144% CPU, 单核满载
↓
工具分析: find-in-table-with-lock 是热点
↓
得出结论: 锁竞争导致串行化
↓
建议优化: 优化锁结构
```

**缺失的关键质疑**

> 「为什么参数服务器会设计成单核瓶颈？」

**应有表现**
- 参数服务器应支持高并发参数访问
- 预期 CPU: 800-1600%
- 实际 144% 严重不符合预期

**改进**: Step 0 领域知识激活

```yaml
1. 应用类型识别
   - 进程名: parameter_serve → 参数服务器
2. 领域知识激活
   - 预期性能: 800-1600% CPU
   - 常见瓶颈: 网络 I/O、锁竞争、内存带宽
3. 建立预期基准
   - 预期负载: 相对均衡分布在多核
4. 异常检测准备
   - 如果 CPU < 400%: 可能存在问题
```

### 目标一致性 (v2.7)

**问题**: Agent 使用 `find-callers` 时遗漏 `--pid` 参数

**后果**: 分析全系统数据而非目标进程，得出错误结论

**解决方案**

| 目标类型 | 必须添加的参数 | 错误后果 |
|---------|---------------|---------|
| 特定进程 | `--pid 12345` | 分析全系统数据，得出错误结论 |
| 特定进程组 | `--comm worker` | 混入其他进程数据，稀释信号 |
| 特定时段 | `--start-time/--end-time` | 被其他时段数据干扰 |

**检查清单**
- [ ] 用户是否指定了具体 PID？→ 所有命令加 `--pid`
- [ ] 用户是否提及进程名/服务名？→ 考虑加 `--comm`
- [ ] 问题是否有明确时间特征？→ 考虑加 `--start-time/--end-time`

### Live Document 机制 (v2.9)

**问题**: netstat/containerd-shim 案例

```
get-comm-top 发现 4 个高内核态进程:
  netstat:         2623 PIDs, 94.7% kernel  ← 分析 ✓
  containerd-shim:  240 PIDs, 89.9% kernel  ← 遗漏 ✗
  sh:                45 PIDs, 86.8% kernel  ← 遗漏 ✗
  python3:          826 PIDs, 82.3% kernel  ← 遗漏 ✗

搜索覆盖率: 1/4 = 25% (严重不足)
```

**根本原因**
- 人脑记忆有限，工具输出后无持久化
- 数字偏见：被 2623 大数字吸引
- 无客观审计机制

**解决方案**

```bash
# 结构化记录问题
spear trace add --id ISS-001 --desc "netstat 高内核态 94.7%"
spear trace add --id ISS-002 --desc "containerd-shim 高内核态 89.9%"

# 强制审计
spear trace list        # 查看待办
spear trace finalize    # 最终审计（pending 不为空时阻止生成报告）
```

**经验教训**

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 问题跟踪 | 人脑记忆 | Live Document 持久化 |
| 审计机制 | 无 | `trace list/finalize` 强制检查 |
| 覆盖率 | 依赖主观 | 强制 100% 或显式接受风险 |

---

## 方法论演进

### 从 SOP 到假设驱动 (v0.7 → v2.0)

**背景**

PID 2573405 案例分析暴露了严格线性 SOP 的问题：
- 过早收敛：看到 FindInTableWithLock 就认定是锁竞争
- 遗漏线索：看到 finish_task_switch 却没有溯源
- 无法并行验证多条假设

**决策**

放弃严格的 Step 1→2→3→4→5 流程，转向「多路径并行假设驱动」：
```
Step 1: 环境边界判定
    ↓
启动多条假设路径并行验证
    ├─→ 路径 A: 锁竞争假设
    ├─→ 路径 B: 调度问题假设
    └─→ 路径 C: 配置问题假设
    ↓
对比证据强度 → 收敛结论
```

**经验教训**

| 维度 | 原来 (SOP) | 现在 (假设驱动) |
|------|-----------|----------------|
| 工具选择 | 严格按 Step 选择 | 根据假设需要灵活选择 |
| 分析顺序 | 固定 1→2→3→4→5 | 多条路径并行 |
| 收敛时机 | 发现热点后立即深入 | 至少验证 3 条假设后才能收敛 |

**关键认知**

- 流程是手段，不是目的
- 假设驱动优于流程驱动
- 给 Agent 自由度 ≠ 放弃规范（关键检查点仍然强制）

---

## 工具设计教训

### 输出格式规范 (v2.10)

**核心原则**

1. **风险置顶**: 所有输出必须包含 `_risk` 字段
2. **时间字符串化**: ISO 8601 格式
3. **扁平化结构**: JSON 嵌套不超过 3 层

```json
{
  "_risk": {
    "level": "warning",
    "message": "发现 2 个高内核态进程组未分析",
    "hint": "建议并行分析: cluster-symbols --comm containerd-shim",
    "action_required": true
  },
  "summary": {...},
  "hotspots": [...]
}
```

### Risk Hint 设计

**演进过程**

| 版本 | Hint 设计 | 问题 |
|------|-----------|------|
| v2.10 | 建议性语气 | Agent 容易忽略 |
| v2.14 | 使用「强制性」「必须」措辞 | 语义强化 |
| v2.16 | `[必须] 添加到 Live Document: doc add ...` | 提供可执行模板 |

**最终规范**

```python
output.add_risk(
    "critical",
    "检测到进程风暴",
    "[必须] 添加到 Live Document: doc add --id <ISS-XXX> "
    "--desc '检测到进程风暴' --risk 'critical' "
    "--hint '对每个进程运行: cluster-symbols --comm <comm>'",
    patterns=["PROCESS_STORM"],
    targets=storm_comms  # 必须处理的目标列表
)
```

### 命名统一 (v2.28)

**core_sec → weight**

```python
# 统一命名前
total_core_per_sec, cluster_core_sec, lock_func_core_sec

# 统一命名后
total_weight, cluster_weight, lock_func_weight
```

**字段命名**
- `user_samples` → `user_records`
- `kernel_samples` → `kernel_records`

**原因**: 避免与原始 perf 采样混淆（数据已按 1 秒聚合）

---

## 输出系统演进

### V1: 原始字典方式

**问题**
- 14 个分析模块各自处理输出
- 字段名拼写错误无法检测
- 缺乏类型检查
- 重复代码：空样本检查、数据质量评估、JSON 输出

### V2: Dataclass 统一架构 (v2.17)

**决策**

引入 `@dataclass` 统一数据模型：
```python
@dataclass
class HotspotItem:
    symbol: str
    self: str        # "15.23%"
    inclusive: str   # "45.67%"
```

**架构**
```
core/
├── output_models.py       # 数据模型定义
├── output_adapter.py      # JSON 转换器
├── output_builder.py      # 输出构建器
├── text_output_adapter.py # 文本渲染
└── display_presets.py     # 显示配置
```

**效果**
- 代码量减少 21%（2058 行 → 1633 行）
- 类型安全，IDE 支持
- 输出格式完全一致

### 模板化重构 (v2.24 → v2.27)

**决策**

将格式化逻辑从命令代码中彻底解耦：

| 模板类型 | 适用场景 |
|---------|---------|
| `simple_list` | hotspots, processes |
| `key_value` | clusters, comm_groups |
| `table` | anomalies, windows |
| `nested` | traces |
| `custom` | bottleneck, cpu_usage |

**关键改进**

数据模型只存原始值，模板负责格式化：
```python
# Before: 存储格式化字符串
class AnomalyItem:
    time_range: str  # "2024-01-01T10:00:00 - 2024-01-01T10:00:05"

# After: 存储原始数据
class AnomalyItem:
    time_range_start: str
    time_range_end: str
```

---

## 文档体系演进

### 问题：职责边界模糊 (v2.4 之前)

| 问题 | 表现 | 影响 |
|------|------|------|
| SKILL.md ↔ workflow.md 重叠 | 两者都包含「标准工作流」 | 用户不知该看哪个 |
| workflow.md 过大 | 514 行 | 查找困难，信息过载 |
| tools.md 定位不清 | 既是命令参考，又包含分析要点 | 参考时分散注意力 |

### 5 层架构 (v2.15)

```
┌─ 第一层：入口引导层
│   └─ SKILL.md [102 行] - 快速开始 + 场景速查
│
├─ 第二层：场景模式层
│   └─ workflow-patterns.md - 5 种典型分析模式
│
├─ 第三层：核心流程层
│   └─ workflow-core.md - 7 Phase 分析流程
│
├─ 第四层：参考层
│   └─ tools.md - 纯命令参考
│
└─ 第五层：规则层
    ├─ heuristics.md - 启发式规则
    ├─ templates.md - 文档模板
    └─ data-format.md - 数据格式
```

**效果**

- SKILL.md 压缩 67%：311 行 → 102 行
- 用户问题「sys 开销高怎么办？」→ 直达 workflow-patterns.md 模式 E

### 文档维护规范

**章节编号规范**
- 禁止使用数字编号（如 `### 1. xxx`）
- 统一使用标题文字本身作为标识

**命令与文档同步规范**
- 修改 CLI 命令时，必须同步更新 SKILL.md 和 references/tools.md

---

## 通用设计原则

### 简单优先

- let it crash，不做复杂错误处理
- 数据文件规范：只使用本工具读取 `.data` 文件
- 尽量少用 regex，尤其避免在对外参数中使用

### AI 友好

- 输出格式便于人类/AI 阅读
- 扁平化 JSON 结构（最多 3 层嵌套）
- 风险信息置顶（`_risk` 字段）

### 渐进式具体化

Risk hint 构建原则：
1. 优先使用用户提供的参数
2. 其次从数据中推断
3. 最后提供获取方法

---

## 参考

- 详细变更记录: `CHANGELOG.md`
- 设计文档: `design-rationale-trace-v1.md`, `design-rationale-trace-v2.md`
- 输出格式规范: `output-format-spec.md`
