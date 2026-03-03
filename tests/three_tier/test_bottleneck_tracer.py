#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BottleneckTraceAdapter 单元测试

验证 bottleneck_tracer.py 的核心功能。
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.composite.bottleneck_tracer import (
    BottleneckTraceAdapter, EntityDistribution, CallPathCluster,
    CorrelationFlag, BottleneckTraceResult,
    create_adapter, run_bottleneck_trace
)
from scripts.perf_toolkit.core.models import RiskInfo, TimeRange
from scripts.perf_toolkit.analysis.models import (
    CommTopResult, CommGroup, HotspotsResult, Hotspot,
    CoreDistributionResult, CoreStat, PathClustersResult, PathCluster,
    CallersResult, CallerAttribution
)
from config.defaults import DiagnosisType


# =============================================================================
# Mock Classes
# =============================================================================

@dataclass
class MockSample:
    """模拟样本数据"""
    comm: str
    pid: str
    cpu: int
    ts: float
    core_per_sec: Optional[float] = None
    stack: Optional[Any] = None


class MockEngine:
    """模拟 Engine"""
    pass


class MockFacade:
    """模拟 AnalysisFacade"""
    
    def __init__(self):
        self._engine = MockEngine()
    
    def analyze_comm_top(self, samples, top_n=10, include_metrics=False):
        """模拟进程组分析"""
        groups = [
            CommGroup(
                comm="test_app",
                total_cpu=85.5,
                kernel_cpu=15.2,
                user_cpu=70.3,
                pid_count=5,
                pids=[1001, 1002, 1003, 1004, 1005],
                cv=0.3,
                monopoly=0.85,
                spawn_rate=0.5,
                diagnosis=DiagnosisType.BOTTLENECK,
                impact_score=75.0
            ),
            CommGroup(
                comm="background_task",
                total_cpu=12.3,
                kernel_cpu=2.1,
                user_cpu=10.2,
                pid_count=1,
                pids=[2001],
                cv=0.1,
                monopoly=0.1,
                spawn_rate=0.1,
                diagnosis=DiagnosisType.HEALTHY,
                impact_score=10.0
            )
        ]
        return CommTopResult(
            groups=groups,
            folded_count=0,
            total_groups=2
        )
    
    def analyze_hotspots(self, samples, comm=None, pid=None, top_n=20, sort_by="self"):
        """模拟热点分析"""
        hotspots = [
            Hotspot(
                symbol="_raw_spin_lock",
                self_pct=45.2,
                inclusive_pct=45.2,
                is_kernel=True
            ),
            Hotspot(
                symbol="process_data",
                self_pct=25.8,
                inclusive_pct=65.3,
                is_kernel=False
            ),
            Hotspot(
                symbol="handle_request",
                self_pct=15.3,
                inclusive_pct=35.7,
                is_kernel=False
            )
        ]
        return HotspotsResult(
            hotspots=hotspots,
            kernel_ratio=45.2,
            user_ratio=54.8,
            sort_by=sort_by
        )
    
    def analyze_core_distribution(self, samples, top_n=10):
        """模拟核心分布分析"""
        cores = [
            CoreStat(cpu_id=0, total_cpu=95.2, kernel_cpu=20.5, user_cpu=74.7),
            CoreStat(cpu_id=1, total_cpu=15.3, kernel_cpu=3.2, user_cpu=12.1),
            CoreStat(cpu_id=2, total_cpu=12.1, kernel_cpu=2.8, user_cpu=9.3),
            CoreStat(cpu_id=3, total_cpu=18.7, kernel_cpu=4.1, user_cpu=14.6)
        ]
        return CoreDistributionResult(
            cores=cores,
            imbalance_level="SEVERE",
            saturated_cores=[cores[0]],
            total_cores=4
        )
    
    def cluster_paths(self, samples, min_depth=2, min_samples=5, top_n=10, comm=None, pid=None):
        """模拟路径聚类"""
        clusters = [
            PathCluster(
                cluster_id="c1",
                path_signature="main -> worker_loop -> process_data -> _raw_spin_lock",
                depth=4,
                weight=45.2,
                cpu_util=45.2
            ),
            PathCluster(
                cluster_id="c2",
                path_signature="main -> handle_request -> process_data",
                depth=3,
                weight=35.7,
                cpu_util=35.7
            )
        ]
        return PathClustersResult(
            clusters=clusters,
            total_clusters=2,
            shown_clusters=2,
            total_weight=80.9,
            clustered_weight=80.9
        )
    
    def analyze_callers(self, samples, target_symbol, comm=None, min_ratio=0.5, top_n=10):
        """模拟调用链溯源"""
        callers = [
            CallerAttribution(
                symbol="process_data -> handle_request",
                call_count=1523,
                call_ratio=65.3,
                total_weight=45.2
            ),
            CallerAttribution(
                symbol="worker_loop",
                call_count=823,
                call_ratio=34.7,
                total_weight=24.1
            )
        ]
        return CallersResult(
            target=target_symbol,
            callers=callers,
            total_weight=45.2
        )


# =============================================================================
# Test Cases
# =============================================================================

def test_entity_distribution_dataclass():
    """测试 EntityDistribution 数据结构"""
    print("\n[TEST] EntityDistribution dataclass")
    
    entity = EntityDistribution(
        comm="test_app",
        count=5,
        incl_saliency=0.65,
        excl_saliency=0.25,
        core_affinity="Fixed",
        throttle_rate=15.5
    )
    
    assert entity.comm == "test_app"
    assert entity.count == 5
    assert entity.incl_saliency == 0.65
    assert entity.excl_saliency == 0.25
    assert entity.core_affinity == "Fixed"
    assert entity.throttle_rate == 15.5
    
    print("  ✓ EntityDistribution 创建成功")


def test_call_path_cluster_dataclass():
    """测试 CallPathCluster 数据结构"""
    print("\n[TEST] CallPathCluster dataclass")
    
    cluster = CallPathCluster(
        cluster_id="c1",
        comm="test_app",
        weight=45.2,
        path=["main", "worker_loop", "process_data", "_raw_spin_lock"],
        hotspot="_raw_spin_lock",
        characteristic="Lock_Contention"
    )
    
    assert cluster.cluster_id == "c1"
    assert cluster.comm == "test_app"
    assert cluster.weight == 45.2
    assert len(cluster.path) == 4
    assert cluster.hotspot == "_raw_spin_lock"
    assert cluster.characteristic == "Lock_Contention"
    
    print("  ✓ CallPathCluster 创建成功")


def test_correlation_flag_dataclass():
    """测试 CorrelationFlag 数据结构"""
    print("\n[TEST] CorrelationFlag dataclass")
    
    flag = CorrelationFlag(
        flag_type="GLOBAL_LOCK_CONTENTION",
        target="_raw_spin_lock",
        message="全局锁占用 45.2% CPU",
        severity="critical"
    )
    
    assert flag.flag_type == "GLOBAL_LOCK_CONTENTION"
    assert flag.target == "_raw_spin_lock"
    assert "45.2%" in flag.message
    assert flag.severity == "critical"
    
    print("  ✓ CorrelationFlag 创建成功")


def test_bottleneck_trace_result_dataclass():
    """测试 BottleneckTraceResult 数据结构"""
    print("\n[TEST] BottleneckTraceResult dataclass")
    
    result = BottleneckTraceResult(
        _risk=RiskInfo(level="critical", message="发现瓶颈"),
        entity_distribution=[],
        common_hotspot="_raw_spin_lock",
        common_hotspot_weight=45.2,
        clusters=[],
        correlation_flags=[],
        total_pids=5,
        total_sys_cpu=97.8,
        top_bottlenecks=["_raw_spin_lock"],
        duration_sec=60.0,
        sample_count=1200,
        time_range=TimeRange()
    )
    
    assert result._risk.level == "critical"
    assert result.common_hotspot == "_raw_spin_lock"
    assert result.common_hotspot_weight == 45.2
    assert result.total_pids == 5
    
    print("  ✓ BottleneckTraceResult 创建成功")


def test_affinity_pattern_fixed():
    """测试 Fixed 亲缘性模式判定"""
    print("\n[TEST] Affinity Pattern: Fixed")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 模拟 Fixed 模式：高度集中在单个核心
    distribution = {0: 95.0, 1: 2.0, 2: 2.0, 3: 1.0}
    pattern = tracer._determine_affinity_pattern(distribution)
    
    # 熵很低，Monopoly 很高 -> Fixed
    assert pattern == "Fixed", f"Expected Fixed, got {pattern}"
    
    print(f"  ✓ 判定为 {pattern}")


def test_affinity_pattern_uniform():
    """测试 Uniform 亲缘性模式判定"""
    print("\n[TEST] Affinity Pattern: Uniform")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 模拟 Uniform 模式：均匀分布
    distribution = {0: 25.0, 1: 25.0, 2: 25.0, 3: 25.0}
    pattern = tracer._determine_affinity_pattern(distribution)
    
    # 熵很高，CV 很低 -> Uniform
    assert pattern == "Uniform", f"Expected Uniform, got {pattern}"
    
    print(f"  ✓ 判定为 {pattern}")


def test_affinity_pattern_scattered():
    """测试 Scattered 亲缘性模式判定"""
    print("\n[TEST] Affinity Pattern: Scattered")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 模拟 Scattered 模式：不规律分布
    distribution = {0: 50.0, 1: 30.0, 2: 15.0, 3: 5.0}
    pattern = tracer._determine_affinity_pattern(distribution)
    
    # 介于 Fixed 和 Uniform 之间 -> Scattered
    assert pattern == "Scattered", f"Expected Scattered, got {pattern}"
    
    print(f"  ✓ 判定为 {pattern}")


def test_detect_correlation_flags():
    """测试关联标志检测"""
    print("\n[TEST] Detect Correlation Flags")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 构造测试数据
    target_group = CommGroup(
        comm="test_app",
        total_cpu=85.5,
        kernel_cpu=15.2,
        user_cpu=70.3,
        pid_count=5,
        pids=[1001],
        cv=0.3,
        monopoly=0.85,
        spawn_rate=0.5,
        diagnosis=DiagnosisType.BOTTLENECK,
        impact_score=75.0
    )
    
    hotspots_result = HotspotsResult(
        hotspots=[
            Hotspot(symbol="_raw_spin_lock", self_pct=45.2, inclusive_pct=45.2, is_kernel=True)
        ],
        kernel_ratio=45.2,
        user_ratio=54.8,
        sort_by="self"
    )
    
    core_dist_result = CoreDistributionResult(
        cores=[CoreStat(cpu_id=0, total_cpu=95.2, kernel_cpu=20.5, user_cpu=74.7)],
        imbalance_level="SEVERE",
        saturated_cores=[CoreStat(cpu_id=0, total_cpu=95.2, kernel_cpu=20.5, user_cpu=74.7)],
        total_cores=4
    )
    
    comm_top_result = CommTopResult(groups=[], folded_count=0, total_groups=0)
    
    # 创建模拟 BottleneckAnalysis
    from scripts.perf_toolkit.composite.models import BottleneckAnalysis
    bottleneck_analysis = BottleneckAnalysis(
        found=True,
        comm="test_app",
        total_cpu=85.5,
        kernel_ratio=17.8,
        pid_count=5,
        cv=0.3,
        monopoly=0.85,
        diagnosis=DiagnosisType.BOTTLENECK,
        impact_score=75.0
    )
    
    # 创建模拟 HotspotsReport（带热点项）
    class MockHotspotItem:
        def __init__(self, symbol, inclusive_percent):
            self.symbol = symbol
            self.inclusive_percent = inclusive_percent
    
    class MockHotspotsReport:
        def __init__(self):
            self.hotspots = [MockHotspotItem("_raw_spin_lock", 45.2)]
    
    hotspots_report = MockHotspotsReport()
    
    flags = tracer._detect_correlation_flags_from_reports(
        bottleneck_analysis, hotspots_report, core_dist_result, comm_top_result
    )
    
    # 验证检测到关键标志
    flag_types = [f.flag_type for f in flags]
    assert "GLOBAL_LOCK_CONTENTION" in flag_types
    assert "SINGLE_CORE_SATURATION" in flag_types
    
    print(f"  ✓ 检测到 {len(flags)} 个关联标志")
    for flag in flags:
        print(f"    - {flag.flag_type}: {flag.severity}")


def test_find_common_hotspot():
    """测试共享热点查找"""
    print("\n[TEST] Find Common Hotspot")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    clusters = [
        CallPathCluster(
            cluster_id="c1",
            comm="test",
            weight=45.2,
            path=["main", "_raw_spin_lock"],
            hotspot="_raw_spin_lock",
            characteristic="Lock_Contention"
        ),
        CallPathCluster(
            cluster_id="c2",
            comm="test",
            weight=35.7,
            path=["main", "process_data", "_raw_spin_lock"],
            hotspot="_raw_spin_lock",
            characteristic="Lock_Contention"
        )
    ]
    
    hotspots = [
        Hotspot(symbol="_raw_spin_lock", self_pct=45.2, inclusive_pct=45.2, is_kernel=True),
        Hotspot(symbol="process_data", self_pct=25.8, inclusive_pct=65.3, is_kernel=False)
    ]
    
    common, weight = tracer._find_common_hotspot(clusters, hotspots)
    
    assert common == "_raw_spin_lock"
    assert weight == 45.2
    
    print(f"  ✓ 共享热点: {common} ({weight}%)")


class MockHotspotItem:
    """模拟 HotspotsReport 中的热点项"""
    def __init__(self, symbol, cpu_percent, inclusive_percent):
        self.symbol = symbol
        self.cpu_percent = cpu_percent  # self_pct
        self.inclusive_percent = inclusive_percent

def test_infer_path_characteristic():
    """测试路径特征推断"""
    print("\n[TEST] Infer Path Characteristic")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 测试 Lock_Contention
    hotspot_lock = MockHotspotItem("_raw_spin_lock", 40.0, 40.0)
    char = tracer._infer_path_characteristic_from_hotspot(["main", "lock"], hotspot_lock)
    assert char == "Lock_Contention"
    print(f"  ✓ Lock_Contention: {char}")
    
    # 测试 Syscall_Bound
    hotspot_syscall = MockHotspotItem("syscall_entry", 10.0, 10.0)
    char = tracer._infer_path_characteristic_from_hotspot(["main", "syscall"], hotspot_syscall)
    assert char == "Syscall_Bound"
    print(f"  ✓ Syscall_Bound: {char}")
    
    # 测试 High_Frequency_Exclusive_CPU (self >> inclusive)
    hotspot_exclusive = MockHotspotItem("compute", 50.0, 20.0)
    char = tracer._infer_path_characteristic_from_hotspot(["main", "compute"], hotspot_exclusive)
    assert char == "High_Frequency_Exclusive_CPU"
    print(f"  ✓ High_Frequency_Exclusive_CPU: {char}")
    
    # 测试 Inclusive_Latency_Victim (inclusive >> self)
    hotspot_victim = MockHotspotItem("wait_queue", 5.0, 60.0)
    char = tracer._infer_path_characteristic_from_hotspot(["main", "wait"], hotspot_victim)
    assert char == "Inclusive_Latency_Victim"
    print(f"  ✓ Inclusive_Latency_Victim: {char}")


def test_trace_full_flow():
    """测试完整分析流程"""
    print("\n[TEST] Full Trace Flow")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    # 创建模拟样本
    samples = [
        MockSample(comm="test_app", pid="1001", cpu=0, ts=1000.0),
        MockSample(comm="test_app", pid="1001", cpu=0, ts=1001.0),
        MockSample(comm="test_app", pid="1002", cpu=0, ts=1002.0),
    ]
    
    result = tracer.trace(samples, target_comm="test_app")
    
    # 验证结果结构
    assert isinstance(result, BottleneckTraceResult)
    assert result._risk is not None
    assert result.total_pids >= 0
    assert result.sample_count == 3
    
    print(f"  ✓ 分析完成")
    print(f"    - Risk Level: {result._risk.level}")
    print(f"    - Total PIDs: {result.total_pids}")
    print(f"    - Entity Distribution: {len(result.entity_distribution)} 项")
    print(f"    - Clusters: {len(result.clusters)} 个")
    print(f"    - Correlation Flags: {len(result.correlation_flags)} 个")


def test_create_adapter_convenience():
    """测试便捷函数 create_adapter"""
    print("\n[TEST] Convenience Function: create_adapter")
    
    facade = MockFacade()
    tracer = create_adapter(facade)
    
    assert isinstance(tracer, BottleneckTraceAdapter)
    assert tracer._facade == facade
    
    print("  ✓ create_adapter 返回正确的实例")


def test_run_bottleneck_trace_convenience():
    """测试便捷函数 run_bottleneck_trace"""
    print("\n[TEST] Convenience Function: run_bottleneck_trace")
    
    facade = MockFacade()
    samples = [MockSample(comm="test_app", pid="1001", cpu=0, ts=1000.0)]
    
    result = run_bottleneck_trace(facade, samples, target_comm="test_app")
    
    assert isinstance(result, BottleneckTraceResult)
    
    print("  ✓ run_bottleneck_trace 返回正确的结果")


def test_empty_samples():
    """测试空样本处理"""
    print("\n[TEST] Empty Samples Handling")
    
    facade = MockFacade()
    tracer = BottleneckTraceAdapter(facade)
    
    result = tracer.trace([])
    
    assert result._risk.level == "info"
    assert "无样本数据" in result._risk.message
    assert result.sample_count == 0
    
    print("  ✓ 空样本正确处理")


# =============================================================================
# Main
# =============================================================================

def main():
    """运行所有测试"""
    print("=" * 60)
    print("BottleneckTraceAdapter 单元测试")
    print("=" * 60)
    
    tests = [
        test_entity_distribution_dataclass,
        test_call_path_cluster_dataclass,
        test_correlation_flag_dataclass,
        test_bottleneck_trace_result_dataclass,
        test_affinity_pattern_fixed,
        test_affinity_pattern_uniform,
        test_affinity_pattern_scattered,
        test_detect_correlation_flags,
        test_find_common_hotspot,
        test_infer_path_characteristic,
        test_create_adapter_convenience,
        test_run_bottleneck_trace_convenience,
        test_empty_samples,
        test_trace_full_flow,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ 断言失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ 异常: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
