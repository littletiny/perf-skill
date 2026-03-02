# SPEAR 多轮 Agent 流水线设计

> 设计文档：三轮诊断-审计-复查流水线架构
> 版本: 1.0
> 创建时间: 2026-03-02

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SPEAR Agent Pipeline v1.0                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │  Round 1     │     │  Round 2     │     │  Round 3     │             │
│  │  诊断轮       │ ──→ │  审计轮       │ ──→ │  复查轮       │             │
│  │  (Diagnose)  │     │  (Audit)     │     │  (Recheck)   │             │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘             │
│         │                    │                    │                     │
│    输入: perf.data      输入: .spear.json    输入: audit_report.json    │
│         + 症状描述           + timeline           + gaps_found          │
│                              + issues             + original_data       │
│         ↓                    ↓                    ↓                     │
│    输出: .spear.json    输出: audit_report    输出: final_report        │
│         + debug/*.md         (通过/失败/建议)      + 确认/修正结论        │
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════    │
│  终止条件: audit_passed=true  OR  max_rounds=2 (防止无限循环)             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 流水线数据流

### 2.1 数据流转图

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Shared Context                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  context/   │  │  context/   │  │  context/   │  │  context/   │   │
│  │  perf.data  │  │  .spear.json│  │  audit_rpt  │  │  final_rpt  │   │
│  │  (原始数据)  │  │  (trace记录)│  │  (审计报告)  │  │  (最终报告)  │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│         ↑               ↑               ↑               ↑              │
└─────────┼───────────────┼───────────────┼───────────────┼──────────────┘
          │               │               │               │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │  Agent 1  │   │  Agent 2  │   │  Agent 3  │   │  Final    │
    │  Diagnose │ → │  Audit    │ → │  Recheck  │ → │  Export   │
    │  (诊断员)  │   │  (审计员)  │   │  (复查员)  │   │  (报告)   │
    └───────────┘   └───────────┘   └───────────┘   └───────────┘
          │               │               │
          └───────────────┴───────────────┘
                      ↓
            ┌─────────────────┐
            │   Controller    │
            │  (流水线控制器)  │
            └─────────────────┘
```

### 2.2 各轮数据格式

#### Round 1 输出: `.spear.json`

```json
{
  "version": "2.0",
  "data_file": "perf.data",
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:30:00Z",
  "timeline": [
    {
      "seq": 1,
      "type": "command",
      "command": "get-comm-top --data perf.data",
      "timestamp": "2026-03-02T10:00:00Z",
      "findings": [
        {
          "type": "risk_created",
          "level": "warning",
          "desc": "netstat 高内核态 94.7%",
          "issue_id": "ISS-001"
        }
      ]
    },
    {
      "seq": 2,
      "type": "command",
      "command": "cluster-symbols --comm netstat",
      "timestamp": "2026-03-02T10:05:00Z",
      "findings": [
        {
          "type": "info",
          "message": "LOCK_CONTENTION 38.36%"
        }
      ]
    }
  ],
  "issues": {
    "ISS-001": {
      "id": "ISS-001",
      "desc": "netstat 高内核态 94.7%",
      "level": "warning",
      "status": "resolved",
      "created_at": "2026-03-02T10:00:00Z",
      "created_by_seq": 1,
      "resolved_at": "2026-03-02T10:05:00Z",
      "resolved_by_seq": 2,
      "result": "根因: /proc/net/tcp 锁竞争，详见 debug/netstat_analysis.md"
    }
  },
  "round_info": {
    "round": 1,
    "agent": "diagnose",
    "symptom": "系统响应慢，CPU高"
  }
}
```

#### Round 2 输出: `audit_report.json`

```json
{
  "audit_time": "2026-03-02T10:35:00Z",
  "auditor": "audit_agent_v1",
  "source_round": 1,
  "summary": {
    "total_issues": 3,
    "passed": 2,
    "failed": 1,
    "warnings": 0,
    "pass_rate": "66.7%"
  },
  "checks": {
    "structural": {
      "status": "passed",
      "items": [
        {"check": "all_resolved_have_result", "status": "passed"},
        {"check": "no_empty_result", "status": "passed"}
      ]
    },
    "timeline": {
      "status": "passed",
      "items": [
        {"check": "has_analysis_commands", "status": "passed"},
        {"check": "result_consistency", "status": "passed"}
      ]
    },
    "depth": {
      "status": "failed",
      "items": [
        {"check": "three_hypotheses", "status": "failed", "issue": "ISS-002"},
        {"check": "driver_analysis", "status": "passed"},
        {"check": "trace_to_source", "status": "warning", "issue": "ISS-003"}
      ]
    },
    "documentation": {
      "status": "passed",
      "items": [
        {"check": "debug_md_exists", "status": "passed"},
        {"check": "hypothesis_table", "status": "passed"}
      ]
    }
  },
  "failed_issues": [
    {
      "id": "ISS-002",
      "reason": "缺少三候选假设验证",
      "current_result": "锁竞争导致性能下降",
      "expected": "应列出被排除的假设，如算法复杂度、资源配置等",
      "severity": "critical",
      "action": "reopen_and_enhance"
    }
  ],
  "warnings": [
    {
      "id": "ISS-003",
      "reason": "溯源深度不足",
      "detail": "未使用 find-callers 定位调用链",
      "severity": "warning",
      "action": "suggest_enhance"
    }
  ],
  "gaps": [
    {
      "type": "missing_hypotheses",
      "issue_id": "ISS-002",
      "suggestion": "补充架构维度和环境维度的假设验证"
    },
    {
      "type": "insufficient_trace",
      "issue_id": "ISS-003",
      "suggestion": "执行 find-callers --target <lock_func>"
    }
  ],
  "overall_status": "failed",
  "recommendation": "需要复查轮补充分析"
}
```

#### Round 3 输出: `final_report.json`

```json
{
  "report_time": "2026-03-02T11:00:00Z",
  "round": 3,
  "previous_audit": "audit_report.json",
  "summary": {
    "original_issues": 3,
    "enhanced_issues": 2,
    "confirmed_issues": 3,
    "final_conclusion": "confirmed"
  },
  "enhancements": [
    {
      "issue_id": "ISS-002",
      "enhancement": "补充三候选假设验证",
      "original": "锁竞争导致性能下降",
      "enhanced": "根因为锁竞争（排除算法复杂度、排除CPU限制）- 详见假设追踪表",
      "verification": "confirmed"
    },
    {
      "issue_id": "ISS-003",
      "enhancement": "补充调用链溯源",
      "action": "执行 find-callers --target pthread_mutex_lock",
      "result": "定位到 mysql_query 调用路径",
      "verification": "confirmed"
    }
  ],
  "conclusions": [
    {
      "issue_id": "ISS-001",
      "root_cause": "netstat 进程风暴导致 /proc/net/tcp 锁竞争",
      "confidence": "high"
    },
    {
      "issue_id": "ISS-002",
      "root_cause": "containerd-shim 频繁状态检查引发内核态开销",
      "confidence": "high"
    }
  ],
  "pipeline_meta": {
    "total_rounds": 3,
    "audit_passed": true,
    "termination_reason": "audit_passed"
  }
}
```

---

## 3. Agent 角色定义

### 3.1 Round 1: 诊断 Agent (DiagnoseAgent)

**角色描述**: 执行 SPEAR 诊断流程，记录完整 trace

**输入**:
```json
{
  "perf_data": "path/to/perf.data",
  "symptom": "用户描述的故障症状",
  "context": "额外上下文信息"
}
```

**执行流程**:
1. 初始化 trace: `spear trace init --data perf.data`
2. 执行标准 SPEAR 诊断流程（7 Phase）
3. 自动记录每个命令执行到 timeline
4. 对每个 issue 进行分析和 complete
5. 生成 debug/*.md 诊断文档

**输出**: `.spear.json` + `debug/*.md`

**系统 Prompt 核心**:
```
你是一个 SPEAR 性能诊断专家。你的任务是：
1. 严格遵循 SPEAR 7 Phase 诊断流程
2. 每执行一个诊断命令，确保 trace 自动记录
3. 对每个发现的 issue，必须提供详细的分析结果
4. 在 debug/*.md 中维护三候选假设追踪表
5. 完成所有 open issues 后才能结束

约束：
- result 不能为空或敷衍（如"ok"/"done"）
- 必须引用具体的 debug/*.md 文档
- 必须体现因果推导过程
```

---

### 3.2 Round 2: 审计 Agent (AuditAgent)

**角色描述**: 独立审计员，验证诊断质量

**输入**:
```json
{
  "spear_json": ".spear.json",
  "debug_dir": "debug/",
  "audit_config": {
    "phases": ["structural", "timeline", "depth", "documentation"],
    "strict_mode": true
  }
}
```

**执行流程**:
1. 读取 `.spear.json` 解析 timeline 和 issues
2. 执行四阶段检查（见下方）
3. 对每个 issue 生成审计结果
4. 识别 gaps 并生成改进建议
5. 输出 audit_report.json

**四阶段检查**:

| 阶段 | 检查项 | 失败处理 |
|------|--------|---------|
| **Phase 1: 结构完整性** | result 非空、非敷衍标记 | Critical - 必须 reopen |
| **Phase 2: Timeline 关联** | 有 analysis commands 支撑 | Failed - 要求补充分析 |
| **Phase 3: 分析深度** | 三候选假设、驱动力、溯源 | Failed - 要求增强 |
| **Phase 4: 文档一致性** | debug/*.md 存在且完整 | Warning - 建议完善 |

**输出**: `audit_report.json`

**系统 Prompt 核心**:
```
你是一个独立的 SPEAR 诊断审计员。你的任务是：
1. 客观验证第一轮诊断的质量
2. 检查结构完整性、timeline 关联、分析深度、文档一致性
3. 识别任何敷衍或不完整的分析
4. 生成明确的 gaps 列表和改进建议

原则：
- 你是独立审计员，不是诊断工程师
- 严格要求三候选准则和因果推导
- 任何不合格的分析都必须标记为 failed
- 提供具体的修复建议
```

---

### 3.3 Round 3: 复查 Agent (RecheckAgent)

**角色描述**: 根据审计结果补充分析和验证

**输入**:
```json
{
  "audit_report": "audit_report.json",
  "spear_json": ".spear.json",
  "perf_data": "path/to/perf.data",
  "gaps": [
    {"type": "missing_hypotheses", "issue_id": "ISS-002"},
    {"type": "insufficient_trace", "issue_id": "ISS-003"}
  ]
}
```

**执行流程**:
1. 读取 audit_report 识别 failed/warning issues
2. 针对每个 gap 补充分析
3. 更新 `.spear.json` 中的 issue result
4. 更新 debug/*.md 诊断文档
5. 验证所有问题是否已充分解决
6. 生成 final_report.json

**输出**: 更新后的 `.spear.json` + `final_report.json`

**系统 Prompt 核心**:
```
你是一个 SPEAR 诊断复查专家。你的任务是：
1. 根据审计报告中的 gaps 补充分析
2. 对标记为 failed 的 issue 进行深度增强
3. 验证三候选假设是否完整
4. 补充缺失的溯源分析（如 find-callers）
5. 确保所有结论都有充分证据支撑

约束：
- 必须解决所有 audit failed 的问题
- 更新 result 时要引用分析命令和时间线
- 保持与原始诊断的连贯性
- 最终结论必须明确、可验证
```

---

## 4. 流水线控制器 (PipelineController)

### 4.1 职责

- 管理多轮 Agent 的调度
- 维护共享上下文
- 决定终止条件
- 处理异常和重试

### 4.2 状态机

```
                    ┌─────────────┐
                    │    Idle     │
                    └──────┬──────┘
                           │ init()
                           ↓
                    ┌─────────────┐
           ┌──────→│   Round 1   │────────┐
           │       │  Diagnosing │        │
           │       └─────────────┘        │
           │              │               │
           │       completed              │
           │              ↓               │
           │       ┌─────────────┐        │
           │       │   Round 2   │        │
           │       │   Auditing  │        │
           │       └──────┬──────┘        │
           │              │               │
           │    ┌─────────┴─────────┐     │
           │    │                   │     │
           │ failed              passed    │
           │    │                   │      │
           │    ↓                   ↓      │
           │ ┌─────────┐      ┌─────────┐  │
           └─┤ Round 3 │      │  Final  │←─┘
             │ Recheck │      │ Export  │
             └────┬────┘      └─────────┘
                  │
            completed
                  ↓
             ┌─────────┐
             │  Final  │
             │ Export  │
             └─────────┘
```

### 4.3 终止条件

| 条件 | 说明 | 输出 |
|------|------|------|
| `audit_passed=true` | 第二轮审计通过 | 直接生成最终报告 |
| `max_rounds=2` | 已完成两轮（诊断+审计+复查）| 生成最终报告（含风险提示）|
| `no_improvement` | 复查轮未解决任何问题 | 终止并标记为 failed |
| `timeout` | 总耗时超过阈值 | 终止并标记为 timeout |

### 4.4 Python 实现框架

```python
# pipeline/controller.py

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import json


class PipelineStatus(Enum):
    IDLE = "idle"
    ROUND1_DIAGNOSING = "round1_diagnosing"
    ROUND2_AUDITING = "round2_auditing"
    ROUND3_RECHECKING = "round3_rechecking"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    max_rounds: int = 2  # 最多几轮（诊断+审计算一轮）
    timeout_seconds: int = 3600
    strict_audit: bool = True
    auto_recheck: bool = True  # 审计失败自动进入复查轮


@dataclass
class PipelineContext:
    perf_data: str
    symptom: str
    work_dir: str
    round_num: int = 0
    status: PipelineStatus = PipelineStatus.IDLE
    artifacts: Dict[str, str] = None  # 各轮输出文件路径
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = {}


class PipelineController:
    """SPEAR Agent Pipeline 控制器"""
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.context: Optional[PipelineContext] = None
        
    def init(self, perf_data: str, symptom: str, work_dir: str):
        """初始化流水线上下文"""
        self.context = PipelineContext(
            perf_data=perf_data,
            symptom=symptom,
            work_dir=work_dir
        )
        return self
    
    def run_round1_diagnose(self, agent: 'DiagnoseAgent') -> Dict:
        """执行第一轮诊断"""
        self.context.status = PipelineStatus.ROUND1_DIAGNOSING
        self.context.round_num = 1
        
        result = agent.run(
            perf_data=self.context.perf_data,
            symptom=self.context.symptom,
            work_dir=self.context.work_dir
        )
        
        self.context.artifacts['round1_spear_json'] = result['spear_json']
        self.context.artifacts['round1_debug_dir'] = result['debug_dir']
        
        return result
    
    def run_round2_audit(self, agent: 'AuditAgent') -> Dict:
        """执行第二轮审计"""
        self.context.status = PipelineStatus.ROUND2_AUDITING
        
        spear_json = self.context.artifacts['round1_spear_json']
        debug_dir = self.context.artifacts['round1_debug_dir']
        
        result = agent.run(
            spear_json=spear_json,
            debug_dir=debug_dir
        )
        
        self.context.artifacts['audit_report'] = result['audit_report']
        self.context.artifacts['audit_passed'] = result['overall_status'] == 'passed'
        
        return result
    
    def run_round3_recheck(self, agent: 'RecheckAgent') -> Dict:
        """执行第三轮复查"""
        self.context.status = PipelineStatus.ROUND3_RECHECKING
        self.context.round_num = 3
        
        result = agent.run(
            audit_report=self.context.artifacts['audit_report'],
            spear_json=self.context.artifacts['round1_spear_json'],
            perf_data=self.context.perf_data,
            work_dir=self.context.work_dir
        )
        
        self.context.artifacts['final_report'] = result['final_report']
        
        return result
    
    def should_continue(self) -> bool:
        """判断是否继续下一轮"""
        # 审计通过，无需继续
        if self.context.artifacts.get('audit_passed'):
            return False
        
        # 已达最大轮数
        if self.context.round_num >= self.config.max_rounds * 2 - 1:
            return False
        
        # 配置了自动复查
        if not self.config.auto_recheck:
            return False
        
        return True
    
    def run(self, 
            diagnose_agent: 'DiagnoseAgent',
            audit_agent: 'AuditAgent',
            recheck_agent: 'RecheckAgent') -> Dict:
        """运行完整流水线"""
        
        # Round 1: 诊断
        round1_result = self.run_round1_diagnose(diagnose_agent)
        
        # Round 2: 审计
        audit_result = self.run_round2_audit(audit_agent)
        
        # 判断是否进入 Round 3
        if self.should_continue():
            # Round 3: 复查
            final_result = self.run_round3_recheck(recheck_agent)
            
            # 可选：再次审计复查结果
            # second_audit = self.run_round2_audit(audit_agent)
        else:
            final_result = {
                'status': 'completed',
                'audit_passed': self.context.artifacts.get('audit_passed', False),
                'reason': 'audit_passed' if self.context.artifacts.get('audit_passed') else 'no_recheck_needed'
            }
        
        self.context.status = PipelineStatus.COMPLETED
        
        return {
            'context': self.context,
            'artifacts': self.context.artifacts,
            'final_status': 'success'
        }
```

---

## 5. 使用示例

### 5.1 完整流水线调用

```python
# 使用示例
from pipeline.controller import PipelineController, PipelineConfig
from pipeline.agents import DiagnoseAgent, AuditAgent, RecheckAgent

# 配置
config = PipelineConfig(
    max_rounds=2,
    strict_audit=True,
    auto_recheck=True
)

# 创建控制器
controller = PipelineController(config)
controller.init(
    perf_data="/path/to/perf.data",
    symptom="系统响应慢，CPU使用率100%",
    work_dir="./diagnosis_case_001"
)

# 创建 Agents
diagnose_agent = DiagnoseAgent(model="claude-3-5-sonnet")
audit_agent = AuditAgent(model="claude-3-5-sonnet")
recheck_agent = RecheckAgent(model="claude-3-5-sonnet")

# 运行流水线
result = controller.run(
    diagnose_agent=diagnose_agent,
    audit_agent=audit_agent,
    recheck_agent=recheck_agent
)

# 查看结果
print(f"最终状态: {result['final_status']}")
print(f"审计通过: {result['artifacts'].get('audit_passed')}")
print(f"最终报告: {result['artifacts'].get('final_report')}")
```

### 5.2 CLI 使用方式

```bash
# 运行完整流水线
spear pipeline run \
  --data perf.data \
  --symptom "系统响应慢" \
  --work-dir ./case_001 \
  --max-rounds 2

# 只运行诊断轮
spear pipeline diagnose \
  --data perf.data \
  --symptom "CPU高" \
  --output ./case_001

# 只运行审计轮（基于已有诊断）
spear pipeline audit \
  --spear-json ./case_001/.spear.json \
  --output ./case_001/audit_report.json

# 运行复查轮（基于审计结果）
spear pipeline recheck \
  --audit-report ./case_001/audit_report.json \
  --output ./case_001/final_report.json
```

---

## 6. 与其他组件的集成

### 6.1 与现有 spear trace 集成

```
┌─────────────────────────────────────────────────────────────┐
│                    现有 SPEAR Trace                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  init   │  │  add    │  │ complete│  │ finalize│        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       └─────────────┴─────────────┴─────────────┘           │
│                     ↓                                       │
│              ┌─────────────┐                                │
│              │ .spear.json │                                │
│              └─────────────┘                                │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │ 读取/写入
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Pipeline Agents                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DiagnoseAgent│  │ AuditAgent  │  │RecheckAgent │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Agent 调用现有工具

```python
# DiagnoseAgent 内部实现示例
class DiagnoseAgent:
    def run(self, perf_data: str, symptom: str, work_dir: str):
        # 1. 初始化
        self.run_spear_command(f"trace init --data {perf_data}")
        
        # 2. 执行诊断命令（自动记录到 trace）
        self.run_spear_command("get-comm-top")
        self.run_spear_command("check-cpu-bottleneck")
        
        # 3. 查看 open issues
        issues = self.run_spear_command("trace issues --status open --format json")
        
        # 4. 分析每个 issue 并 complete
        for issue in issues['pending']:
            self.analyze_issue(issue)
            self.run_spear_command(f"trace complete --id {issue['id']} --result '{result}'")
        
        # 5. 生成 debug/*.md
        self.generate_debug_doc()
        
        return {'spear_json': f'{work_dir}/.spear.json'}
```

---

## 7. 质量度量

### 7.1 流水线级指标

| 指标 | 计算方式 | 目标 |
|------|---------|------|
| 首次通过率 | audit_passed=true / 总运行数 | > 70% |
| 复查成功率 | 复查后通过 / 首次失败数 | > 90% |
| 平均轮数 | 总轮数 / 总运行数 | < 2.5 |
| 平均耗时 | 总耗时 / 总运行数 | < 30min |

### 7.2 Agent 级指标

| Agent | 指标 | 说明 |
|-------|------|------|
| DiagnoseAgent | issue 覆盖率 | 发现的真实问题 / 总问题 |
| DiagnoseAgent | result 完整度 | 有详细 result 的 issue / 总 issue |
| AuditAgent | 误报率 | 错误标记 failed / 总审计数 |
| AuditAgent | 漏检率 | 未发现的真正问题 / 总问题 |
| RecheckAgent | 修复成功率 | 成功修复的 gap / 总 gaps |

---

## 8. 参考文档

- [audit-process.md](./audit-process.md) - 审计流程详细规范
- [design-rationale-trace-v2.md](./design-rationale-trace-v2.md) - Trace v2.0 设计
- [trace-interface.md](./trace-interface.md) - Trace CLI 接口
- [../SKILL.md](../SKILL.md) - SPEAR 方法论
- [../references/workflow.md](../references/workflow.md) - 7 Phase 分析流程
