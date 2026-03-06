# Callchain 截断问题修复计划

## 问题概述

`finish_task_switch` 等内核函数的调用链被过早截断，无法显示关键的业务调用源（如 `FindInTableWithLock`）。

根因：`facade.py:247` 硬编码 `caller_stack = normalized_names[idx+1:idx+6]`，只取5层，导致跨内核/用户态边界的调用链被截断。

---

## 架构设计

### 核心改进点

```
┌─────────────────────────────────────────────────────────────┐
│                    CallchainExtractor                       │
│         (新增：智能调用链提取，支持跨态穿透)                  │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │  DepthPolicy │   │ BoundaryDet  │   │   Formatter  │
   │  (深度策略)   │   │ (边界检测)   │   │  (分层输出)   │
   └──────────────┘   └──────────────┘   └──────────────┘
```

### 接口定义

```python
# === 模块A: symbol.py 新增 ===
class KernelAwareness:
    """内核感知工具类"""
    
    # 需要穿透分析的内核函数白名单
    PENETRATION_TARGETS: Set[str] = {...}
    
    @staticmethod
    def is_kernel_function(symbol_name: str) -> bool:
        """判断是否为内核函数"""
        pass
    
    @staticmethod
    def should_penetrate(symbol_name: str) -> bool:
        """判断是否需要穿透到用户态"""
        pass


# === 模块B: callchain_extractor.py 新增 ===
@dataclass
class ExtractedCallchain:
    """提取的调用链结果"""
    kernel_path: List[str]           # 内核态路径（可选）
    user_entry_point: Optional[str]  # 用户态入口点
    business_callers: List[str]      # 业务调用链
    penetration_depth: int           # 实际穿透深度


class CallchainExtractor:
    """智能调用链提取器"""
    
    def __init__(self, max_depth: int = 10, 
                 kernel_penetration: bool = True):
        self.max_depth = max_depth
        self.kernel_penetration = kernel_penetration
    
    def extract(self, 
                stack: List[str], 
                target_idx: int,
                target_symbol: str) -> ExtractedCallchain:
        """
        提取调用链
        
        Args:
            stack: 完整调用栈
            target_idx: 目标函数在栈中的索引
            target_symbol: 目标函数名
            
        Returns:
            ExtractedCallchain: 提取结果
        """
        pass


# === 模块C: callchain_formatter.py 修改 ===
class LayeredCallchainFormatter:
    """分层调用链格式化器"""
    
    def format_kernel_user_separated(
        self, 
        extracted: ExtractedCallchain,
        weight: float
    ) -> str:
        """
        格式化内核/用户态分离的调用链
        
        输出示例:
        #3 [5.50%] FindInTableWithLock <- InsertWithProb <- ...
           [kernel: __schedule <- schedule <- do_nanosleep <- ...]
        """
        pass
```

---

## 任务拆分

### 开发人员 A - 内核感知与策略层 (Owner: TBD)

**任务**: 实现内核函数识别和穿透策略

**文件**:
- `scripts/perf_toolkit/core/symbol.py` (修改)
- `config/defaults.py` (修改 - 添加白名单配置)

**交付物**:
```python
# symbol.py 新增
class KernelAwareness:
    """
    内核感知工具类
    
    识别需要穿透分析的内核函数，用于跨态调用链分析。
    """
    
    # 从配置加载
    PENETRATION_TARGETS: Set[str] = set()
    
    # 内核函数特征关键字
    KERNEL_INDICATORS = ['_[k]', '_[kernel]', ...]
    
    @classmethod
    def load_config(cls, config: Dict):
        """从配置加载白名单"""
        targets = config.get('kernel_penetration_targets', [])
        cls.PENETRATION_TARGETS = set(targets)
    
    @staticmethod
    def is_kernel_function(symbol_name: str, 
                          module: Optional[str] = None) -> bool:
        """
        判断是否为内核函数
        
        规则:
        1. 名称以 _[k] 结尾
        2. module 包含 kernel.kallsyms
        3. 名称匹配内核函数模式
        """
        pass
    
    @staticmethod
    def should_penetrate(symbol_name: str) -> Tuple[bool, str]:
        """
        判断是否需要穿透到用户态
        
        Returns:
            Tuple[bool, str]: (是否穿透, 原因)
        """
        pass
    
    @staticmethod
    def find_user_entry_point(stack: List[str], 
                              start_idx: int) -> Optional[int]:
        """
        在栈中找到用户态入口点索引
        
        从内核对齐函数出发，找到第一个用户态函数的位置
        """
        pass
```

**配置添加** (config/defaults.py):
```python
# 需要穿透分析的内核函数白名单
KERNEL_PENETRATION_TARGETS = [
    'finish_task_switch',
    '__schedule',
    'schedule',
    'switch_mm_irqs_off',
    'native_safe_halt',
    'do_nanosleep',
    'hrtimer_nanosleep',
    # ... 其他
]

# 调用链提取配置
CALLCHAIN_EXTRACTION = {
    'default_max_depth': 10,
    'kernel_penetration_max_depth': 15,
    'min_kernel_layers': 3,  # 至少保留的内核层数
}
```

**验收标准**:
- [ ] `KernelAwareness.is_kernel_function("finish_task_switch_[k]")` 返回 True
- [ ] `KernelAwareness.should_penetrate("finish_task_switch")` 返回 (True, "in_whitelist")
- [ ] `find_user_entry_point` 能正确识别 `__GI___nanosleep` 位置
- [ ] 单元测试覆盖所有场景

---

### 开发人员 B - 调用链提取核心 (Owner: TBD)

**任务**: 实现智能调用链提取器

**文件**:
- `scripts/perf_toolkit/analysis/callchain_extractor.py` (新建)

**依赖接口** (由 A 提供):
```python
from ..core.symbol import KernelAwareness

# 使用示例
is_kernel = KernelAwareness.is_kernel_function(symbol)
should_pen = KernelAwareness.should_penetrate(target)
user_idx = KernelAwareness.find_user_entry_point(stack, target_idx)
```

**交付物**:
```python
# callchain_extractor.py
from dataclasses import dataclass
from typing import List, Optional, Tuple
from ..core.symbol import KernelAwareness


@dataclass(frozen=True)
class ExtractedCallchain:
    """
    提取的调用链结果
    
    Attributes:
        target_symbol: 目标函数名
        kernel_path: 内核态调用路径（从内核对齐函数到系统调用入口）
        syscall_entry: 系统调用入口点（如 __x64_sys_nanosleep）
        user_entry_point: 用户态入口点（如 __GI___nanosleep）
        business_callers: 业务层调用链（从 user_entry_point 往上）
        raw_path: 完整原始路径（用于调试）
        extraction_strategy: 使用的提取策略
    """
    target_symbol: str
    kernel_path: List[str]
    syscall_entry: Optional[str]
    user_entry_point: Optional[str]
    business_callers: List[str]
    raw_path: List[str]
    extraction_strategy: str  # "standard" | "kernel_penetration" | "truncated"


class CallchainExtractor:
    """
    智能调用链提取器
    
    根据目标函数类型，自动选择提取策略：
    1. 用户态函数：标准提取，取固定深度
    2. 内核对齐函数：穿透模式，延伸到用户态业务函数
    """
    
    def __init__(self, 
                 default_max_depth: int = 10,
                 penetration_max_depth: int = 15,
                 min_kernel_layers: int = 3):
        self.default_max_depth = default_max_depth
        self.penetration_max_depth = penetration_max_depth
        self.min_kernel_layers = min_kernel_layers
    
    def extract(self,
                stack: List[str],
                target_idx: int,
                target_symbol: str) -> ExtractedCallchain:
        """
        提取调用链
        
        算法:
        1. 判断目标函数类型（内核/用户态，是否需要穿透）
        2. 如果是普通函数，使用标准提取
        3. 如果是穿透目标，使用穿透模式
        """
        if not stack or target_idx < 0 or target_idx >= len(stack):
            return self._empty_result(target_symbol)
        
        is_kernel = KernelAwareness.is_kernel_function(target_symbol)
        should_pen, reason = KernelAwareness.should_penetrate(target_symbol)
        
        if is_kernel and should_pen:
            return self._extract_with_penetration(
                stack, target_idx, target_symbol
            )
        else:
            return self._extract_standard(
                stack, target_idx, target_symbol
            )
    
    def _extract_standard(self, stack, target_idx, target_symbol) -> ExtractedCallchain:
        """标准提取模式"""
        callers = stack[target_idx+1:target_idx+1+self.default_max_depth]
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=callers,
            raw_path=stack,
            extraction_strategy="standard"
        )
    
    def _extract_with_penetration(self, stack, target_idx, target_symbol) -> ExtractedCallchain:
        """
        内核穿透提取模式
        
        关键逻辑：
        1. 向上遍历，识别内核/用户态边界
        2. 保留内核路径（用于展示）
        3. 提取用户态业务调用链
        """
        kernel_path = []
        business_callers = []
        syscall_entry = None
        user_entry_point = None
        
        found_user = False
        kernel_layer_count = 0
        
        for i in range(target_idx + 1, len(stack)):
            symbol = stack[i]
            is_sym_kernel = KernelAwareness.is_kernel_function(symbol)
            
            if is_sym_kernel and not found_user:
                kernel_path.append(symbol)
                kernel_layer_count += 1
                
                # 识别系统调用入口（启发式：以 sys_ 或 __x64_sys_ 开头）
                if 'sys_' in symbol or symbol.startswith('__x64_'):
                    syscall_entry = symbol
            else:
                if not found_user:
                    # 首次遇到用户态函数
                    found_user = True
                    user_entry_point = symbol
                
                if len(business_callers) < self.default_max_depth:
                    business_callers.append(symbol)
            
            # 终止条件：已找到用户态且收集了足够的业务调用层
            if found_user and len(business_callers) >= self.default_max_depth:
                break
            
            # 安全限制：总遍历深度
            if i - target_idx > self.penetration_max_depth:
                break
        
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=kernel_path,
            syscall_entry=syscall_entry,
            user_entry_point=user_entry_point,
            business_callers=business_callers,
            raw_path=stack,
            extraction_strategy="kernel_penetration" if found_user else "truncated"
        )
    
    def _empty_result(self, target_symbol: str) -> ExtractedCallchain:
        """返回空结果"""
        return ExtractedCallchain(
            target_symbol=target_symbol,
            kernel_path=[],
            syscall_entry=None,
            user_entry_point=None,
            business_callers=[],
            raw_path=[],
            extraction_strategy="empty"
        )
```

**验收标准**:
- [ ] 对 `finish_task_switch` 能提取完整的 `FindInTableWithLock` 调用链
- [ ] 提取结果包含 `kernel_path` 和 `business_callers` 分离
- [ ] 对普通用户态函数保持原有行为
- [ ] 边界情况处理（空栈、目标不存在等）

---

### 开发人员 C - 格式化与输出层 (Owner: TBD)

**任务**: 实现分层调用链格式化

**文件**:
- `scripts/perf_toolkit/core/callchain_formatter.py` (修改/扩展)

**依赖接口** (由 B 提供):
```python
from ..analysis.callchain_extractor import ExtractedCallchain, CallchainExtractor

# 使用示例
extractor = CallchainExtractor()
extracted = extractor.extract(stack, target_idx, target_symbol)
```

**交付物**:
```python
# callchain_formatter.py 扩展

from typing import List
from ..analysis.callchain_extractor import ExtractedCallchain


class LayeredCallchainFormatter:
    """
    分层调用链格式化器
    
    支持两种输出模式：
    1. compact: 紧凑模式（单行，业务调用优先）
    2. detailed: 详细模式（内核/用户态分离展示）
    """
    
    def __init__(self, mode: str = "compact", 
                 max_kernel_display: int = 5):
        self.mode = mode
        self.max_kernel_display = max_kernel_display
    
    def format(self, 
               extracted: ExtractedCallchain,
               weight_percent: float,
               index: int = 1) -> str:
        """
        格式化调用链
        
        Args:
            extracted: 提取的调用链
            weight_percent: 占比百分比
            index: 序号
            
        Returns:
            格式化后的字符串
        """
        if self.mode == "compact":
            return self._format_compact(extracted, weight_percent, index)
        else:
            return self._format_detailed(extracted, weight_percent, index)
    
    def _format_compact(self, extracted, weight_percent, index) -> str:
        """
        紧凑格式
        
        示例:
        #3 [5.50%] FindInTableWithLock <- InsertWithProb <- PushVecFid <- PushModel <- PushModels
        """
        business = extracted.business_callers
        if not business:
            # 没有找到用户态调用者，显示内核路径
            path = extracted.kernel_path[:self.max_kernel_display]
            path_str = " <- ".join(path) if path else "(no callers)"
        else:
            path_str = " <- ".join(business)
        
        return f"#{index} [{weight_percent:.2f}%] {path_str}"
    
    def _format_detailed(self, extracted, weight_percent, index) -> str:
        """
        详细格式（分层展示）
        
        示例:
        #3 [5.50%] FindInTableWithLock <- InsertWithProb <- PushVecFid <- PushModel <- PushModels
           [kernel path] __schedule <- schedule <- do_nanosleep <- ...
           [syscall] __x64_sys_nanosleep
        """
        lines = []
        
        # 主调用链（业务层）
        business = extracted.business_callers
        if business:
            business_str = " <- ".join(business)
            lines.append(f"#{index} [{weight_percent:.2f}%] {business_str}")
        
        # 内核路径（可选展示）
        kernel = extracted.kernel_path
        if kernel:
            kernel_display = kernel[:self.max_kernel_display]
            kernel_str = " <- ".join(kernel_display)
            if len(kernel) > self.max_kernel_display:
                kernel_str += " <- ..."
            lines.append(f"   [kernel] {kernel_str}")
        
        # 系统调用入口
        if extracted.syscall_entry:
            lines.append(f"   [syscall] {extracted.syscall_entry}")
        
        return "\n".join(lines)
    
    def format_collapsed(self, 
                         extractions: List[Tuple[ExtractedCallchain, float]],
                         top_n: int = 5) -> str:
        """
        格式化多个调用链的汇总视图
        
        用于 bottleneck 输出的 CALLCHAINS 部分
        """
        lines = []
        
        # 按权重排序
        sorted_extractions = sorted(extractions, 
                                    key=lambda x: x[1], 
                                    reverse=True)[:top_n]
        
        for i, (extracted, weight) in enumerate(sorted_extractions, 1):
            lines.append(self.format(extracted, weight, i))
        
        return "\n".join(lines)


# 便捷函数，供 facade.py 使用
def format_callchain_for_bottleneck(
    stack: List[str],
    target_idx: int,
    target_symbol: str,
    weight_percent: float,
    index: int = 1
) -> str:
    """
    供 bottleneck 输出使用的便捷格式化函数
    
    这是 facade.py 当前调用路径的替代品
    """
    from ..analysis.callchain_extractor import CallchainExtractor
    
    extractor = CallchainExtractor()
    extracted = extractor.extract(stack, target_idx, target_symbol)
    
    formatter = LayeredCallchainFormatter(mode="compact")
    return formatter.format(extracted, weight_percent, index)
```

**验收标准**:
- [ ] `format_compact` 输出格式与现有 bottleneck 输出兼容
- [ ] 对穿透提取的调用链，能正确显示业务层调用
- [ ] `format_detailed` 清晰展示内核/用户态分层
- [ ] 集成到现有输出流程，无破坏性变更

---

### 开发人员 D - 集成与测试 (Owner: TBD)

**任务**: 集成各模块，替换现有实现，编写测试

**文件**:
- `scripts/perf_toolkit/analysis/facade.py` (修改 - 替换 analyze_callers)
- `scripts/perf_toolkit/cli/commands/analysis/callers.py` (修改 - 支持新格式)
- `tests/unit/test_callchain_extractor.py` (新建)
- `tests/unit/test_kernel_awareness.py` (新建)
- `tests/functional/test_finish_task_switch_fix.py` (新建)

**依赖接口** (由 A, B, C 提供):
```python
from ..core.symbol import KernelAwareness
from ..analysis.callchain_extractor import CallchainExtractor, ExtractedCallchain
from ..core.callchain_formatter import LayeredCallchainFormatter
```

**交付物**:

#### 1. facade.py 修改

```python
# facade.py analyze_callers 方法替换

def analyze_callers(self, samples: List[Sample],
                    target_symbol: str,
                    comm: Optional[str] = None,
                    pid: Optional[int] = None,
                    min_ratio: float = 0.5,
                    top_n: int = 10,
                    use_penetration: bool = True) -> CallersResult:
    """
    调用链溯源分析（支持内核穿透）
    
    Args:
        ...
        use_penetration: 是否启用内核穿透模式
    """
    # 过滤样本（保持原有逻辑）
    filtered_samples = samples
    if comm:
        filtered_samples = [s for s in filtered_samples if s.comm == comm]
    if pid:
        filtered_samples = [s for s in filtered_samples if str(s.pid) == str(pid)]
    
    if not filtered_samples:
        return CallersResult(target=target_symbol, callers=[], ...)
    
    # 初始化提取器
    extractor = CallchainExtractor() if use_penetration else None
    total_weight, _ = self._engine.get_total_core_per_sec(filtered_samples)
    
    # 溯源分析（使用新提取器）
    from collections import defaultdict
    attribution = defaultdict(float)
    target_weight = 0.0
    
    for s in filtered_samples:
        stack = s.stack
        if not stack:
            continue
        
        weight = self._engine.get_sample_weight(s)
        normalized_names = stack.get_normalized_names()
        
        if target_symbol in normalized_names:
            target_weight += weight
            idx = normalized_names.index(target_symbol)
            
            # === 关键改进：使用新提取器 ===
            if extractor:
                extracted = extractor.extract(normalized_names, idx, target_symbol)
                # 优先使用业务调用链，如果没有则使用内核路径
                caller_stack = (extracted.business_callers 
                               if extracted.business_callers 
                               else extracted.kernel_path[:5])
            else:
                # 回退到旧逻辑
                caller_stack = normalized_names[idx+1:idx+6]
            
            if caller_stack:
                attribution[tuple(caller_stack)] += weight
    
    # 构建 callers 列表（保持原有逻辑，但使用新的符号连接方式）
    callers = []
    for stack_tuple, weight_val in attribution.items():
        ratio_total = (weight_val / total_weight * 100) if total_weight > 0 else 0
        if ratio_total >= min_ratio:
            callers.append(CallerAttribution(
                symbol=" <- ".join(stack_tuple),  # 使用 <- 连接
                call_count=int(weight_val * 100),
                call_ratio=ratio_total,
                total_weight=weight_val
            ))
    
    callers.sort(key=lambda x: x.call_count, reverse=True)
    callers = callers[:top_n]
    
    # risks（保持原有逻辑）
    risks = []
    if target_weight < 0.01:
        risks.append(RiskInfo(...))
    
    return CallersResult(
        target=target_symbol,
        callers=callers,
        total_weight=target_weight,
        risks=risks
    )
```

#### 2. 集成测试

```python
# tests/functional/test_finish_task_switch_fix.py

"""
测试 finish_task_switch 调用链截断问题修复

验证点：
1. finish_task_switch 的调用链能正确显示 FindInTableWithLock
2. 内核穿透模式正常工作
3. 不影响普通函数的调用链提取
"""

import unittest
from pathlib import Path

# 加载测试数据
DATA_FILE = Path(__file__).parent.parent / "data/new_format/ps.data"


class TestFinishTaskSwitchFix(unittest.TestCase):
    """测试 finish_task_switch 调用链修复"""
    
    @classmethod
    def setUpClass(cls):
        """加载测试数据"""
        from scripts.perf_toolkit.core.engine import PerfExpertEngine
        cls.engine = PerfExpertEngine()
        cls.samples = cls.engine.load_samples(str(DATA_FILE))
    
    def test_findintablewithlock_visible(self):
        """
        验证 FindInTableWithLock 在 finish_task_switch 调用链中可见
        """
        from scripts.perf_toolkit.analysis.facade import AnalysisFacade
        
        facade = AnalysisFacade(self.engine)
        result = facade.analyze_callers(
            self.samples,
            target_symbol="finish_task_switch",
            comm="parameter_serve",
            use_penetration=True
        )
        
        # 检查是否有调用链包含 FindInTableWithLock
        caller_symbols = [c.symbol for c in result.callers]
        found = any("FindInTableWithLock" in s for s in caller_symbols)
        
        self.assertTrue(
            found,
            f"FindInTableWithLock 应该在 finish_task_switch 的调用链中可见，"
            f"但实际调用链为: {caller_symbols}"
        )
    
    def test_kernel_path_preservation(self):
        """
        验证内核路径被正确保留
        """
        from scripts.perf_toolkit.analysis.callchain_extractor import CallchainExtractor
        
        # 构造测试栈
        test_stack = [
            "finish_task_switch",
            "__schedule",
            "schedule", 
            "do_nanosleep",
            "hrtimer_nanosleep",
            "__x64_sys_nanosleep",
            "do_syscall_64",
            "entry_SYSCALL_64_after_hwframe",
            "__GI___nanosleep",
            "FindInTableWithLock",
            "InsertWithProb",
        ]
        
        extractor = CallchainExtractor()
        extracted = extractor.extract(test_stack, 0, "finish_task_switch")
        
        # 验证内核路径包含关键函数
        self.assertIn("__schedule", extracted.kernel_path)
        self.assertIn("do_nanosleep", extracted.kernel_path)
        
        # 验证用户态入口点
        self.assertEqual(extracted.user_entry_point, "__GI___nanosleep")
        
        # 验证业务调用链
        self.assertIn("FindInTableWithLock", extracted.business_callers)
    
    def test_backward_compatibility(self):
        """
        验证关闭穿透模式时行为与之前一致
        """
        from scripts.perf_toolkit.analysis.facade import AnalysisFacade
        
        facade = AnalysisFacade(self.engine)
        
        # 使用穿透模式
        result_with = facade.analyze_callers(
            self.samples, target_symbol="AdamOptimizer::Optimize",
            use_penetration=True
        )
        
        # 不使用穿透模式
        result_without = facade.analyze_callers(
            self.samples, target_symbol="AdamOptimizer::Optimize",
            use_penetration=False
        )
        
        # 对于用户态函数，两者结果应该一致
        self.assertEqual(
            len(result_with.callers),
            len(result_without.callers)
        )
```

#### 3. 回归测试脚本

```bash
#!/bin/bash
# tests/run_regression.sh

echo "=== 运行调用链截断修复回归测试 ==="

# 1. 单元测试
echo "[1/4] 运行单元测试..."
python3 -m pytest tests/unit/test_kernel_awareness.py -v
python3 -m pytest tests/unit/test_callchain_extractor.py -v

# 2. 功能测试
echo "[2/4] 运行功能测试..."
python3 -m pytest tests/functional/test_finish_task_switch_fix.py -v

# 3. 验证数据输出
echo "[3/4] 验证实际数据输出..."
python3 scripts/shecr.py get-callers \
    --data tests/data/new_format/ps.data \
    --symbol "finish_task_switch" \
    --comm "parameter_serve" \
    --output-format layered

# 4. 对比修复前后
echo "[4/4] 对比 bottleneck 输出..."
python3 scripts/shecr.py bottleneck-trace \
    --data tests/data/new_format/ps.data \
    --target parameter_serve > /tmp/bottleneck_new.txt

echo "检查 FindInTableWithLock 是否出现:"
grep -i "findintablewithlock" /tmp/bottleneck_new.txt && echo "✓ 修复成功" || echo "✗ 未找到"
```

**验收标准**:
- [ ] `facade.analyze_callers` 成功集成新提取器
- [ ] `FindInTableWithLock` 在 finish_task_switch 调用链中可见
- [ ] 所有现有测试通过（向后兼容）
- [ ] 新增测试覆盖率达 80%+
- [ ] 集成测试脚本全部通过

---

## 协作流程

### 开发顺序

```
Day 1: 
  - A 完成 KernelAwareness 基础框架
  - B 完成 CallchainExtractor 框架（使用 mock 的 KernelAwareness）
  
Day 2:
  - A 完成 KernelAwareness 实现 + 单元测试
  - B 完成 CallchainExtractor 实现 + 单元测试
  - C 完成 LayeredCallchainFormatter 框架
  
Day 3:
  - A, B, C 接口联调
  - C 完成 Formatter 实现
  
Day 4:
  - D 完成 facade.py 集成
  - D 完成集成测试
  
Day 5:
  - 联调测试
  - 修复问题
  - 代码审查
```

### 接口契约

**A -> B 接口**:
```python
# A 必须提供的稳定接口
class KernelAwareness:
    @staticmethod
    def is_kernel_function(symbol_name: str, module: Optional[str] = None) -> bool
    
    @staticmethod  
    def should_penetrate(symbol_name: str) -> Tuple[bool, str]
    
    @staticmethod
    def find_user_entry_point(stack: List[str], start_idx: int) -> Optional[int]
```

**B -> C 接口**:
```python
# B 必须提供的稳定接口
@dataclass
class ExtractedCallchain:
    target_symbol: str
    kernel_path: List[str]
    syscall_entry: Optional[str]
    user_entry_point: Optional[str]
    business_callers: List[str]
    raw_path: List[str]
    extraction_strategy: str

class CallchainExtractor:
    def extract(self, stack: List[str], target_idx: int, target_symbol: str) -> ExtractedCallchain
```

**C -> D 接口**:
```python
# C 必须提供的稳定接口
class LayeredCallchainFormatter:
    def format(self, extracted: ExtractedCallchain, weight_percent: float, index: int = 1) -> str
    def format_collapsed(self, extractions: List[Tuple[ExtractedCallchain, float]], top_n: int = 5) -> str
```

### 代码审查清单

- [ ] 接口是否符合契约定义
- [ ] 是否处理了边界情况（空栈、越界等）
- [ ] 单元测试是否覆盖主要分支
- [ ] 类型注解是否完整
- [ ] 文档字符串是否清晰

---

## 风险与应对

| 风险 | 概率 | 影响 | 应对策略 |
|-----|-----|-----|---------|
| 接口变更导致联调困难 | 中 | 高 | Day 2 结束前冻结接口，使用 mock 先行开发 |
| 性能下降（遍历深度增加） | 低 | 中 | 添加性能测试基线，确保不劣化 10% |
| 向后兼容性问题 | 中 | 高 | 保留旧代码路径，通过参数开关控制 |
| 测试数据不完整 | 低 | 低 | 构造模拟数据，覆盖边界场景 |

---

## 完成标准

1. **功能完成**: `finish_task_switch` 调用链显示 `FindInTableWithLock`
2. **测试通过**: 所有新旧测试通过，覆盖率达 80%
3. **文档更新**: SKILL.md 和 AGENTS.md 相关文档更新
4. **代码审查**: 至少 1 人审查通过
5. **无回归**: 现有 bottleneck 输出格式无破坏性变更
