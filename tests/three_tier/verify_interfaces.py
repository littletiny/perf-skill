#!/usr/bin/env python3
"""
三层架构接口快速验证脚本

用于开发过程中快速验证各层接口是否可用，
不依赖完整实现，主要用于接口契约验证。

使用方法:
    python3 tests/three_tier/verify_interfaces.py
    
输出:
    - ✅ 表示接口已就绪
    - ⚠️ 表示接口部分就绪或有警告
    - ❌ 表示接口未实现
"""

import sys
from pathlib import Path
from enum import Enum

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class Status(Enum):
    """验证状态"""
    READY = "✅"
    PARTIAL = "⚠️"
    MISSING = "❌"


def print_header(title):
    """打印标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_item(name, status, detail=""):
    """打印验证项"""
    detail_str = f" - {detail}" if detail else ""
    print(f"  {status.value} {name}{detail_str}")


def verify_core_interfaces():
    """验证Core层接口"""
    print_header("Layer 1: Core层接口验证")
    
    # 验证Engine类存在
    try:
        from perf_toolkit.core.engine import PerfExpertEngine
        print_item("PerfExpertEngine", Status.READY)
    except ImportError:
        print_item("PerfExpertEngine", Status.MISSING)
        return
    
    try:
        engine = PerfExpertEngine("")
    except:
        # 如果构造需要参数，尝试无参构造
        try:
            engine = PerfExpertEngine.__new__(PerfExpertEngine)
        except:
            print_item("PerfExpertEngine实例化", Status.PARTIAL, "需要进一步检查")
            return
    
    # 验证已有接口
    required_methods = [
        'get_comm_cpu_util',
        'get_pid_cpu_util', 
        'get_core_cpu_util',
        'get_filtered_samples',
        'get_time_range'
    ]
    
    for method in required_methods:
        if hasattr(engine, method):
            print_item(f"Engine.{method}()", Status.READY, "已有接口")
        else:
            print_item(f"Engine.{method}()", Status.MISSING)
    
    # 验证新增接口
    new_methods = [
        'get_process_lifecycle',
        'get_pid_cpu_distribution',
        'get_call_graph'
    ]
    
    for method in new_methods:
        if hasattr(engine, method):
            print_item(f"Engine.{method}()", Status.READY, "新增接口")
        else:
            print_item(f"Engine.{method}()", Status.MISSING, "待实现")


def verify_risk_interfaces():
    """验证Risk接口"""
    print_header("Core层: Risk接口验证")
    
    # RiskMixin
    try:
        from perf_toolkit.core.risk_mixin import RiskMixin
        print_item("RiskMixin:", Status.READY)
        
        # 验证关键方法
        mixin = RiskMixin()
        required_methods = ['add_risk', 'get_top_risk', 'format_output']
        for method in required_methods:
            if hasattr(mixin, method):
                print_item(f"  .{method}()", Status.READY)
            else:
                print_item(f"  .{method}()", Status.MISSING)
                
    except ImportError:
        print_item("RiskMixin:", Status.MISSING)
    
    # RiskInfo
    try:
        from perf_toolkit.core.output_models import RiskInfo
        print_item("RiskInfo (dataclass):", Status.READY)
    except (ImportError, AttributeError):
        print_item("RiskInfo (dataclass):", Status.MISSING)


def verify_analysis_interfaces():
    """验证Analysis层接口"""
    print_header("Layer 2: Analysis层接口验证")
    
    # Facade
    try:
        from perf_toolkit.analysis.facade import AnalysisFacade
        print_item("AnalysisFacade:", Status.READY)
        
        # 验证接口方法
        facade_methods = [
            'analyze_comm_top',
            'analyze_hotspots',
            'analyze_core_distribution',
            'detect_anomalies',
            'analyze_callers',
            'cluster_paths'
        ]
        
        for method in facade_methods:
            if hasattr(AnalysisFacade, method):
                print_item(f"  .{method}()", Status.READY)
            else:
                print_item(f"  .{method}()", Status.MISSING)
                
    except ImportError:
        print_item("AnalysisFacade", Status.MISSING, "待实现")
    
    # Analyzers
    analyzers = [
        ('CommTopAnalyzer', 'analysis.comm_top'),
        ('HotspotsAnalyzer', 'analysis.hotspots'),
        ('CoreDistAnalyzer', 'analysis.core_distribution'),
        ('AnomaliesAnalyzer', 'analysis.anomalies')
    ]
    
    print("")  # 空行
    print_item("Analyzers:", Status.PARTIAL, "")
    for name, module in analyzers:
        try:
            exec(f"from perf_toolkit.{module} import {name}")
            print_item(f"  .{name}()", Status.READY)
        except ImportError:
            print_item(f"  .{name}()", Status.MISSING)


def verify_composite_interfaces():
    """验证Composite层接口"""
    print_header("Layer 3: Composite层接口验证")
    
    commands = [
        ('sys_audit', 'cmd_sys_audit'),
        ('bottleneck_trace', 'cmd_bottleneck_trace'),
        ('storm_trace', 'cmd_storm_trace')
    ]
    
    for module, cmd in commands:
        try:
            exec(f"from perf_toolkit.composite.{module} import {cmd}")
            print_item(f"composite/{module}.py", Status.READY, f"{cmd}可用")
        except ImportError:
            print_item(f"composite/{module}.py", Status.MISSING, f"{cmd}待实现")


def verify_output_models():
    """验证输出模型"""
    print_header("输出模型验证")
    
    models = [
        'RiskInfo',
        'CommTopOutput',
        'SysAuditOutput',
        'BottleneckTraceOutput',
        'StormTraceOutput'
    ]
    
    try:
        from perf_toolkit.core import output_models
        
        for model in models:
            if hasattr(output_models, model):
                print_item(f"{model}", Status.READY)
            else:
                print_item(f"{model}", Status.MISSING)
    except ImportError:
        print_item("output_models模块", Status.MISSING)


def verify_trace_integration():
    """验证Trace集成"""
    print_header("Trace集成验证")
    
    try:
        from perf_toolkit.core.trace import Trace
        print_item("Trace类:", Status.READY)
        
        # 验证关键方法
        methods = ['begin_command', 'record_risk', 'end_command']
        for method in methods:
            if hasattr(Trace, method):
                print_item(f"  .{method}()", Status.READY)
            else:
                print_item(f"  .{method}()", Status.MISSING)
    except ImportError:
        print_item("Trace类:", Status.MISSING)
    
    # OutputBuilder集成
    try:
        from perf_toolkit.core.output_builder import OutputBuilder
        print_item("OutputBuilder:", Status.READY)
        
        if hasattr(OutputBuilder, 'record_risk'):
            print_item("  .record_risk()", Status.READY)
        else:
            print_item("  .record_risk()", Status.MISSING)
    except ImportError:
        print_item("OutputBuilder:", Status.MISSING)


def print_summary():
    """打印总结"""
    print(f"\n{'=' * 60}")
    print("  验证说明")
    print(f"{'=' * 60}")
    print("""
图例:
  ✅ 已就绪 - 接口已实现，可使用
  ⚠️ 部分就绪 - 部分功能可用，有待完善
  ❌ 未实现 - 接口尚未实现

下一步:
  1. 确保所有 ❌ 项都被实现
  2. 运行测试: python3 tests/three_tier/run_all_tests.py
  3. 验证通过后即可集成
""")


def main():
    """主函数"""
    print(f"\n{'=' * 60}")
    print("  三层架构接口快速验证")
    print(f"{'=' * 60}")
    print(f"\n项目路径: {PROJECT_ROOT}")
    
    verify_core_interfaces()
    verify_risk_interfaces()
    verify_analysis_interfaces()
    verify_composite_interfaces()
    verify_output_models()
    verify_trace_integration()
    print_summary()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
