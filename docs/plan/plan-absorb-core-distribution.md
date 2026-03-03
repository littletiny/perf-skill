# Plan: Absorb analyze-core-distribution into sys-audit and bottleneck-trace

## 背景

根据需求，`analyze-core-distribution` 独立接口将被删除，其功能拆分吸收到：
1. **sys-audit**: 作为全局指纹的一部分（检测核心倾斜、单核爆满）
2. **bottleneck-trace**: 检测并报告 Affinity Conflict（亲和性冲突）

## 改动范围

### 1. 删除独立 CLI 命令

**文件**: `scripts/perf_toolkit/cli/commands/analysis/core_dist.py`
- **操作**: 删除整个文件

**文件**: `scripts/perf_toolkit/cli/commands/analysis/__init__.py`
- **操作**: 
  - 从 `COMMAND_MAP` 中移除 `'analyze-core-distribution'` 条目
  - 从 `handler_map` 中移除对应映射
  - 删除 `analyze-core-distribution` 的 add_parser 代码块

**文档更新**:
- `references/tools.md`: 移除该命令的文档
- `SKILL.md`: 更新命令列表

### 2. 吸收到 sys-audit（全局指纹）

#### 2.1 数据模型扩展

**文件**: `scripts/perf_toolkit/core/output_models.py`

在 `SystemFingerprint` dataclass 中添加核心分布相关字段：

```python
@dataclass
class SystemFingerprint:
    """系统指纹"""
    pressure_state: str = PressureState.NORMAL
    cpu_some: float = 0.0
    cpu_full: float = 0.0
    io_some: float = 0.0
    memory_full: float = 0.0
    throttle_events: int = 0
    context_switch_rate: str = ContextSwitchRate.NORMAL
    
    # 新增: 核心分布指纹
    core_imbalance_detected: bool = False      # 是否存在核心倾斜
    core_imbalance_level: str = "NORMAL"       # 倾斜级别: NORMAL/MODERATE/HIGH/CRITICAL
    single_core_saturation: bool = False       # 是否存在单核爆满
    saturated_core_count: int = 0              # 饱和核心数量
    saturated_core_ids: List[int] = field(default_factory=list)  # 饱和核心ID列表
    max_core_utilization: float = 0.0          # 最高核心利用率
    avg_core_utilization: float = 0.0          # 平均核心利用率
```

#### 2.2 构建逻辑更新

**文件**: `scripts/perf_toolkit/cli/commands/composite/sys_audit.py`

更新 `_build_system_fingerprint` 函数：

```python
def _build_system_fingerprint(
    diagnosis: 'DiagnosisReport',
    core_dist: CoreDistributionReport
) -> SystemFingerprint:
    """构建系统指纹（包含核心分布检测）"""
    
    # 计算核心分布指标
    core_stats = core_dist.core_stats
    if core_stats:
        utils = [c.total_cpu for c in core_stats]
        max_util = max(utils)
        min_util = min(utils)
        avg_util = sum(utils) / len(utils)
        imbalance_ratio = max_util / avg_util if avg_util > 0 else 0
        
        # 检测核心倾斜
        core_imbalance_detected = imbalance_ratio > 2.0 and max_util > 50
        if imbalance_ratio > 10 and max_util > 50:
            core_imbalance_level = ImbalanceLevel.CRITICAL
        elif imbalance_ratio > 5:
            core_imbalance_level = ImbalanceLevel.HIGH
        elif imbalance_ratio > 2:
            core_imbalance_level = ImbalanceLevel.MODERATE
        else:
            core_imbalance_level = ImbalanceLevel.NORMAL
        
        # 检测单核爆满
        saturated_cores = [c.cpu_id for c in core_stats if c.total_cpu > 80]
        single_core_saturation = len(saturated_cores) == 1 and len(core_stats) > 1
    else:
        core_imbalance_detected = False
        core_imbalance_level = ImbalanceLevel.NORMAL
        single_core_saturation = False
        saturated_cores = []
        max_util = avg_util = 0.0
    
    # 原有压力状态逻辑
    pressure_state = PressureState.NORMAL
    if diagnosis.primary_suspect and diagnosis.primary_suspect.diagnosis == DiagnosisType.BOTTLENECK:
        pressure_state = PressureState.CRITICAL_CONTENTION
    elif diagnosis.secondary_loads:
        pressure_state = PressureState.MODERATE_CONTENTION
    
    return SystemFingerprint(
        pressure_state=pressure_state,
        cpu_some=0.92 if diagnosis.primary_suspect else 0.0,
        cpu_full=0.45 if diagnosis.primary_suspect else 0.0,
        io_some=0.12,
        throttle_events=1250 if diagnosis.primary_suspect else 0,
        context_switch_rate=ContextSwitchRate.EXTREME if diagnosis.secondary_loads else ContextSwitchRate.NORMAL,
        # 新增核心分布指纹
        core_imbalance_detected=core_imbalance_detected,
        core_imbalance_level=core_imbalance_level,
        single_core_saturation=single_core_saturation,
        saturated_core_count=len(saturated_cores),
        saturated_core_ids=saturated_cores[:5],  # 最多5个
        max_core_utilization=max_util,
        avg_core_utilization=avg_util
    )
```

### 3. 吸收到 bottleneck-trace（系统级瓶颈检测 + Affinity Conflict）

#### 3.1 系统级瓶颈检测类型

根据 Hierarchical Driver 模型（L1-L2），bottleneck-trace 需要支持以下系统级瓶颈类型：

| 类型 | 检测依据 | 输出字段 |
|------|----------|----------|
| `SINGLE_CORE_SATURATION` | 单核利用率 > 80%，Monopoly > 0.8 | `core_saturation` |
| `AFFINITY_CONFLICT` | 目标进程运行在已被占满的核心上 | `affinity_conflict` |
| `SYSTEM_WIDE_CPU` | 全局 CPU 利用率 > 80%，多核饱和 | `system_wide_pressure` |
| `RESOURCE_CONTENTION` | 多进程竞争同一核心/资源 | `contention_detected` |

#### 3.2 数据模型扩展

**文件**: `scripts/perf_toolkit/core/output_models.py`

在 `BottleneckProfile` 中新增系统级瓶颈检测字段：

```python
@dataclass
class BottleneckProfile:
    """瓶颈特征分析数据"""
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = DiagnosisType.NORMAL
    impact_score: float = 0.0
    
    # 新增: 系统级瓶颈检测
    bottleneck_type: str = "UNKNOWN"           # SINGLE_CORE/SYSTEM_WIDE/AFFINITY_CONFLICT/RESOURCE_CONTENTION
    core_saturation: Dict = field(default_factory=dict)  # {cpu_id: utilization}
    system_wide_pressure: bool = False         # 是否系统级压力
    contention_detected: bool = False          # 是否检测到资源竞争
    
    # 新增: 亲和性冲突检测
    affinity_conflict: bool = False            # 是否存在亲和性冲突
    conflict_core_id: Optional[int] = None     # 冲突核心ID
    conflict_description: str = ""             # 冲突描述，如 "Core #4 is saturated by lsof_cluster"
```

新增 `CoreSaturationInfo` dataclass：

```python
@dataclass
class CoreSaturationInfo:
    """核心饱和信息"""
    cpu_id: int
    utilization: float
    dominant_comm: str           # 占用该核心的主要进程
    dominant_comm_ratio: float   # 主要进程占比
```

```python
@dataclass
class BottleneckProfile:
    """瓶颈特征分析数据"""
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = DiagnosisType.NORMAL
    impact_score: float = 0.0
    
    # 新增: 亲和性冲突检测
    affinity_conflict: bool = False            # 是否存在亲和性冲突
    conflict_core_id: Optional[int] = None     # 冲突核心ID
    conflict_description: str = ""             # 冲突描述，如 "Core #4 is saturated by lsof_cluster"
```

在 `RootCauseAnalysis` 中可选择性添加受害路径标记：

```python
@dataclass
class RootCauseAnalysis:
    """根因分析"""
    primary_driver: str
    evidence: str
    mechanism: str
    victim: str
    affinity_conflict: bool = False            # 新增: 是否是亲和性冲突导致的受害者
    conflict_core_id: Optional[int] = None     # 冲突核心ID
```

#### 3.3 检测逻辑实现

**文件**: `scripts/perf_toolkit/composite/bottleneck_trace.py`

新增系统级瓶颈检测函数 `_analyze_system_wide_bottleneck`：

```python
def _analyze_system_wide_bottleneck(
    facade: AnalysisFacade,
    samples: List[Dict],
    target_comm: str
) -> Tuple[str, Dict, Optional[CoreSaturationInfo]]:
    """
    分析系统级瓶颈类型
    
    根据核心分布判断瓶颈是单核饱和、系统级压力还是亲和性冲突。
    
    Returns:
        Tuple[瓶颈类型, 核心分布信息, 主要饱和核心信息]
    """
    from config.defaults import Thresholds
    
    # 1. 获取核心分布
    core_dist_result = facade.analyze_core_distribution(samples)
    
    if not core_dist_result.cores:
        return "UNKNOWN", {}, None
    
    # 2. 计算系统级指标
    core_utils = {c.cpu_id: c.total_cpu for c in core_dist_result.cores}
    avg_util = sum(core_utils.values()) / len(core_utils)
    max_util = max(core_utils.values())
    min_util = min(core_utils.values())
    
    # 3. 统计饱和核心
    saturated_cores = {
        cpu_id: util for cpu_id, util in core_utils.items()
        if util > Thresholds.CORE_SATURATED_THRESHOLD
    }
    saturated_count = len(saturated_cores)
    total_cores = len(core_utils)
    
    # 4. 找出占用最高饱和核心的主要进程
    dominant_core_info = None
    if saturated_cores:
        max_core_id = max(saturated_cores, key=saturated_cores.get)
        max_util_val = saturated_cores[max_core_id]
        
        # 统计该核心上的进程分布
        core_samples = [s for s in samples if s.get('cpu_id', s.get('cpu', -1)) == max_core_id]
        comm_count: Dict[str, int] = {}
        for s in core_samples:
            comm = s.get('comm', 'unknown')
            comm_count[comm] = comm_count.get(comm, 0) + 1
        
        if comm_count:
            top_comm = max(comm_count, key=comm_count.get)
            top_ratio = comm_count[top_comm] / len(core_samples) if core_samples else 0
            dominant_core_info = CoreSaturationInfo(
                cpu_id=max_core_id,
                utilization=max_util_val,
                dominant_comm=top_comm,
                dominant_comm_ratio=top_ratio
            )
    
    # 5. 判断瓶颈类型
    core_dist_info = {
        "avg_utilization": avg_util,
        "max_utilization": max_util,
        "min_utilization": min_util,
        "saturated_core_count": saturated_count,
        "total_core_count": total_cores,
        "saturated_cores": saturated_cores
    }
    
    # 系统级压力：多核饱和或全局高利用率
    if saturated_count >= total_cores * 0.5 or avg_util > 70:
        return "SYSTEM_WIDE", core_dist_info, dominant_core_info
    
    # 单核饱和：只有一个核心饱和
    if saturated_count == 1:
        # 检查是否是目标进程导致的
        if dominant_core_info and dominant_core_info.dominant_comm == target_comm:
            return "SINGLE_CORE_SELF", core_dist_info, dominant_core_info
        else:
            return "AFFINITY_CONFLICT", core_dist_info, dominant_core_info
    
    # 资源竞争：多个核心部分饱和
    if saturated_count > 1 and saturated_count < total_cores * 0.5:
        return "RESOURCE_CONTENTION", core_dist_info, dominant_core_info
    
    return "NORMAL", core_dist_info, None
```

修改 `_analyze_bottleneck` 函数，整合系统级分析：

```python
def _analyze_bottleneck(
    facade: AnalysisFacade, 
    samples, 
    comm: str
) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征（包含系统级分析）"""
    
    # ... 原有分析逻辑 ...
    
    # 新增: 系统级瓶颈分析
    bottleneck_type, core_dist_info, dominant_core = _analyze_system_wide_bottleneck(
        facade, samples, comm
    )
    
    # 新增: Affinity Conflict 检测（当不是自身导致单核饱和时）
    has_conflict = False
    conflict_core = None
    conflict_desc = ""
    
    if bottleneck_type == "AFFINITY_CONFLICT" and dominant_core:
        has_conflict = True
        conflict_core = dominant_core.cpu_id
        conflict_desc = f"Core #{dominant_core.cpu_id} is saturated by {dominant_core.dominant_comm}"
        
        # 检查目标进程在该核心上的占比
        comm_samples = [s for s in samples if s.get('comm') == comm]
        core_samples = [s for s in comm_samples if s.get('cpu_id', s.get('cpu', -1)) == conflict_core]
        if comm_samples and len(core_samples) / len(comm_samples) > 0.3:
            conflict_desc += f", {comm} also runs on this core"
    
    # 更新返回结果
    result = BottleneckAnalysis(
        found=True,
        comm=comm,
        total_cpu=target_group.total_cpu,
        kernel_ratio=kernel_ratio,
        pid_count=target_group.pid_count,
        cv=target_group.cv,
        monopoly=target_group.monopoly,
        diagnosis=target_group.diagnosis,
        impact_score=target_group.impact_score,
        risks=risks,
        # 新增系统级分析结果
        bottleneck_type=bottleneck_type,
        core_saturation=core_dist_info.get("saturated_cores", {}),
        system_wide_pressure=bottleneck_type == "SYSTEM_WIDE",
        contention_detected=bottleneck_type == "RESOURCE_CONTENTION",
        # 新增亲和性冲突信息
        affinity_conflict=has_conflict,
        conflict_core_id=conflict_core,
        conflict_description=conflict_desc
    )
    
    # 根据瓶颈类型添加 risk
    if bottleneck_type == "AFFINITY_CONFLICT":
        result.risks.append(RiskInfo(
            level="warning",
            message=f"{comm} 受亲和性冲突影响: {conflict_desc}",
            hint=f"检查 {comm} 的 CPU 亲和性设置或考虑迁移到其他核心",
            patterns=["AFFINITY_CONFLICT"],
            pending_targets=[comm],
            source="bottleneck"
        ))
    elif bottleneck_type == "SYSTEM_WIDE":
        result.risks.append(RiskInfo(
            level="critical",
            message=f"系统级 CPU 压力: {core_dist_info['saturated_core_count']}/{core_dist_info['total_core_count']} 核心饱和",
            hint="系统整体负载过高，考虑扩容或优化全局配置",
            patterns=["SYSTEM_WIDE_PRESSURE"],
            pending_targets=[comm],
            source="bottleneck"
        ))
    elif bottleneck_type == "SINGLE_CORE_SELF":
        result.risks.append(RiskInfo(
            level="critical",
            message=f"{comm} 单核饱和 (Monopoly={target_group.monopoly:.2f})",
            hint=f"执行 get-hotspots --comm {comm} 分析热点函数",
            patterns=["SINGLE_CORE_SATURATION"],
            pending_targets=[comm],
            source="bottleneck"
        ))
    
    return result
```

原 `_detect_affinity_conflict` 函数（已整合到 `_analyze_system_wide_bottleneck`）：

```python
def _detect_affinity_conflict(
    facade: AnalysisFacade,
    samples: List[Dict],
    target_comm: str
) -> Tuple[bool, Optional[int], str]:
    """
    检测亲和性冲突
    
    检查目标进程是否运行在已被其他高负载进程占满的核心上。
    
    Returns:
        Tuple[是否冲突, 冲突核心ID, 冲突描述]
    """
    # 1. 获取各核心利用率
    core_util_result = facade.analyze_core_distribution(samples)
    
    # 2. 找出饱和核心（利用率 > 80%）
    saturated_cores = {
        c.cpu_id: c for c in core_util_result.cores 
        if c.total_cpu > 80
    }
    
    if not saturated_cores:
        return False, None, ""
    
    # 3. 获取目标进程在各核心上的分布
    comm_samples = [s for s in samples if s.get('comm') == target_comm]
    if not comm_samples:
        return False, None, ""
    
    # 统计目标进程在饱和核心上的样本数
    core_sample_count: Dict[int, int] = {}
    for s in comm_samples:
        cpu_id = s.get('cpu_id', s.get('cpu', -1))
        if cpu_id in saturated_cores:
            core_sample_count[cpu_id] = core_sample_count.get(cpu_id, 0) + 1
    
    if not core_sample_count:
        return False, None, ""
    
    # 4. 找出目标进程运行最多的饱和核心
    max_core_id = max(core_sample_count, key=core_sample_count.get)
    max_count = core_sample_count[max_core_id]
    total_samples = len(comm_samples)
    
    # 如果目标进程有超过30%的样本在饱和核心上，认为是冲突
    if max_count / total_samples < 0.3:
        return False, None, ""
    
    # 5. 找出占用该核心的主要进程
    core_samples = [s for s in samples if s.get('cpu_id', s.get('cpu', -1)) == max_core_id]
    comm_count: Dict[str, int] = {}
    for s in core_samples:
        comm = s.get('comm', 'unknown')
        if comm != target_comm:
            comm_count[comm] = comm_count.get(comm, 0) + 1
    
    if comm_count:
        top_comm = max(comm_count, key=comm_count.get)
        conflict_desc = f"Core #{max_core_id} is saturated by {top_comm}"
    else:
        conflict_desc = f"Core #{max_core_id} is saturated"
    
    return True, max_core_id, conflict_desc
```

在 `_analyze_bottleneck` 函数中调用冲突检测：

```python
def _analyze_bottleneck(
    facade: AnalysisFacade, 
    samples, 
    comm: str
) -> BottleneckAnalysis:
    """分析指定进程的瓶颈特征（包含亲和性冲突检测）"""
    
    # ... 原有分析逻辑 ...
    
    # 新增: 检测亲和性冲突
    has_conflict, conflict_core, conflict_desc = _detect_affinity_conflict(
        facade, samples, comm
    )
    
    # 更新返回结果
    result = BottleneckAnalysis(
        found=True,
        comm=comm,
        total_cpu=target_group.total_cpu,
        kernel_ratio=kernel_ratio,
        pid_count=target_group.pid_count,
        cv=target_group.cv,
        monopoly=target_group.monopoly,
        diagnosis=target_group.diagnosis,
        impact_score=target_group.impact_score,
        risks=risks,
        # 新增亲和性冲突信息
        affinity_conflict=has_conflict,
        conflict_core_id=conflict_core,
        conflict_description=conflict_desc
    )
    
    # 如果有亲和性冲突，添加 risk
    if has_conflict:
        result.risks.append(RiskInfo(
            level="warning",
            message=f"{comm} 受亲和性冲突影响: {conflict_desc}",
            hint=f"检查 {comm} 的 CPU 亲和性设置或考虑迁移到其他核心",
            patterns=["AFFINITY_CONFLICT"],
            pending_targets=[comm],
            source="bottleneck"
        ))
    
    return result
```

**文件**: `scripts/perf_toolkit/composite/models.py`

确保 `BottleneckAnalysis` dataclass 包含新字段：

```python
@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = DiagnosisType.NORMAL
    impact_score: float = 0.0
    risks: List[RiskInfo] = field(default_factory=list)
    
    # 新增: 亲和性冲突
    affinity_conflict: bool = False
    conflict_core_id: Optional[int] = None
    conflict_description: str = ""
```

#### 3.4 模型层更新

**文件**: `scripts/perf_toolkit/composite/models.py`

确保 `BottleneckAnalysis` dataclass 包含新字段：

```python
@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    found: bool = False
    comm: str = ""
    total_cpu: float = 0.0
    kernel_ratio: float = 0.0
    pid_count: int = 0
    cv: float = 0.0
    monopoly: float = 0.0
    diagnosis: str = DiagnosisType.NORMAL
    impact_score: float = 0.0
    risks: List[RiskInfo] = field(default_factory=list)
    
    # 新增: 系统级瓶颈分析
    bottleneck_type: str = "UNKNOWN"           # SINGLE_CORE_SELF/SYSTEM_WIDE/AFFINITY_CONFLICT/RESOURCE_CONTENTION/NORMAL
    core_saturation: Dict = field(default_factory=dict)
    system_wide_pressure: bool = False
    contention_detected: bool = False
    
    # 新增: 亲和性冲突
    affinity_conflict: bool = False
    conflict_core_id: Optional[int] = None
    conflict_description: str = ""
```

#### 3.5 CLI 层更新

**文件**: `scripts/perf_toolkit/cli/commands/composite/bottleneck_trace.py`

更新 `_build_root_cause` 函数，支持系统级瓶颈类型：

```python
def _build_root_cause(
    bottleneck: BottleneckAnalysis,
    target_comm: str
) -> Optional[RootCauseAnalysis]:
    """构建根因分析（包含系统级瓶颈类型）"""
    if not bottleneck.found:
        return None
    
    # 根据瓶颈类型构建根因分析
    if bottleneck.bottleneck_type == "AFFINITY_CONFLICT":
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 受 CPU 亲和性冲突影响",
            evidence=bottleneck.conflict_description or f"运行在饱和核心 Core #{bottleneck.conflict_core_id}",
            mechanism="目标进程与其他高负载进程共享同一核心，导致资源竞争",
            victim=f"{target_comm} 的有效 CPU 时间被抢占",
            affinity_conflict=True,
            conflict_core_id=bottleneck.conflict_core_id
        )
    
    elif bottleneck.bottleneck_type == "SYSTEM_WIDE":
        return RootCauseAnalysis(
            primary_driver=f"系统级 CPU 压力影响 {target_comm}",
            evidence=f"{len(bottleneck.core_saturation)} 个核心饱和，全局资源紧张",
            mechanism="系统整体负载过高，调度器无法为所有进程分配足够 CPU 时间",
            victim=f"{target_comm} 与其他进程共同受限于系统资源"
        )
    
    elif bottleneck.bottleneck_type == "SINGLE_CORE_SELF":
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 单核瓶颈",
            evidence=f"Monopoly={bottleneck.monopoly:.2f}, 单进程独占 CPU",
            mechanism="单进程无法利用多核，导致串行化执行",
            victim="业务请求处理延迟增加"
        )
    
    elif bottleneck.bottleneck_type == "RESOURCE_CONTENTION":
        return RootCauseAnalysis(
            primary_driver=f"{target_comm} 面临多核资源竞争",
            evidence=f"多个核心部分饱和，进程间资源竞争",
            mechanism="多进程争夺 CPU 资源，调度开销增加",
            victim=f"{target_comm} 的调度延迟增加"
        )
    
    # 原有诊断逻辑（STORM, UNBALANCED 等）...
```

更新 `BottleneckProfile` 构建，包含系统级瓶颈信息：

```python
bottleneck_profile = BottleneckProfile(
    found=bottleneck_analysis.found,
    comm=bottleneck_analysis.comm,
    total_cpu=bottleneck_analysis.total_cpu,
    kernel_ratio=bottleneck_analysis.kernel_ratio,
    pid_count=bottleneck_analysis.pid_count,
    cv=bottleneck_analysis.cv,
    monopoly=bottleneck_analysis.monopoly,
    diagnosis=bottleneck_analysis.diagnosis,
    impact_score=bottleneck_analysis.impact_score,
    # 新增系统级瓶颈信息
    bottleneck_type=bottleneck_analysis.bottleneck_type,
    core_saturation=bottleneck_analysis.core_saturation,
    system_wide_pressure=bottleneck_analysis.system_wide_pressure,
    contention_detected=bottleneck_analysis.contention_detected,
    # 新增亲和性冲突
    affinity_conflict=bottleneck_analysis.affinity_conflict,
    conflict_core_id=bottleneck_analysis.conflict_core_id,
    conflict_description=bottleneck_analysis.conflict_description
)
```

### 4. 保留的 Core Distribution 分析能力

注意：`analyze_core_distribution` 分析能力本身保留在 Analysis 层（`analysis/core_distribution.py` 和 `facade.py`），只是移除了独立的 CLI 命令。sys-audit 和 bottleneck-trace 仍通过 Facade 调用该分析能力。

### 5. 测试更新

**需要更新的测试文件**:
- `tests/three_tier/test_core_interfaces.py`: 如果测试了 CLI 命令，需要移除相关测试
- `tests/test_trace_audit.py`: 检查是否涉及该命令
- 其他相关测试

**需要新增的测试**:
- sys-audit 中核心分布指纹检测的测试
- bottleneck-trace 中亲和性冲突检测的测试

## 实施顺序

1. **Phase 1**: 修改数据模型（output_models.py, composite/models.py）
2. **Phase 2**: 修改 bottleneck-trace 系统级检测逻辑（composite/bottleneck_trace.py）
3. **Phase 3**: 修改 sys-audit 构建逻辑（cli/commands/composite/sys_audit.py）
4. **Phase 4**: 修改 CLI 层 bottleneck-trace（cli/commands/composite/bottleneck_trace.py）
5. **Phase 5**: 删除 analyze-core-distribution CLI 命令
6. **Phase 6**: 更新文档
7. **Phase 7**: 运行测试验证

## 变更总结

### 功能增强

| 命令 | 新增能力 | 说明 |
|------|----------|------|
| `sys-audit` | 核心分布指纹 | `system_fingerprint` 新增 `core_imbalance_detected`, `single_core_saturation` 等字段 |
| `bottleneck-trace` | 系统级瓶颈分类 | 新增 `bottleneck_type` 字段，区分 SINGLE_CORE_SELF/SYSTEM_WIDE/AFFINITY_CONFLICT/RESOURCE_CONTENTION |
| `bottleneck-trace` | 亲和性冲突检测 | 新增 `affinity_conflict`, `conflict_core_id`, `conflict_description` 字段 |
| `bottleneck-trace` | 系统级压力检测 | 新增 `system_wide_pressure`, `contention_detected` 字段 |

### 删除内容

| 内容 | 说明 |
|------|------|
| `analyze-core-distribution` CLI 命令 | 功能被完全吸收到 sys-audit 和 bottleneck-trace |

### 向后兼容性

- **Breaking Change**: `analyze-core-distribution` 命令将被删除，用户需改用 `sys-audit` 或 `bottleneck-trace`
- **数据格式**: `bottleneck-trace` 输出新增字段，现有字段保持不变

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 删除 CLI 命令破坏用户脚本 | 高 | 在 CHANGELOG 中明确标记 Breaking Change |
| Affinity Conflict 检测不准确 | 中 | 设置合理的阈值（30%样本在饱和核心），可配置 |
| 性能开销增加 | 低 | analyze_core_distribution 分析已存在，只是复用结果 |

## 验收标准

1. `shecr analyze-core-distribution` 命令不存在（返回未知命令错误）
2. `shecr sys-audit` 输出包含 `system_fingerprint.core_imbalance_detected` 等字段
3. `shecr bottleneck-trace --comm <name>` 输出包含：
   - `bottleneck_type`: SINGLE_CORE_SELF/SYSTEM_WIDE/AFFINITY_CONFLICT/RESOURCE_CONTENTION
   - `affinity_conflict`: true/false
   - `conflict_description`: 如 "Core #4 is saturated by lsof_cluster"
   - `system_wide_pressure`: true/false
4. **系统级瓶颈检测场景覆盖**:
   - 单核自饱和：目标进程自身独占核心
   - 亲和性冲突：目标进程与其他进程共享饱和核心
   - 系统级压力：多核饱和，全局资源紧张
   - 资源竞争：部分核心饱和，多进程竞争
5. 所有现有测试通过
6. 文档已同步更新
