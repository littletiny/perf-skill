#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output Adapter - 将数据模型转换为 JSON 输出

遵循 output-format-spec.md 规范：
- 所有数据模型通过此类转换为 JSON 格式
- 统一处理时间格式、百分比格式等
- 确保输出格式的一致性
"""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime


class OutputAdapter:
    """
    统一的输出适配器，将数据模型转换为 JSON 格式
    
    Usage:
        # 创建输出模型
        output = CommTopOutput(
            risk=RiskInfo(level="none"),
            comm_groups=[CommGroupItem(...)],
            summary=CommGroupSummary(...),
            time_range=TimeRange(...)
        )
        
        # 转换为 JSON
        adapter = OutputAdapter()
        json_output = adapter.to_json(output)
    """
    
    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """
        初始化适配器
        
        Args:
            indent: JSON 缩进
            ensure_ascii: 是否转义非 ASCII 字符
        """
        self.indent = indent
        self.ensure_ascii = ensure_ascii
    
    def to_dict(self, obj: Any) -> Any:
        """
        将对象转换为字典（递归处理）
        
        Args:
            obj: 要转换的对象
            
        Returns:
            转换后的字典
        """
        if obj is None:
            return None
        
        # 处理 dataclass
        if is_dataclass(obj):
            result = {}
            for key, value in asdict(obj).items():
                # 跳过 None 值（可选，如果需要保留 None 可以注释掉）
                if value is not None:
                    result[key] = self.to_dict(value)
            return result
        
        # 处理列表
        if isinstance(obj, list):
            return [self.to_dict(item) for item in obj]
        
        # 处理字典
        if isinstance(obj, dict):
            return {key: self.to_dict(value) for key, value in obj.items()}
        
        # 基本类型直接返回
        return obj
    
    def to_json(self, obj: Any) -> str:
        """
        将对象转换为 JSON 字符串
        
        Args:
            obj: 要转换的对象
            
        Returns:
            JSON 字符串
        """
        import json
        return json.dumps(
            self.to_dict(obj),
            indent=self.indent,
            ensure_ascii=self.ensure_ascii
        )
    
    def print_json(self, obj: Any):
        """打印 JSON 输出"""
        print(self.to_json(obj))


class CompactOutputAdapter(OutputAdapter):
    """
    紧凑模式输出适配器（用于生产环境）
    
    特点：
    - 无缩进，体积更小
    - 跳过 None 值
    - 不转义 Unicode
    """
    
    def __init__(self):
        super().__init__(indent=None, ensure_ascii=False)
    
    def to_dict(self, obj: Any) -> Any:
        """重写 to_dict 以跳过所有 None 值"""
        if obj is None:
            return None
        
        if is_dataclass(obj):
            result = {}
            for key, value in asdict(obj).items():
                # 严格跳过 None 和空值
                if value is None:
                    continue
                if isinstance(value, (list, dict)) and len(value) == 0:
                    continue
                result[key] = self.to_dict(value)
            return result
        
        if isinstance(obj, list):
            return [self.to_dict(item) for item in obj]
        
        if isinstance(obj, dict):
            return {key: self.to_dict(value) for key, value in obj.items() if value is not None}
        
        return obj


# =============================================================================
# Helper Functions
# =============================================================================

def to_json_output(obj: Any, compact: bool = False) -> str:
    """
    快速转换为 JSON 字符串
    
    Args:
        obj: 要转换的对象
        compact: 是否使用紧凑模式
        
    Returns:
        JSON 字符串
    """
    adapter = CompactOutputAdapter() if compact else OutputAdapter()
    return adapter.to_json(obj)


def print_json_output(obj: Any, compact: bool = False):
    """快速打印 JSON 输出"""
    print(to_json_output(obj, compact))
