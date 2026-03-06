# Callchain 截断问题修复计划

## 问题概述

`finish_task_switch` 等内核函数的调用链被过早截断，无法显示关键的业务调用源（如 `FindInTableWithLock`）。

**根因**: `facade.py:247` 硬编码 `caller_stack = normalized_names[idx+1:idx+6]`，只取5层，导致跨内核/用户态边界的调用链被截断。

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
    
    PENETRATION_TARGETS: Set[str] = {...}  # 需要穿透分析的内核函数白名单
    
    @staticmethod
    def is_kernel_function(symbol_name: str) -> bool:
        """判断是否为内核函数"""
    
    @staticmethod
    def should_penetrate(symbol_name: str) -> bool:
        """判断是否需要穿透到用户态"""


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
    
    def __init__(self, max_depth: int = 10, kernel_penetration: bool = True)
    
    def extract(self, stack: List[str], target_idx: int, target_symbol: str) 
                -> ExtractedCallchain


# === 模块C: callchain_formatter.py 修改 ===
class LayeredCallchainFormatter:
    """分层调用链格式化器"""
    
    def format_kernel_user_separated(self, extracted: ExtractedCallchain, 
                                     weight: float) -> str
```

---

## 任务拆分

### 开发人员 A - 内核感知与策略层

**任务**: 实现内核函数识别和穿透策略

**文件**:
- `scripts/perf_toolkit/core/symbol.py` (修改)
- `config/defaults.py` (修改 - 添加白名单配置)

**关键实现**:
```python
class KernelAwareness:
    PENETRATION_TARGETS: Set[str] = set()  # 从配置加载
    
    @classmethod
    def load_config(cls, config: Dict):
        targets = config.get('kernel_penetration_targets', [])
        cls.PENETRATION_TARGETS = set(targets)
    
    @staticmethod
    def is_kernel_function(symbol_name: str) -> bool:
        # 规则: 名称以 _[k] 结尾 / module 包含 kernel.kallsyms
        pass
    
    @staticmethod
    def should_penetrate(symbol_name: str) -> Tuple[bool, str]:
        # 返回 (是否穿透, 原因)
        pass
    
    @staticmethod
    def find_user_entry_point(stack: List[str], start_idx: int) -> Optional[int]:
        # 从内核对齐函数出发，找到第一个用户态函数的位置
        pass
```

**配置添加** (config/defaults.py):
```python
KERNEL_PENETRATION_TARGETS = [
    'finish_task_switch', '__schedule', 'schedule', 'switch_mm_irqs_off',
    'native_safe_halt', 'do_nanosleep', 'hrtimer_nanosleep',
]

CALLCHAIN_EXTRACTION = {
    'default_max_depth': 10,
    'kernel_penetration_max_depth': 15,
    'min_kernel_layers': 3,
}
```

**验收标准**:
- [ ] `KernelAwareness.should_penetrate("finish_task_switch")` 返回 (True, "in_whitelist")
- [ ] `find_user_entry_point` 能正确识别 `__GI___nanosleep` 位置
- [ ] 单元测试覆盖所有场景

---

### 开发人员 B - 调用链提取核心

**任务**: 实现智能调用链提取器

**文件**:
- `scripts/perf_toolkit/analysis/callchain_extractor.py` (新建)

**核心算法**:
```python
class CallchainExtractor:
    def extract(self, stack, target_idx, target_symbol) -> ExtractedCallchain:
        is_kernel = KernelAwareness.is_kernel_function(target_symbol)
        should_pen, reason = KernelAwareness.should_penetrate(target_symbol)
        
        if is_kernel and should_pen:
            return self._extract_with_penetration(stack, target_idx, target_symbol)
        else:
            return self._extract_standard(stack, target_idx, target_symbol)
    
    def _extract_with_penetration(self, stack, target_idx, target_symbol):
        """内核穿透提取模式"""
        # 1. 向上遍历，识别内核/用户态边界
        # 2. 保留内核路径（用于展示）
        # 3. 提取用户态业务调用链
```

**验收标准**:
- [ ] 对 `finish_task_switch` 能提取完整的 `FindInTableWithLock` 调用链
- [ ] 提取结果包含 `kernel_path` 和 `business_callers` 分离
- [ ] 对普通用户态函数保持原有行为
- [ ] 边界情况处理（空栈、目标不存在等）

---

### 开发人员 C - 格式化与输出层

**任务**: 实现分层调用链格式化

**文件**:
- `scripts/perf_toolkit/core/callchain_formatter.py` (修改/扩展)

**核心功能**:
```python
class LayeredCallchainFormatter:
    """支持两种输出模式：
    1. compact: 紧凑模式（单行，业务调用优先）
    2. detailed: 详细模式（内核/用户态分离展示）
    """
    
    def format(self, extracted: ExtractedCallchain, 
               weight_percent: float, index: int = 1) -> str
    
    def format_collapsed(self, extractions: List[Tuple[ExtractedCallchain, float]], 
                         top_n: int = 5) -> str
```

**验收标准**:
- [ ] `format_compact` 输出格式与现有 bottleneck 输出兼容
- [ ] 对穿透提取的调用链，能正确显示业务层调用
- [ ] `format_detailed` 清晰展示内核/用户态分层
- [ ] 集成到现有输出流程，无破坏性变更

---

### 开发人员 D - 集成与测试

**任务**: 集成各模块，替换现有实现，编写测试

**文件**:
- `scripts/perf_toolkit/analysis/facade.py` (修改)
- `tests/unit/test_callchain_extractor.py` (新建)
- `tests/unit/test_kernel_awareness.py` (新建)

**facade.py 关键修改**:
```python
def analyze_callers(self, samples, target_symbol, ..., use_penetration: bool = True):
    # 初始化提取器
    extractor = CallchainExtractor() if use_penetration else None
    
    for s in filtered_samples:
        if extractor:
            extracted = extractor.extract(normalized_names, idx, target_symbol)
            caller_stack = (extracted.business_callers 
                           if extracted.business_callers 
                           else extracted.kernel_path[:5])
        else:
            # 回退到旧逻辑
            caller_stack = normalized_names[idx+1:idx+6]
```

**验收标准**:
- [ ] `facade.analyze_callers` 成功集成新提取器
- [ ] `FindInTableWithLock` 在 finish_task_switch 调用链中可见
- [ ] 所有现有测试通过（向后兼容）
- [ ] 新增测试覆盖率达 80%+

---

## 协作流程

### 开发顺序

```
Day 1: A 完成 KernelAwareness 框架；B 完成 CallchainExtractor 框架
Day 2: A/B 各自完成实现 + 单元测试；C 完成 Formatter 框架
Day 3: A/B/C 接口联调
Day 4: D 完成 facade.py 集成 + 集成测试
Day 5: 联调测试 + 修复问题
```

### 接口契约

**A -> B 接口**:
```python
class KernelAwareness:
    @staticmethod
    def is_kernel_function(symbol_name: str) -> bool
    @staticmethod  
    def should_penetrate(symbol_name: str) -> Tuple[bool, str]
    @staticmethod
    def find_user_entry_point(stack: List[str], start_idx: int) -> Optional[int]
```

**B -> C 接口**:
```python
@dataclass
class ExtractedCallchain:
    target_symbol: str
    kernel_path: List[str]
    user_entry_point: Optional[str]
    business_callers: List[str]

class CallchainExtractor:
    def extract(self, stack: List[str], target_idx: int, target_symbol: str) 
                -> ExtractedCallchain
```

**C -> D 接口**:
```python
class LayeredCallchainFormatter:
    def format(self, extracted: ExtractedCallchain, 
               weight_percent: float, index: int = 1) -> str
```

---

## 完成标准

1. **功能完成**: `finish_task_switch` 调用链显示 `FindInTableWithLock`
2. **测试通过**: 所有新旧测试通过，覆盖率达 80%
3. **文档更新**: SKILL.md 和 AGENTS.md 相关文档更新
4. **代码审查**: 至少 1 人审查通过
5. **无回归**: 现有 bottleneck 输出格式无破坏性变更

---

## 风险与应对

| 风险 | 概率 | 影响 | 应对策略 |
|-----|-----|-----|---------|
| 接口变更导致联调困难 | 中 | 高 | Day 2 结束前冻结接口，使用 mock 先行开发 |
| 向后兼容性问题 | 中 | 高 | 保留旧代码路径，通过参数开关控制 |
| 性能下降（遍历深度增加） | 低 | 中 | 添加性能测试基线，确保不劣化 10% |
