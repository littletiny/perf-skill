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

### 1. 热点感知提取器 (HotspotsAwareExtractor)

```python
class HotspotsAwareExtractor:
    """
    热点感知调用链提取器
    
    核心思想：
    1. 自动从全局数据学习热点函数（Top N by inclusive_pct）
    2. 提取调用链时，跳过冷函数，直达下一个热点或源头
    3. 无需配置，完全数据驱动
    """
    
    def __init__(self, samples: List[Sample]):
        # 从样本中学习热点
        self.hotspots = self._learn_hotspots(samples)
        
    def _learn_hotspots(self, samples) -> Set[str]:
        """
        学习热点函数
        
        策略：
        1. 计算每个符号的 inclusive_pct
        2. 取 Top N (如 Top 20) 作为热点
        3. 同时包含占比 > 0.5% 的符号
        """
        symbol_weights = defaultdict(float)
        for s in samples:
            weight = get_sample_weight(s)
            for sym in s.stack.get_normalized_names():
                symbol_weights[sym] += weight
        
        # 按权重排序，取 Top 20 + 占比 > 0.5% 的
        total = sum(symbol_weights.values())
        sorted_syms = sorted(symbol_weights.items(), key=lambda x: x[1], reverse=True)
        
        hotspots = set()
        for sym, weight in sorted_syms[:20]:  # Top 20
            hotspots.add(sym)
        for sym, weight in sorted_syms:  # 占比 > 0.5%
            if weight / total > 0.005:
                hotspots.add(sym)
        
        return hotspots
    
    def extract(self, stack: List[str], target_idx: int) -> HotspotAwareChain:
        """
        提取调用链
        
        算法：
        1. 从 target_idx+1 开始向上遍历
        2. 如果遇到热点函数 → 保留
        3. 如果遇到冷函数 → 跳过，计数+1
        4. 当冷函数计数达到阈值 → 折叠为 ".."
        5. 直达栈底或遇到下一个热点
        """
        pass
```

### 2. 冷函数折叠器 (ColdFunctionFolder)

```python
@dataclass
class FoldedCallchain:
    """折叠后的调用链"""
    segments: List[ChainSegment]  # 段列表（热点段或折叠段）
    hotspot_count: int            # 经过的热点数
    folded_count: int             # 被折叠的函数数


@dataclass  
class ChainSegment:
    """调用链段"""
    type: str  # "hotspot" | "folded" | "normal"
    symbols: List[str]  # 段内的符号
    fold_count: int     # 如果是 folded 段，表示折叠了多少个函数


class ColdFunctionFolder:
    """
    冷函数折叠器
    
    折叠策略：
    1. 连续冷函数超过 2 个 → 折叠为 ".."
    2. 热点函数之间的距离 > 3 → 中间折叠
    3. 保留调用链骨架（热点+入口点）
    """
    
    def fold(self, 
             stack: List[str], 
             hotspots: Set[str],
             min_fold_threshold: int = 2) -> FoldedCallchain:
        """
        折叠冷函数
        
        Args:
            stack: 完整调用栈
            hotspots: 热点函数集合
            min_fold_threshold: 最少连续冷函数数才折叠
        """
        segments = []
        current_normal = []
        current_cold = []
        
        for sym in stack:
            if sym in hotspots:
                # 遇到热点：先处理待处理的冷函数
                if len(current_cold) >= min_fold_threshold:
                    segments.append(ChainSegment(
                        type="folded", symbols=[".."], fold_count=len(current_cold)
                    ))
                elif current_cold:
                    # 冷函数不够折叠阈值，算作 normal
                    current_normal.extend(current_cold)
                
                # 保留热点
                current_normal.append(sym)
                segments.append(ChainSegment(
                    type="hotspot", symbols=current_normal, fold_count=0
                ))
                current_normal = []
                current_cold = []
            else:
                current_cold.append(sym)
        
        # 处理剩余
        if len(current_cold) >= min_fold_threshold:
            segments.append(ChainSegment(
                type="folded", symbols=[".."], fold_count=len(current_cold)
            ))
        elif current_cold:
            segments.append(ChainSegment(
                type="normal", symbols=current_cold, fold_count=0
            ))
        
        return FoldedCallchain(
            segments=segments,
            hotspot_count=sum(1 for s in segments if s.type == "hotspot"),
            folded_count=sum(s.fold_count for s in segments if s.type == "folded")
        )
```

## 输出格式

### 示例 1: finish_task_switch (热点穿透)

```
# 传统输出 (截断):
>>> finish_task_switch (11.60%)
  #1 [1.28%] __schedule <- schedule <- do_nanosleep <- hrtimer_nanosleep <- __x64_sys_nanosleep

# 新输出 (自动穿透，直达业务热点):
>>> finish_task_switch (11.60%) [穿透模式]
  #1 [5.50%] .. <- FindInTableWithLock <- InsertWithProb <- PushVecFid <- PushModel <- PushModels <- zero_copy_push
     [穿透: __schedule <- schedule <- do_nanosleep <- hrtimer_nanosleep <- __x64_sys_nanosleep <- __GI___nanosleep]
     [热点路径: finish_task_switch -> .. -> FindInTableWithLock -> PushVecFid]
  #2 [5.47%] .. <- FindInTableWithLock <- Find <- FetchVec <- FetchOneModel <- FetchModels <- zero_copy_fetch
```

### 示例 2: 多层热点串联

```
# 当调用链中有多个热点时，自动串联
>>> __schedule (15.20%) [内核热点]
  #1 [8.30%] .. <- FindInTableWithLock <- .. <- PushModel <- .. <- zero_copy_push
     [热点链: __schedule -> .. -> FindInTableWithLock -> PushModel -> zero_copy_push]
     [折叠: do_nanosleep <- hrtimer_nanosleep <- __x64_sys_nanosleep <- __GI___nanosleep (4层)]
```

### 示例 3: 紧凑模式 (默认)

```
>>> finish_task_switch (11.60%)
  #1 [5.50%] ..→FindInTableWithLock→InsertWithProb→PushVecFid→PushModel→PushModels→zero_copy_push
  #2 [5.47%] ..→FindInTableWithLock→Find→FetchVec→FetchOneModel→FetchModels→zero_copy_fetch
  
>>> AdamOptimizer::Optimize (70.19%)
  #1 [49.26%] VecParameter::Update→PushVecFid→PushModel→PushModels→zero_copy_push→process_zero_copy_push
```

## 关键改进点

| 特性 | 传统方案 | 新方案 |
|-----|---------|-------|
| 配置 | 需要白名单 | 无需配置，数据驱动 |
| 穿透 | 仅白名单函数 | 所有热点函数自动穿透 |
| 长度 | 固定5层，易截断 | 动态折叠，保留完整骨架 |
| 可读性 | 内核函数淹没业务逻辑 | 突出热点，折叠冷函数 |
| 源头 | 常看不到源头 | 直达业务源头 |

## 实现计划

### 任务 1: HotspotsAwareExtractor (Owner: A)
- 实现热点学习算法
- 实现穿透提取逻辑
- 单元测试

### 任务 2: ColdFunctionFolder (Owner: B)  
- 实现折叠算法
- 实现分段格式化
- 单元测试

### 任务 3: 输出格式化 (Owner: C)
- 紧凑模式输出
- 详细模式输出
- 热点路径高亮

### 任务 4: 集成 (Owner: D)
- 集成到 facade.analyze_callers
- 替换现有 bottleneck 输出
- 回归测试

## 向后兼容

- 新增 `use_smart_chain=True` 参数
- 默认启用新功能
- 保留 `use_penetration` 作为备选
