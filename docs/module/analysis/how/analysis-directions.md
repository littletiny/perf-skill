# 分析方向性设计：Top-Down vs Bottom-Up

> **Fork Drowning Problem and Bidirectional Convergence**
>
> 为什么性能分析需要双向汇聚，以及两种分析方向的不可替代性

---

## 1. 分叉淹没问题（Fork Drowning Problem）

### 1.1 问题定义

在调用链分析中，**调用栈的分叉点越靠近根部，单一方向的分析越容易丢失重要模式**。

```
示例调用结构：

                    main (inclusive: 100%)
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
       init       worker*       monitor
        │            │            │
   ┌────┴────┐   ┌───┴───┐        │
   ▼         ▼   ▼       ▼        ▼
  cfgA     cfgB  A       B      health

实际样本分布：
- main → init → cfgA (5%)
- main → init → cfgB (3%)
- main → worker1 → A → B (20%)
- main → worker1 → A → C (15%)
- main → worker2 → A → B (12%)
- main → worker2 → C → D (8%)
- main → monitor → health (2%)
```

### 1.2 单向分析的盲区

| 分析方向 | 能看到什么 | 丢失什么 |
|----------|-----------|----------|
| **Top-Down** (从 main 开始) | main→init (8%), main→worker* (55%), main→monitor (2%) | worker1 和 worker2 被分散到不同路径，A 的共性被淹没 |
| **Bottom-Up** (从热点开始) | B(32%), C(15%), D(8%), cfgA(5%)... | 不知道 B 分别来自 worker1→A 和 worker2→A |

**核心问题**：单一方向的分析会在分叉点处"淹没"重要的中间层模式。

---

## 2. 两种分析方向的对比

### 2.1 Top-Down：路径聚类 (cluster-paths)

**原理**：从调用栈根部（叶节点）向上构建 Trie，寻找公共前缀

```
叶到根路径：
  B → A → worker1 → main (20%)
  C → A → worker1 → main (15%)
  B → A → worker2 → main (12%)
  D → C → worker2 → main (8%)

Trie 聚合结果：
  B→A→worker1→main (20%)
  C→A→worker1→main (15%)
  B→A→worker2→main (12%)  ← worker1/worker2 被分散
  D→C→worker2→main (8%)   ← C 被分散到不同分支
```

**优势**：
- 自动发现调用路径模式
- 无需预设热点目标
- 适合探索性分析

**局限**：
- 早期分叉导致路径分散
- 难以识别跨分支的共性（如 worker1 和 worker2 都是 worker）

### 2.2 Bottom-Up：热点溯源 (find-callers)

**原理**：从热点函数向上追溯调用者

```
假设 hotspots self 排序：B(20%), A(15%), C(12%), D(8%)...

find-callers --target B:
  A → worker1 → main (20%)
  A → worker2 → main (12%)
  
find-callers --target A:
  worker1 → main (35%)  ← 15+20
  worker2 → main (12%)
```

**优势**：
- 精准定位热点来源
- 不受早期分叉影响
- 适合已知目标的深度分析

**局限**：
- 需要预设目标（或使用 auto-target 逐个分析）
- 多热点时输出分散，人眼难以关联

---

## 3. 与 Flame Graph / Call Graph 的类比

### 3.1 Flame Graph（火焰图）≈ Top-Down

**特征**：
- 从根部向下展开调用栈
- 宽度表示样本数量（inclusive）
- 颜色通常表示函数类型或差异

**问题**：
```
Flame Graph 展示：
┌─────────────────────────────────────────┐ 100% main
│ ┌───────────────┐ ┌───────────────────┐ │
│ │ init (8%)     │ │ worker* (55%)     │ │
│ │ ┌───┬───┐     │ │ ┌───┬───┬───┬───┐ │ │
│ │cfgA│cfgB│     │ │ A  │ A │ C │...│ │ │
│ └───┴───┘     │ └───┴───┴───┴───┘ │ │
└─────────────────────────────────────────┘

问题：worker1→A 和 worker2→A 在图中不连续，
      人眼难以发现 A 是共性中间节点
```

### 3.2 Call Graph（调用图）≈ Bottom-Up

**特征**：
- 以函数为节点，调用关系为边
- 可以双向遍历（caller/callee）
- 通常用于单函数分析

**问题**：
```
Call Graph 展示（以 B 为中心）：

  B ←── A ←── worker1 ←── main
  ↑
  └── A ←── worker2 ←── main

问题：多热点时需要生成多个子图，
      难以在全局视角下对比不同热点的调用上下文
```

### 3.3 类比总结

| 特性 | Flame Graph (Top-Down) | Call Graph (Bottom-Up) | cluster-paths | find-callers |
|------|------------------------|------------------------|---------------|--------------|
| **视角** | 全局调用树 | 局部调用关系 | 全局路径聚类 | 局部热点溯源 |
| **优势** | 全局结构感 | 精确关系 | 自动模式发现 | 精准定位 |
| **盲区** | 早期分叉分散 | 缺乏全局上下文 | 早期分叉 | 目标依赖 |
| **适用** | 探索性分析 | 定向分析 | 发现主要调用模式 | 热点根因确认 |

---

## 4. 双向汇聚的必要性

### 4.1 单一方向的局限

**纯 Top-Down 的陷阱**：
```
main → X → Y → Z → A (hot 30%)
main → X → Y → W → B (hot 25%)

Top-Down 看到：
- main→X→Y→Z→A (30%)
- main→X→Y→W→B (25%)

丢失：Y 是共同上游，可能 Y 层有问题
```

**纯 Bottom-Up 的陷阱**：
```
find-callers --target A: X→Y→Z (30%)
find-callers --target B: X→Y→W (25%)

丢失：需要人眼对比才能发现 X→Y 是共性
```

### 4.2 双向汇聚的收益

```
Top-Down (cluster-paths):
  发现主要路径模式，识别分叉点位置
  
Bottom-Up (find-callers):
  从热点向上追溯，验证具体调用链

汇聚点：
  当 cluster-paths 显示 "main→X→Y→* (55%)"
  且 find-callers A/B 都经过 X→Y 时
  → 确认 Y 层是共同上游，优先分析 Y
```

### 4.3 工具组合策略

| 诊断阶段 | 推荐工具 | 目的 |
|----------|----------|------|
| **探索阶段** | cluster-paths | 发现主要调用模式，确定分叉点位置 |
| **定位阶段** | hotspots + find-callers | 识别热点，精准溯源 |
| **验证阶段** | 两者对比 | 确认热点路径与全局模式的一致性 |

---

## 5. 在 SHECR 方法论中的定位

### 5.1 三层架构映射

```
Composite Layer:
  bottleneck-analyze (内部组合: hotspots + find-callers topN)
  
Analysis Layer:
  ├─ cluster-paths → Top-Down 路径聚类
  ├─ get-hotspots → 热点识别
  └─ find-callers → Bottom-Up 溯源

汇聚检查点 (Convergence Point):
  当 bottleneck-analyze 无法明确根因时，
  使用 cluster-paths 补充全局视角
```

### 5.2 与 Hierarchical Driver 的关系

在 `methodology-hierarchical-debugging.md` 的 V 型模型中：

```
Top-Down (假设生成)          Bottom-Up (证据聚合)
     │                             │
  L3 调度假设                  cluster-paths 模式
     │                             │
  L4 代码假设                  find-callers 溯源
     │                             │
     └───────────┬─────────────────┘
                 ▼
        ┌─────────────────┐
        │ 假设-证据交汇点  │
        │ cluster-paths   │ ← 提供"全局结构"证据
        │ 与 hotspots     │
        │ 一致性验证      │
        └─────────────────┘
```

---

## 6. 结论

### 6.1 核心观点

1. **分叉淹没是固有局限**：任何单一方向的分析都会在分叉点处丢失信息
2. **Top-Down 适合探索**：`cluster-paths` 自动发现调用模式，无需预设目标
3. **Bottom-Up 适合定位**：`find-callers` 精准溯源，不受早期分叉影响
4. **双向汇聚是必要的**：只有对比两种方向的输出，才能识别真正的共同上游

### 6.2 实践建议

**默认工作流**（覆盖 90% 场景）：
```bash
# Composite 层一键诊断
shecr bottleneck-analyze --comm <name>
# 内部自动执行: hotspots → find-callers(top1)
```

**深度分析工作流**（复杂场景）：
```bash
# Step 1: Top-Down 探索全局模式
shecr cluster-paths --comm <name> --min-depth 3

# Step 2: Bottom-Up 定位热点
shecr get-hotspots --comm <name> --sort-by self
shecr find-callers --target <hotspot>

# Step 3: 汇聚验证
# 对比 cluster-paths 的路径模式与 find-callers 的调用链
# 确认是否存在共同上游
```

### 6.3 设计决策

**保留 cluster-paths 的独立性的理由**：

1. **语义差异**：`cluster-paths` 是模式发现工具，`find-callers` 是溯源工具
2. **使用场景不同**：探索阶段 vs 定位阶段
3. **输出形态互补**：全局路径列表 vs 单函数调用树
4. **双向验证需求**：方法论要求假设-证据交汇，两者提供不同维度的证据

---

## 参考

- [methodology-hierarchical-debugging.md](./methodology-hierarchical-debugging.md) - 分层驱动调试方法论
- [design-three-tier-architecture.md](./design-three-tier-architecture.md) - 三层架构设计
- Brendan Gregg's Flame Graph: https://www.brendangregg.com/flamegraphs.html
- Call Graph (Computer Science): https://en.wikipedia.org/wiki/Call_graph

---

*文档版本: 1.0*
*创建时间: 2026-03-03*
