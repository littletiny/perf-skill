#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default Configuration - 全项目默认常量配置

所有输出相关的常量、阈值、枚举值统一在此定义，避免分散硬编码。
使用方式:
    from config.defaults import OutputDefaults, DiagnosisType, RiskPattern
    
    if diagnosis == DiagnosisType.BOTTLENECK:
        print(OutputDefaults.BOTTLENECK_ANALYZE_TITLE)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# SHECR Attention Flags
# =============================================================================

class AttentionFlag:
    """SHECR Attention Flags - 用于标记信息优先级"""
    X0 = "<X0>"   # 阻塞级 (Critical/Blocker)
    X1 = "<X1>"   # 重要级 (High/Major)
    X2 = "<X2>"   # 提示级 (Medium/Minor)
    XA = "<XA>"   # 操作建议 (Action)


# =============================================================================
# Diagnosis Types - 诊断类型常量
# =============================================================================

class DiagnosisType:
    """进程诊断类型"""
    BOTTLENECK = "BOTTLENECK"       # 单进程瓶颈
    STORM = "STORM"                 # 进程风暴
    UNBALANCED = "UNBALANCED"       # 负载不均衡
    NORMAL = "NORMAL"               # 正常
    HEALTHY = "HEALTHY"             # 健康


class PressureState:
    """系统压力状态"""
    NORMAL = "NORMAL"                           # 正常
    MODERATE_CONTENTION = "MODERATE_CONTENTION" # 中度竞争
    CRITICAL_CONTENTION = "CRITICAL_CONTENTION" # 严重竞争


class SeverityLevel:
    """严重级别"""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImbalanceLevel:
    """负载不均衡级别"""
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class ContextSwitchRate:
    """上下文切换速率评估"""
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


# =============================================================================
# Expert Anchor Types - 专家锚点类型
# =============================================================================

class ExpertAnchorType:
    """专家锚点类型"""
    NOISY_NEIGHBOR = "NOISY_NEIGHBOR"   # 噪音邻居
    QUOTA_VICTIM = "QUOTA_VICTIM"       # Quota 受害者


# =============================================================================
# Risk Patterns - Risk 模式标识
# =============================================================================

class RiskPattern:
    """Risk 模式标识常量"""
    # 数据质量问题
    NO_SAMPLES = "NO_SAMPLES"
    CRITICAL_DATA_QUALITY = "CRITICAL_DATA_QUALITY"
    
    # 主要嫌疑人
    PRIMARY_SUSPECT = "PRIMARY_SUSPECT"
    
    # 内核相关
    HIGH_KERNEL = "HIGH_KERNEL"
    HIGH_KERNEL_HOTSPOT = "HIGH_KERNEL_HOTSPOT"
    
    # 竞争相关
    LOCK_CONTENTION = "LOCK_CONTENTION"
    PROCESS_STORM = "PROCESS_STORM"
    UNBALANCED_LOAD = "UNBALANCED_LOAD"
    SINGLE_CORE_SATURATION = "SINGLE_CORE_SATURATION"
    
    # 目标活动
    LOW_TARGET_ACTIVITY = "LOW_TARGET_ACTIVITY"


# =============================================================================
# Output Display Constants - 输出显示常量
# =============================================================================

@dataclass(frozen=True)
class OutputDefaults:
    """输出显示默认值"""
    
    # -------------------------------------------------------------------------
    # 通用占位符
    # -------------------------------------------------------------------------
    NA = "N/A"
    ROOT = "(root)"
    NO_DATA = "No data found"
    
    # -------------------------------------------------------------------------
    # Composite 输出标题
    # -------------------------------------------------------------------------
    BOTTLENECK_ANALYZE_TITLE = "## [BOTTLENECK_ANALYZE]"
    SYS_AUDIT_TITLE = "## [SYSTEM_AUDIT]"
    
    # -------------------------------------------------------------------------
    # Bottleneck Trace Section Headers
    # -------------------------------------------------------------------------
    BOTTLENECK_PROFILE_HEADER = "### 瓶颈特征 (Bottleneck Profile)"
    HOTSPOTS_HEADER = "### 热点函数 (Hotspots)"
    HOTSPOTS_SORT_HINT = "> 排序: 按 Self CPU 占比"
    CALL_CHAIN_HEADER = "### 调用链溯源 (Call Chain Analysis)"
    CALL_CHAIN_TARGET_PREFIX = "> 目标:"
    ROOT_CAUSE_HEADER = "### 根因分析 (Root Cause)"
    RECOMMENDATIONS_HEADER = "建议操作:"
    
    # -------------------------------------------------------------------------
    # SysAudit Section Headers
    # -------------------------------------------------------------------------
    SYS_FINGERPRINT_HEADER = "### 系统指纹 (System Fingerprint)"
    CONTENTION_MATRIX_HEADER = "### 竞争矩阵 (Contention Matrix)"
    PROCESS_HIERARCHY_HEADER = "### 进程分层 (Process Hierarchy)"
    CORE_DISTRIBUTION_HEADER = "### 核心分布 (Core Distribution)"
    ANOMALY_DETECTION_HEADER = "### 异常检测 (Anomaly Detection)"
    EXPERT_ANCHORS_HEADER = "### 专家锚点 (Expert Anchors)"
    ROOT_CAUSE_CHAIN_HEADER = "### 根因链 (Root Cause Chain)"
    
    # -------------------------------------------------------------------------
    # 状态标签
    # -------------------------------------------------------------------------
    PRIMARY_SUSPECT_LABEL = "Primary Suspect (真瓶颈)"
    SECONDARY_LOADS_LABEL = "Secondary Loads (次要负载)"
    BACKGROUND_NOISE_LABEL = "Background Noise (背景噪音)"
    
    # -------------------------------------------------------------------------
    # 评估标签
    # -------------------------------------------------------------------------
    ASSESSMENT_SATURATED = "单核饱和"
    ASSESSMENT_HIGH_KERNEL = "高内核态"
    ASSESSMENT_SINGLE_CORE_EXCLUSIVE = "单核独占"
    ASSESSMENT_UNBALANCED = "不均衡"
    
    # -------------------------------------------------------------------------
    # 图表字符
    # -------------------------------------------------------------------------
    TABLE_CORNER_TL = "┌"
    TABLE_CORNER_TR = "┐"
    TABLE_CORNER_BL = "└"
    TABLE_CORNER_BR = "┘"
    TABLE_HLINE = "─"
    TABLE_VLINE = "│"
    TABLE_CROSS = "┼"
    TABLE_T_DOWN = "┬"
    TABLE_T_UP = "┴"
    TABLE_T_RIGHT = "├"
    TABLE_T_LEFT = "┤"
    
    TREE_BRANCH = "├─"
    TREE_END = "└─"
    
    # -------------------------------------------------------------------------
    # 截断提示
    # -------------------------------------------------------------------------
    TRUNCATION_HINT = "# ... {count} more items (use --top-n to show more)"


# =============================================================================
# Display Presets - 显示预设常量
# =============================================================================

@dataclass(frozen=True)
class DisplayPresets:
    """显示预设默认值"""
    
    # Headers
    HOTSPOTS_HEADER = "# index,funcname,self,inclusive"
    PROCESSES_HEADER = "# comm(pid) (usr+sys)/sys"
    COMM_GROUPS_HEADER = "# comm,pids,cpu_util,event"
    SYMBOL_CLUSTERS_HEADER = "# event_type | pct_of_total (cluster_weight / total_weight)"
    PATH_CLUSTERS_HEADER = "# index,percent,cpu_util,path"
    ATTRIBUTIONS_HEADER = "# index,ratio,callstack"
    TRACES_HEADER = "# target (cpu_util) <- callstack | 热点标记 **[sym]** | 聚合热点 **(sym..)** | 普通聚合 (sym..) | 折叠 .."
    CALLCHAINS_HEADER = "### [CALLCHAINS] 热点函数调用链 | 热点标记 **[sym]** | 聚合栈热点 **(sym..)** | 聚合概念 (sym..) | 折叠 .."
    CORES_HEADER = "# SATURATED_CORES: index,cpu_id,(usr+sys)/sys"
    PROCESS_VARIETY_HEADER = "# PROCESS_STORM: comm,pids_per_min,cpu_util"
    ANOMALIES_HEADER = "# type,cpu_id,time_range,change,severity"
    WINDOWS_HEADER = "# cpu_id,start_time,end_time,util,weight"
    
    # Empty Messages
    NO_HOTSPOTS = "No hotspots found"
    NO_PROCESSES = "No processes found"
    NO_COMM_GROUPS = "No process groups found"
    NO_SYMBOL_CLUSTERS = "No symbol clusters found"
    NO_PATH_CLUSTERS = "No path clusters found"
    NO_ATTRIBUTIONS = "No attributions found"
    NO_TRACES = "No traces found"
    NO_CORES = "No saturated cores found"
    NO_PROCESS_VARIETY = "No process variety data"
    NO_ANOMALIES = "No anomalies detected"
    NO_WINDOWS = "No windows data"


# =============================================================================
# Thresholds - 分析阈值
# =============================================================================

@dataclass(frozen=True)
class Thresholds:
    """分析阈值常量"""
    
    # -------------------------------------------------------------------------
    # Bottleneck Detection Thresholds
    # -------------------------------------------------------------------------
    MONOPOLY_HIGH = 0.8             # 高 Monopoly 阈值
    MONOPOLY_CRITICAL = 0.9         # 严重 Monopoly 阈值
    
    CV_UNBALANCED = 1.0             # 不均衡 CV 阈值
    CV_HIGH = 2.0                   # 高 CV 阈值
    
    IMPACT_SCORE_LOW = 10.0         # 低影响分数
    IMPACT_SCORE_MEDIUM = 20.0      # 中等影响分数
    IMPACT_SCORE_HIGH = 50.0        # 高影响分数
    
    # -------------------------------------------------------------------------
    # CPU Utilization Thresholds
    # -------------------------------------------------------------------------
    CPU_UTIL_LOW = 30.0             # 低 CPU 利用率
    CPU_UTIL_MEDIUM = 50.0          # 中等 CPU 利用率
    CPU_UTIL_HIGH = 80.0            # 高 CPU 利用率
    CPU_UTIL_CRITICAL = 100.0       # 严重 CPU 利用率
    CPU_UTIL_EXTREME = 1000.0       # 极高 CPU 利用率 (多核累加)
    
    # -------------------------------------------------------------------------
    # Kernel Ratio Thresholds
    # -------------------------------------------------------------------------
    KERNEL_RATIO_HIGH = 50.0        # 高内核态比例
    KERNEL_RATIO_CRITICAL = 70.0    # 严重内核态比例
    
    # -------------------------------------------------------------------------
    # Core Distribution Thresholds
    # -------------------------------------------------------------------------
    IMBALANCE_RATIO_CRITICAL = 10.0  # 极不均衡比例
    CORE_SATURATED_THRESHOLD = 50.0  # 核心饱和阈值
    
    # -------------------------------------------------------------------------
    # CPU Overview Display Thresholds
    # -------------------------------------------------------------------------
    CPU_OVERVIEW_MIN_UTIL = 40.0     # CPU Overview 最小显示阈值 (低于此值不展示)
    
    # -------------------------------------------------------------------------
    # Z-Score Thresholds (Anomaly Detection)
    # -------------------------------------------------------------------------
    Z_SCORE_MEDIUM = 2.0            # 中等异常 Z-Score
    Z_SCORE_HIGH = 2.5              # 高异常 Z-Score
    
    # -------------------------------------------------------------------------
    # Core Affinity & Throttle Detection
    # -------------------------------------------------------------------------
    CV_AFFINITY_UNIFORM = 0.5       # Core Affinity: Uniform 阈值
    CV_UNBALANCED_LOAD = 1.5        # UNBALANCED_LOAD flag 阈值
    AFFINITY_FIXED_CPU_MIN = 90.0   # Fixed 需要 CPU > 90%
    AFFINITY_THROTTLE_INFER_CPU_MAX = 90.0  # 节流推断: CPU < 90
    
    # -------------------------------------------------------------------------
    # Correlation Flags 阈值 (bottleneck-analyze)
    # -------------------------------------------------------------------------
    LOCK_CONTENTION_INCLUSIVE_PCT = 40.0    # GLOBAL_LOCK_CONTENTION 阈值
    THROTTLE_VICTIM_CPU_MAX = 80.0          # THROTTLE_VICTIM: CPU < 80
    THROTTLE_RATE_MIN = 50.0                # 节流率 > 50%
    STORM_SPAWN_RATE = 100.0                # STORM_PATTERN 产生速率阈值


# =============================================================================
# Event Configuration - 事件命名和格式统一配置
# =============================================================================

@dataclass(frozen=True)
class EventConfig:
    """Event 配置 - 统一事件命名和格式"""
    
    # Event 类型标识
    BOTTLENECK_MARKER = "M"           # Monopoly 标记
    STORM_MARKER = "RATE"             # Spawn rate 标记  
    UNBALANCED_MARKER = "CV"          # CV 标记
    
    # Event 格式模板
    BOTTLENECK_FORMAT = "{type}({marker}={value:.4f})"
    STORM_FORMAT = "{type}({value:.1f}/s)"
    UNBALANCED_FORMAT = "{type}({marker}={value:.4f})"
    NORMAL_FORMAT = "normal"
    
    # Event 检测配置
    STORM_RATE_THRESHOLD = 100.0      # 风暴速率阈值 (/s)
    STORM_RATE_DISPLAY_UNIT = "/s"    # 显示单位


# =============================================================================
# Diagnosis Thresholds - 诊断阈值配置
# =============================================================================

@dataclass(frozen=True)
class DiagnosisThresholds:
    """诊断阈值配置"""
    
    # Monopoly 诊断
    BOTTLENECK_MONOPOLY_MIN = 0.8
    
    # Storm 诊断  
    STORM_RATE_MIN = 100.0            # 与 EventConfig.STORM_RATE_THRESHOLD 一致
    STORM_PID_COUNT_MIN = 1000        # 进程数阈值
    
    # Unbalanced 诊断
    UNBALANCED_CV_MIN = 1.0


# =============================================================================
# String Constants - 字符串常量统一配置
# =============================================================================

@dataclass(frozen=True)
class StringConstants:
    """字符串常量 - 避免代码中硬编码字符串"""
    
    # ==========================================================================
    # Core Affinity 值
    # ==========================================================================
    AFFINITY_FIXED = "Fixed"
    AFFINITY_UNIFORM = "Uniform"
    AFFINITY_SCATTERED = "Scattered"
    
    # ==========================================================================
    # Path Characteristic 值
    # ==========================================================================
    CHAR_COMPUTE = "COMPUTE"
    CHAR_LOCK_CONTENTION = "Lock_Contention"
    CHAR_IO_WAIT = "IO_Wait_Dominant"
    CHAR_SYSCALL_BOUND = "Syscall_Bound"
    CHAR_LATENCY_VICTIM = "Inclusive_Latency_Victim"
    CHAR_HIGH_FREQ_CPU = "High_Frequency_Exclusive_CPU"
    
    # ==========================================================================
    # 符号检测关键词 (小写，用于 in 检查)
    # ==========================================================================
    LOCK_KEYWORDS = ["lock", "mutex", "spin", "rwsem"]
    IO_KEYWORDS = ["io_schedule"]
    SYSCALL_KEYWORDS = ["syscall", "sys_", "entry_syscall"]
    
    # ==========================================================================
    # 全局锁符号列表
    # ==========================================================================
    GLOBAL_LOCK_SYMBOLS = [
        "_raw_spin_lock",
        "mutex_lock", 
        "rwsem_down_read",
        "spin_lock",
        "queue_spin_lock"
    ]


# =============================================================================
# Risk Display Configuration
# =============================================================================

@dataclass(frozen=True)
class RiskDisplayDefaults:
    """Risk 显示默认配置"""
    
    # Colors (ANSI escape codes)
    COLOR_CRITICAL = "\033[91m"
    COLOR_WARNING = "\033[93m"
    COLOR_INFO = "\033[94m"
    COLOR_RESET = "\033[0m"
    
    # Templates
    TEMPLATE_ISSUE_OPEN = "[OPEN] [{id}] [{level}] {desc}"
    TEMPLATE_ISSUE_RESOLVED = "[RESOLVED] [{id}] [{level}] {desc}"
    TEMPLATE_HINT = "→ {hint}"
    TEMPLATE_RESULT = "→ {result}"
    TEMPLATE_LIST_HEADER_OPEN = "[OPEN] {count} issues pending"
    TEMPLATE_LIST_HEADER_RESOLVED = "[RESOLVED] {count} issues"
    TEMPLATE_LIST_HEADER_ALL = "[ALL] {open_count} open, {resolved_count} resolved"
    TEMPLATE_TIMELINE_COMMAND = "[{seq}] {time} {command}"
    TEMPLATE_TIMELINE_FINDING_CREATED = "[{level}] {issue_id}: {desc}"
    TEMPLATE_TIMELINE_FINDING_RESOLVED = "[RESOLVED] {issue_id}: {result}"
    TEMPLATE_TIMELINE_INFO = "[INFO] {message}"
    
    # Risk Level Labels
    RISK_CRITICAL_LABEL = "[RISK-CRITICAL]"
    RISK_WARNING_LABEL = "[RISK-WARNING]"
    RISK_INFO_LABEL = "[RISK-INFO]"


# =============================================================================
# Composite Analysis Defaults
# =============================================================================

@dataclass(frozen=True)
class CompositeDefaults:
    """Composite 分析默认值"""
    
    # Bottleneck Trace
    DEFAULT_TOP_N = 10
    DEFAULT_TOP_HOTSPOTS = 5
    DEFAULT_TOP_CALLERS = 3
    
    # Sys Audit
    DEFAULT_SYS_AUDIT_TOP_N = 20
    DEFAULT_SECONDARY_LOADS_LIMIT = 3
    DEFAULT_EXPERT_ANCHORS_LIMIT = 2
    DEFAULT_SATURATED_CORES_LIMIT = 5
    
    # CPU Quota Assumption (for contention calculation)
    DEFAULT_CPU_QUOTA_LIMIT = 200.0  # 假设 2 cores


# =============================================================================
# Sampling Defaults
# =============================================================================

@dataclass(frozen=True)
class SamplingDefaults:
    """采样默认值"""
    DEFAULT_FREQ = 19               # 默认采样频率 (Hz)
    DEFAULT_WINDOW_SIZE = 1.0       # 默认窗口大小 (秒)
    DEFAULT_SPIKE_THRESHOLD = 0.5   # 默认突变阈值
    DEFAULT_MIN_UTILIZATION = 0.3   # 默认最小利用率


# =============================================================================
# CallChain Format Configuration
# =============================================================================

@dataclass(frozen=True)
class CallChainFormat:
    """CallChain 输出格式配置"""
    
    # 分隔符
    SEPARATOR_TOP_DOWN = " → "      # 正向: 入口 → 热点
    SEPARATOR_BOTTOM_UP = " <- "     # 反向: 热点 <- 入口
    
    # 标记
    CODE_MARKER = "`"                 # 代码标记: `function`
    
    # 热点标记: **[sym]**
    HOTSPOT_PREFIX = "**["
    HOTSPOT_SUFFIX = "]**"
    
    # 聚合标记: (sym..)
    AGGREGATED_PREFIX = "("
    AGGREGATED_SUFFIX = "..)"
    
    # 聚合且热点标记: **(sym..)**
    AGG_HOTSPOT_PREFIX = "**("
    AGG_HOTSPOT_SUFFIX = "..)**"
    
    # 默认格式模板
    TEMPLATE_SIMPLE = "{path}"                                    # 纯路径
    TEMPLATE_WITH_RATIO = "[{ratio}] {path}"                     # 带比例
    TEMPLATE_WITH_HOTSPOT = "{path} -> {hotspot_marker}"         # 带热点
    
    # 样式预设
    STYLE_DEFAULT = "default"         # 标准格式
    STYLE_MARKDOWN = "markdown"       # Markdown 格式 (带 ` 标记)
    STYLE_PLAIN = "plain"             # 纯文本 (无标记)


# =============================================================================
# Kernel Penetration Configuration - 内核穿透配置
# =============================================================================

class KernelPenetrationConfig:
    """内核穿透分析配置"""
    
    # 需要穿透分析的内核函数白名单
    KERNEL_PENETRATION_TARGETS = [
        'finish_task_switch',
        '__schedule',
        'schedule',
        'switch_mm_irqs_off',
        'native_safe_halt',
        'do_nanosleep',
        'hrtimer_nanosleep',
    ]
    
    # 调用链提取配置
    CALLCHAIN_EXTRACTION = {
        'default_max_depth': 10,
        'kernel_penetration_max_depth': 15,
        'min_kernel_layers': 3,
    }


# =============================================================================
# Symbol Rules Configuration - 符号处理规则配置
# =============================================================================

import json
import os
from pathlib import Path


@dataclass
class SymbolRules:
    """
    符号处理规则配置
    
    用于控制调用链中符号的显示行为：
    - hidden: 完全隐藏的符号
    - collapse: 折叠为一组的符号
    
    支持简单通配符模式匹配（如 *__x64_sys_*）
    """
    hidden: List[str] = field(default_factory=list)
    collapse_groups: Dict[str, Dict] = field(default_factory=dict)
    
    # 运行时函数跳过配置
    skip_runtime_at_bottom: bool = True
    runtime_patterns: List[str] = field(default_factory=list)
    anchor_offset_from_bottom: int = 3
    
    # 聚类配置 (用于 cluster-paths)
    clustering: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'min_depth': 2,
        'min_samples': 5
    })
    
    @classmethod
    def from_file(cls, filepath: Optional[str] = None) -> 'SymbolRules':
        """
        从 JSON 文件加载符号规则
        
        Args:
            filepath: 配置文件路径，默认使用 config/symbol_rules.json
            
        Returns:
            SymbolRules 实例
        """
        if filepath is None:
            # 默认路径：当前文件所在目录的 symbol_rules.json
            config_dir = Path(__file__).parent
            filepath = config_dir / "symbol_rules.json"
        
        if not os.path.exists(filepath):
            # 返回默认配置
            return cls._default_rules()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rules = data.get('rules', {})
            sampling = data.get('sampling', {})
            clustering = data.get('clustering', {})
            
            return cls(
                hidden=rules.get('hidden', {}).get('patterns', []),
                collapse_groups={
                    g['name']: g 
                    for g in rules.get('collapse', {}).get('groups', [])
                },
                skip_runtime_at_bottom=sampling.get('skip_bottom_runtime', True),
                runtime_patterns=sampling.get('runtime_function_patterns', []),
                anchor_offset_from_bottom=sampling.get('anchor_from_bottom', 3),
                clustering={
                    'enabled': clustering.get('enabled', True),
                    'min_depth': clustering.get('min_depth', 2),
                    'min_samples': clustering.get('min_samples', 5)
                } if clustering else {
                    'enabled': True,
                    'min_depth': 2,
                    'min_samples': 5
                }
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[Warning] Failed to load symbol rules from {filepath}: {e}")
            return cls._default_rules()
    
    @classmethod
    def _default_rules(cls) -> 'SymbolRules':
        """返回默认规则"""
        return cls(
            hidden=['__clone', 'clone', 'start_thread', 'execute_native_thread_routine'],
            collapse_groups={
                'python_interpreter': {
                    'name': 'python_interpreter',
                    'symbols': ['_Py*', 'Py*'],
                    'display': '(python_interp)'
                }
            },
            skip_runtime_at_bottom=True,
            runtime_patterns=['__clone', 'start_thread', 'execute_native_thread_routine'],
            anchor_offset_from_bottom=3
        )
    
    @staticmethod
    def _match_pattern(symbol: str, pattern: str) -> bool:
        """
        简单通配符匹配
        
        支持的通配符：
        - *: 匹配任意字符序列
        
        Args:
            symbol: 符号名
            pattern: 匹配模式
            
        Returns:
            是否匹配
        """
        # 完全匹配
        if symbol == pattern:
            return True
        # 简单通配符匹配（仅支持 *）
        if '*' in pattern:
            import fnmatch
            return fnmatch.fnmatch(symbol, pattern)
        return False
    
    def is_hidden(self, symbol: str) -> bool:
        """
        检查符号是否在隐藏列表中
        
        支持简单通配符模式匹配
        """
        for pattern in self.hidden:
            if self._match_pattern(symbol, pattern):
                return True
        return False
    
    def get_collapse_group(self, symbol: str) -> Optional[str]:
        """
        检查符号属于哪个折叠组
        
        Args:
            symbol: 符号名
            
        Returns:
            折叠组的 display 名称，如果不属于任何组返回 None
        """
        for group_name, group_config in self.collapse_groups.items():
            symbols = group_config.get('symbols', [])
            for pattern in symbols:
                if self._match_pattern(symbol, pattern):
                    return group_config.get('display', f"[{group_name}]")
        return None
    
    def is_runtime(self, symbol: str) -> bool:
        """
        检查符号是否是运行时函数
        
        支持通配符模式匹配
        """
        for pattern in self.runtime_patterns:
            if self._match_pattern(symbol, pattern):
                return True
        return False
    
    def find_meaningful_anchor(self, stack: List[str]) -> int:
        """
        从栈底向上找有意义的锚点索引
        
        策略：
        1. 如果栈底不是运行时函数，直接返回栈底
        2. 如果栈底是运行时函数，向上找第一个非运行时函数
        3. 如果全是运行时函数，返回栈底
        
        Args:
            stack: 调用栈符号列表
            
        Returns:
            有意义的锚点索引（从0开始）
        """
        if not stack:
            return 0
        
        if not self.skip_runtime_at_bottom:
            return len(stack) - 1
        
        # 从栈底向上找，找到第一个非运行时函数
        for i in range(len(stack) - 1, -1, -1):
            if not self.is_runtime(stack[i]):
                return i
        
        # 全是运行时函数，返回栈底
        return len(stack) - 1
    
    def filter_stack(self, stack: List[str]) -> List[str]:
        """
        过滤调用栈，移除 hidden 符号
        
        Args:
            stack: 原始调用栈
            
        Returns:
            过滤后的调用栈
        """
        return [s for s in stack if not self.is_hidden(s)]
    
    def process_stack(self, stack: List[str], normalize: bool = True) -> 'ProcessedStack':
        """
        处理调用栈，应用所有规则
        
        处理流程：
        1. 移除 hidden 符号
        2. 应用 collapse（将组内符号折叠）
        3. 规范化 symbol name（只保留 classname::method，默认启用）
        
        Args:
            stack: 原始调用栈
            normalize: 是否规范化 symbol name，默认为 True
            
        Returns:
            ProcessedStack 对象
        """
        return ProcessedStack.process(stack, self, normalize=normalize)
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        规范化符号名，只保留最后的 ClassName::method 部分
        
        转换示例：
        - "std::vector<int>::push_back" -> "vector<int>::push_back"
        - "MyClass::MyClass::method" -> "MyClass::method"
        - "parameter_server::optimizer::AdamOptimizer::Optimize" -> "AdamOptimizer::Optimize"
        - "func" -> "func" (无 :: 的不变)
        - "[syscall]" -> "[syscall]" (折叠组标记不变)
        - "(aggregate:module)" -> "(aggregate:module)" (聚合标记不变)
        - "(concept:name)" -> "(concept:name)" (概念标记不变)
        
        Args:
            symbol: 原始符号名
            
        Returns:
            截断后的符号名
        """
        # 保留折叠组标记 [name]
        if symbol.startswith('[') and symbol.endswith(']'):
            return symbol
        
        # 保留聚合标记 (aggregate:name) 和概念标记 (concept:name)
        if symbol.startswith('(aggregate:') and symbol.endswith(')'):
            return symbol
        if symbol.startswith('(concept:') and symbol.endswith(')'):
            return symbol
        
        if '::' not in symbol:
            return symbol
        
        parts = symbol.split('::')
        if len(parts) >= 2:
            return '::'.join(parts[-2:])
        return symbol


@dataclass
class ProcessedStack:
    """
    处理后的调用栈结果
    
    包含处理后的栈和统计信息
    """
    original_stack: List[str]
    processed_stack: List[str]
    
    # 统计信息
    hidden_count: int = 0
    collapsed_count: int = 0
    
    @classmethod
    def process(cls, stack: List[str], rules: SymbolRules, normalize: bool = True) -> 'ProcessedStack':
        """
        处理调用栈，应用 symbol 规则
        
        处理流程：
        1. 移除 hidden 符号
        2. 应用 collapse（将连续的组内符号折叠）
        3. 规范化 symbol name（可选）
        
        Args:
            stack: 原始调用栈（栈顶在索引 0）
            rules: SymbolRules 实例
            normalize: 是否规范化 symbol name，默认为 True
            
        Returns:
            ProcessedStack 对象
            
        Example:
            >>> rules = SymbolRules(
            ...     hidden=['__clone'],
            ...     collapse_groups={'memory': {'symbols': ['malloc', 'free'], 'display': '(memory_ops)'}}
            ... )
            >>> stack = ['malloc', '__clone', 'main', 'start_thread']
            >>> result = ProcessedStack.process(stack, rules)
            >>> result.processed_stack
            ['malloc', 'main']
        """
        if not stack:
            return cls(original_stack=[], processed_stack=[])
        
        # 阶段1: 移除 hidden 符号
        filtered = [sym for sym in stack if not rules.is_hidden(sym)]
        hidden_count = len(stack) - len(filtered)
        
        # 阶段2: 应用 collapse（折叠连续的组内符号）
        processed = []
        collapsed_count = 0
        i = 0
        
        while i < len(filtered):
            sym = filtered[i]
            collapse_display = rules.get_collapse_group(sym)
            
            if collapse_display:
                # 检查是否是连续的组内符号
                if processed and processed[-1] == collapse_display:
                    # 已经是折叠组的一部分，跳过
                    collapsed_count += 1
                    i += 1
                    continue
                
                # 开始一个新的折叠组，检查后面还有多少连续的同组符号
                j = i + 1
                while j < len(filtered) and rules.get_collapse_group(filtered[j]) == collapse_display:
                    j += 1
                    collapsed_count += 1
                
                processed.append(collapse_display)
                i = j
            else:
                processed.append(sym)
                i += 1
        
        # 阶段2.5: 折叠连续的相同聚合符号（如多个 unknown_func[module]）
        # 这些符号在 sample parse 阶段被聚合成相同字符串，展示时需进一步折叠
        deduped = []
        for sym in processed:
            # 如果当前符号与前一个相同，跳过（折叠）
            if deduped and deduped[-1] == sym:
                collapsed_count += 1
                continue
            deduped.append(sym)
        processed = deduped
        
        # 阶段3: 规范化 symbol name（只保留 classname::method）
        if normalize:
            processed = [rules.normalize_symbol(sym) for sym in processed]
        
        return cls(
            original_stack=list(stack),
            processed_stack=processed,
            hidden_count=hidden_count,
            collapsed_count=collapsed_count
        )
    
    def get_summary(self) -> str:
        """获取处理摘要"""
        total_ops = self.hidden_count + self.collapsed_count
        if total_ops == 0:
            return "No transformations applied"
        
        parts = []
        if self.hidden_count > 0:
            parts.append(f"{self.hidden_count} hidden")
        if self.collapsed_count > 0:
            parts.append(f"{self.collapsed_count} collapsed")
        
        return f"Applied: {', '.join(parts)} ({len(self.original_stack)} -> {len(self.processed_stack)} symbols)"
    
    def __len__(self) -> int:
        return len(self.processed_stack)
    
    def __iter__(self):
        return iter(self.processed_stack)
    
    def __getitem__(self, index) -> str:
        return self.processed_stack[index]


# 全局符号规则实例（懒加载）
_symbol_rules: Optional[SymbolRules] = None


def get_symbol_rules() -> SymbolRules:
    """获取全局符号规则实例"""
    global _symbol_rules
    if _symbol_rules is None:
        _symbol_rules = SymbolRules.from_file()
    return _symbol_rules


# =============================================================================
# 便捷访问函数
# =============================================================================

def get_default_output_config() -> Dict:
    """获取完整的默认输出配置（用于 JSON 序列化）"""
    return {
        "attention_flags": {
            "X0": AttentionFlag.X0,
            "X1": AttentionFlag.X1,
            "X2": AttentionFlag.X2,
            "XA": AttentionFlag.XA,
        },
        "diagnosis_types": {
            "BOTTLENECK": DiagnosisType.BOTTLENECK,
            "STORM": DiagnosisType.STORM,
            "UNBALANCED": DiagnosisType.UNBALANCED,
            "NORMAL": DiagnosisType.NORMAL,
            "HEALTHY": DiagnosisType.HEALTHY,
        },
        "severity_levels": {
            "NONE": SeverityLevel.NONE,
            "LOW": SeverityLevel.LOW,
            "MEDIUM": SeverityLevel.MEDIUM,
            "HIGH": SeverityLevel.HIGH,
            "CRITICAL": SeverityLevel.CRITICAL,
        },
        "thresholds": {
            "monopoly_high": Thresholds.MONOPOLY_HIGH,
            "monopoly_critical": Thresholds.MONOPOLY_CRITICAL,
            "cv_unbalanced": Thresholds.CV_UNBALANCED,
            "cv_high": Thresholds.CV_HIGH,
            "cpu_util_high": Thresholds.CPU_UTIL_HIGH,
            "cpu_util_critical": Thresholds.CPU_UTIL_CRITICAL,
            "kernel_ratio_high": Thresholds.KERNEL_RATIO_HIGH,
        },
    }
