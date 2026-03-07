# 三层架构设计文档：Core - Analysis - Composite

> 创建时间: 2026-03-02  
> 更新日期: 2026-03-03
> 设计目标: 解决工具冗余、trace污染、职责边界不清问题
> 
> **本次更新**: 整合命令瘦身结论（6个分析工具 + 2个组合命令 + 4个环境命令 + 9个trace子命令）

---

## 1. 背景与问题

### 1.1 当前架构

```
三层架构实现:
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: CLI Layer (cli/)                                  │
│  ├─ commands/analysis/  (6个分析命令)                       │
│  ├─ commands/composite/ (2个组合命令)                       │
│  ├─ commands/trace/     (9个trace子命令)                    │
│  └─ commands/env/       (4个环境命令)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Composite (composite/*.py)                        │
│  ├─ sys_audit.py         (sys-audit 命令)                  │
│  └─ bottleneck_analyze.py  (bottleneck-analyze 命令)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Analysis (analysis/*.py)                          │
│  ├─ facade.py            (对外接口封装)                     │
│  ├─ hotspots.py          (get-hotspots)                     │
│  ├─ comm_top.py          (get-comm-top)                     │
│  ├─ anomalies.py         (detect-anomalies)                 │
│  ├─ core_distribution.py (analyze-core-distribution)        │
│  ├─ path_clusters.py     (cluster-paths)                    │
│  └─ trace.py             (find-callers)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Core (core/*.py)                                  │
│  ├─ engine.py            (PerfExpertEngine)                 │
│  ├─ output_builder.py    (输出构建器)                       │
│  ├─ trace.py             (诊断过程追踪)                     │
│  ├─ output_models.py     (数据模型)                         │
│  └─ engine_types.py      (类型定义)                         │
└─────────────────────────────────────────────────────────────┘
```

**解决的问题**:

1. **职责边界清晰**: Core负责数据，Analysis负责分析，Composite负责编排，CLI负责命令接口
2. **Trace隔离**: Composite调用Analysis内部接口时，不触发Trace记录
3. **分层接口**: 通过AnalysisFacade暴露干净接口供Composite调用
4. **可测试性**: 每层可独立测试，Mock下层依赖

### 1.2 命令结构

**实际命令清单**（共21个命令/子命令）：

| 类别 | 数量 | 命令 |
|------|------|------|
| **环境命令** | 4 | `init`, `use`, `list`, `status` |
| **分析命令** | 6 | `get-hotspots`, `find-callers`, `detect-anomalies`, `cluster-paths`, `analyze-core-distribution`, `get-comm-top` |
| **组合命令** | 2 | `sys-audit`, `bottleneck-analyze` |
| **Trace子命令** | 9 | `init`, `add`, `timeline`, `issues`, `audit`, `complete`, `reopen`, `finalize`, `export` |

**6个核心分析工具**：

| 层级 | 工具 | 职责 |
|------|------|------|
| 系统级 | `analyze-core-distribution` | 核心热力图、单核饱和、中断不均 |
| 时间级 | `detect-anomalies` | 趋势突变检测 |
| 实体级 | `get-comm-top` | 进程组聚合 + 离群检测(CV) |
| 函数级 | `get-hotspots` | 热点函数识别 |
| 关系级 | `find-callers` | 调用链溯源 |
| 模式级 | `cluster-paths` | 业务逻辑路径聚类 |

**2个组合命令**（解决"高噪音掩盖真问题"）：

| 组合命令 | 链式触发 | 用途 |
|----------|----------|------|
| `sys-audit` | anomalies → core-dist → comm-top | 系统全景扫描，自动降噪 |
| `bottleneck-analyze` | comm-top → hotspots → cluster-paths | 瓶颈深度分析 |

### 1.3 具体场景

```python
# 问题场景：sys-audit 组合命令
@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    # 1. 调用 detect-anomalies
    result1 = call_command("detect-anomalies")  # 被记录到trace
    
    # 2. 调用 analyze-core-distribution  
    result2 = call_command("analyze-core-distribution")  # 被记录到trace
    
    # 3. 调用 get-comm-top
    result3 = call_command("get-comm-top")  # 被记录到trace
    
    # timeline 中会出现：
    # - sys-audit
    # - detect-anomalies  
    # - analyze-core-distribution
    # - get-comm-top
    # 用户看到的是混乱的嵌套记录
```

---

## 2. 设计目标

### 2.1 核心目标

| 目标 | 描述 |
|------|------|
| **职责分离** | Core负责数据，Analysis负责分析，Composite负责编排 |
| **接口清晰** | 每层通过明确定义的API交互，禁止跨层直接访问 |
| **Trace隔离** | Composite调用Analysis内部接口时，不触发Trace记录 |
| **可测试性** | 每层可独立测试，Mock下层依赖 |

### 2.2 架构原则

```
┌─────────────────────────────────────────────────────────────┐
│                     三层架构原则                              │
├─────────────────────────────────────────────────────────────┤
│  1. 向下依赖：每层只能调用直接下层的接口                        │
│  2. 接口封装：下层能力通过Facade模式暴露                        │
│  3. Trace边界：Composite层统一记录，Analysis内部调用不记录       │
│  4. 数据流动：Core → Analysis → Composite（单向）              │
│  5. 自动降噪：高Count+低CPU的进程组默认折叠                     │
│  6. 异常优先：输出按危害指数排序，非绝对CPU值                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 关键指标设计

为解决"A（高Count亮眼数字）掩盖B（真瓶颈）"问题，引入以下核心指标：

| 指标 | 名称 | 用途 | 阈值建议 |
|------|------|------|----------|
| **CV** | 变异系数 (Coefficient of Variation) | 识别组内离群进程 | CV > 1.0 为异常 |
| **Monopoly** | 核心独占率 | 识别单核瓶颈 | Monopoly > 0.8 为高危 |
| **Spawn Rate** | 进程产生速率 | 检测短生命周期风暴 | > 10/s 为风暴 |
| **Impact Score** | 危害指数 | 综合排序依据 | 按此值降序排列 |

**Impact Score计算公式**：
```
Impact = (CPU% × 0.3) + (CV × 40) + (Monopoly × 50) + (Mutation_Rate × 30)
```

- 高Count低CPU的进程：Impact得分低，自动折叠
- 低Count高Monopoly的进程：Impact得分高，强制置顶

---

## 3. 架构设计

### 3.1 目标架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: CLI (命令层)                                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ cli/commands/                                           ││
│  │   ├── analysis/       (6个分析命令)                     ││
│  │   │   ├── get_hotspots.py                               ││
│  │   │   ├── find_callers.py                               ││
│  │   │   ├── detect_anomalies.py                           ││
│  │   │   ├── cluster_paths.py                              ││
│  │   │   ├── analyze_core_distribution.py                  ││
│  │   │   └── get_comm_top.py                               ││
│  │   ├── composite/      (2个组合命令)                     ││
│  │   │   ├── sys_audit.py                                  ││
│  │   │   └── bottleneck_analyze.py                         ││
│  │   ├── env/            (4个环境命令)                     ││
│  │   │   ├── init.py, use.py, list.py, status.py           ││
│  │   └── trace/          (9个trace子命令)                  ││
│  │       ├── init.py, add.py, timeline.py, ...             ││
│  └─────────────────────────────────────────────────────────┘│
│  职责: 命令行接口，处理用户输入和输出格式化                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 调用 Composite / Analysis
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Composite (组合层)                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ composite/                                              ││
│  │   ├── sys_audit.py      (sys-audit 命令)               ││
│  │   ├── bottleneck_analyze.py (bottleneck-analyze 命令)  ││
│  │   └── risk_aggregator.py (Risk聚合)                    ││
│  └─────────────────────────────────────────────────────────┘│
│  职责: 编排多个analysis工具，生成综合诊断报告                   │
│  Trace: 记录顶层命令，不记录内部analysis调用                   │
│  核心能力: 自动降噪、危害排序、A/B分离（解决亮眼数字掩盖问题）   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 调用 Analysis Facade（不触发Trace）
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Analysis (分析层)                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ analysis/                                               ││
│  │   ├── facade.py         (AnalysisFacade)               ││
│  │   ├── base.py           (分析器基类)                   ││
│  │   ├── interfaces.py     (分析接口)                     ││
│  │   ├── models.py         (分析数据模型)                 ││
│  │   ├── hotspots.py       (get-hotspots 实现)            ││
│  │   ├── comm_top.py       (get-comm-top 实现)            ││
│  │   ├── anomalies.py      (detect-anomalies 实现)        ││
│  │   ├── core_distribution.py (analyze-core-distribution) ││
│  │   ├── path_clusters.py  (cluster-paths 实现)           ││
│  │   └── trace.py          (find-callers 实现)            ││
│  └─────────────────────────────────────────────────────────┘│
│  职责: 实现具体诊断逻辑，提供CLI和内部两种接口                  │
│  约束: 所有数据解析必须从core.engine获取                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 调用 Core Engine
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Core (核心层)                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ core/                                                   ││
│  │   ├── engine.py         (PerfExpertEngine)             ││
│  │   ├── output_builder.py (OutputBuilder)                ││
│  │   ├── trace.py          (诊断过程追踪)                 ││
│  │   ├── output_models.py  (数据模型)                     ││
│  │   └── engine_types.py   (类型定义)                     ││
│  └─────────────────────────────────────────────────────────┘│
│  职责: 数据解析、Trace记录、基础输出能力                       │
│  约束: 不依赖上层，提供纯粹的基础能力                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 关键设计决策

#### 决策1: Analysis Facade 模式

```python
# analysis/facade.py
"""
Analysis Facade - 对外暴露的干净接口

供 Composite 层调用，不触发 Trace 记录
"""
from typing import List, Dict, Optional, Any
from ..core.engine import PerfExpertEngine

class AnalysisFacade:
    """分析层外观类，封装所有analysis工具的内部实现"""
    
    def __init__(self, engine: PerfExpertEngine):
        self.engine = engine
        # 初始化各分析模块（内部实现类，非命令包装）
        from . import comm_top, hotspots, anomalies, core_distribution
        self._comm_top_impl = comm_top.CommTopAnalyzer(engine)
        self._hotspots_impl = hotspots.HotspotsAnalyzer(engine)
        self._anomalies_impl = anomalies.AnomaliesAnalyzer(engine)
        self._core_dist_impl = core_distribution.CoreDistAnalyzer(engine)
    
    # ========== 供 Composite 调用的内部接口（不触发Trace） ==========
    
    def analyze_comm_top(self, 
                         samples: List[Dict], 
                         top_n: int = 10,
                         enable_trace: bool = False) -> Dict:
        """
        分析进程组CPU排行（内部接口 - 增强版）
        
        整合能力:
        - 原 get-process-top: 通过CV/Monopoly识别单进程异常
        - 原 cluster-comm: 按进程名聚合
        - 原 count-process-variety: 通过Spawn Rate检测进程风暴
        
        Args:
            samples: 样本数据（由core.engine提供）
            top_n: 返回前N个（已过滤掉背景噪音）
            enable_trace: 是否记录到trace（Composite调用时应为False）
        
        Returns:
            CommTop分析结果（原始dict，非Output模型）
        """
        return self._comm_top_impl.analyze(samples, top_n=top_n)
    
    def analyze_hotspots(self,
                         samples: List[Dict],
                         comm: Optional[str] = None,
                         pid: Optional[int] = None,
                         top_n: int = 20,
                         enable_trace: bool = False) -> Dict:
        """分析热点函数（内部接口）"""
        return self._hotspots_impl.analyze(samples, comm=comm, pid=pid, top_n=top_n)
    
    def analyze_core_distribution(self,
                                   samples: List[Dict],
                                   enable_trace: bool = False) -> Dict:
        """分析核心级负载分布（内部接口）"""
        return self._core_dist_impl.analyze(samples)
    
    def detect_anomalies(self,
                         samples: List[Dict],
                         window_size: int = 10,
                         threshold: float = 2.0,
                         enable_trace: bool = False) -> Dict:
        """检测时序异常（内部接口）"""
        return self._anomalies_impl.analyze(samples, window_size, threshold)


# ========== CLI 命令包装（触发Trace） ==========

@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """CLI命令入口 - 会触发Trace记录"""
    facade = AnalysisFacade(engine)
    result = facade.analyze_comm_top(
        samples, 
        top_n=getattr(args, 'top_n', 10),
        enable_trace=True  # CLI调用时记录Trace
    )
    # 转换为Output模型并输出...
```

#### 决策2: 双接口设计（CLI vs Internal）

```python
# analysis/comm_top.py

class CommTopAnalyzer:
    """
    CommTop分析器 - 纯逻辑实现，不处理CLI和Trace
    
    整合原 get-process-top + cluster-comm + count-process-variety 能力
    
    设计原则:
    1. 只依赖core.engine获取数据
    2. 不直接操作trace
    3. 自动降噪：折叠高Count+低CPU的"平庸"组
    4. 智能排序：按Impact Score而非单纯CPU%
    5. 返回原始dict，由上层决定如何包装
    """
    
    def __init__(self, engine: PerfExpertEngine):
        self.engine = engine
    
    def analyze(self, samples: List[Dict], top_n: int = 10) -> Dict:
        """
        核心分析逻辑（内部接口 - 增强版）
        
        Returns:
            {
                "groups": [...],          # 进程组列表（已过滤噪音）
                "cv_analysis": {...},     # 变异系数分析
                "monopoly_scores": {...}, # 核心独占率分析
                "spawn_rates": {...},     # 进程产生速率分析
                "folded_groups": [...],   # 被折叠的"平庸"组
                "recommendations": [...]  # 诊断建议
            }
        """
        # 1. 从engine获取数据
        comm_util = self.engine.get_comm_cpu_util(samples)
        
        # 2. 计算增强指标（CV、Monopoly、SpawnRate）
        analysis_result = self._calculate_metrics(comm_util, samples)
        
        # 3. 自动降噪：分离"关键组"和"背景组"
        critical_groups, folded_groups = self._noise_reduction(analysis_result)
        
        # 4. 按Impact Score排序
        critical_groups.sort(key=lambda x: x["impact_score"], reverse=True)
        
        # 5. 生成诊断建议
        recommendations = self._generate_recommendations(critical_groups)
        
        return {
            "groups": critical_groups[:top_n],
            "folded_groups": folded_groups,
            "cv_analysis": analysis_result["cv_map"],
            "monopoly_scores": analysis_result["monopoly_map"],
            "spawn_rates": analysis_result["spawn_rate_map"],
            "recommendations": recommendations
        }
    
    def _calculate_metrics(self, comm_util: Dict, samples: List[Dict]) -> Dict:
        """
        计算CV、Monopoly、SpawnRate等增强指标
        
        CV (变异系数): 识别组内离群进程
        Monopoly (核心独占率): 识别单核瓶颈
        Spawn Rate: 检测短生命周期风暴
        """
        # ... 实现逻辑 ...
        pass
    
    def _noise_reduction(self, analysis: Dict) -> Tuple[List[Dict], List[Dict]]:
        """
        自动降噪：分离关键组和背景组
        
        折叠条件:
        1. Count > 100 且 Total_CPU < 5% （高Count低CPU）
        2. CV < 0.1 且 Monopoly < 0.1 （分布均匀无离群）
        """
        # ... 实现逻辑 ...
        pass
    
    def _generate_recommendations(self, groups: List[Dict]) -> List[Dict]:
        """
        基于分析结果生成建议
        
        识别类型:
        - BOTTLENECK: 高Monopoly单点瓶颈
        - UNBALANCED: 高CV组内离群
        - STORM: 高Spawn Rate进程风暴
        - HEALTHY: 正常负载
        """
        # ... 实现逻辑 ...
        pass


# CLI命令包装（在文件底部或单独文件）
@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """CLI入口 - 使用Analyzer并处理输出和Trace"""
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(samples, top_n=getattr(args, 'top_n', 10))
    
    # 转换为Output模型
    output = CommTopOutput(...)
    
    # 自动记录risk（通过builder）
    if result["recommendations"]:
        for rec in result["recommendations"]:
            builder.record_risk("warning", rec["message"], rec["hint"])
    
    return output
```

#### 决策3: Composite层实现

```python
# composite/sys_audit.py

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """
    系统审计组合命令
    
    编排逻辑:
    1. detect-anomalies → 发现突变时刻
    2. analyze-core-distribution → 分析核心分布
    3. get-comm-top → 分析进程组
    4. 综合分析，生成诊断报告
    """
    from ..analysis.facade import AnalysisFacade
    from ..core.output_models import SysAuditOutput
    
    # 创建facade（内部调用，不触发Trace）
    facade = AnalysisFacade(engine)
    
    # 执行多个分析（不记录到Trace）
    anomalies = facade.detect_anomalies(samples, enable_trace=False)
    core_dist = facade.analyze_core_distribution(samples, enable_trace=False)
    comm_top = facade.analyze_comm_top(samples, top_n=10, enable_trace=False)
    
    # 综合分析结果
    diagnosis = _synthesize_diagnosis(anomalies, core_dist, comm_top)
    
    # 记录到Trace（只记录sys-audit整体，不记录子调用）
    if diagnosis["primary_suspect"]:
        builder.record_risk(
            "critical",
            f"主要嫌疑人: {diagnosis['primary_suspect']['comm']}",
            diagnosis['primary_suspect']['suggestion']
        )
    
    # 构建综合输出
    output = SysAuditOutput(
        anomalies=anomalies,
        core_distribution=core_dist,
        comm_top=comm_top,
        diagnosis=diagnosis
    )
    
    return output


def _synthesize_diagnosis(anomalies: Dict, core_dist: Dict, comm_top: Dict) -> Dict:
    """
    综合分析结果，识别真正的瓶颈
    
    解决A掩盖B问题的核心逻辑:
    1. 检查CV和Monopoly指标
    2. 按危害指数而非绝对CPU排序
    3. 区分"背景负载"和"性能瓶颈"
    """
    # ... 实现逻辑 ...
    pass
```

---

## 4. 接口规范

### 4.1 Core层接口（数据层）

```python
# core/engine.py

class PerfExpertEngine:
    """
    数据引擎 - 唯一数据源
    
    约束: 所有数据解析逻辑必须在此实现，analysis层禁止自行解析
    """
    
    # ========== 数据加载 ==========
    def load_data(self, data_file: str) -> bool:
        """加载perf数据文件"""
        pass
    
    # ========== 基础查询接口 ==========
    def get_filtered_samples(self, 
                             start_time: Optional[float] = None,
                             end_time: Optional[float] = None,
                             cpu_id: Optional[int] = None,
                             pid: Optional[int] = None,
                             comm: Optional[str] = None,
                             comm_regex: Optional[str] = None) -> List[Dict]:
        """获取过滤后的样本"""
        pass
    
    def get_time_range(self) -> Tuple[float, float]:
        """获取数据时间范围"""
        pass
    
    # ========== CPU利用率接口（收拢于此） ==========
    def get_comm_cpu_util(self, samples: List[Dict]) -> Dict[str, Dict]:
        """
        获取进程组级CPU利用率
        
        Returns:
            {
                "comm_name": {
                    "total_pct": float,      # 总CPU%
                    "kernel_pct": float,     # 内核态CPU%
                    "user_pct": float,       # 用户态CPU%
                    "pid_count": int,        # 进程数
                    "pids": List[int]        # PID列表
                }
            }
        """
        pass
    
    def get_pid_cpu_util(self, samples: List[Dict]) -> Dict[int, Dict]:
        """获取进程级CPU利用率"""
        pass
    
    def get_core_cpu_util(self, samples: List[Dict]) -> Dict[int, Dict]:
        """获取核心级CPU利用率"""
        pass
    
    def get_symbol_hotspots(self, 
                            samples: List[Dict],
                            comm: Optional[str] = None,
                            pid: Optional[int] = None) -> Dict[str, Dict]:
        """获取符号热点"""
        pass
    
    # ========== 进程生命周期接口（新增） ==========
    def get_process_lifecycle(self, 
                              samples: List[Dict],
                              comm: Optional[str] = None) -> Dict:
        """
        获取进程生命周期信息
        
        用于计算Spawn Rate（进程产生速率），检测短生命周期风暴
        
        Returns:
            {
                "spawn_events": List[Dict],  # 进程创建事件
                "exit_events": List[Dict],   # 进程退出事件
                "spawn_rate": float          # 产生速率（每秒）
            }
        """
        pass
    
    # ========== 调用链接口 ==========
    def get_call_graph(self,
                       samples: List[Dict],
                       target_symbol: str,
                       comm: Optional[str] = None) -> Dict:
        """获取指定符号的调用图"""
        pass
```

### 4.2 Analysis层接口（内部API）

```python
# analysis/facade.py

class AnalysisFacade:
    """
    Analysis Facade - 对外暴露的干净接口
    
    供Composite层调用，不触发Trace记录
    """
    
    def __init__(self, engine: PerfExpertEngine):
        self.engine = engine
    
    # ========== Comm分析 ==========
    def analyze_comm_top(self,
                         samples: List[Dict],
                         top_n: int = 10) -> Dict:
        """
        进程组CPU分析（增强版 - 三合一）
        
        整合原 get-process-top + cluster-comm + count-process-variety 能力：
        - 纵向聚合：按进程名分组（原cluster-comm）
        - 横向离群：CV方差分析识别异常PID（原get-process-top）
        - 时间动态：Spawn Rate检测进程风暴（原count-process-variety）
        
        Returns:
            {
                "groups": [{
                    "comm": str,
                    "total_cpu": float,
                    "count": int,
                    "cv": float,              # 变异系数
                    "monopoly": float,        # 核心独占率
                    "spawn_rate": float,      # 产生速率
                    "outlier_pid": Optional[int],
                    "impact_score": float,    # 危害指数
                    "diagnosis": str          # HEALTHY/UNBALANCED/BOTTLENECK/STORM
                }],
                "folded_groups": [{          # 被折叠的"平庸"组
                    "comm": str,
                    "reason": str             # "low_cpu_high_count" | "uniform_distribution"
                }],
                "folded_count": int,
                "total_groups": int
            }
        """
        pass
    
    # ========== 热点分析 ==========
    def analyze_hotspots(self,
                         samples: List[Dict],
                         comm: Optional[str] = None,
                         pid: Optional[int] = None,
                         top_n: int = 20) -> Dict:
        """
        热点函数分析
        
        Returns:
            {
                "hotspots": [{
                    "symbol": str,
                    "cpu_percent": float,
                    "call_count": int,
                    "resource_tag": str       # LOCK_CONTENTION/SYSCALL/...
                }],
                "kernel_ratio": float,
                "user_ratio": float
            }
        """
        pass
    
    # ========== 核心分布分析 ==========
    def analyze_core_distribution(self,
                                   samples: List[Dict]) -> Dict:
        """
        核心级负载分布分析
        
        Returns:
            {
                "core_stats": [{
                    "core_id": int,
                    "total_cpu": float,
                    "user_cpu": float,
                    "kernel_cpu": float,
                    "softirq_cpu": float
                }],
                "imbalance_score": float,     # 不均衡分数
                "saturated_cores": List[int]   # 饱和核心列表
            }
        """
        pass
    
    # ========== 异常检测 ==========
    def detect_anomalies(self,
                         samples: List[Dict],
                         window_size: int = 10,
                         threshold: float = 2.0) -> Dict:
        """
        时序异常检测
        
        Returns:
            {
                "anomalies": [{
                    "timestamp": float,
                    "cpu_spike": float,
                    "deviation": float
                }],
                "baseline": float,
                "mutation_detected": bool
            }
        """
        pass
    
    # ========== 溯源分析 ==========
    def analyze_callers(self,
                        samples: List[Dict],
                        target_symbol: str,
                        comm: Optional[str] = None) -> Dict:
        """
        调用链溯源
        
        Returns:
            {
                "callers": [{
                    "symbol": str,
                    "call_count": int,
                    "call_ratio": float
                }],
                "call_graph": Dict
            }
        """
        pass
    
    # ========== 路径聚类 ==========
    def cluster_paths(self,
                      samples: List[Dict],
                      comm: Optional[str] = None) -> Dict:
        """
        调用路径聚类
        
        Returns:
            {
                "clusters": [{
                    "path_prefix": str,
                    "business_module": str,   # Logging/Network/GC/...
                    "cpu_contribution": float
                }]
            }
        """
        pass
```

### 4.3 Composite层接口（组合命令）

```python
# composite/interfaces.py

"""
Composite层接口定义

组合命令通过编排多个analysis工具，生成综合诊断报告
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class DiagnosisReport:
    """综合诊断报告"""
    primary_suspect: Optional[Dict]      # 主要嫌疑人
    secondary_loads: List[Dict]          # 次要负载
    background_noise: List[Dict]         # 背景噪音
    root_cause_chain: str                # 根因链描述
    recommendations: List[str]           # 操作建议


class CompositeAnalyzer:
    """
    组合分析器基类
    
    子类实现具体的组合诊断逻辑
    """
    
    def __init__(self, facade: AnalysisFacade):
        self.facade = facade
    
    def analyze(self, samples: List[Dict]) -> DiagnosisReport:
        """执行组合分析"""
        raise NotImplementedError


# 具体实现示例
class SysAuditAnalyzer(CompositeAnalyzer):
    """系统审计分析器"""
    
    def analyze(self, samples: List[Dict]) -> DiagnosisReport:
        # 1. 获取各维度分析结果
        anomalies = self.facade.detect_anomalies(samples)
        core_dist = self.facade.analyze_core_distribution(samples)
        comm_top = self.facade.analyze_comm_top(samples, top_n=20)
        
        # 2. 综合判断
        return self._synthesize(anomalies, core_dist, comm_top)
    
    def _synthesize(self, anomalies, core_dist, comm_top) -> DiagnosisReport:
        """综合分析结果"""
        # ... 实现 ...
        pass


class BottleneckTraceAnalyzer(CompositeAnalyzer):
    """瓶颈追踪分析器"""
    
    def analyze(self, 
                samples: List[Dict],
                target_comm: Optional[str] = None) -> DiagnosisReport:
        # 1. 找到瓶颈进程
        comm_top = self.facade.analyze_comm_top(samples)
        bottleneck = self._find_bottleneck(comm_top)
        
        if not bottleneck:
            return DiagnosisReport(
                primary_suspect=None,
                recommendations=["未检测到明显瓶颈"]
            )
        
        # 2. 深度分析
        hotspots = self.facade.analyze_hotspots(
            samples, 
            comm=bottleneck["comm"]
        )
        
        # 3. 生成报告
        return self._build_report(bottleneck, hotspots)
```

---

## 5. 数据流与Trace边界

### 5.1 正常CLI调用（记录Trace）

```
用户执行: shecr get-comm-top --data xxx.data

数据流:
┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│ CLI层   │───▶│ command装饰器 │───▶│ cmd_get_    │───▶│ CommTop  │
│         │    │ (begin_command│    │ comm_top    │    │ Analyzer │
└─────────┘    │ 记录Trace)   │    └──────┬──────┘    └────┬─────┘
               └──────────────┘           │                │
                                          ▼                ▼
                                    ┌──────────┐    ┌──────────┐
                                    │ Analysis │───▶│ Core     │
                                    │ Facade   │    │ Engine   │
                                    └──────────┘    └──────────┘
                                          │
                                          ▼
                                    ┌──────────┐
                                    │ Output   │
                                    │ Builder  │
                                    │ (print_  │
                                    │  output) │
                                    └──────────┘

Trace记录:
- timeline[0]: command="get-comm-top --data xxx.data"
- 如发现risk: issues[ISS-001] = {...}
```

### 5.2 Composite调用（不记录子Trace）

```
用户执行: shecr sys-audit --data xxx.data

数据流:
┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ CLI层   │───▶│ command装饰器 │───▶│ cmd_sys_    │───▶│ Analysis     │
│         │    │ (begin_command│    │ audit       │    │ Facade       │
└─────────┘    │ 记录Trace)   │    │             │    │ (enable_trace│
               └──────────────┘    │             │    │  =False)     │
                                   └──────┬──────┘    └──────┬───────┘
                                          │                    │
                                          │    ┌───────────────┼───────────┐
                                          │    ▼               ▼           ▼
                                          │ ┌────────┐    ┌────────┐   ┌────────┐
                                          │ │ detect │    │analyze │   │get-comm│
                                          │ │anomalies│   │core-dist   │-top    │
                                          │ └───┬────┘    └───┬────┘   └───┬────┘
                                          │     │             │            │
                                          │     └─────────────┴─────┬──────┘
                                          │                         ▼
                                          │                   ┌──────────┐
                                          │                   │ Core     │
                                          │                   │ Engine   │
                                          │                   └──────────┘
                                          ▼
                                    ┌──────────┐
                                    │ Output   │
                                    │ Builder  │
                                    │ (print_  │
                                    │  output) │
                                    └──────────┘

Trace记录:
- timeline[0]: command="sys-audit --data xxx.data"（只记录顶层）
- 内部调用的detect-anomalies/analyze-core-distribution/get-comm-top不记录
- 如发现risk: issues[ISS-001] = {...}
```

---

## 6. Composite命令详细设计

### 6.1 sys-audit（系统审计）

**目标**: 快速扫描系统全景，自动识别"真瓶颈"vs"背景噪音"

**链式触发**: `detect-anomalies` → `analyze-core-distribution` → `get-comm-top`

**输出示例**:
```
[系统审计报告]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 异常发现
   系统CPU在10:05突变+80%，Core #7单核饱和

2. 嫌疑人排序（按Impact Score）
   ┌─────────────┬────────┬───────┬───────────┬─────────────┐
   │ COMM        │ CPU%   │ Count │ Monopoly  │ Diagnosis   │
   ├─────────────┼────────┼───────┼───────────┼─────────────┤
   │ app_worker  │ 12%    │ 10    │ 0.92!!    │ BOTTLENECK  │ ← 真凶B
   │ lsof        │ 400%   │ 2000  │ 0.05      │ HIGH_VOLUME │ ← 亮眼A
   └─────────────┴────────┴───────┴───────────┴─────────────┘

3. 背景噪音（已折叠）
   24个组（含log-agent x 2000）| 总CPU: 15% | 状态: Quiet

4. 建议操作
   [CRITICAL] app_worker独占Core #7，建议执行: bottleneck-analyze --comm app_worker
```

### 6.2 bottleneck-analyze（瓶颈分析）

**目标**: 深度分析被识别出的瓶颈进程

**链式触发**: `get-comm-top` → `get-hotspots` → `cluster-paths`

**自动触发条件**: 
- `sys-audit`中发现Monopoly > 0.8的进程
- 用户手动指定`--comm`参数

**输出示例**:
```
[瓶颈追踪报告: app_worker]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 进程画像
   COMM: app_worker | PID: 5829 | Core: #7 | CPU: 98%

2. 热点函数（Top 5）
   ┌─────────────────────┬────────┬─────────────┐
   │ Symbol              │ CPU%   │ ResourceTag │
   ├─────────────────────┼────────┼─────────────┤
   │ spinlock_wait       │ 85%    │ LOCK_CONT   │
   │ memory_reclaim      │ 10%    │ MEMORY      │
   └─────────────────────┴────────┴─────────────┘

3. 调用路径聚类
   业务模块: Database_Query → Lock_Contention
   根因: 高频查询触发锁竞争

4. 建议操作
   [优化建议] 检查数据库查询逻辑，减少全局锁持有时间
```



## 7. 实施计划

### Phase 1: Core层完善（1周）

- [ ] 收拢所有数据解析逻辑到`core/engine.py`
- [ ] 新增`get_process_lifecycle()`接口（支持Spawn Rate计算）
- [ ] 新增`get_call_graph()`接口
- [ ] 删除/合并旧接口：`get_pid_cpu_util()`整合进`get_comm_cpu_util()`
- [ ] 确保analysis层无法直接访问原始数据文件

### Phase 2: Analysis层重构（2周）

- [ ] 创建`analysis/facade.py`，定义`AnalysisFacade`类
- [ ] 重构现有analysis工具，提取纯逻辑到`XXXAnalyzer`类
  - [ ] `comm_top.py` → `CommTopAnalyzer`（整合get-process-top + cluster-comm + count-process-variety）
  - [ ] `hotspots.py` → `HotspotsAnalyzer`
  - [ ] `core_distribution.py` → `CoreDistAnalyzer`（整合check-cpu-bottleneck + show-cpu-usage）
  - [ ] `anomalies.py` → `AnomaliesAnalyzer`
  - [ ] `clusters.py` → 合并到`path_clusters.py`或独立保留
- [ ] 删除冗余工具文件
- [ ] CLI命令改为调用`Analyzer`并处理输出/Trace
- [ ] 确保所有数据访问通过`engine`接口

### Phase 3: Composite层实现（1周）

- [ ] 创建`composite/`目录
- [ ] 实现`composite/sys_audit.py`（自动降噪 + 危害排序）
- [ ] 实现`composite/bottleneck_analyze.py`（Monopoly驱动深度分析）

- [ ] 注册composite命令到CLI
- [ ] 实现自动触发逻辑（sys-audit发现异常自动建议后续命令）

### Phase 4: Enhanced get-comm-top（1周）

- [ ] 在`CommTopAnalyzer`中实现CV计算（变异系数）
- [ ] 实现Monopoly计算（核心独占率）
- [ ] 实现SpawnRate计算（进程产生速率）
- [ ] 实现Impact Score危害指数评分
- [ ] 实现自动降噪逻辑（折叠高Count+低CPU组）
- [ ] 实现智能排序（按Impact Score而非CPU%）

### Phase 5: 测试与文档（1周）

- [ ] 编写单元测试（各层独立测试）
- [ ] 集成测试（验证Trace边界）
- [ ] 降噪逻辑测试（验证高Count低CPU组被正确折叠）
- [ ] Impact Score排序测试（验证B优先于A）
- [ ] 更新SKILL.md和references/tools.md
- [ ] 更新AGENTS.md中的工具清单

---

## 8. 关键代码变更示例

### 7.1 Analysis层重构示例

```python
# 重构前 (analysis/comm_top.py)
@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    comm_util = engine.get_comm_cpu_util(samples)
    # ... 直接在这里实现所有逻辑 ...
    return output


# 重构后 (analysis/comm_top.py)
class CommTopAnalyzer:
    """纯分析逻辑，与CLI解耦"""
    
    def __init__(self, engine: PerfExpertEngine):
        self.engine = engine
    
    def analyze(self, samples: List[Dict], top_n: int = 10) -> Dict:
        """内部接口，返回原始数据"""
        comm_util = self.engine.get_comm_cpu_util(samples)
        # ... 分析逻辑 ...
        return {
            "groups": groups,
            "cv_analysis": cv_map,
            "monopoly_scores": monopoly_map,
            # ...
        }


@command("get-comm-top")
def cmd_get_comm_top(builder, engine, args, samples):
    """CLI包装，处理输出和Trace"""
    analyzer = CommTopAnalyzer(engine)
    result = analyzer.analyze(samples, top_n=getattr(args, 'top_n', 10))
    
    # 转换为Output模型
    output = CommTopOutput(...)
    
    # 记录risk到Trace
    for rec in result["recommendations"]:
        builder.record_risk(rec["level"], rec["message"], rec["hint"])
    
    return output
```

### 7.2 Facade接口实现

```python
# analysis/facade.py

class AnalysisFacade:
    """对外暴露的干净接口"""
    
    def __init__(self, engine: PerfExpertEngine):
        self.engine = engine
        # 延迟初始化analyzer实例
        self._analyzers = {}
    
    def _get_analyzer(self, name: str):
        """延迟获取analyzer实例"""
        if name not in self._analyzers:
            if name == "comm_top":
                from .comm_top import CommTopAnalyzer
                self._analyzers[name] = CommTopAnalyzer(self.engine)
            elif name == "hotspots":
                from .hotspots import HotspotsAnalyzer
                self._analyzers[name] = HotspotsAnalyzer(self.engine)
            # ...
        return self._analyzers[name]
    
    def analyze_comm_top(self, samples: List[Dict], top_n: int = 10) -> Dict:
        """供Composite调用的内部接口"""
        analyzer = self._get_analyzer("comm_top")
        return analyzer.analyze(samples, top_n=top_n)
    
    def analyze_hotspots(self, 
                         samples: List[Dict],
                         comm: Optional[str] = None,
                         pid: Optional[int] = None,
                         top_n: int = 20) -> Dict:
        analyzer = self._get_analyzer("hotspots")
        return analyzer.analyze(samples, comm=comm, pid=pid, top_n=top_n)
    
    # ... 其他接口 ...
```

### 7.3 Composite命令实现

```python
# composite/sys_audit.py

from ..core.command_decorator import command
from ..analysis.facade import AnalysisFacade
from ..core.output_models import SysAuditOutput, RiskInfo

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    """系统审计组合命令"""
    
    # 使用Facade调用analysis工具（不触发Trace）
    facade = AnalysisFacade(engine)
    
    # 并行执行多个分析
    anomalies = facade.detect_anomalies(samples)
    core_dist = facade.analyze_core_distribution(samples)
    comm_top = facade.analyze_comm_top(samples, top_n=20)
    
    # 综合分析
    diagnosis = _synthesize(anomalies, core_dist, comm_top)
    
    # 只记录综合诊断结果到Trace
    if diagnosis["primary_suspect"]:
        builder.record_risk(
            "critical",
            f"发现主要性能瓶颈: {diagnosis['primary_suspect']['comm']}",
            f"执行 bottleneck-analyze --comm {diagnosis['primary_suspect']['comm']} 深入分析"
        )
    
    # 构建输出
    output = SysAuditOutput(
        _risk=RiskInfo(...),
        diagnosis=diagnosis,
        details={
            "anomalies": anomalies,
            "core_distribution": core_dist,
            "comm_top": comm_top
        }
    )
    
    return output


def _synthesize(anomalies, core_dist, comm_top) -> Dict:
    """
    综合分析结果，识别真正瓶颈
    
    核心逻辑（解决A掩盖B问题）：
    1. 按Impact Score排序，非单纯CPU%
    2. 高Monopoly进程强制置顶（即使CPU总量低）
    3. 高CV组标识为UNBALANCED
    4. 高Spawn Rate组标识为STORM
    """
    candidates = []
    for group in comm_top["groups"]:
        # Impact Score综合计算
        impact_score = (
            group["total_cpu"] * 0.3 +
            group["cv"] * 40 +
            group["monopoly"] * 50 +
            group.get("mutation_rate", 0) * 30
        )
        candidates.append({
            **group,
            "impact_score": impact_score
        })
    
    # 按危害指数降序排列
    candidates.sort(key=lambda x: x["impact_score"], reverse=True)
    
    # 分类输出
    primary = candidates[0] if candidates else None
    secondary = candidates[1:3] if len(candidates) > 1 else []
    
    return {
        "primary_suspect": primary,           # 主要嫌疑人（真瓶颈B）
        "secondary_loads": secondary,         # 次要负载（高Count的A）
        "background_noise": comm_top["folded_groups"],  # 折叠的背景噪音
        "root_cause_chain": _build_cause_chain(primary, anomalies, core_dist)
    }
```

---

## 9. 验证与测试

### 8.1 测试策略

| 测试类型 | 测试目标 | 测试方法 |
|----------|----------|----------|
| 单元测试 | 各Analyzer逻辑正确性 | Mock engine接口 |
| 集成测试 | Facade接口调用链 | 使用真实测试数据 |
| Trace测试 | 验证Trace边界 | 检查timeline记录 |
| 端到端测试 | Composite命令完整流程 | 完整数据文件测试 |

### 8.2 Trace边界验证

```python
# 测试用例: test_trace_boundary.py

def test_composite_does_not_pollute_timeline():
    """验证Composite调用不污染timeline"""
    
    # 1. 执行 composite 命令
    run_command("sys-audit --data test.data")
    
    # 2. 读取 trace 文件
    trace = load_trace(".shecr.json")
    
    # 3. 验证只记录了顶层命令
    assert len(trace["timeline"]) == 1
    assert trace["timeline"][0]["command"].startswith("sys-audit")
    
    # 4. 验证没有记录子命令
    commands = [t["command"] for t in trace["timeline"]]
    assert "get-comm-top" not in " ".join(commands)
    assert "detect-anomalies" not in " ".join(commands)


def test_cli_records_to_timeline():
    """验证CLI命令正确记录到timeline"""
    
    # 1. 执行单个 analysis 命令
    run_command("get-comm-top --data test.data")
    
    # 2. 读取 trace 文件
    trace = load_trace(".shecr.json")
    
    # 3. 验证记录了该命令
    assert len(trace["timeline"]) == 1
    assert "get-comm-top" in trace["timeline"][0]["command"]
```

---

## 10. 总结

### 10.1 关键设计点回顾

1. **四层架构**: Core（数据）→ Analysis（分析）→ Composite（编排）→ CLI（命令接口）
   - 6个分析命令: get-hotspots, find-callers, detect-anomalies, cluster-paths, analyze-core-distribution, get-comm-top
   - 2个组合命令: sys-audit, bottleneck-analyze
   - 4个环境命令: init, use, list, status
   - 9个trace子命令: init, add, timeline, issues, audit, complete, reopen, finalize, export

2. **Facade模式**: Analysis层通过Facade暴露内部接口，供Composite调用

3. **双接口设计**: 每个analysis工具提供CLI接口（记录Trace）和内部接口（不记录）

4. **数据边界**: 所有数据解析必须在Core层完成，Analysis层禁止自行解析

5. **自动降噪**: 通过CV/Monopoly/Impact Score识别并折叠背景噪音

6. **危害排序**: 按Impact Score排序，解决"A（亮眼数字）掩盖B（真瓶颈）"问题

### 10.2 收益

| 收益 | 说明 |
|------|------|
| **职责清晰** | Core(数据) → Analysis(分析) → Composite(编排) → CLI(接口)，每层只关注自己的核心职责 |
| **降噪能力** | 自动折叠高Count低CPU的背景进程，聚焦真问题 |
| **智能排序** | Impact Score算法确保真瓶颈优先展示 |
| **可测试** | 每层可独立Mock和测试 |
| **Trace干净** | Composite调用不污染诊断记录 |
| **可扩展** | 新增组合命令无需修改底层工具 |

### 10.3 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 重构范围大 | 分Phase实施，保持CLI兼容；先实现新功能再删除旧工具 |
| 降噪误判 | 提供`--show-all`参数强制展示所有组；可配置降噪阈值 |
| 算法调参 | CV/Monopoly/Impact权重提供配置文件调整 |
| 性能开销 | Facade延迟初始化analyzer |
| 学习成本 | 完善文档和示例代码；提供迁移指南 |
