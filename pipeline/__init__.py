"""
SPEAR Agent Pipeline - 多轮诊断-审计-复查流水线

提供三轮 Agent 协作架构：
- Round 1: DiagnoseAgent - 执行 SPEAR 诊断流程
- Round 2: AuditAgent - 审计诊断质量
- Round 3: RecheckAgent - 根据审计结果复查

用法:
    from pipeline import PipelineController, PipelineConfig
    
    config = PipelineConfig(max_rounds=2)
    controller = PipelineController(config)
    controller.init(perf_data="perf.data", symptom="CPU高", work_dir="./case")
    
    result = controller.run(
        diagnose_agent=DiagnoseAgent(),
        audit_agent=AuditAgent(),
        recheck_agent=RecheckAgent()
    )
"""

from .controller import PipelineController, PipelineConfig, PipelineContext, PipelineStatus
from .agents import DiagnoseAgent, AuditAgent, RecheckAgent

__all__ = [
    'PipelineController',
    'PipelineConfig',
    'PipelineContext',
    'PipelineStatus',
    'DiagnoseAgent',
    'AuditAgent',
    'RecheckAgent',
]

__version__ = '1.0.0'
