# SPEAR-perf-hunter v2.1 更新日志

## 更新概览

本次更新包含以下改进：
1. **Bug 修复**: `cluster-symbols --custom-rules` 现在支持列表格式的规则
2. **新功能**: 新增 `analyze-core-distribution` 工具，支持核心级负载分布分析
3. **文档更新**: 重构 SKILL.md 为规则驱动的泛化方法论

---

## 1. Bug 修复: cluster-symbols --custom-rules

### 问题
当使用 `--custom-rules` 参数传入 JSON 对象，且值为列表时会报错：
```bash
TypeError: unhashable type: 'list'
```

### 修复
修改文件: `scripts/perf_toolkit/analysis/clusters.py`

修复内容: 支持 pattern 为列表或字符串格式
```python
# 支持 pattern 为列表或字符串
if isinstance(pattern, list):
    pattern_str = '|'.join(pattern)
else:
    pattern_str = pattern
if re.search(pattern_str, sym):
    matched_groups.add(group)
```

### 使用方式
```bash
# 方式 1: 字符串格式 (正则表达式)
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --custom-rules '{"SCHEDULING": "schedule|nanosleep"}'

# 方式 2: 列表格式 (自动转换)
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --custom-rules '{"SCHEDULING": ["schedule", "nanosleep"]}'
```

---

## 2. 新功能: analyze-core-distribution

### 用途
分析进程在各 CPU 核心的负载分布，识别：
- 负载不均衡程度 (单核饱和 vs 均衡分布)
- 线程状态分布 (active vs sleeping)
- 各核心热点函数

### 典型场景
解决 PID 2573405 案例中暴露的问题：
- 72 个核心都有线程分布，但 1 个核心满载，其他几乎空闲
- 需要区分"锁竞争"vs"主动休眠"导致的瓶颈

### 使用方法
```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data perf.script \
  --pid 2573405
```

### 输出示例
```json
{
  "summary": {
    "total_cores_with_activity": 72,
    "max_utilization_pct": 97.45,
    "min_utilization_pct": 0.21,
    "avg_utilization_pct": 2.0,
    "imbalance_level": "CRITICAL",
    "imbalance_description": "单核满载，其他核心几乎空闲"
  },
  "cores": [
    {
      "cpu_id": 40,
      "utilization_pct": 97.45,
      "states": {"active": 2}
    },
    {
      "cpu_id": 81,
      "utilization_pct": 9.06,
      "states": {"sleeping": 1, "active": 1}
    }
  ],
  "patterns": [
    {
      "type": "SINGLE_CORE_SATURATION",
      "suggestion": "检查锁竞争、CPU亲和性绑定或应用层主动休眠"
    }
  ]
}
```

### 关键指标
- `imbalance_level`: LOW/MEDIUM/HIGH/CRITICAL
- `imbalance_ratio`: 最大利用率 / 平均利用率
- `states`: sleeping (休眠) / active (活跃)
- `patterns`: 自动检测到的异常模式

---

## 3. 文档重构

### SKILL.md 改进

**从**: 决策树驱动的步骤指南 (Step 1→2→3→4→5)

**到**: 规则驱动的方法论框架

**核心变化**:
1. **前置领域知识激活** (Step 0)
   - 强调先建立预期，再验证差距
   - 应用类型识别 → 建立性能基线 → 对比现实

2. **竞争性假设并行验证**
   - 至少同时维护 3 条假设
   - 发散→探索→收敛的循环

3. **异常驱动分析**
   - 只有"预期 vs 现实"有差距才深入
   - 工具服务于假设验证

4. **关键检查点**
   - 发现调度函数 → 必须溯源
   - 发现负载不均衡 → 必须用 `analyze-core-distribution`
   - 发现锁函数 → 必须评估粒度

### tools.md 改进

1. **新增工具**: `analyze-core-distribution` 详细说明
2. **新增模式**: "负载不均衡分析"工作流
3. **修复说明**: `--custom-rules` 支持列表格式

---

## 工具联动改进

### 原有模式
```
# 模式 1: 探索式诊断
check-cpu-bottleneck → cluster-paths → find-callers --auto-target

# 模式 2: 定向分析
get-hotspots → find-callers --target <func>
```

### 新增模式
```
# 模式 4: 负载不均衡分析
check-cpu-bottleneck → analyze-core-distribution → find-callers --target <调度函数>
```

---

## 文件变更清单

### 修改的文件
1. `scripts/perf_toolkit/analysis/clusters.py`
   - 修复 `--custom-rules` 列表格式支持

2. `scripts/perf_expert.py`
   - 导入 `cmd_analyze_core_distribution`
   - 添加 `analyze-core-distribution` 子命令
   - 添加命令映射

3. `SKILL.md`
   - 重构为规则驱动的泛化方法论
   - 添加 `analyze-core-distribution` 说明
   - 添加工具参考附录

4. `references/tools.md`
   - 添加 `analyze-core-distribution` 详细说明
   - 添加 `--custom-rules` 使用示例
   - 更新工具清单和工作流

### 新增的文件
1. `scripts/perf_toolkit/analysis/core_distribution.py`
   - 新工具实现

2. `CHANGES.md` (本文件)
   - 变更日志

---

## 验证测试

### cluster-symbols 修复验证
```bash
python3 scripts/perf_expert.py cluster-symbols \
  --data perf.script \
  --pid 2573405 \
  --custom-rules '{"SCHEDULING": ["schedule", "nanosleep"]}'
# 输出正常，无 TypeError
```

### analyze-core-distribution 功能验证
```bash
python3 scripts/perf_expert.py analyze-core-distribution \
  --data perf.script \
  --pid 2573405
# 正确识别 SINGLE_CORE_SATURATION 和 WIDE_DISTRIBUTION_LOW_UTIL 模式
```

---

## 使用建议

### 对于单核瓶颈场景
1. 使用 `check-cpu-bottleneck` 确认瓶颈类型
2. 使用 `analyze-core-distribution` 分析负载分布
   - 如果 `imbalance_level` = CRITICAL → 检查调度/休眠问题
   - 如果多核都有负载但低 → 检查锁竞争
3. 使用 `find-callers` 溯源热点函数

### 对于负载不均衡场景
1. 使用 `analyze-core-distribution` 获取全貌
2. 关注 `patterns` 字段的自动检测
3. 结合 `cluster-symbols` 分析调度行为
4. 使用 `--custom-rules` 自定义关注特定模式

---

## v2.2 (2026-02-28)

### 重构 tools.md —— Top-Down + Bottom-Up 混合分析模式

#### 修改理由
原 tools.md 采用平铺式的工具列表组织方式，缺乏结构化的分析流程指导。实际性能分析需要结合：
1. **Top-Down 宏观切入**: 从系统级概览建立上下文
2. **Bottom-Up 微观溯源**: 从热点函数逐层深入

#### 修改内容
1. **新增分析流程总览图**: 清晰展示 7 个分析阶段及其关系
2. **按分析阶段重组工具**: Phase 1→7 的渐进式分析路径
3. **新增语义分析章节**: 根据符号名猜测 workload 和技术领域
4. **新增专家经验查缺补漏章节**: 关键信号检查清单和全局一致性检查
5. **新增典型分析模式**: 4 种快捷路径（单进程高 CPU、系统缓慢、进程风暴、负载不均衡）
6. **保留原有内容**: 内核函数规范化、CPU 利用率计算、可靠性评估、通用参数

#### 文件变更
- `references/tools.md`: 完全重构，从 392 行扩展为结构化文档

---

更新日期: 2026-02-28
版本: v2.2
