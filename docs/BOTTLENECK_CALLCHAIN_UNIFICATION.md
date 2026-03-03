# CallChain 输出风格统一方案

> 版本: 1.0  
> 日期: 2026-03-04  
> 目标: find-callers / cluster-paths / bottleneck-trace 使用统一的 callchain 输出函数

---

## 当前问题

### 1. 三种不同的 callchain 输出风格

| 命令 | 数据结构 | 当前渲染格式 | 代码位置 |
|------|----------|--------------|----------|
| **find-callers** | `AttributionItem.caller_stack: List[str]` | `#1 [ratio%] func1 <- func2 <- func3` | `text_output_adapter.py:130-133` |
| **cluster-paths** | `PathClusterItem.path_signature: str` | `#1 ratio% cpu% path -> signature` | `text_output_adapter.py:122-128` |
| **bottleneck-trace** | `CallPathCluster.path: List[str], hotspot: str` | `` `comm` -> `func1` -> **[HOTSPOT]** `` | `text_output_adapter.py:452-465` |

### 2. 问题分析

```python
# 问题 1: 重复的实现
# text_output_adapter.py 中有 3 个不同的格式化函数

def _format_attribution_line(self, item, index):
    # find-callers 使用
    stack = self._format_field_value(item, "caller_stack")  # " <- " 连接
    return f"#{index} [{ratio}] {stack}"

def _format_path_cluster_line(self, item, index, config):
    # cluster-paths 使用
    path = _get_attr(item, 'path_signature', 'N/A')  # 直接字符串
    return f"{prefix} {ratio_pct:.2f}% {cpu_util:.2f}% {path}"

def _format_call_path(self, path: List[str], hotspot: str) -> str:
    # bottleneck-trace 使用
    # 自定义复杂格式: `comm` -> `func1` -> **[HOTSPOT]**
```

### 3. 不一致点

| 维度 | find-callers | cluster-paths | bottleneck-trace |
|------|--------------|---------------|------------------|
| 分隔符 | ` <- ` (反向) | 直接字符串 | ` -> ` (正向) |
| 代码标记 | 无 | 无 | `` ` `` 包裹 |
| 热点标记 | 无 | 无 | `**[HOTSPOT]**` |
| 方向 | Bottom-Up | 混合 | Top-Down |

---

## 统一方案

### 设计原则

1. **单一函数**: 所有 callchain 输出使用同一个 `format_callchain()` 函数
2. **风格可配置**: 通过参数控制分隔符、标记、方向
3. **向后兼容**: 保留现有输出的视觉风格，只统一实现

### 统一输出格式标准

```python
# config/defaults.py - 新增 CallChainFormat 配置

@dataclass(frozen=True)
class CallChainFormat:
    """CallChain 输出格式配置"""
    
    # 分隔符
    SEPARATOR_TOP_DOWN = " -> "      # 正向: 入口 -> 热点
    SEPARATOR_BOTTOM_UP = " <- "     # 反向: 热点 <- 入口
    
    # 标记
    CODE_MARKER = "`"                 # 代码标记: `function`
    HOTSPOT_PREFIX = "**["           # 热点前缀
    HOTSPOT_SUFFIX = "]**"           # 热点后缀
    
    # 默认格式模板
    TEMPLATE_SIMPLE = "{path}"                                    # 纯路径
    TEMPLATE_WITH_RATIO = "[{ratio}] {path}"                     # 带比例
    TEMPLATE_WITH_HOTSPOT = "{path} -> {hotspot_marker}"         # 带热点
    
    # 样式预设
    STYLE_DEFAULT = "default"         # 标准格式
    STYLE_MARKDOWN = "markdown"       # Markdown 格式 (带 ` 标记)
    STYLE_PLAIN = "plain"             # 纯文本 (无标记)
```

### 统一函数设计

```python
# perf_toolkit/core/callchain_formatter.py

from typing import List, Optional
from config.defaults import CallChainFormat, StringConstants

class CallChainFormatter:
    """统一的 CallChain 格式化器"""
    
    @staticmethod
    def format(
        path: List[str],
        hotspot: Optional[str] = None,
        direction: str = "top_down",  # "top_down" | "bottom_up"
        style: str = "markdown",      # "markdown" | "plain"
        ratio: Optional[float] = None,
        use_hotspot_marker: bool = True
    ) -> str:
        """
        格式化调用链
        
        Args:
            path: 调用路径 (函数名列表)
            hotspot: 热点函数名 (可选)
            direction: 方向 "top_down" (入口->热点) 或 "bottom_up" (热点<-入口)
            style: 样式 "markdown" (带`标记) 或 "plain" (纯文本)
            ratio: 占比百分比 (可选)
            use_hotspot_marker: 是否使用 **[hotspot]** 标记
            
        Returns:
            格式化后的字符串
        """
        if not path:
            if hotspot:
                return CallChainFormatter._format_hotspot(hotspot, style, use_hotspot_marker)
            return StringConstants.NA
        
        # 选择分隔符
        separator = (CallChainFormat.SEPARATOR_TOP_DOWN 
                    if direction == "top_down" 
                    else CallChainFormat.SEPARATOR_BOTTOM_UP)
        
        # 格式化路径节点
        if style == "markdown":
            nodes = [f"{CallChainFormat.CODE_MARKER}{n}{CallChainFormat.CODE_MARKER}" 
                    for n in path]
        else:
            nodes = list(path)
        
        # 添加热点
        if hotspot:
            if use_hotspot_marker:
                hotspot_str = CallChainFormatter._format_hotspot(hotspot, style, True)
            else:
                hotspot_str = (f"{CallChainFormat.CODE_MARKER}{hotspot}{CallChainFormat.CODE_MARKER}"
                             if style == "markdown" else hotspot)
            
            # 热点是否已在路径中
            if path[-1] != hotspot:
                if direction == "top_down":
                    nodes.append(hotspot_str)
                else:
                    nodes.insert(0, hotspot_str)
        
        # 连接路径
        path_str = separator.join(nodes)
        
        # 添加比例
        if ratio is not None:
            return CallChainFormat.TEMPLATE_WITH_RATIO.format(
                ratio=f"{ratio:.2f}%",
                path=path_str
            )
        
        return path_str
    
    @staticmethod
    def _format_hotspot(hotspot: str, style: str, use_marker: bool) -> str:
        """格式化热点标记"""
        if not use_marker:
            if style == "markdown":
                return f"{CallChainFormat.CODE_MARKER}{hotspot}{CallChainFormat.CODE_MARKER}"
            return hotspot
        
        return (f"{CallChainFormat.HOTSPOT_PREFIX}{hotspot}{CallChainFormat.HOTSPOT_SUFFIX}")
    
    @staticmethod
    def parse(path_str: str, separator: Optional[str] = None) -> List[str]:
        """
        解析调用链字符串为列表
        
        Args:
            path_str: 调用链字符串
            separator: 分隔符 (默认自动检测)
            
        Returns:
            函数名列表
        """
        if not path_str or path_str == StringConstants.NA:
            return []
        
        # 自动检测分隔符
        if separator is None:
            if CallChainFormat.SEPARATOR_TOP_DOWN in path_str:
                separator = CallChainFormat.SEPARATOR_TOP_DOWN
            elif CallChainFormat.SEPARATOR_BOTTOM_UP in path_str:
                separator = CallChainFormat.SEPARATOR_BOTTOM_UP
            else:
                # 尝试直接分割
                return [path_str]
        
        parts = path_str.split(separator)
        
        # 去除代码标记
        cleaned = []
        for part in parts:
            part = part.strip()
            if part.startswith(CallChainFormat.CODE_MARKER) and part.endswith(CallChainFormat.CODE_MARKER):
                part = part[1:-1]
            # 去除热点标记 **[...]**
            if part.startswith(CallChainFormat.HOTSPOT_PREFIX) and part.endswith(CallChainFormat.HOTSPOT_SUFFIX):
                part = part[len(CallChainFormat.HOTSPOT_PREFIX):-len(CallChainFormat.HOTSPOT_SUFFIX)]
            cleaned.append(part)
        
        return cleaned


# 便捷函数
def format_callchain(
    path: List[str],
    hotspot: Optional[str] = None,
    direction: str = "top_down",
    style: str = "markdown",
    ratio: Optional[float] = None
) -> str:
    """便捷的 callchain 格式化函数"""
    return CallChainFormatter.format(path, hotspot, direction, style, ratio)
```

---

## 重构代码

### 1. 重构前（3个独立函数）

```python
# text_output_adapter.py - 当前实现

class SimpleListTemplate(Template):
    def _format_attribution_line(self, item: Any, index: int) -> str:
        """find-callers 使用"""
        ratio = self._format_field_value(item, "ratio_of_target_pct")
        stack = self._format_field_value(item, "caller_stack")  # 使用 _format_field_value
        return f"#{index} [{ratio}] {stack}"

    def _format_path_cluster_line(self, item: Any, index: int, config: Any) -> str:
        """cluster-paths 使用"""
        weight, total = _get_attr(item, 'weight', 0), _get_attr(item, 'total_weight', 1)
        duration, path = _get_attr(item, 'duration', 1), _get_attr(item, 'path_signature', 'N/A')
        ratio_pct = (weight / total * 100) if total > 0 else 0
        cpu_util = (weight / duration * 100) if duration > 0 else 0
        prefix = config.index_format.format(index=index) if config.index_format else f"#{index}"
        return f"{prefix} {ratio_pct:.2f}% {cpu_util:.2f}% {path}"

class CustomTemplate(Template):
    def _format_call_path(self, path: List[str], hotspot: str) -> str:
        """bottleneck-trace 使用"""
        if not path:
            return f"**[{hotspot}]**"
        parts = []
        for i, node in enumerate(path):
            if i == 0:
                parts.append(f"`{node}`")
            else:
                parts.append(f"-> `{node}`")
        parts.append(f"-> **[{hotspot}]**")
        return " ".join(parts)
```

### 2. 重构后（统一使用 CallChainFormatter）

```python
# text_output_adapter.py - 重构后

from perf_toolkit.core.callchain_formatter import CallChainFormatter, format_callchain

class SimpleListTemplate(Template):
    def _format_attribution_line(self, item: Any, index: int) -> str:
        """find-callers 使用统一格式化器"""
        ratio_str = self._format_field_value(item, "ratio_of_target_pct")
        stack = _get_attr(item, "caller_stack", [])
        
        # 解析比例
        try:
            ratio = float(ratio_str.rstrip('%'))
        except (ValueError, AttributeError):
            ratio = 0.0
        
        # 使用统一格式化器 (bottom_up 风格, plain 样式)
        path_str = CallChainFormatter.format(
            path=stack,
            direction="bottom_up",
            style="plain",
            ratio=ratio
        )
        return f"#{index} {path_str}"

    def _format_path_cluster_line(self, item: Any, index: int, config: Any) -> str:
        """cluster-paths 使用统一格式化器"""
        weight = _get_attr(item, 'weight', 0)
        total = _get_attr(item, 'total_weight', 1)
        duration = _get_attr(item, 'duration', 1)
        path_sig = _get_attr(item, 'path_signature', '')
        
        ratio_pct = (weight / total * 100) if total > 0 else 0
        cpu_util = (weight / duration * 100) if duration > 0 else 0
        
        # path_signature 是字符串, 需要解析为列表
        path = CallChainFormatter.parse(path_sig)
        
        # 使用统一格式化器 (top_down 风格, plain 样式, 不带热点标记)
        path_str = CallChainFormatter.format(
            path=path,
            direction="top_down",
            style="plain"
        )
        
        prefix = config.index_format.format(index=index) if config.index_format else f"#{index}"
        return f"{prefix} {ratio_pct:.2f}% {cpu_util:.2f}% {path_str}"

class CustomTemplate(Template):
    def _format_call_path(self, path: List[str], hotspot: str) -> str:
        """bottleneck-trace 使用统一格式化器"""
        return CallChainFormatter.format(
            path=path,
            hotspot=hotspot,
            direction="top_down",
            style="markdown",
            use_hotspot_marker=True
        )
```

---

## 数据结构统一

### 当前数据结构

```python
# find-callers
@dataclass
class AttributionItem:
    caller_stack: List[str]          # 调用栈 (bottom-up)
    ratio_of_target_pct: str
    cpu_util: str

# cluster-paths  
@dataclass
class PathClusterItem:
    cluster_id: str
    path_signature: str              # 字符串形式
    weight: float
    total_weight: float
    duration: float

# bottleneck-trace
@dataclass
class CallPathCluster:
    cluster_id: str
    comm: str
    weight: float
    path: List[str]                  # 调用路径
    hotspot: str
    characteristic: str
```

### 建议: 添加统一的 path 字段

```python
# output_models.py - 统一添加 path 字段

@dataclass
class AttributionItem:
    caller_stack: List[str]
    ratio_of_target_pct: str
    cpu_util: str
    # 新增: 统一 path 字段
    _path: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self._path and self.caller_stack:
            self._path = list(self.caller_stack)

@dataclass
class PathClusterItem:
    cluster_id: str
    path_signature: str
    weight: float
    total_weight: float
    duration: float
    # 新增: 统一 path 字段
    _path: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self._path and self.path_signature:
            # 解析 path_signature
            from perf_toolkit.core.callchain_formatter import CallChainFormatter
            self._path = CallChainFormatter.parse(self.path_signature)
```

---

## 实施步骤

### Phase 1: 创建统一格式化器

1. 创建 `config/defaults.py` 添加 `CallChainFormat`
2. 创建 `perf_toolkit/core/callchain_formatter.py`
3. 添加单元测试

### Phase 2: 重构 text_output_adapter

1. 导入 `CallChainFormatter`
2. 替换 `_format_attribution_line`
3. 替换 `_format_path_cluster_line`
4. 替换 `_format_call_path`

### Phase 3: 统一数据结构

1. 在 `output_models.py` 中添加 `_path` 字段
2. 更新相关构造代码

### Phase 4: 验证

1. 对比重构前后输出是否一致
2. 确保所有测试通过

---

## 验证检查清单

- [ ] `CallChainFormatter.format()` 能处理所有三种场景
- [ ] `CallChainFormatter.parse()` 能正确解析现有格式
- [ ] find-callers 输出风格保持不变
- [ ] cluster-paths 输出风格保持不变
- [ ] bottleneck-trace 输出风格保持不变
- [ ] 单元测试覆盖率 > 90%

---

## 示例对比

### find-callers

```python
# 重构前
#1 [15.50%] vfs_read <- entry_SYSCALL_64_after_hwframe

# 重构后 (风格一致)
#1 [15.50%] vfs_read <- entry_SYSCALL_64_after_hwframe
```

### cluster-paths

```python
# 重构前
#1 45.20% 12.30% main -> worker -> process

# 重构后 (风格一致)
#1 45.20% 12.30% main -> worker -> process
```

### bottleneck-trace

```python
# 重构前
`app_B` -> `handle_request` -> `write_log` -> **[__cfs_rq_runtime_get]**

# 重构后 (风格一致)
`app_B` -> `handle_request` -> `write_log` -> **[__cfs_rq_runtime_get]**
```

---

## 相关文件

- `config/defaults.py` - 添加 CallChainFormat
- `perf_toolkit/core/callchain_formatter.py` - 新建统一格式化器
- `perf_toolkit/core/text_output_adapter.py` - 重构现有代码
- `perf_toolkit/core/output_models.py` - 可选: 统一 _path 字段
