# Core Layer 接口设计文档

> 设计目标：为 perf-hunter 三层架构提供强类型 Core Layer 接口
> 
> 核心原则：**禁止裸 `dict` 传递数据，必须使用 `dataclass`**

---

## 1. 概述

Core Layer 是 perf-hunter 三层架构的最底层，负责：
- 数据加载与解析
- 符号解析与管理
- 输出构建与格式化
- Trace 记录

### 1.1 架构位置

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Composite (组合层)                             │
│  通过 AnalysisFacade 调用，不直接访问 Core Layer        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Analysis (分析层)                              │
│  通过 Engine 接口获取数据，通过 OutputBuilder 输出        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Core (核心层) ← 本文档定义                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Engine    │  │OutputBuilder│  │    Trace    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **强类型** | 所有数据结构使用 dataclass，禁止裸 dict |
| **类型注解** | 所有方法参数和返回值必须有类型注解 |
| **文档自描述** | 每个 dataclass 和方法必须有 docstring |
| **不可变性优先** | 数据对象一旦创建，优先不修改 |
| **单一职责** | 每个类只负责一类功能 |

---

## 2. 数据模型定义

### 2.1 基础类型

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any, Tuple
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    """风险等级枚举
    
    对应 SHECR 方法论中的 attention flags:
    - CRITICAL: X0 - 关键问题，必须解决
    - WARNING: X1 - 警告，需要关注
    - INFO: X2 - 信息提示
    - NONE: 无风险
    """
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


class DataQualityLevel(Enum):
    """数据质量等级"""
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
```

### 2.2 CPU 相关数据模型

```python
@dataclass(frozen=True)
class UserKernelStats:
    """用户态/内核态 CPU 统计
    
    Attributes:
        user_core_sec: 用户态核心秒数
        kernel_core_sec: 内核态核心秒数
        total_core_sec: 总核心秒数
        user_records: 用户态样本数
        kernel_records: 内核态样本数
    """
    user_core_sec: float = 0.0
    kernel_core_sec: float = 0.0
    total_core_sec: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass(frozen=True)
class CPUUtilization:
    """CPU 利用率（整体统计）
    
    Attributes:
        total_pct: 总利用率百分比 (0-100)
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        total_core_seconds: 总核心秒数
        user_core_seconds: 用户态核心秒数
        kernel_core_seconds: 内核态核心秒数
        duration: 采样持续时间（秒）
        user_records: 用户态样本数
        kernel_records: 内核态样本数
    """
    total_pct: float = 0.0
    user_pct: float = 0.0
    kernel_pct: float = 0.0
    total_core_seconds: float = 0.0
    user_core_seconds: float = 0.0
    kernel_core_seconds: float = 0.0
    duration: float = 0.0
    user_records: int = 0
    kernel_records: int = 0


@dataclass(frozen=True)
class CoreCPUInfo:
    """核心级 CPU 信息
    
    Attributes:
        cpu_id: CPU 核心 ID
        total_pct: 总利用率百分比
        kernel_pct: 内核态利用率百分比
        user_pct: 用户态利用率百分比
    """
    cpu_id: int
    total_pct: float
    kernel_pct: float
    user_pct: float = 0.0


@dataclass(frozen=True)
class ProcessCPUInfo:
    """进程级 CPU 信息
    
    Attributes:
        comm: 进程名
        pid: 进程 ID
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
    """
    comm: str
    pid: str
    total_pct: float
    user_pct: float
    kernel_pct: float


@dataclass(frozen=True)
class PidCPUInfo:
    """PID 级 CPU 信息（按 PID 聚合，合并相同 PID 的不同 comm）
    
    Attributes:
        pid: 进程 ID
        comm: 进程名（使用出现次数最多的 comm）
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        sample_count: 样本数
    """
    pid: int
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    sample_count: int = 0


@dataclass(frozen=True)
class CommCPUInfo:
    """进程组（comm）级 CPU 信息
    
    Attributes:
        comm: 进程组名
        total_pct: 总利用率百分比
        user_pct: 用户态利用率百分比
        kernel_pct: 内核态利用率百分比
        pid_count: 包含的 PID 数量
        pids: PID 集合
    """
    comm: str
    total_pct: float
    user_pct: float
    kernel_pct: float
    pid_count: int
    pids: Set[str] = field(default_factory=set)


@dataclass
class SymbolCPUInfo:
    """符号级 CPU 信息
    
    Attributes:
        self_pct: 各符号的自耗时百分比
        inclusive_pct: 各符号的包含耗时百分比
        core_sec: 各符号的核心秒数
        self_core_sec: 各符号的自耗时核心秒数
        total_core_sec: 总核心秒数
    """
    self_pct: Dict[str, float] = field(default_factory=dict)
    inclusive_pct: Dict[str, float] = field(default_factory=dict)
    core_sec: Dict[str, float] = field(default_factory=dict)
    self_core_sec: Dict[str, float] = field(default_factory=dict)
    total_core_sec: float = 0.0
```

### 2.3 样本数据模型

```python
@dataclass(frozen=True)
class Sample:
    """单个样本数据（替代裸 dict）
    
    这是 Core Layer 的基础数据单元，所有分析都基于此结构。
    
    Attributes:
        comm: 进程名
        pid: 进程 ID
        cpu: CPU 核心 ID
        ts: 时间戳（Unix timestamp）
        core_per_sec: 每秒核心数（可选，用于预计算数据）
        stack: 调用栈（SymbolStack 对象，可选）
    """
    comm: str
    pid: str
    cpu: int
    ts: float
    core_per_sec: Optional[float] = None
    stack: Optional[Any] = None  # SymbolStack 对象，延迟导入避免循环依赖


@dataclass(frozen=True)
class FilterCriteria:
    """样本过滤条件
    
    Attributes:
        start_time: 开始时间戳
        end_time: 结束时间戳
        cpu_id: CPU ID 过滤
        pid: PID 过滤
        comm: 进程名过滤（精确匹配）
        comm_regex: 进程名过滤（正则匹配）
    """
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    cpu_id: Optional[int] = None
    pid: Optional[int] = None
    comm: Optional[str] = None
    comm_regex: Optional[str] = None
```

### 2.4 进程生命周期数据模型

```python
@dataclass(frozen=True)
class LifecycleEvent:
    """进程生命周期事件
    
    Attributes:
        pid: 进程 ID
        comm: 进程名
        timestamp: 事件发生时间戳
        type: 事件类型 ("spawn" | "exit")
    """
    pid: str
    comm: str
    timestamp: float
    type: str  # "spawn" | "exit"


@dataclass(frozen=True)
class LifecycleStats:
    """生命周期统计
    
    Attributes:
        total_unique_pids: 唯一 PID 总数
        duration_sec: 观察持续时间
        avg_lifetime_sec: 平均生命周期（秒）
    """
    total_unique_pids: int = 0
    duration_sec: float = 0.0
    avg_lifetime_sec: float = 0.0


@dataclass
class ProcessLifecycle:
    """进程生命周期信息
    
    用于计算 Spawn Rate（进程产生速率），检测短生命周期风暴。
    
    Attributes:
        spawn_events: 进程创建事件列表
        exit_events: 进程退出事件列表
        spawn_rate: 进程产生速率（每秒）
        lifecycle_stats: 生命周期统计
    """
    spawn_events: List[LifecycleEvent] = field(default_factory=list)
    exit_events: List[LifecycleEvent] = field(default_factory=list)
    spawn_rate: float = 0.0
    lifecycle_stats: LifecycleStats = field(default_factory=LifecycleStats)
```

### 2.5 调用图数据模型

```python
@dataclass(frozen=True)
class CallerInfo:
    """调用者信息
    
    Attributes:
        symbol: 调用者符号名
        call_count: 调用次数
        total_weight: 总权重
        call_ratio: 调用比例
    """
    symbol: str
    call_count: int
    total_weight: float
    call_ratio: float = 0.0


@dataclass(frozen=True)
class CallEdge:
    """调用边信息
    
    Attributes:
        callee: 被调用者符号
        count: 调用次数
        weight: 权重
    """
    callee: str
    count: int
    weight: float


@dataclass
class CallGraph:
    """调用图
    
    Attributes:
        callers: 调用者列表
        call_graph: 调用图结构（调用者 -> 被调用者列表）
        hot_paths: 热点调用路径
    """
    callers: List[CallerInfo] = field(default_factory=list)
    call_graph: Dict[str, List[CallEdge]] = field(default_factory=dict)
    hot_paths: List[str] = field(default_factory=list)
```

### 2.6 Risk 相关数据模型

```python
@dataclass
class RiskInfo:
    """风险信息结构 - 所有输出的第一个字段
    
    遵循 output-format-spec.md 规范，风险置顶原则。
    
    Attributes:
        level: 风险等级 ("critical" | "warning" | "info" | "none")
        message: 风险描述信息
        hint: 建议操作或提示
        patterns: 匹配的 attention flags 列表 (X0, X1, X2, XA)
        pending_targets: 待处理目标列表
        action_required: 是否需要立即行动（自动计算）
    """
    level: str  # "critical" | "warning" | "info" | "none"
    message: str = ""
    hint: str = ""
    patterns: List[str] = field(default_factory=list)
    pending_targets: List[str] = field(default_factory=list)
    action_required: bool = False

    def __post_init__(self):
        """验证 level 并自动计算 action_required"""
        valid_levels = ["critical", "warning", "info", "none"]
        if self.level not in valid_levels:
            self.level = "info"
        self.action_required = self.level in ["critical", "warning"]


@dataclass(frozen=True)
class TimeRange:
    """时间范围结构 - ISO 8601 格式
    
    Attributes:
        start_time: 开始时间（ISO 8601 格式）
        end_time: 结束时间（ISO 8601 格式）
        duration: 持续时间（秒）
    """
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: float = 0.0

    @classmethod
    def from_timestamps(cls, start_ts: Optional[float], end_ts: Optional[float]) -> 'TimeRange':
        """从时间戳创建 TimeRange"""
        if start_ts is None or end_ts is None:
            return cls()
        return cls(
            start_time=datetime.fromtimestamp(start_ts).isoformat() if start_ts else None,
            end_time=datetime.fromtimestamp(end_ts).isoformat() if end_ts else None,
            duration=round(end_ts - start_ts, 2)
        )
```

### 2.7 质量评估数据模型

```python
@dataclass(frozen=True)
class QualityMetrics:
    """数据质量指标
    
    Attributes:
        total_samples: 总样本数
        time_range_seconds: 时间范围（秒）
        cpu_count: CPU 核心数
        level: 质量等级
        warning: 质量警告信息
    """
    total_samples: int = 0
    time_range_seconds: float = 0.0
    cpu_count: int = 0
    level: str = "unknown"
    warning: str = ""


@dataclass(frozen=True)
class DataQualityMetrics:
    """详细数据质量指标
    
    Attributes:
        record_count: 记录数
        duration_sec: 持续时间（秒）
        cpu_utilization_pct: CPU 利用率百分比
        utilization_source: 利用率来源
        total_weight: 总权重
        avg_weight: 平均权重
    """
    record_count: int = 0
    duration_sec: float = 0.0
    cpu_utilization_pct: float = 0.0
    utilization_source: str = "unknown"
    total_weight: Optional[float] = None
    avg_weight: Optional[float] = None
```

### 2.8 输出基础数据模型

```python
@dataclass
class BaseSummary:
    """基础摘要结构"""
    pass


@dataclass
class BaseOutput:
    """基础输出结构 - 所有输出的基类
    
    Attributes:
        _risk: 风险信息（必须作为第一个字段）
        summary: 摘要信息
        time_range: 时间范围
        _template_config: 模板配置（内部使用）
    """
    _risk: RiskInfo
    summary: Optional[BaseSummary] = None
    time_range: Optional[TimeRange] = None
    _template_config: Optional[Any] = None
```

---

## 3. Engine 接口定义

### 3.1 PerfExpertEngine 类

```python
class PerfExpertEngine:
    """性能数据引擎 - Core Layer 核心类
    
    职责：
    1. 数据加载与解析
    2. CPU 利用率计算（收拢所有利用率计算逻辑）
    3. 进程生命周期分析
    4. 调用图构建
    5. 符号解析
    
    约束：
    - 所有数据解析逻辑必须在此实现
    - Analysis Layer 禁止自行解析原始数据
    - 所有返回值必须是具体 dataclass 类型
    """

    def __init__(self, file_path: str, freq: int = 19):
        """初始化引擎
        
        Args:
            file_path: perf 数据文件路径
            freq: 采样频率（Hz），仅用于原始 perf 格式
        """
        pass

    # ========================================================================
    # 数据加载接口
    # ========================================================================

    def load_data(self, data_file: str) -> bool:
        """加载 perf 数据文件
        
        Args:
            data_file: 数据文件路径
            
        Returns:
            加载是否成功
        """
        pass

    def get_time_range(self) -> Tuple[float, float]:
        """获取数据时间范围
        
        Returns:
            (开始时间戳, 结束时间戳)
        """
        pass

    # ========================================================================
    # 样本查询接口
    # ========================================================================

    def get_filtered_samples(
        self,
        criteria: Optional[FilterCriteria] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        cpu_id: Optional[int] = None,
        pid: Optional[int] = None,
        comm: Optional[str] = None,
        comm_regex: Optional[str] = None
    ) -> List[Sample]:
        """获取过滤后的样本
        
        支持两种方式传递过滤条件：
        1. 通过 criteria 参数传递 FilterCriteria 对象
        2. 通过独立参数传递（优先级高于 criteria）
        
        Args:
            criteria: 过滤条件对象
            start_time: 开始时间戳
            end_time: 结束时间戳
            cpu_id: CPU ID
            pid: 进程 ID
            comm: 进程名（精确匹配）
            comm_regex: 进程名（正则匹配）
            
        Returns:
            符合条件的 Sample 列表
        """
        pass

    def get_all_samples(self) -> List[Sample]:
        """获取所有样本
        
        Returns:
            所有 Sample 列表
        """
        pass

    # ========================================================================
    # CPU 利用率接口（所有 CPU 计算收拢于此）
    # ========================================================================

    def get_cpu_utilization(self, samples: Optional[List[Sample]] = None) -> CPUUtilization:
        """获取整体 CPU 利用率
        
        Args:
            samples: 样本列表（默认使用所有样本）
            
        Returns:
            CPU 利用率统计
        """
        pass

    def get_comm_cpu_info(
        self,
        samples: Optional[List[Sample]] = None,
        min_cpu_pct: float = 0.0
    ) -> List[CommCPUInfo]:
        """获取进程组级 CPU 信息
        
        Args:
            samples: 样本列表（默认使用所有样本）
            min_cpu_pct: 最小 CPU 百分比过滤
            
        Returns:
            CommCPUInfo 列表（按总利用率降序）
        """
        pass

    def get_core_cpu_info(
        self,
        samples: Optional[List[Sample]] = None
    ) -> List[CoreCPUInfo]:
        """获取核心级 CPU 信息
        
        Args:
            samples: 样本列表（默认使用所有样本）
            
        Returns:
            CoreCPUInfo 列表（按 cpu_id 排序）
        """
        pass

    def get_pid_cpu_info(
        self,
        samples: Optional[List[Sample]] = None,
        min_cpu_pct: float = 0.0
    ) -> List[PidCPUInfo]:
        """获取 PID 级 CPU 信息
        
        Args:
            samples: 样本列表（默认使用所有样本）
            min_cpu_pct: 最小 CPU 百分比过滤
            
        Returns:
            PidCPUInfo 列表（按总利用率降序）
        """
        pass

    def get_process_cpu_info(
        self,
        samples: Optional[List[Sample]] = None
    ) -> List[ProcessCPUInfo]:
        """获取进程级 CPU 信息（comm + pid 组合）
        
        Args:
            samples: 样本列表（默认使用所有样本）
            
        Returns:
            ProcessCPUInfo 列表
        """
        pass

    # ========================================================================
    # 符号热点接口
    # ========================================================================

    def get_symbol_cpu_info(
        self,
        samples: Optional[List[Sample]] = None,
        comm: Optional[str] = None,
        pid: Optional[int] = None
    ) -> SymbolCPUInfo:
        """获取符号级 CPU 信息
        
        Args:
            samples: 样本列表（默认使用所有样本）
            comm: 按进程名过滤
            pid: 按 PID 过滤
            
        Returns:
            符号 CPU 信息
        """
        pass

    # ========================================================================
    # 进程生命周期接口
    # ========================================================================

    def get_process_lifecycle(
        self,
        samples: Optional[List[Sample]] = None,
        comm: Optional[str] = None
    ) -> ProcessLifecycle:
        """获取进程生命周期信息
        
        用于计算 Spawn Rate（进程产生速率），检测短生命周期风暴。
        
        Args:
            samples: 样本列表（默认使用所有样本）
            comm: 按进程名过滤
            
        Returns:
            进程生命周期信息
        """
        pass

    # ========================================================================
    # 调用图接口
    # ========================================================================

    def get_call_graph(
        self,
        target_symbol: str,
        samples: Optional[List[Sample]] = None,
        comm: Optional[str] = None,
        max_depth: int = 5
    ) -> CallGraph:
        """获取指定符号的调用图
        
        Args:
            target_symbol: 目标符号名
            samples: 样本列表（默认使用所有样本）
            comm: 按进程名过滤
            max_depth: 最大调用深度
            
        Returns:
            调用图信息
        """
        pass

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def get_total_core_per_sec(
        self,
        samples: Optional[List[Sample]] = None
    ) -> Tuple[float, int]:
        """获取总核心秒数和样本数
        
        Args:
            samples: 样本列表
            
        Returns:
            (总核心秒数, 样本数)
        """
        pass

    def assess_data_quality(
        self,
        samples: Optional[List[Sample]] = None
    ) -> Tuple[DataQualityLevel, str, DataQualityMetrics]:
        """评估数据质量
        
        Args:
            samples: 样本列表
            
        Returns:
            (质量等级, 警告信息, 详细指标)
        """
        pass
```

---

## 4. OutputBuilder 接口定义

### 4.1 OutputBuilder 类

```python
class OutputBuilder:
    """输出构建器 - 统一输出生成
    
    职责：
    1. 数据质量评估
    2. 输出格式化
    3. Trace 自动记录
    4. Risk 自动提取和记录
    
    使用方式：
        builder = OutputBuilder(engine, args)
        builder.begin_command("get-comm-top")
        
        # ... 分析逻辑 ...
        
        output = CommTopOutput(
            _risk=risk_info,
            processes=process_items,
            summary=summary
        )
        builder.print_output(output)
    """

    def __init__(
        self,
        engine: PerfExpertEngine,
        args: Any,
        compact: bool = False,
        text_mode: bool = True
    ):
        """初始化输出构建器
        
        Args:
            engine: PerfExpertEngine 实例
            args: argparse namespace 或配置对象
            compact: 是否使用紧凑模式输出
            text_mode: 是否使用人类可读的文本格式输出
        """
        pass

    # ========================================================================
    # 命令生命周期管理
    # ========================================================================

    def begin_command(self, command_name: str) -> None:
        """命令开始时调用，自动初始化 Trace 并记录命令
        
        Args:
            command_name: 命令名称，如 "get-comm-top"
        """
        pass

    def end_command(self) -> None:
        """命令结束时调用，保存 Trace"""
        pass

    # ========================================================================
    # Trace 记录接口
    # ========================================================================

    def record_risk(
        self,
        level: str,
        desc: str,
        hint: str = ""
    ) -> str:
        """记录发现的风险，自动创建 issue
        
        Args:
            level: critical/warning/info
            desc: 风险描述
            hint: 建议操作
            
        Returns:
            创建的 issue ID（或空字符串）
        """
        pass

    def record_resolution(
        self,
        issue_id: str,
        result: str
    ) -> None:
        """标记 issue 已解决
        
        Args:
            issue_id: 要解决的 issue ID
            result: 分析结果/结论
        """
        pass

    def record_info(self, message: str) -> None:
        """记录一般信息
        
        Args:
            message: 信息内容
        """
        pass

    def get_trace_summary(self) -> TraceSummary:
        """获取 Trace 摘要
        
        Returns:
            Trace 摘要信息
        """
        pass

    # ========================================================================
    # 数据质量评估
    # ========================================================================

    def assess_quality(
        self,
        samples: Optional[List[Sample]] = None,
        early_return: bool = False
    ) -> Optional[QualityMetrics]:
        """评估数据质量
        
        Args:
            samples: 样本列表
            early_return: 是否在质量不足时提前返回
            
        Returns:
            质量指标（如果 early_return=False 且质量不足可能返回 None）
        """
        pass

    def check_empty_samples(
        self,
        samples: List[Sample],
        filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """检查样本是否为空，如果为空则输出错误并返回 True
        
        Args:
            samples: 样本列表
            filters: 过滤条件（用于错误信息）
            
        Returns:
            是否为空样本
        """
        pass

    # ========================================================================
    # 输出接口
    # ========================================================================

    def print_output(
        self,
        output: BaseOutput,
        auto_end: bool = True
    ) -> None:
        """打印输出对象
        
        自动从 output 中提取 risk 信息并记录到 Trace。
        
        Args:
            output: 继承自 BaseOutput 的输出对象
            auto_end: 是否自动结束命令记录
        """
        pass

    def print_json(self, data: Dict[str, Any]) -> None:
        """打印字典数据（兼容 V1）
        
        Args:
            data: 要输出的字典
        """
        pass

    def to_dict(self, output: BaseOutput) -> Dict[str, Any]:
        """将输出对象转换为字典
        
        Args:
            output: 输出对象
            
        Returns:
            字典表示
        """
        pass
```

---

## 5. 辅助接口

### 5.1 Trace 接口

```python
class Trace:
    """诊断过程追踪
    
    职责：记录诊断命令执行过程、发现的问题和解决方案。
    由 OutputBuilder 内部使用，一般不直接调用。
    """

    def init(self, data_file: str) -> None:
        """初始化 Trace 文档"""
        pass

    def begin_command(self, command: str) -> None:
        """记录命令开始"""
        pass

    def end_command(self) -> None:
        """记录命令结束"""
        pass

    def record_risk(
        self,
        level: str,
        desc: str,
        hint: str = ""
    ) -> str:
        """记录风险"""
        pass

    def record_resolution(
        self,
        issue_id: str,
        result: str
    ) -> None:
        """记录解决方案"""
        pass
```

### 5.2 Symbol 接口

```python
@dataclass(frozen=True)
class Symbol:
    """符号信息
    
    Attributes:
        name: 符号名
        module: 所属模块
        is_kernel: 是否为内核符号
    """
    name: str
    module: Optional[str] = None
    is_kernel: bool = False

    @staticmethod
    def _strip_offset(symbol_str: str) -> str:
        """去除符号名中的偏移量"""
        pass


@dataclass
class SymbolStack:
    """调用栈
    
    Attributes:
        symbols: 符号列表（从底到顶）
        kernel_depth: 内核栈深度
    """
    symbols: List[Symbol] = field(default_factory=list)
    kernel_depth: int = 0
```

---

## 6. 使用示例

### 6.1 基本使用流程

```python
from perf_toolkit.core.engine import PerfExpertEngine
from perf_toolkit.core.output_builder import OutputBuilder
from perf_toolkit.core.output_models import (
    RiskInfo, CommGroupItem, CommGroupSummary, CommTopOutput,
    TimeRange
)

# 1. 初始化 Engine
engine = PerfExpertEngine("perf.data")

# 2. 初始化 OutputBuilder
args = type('Args', (), {'data': 'perf.data', 'trace': True})()
builder = OutputBuilder(engine, args)
builder.begin_command("get-comm-top")

# 3. 获取样本
samples = engine.get_all_samples()

# 4. 检查数据质量
if builder.check_empty_samples(samples):
    return

# 5. 执行分析
comm_info_list = engine.get_comm_cpu_info(samples, min_cpu_pct=0.1)

# 6. 构建输出
comm_groups = [
    CommGroupItem.from_stats(
        comm=info.comm,
        pid_count=info.pid_count,
        aggregate_cpu=info.total_pct,
        kernel_ratio=info.kernel_pct
    )
    for info in comm_info_list
]

risk = RiskInfo(
    level="info",
    message="分析完成",
    patterns=["ANALYSIS_COMPLETE"]
)

summary = CommGroupSummary(
    total_comm_groups=len(comm_groups),
    high_kernel_groups=sum(1 for g in comm_groups if float(g.kernel.rstrip('%')) > 50)
)

output = CommTopOutput(
    _risk=risk,
    comm_groups=comm_groups,
    summary=summary,
    time_range=TimeRange.from_timestamps(
        samples[0].ts if samples else None,
        samples[-1].ts if samples else None
    )
)

# 7. 输出结果
builder.print_output(output)
```

### 6.2 使用 FilterCriteria

```python
from perf_toolkit.core.engine import FilterCriteria

# 构建过滤条件
criteria = FilterCriteria(
    start_time=1705312200.0,
    end_time=1705312300.0,
    comm="nginx",
    cpu_id=0
)

# 获取过滤后的样本
samples = engine.get_filtered_samples(criteria=criteria)

# 或使用独立参数
samples = engine.get_filtered_samples(
    start_time=1705312200.0,
    end_time=1705312300.0,
    comm="nginx"
)
```

### 6.3 获取调用图

```python
# 获取指定符号的调用图
call_graph = engine.get_call_graph(
    target_symbol="mutex_lock",
    samples=samples,
    comm="my_app",
    max_depth=3
)

# 遍历调用者
for caller in call_graph.callers:
    print(f"{caller.symbol}: {caller.call_count} calls, {caller.call_ratio:.2%}")

# 遍历调用边
for caller_symbol, edges in call_graph.call_graph.items():
    for edge in edges:
        print(f"{caller_symbol} -> {edge.callee}: {edge.count}")
```

---

## 7. 接口演进历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-02 | 初始版本，使用裸 dict 传递数据 |
| v2.0 | 2026-03 | 引入 dataclass 强类型接口，定义 Core Layer 边界 |

---

## 8. 相关文档

- [三层架构设计](design-three-tier-architecture.md) - 整体架构设计
- [输出格式规范](output-format-spec.md) - 输出格式详细规范
- [SHECR 方法论](../references/methodology.md) - 分析方法论
