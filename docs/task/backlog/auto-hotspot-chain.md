# 自动热点串联与冷函数折叠设计方案

## 核心思路

**无需白名单配置**，从数据本身学习热点，智能串联调用链。

```
传统方式: finish_task_switch -> __schedule -> schedule -> do_nanosleep -> ... (截断)
                                        ↑
新方式:   finish_task_switch -> .. -> FindInTableWithLock -> .. -> PushModel
              ↑                    ↑
           (热点保留)        (穿透冷函数，直达下一个热点)
```

## 算法设计

### HotspotsAwareExtractor

从全局数据学习热点（Top N by inclusive_pct），提取调用链时跳过冷函数。

```python
class HotspotsAwareExtractor:
    def __init__(self, samples: List[Sample]):
        self.hotspots = self._learn_hotspots(samples)  # 自动学习
    
    def _learn_hotspots(self, samples) -> Set[str]:
        # 策略: Top 20 + 占比 > 0.5% 的符号
        pass
    
    def extract(self, stack: List[str], target_idx: int) -> HotspotAwareChain:
        # 1. 从 target_idx+1 开始向上遍历
        # 2. 遇到热点函数 → 保留
        # 3. 遇到冷函数 → 跳过，计数+1
        # 4. 冷函数计数达到阈值 → 折叠为 ".."
        pass
```

### ColdFunctionFolder

```python
@dataclass
class FoldedCallchain:
    segments: List[ChainSegment]  # 段列表（热点段或折叠段）
    hotspot_count: int
    folded_count: int
```

**折叠策略:**
- 连续冷函数超过 2 个 → 折叠为 ".."
- 热点函数之间的距离 > 3 → 中间折叠
- 保留调用链骨架（热点+入口点）

## 输出格式示例

```
# 传统输出 (截断):
>>> finish_task_switch (11.60%)
  #1 [1.28%] __schedule <- schedule <- do_nanosleep <- ...

# 新输出 (自动穿透):
>>> finish_task_switch (11.60%) [穿透模式]
  #1 [5.50%] .. <- FindInTableWithLock <- InsertWithProb <- PushVecFid <- PushModel
     [穿透: __schedule <- schedule <- do_nanosleep <- hrtimer_nanosleep]
```

## 关键改进点

| 特性 | 传统方案 | 新方案 |
|-----|---------|-------|
| 配置 | 需要白名单 | 无需配置，数据驱动 |
| 穿透 | 仅白名单函数 | 所有热点函数自动穿透 |
| 长度 | 固定5层，易截断 | 动态折叠，保留完整骨架 |
| 可读性 | 内核函数淹没业务逻辑 | 突出热点，折叠冷函数 |

## 实现计划

| 任务 | 负责人 | 内容 |
|------|--------|------|
| HotspotsAwareExtractor | A | 热点学习算法 + 穿透提取逻辑 + 单元测试 |
| ColdFunctionFolder | B | 折叠算法 + 分段格式化 + 单元测试 |
| 输出格式化 | C | 紧凑/详细模式输出 + 热点路径高亮 |
| 集成 | D | 集成到 facade.analyze_callers + 回归测试 |

## 向后兼容

- 新增 `use_smart_chain=True` 参数
- 默认启用新功能
- 保留 `use_penetration` 作为备选
