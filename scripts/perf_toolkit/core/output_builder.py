#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutputBuilder - Unified output interface for all analysis tools

统一所有分析工具的输出格式，消除重复代码，确保一致性。
"""

import json
from typing import List, Dict, Optional, Any, Callable
from .risk_mixin import RiskAwareOutput
from .format_utils import format_time_range, safe_time_range
from .reliability import assess_data_quality


# Standard field name mapping for different data types
DATA_TYPE_FIELDS = {
    "hotspots": "hotspots",
    "clusters": "clusters",
    "processes": "processes",
    "comm_groups": "comm_groups",
    "cores": "cores",
    "anomalies": "anomalies",
    "traces": "traces",
    "attributions": "attributions",
    "process_variety": "process_variety",
    "stacks": "stacks",
    "windows": "windows",
    "flamegraph": "data",
    "callgraph": "data",
    "generic": "data",
}


class OutputBuilder:
    """
    Unified output builder for all analysis tools.
    
    Usage:
        builder = OutputBuilder(engine, args)
        
        # Check empty samples
        if builder.check_empty_samples(samples):
            return
            
        # Assess data quality
        quality_level = builder.assess_quality(samples)
        
        # Build output
        result = builder.build(
            data_type="hotspots",
            data=hotspots_list,
            summary={"total": len(hotspots_list)}
        )
        builder.print_json(result)
    """
    
    def __init__(self, engine, args):
        """
        Initialize output builder.
        
        Args:
            engine: PerfExpertEngine instance
            args: argparse namespace with tool arguments
        """
        self.engine = engine
        self.args = args
        self._risk_output = RiskAwareOutput()
        self._quality_level = None
        self._quality_metrics = None
        self._samples = None
    
    def check_empty_samples(self, samples: List[Dict], filters: Dict = None) -> bool:
        """
        Check if samples is empty and output error JSON if so.
        
        Args:
            samples: List of sample dictionaries
            filters: Optional dict of applied filters for error message
            
        Returns:
            True if samples is empty (caller should return), False otherwise
        """
        if samples:
            self._samples = samples
            return False
            
        # Build error response for empty samples
        error_data = {
            "error": "No samples found",
            "time_range": format_time_range(
                getattr(self.args, 'start_time', None),
                getattr(self.args, 'end_time', None)
            ),
            "available_range": self.engine.get_time_range()
        }
        
        if filters:
            error_data["filters"] = filters
            
        result = self._risk_output.add_risk(
            "warning",
            "未找到样本数据",
            "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '未找到样本数据' --risk 'warning' --hint '检查过滤条件'",
            patterns=["NO_SAMPLES"]
        ).build(error_data)
        
        self.print_json(result)
        return True
    
    def assess_quality(self, samples: List[Dict] = None, 
                       early_return: bool = False) -> Optional[str]:
        """
        Assess data quality and store results.
        
        Args:
            samples: List of samples (uses stored samples if None)
            early_return: If True and quality is CRITICAL, print and return True
            
        Returns:
            Quality level string, or True if early_return and CRITICAL
        """
        if samples is None:
            samples = self._samples
            
        if not samples:
            self._quality_level = "CRITICAL"
            self._quality_metrics = {}
            return self._quality_level if not early_return else False
            
        duration = samples[-1]['ts'] - samples[0]['ts'] if len(samples) > 1 else 0
        record_count = len(samples)
        
        total_core_per_sec, _ = self.engine.get_total_core_per_sec(samples)
        quality_level, warning_msg, metrics = assess_data_quality(
            duration, total_core_per_sec=total_core_per_sec, record_count=record_count
        )
        
        self._quality_level = quality_level
        self._quality_metrics = {
            "level": quality_level,
            "warning": warning_msg,
            "metrics": metrics
        }
        
        # Handle early return for critical quality
        if early_return and quality_level == "CRITICAL":
            result = self.add_data_quality_risk().build({
                "data_quality": self._quality_metrics,
                "error": "Insufficient data quality for analysis"
            })
            self.print_json(result)
            return True
            
        return quality_level
    
    def add_data_quality_risk(self, message: str = None) -> 'OutputBuilder':
        """
        Add standard data quality risk if quality is CRITICAL.
        
        Args:
            message: Custom message (uses default if None)
            
        Returns:
            Self for chaining
        """
        if self._quality_level == "CRITICAL":
            msg = message or "数据质量不足！分析结果完全不可信"
            self._risk_output.add_risk(
                "critical",
                msg,
                "[必须] 添加到 Live Document: doc add --id <ISS-XXX> --desc '数据质量不足！分析结果完全不可信' --risk 'critical' --hint '使用更长的采样时间重新采集数据'",
                patterns=["CRITICAL_DATA_QUALITY"]
            )
        return self
    
    def add_risk(self, level: str, message: str, hint: str = "",
                 patterns: List[str] = None, targets: List[str] = None) -> 'OutputBuilder':
        """
        Add a custom risk hint.
        
        Args:
            level: Risk level - critical/warning/info/none
            message: Risk description
            hint: Recommended next action
            patterns: List of detected pattern names
            targets: List of targets to process
            
        Returns:
            Self for chaining
        """
        self._risk_output.add_risk(level, message, hint, patterns, targets)
        return self
    
    def get_time_range(self, samples: List[Dict] = None) -> Dict:
        """
        Get formatted time range from samples.
        
        Args:
            samples: List of samples (uses stored samples if None)
            
        Returns:
            Formatted time range dict
        """
        if samples is None:
            samples = self._samples
        return safe_time_range(samples)
    
    def build(self, data_type: str, data: Any, 
              summary: Dict = None,
              time_range: Dict = None,
              include_quality: bool = False,
              include_time_range: bool = False,
              **extra_fields) -> Dict:
        """
        Build final output with standard structure.
        
        Args:
            data_type: Type of data (determines field name)
            data: Main data content (list or string)
            summary: Optional summary statistics
            time_range: Optional time range (auto-detected if None)
            include_quality: Whether to include data_quality field
            include_time_range: Whether to include time_range field (default False for most tools)
            **extra_fields: Additional fields to include
            
        Returns:
            Complete output dictionary with _risk field
        """
        # Auto-add data quality risk if CRITICAL
        self.add_data_quality_risk()
        
        # Build output structure
        output = {}
        
        # Add summary if provided
        if summary is not None:
            output["summary"] = summary
            
        # Add time range only if explicitly requested
        if include_time_range:
            if time_range is None:
                time_range = self.get_time_range()
            output["time_range"] = time_range
        
        # Add data quality info if requested
        if include_quality and self._quality_metrics:
            output["data_quality"] = self._quality_metrics
            
        # Add extra fields
        output.update(extra_fields)
        
        # Add main data with appropriate field name
        field_name = DATA_TYPE_FIELDS.get(data_type, "data")
        output[field_name] = data
        
        # Add _risk field via RiskAwareOutput
        return self._risk_output.build(output)
    
    def build_simple(self, data: Dict) -> Dict:
        """
        Build output with simple data dict (no automatic field mapping).
        
        Args:
            data: Data dictionary to wrap with _risk
            
        Returns:
            Output with _risk field prepended
        """
        self.add_data_quality_risk()
        return self._risk_output.build(data)
    
    def print_json(self, result: Dict, **json_kwargs):
        """
        Print result as JSON.
        
        Args:
            result: Output dictionary
            **json_kwargs: Additional arguments for json.dumps()
        """
        defaults = {
            "indent": 2,
            "ensure_ascii": False
        }
        defaults.update(json_kwargs)
        print(json.dumps(result, **defaults))


class AnalysisExecutor:
    """
    Higher-level helper for common analysis patterns.
    
    Usage:
        def cmd_my_tool(engine, args):
            executor = AnalysisExecutor(engine, args)
            
            # Standard init: filters, empty check, quality assessment
            if not executor.init(args_filter=True):
                return
                
            # Process samples...
            results = process(executor.samples)
            
            # Build and output
            executor.output("hotspots", results, {"total": len(results)})
    """
    
    def __init__(self, engine, args):
        self.engine = engine
        self.args = args
        self.builder = OutputBuilder(engine, args)
        self.samples = None
        self.quality_level = None
    
    def fetch_samples(self, **extra_filters) -> List[Dict]:
        """
        Fetch filtered samples based on args.
        
        Args:
            **extra_filters: Additional filter parameters
            
        Returns:
            List of filtered samples
        """
        # Build standard filters from args
        filters = {
            'start_time': getattr(self.args, 'start_time', None),
            'end_time': getattr(self.args, 'end_time', None),
            'cpu_id': getattr(self.args, 'cpu_id', None),
            'pid': getattr(self.args, 'pid', None),
            'comm': getattr(self.args, 'comm', None),
            'comm_regex': getattr(self.args, 'comm_regex', None),
        }
        filters.update(extra_filters)
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        self.samples = self.engine.get_filtered_samples(**filters)
        return self.samples
    
    def init(self, empty_check: bool = True, 
             quality_check: bool = True,
             early_return_critical: bool = False,
             **extra_filters) -> bool:
        """
        Standard initialization: fetch samples, check empty, assess quality.
        
        Args:
            empty_check: Whether to check and handle empty samples
            quality_check: Whether to assess data quality
            early_return_critical: Whether to return early on CRITICAL quality
            **extra_filters: Additional filter parameters
            
        Returns:
            True if initialization successful (can continue), False otherwise
        """
        # Fetch samples
        self.fetch_samples(**extra_filters)
        
        # Check empty
        if empty_check and self.builder.check_empty_samples(self.samples):
            return False
            
        # Assess quality
        if quality_check:
            result = self.builder.assess_quality(self.samples, early_return_critical)
            if early_return_critical and result is True:
                return False
            self.quality_level = result if isinstance(result, str) else self.builder._quality_level
            
        return True
    
    def output(self, data_type: str, data: Any, 
               summary: Dict = None, **extra_fields):
        """
        Build and print output.
        
        Args:
            data_type: Type of data for field naming
            data: Main data content
            summary: Optional summary statistics
            **extra_fields: Additional fields
        """
        result = self.builder.build(
            data_type=data_type,
            data=data,
            summary=summary,
            **extra_fields
        )
        self.builder.print_json(result)
