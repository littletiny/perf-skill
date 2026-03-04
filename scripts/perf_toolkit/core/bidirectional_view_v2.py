#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bidirectional View V2 - 三段式双向调用链视图

支持多分支分叉场景：
1. [BOTTOM-UP] 热点溯源 - 多个分支汇聚到热点
2. [TOP-DOWN] 入口追踪 - 多个入口汇聚到共同点
3. [GLOBAL] 完整路径 - 端到端笛卡尔积连接

Example:
    >>> view = BidirectionalViewV2(
    ...     comm="app_worker",
    ...     hotspot="_raw_spin_lock",
    ...     upstream_branches=[...],
    ...     downstream_entries=[...]
    ... )
    >>> print(render_bidirectional_view_v2(view))
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Tuple
from enum import Enum, auto

import sys
from pathlib import Path

# 添加 scripts 目录到路径（支持直接运行此文件和作为模块导入）
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from perf_toolkit.core.callchain_formatter import CallChainFormatter


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class UpstreamBranch:
    """
    上游分支 (Bottom-Up)
    
    从热点向上追溯的一个调用分支。
    path 顺序: [直接调用者, ..., 根调用者] 
    例如: hotfunc <- A <- X1 <- X2 <- X3，则 path = [A, X1, X2, X3]
    拼接时会自动反转，使得完整路径为: entry -> ... -> X3 -> X2 -> X1 -> A -> hotfunc
    """
    branch_id: str          # 分支标识，如 "X", "Y"
    path: List[str]         # 从热点上游第一个调用者到根（按离热点近到远）
    weight: float           # 占比 (0-100)
    converges_at: Optional[str] = None  # 与 topdown 汇合的节点


@dataclass
class DownstreamEntry:
    """
    下游入口 (Top-Down)
    
    从入口向下到汇聚点的路径。
    path 顺序: [entry, node2, node3, ..., converge_node]
    """
    entry_id: str           # 入口标识，如 "entry1"
    path: List[str]         # 从入口到汇聚点（含汇聚点）
    weight: float           # 占比 (0-100)


@dataclass
class CompletePath:
    """
    完整的端到端路径
    
    由 downstream_entry 和 upstream_branch 笛卡尔积连接而成。
    """
    entry_id: str           # 入口标识
    branch_id: str          # 分支标识
    full_path: List[str]    # 完整路径 [entry, ..., converge, ..., hotspot]
    upstream_weight: float  # bottomup 分支权重
    downstream_weight: float # topdown 路径权重
    combined_weight: float  # 联合权重


@dataclass
class BidirectionalViewV2:
    """
    双向视图 V2 - 支持多分支分叉
    
    Attributes:
        comm: 进程名
        hotspot: 热点函数（所有路径的汇聚点）
        upstream_branches: Bottom-Up 分支列表（可能有多个）
        downstream_entries: Top-Down 入口列表（可能有多个）
        converge_node: 汇聚点（两边共同的节点）
        complete_paths: 笛卡尔积生成的完整路径
    """
    comm: str
    hotspot: str
    upstream_branches: List[UpstreamBranch] = field(default_factory=list)
    downstream_entries: List[DownstreamEntry] = field(default_factory=list)
    converge_node: Optional[str] = None
    complete_paths: List[CompletePath] = field(default_factory=list)


# =============================================================================
# Convergence Detection
# =============================================================================

def find_convergence_point(
    upstream_branches: List[UpstreamBranch],
    downstream_entries: List[DownstreamEntry]
) -> Optional[str]:
    """
    找到 bottomup 和 topdown 的汇聚点。
    
    策略：找第一个在 upstream_branches 中出现，
    且至少在一条 downstream_entry.path 中出现的节点。
    
    优先返回在 downstream 路径末尾附近的节点（更接近热点）。
    
    Args:
        upstream_branches: 上游分支列表
        downstream_entries: 下游入口列表
        
    Returns:
        汇聚点符号，如果没有则返回 None
    """
    if not upstream_branches or not downstream_entries:
        return None
    
    # 收集所有上游节点
    upstream_nodes: Set[str] = set()
    for branch in upstream_branches:
        upstream_nodes.update(branch.path)
    
    # 找第一个同时出现在 downstream 中的节点
    # 优先从 downstream 路径末尾开始找（更接近热点）
    best_convergence: Optional[str] = None
    best_score = -1
    
    for entry in downstream_entries:
        for i, node in enumerate(reversed(entry.path)):
            if node in upstream_nodes:
                # 评分：越靠近路径末尾（i越小）分数越高
                score = len(entry.path) - i
                if score > best_score:
                    best_score = score
                    best_convergence = node
    
    return best_convergence


def build_complete_paths(
    downstream_entries: List[DownstreamEntry],
    upstream_branches: List[UpstreamBranch],
    converge_node: Optional[str],
    hotspot: str
) -> List[CompletePath]:
    """
    构建完整的端到端路径（笛卡尔积或单边）。
    
    路径拼接逻辑：
    - downstream: entry -> ... -> converge_node (从上到下)
    - upstream: 从 converge_node 之后的部分，反转后添加（从下到上）
    - hotspot: 最后添加
    
    例如:
    - downstream: entry1 -> N -> S1 -> S2 -> S3 -> A
    - upstream: [A, X1, X2, X3]，converge=A，取 A 之后的部分 [X1, X2, X3]
    - 反转: [X3, X2, X1]
    - 结果: entry1 -> N -> S1 -> S2 -> S3 -> A -> X3 -> X2 -> X1 -> hotfunc
    
    Args:
        downstream_entries: 下游入口列表
        upstream_branches: 上游分支列表
        converge_node: 汇聚点（可为 None）
        hotspot: 热点函数
        
    Returns:
        完整路径列表，按 combined_weight 降序
    """
    complete_paths: List[CompletePath] = []
    
    # 处理双边数据
    if downstream_entries and upstream_branches:
        for entry in downstream_entries:
            for branch in upstream_branches:
                full_path: List[str] = []
                
                # 1. 添加 downstream 路径（到汇聚点）
                if converge_node and converge_node in entry.path:
                    idx = entry.path.index(converge_node)
                    full_path.extend(entry.path[:idx + 1])
                else:
                    full_path.extend(entry.path)
                
                # 2. 添加上游路径（从汇聚点之后开始，反转顺序）
                upstream_part: List[str] = []
                if converge_node and converge_node in branch.path:
                    idx = branch.path.index(converge_node)
                    upstream_part = branch.path[idx + 1:]
                else:
                    upstream_part = branch.path
                
                # 反转上游路径，使得 root 在前，热点调用者在后
                full_path.extend(reversed(upstream_part))
                
                # 3. 添加热点
                if not full_path or full_path[-1] != hotspot:
                    full_path.append(hotspot)
                
                combined = (entry.weight * branch.weight) / 100.0
                
                complete_paths.append(CompletePath(
                    entry_id=entry.entry_id,
                    branch_id=branch.branch_id,
                    full_path=full_path,
                    upstream_weight=branch.weight,
                    downstream_weight=entry.weight,
                    combined_weight=combined
                ))
    
    # 只有 downstream 数据
    elif downstream_entries and not upstream_branches:
        for entry in downstream_entries:
            full_path = list(entry.path)
            if not full_path or full_path[-1] != hotspot:
                full_path.append(hotspot)
            
            complete_paths.append(CompletePath(
                entry_id=entry.entry_id,
                branch_id="-",
                full_path=full_path,
                upstream_weight=0.0,
                downstream_weight=entry.weight,
                combined_weight=entry.weight
            ))
    
    # 只有 upstream 数据
    elif upstream_branches and not downstream_entries:
        for branch in upstream_branches:
            # upstream 单独存在时，反转使得 root 在前
            full_path = list(reversed(branch.path))
            if not full_path or full_path[-1] != hotspot:
                full_path.append(hotspot)
            
            complete_paths.append(CompletePath(
                entry_id="-",
                branch_id=branch.branch_id,
                full_path=full_path,
                upstream_weight=branch.weight,
                downstream_weight=0.0,
                combined_weight=branch.weight
            ))
    
    # 按 combined_weight 降序排序
    complete_paths.sort(key=lambda p: -p.combined_weight)
    return complete_paths


def aggregate_paths(
    paths: List[CompletePath],
    keep_top_n: int = 3
) -> List[CompletePath]:
    """
    聚合完整路径，保留 top N 条不聚合，其余聚合成一条。
    
    聚合策略：
    1. 按 combined_weight 排序
    2. 保留前 keep_top_n 条（不聚合）
    3. 剩余路径（如果有）聚合成一条
    
    Args:
        paths: 完整路径列表
        keep_top_n: 保留不聚合的路径数（默认3）
        
    Returns:
        聚合后的路径列表
    """
    if len(paths) <= keep_top_n:
        return paths
    
    # 保留前 N 条
    top_paths = paths[:keep_top_n]
    remaining = paths[keep_top_n:]
    
    # 聚合剩余路径
    total_weight = sum(p.combined_weight for p in remaining)
    total_downstream = sum(p.downstream_weight for p in remaining)
    total_upstream = sum(p.upstream_weight for p in remaining)
    
    # 统计剩余的 entries 和 branches
    entry_ids = set(p.entry_id for p in remaining)
    branch_ids = set(p.branch_id for p in remaining)
    
    # 简化显示
    entry_str = f"{len(entry_ids)}e" if len(entry_ids) > 1 else list(entry_ids)[0]
    branch_str = f"{len(branch_ids)}b" if len(branch_ids) > 1 else list(branch_ids)[0]
    
    aggregated = CompletePath(
        entry_id=f"{entry_str}",
        branch_id=f"{branch_str}",
        full_path=[f"... {len(remaining)} paths aggregated ..."],
        upstream_weight=total_upstream / len(remaining),
        downstream_weight=total_downstream / len(remaining),
        combined_weight=total_weight
    )
    
    return top_paths + [aggregated]


# =============================================================================
# View Builder
# =============================================================================

def build_bidirectional_view_v2(
    comm: str,
    hotspot: str,
    upstream_branches: List[UpstreamBranch],
    downstream_entries: List[DownstreamEntry],
    keep_top_n: int = 3
) -> BidirectionalViewV2:
    """
    构建双向视图 V2。
    
    Args:
        comm: 进程名
        hotspot: 热点函数
        upstream_branches: 上游分支列表
        downstream_entries: 下游入口列表
        keep_top_n: 保留不聚合的路径数（默认3），其余聚合成一条
        
    Returns:
        BidirectionalViewV2 实例
    """
    # 1. 检测汇聚点
    converge_node = find_convergence_point(upstream_branches, downstream_entries)
    
    # 2. 更新每个分支的 converges_at
    if converge_node:
        for branch in upstream_branches:
            if converge_node in branch.path:
                branch.converges_at = converge_node
    
    # 3. 构建完整路径
    complete_paths = build_complete_paths(
        downstream_entries, upstream_branches, 
        converge_node or hotspot, hotspot
    )
    
    # 4. 聚合路径（保留 keep_top_n 条不聚合，其余聚合）
    aggregated_paths = aggregate_paths(complete_paths, keep_top_n=keep_top_n)
    
    return BidirectionalViewV2(
        comm=comm,
        hotspot=hotspot,
        upstream_branches=upstream_branches,
        downstream_entries=downstream_entries,
        converge_node=converge_node,
        complete_paths=aggregated_paths
    )


# =============================================================================
# Renderer
# =============================================================================

def render_bidirectional_view_v2(view: BidirectionalViewV2) -> str:
    """
    渲染双向视图 - 仅 GLOBAL 完整调用链（已聚合）。
    
    Args:
        view: BidirectionalViewV2 实例
        
    Returns:
        渲染后的 Markdown 格式字符串
    """
    lines: List[str] = [
        f"## [BOTTLENECK: {view.comm}] → {view.hotspot}",
        "",
    ]
    
    # 只保留 GLOBAL 部分（使用已聚合的路径）
    lines.extend(_render_global_section(view))
    
    return "\n".join(lines)


def _render_global_section(view: BidirectionalViewV2) -> List[str]:
    """渲染 GLOBAL 部分（路径已聚合）- 使用 CallChainFormatter 统一风格"""
    lines = [
        "### [CALLCHAINS] 完整调用链",
        "",
    ]
    
    for i, path in enumerate(view.complete_paths, 1):
        if len(path.full_path) == 1 and "aggregated" in path.full_path[0]:
            # 聚合项
            lines.append(f"#{i} [{path.combined_weight:.2f}%] {path.full_path[0]}")
        else:
            # 使用 CallChainFormatter 统一格式化
            # full_path 顺序是 [entry, ..., hotspot]，需要反转使热点在前
            # bottom_up 方向: 热点 <- caller <- entry
            reversed_path = list(reversed(path.full_path))
            path_str = CallChainFormatter.format(
                path=reversed_path,
                direction="bottom_up",  # 热点 <- caller <- entry
                style="plain",          # 纯文本，无 markdown 标记
                use_hotspot_marker=False
            )
            lines.append(f"#{i} [{path.combined_weight:.2f}%] {path_str}")
    
    return lines


# =============================================================================
# Convenience Functions
# =============================================================================

def build_and_render_v2(
    comm: str,
    hotspot: str,
    upstream_branches: List[UpstreamBranch],
    downstream_entries: List[DownstreamEntry],
    keep_top_n: int = 3
) -> str:
    """
    一站式构建并渲染双向视图 V2。
    
    Args:
        comm: 进程名
        hotspot: 热点函数
        upstream_branches: 上游分支列表
        downstream_entries: 下游入口列表
        keep_top_n: 保留不聚合的路径数（默认3），其余聚合成一条
        
    Returns:
        渲染后的 Markdown 格式字符串
    """
    view = build_bidirectional_view_v2(
        comm, hotspot, upstream_branches, downstream_entries,
        keep_top_n=keep_top_n
    )
    return render_bidirectional_view_v2(view)


# =============================================================================
# Test Entry Point
# =============================================================================

if __name__ == "__main__":
    # 测试用例：匹配用户描述的分叉场景
    
    # Bottom-Up: hotfunc--A--X1--X2--X3 / hotfunc--A--Y1--Y2--Y3
    upstream_branches = [
        UpstreamBranch(branch_id="X", path=["A", "X1", "X2", "X3"], weight=35.0),
        UpstreamBranch(branch_id="Y", path=["A", "Y1", "Y2", "Y3"], weight=28.0),
    ]
    
    # Top-Down: entry1--N--S1--S2--S3--A / entry2--N--D1--D2--D3--A / entry3--N--Z1--Z2--Z3--A
    downstream_entries = [
        DownstreamEntry(entry_id="entry1", path=["entry1", "N", "S1", "S2", "S3", "A"], weight=20.0),
        DownstreamEntry(entry_id="entry2", path=["entry2", "N", "D1", "D2", "D3", "A"], weight=15.0),
        DownstreamEntry(entry_id="entry3", path=["entry3", "N", "Z1", "Z2", "Z3", "A"], weight=10.0),
    ]
    
    # 构建并渲染
    output = build_and_render_v2(
        comm="app_worker",
        hotspot="hotfunc",
        upstream_branches=upstream_branches,
        downstream_entries=downstream_entries
    )
    print(output)
