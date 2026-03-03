"""
trace audit - 审计 resolved issues 的分析质量
"""
import json
import os
from typing import List, Dict, Any
from dataclasses import asdict

from perf_toolkit.core.trace import Trace
from perf_toolkit.core.risk_config import RiskDisplayConfig, get_risk_config
from perf_toolkit.core.output_models import (
    CheckResult, IssueAuditResult, AuditSummary, AuditOutput
)


def register_audit_parser(subparsers):
    """注册 audit 子命令参数"""
    p = subparsers.add_parser('audit', help="Audit resolved issues for quality")
    p.add_argument("--phase", choices=['all', 'structural', 'timeline', 'depth'], default='all')
    p.add_argument("--format", choices=['text', 'json'], default='text')
    p.add_argument("--output", help="Output file path")
    p.add_argument("--no-fail", action="store_true", help="Don't exit with error on failure")
    p.add_argument('--risk-config', metavar='PATH', help='Risk display config file')
    p.add_argument('--risk-style', choices=['default', 'ci', 'compact'], help='Risk style')


def _load_risk_config_from_args(args) -> RiskDisplayConfig:
    """从 args 加载 Risk 配置"""
    cfg = get_risk_config(explicit_path=getattr(args, 'risk_config', None))
    if style := getattr(args, 'risk_style', None):
        cfg.apply_mode(style)
    if os.getenv('NO_COLOR') or os.getenv('SPEAR_NO_COLOR'):
        cfg.colors = {k: '' for k in cfg.colors}
    return cfg


def _audit_issue(issue: Dict[str, Any], timeline: List[Dict[str, Any]], phase: str) -> IssueAuditResult:
    """
    审计单个 issue
    """
    result = IssueAuditResult(
        issue_id=issue['id'],
        desc=issue['desc'],
        status="passed",
        checks={}
    )

    # 结构完整性检查
    if phase in ['all', 'structural']:
        result_text = issue.get('result', '')
        if not result_text or len(result_text) < 10:
            result.checks['structural'] = CheckResult(
                status='failed',
                message='Result too short or empty'
            )
        elif result_text.lower() in ['ok', 'fixed', 'done', 'resolved', '完成']:
            result.checks['structural'] = CheckResult(
                status='warning',
                message='Result appears to be perfunctory'
            )
        else:
            result.checks['structural'] = CheckResult(status='passed')

    # Timeline 关联检查
    if phase in ['all', 'timeline']:
        created_by = issue.get('created_by_seq')
        resolved_by = issue.get('resolved_by_seq')

        if not created_by:
            result.checks['timeline'] = CheckResult(
                status='warning',
                message='No timeline association for creation'
            )
        elif not resolved_by:
            result.checks['timeline'] = CheckResult(
                status='warning',
                message='No timeline association for resolution'
            )
        else:
            # 检查是否有足够的分析命令
            analysis_commands = 0
            for record in timeline:
                seq = record.get('seq', 0)
                if created_by <= seq <= resolved_by:
                    cmd = record.get('command', '')
                    if any(x in cmd for x in ['hotspots', 'callers', 'anomalies', 'audit']):
                        analysis_commands += 1

            if analysis_commands < 1:
                result.checks['timeline'] = CheckResult(
                    status='warning',
                    message='No analysis commands between creation and resolution'
                )
            else:
                result.checks['timeline'] = CheckResult(
                    status='passed',
                    message=f'{analysis_commands} analysis commands found'
                )

    # 分析深度检查
    if phase in ['all', 'depth']:
        result_text = issue.get('result', '')
        depth_keywords = ['because', 'caused by', 'due to', '根因', '原因', '导致', '由于']
        has_depth = any(kw in result_text.lower() for kw in depth_keywords)

        if not has_depth:
            result.checks['depth'] = CheckResult(
                status='warning',
                message='Result lacks causal reasoning (no depth keywords)'
            )
        else:
            result.checks['depth'] = CheckResult(status='passed')

    # 总体状态
    statuses = [c.status for c in result.checks.values()]
    if 'failed' in statuses:
        result.status = 'failed'
    elif 'warning' in statuses:
        result.status = 'warning'
    else:
        result.status = 'passed'

    return result


def _convert_to_dict(output: AuditOutput) -> Dict[str, Any]:
    """将 AuditOutput 转换为可 JSON 序列化的 dict"""
    return {
        "summary": {
            "total": output.summary.total,
            "passed": output.summary.passed,
            "warning": output.summary.warning,
            "failed": output.summary.failed
        },
        "results": [
            {
                "issue_id": r.issue_id,
                "desc": r.desc,
                "status": r.status,
                "checks": {
                    name: {"status": c.status, "message": c.message}
                    for name, c in r.checks.items()
                }
            }
            for r in output.results
        ]
    }


def cmd_doc_audit(args):
    """
    审计 resolved issues 的分析质量
    """
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)

    phase = getattr(args, 'phase', 'all')
    output = getattr(args, 'output', None)

    # 获取所有 resolved issues
    resolved_issues = doc.get_resolved_issues()

    if not resolved_issues:
        print("[AUDIT] No resolved issues to audit")
        return

    # 执行审计检查
    audit_results: List[IssueAuditResult] = []
    failed_count = 0
    warning_count = 0
    passed_count = 0

    for issue in resolved_issues:
        result = _audit_issue(issue, doc.data.get('timeline', []), phase)
        audit_results.append(result)

        if result.status == 'failed':
            failed_count += 1
        elif result.status == 'warning':
            warning_count += 1
        else:
            passed_count += 1

    # 创建输出结构
    audit_output = AuditOutput(
        summary=AuditSummary(
            total=len(resolved_issues),
            passed=passed_count,
            warning=warning_count,
            failed=failed_count
        ),
        results=audit_results
    )

    if getattr(args, 'format', 'text') == 'json':
        content = json.dumps(_convert_to_dict(audit_output), indent=2)
    else:
        lines = []
        lines.append("=" * 65)
        lines.append("AUDIT REPORT")
        lines.append("=" * 65)
        lines.append(f"Total: {len(resolved_issues)}, Passed: {passed_count}, "
                    f"Warning: {warning_count}, Failed: {failed_count}")
        lines.append("")

        for result in audit_results:
            status = result.status.upper()
            lines.append(f"[{status}] {result.issue_id}: {result.desc[:50]}")
            for check_name, check in result.checks.items():
                icon = "✓" if check.status == 'passed' else "⚠" if check.status == 'warning' else "✗"
                msg = check.message
                lines.append(f"  {icon} {check_name}: {msg}")
            lines.append("")

        content = '\n'.join(lines)

    if output:
        with open(output, 'w') as f:
            f.write(content)
        print(f"[AUDIT] Report saved to {output}")
    else:
        print(content)

    # 根据结果退出
    if failed_count > 0 and not getattr(args, 'no_fail', False):
        import sys
        sys.exit(1)
