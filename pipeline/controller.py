"""
Pipeline Controller - 多轮 Agent 流水线控制器

管理诊断-审计-复查的生命周期，控制数据流和终止条件。
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """流水线状态"""
    IDLE = "idle"
    ROUND1_DIAGNOSING = "round1_diagnosing"
    ROUND2_AUDITING = "round2_auditing"
    ROUND3_RECHECKING = "round3_rechecking"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class PipelineConfig:
    """流水线配置"""
    max_rounds: int = 2  # 最多几轮（诊断+审计算一轮）
    timeout_seconds: int = 3600
    strict_audit: bool = True
    auto_recheck: bool = True  # 审计失败自动进入复查轮
    save_intermediate: bool = True  # 保存中间结果
    
    def to_dict(self) -> Dict:
        return {
            'max_rounds': self.max_rounds,
            'timeout_seconds': self.timeout_seconds,
            'strict_audit': self.strict_audit,
            'auto_recheck': self.auto_recheck,
            'save_intermediate': self.save_intermediate
        }


@dataclass
class PipelineContext:
    """流水线上下文"""
    perf_data: str
    symptom: str
    work_dir: str
    round_num: int = 0
    status: PipelineStatus = PipelineStatus.IDLE
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'perf_data': self.perf_data,
            'symptom': self.symptom,
            'work_dir': self.work_dir,
            'round_num': self.round_num,
            'status': self.status.value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'artifacts': self.artifacts
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PipelineContext':
        return cls(
            perf_data=data['perf_data'],
            symptom=data['symptom'],
            work_dir=data['work_dir'],
            round_num=data.get('round_num', 0),
            status=PipelineStatus(data.get('status', 'idle')),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            artifacts=data.get('artifacts', {})
        )


class PipelineController:
    """
    SPEAR Agent Pipeline 控制器
    
    管理三轮 Agent 的调度：
    1. Round 1: DiagnoseAgent - 执行诊断，生成 .spear.json
    2. Round 2: AuditAgent - 审计质量，生成 audit_report.json
    3. Round 3: RecheckAgent - 复查修复，生成 final_report.json
    
    终止条件：
    - 审计通过（audit_passed=true）
    - 达到最大轮数
    - 超时
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.context: Optional[PipelineContext] = None
        self._diagnose_agent: Optional['DiagnoseAgent'] = None
        self._audit_agent: Optional['AuditAgent'] = None
        self._recheck_agent: Optional['RecheckAgent'] = None
        
    def init(self, perf_data: str, symptom: str, work_dir: str) -> 'PipelineController':
        """
        初始化流水线上下文
        
        Args:
            perf_data: perf 数据文件路径
            symptom: 故障症状描述
            work_dir: 工作目录
        """
        os.makedirs(work_dir, exist_ok=True)
        
        self.context = PipelineContext(
            perf_data=perf_data,
            symptom=symptom,
            work_dir=work_dir
        )
        self.context.start_time = datetime.now().isoformat()
        
        logger.info(f"Pipeline initialized: work_dir={work_dir}")
        return self
    
    def load(self, state_file: str) -> 'PipelineController':
        """从状态文件恢复流水线"""
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        self.context = PipelineContext.from_dict(data['context'])
        self.config = PipelineConfig(**data['config'])
        
        logger.info(f"Pipeline loaded from {state_file}")
        return self
    
    def save(self) -> str:
        """保存流水线状态"""
        if not self.context:
            raise ValueError("Pipeline not initialized")
        
        state_file = os.path.join(self.context.work_dir, 'pipeline_state.json')
        data = {
            'version': '1.0',
            'config': self.config.to_dict(),
            'context': self.context.to_dict()
        }
        
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Pipeline state saved to {state_file}")
        return state_file
    
    def run_round1_diagnose(self, agent: 'DiagnoseAgent') -> Dict:
        """
        执行第一轮：诊断
        
        Args:
            agent: DiagnoseAgent 实例
            
        Returns:
            诊断结果字典
        """
        if not self.context:
            raise ValueError("Pipeline not initialized. Call init() first.")
        
        self.context.status = PipelineStatus.ROUND1_DIAGNOSING
        self.context.round_num = 1
        
        logger.info("=" * 60)
        logger.info("ROUND 1: DIAGNOSING")
        logger.info("=" * 60)
        
        result = agent.run(
            perf_data=self.context.perf_data,
            symptom=self.context.symptom,
            work_dir=self.context.work_dir
        )
        
        # 记录产物
        self.context.artifacts['round1'] = {
            'spear_json': result.get('spear_json'),
            'debug_dir': result.get('debug_dir'),
            'issues_count': result.get('issues_count', 0),
            'completed_count': result.get('completed_count', 0)
        }
        
        if self.config.save_intermediate:
            self.save()
        
        logger.info(f"Round 1 completed: {result.get('completed_count', 0)}/{result.get('issues_count', 0)} issues resolved")
        return result
    
    def run_round2_audit(self, agent: 'AuditAgent') -> Dict:
        """
        执行第二轮：审计
        
        Args:
            agent: AuditAgent 实例
            
        Returns:
            审计结果字典
        """
        if not self.context:
            raise ValueError("Pipeline not initialized")
        
        self.context.status = PipelineStatus.ROUND2_AUDITING
        
        logger.info("=" * 60)
        logger.info("ROUND 2: AUDITING")
        logger.info("=" * 60)
        
        round1 = self.context.artifacts.get('round1', {})
        spear_json = round1.get('spear_json')
        debug_dir = round1.get('debug_dir')
        
        if not spear_json or not os.path.exists(spear_json):
            raise FileNotFoundError(f"Round 1 output not found: {spear_json}")
        
        result = agent.run(
            spear_json=spear_json,
            debug_dir=debug_dir,
            strict=self.config.strict_audit
        )
        
        audit_passed = result.get('overall_status') == 'passed'
        
        self.context.artifacts['round2'] = {
            'audit_report': result.get('audit_report'),
            'passed': audit_passed,
            'summary': result.get('summary', {}),
            'gaps': result.get('gaps', [])
        }
        
        if self.config.save_intermediate:
            self.save()
        
        logger.info(f"Round 2 completed: passed={audit_passed}, "
                   f"issues={result.get('summary', {}).get('total_issues', 0)}, "
                   f"failed={result.get('summary', {}).get('failed', 0)}")
        return result
    
    def run_round3_recheck(self, agent: 'RecheckAgent') -> Dict:
        """
        执行第三轮：复查
        
        Args:
            agent: RecheckAgent 实例
            
        Returns:
            复查结果字典
        """
        if not self.context:
            raise ValueError("Pipeline not initialized")
        
        self.context.status = PipelineStatus.ROUND3_RECHECKING
        self.context.round_num = 3
        
        logger.info("=" * 60)
        logger.info("ROUND 3: RECHECKING")
        logger.info("=" * 60)
        
        round1 = self.context.artifacts.get('round1', {})
        round2 = self.context.artifacts.get('round2', {})
        
        result = agent.run(
            audit_report=round2.get('audit_report'),
            spear_json=round1.get('spear_json'),
            perf_data=self.context.perf_data,
            work_dir=self.context.work_dir,
            gaps=round2.get('gaps', [])
        )
        
        self.context.artifacts['round3'] = {
            'final_report': result.get('final_report'),
            'enhancements': result.get('enhancements', []),
            'verification_status': result.get('verification_status', 'unknown')
        }
        
        if self.config.save_intermediate:
            self.save()
        
        logger.info(f"Round 3 completed: enhancements={len(result.get('enhancements', []))}")
        return result
    
    def should_continue(self) -> bool:
        """
        判断是否继续下一轮
        
        返回 False 如果：
        - 审计通过
        - 未配置自动复查
        - 已达到最大轮数
        """
        round2 = self.context.artifacts.get('round2', {})
        
        # 审计通过，无需继续
        if round2.get('passed'):
            logger.info("Audit passed, no need for recheck")
            return False
        
        # 未配置自动复查
        if not self.config.auto_recheck:
            logger.info("Auto recheck disabled")
            return False
        
        # 检查最大轮数
        # 当前 round_num: 1=诊断, 2=审计, 3=复查
        # 最大轮数 2 意味着可以执行 诊断+审计+复查（3轮）
        max_round_num = self.config.max_rounds * 2 - 1
        if self.context.round_num >= max_round_num:
            logger.info(f"Max rounds reached ({self.config.max_rounds})")
            return False
        
        # 检查是否有 gaps 需要修复
        gaps = round2.get('gaps', [])
        if not gaps:
            logger.info("No gaps to fix")
            return False
        
        return True
    
    def run(self, 
            diagnose_agent: 'DiagnoseAgent',
            audit_agent: 'AuditAgent',
            recheck_agent: Optional['RecheckAgent'] = None) -> Dict:
        """
        运行完整流水线
        
        Args:
            diagnose_agent: 诊断 Agent
            audit_agent: 审计 Agent
            recheck_agent: 复查 Agent（可选，审计失败时进入复查轮）
            
        Returns:
            流水线执行结果
        """
        if not self.context:
            raise ValueError("Pipeline not initialized. Call init() first.")
        
        self._diagnose_agent = diagnose_agent
        self._audit_agent = audit_agent
        self._recheck_agent = recheck_agent
        
        try:
            # Round 1: 诊断
            round1_result = self.run_round1_diagnose(diagnose_agent)
            
            # Round 2: 审计
            audit_result = self.run_round2_audit(audit_agent)
            
            # Round 3: 复查（如果需要且配置了）
            if self.should_continue() and recheck_agent:
                recheck_result = self.run_round3_recheck(recheck_agent)
                
                # 复查后可选择再次审计（简化版，可选）
                # if self.config.double_check:
                #     self.run_round2_audit(audit_agent)
            
            # 完成
            self.context.status = PipelineStatus.COMPLETED
            self.context.end_time = datetime.now().isoformat()
            
            # 生成最终报告
            final_result = self._generate_final_report()
            
            self.save()
            
            return final_result
            
        except Exception as e:
            self.context.status = PipelineStatus.FAILED
            self.context.end_time = datetime.now().isoformat()
            self.save()
            logger.error(f"Pipeline failed: {e}")
            raise
    
    def _generate_final_report(self) -> Dict:
        """生成最终报告"""
        round1 = self.context.artifacts.get('round1', {})
        round2 = self.context.artifacts.get('round2', {})
        round3 = self.context.artifacts.get('round3', {})
        
        report = {
            'pipeline_version': '1.0',
            'status': 'completed',
            'context': {
                'perf_data': self.context.perf_data,
                'symptom': self.context.symptom,
                'work_dir': self.context.work_dir,
                'total_rounds': self.context.round_num,
                'duration': {
                    'start': self.context.start_time,
                    'end': self.context.end_time
                }
            },
            'diagnosis': {
                'issues_count': round1.get('issues_count', 0),
                'resolved_count': round1.get('completed_count', 0),
                'spear_json': round1.get('spear_json'),
                'debug_dir': round1.get('debug_dir')
            },
            'audit': {
                'passed': round2.get('passed', False),
                'summary': round2.get('summary', {}),
                'audit_report': round2.get('audit_report')
            },
            'recheck': round3 if round3 else None,
            'final_status': 'success' if round2.get('passed') or round3 else 'needs_review'
        }
        
        # 保存最终报告
        report_path = os.path.join(self.context.work_dir, 'pipeline_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Status: {report['final_status']}")
        logger.info(f"Audit passed: {report['audit']['passed']}")
        logger.info(f"Report: {report_path}")
        
        return report
    
    def get_status(self) -> Dict:
        """获取当前流水线状态"""
        if not self.context:
            return {'status': 'not_initialized'}
        
        return {
            'status': self.context.status.value,
            'round': self.context.round_num,
            'artifacts': list(self.context.artifacts.keys()),
            'context': self.context.to_dict()
        }
