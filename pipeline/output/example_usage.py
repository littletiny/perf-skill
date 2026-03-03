#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BottleneckTraceOutputBuilder 使用示例

展示如何使用输出格式化模块生成四段式报告。
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from perf_toolkit.core.models import RiskInfo, TimeRange
from output.bottleneck_trace_builder import (
    BottleneckTraceOutputBuilder,
    BottleneckTraceResult,
    EntityDistribution,
    CallPathCluster,
    CorrelationFlag,
)


def create_sample_result() -> BottleneckTraceResult:
    """创建示例 BottleneckTraceResult"""
    
    # 实体分布
    entities = [
        EntityDistribution(
            comm="app_B",
            count=1,
            incl_saliency=0.96,
            excl_saliency=0.12,
            core_affinity="Fixed: [Core_4]",
            throttle_rate=82.5
        ),
        EntityDistribution(
            comm="lsof",
            count=2000,
            incl_saliency=0.45,
            excl_saliency=0.88,
            core_affinity="Uniform: [Core_0-255]",
            throttle_rate=5.2
        ),
        EntityDistribution(
            comm="others",
            count=420,
            incl_saliency=0.02,
            excl_saliency=0.01,
            core_affinity="Scattered",
            throttle_rate=0.0
        ),
    ]
    
    # 调用路径聚类
    clusters = [
        CallPathCluster(
            cluster_id="lsof Cluster 68%",
            comm="lsof",
            weight=68.0,
            path=["lsof", "vfs_read", "iterate_dir", "__d_lookup_rcu"],
            hotspot="_raw_spin_lock",
            characteristic="High_Frequency_Exclusive_CPU"
        ),
        CallPathCluster(
            cluster_id="appB single/serval 28%",
            comm="app_B",
            weight=28.0,
            path=["app_B", "handle_request", "write_log", "__cfs_rq_runtime_get"],
            hotspot="_raw_spin_lock",
            characteristic="Inclusive_Latency_Victim"
        ),
    ]
    
    # 关联标志
    flags = [
        CorrelationFlag(
            flag_type="GLOBAL_LOCK_CONTENTION",
            target="_raw_spin_lock",
            message="usage exceeds 40% of sys time",
            severity="critical"
        ),
        CorrelationFlag(
            flag_type="SINGLE_CORE_SATURATION",
            target="Core_4",
            message="utilization 98.5%, Monopoly 0.96",
            severity="critical"
        ),
        CorrelationFlag(
            flag_type="THROTTLE_VICTIM",
            target="app_B",
            message="throttled 82.5% of observation window",
            severity="warning"
        ),
        CorrelationFlag(
            flag_type="STORM_PATTERN",
            target="lsof",
            message="spawn rate 450/s, PID count 2000+",
            severity="warning"
        ),
    ]
    
    # RiskInfo
    risk = RiskInfo(
        level="critical",
        message="发现严重 CPU 瓶颈: app_B 单核饱和",
        hint="find-callers --target _raw_spin_lock --comm app_B",
        patterns=["SINGLE_CORE_SATURATION", "LOCK_CONTENTION"]
    )
    
    # 时间范围
    time_range = TimeRange(
        start_time="2026-03-01T10:00:00+08:00",
        end_time="2026-03-01T10:01:00+08:00",
        duration=60.0
    )
    
    return BottleneckTraceResult(
        _risk=risk,
        entity_distribution=entities,
        common_hotspot="_raw_spin_lock",
        common_hotspot_weight=72.4,
        clusters=clusters,
        correlation_flags=flags,
        total_pids=2421,
        total_sys_cpu=165.2,
        top_bottlenecks=["_raw_spin_lock", "cgroup_try_mem_free", "futex_wait"],
        duration_sec=60.0,
        sample_count=31500,
        time_range=time_range
    )


def main():
    """主函数 - 展示输出效果"""
    print("=" * 80)
    print("BottleneckTraceOutputBuilder 使用示例")
    print("=" * 80)
    print()
    
    # 创建示例数据
    result = create_sample_result()
    
    # 使用 BottleneckTraceOutputBuilder 构建输出
    builder = BottleneckTraceOutputBuilder(result)
    output = builder.build()
    
    # 打印输出
    print(output)
    
    print("=" * 80)
    print("示例完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
