#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default Configuration - 全项目默认常量配置

所有输出相关的常量、阈值、枚举值统一在此定义，避免分散硬编码。
使用方式:
    from config.defaults import OutputDefaults, DiagnosisType, RiskPattern
    
    if diagnosis == DiagnosisType.BOTTLENECK:
        print(OutputDefaults.BOTTLENECK_TRACE_TITLE)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    BOTTLENECK_TRACE_TITLE = "## [BOTTLENECK_TRACE]"
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
    TRACES_HEADER = "# target (cpu_util) <- callstack"
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
    # Z-Score Thresholds (Anomaly Detection)
    # -------------------------------------------------------------------------
    Z_SCORE_MEDIUM = 2.0            # 中等异常 Z-Score
    Z_SCORE_HIGH = 2.5              # 高异常 Z-Score


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
