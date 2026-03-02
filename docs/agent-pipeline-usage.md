# Agent Pipeline 使用指南

> SPEAR 多轮流水线使用示例
> 版本: 1.0

---

## 1. 快速开始

### 1.1 完整流水线（推荐）

一键运行诊断-审计-复查三轮流水线：

```bash
cd /path/to/perf-hunter

python -m pipeline.cli run \
  --data /path/to/perf.data \
  --symptom "系统响应慢，CPU使用率100%" \
  --output ./case_001 \
  --max-rounds 2 \
  --auto-recheck
```

**输出结构**：
```
case_001/
├── .spear.json              # Round 1: 诊断 trace 记录
├── debug/
│   └── diagnosis_analysis.md # 诊断文档
├── audit_report.json         # Round 2: 审计报告
├── final_report.json         # Round 3: 复查报告（如需要）
├── pipeline_state.json       # 流水线状态
└── pipeline_report.json      # 最终汇总报告
```

---

## 2. 分步执行

### 2.1 第一轮：诊断

```bash
python -m pipeline.cli diagnose \
  --data perf.data \
  --symptom "MySQL 响应延迟高" \
  --output ./mysql_case
```

**输出**：
```
Running diagnosis...
  Data: perf.data
  Symptom: MySQL 响应延迟高
  Output: ./mysql_case

Diagnosis completed!
  Issues found: 3
  Resolved: 3
  Spear JSON: ./mysql_case/.spear.json
  Debug dir: ./mysql_case/debug
```

### 2.2 第二轮：审计

```bash
python -m pipeline.cli audit \
  --spear-json ./mysql_case/.spear.json \
  --strict
```

**输出示例**：
```
Running audit...
  Spear JSON: ./mysql_case/.spear.json

Audit completed!
  Status: failed
  Issues: 3
  Passed: 2
  Failed: 1
  Warnings: 0
  Report: ./mysql_case/audit_report.json

Gaps found (1):
  - missing_hypotheses: 补充架构维度和环境维度的假设验证
```

**审计失败时的 audit_report.json**：
```json
{
  "audit_time": "2026-03-02T15:00:00",
  "overall_status": "failed",
  "summary": {
    "total_issues": 3,
    "passed": 2,
    "failed": 1,
    "pass_rate": "66.7%"
  },
  "failed_issues": [
    {
      "id": "ISS-002",
      "check": "missing_hypotheses",
      "reason": "Result does not show three-hypothesis evaluation",
      "current_result": "锁竞争导致性能下降",
      "expected": "应体现三候选假设的验证过程"
    }
  ],
  "gaps": [
    {
      "type": "missing_hypotheses",
      "issue_id": "ISS-002",
      "suggestion": "补充架构维度和环境维度的假设验证"
    }
  ]
}
```

### 2.3 第三轮：复查

当审计失败时，运行复查轮：

```bash
python -m pipeline.cli recheck \
  --audit-report ./mysql_case/audit_report.json \
  --output ./mysql_case
```

**输出**：
```
Running recheck...
  Audit report: ./mysql_case/audit_report.json

Recheck completed!
  Status: completed
  Enhancements: 1
  Final report: ./mysql_case/final_report.json
```

---

## 3. Python API 使用

### 3.1 基础用法

```python
from pipeline import PipelineController, PipelineConfig
from pipeline.agents import DiagnoseAgent, AuditAgent, RecheckAgent

# 配置
config = PipelineConfig(
    max_rounds=2,
    strict_audit=True,
    auto_recheck=True
)

# 初始化控制器
controller = PipelineController(config)
controller.init(
    perf_data="/path/to/perf.data",
    symptom="系统响应慢，CPU高",
    work_dir="./case_001"
)

# 运行流水线
result = controller.run(
    diagnose_agent=DiagnoseAgent(),
    audit_agent=AuditAgent(),
    recheck_agent=RecheckAgent()
)

# 查看结果
print(f"状态: {result['final_status']}")
print(f"审计通过: {result['audit']['passed']}")
```

### 3.2 高级用法：自定义 Agent

```python
from pipeline.agents import DiagnoseAgent

class MyDiagnoseAgent(DiagnoseAgent):
    """自定义诊断 Agent，添加额外分析步骤"""
    
    def _execute_diagnosis(self, perf_data, symptom):
        # 调用父类标准流程
        findings = super()._execute_diagnosis(perf_data, symptom)
        
        # 添加自定义分析
        custom_result = self.run_spear_command(
            f"detect-anomalies --data {perf_data} --format json"
        )
        if custom_result:
            findings.append({
                'phase': 'custom',
                'tool': 'detect-anomalies',
                'result': custom_result
            })
        
        return findings

# 使用自定义 Agent
controller.run(
    diagnose_agent=MyDiagnoseAgent(),
    audit_agent=AuditAgent(),
    recheck_agent=RecheckAgent()
)
```

### 3.3 分步控制

```python
from pipeline import PipelineController, PipelineStatus

controller = PipelineController()
controller.init(
    perf_data="perf.data",
    symptom="CPU高",
    work_dir="./case"
)

# 只运行诊断轮
diagnose_agent = DiagnoseAgent()
round1_result = controller.run_round1_diagnose(diagnose_agent)

# 检查诊断结果
if round1_result['pending_count'] > 0:
    print(f"Warning: {round1_result['pending_count']} issues still open")

# 运行审计轮
audit_agent = AuditAgent()
audit_result = controller.run_round2_audit(audit_agent)

# 根据审计结果决定是否复查
if audit_result['overall_status'] == 'failed':
    print("Audit failed, running recheck...")
    recheck_agent = RecheckAgent()
    recheck_result = controller.run_round3_recheck(recheck_agent)
else:
    print("Audit passed!")

# 生成最终报告
final_report = controller._generate_final_report()
```

---

## 4. 流水线状态管理

### 4.1 保存和恢复

```python
# 运行中自动保存
controller.run(
    diagnose_agent=DiagnoseAgent(),
    audit_agent=AuditAgent(),
    recheck_agent=RecheckAgent()
)

# 手动保存状态
state_file = controller.save()
print(f"State saved to: {state_file}")

# 从状态恢复
new_controller = PipelineController()
new_controller.load(state_file)

# 查看状态
status = new_controller.get_status()
print(f"Current status: {status['status']}")
print(f"Current round: {status['round']}")
```

### 4.2 查看状态

```bash
python -m pipeline.cli status --state ./case_001/pipeline_state.json
```

**输出**：
```
Pipeline Status
============================================================
Status: completed
Round: 3
Work dir: ./case_001
Perf data: /path/to/perf.data
Symptom: 系统响应慢，CPU高
Start time: 2026-03-02T14:00:00
End time: 2026-03-02T14:30:00

Artifacts:
  - round1
  - round2
  - round3
```

---

## 5. 与 SPEAR 工具集成

### 5.1 现有 SPEAR 项目升级

如果你的项目已经有 SPEAR trace 记录，可以直接进行审计：

```bash
# 已有 .spear.json，直接审计
python -m pipeline.cli audit --spear-json ./.spear.json --strict
```

### 5.2 扩展现有 Agent

```python
from pipeline.agents import AuditAgent

class StrictAuditAgent(AuditAgent):
    """更严格的审计 Agent"""
    
    PERFUNCTORY_MARKS = ['ok', 'done', 'fixed', 'completed', 'yes', 'no', '', 
                         'good', 'okok', 'done.']  # 扩展敷衍标记列表
    
    def _check_depth(self, issues, debug_dir):
        result = super()._check_depth(issues, debug_dir)
        
        # 额外检查：要求必须有驱动力分析
        for issue_id, issue in issues.items():
            result_text = issue.get('result', '')
            has_driver = any(kw in result_text for kw in 
                           ['驱动', '流量', '请求', 'driver', 'workload'])
            if not has_driver:
                result['warnings'].append({
                    'id': issue_id,
                    'check': 'missing_driver_analysis',
                    'reason': 'Result lacks driver analysis'
                })
        
        return result

# 使用严格审计
controller.run(
    diagnose_agent=DiagnoseAgent(),
    audit_agent=StrictAuditAgent(),
    recheck_agent=RecheckAgent()
)
```

---

## 6. 故障排查

### 6.1 诊断轮未完成所有 issues

**现象**：审计时发现仍有 open issues

**处理**：
```python
# 检查未完成的 issues
issues = controller.run_spear_command("trace issues --status open --format json")
print(f"Open issues: {issues}")

# 手动补充分析
for issue in issues['pending']:
    # 执行额外分析...
    controller.run_spear_command(
        f'trace complete --id {issue["id"]} --result "补充分析结果"'
    )
```

### 6.2 审计误报

**现象**：审计错误地标记了合格的 issue

**处理**：
```python
# 查看详细审计结果
with open('./case/audit_report.json') as f:
    audit = json.load(f)

# 检查具体失败原因
for failed in audit['failed_issues']:
    print(f"Issue {failed['id']}: {failed['reason']}")
    print(f"  Current: {failed.get('current_result')}")
    print(f"  Expected: {failed.get('expected')}")
```

### 6.3 复查未修复问题

**现象**：复查后审计仍然失败

**检查点**：
1. 复查 Agent 是否正确读取了 gaps
2. 复查后的 result 是否满足审计要求
3. 是否需要第二轮复查

```python
# 复查后再次审计
recheck_result = controller.run_round3_recheck(recheck_agent)

# 重新审计
second_audit = controller.run_round2_audit(audit_agent)
print(f"Second audit: {second_audit['overall_status']}")
```

---

## 7. 最佳实践

### 7.1 工作目录组织

```
projects/
├── case_001_mysql_slow/      # 每个 case 独立目录
│   ├── perf.data
│   ├── .spear.json
│   ├── debug/
│   ├── audit_report.json
│   └── final_report.json
├── case_002_cpu_high/
└── case_003_mem_leak/
```

### 7.2 CI/CD 集成

```yaml
# .github/workflows/spear-pipeline.yml
name: SPEAR Diagnosis

on:
  workflow_dispatch:
    inputs:
      perf_data:
        description: 'Perf data file path'
        required: true
      symptom:
        description: 'Symptom description'
        required: true

jobs:
  diagnose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run SPEAR Pipeline
        run: |
          python -m pipeline.cli run \
            --data ${{ github.event.inputs.perf_data }} \
            --symptom "${{ github.event.inputs.symptom }}" \
            --output ./output \
            --strict
      
      - name: Upload Reports
        uses: actions/upload-artifact@v3
        with:
          name: spear-reports
          path: ./output/*.json
```

### 7.3 质量门禁

```python
# 质量检查脚本
import json
import sys

def check_quality(audit_report_path):
    with open(audit_report_path) as f:
        report = json.load(f)
    
    summary = report['summary']
    
    # 检查通过率
    pass_rate = summary['passed'] / summary['total_issues']
    if pass_rate < 0.8:
        print(f"ERROR: Pass rate {pass_rate:.1%} < 80%")
        return False
    
    # 检查是否有 Critical 失败
    critical_failures = [f for f in report['failed_issues'] 
                        if f.get('severity') == 'critical']
    if critical_failures:
        print(f"ERROR: {len(critical_failures)} critical failures")
        return False
    
    print("Quality check passed!")
    return True

if __name__ == '__main__':
    if not check_quality(sys.argv[1]):
        sys.exit(1)
```

---

## 8. 参考

- [agent-pipeline-design.md](./agent-pipeline-design.md) - 架构设计文档
- [audit-process.md](./audit-process.md) - 审计流程规范
- [../SKILL.md](../SKILL.md) - SPEAR 方法论
