# 双向调用链视图设计 (Bidirectional CallChain View)

> **方向选择**: 垂直布局（Bottom-Up 在上，Top-Down 在下）
> 
> **理由**: 宽度充足，连接线简单，分叉点自然展示

---

## 1. 设计目标

将 `cluster-paths` (Top-Down) 和 `find-callers` (Bottom-Up) 的输出整合为单一视图，帮助用户：

1. **快速识别共同路径** - 两边都存在的节点即汇聚点
2. **定位分叉点** - 路径分歧的位置一目了然  
3. **验证数据一致性** - 相同 weight 的节点可以双向验证

---

## 2. 布局设计

### 2.1 垂直方向布局

```
┌──────────────────────────────────────────────────────┐
│                    TOP-DOWN                          │
│                (Root → Hotspot)                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│       (root)                                         │
│         │                                            │
│         ▼                                            │
│   tcp_get_idx                                        │
│         │                                            │
│         ▼                                            │
│   tcp_seq_start  ════════▶  45.9%                   │
│         │                                            │
│         ├──────────────┐                             │
│         │      ....... │                             │
│         ▼      .     . ▼                             │
│      seq_read  . FORK. seq_read  ════════▶  85.2%   │
│         │      .     . │                             │
│         ▼      ....... ▼                             │
│   proc_reg_read        proc_reg_read                 │
│         │                    │                       │
│         ▼                    ▼                       │
│      vfs_read             vfs_read                   │
│         │                    │                       │
│         └────────┬───────────┘                       │
│                  ▼                                   │
│      established_get_first  ════════▶  85.2%        │
│                  │                                   │
│                  ▼                                   │
│              HOTSPOT                                 │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ════════════════════════════════════════════════   │
│              CONVERGENCE MIRROR                      │
│         （虚线连接未聚合的链路）                       │
│  ────────────────────────────────────────────────   │
├──────────────────────────────────────────────────────┤
│                                                      │
│   established_get_first  ◀═══════  85.2%            │
│            │                                         │
│            ▼                                         │
│        vfs_read        ◀════════  85.2%            │
│            │                                         │
│            ▼                                         │
│     proc_reg_read      ◀════════  85.2%            │
│            │                                         │
│            ▼                                         │
│       seq_read         ◀════════  85.2%            │
│            │                                         │
│       ┌────┴────┐                                    │
│       │   FORK  │                                    │
│       ▼         ▼                                    │
│   tcp_seq_   tcp_seq_                                │
│    start      next                                   │
│       │         │                                    │
│       ▼         ▼                                    │
│  tcp_get_idx   ...                                   │
│       │                                              │
│       ▼                                              │
│   (root)                                             │
│                                                      │
├──────────────────────────────────────────────────────┤
│                    BOTTOM-UP                         │
│                (Hotspot → Root)                      │
└──────────────────────────────────────────────────────┘
```

### 2.2 连接线语义

| 符号 | 含义 | 使用场景 |
|------|------|----------|
| `═══════▶` | 权重流向 | 从 parent 到 child，标注 weight |
| `◀═══════` | 权重溯源 | 从 child 到 parent，标注 weight |
| `│` `├` `└` | 树形结构 | 普通的调用关系 |
| `.......` | 虚线引导 | 跨层级的语义关联（不精确对应） |
| `FORK` | 分叉标记 | 一个节点有多个子节点的位置 |

---

## 3. 数据结构

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

class NodeSource(Enum):
    """节点来源"""
    BOTTOM_UP_ONLY = "bu_only"      # 仅 Bottom-Up 有
    TOP_DOWN_ONLY = "td_only"       # 仅 Top-Down 有
    BOTH = "both"                   # 两边都有（汇聚点）

@dataclass
class BidirectionalNode:
    """双向视图节点
    
    注意：这是一个视图层节点，不是数据层节点。
    它只负责展示，不负责存储完整的调用链数据。
    """
    symbol: str
    weight: float = 0.0
    source: NodeSource = NodeSource.BOTH
    
    # 展示层级（用于对齐）
    level: int = 0
    
    # 连接标记
    is_convergence: bool = False    # 汇聚点（两边都有）
    is_fork_point: bool = False     # 分叉点（多个子节点）
    is_mirror_anchor: bool = False  # 镜像锚点（用于虚线连接）

@dataclass
class BidirectionalView:
    """双向视图容器"""
    # 热点信息
    hotspot: str
    total_weight: float
    
    # Bottom-Up 侧（从上往下：hotspot → root）
    bu_nodes: List[BidirectionalNode] = field(default_factory=list)
    
    # Top-Down 侧（从上往下：root → hotspot）
    td_nodes: List[BidirectionalNode] = field(default_factory=list)
    
    # 镜像连接（虚线连接的对齐点）
    mirror_pairs: List[tuple] = field(default_factory=list)
    
    # 关键发现
    convergence_path: List[str] = field(default_factory=list)
    fork_points: List[str] = field(default_factory=list)
```

---

## 4. 渲染算法

### 4.1 核心逻辑

```python
def render_bidirectional_view(view: BidirectionalView) -> str:
    """渲染双向视图为文本格式"""
    lines = [
        "## [BIDIRECTIONAL_VIEW] 双向调用链汇聚",
        "",
        "```",
        "┌──────────────────────────────────────────────┐",
        "│              BOTTOM-UP                       │",
        "│         (Hotspot → Root)                     │",
        "├──────────────────────────────────────────────┤",
    ]
    
    # 1. 渲染 Bottom-Up 侧（从上到下）
    lines.extend(_render_bu_side(view.bu_nodes))
    
    # 2. 渲染中间分隔带
    lines.extend([
        "├──────────────────────────────────────────────┤",
        "│  ════════════════════════════════════════   │",
        "│         CONVERGENCE MIRROR                   │",
        "│  ─────────────────────────────────────────  │",
        "├──────────────────────────────────────────────┤",
    ])
    
    # 3. 渲染 Top-Down 侧（从上到下）
    lines.extend(_render_td_side(view.td_nodes, view.mirror_pairs))
    
    lines.extend([
        "├──────────────────────────────────────────────┤",
        "│              TOP-DOWN                        │",
        "│         (Root → Hotspot)                     │",
        "└──────────────────────────────────────────────┘",
        "```",
        "",
        f"**汇聚路径**: `{' -> '.join(view.convergence_path)}`",
        f"**分叉点**: {', '.join(f'`{p}`' for p in view.fork_points)}",
    ])
    
    return "\n".join(lines)


def _render_bu_side(nodes: List[BidirectionalNode]) -> List[str]:
    """渲染 Bottom-Up 侧
    
    方向：Hotspot (上) → Root (下)
    连接线：从 parent 指向 child（向下箭头）
    """
    lines = []
    
    for i, node in enumerate(nodes):
        indent = "    " * node.level
        
        # 判断是否为汇聚点
        arrow = "◀═══════" if node.is_convergence else "│       "
        weight_str = f"{node.weight:.1%}" if node.weight > 0 else ""
        
        # 分叉点特殊标记
        if node.is_fork_point:
            lines.append(f"│{indent}    │    ")
            lines.append(f"│{indent}   ┌┴┐   ")
            lines.append(f"│{indent}   │F│   ")  # FORK
            lines.append(f"│{indent}   └┬┘   ")
        
        lines.append(f"│{indent}{node.symbol:20} {arrow} {weight_str:>6}")
        
        # 不是最后一个节点，添加连接线
        if i < len(nodes) - 1:
            lines.append(f"│{indent}    │    ")
            lines.append(f"│{indent}    ▼    ")
    
    return lines


def _render_td_side(nodes: List[BidirectionalNode], 
                    mirror_pairs: List[tuple]) -> List[str]:
    """渲染 Top-Down 侧
    
    方向：Root (上) → Hotspot (下)
    连接线：从 parent 指向 child（向下箭头）
    
    需要通过 mirror_pairs 添加虚线连接到上方的 BU 侧
    """
    lines = []
    mirror_dict = dict(mirror_pairs)  # symbol -> bu_level
    
    for i, node in enumerate(nodes):
        indent = "    " * node.level
        
        # 检查是否需要虚线连接
        mirror_marker = ""
        if node.symbol in mirror_dict:
            mirror_marker = "......."  # 虚线连接到上方
        
        # 判断是否为汇聚点
        arrow = "═══════▶" if node.is_convergence else "        "
        weight_str = f"{node.weight:.1%}" if node.weight > 0 else ""
        
        # 分叉点特殊标记
        if node.is_fork_point:
            lines.append(f"│{indent}   ┌┬┐   ")
            lines.append(f"│{indent}   │F│   ")
            lines.append(f"│{indent}   └┴┘   ")
        
        lines.append(f"│{indent}{node.symbol:20} {arrow} {weight_str:>6} {mirror_marker}")
        
        # 不是最后一个节点，添加连接线
        if i < len(nodes) - 1:
            next_node = nodes[i + 1]
            if next_node.level > node.level:
                # 向下深入
                lines.append(f"│{indent}    │    ")
                lines.append(f"│{indent}    ▼    ")
            elif next_node.level < node.level:
                # 回溯汇聚
                lines.append(f"│{indent}    └────┬")
    
    return lines
```

---

## 5. 从数据构建视图

```python
def build_bidirectional_view(
    bu_chains: List[CallChain],      # Bottom-Up 链 (hotspot→root)
    td_clusters: List[PathCluster]   # Top-Down 簇 (root→hotspot)
) -> BidirectionalView:
    """从原始数据构建双向视图"""
    
    # 1. 找出共同节点（汇聚点）
    bu_symbols = set()
    for chain in bu_chains:
        bu_symbols.update(chain.symbols)
    
    td_symbols = set()
    for cluster in td_clusters:
        td_symbols.update(cluster.symbols)
    
    convergence = bu_symbols & td_symbols
    
    # 2. 构建 BU 侧节点（按第一个链的顺序）
    bu_nodes = []
    reference_chain = bu_chains[0]  # 用权重最大的链作为参考
    
    for i, symbol in enumerate(reference_chain.symbols):
        node = BidirectionalNode(
            symbol=symbol,
            weight=reference_chain.weight if symbol == reference_chain.symbols[0] else 0,
            source=NodeSource.BOTH if symbol in convergence else NodeSource.BOTTOM_UP_ONLY,
            level=i,
            is_convergence=symbol in convergence,
            is_fork_point=_is_fork_point(symbol, bu_chains),
        )
        bu_nodes.append(node)
    
    # 3. 构建 TD 侧节点（反转顺序以匹配视觉流向）
    td_nodes = []
    reference_cluster = td_clusters[0]
    
    for i, symbol in enumerate(reference_cluster.symbols):
        node = BidirectionalNode(
            symbol=symbol,
            weight=reference_cluster.weight if i == len(reference_cluster.symbols) - 1 else 0,
            source=NodeSource.BOTH if symbol in convergence else NodeSource.TOP_DOWN_ONLY,
            level=len(reference_cluster.symbols) - 1 - i,  # 反转层级
            is_convergence=symbol in convergence,
            is_fork_point=_is_fork_point(symbol, td_clusters),
        )
        td_nodes.append(node)
    
    # 4. 构建镜像对（用于虚线连接）
    mirror_pairs = []
    for symbol in convergence:
        bu_level = next((n.level for n in bu_nodes if n.symbol == symbol), 0)
        td_level = next((n.level for n in td_nodes if n.symbol == symbol), 0)
        mirror_pairs.append((symbol, (bu_level, td_level)))
    
    return BidirectionalView(
        hotspot=reference_chain.symbols[0],
        total_weight=reference_chain.weight,
        bu_nodes=bu_nodes,
        td_nodes=td_nodes,
        mirror_pairs=mirror_pairs,
        convergence_path=[s for s in reference_chain.symbols if s in convergence],
        fork_points=[n.symbol for n in bu_nodes if n.is_fork_point],
    )


def _is_fork_point(symbol: str, chains: List[CallChain]) -> bool:
    """判断某节点是否为分叉点"""
    children = set()
    for chain in chains:
        if symbol in chain.symbols:
            idx = chain.symbols.index(symbol)
            if idx > 0:  # 不是最后一个（还有 child）
                children.add(chain.symbols[idx - 1])
    return len(children) > 1
```

---
## 6. 针对 1.txt 的实际输出示例

```markdown
## [BIDIRECTIONAL_VIEW] 双向调用链汇聚

```
┌──────────────────────────────────────────────┐
│              BOTTOM-UP                       │
│         (Hotspot → Root)                     │
├──────────────────────────────────────────────┤
│                                              │
│   established_get_first  ◀═══════  85.2%     │
│            │                                 │
│            ▼                                 │
│        vfs_read        ◀════════  85.2%     │
│            │                                 │
│            ▼                                 │
│     proc_reg_read      ◀════════  85.2%     │
│            │                                 │
│            ▼                                 │
│       seq_read         ◀════════  85.2%     │
│            │                                 │
│           ┌┴┐                                │
│           │F│              FORK POINT        │
│           └┬┘                                │
│     ┌──────┴──────┐                          │
│     ▼             ▼                          │
│  tcp_seq_start  tcp_seq_next                 │
│     │             │                          │
│     ▼             ▼                          │
│  tcp_get_idx    (truncated)                  │
│     │                                        │
│     ▼                                        │
│   (root)                                     │
├──────────────────────────────────────────────┤
│  ════════════════════════════════════════   │
│         CONVERGENCE MIRROR                   │
│  ─────────────────────────────────────────  │
├──────────────────────────────────────────────┤
│   (root)                                     │
│     │                                        │
│     ▼                                        │
│  tcp_get_idx                                 │
│     │                                        │
│     ▼      .......                           │
│  tcp_seq_start  ════════▶  45.9%             │
│     │      .......                           │
│     ├──────┐                                 │
│     │      │                                 │
│     ▼      ▼                                 │
│  seq_read  .............. seq_read  ════════▶│
│     │      .......      │      85.2%         │
│     │      .......      │                    │
│     └──────┬────────────┘                    │
│            ▼                                 │
│     proc_reg_read                            │
│            │                                 │
│            ▼                                 │
│        vfs_read                              │
│            │                                 │
│            ▼                                 │
│   established_get_first  ════════▶  85.2%    │
│            │                                 │
│            ▼                                 │
│         HOTSPOT                              │
├──────────────────────────────────────────────┤
│              TOP-DOWN                        │
│         (Root → Hotspot)                     │
└──────────────────────────────────────────────┘
```

**汇聚路径**: `seq_read -> proc_reg_read -> vfs_read -> established_get_first`
**分叉点**: `seq_read`
**覆盖样本**: 85.2%

### 解读

1. **共同路径**: 中间四层在两边视图都存在，说明这是主要瓶颈路径
2. **分叉点**: 在 `seq_read` 处，调用来源分为两个分支
3. **未聚合部分**: 虚线 `.......` 表示两边存在但层级不完全对齐的节点
```

---

## 7. 为什么选垂直方向

| 对比维度 | 左右方向 | 垂直方向 ✅ |
|----------|----------|-------------|
| **宽度限制** | 节点名易截断 | 每行独立，宽度充足 |
| **对齐复杂度** | 需计算两边字符数对齐 | 仅需单行内对齐 |
| **分叉展示** | 需左右同时分叉，混乱 | 树形结构自然展示 |
| **阅读顺序** | 左→右，符合习惯 | 上→下，同样自然 |
| **连接线** | 跨中间空白连接 | 同一行或相邻行连接 |
| **代码实现** | 复杂字符串格式化 | 简单行拼接 |

---

## 8. 接口约定

```python
# 输入：CallChain 来自 find-callers，PathCluster 来自 cluster-paths
def build_and_render(
    bu_chains: List[CallChain],
    td_clusters: List[PathCluster]
) -> str:
    """一站式构建并渲染双向视图"""
    view = build_bidirectional_view(bu_chains, td_clusters)
    return render_bidirectional_view(view)
```

---

*文档版本: 1.0*
*创建时间: 2026-03-04*
