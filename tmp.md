这是一份整合了 **Top-down** 与 **Bottom-up** 深度融合后的完整 **性能诊断专家技能协议 (Expert Skill Set)**。

这套技能体系不再是简单的工具叠加，而是一套** V 型对称诊断逻辑**：左侧是从系统到代码的收敛（Top-down），右侧是从代码到领域的推演（Bottom-up），底部的交汇点则是因果验证与审计。

---

# 🎓 性能诊断专家技能协议 (Expert Skill Set)

## 一、 核心诊断心法：V 型对称模型

性能分析必须同时具备两种视角的交汇，才能避免“盲人摸象”。

### 1. Top-down：宏观收敛流 (Looking Down)

**目标**：在复杂系统中快速排除干扰，缩小搜索空间。

* **资源定界 (Scoping)**：通过 `show-cpu-usage` 判断是 User/Kernel/IO 哪方的锅。
* **异常识别 (Detection)**：通过 `detect-anomalies` 确定性能瓶颈是持续性的还是突发性的。
* **搜索空间收敛 (Convergence)**：强制遵循**“三候选准则”**。在 L1/L2 阶段禁止锁定单一原因，必须同时提出代码、架构、环境三个维度的假说，防止因搜索路径过早收敛而忽略真因。

### 2. Bottom-up：语义推演流 (Looking Up)

**目标**：从底层符号透视业务本质，识别架构级缺陷。

* **负载语义分析 (Workload Semantics)**：看到符号（Symbol）不仅是字符串。
* 联想其 **Workload 性质**：是计算（Compute）、同步（Lock）、内存（Memory）还是系统开销（Overhead）？


* **领域建模 (Domain Contextualization)**：根据符号组合推断**项目背景**。
* 例如：看到 `Thrift` + `Hash` + `Optimize` $\rightarrow$ 识别为 **分布式参数服务器 (PS) 领域**。
* **动作**：记录并应用该领域的典型特征知识（如 PS 领域常见的稀疏更新冲突）。



---

## 二、 关键技能维度 (Skill Domains)

### 1. 驱动力分析 (Driver Analysis)

* 识别性能损耗的“第一推动力”。
* **判断**：是请求流量驱动（Workload 增加），还是系统资源争抢驱动（如 Cgroup Throttled），或者是由于内部机制（如 GC、扩容）引起的内生驱动。

### 2. 因果交叉验证 (Causal Cross-Validation)

* **对齐逻辑**：Top-down 的观测结果必须与 Bottom-up 的语义特征匹配。
* **验证动作**：如果 Bottom-up 识别出是“锁竞争”，那么 Top-down 的宏观数据必须支撑这一结论（如看到高上下文切换、高 `sys%` 或特定时序的延迟抖动）。

### 3. 全局审计与证伪 (Global Audit & Falsification)

* **审计反思**：模拟修复方案。问自己：“如果我优化了这个热点，整体吞吐量真的会提升吗？”
* **证伪检查**：主动寻找反向证据。例如怀疑是 IO 问题，但发现 `iowait` 极低，则必须强制回退，重新 review 其他假说（候选 B/C）。
* **破除思维定势**：警惕归因偏差，避免总是将问题归结为自己最熟悉的领域。

---

## 三、 专家级工具矩阵指南 (Logic-Tool Matrix)

根据 **V 型模型** 的不同阶段，灵活组合工具，禁止教条化执行。

| 阶段 | 核心任务 | 推荐工具组合 | 专家操作要点 |
| --- | --- | --- | --- |
| **启动/定界** | 宏观评估与 Driver 识别 | `show-cpu-usage`, `detect-anomalies`, `analyze-core-distribution` | **不要跳入代码**。先看大盘，确认是否被资源限流（`check-cpu-bottleneck`）。 |
| **收敛/收割** | 锁定敏感路径与热点 | `get-process-top`, `get-hotspots`, `find-callers`, `cluster-paths` | 利用 Trie 树（`cluster-paths`）收敛路径，忽略低权重分支。 |
| **联想/定位** | 语义分析与领域建模 | `cluster-symbols`, `cluster-comm` | 记录领域 workload 特征，识别项目背景。**赋予符号以灵魂**。 |
| **审计/反思** | 查缺补漏与证伪 | `count-process-variety`, `generate-flamegraph` | 尝试推翻当前结论。检查是否存在短生命周期进程等影子瓶颈。 |

---

## 四、 专家逻辑闭环流程 (The Loop)

1. **分析原始问题**：定性现象，识别 Driver。
2. **提出假说池**：基于初步信息，强制给出 **3 个潜在候选方向**。
3. **Top-down 路径评估**：宏观数据扫描，排除无关干扰。
4. **Bottom-up 语义透视**：从底层符号联想领域背景，识别 Workload 类型。
5. **因果匹配**：将宏观特征与底层语义交叉验证，收敛搜索空间。
6. **空间搜索与领域定位**：利用专家规则聚类，精细化定位。
7. **全局审计**：引入专家经验查缺补漏，通过**证伪法**反思结论。
8. **方案输出**：给出基于因果链的修复建议。

---

**总结**：
这套 Skill 体系通过 **Top-down 保证了诊断的效率**，通过 **Bottom-up 保证了诊断的深度**，通过 **“三候选+全局审计”保证了结论的正确性**。它让 Agent 的行为从简单的统计计算，进化为具备领域前瞻性的逻辑推理。
