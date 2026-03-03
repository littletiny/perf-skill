#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster-paths 命令实现
"""

from perf_toolkit.cli.decorators import command
from perf_toolkit.cli.builders import create_risk_info
from perf_toolkit.core.output_models import (
    RiskInfo, RiskLevel, PathClusterItem, PathClusterSummary, PathClustersOutput, TimeRange
)
from perf_toolkit.analysis.path_clusters import PathClustersAnalyzer


@command("cluster-paths")
def cmd_cluster_paths(builder, engine, args, samples):
    """[Skill] Cluster samples by common call path prefixes"""
    
    analyzer = PathClustersAnalyzer(engine)
    result = analyzer.analyze(
        samples,
        top_n=getattr(args, 'top_n', 10),
        min_depth=getattr(args, 'min_depth', 2),
        min_samples=getattr(args, 'min_samples', 5)
    )
    
    for risk in result.risks:
        builder.record_risk(risk.level, risk.message, risk.hint)
    
    top_risk = None
    if result.risks:
        top_risk = min(result.risks, key=lambda r: RiskLevel.from_string(r.level).value)
    
    path_clusters = [
        PathClusterItem.from_raw(
            cluster_id=c.cluster_id,
            path_signature=c.path_signature,
            weight=c.weight,
            total_weight=result.total_weight,
            duration=getattr(args, 'duration', 1.0)
        )
        for c in result.clusters
    ]
    
    risk_output = create_risk_info(
        level=top_risk.level,
        message=top_risk.message,
        hint=top_risk.hint,
        patterns=top_risk.patterns,
        pending_targets=top_risk.pending_targets
    ) if top_risk else create_risk_info(level="none")
    
    output = PathClustersOutput(
        _risk=risk_output,
        path_clusters=path_clusters,
        summary=PathClusterSummary(
            total_clusters=result.total_clusters,
            shown_clusters=result.shown_clusters,
            clustered_weight=result.clustered_weight
        ),
        time_range=TimeRange.from_timestamps(
            samples[0].ts if samples else None,
            samples[-1].ts if len(samples) > 1 else None
        )
    )
    
    return output
