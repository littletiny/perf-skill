#!/usr/bin/env python3
"""
SPEAR Pipeline CLI - 多轮流水线命令行接口

用法:
    python -m pipeline.cli run --data perf.data --symptom "CPU高"
    python -m pipeline.cli diagnose --data perf.data --output ./case
    python -m pipeline.cli audit --spear-json ./case/.spear.json
    python -m pipeline.cli recheck --audit-report ./case/audit_report.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import PipelineController, PipelineConfig
from pipeline.agents import DiagnoseAgent, AuditAgent, RecheckAgent


def cmd_run(args):
    """运行完整流水线"""
    config = PipelineConfig(
        max_rounds=args.max_rounds,
        strict_audit=args.strict,
        auto_recheck=args.auto_recheck
    )
    
    controller = PipelineController(config)
    controller.init(
        perf_data=args.data,
        symptom=args.symptom,
        work_dir=args.output
    )
    
    # 创建 Agents
    diagnose_agent = DiagnoseAgent()
    audit_agent = AuditAgent()
    recheck_agent = RecheckAgent() if args.auto_recheck else None
    
    print(f"=" * 60)
    print("SPEAR Agent Pipeline")
    print(f"=" * 60)
    print(f"Perf data: {args.data}")
    print(f"Symptom: {args.symptom}")
    print(f"Work dir: {args.output}")
    print(f"Max rounds: {args.max_rounds}")
    print(f"Auto recheck: {args.auto_recheck}")
    print(f"=" * 60)
    
    try:
        result = controller.run(
            diagnose_agent=diagnose_agent,
            audit_agent=audit_agent,
            recheck_agent=recheck_agent
        )
        
        print(f"\n{'=' * 60}")
        print("PIPELINE COMPLETED")
        print(f"{'=' * 60}")
        print(f"Final status: {result['final_status']}")
        print(f"Audit passed: {result['audit']['passed']}")
        
        if result.get('recheck'):
            print(f"Recheck performed: Yes")
        
        print(f"\nArtifacts:")
        for key, value in result.get('artifacts', {}).items():
            print(f"  {key}: {value}")
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: Pipeline failed: {e}", file=sys.stderr)
        return 1


def cmd_diagnose(args):
    """只运行诊断轮"""
    agent = DiagnoseAgent()
    
    print(f"Running diagnosis...")
    print(f"  Data: {args.data}")
    print(f"  Symptom: {args.symptom}")
    print(f"  Output: {args.output}")
    
    result = agent.run(
        perf_data=args.data,
        symptom=args.symptom,
        work_dir=args.output
    )
    
    print(f"\nDiagnosis completed!")
    print(f"  Issues found: {result['issues_count']}")
    print(f"  Resolved: {result['completed_count']}")
    print(f"  Spear JSON: {result['spear_json']}")
    print(f"  Debug dir: {result['debug_dir']}")
    
    return 0


def cmd_audit(args):
    """只运行审计轮"""
    agent = AuditAgent()
    
    print(f"Running audit...")
    print(f"  Spear JSON: {args.spear_json}")
    
    debug_dir = args.debug_dir or os.path.join(os.path.dirname(args.spear_json), 'debug')
    
    result = agent.run(
        spear_json=args.spear_json,
        debug_dir=debug_dir,
        strict=args.strict
    )
    
    print(f"\nAudit completed!")
    print(f"  Status: {result['overall_status']}")
    print(f"  Issues: {result['summary'].get('total_issues', 0)}")
    print(f"  Passed: {result['summary'].get('passed', 0)}")
    print(f"  Failed: {result['summary'].get('failed', 0)}")
    print(f"  Warnings: {result['summary'].get('warnings', 0)}")
    print(f"  Report: {result['audit_report']}")
    
    if result.get('gaps'):
        print(f"\nGaps found ({len(result['gaps'])}):")
        for gap in result['gaps']:
            print(f"  - {gap['type']}: {gap.get('suggestion', 'N/A')}")
    
    return 0 if result['overall_status'] == 'passed' else 2


def cmd_recheck(args):
    """只运行复查轮"""
    agent = RecheckAgent()
    
    print(f"Running recheck...")
    print(f"  Audit report: {args.audit_report}")
    
    work_dir = args.output or os.path.dirname(args.audit_report)
    spear_json = args.spear_json or os.path.join(work_dir, '.spear.json')
    
    # 自动查找 perf.data
    perf_data = args.data
    if not perf_data and os.path.exists(spear_json):
        with open(spear_json, 'r') as f:
            trace_data = json.load(f)
        perf_data = trace_data.get('data_file')
    
    if not perf_data:
        print("ERROR: Cannot determine perf.data path", file=sys.stderr)
        return 1
    
    result = agent.run(
        audit_report=args.audit_report,
        spear_json=spear_json,
        perf_data=perf_data,
        work_dir=work_dir
    )
    
    print(f"\nRecheck completed!")
    print(f"  Status: {result['status']}")
    print(f"  Enhancements: {len(result.get('enhancements', []))}")
    print(f"  Final report: {result['final_report']}")
    
    return 0


def cmd_status(args):
    """查看流水线状态"""
    state_file = args.state
    
    if not os.path.exists(state_file):
        print(f"ERROR: State file not found: {state_file}", file=sys.stderr)
        return 1
    
    with open(state_file, 'r') as f:
        data = json.load(f)
    
    context = data.get('context', {})
    
    print(f"Pipeline Status")
    print(f"=" * 60)
    print(f"Status: {context.get('status', 'unknown')}")
    print(f"Round: {context.get('round_num', 0)}")
    print(f"Work dir: {context.get('work_dir', 'N/A')}")
    print(f"Perf data: {context.get('perf_data', 'N/A')}")
    print(f"Symptom: {context.get('symptom', 'N/A')}")
    print(f"Start time: {context.get('start_time', 'N/A')}")
    print(f"End time: {context.get('end_time', 'N/A')}")
    
    artifacts = context.get('artifacts', {})
    if artifacts:
        print(f"\nArtifacts:")
        for key in artifacts.keys():
            print(f"  - {key}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='SPEAR Agent Pipeline - 多轮诊断-审计-复查流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整流水线
  %(prog)s run --data perf.data --symptom "系统响应慢" --output ./case_001

  # 只运行诊断轮
  %(prog)s diagnose --data perf.data --symptom "CPU高" --output ./case_001

  # 只运行审计轮（基于已有诊断）
  %(prog)s audit --spear-json ./case_001/.spear.json

  # 运行复查轮（基于审计结果）
  %(prog)s recheck --audit-report ./case_001/audit_report.json

  # 查看流水线状态
  %(prog)s status --state ./case_001/pipeline_state.json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # run 命令
    run_parser = subparsers.add_parser('run', help='运行完整流水线')
    run_parser.add_argument('--data', '-d', required=True, help='perf 数据文件路径')
    run_parser.add_argument('--symptom', '-s', required=True, help='故障症状描述')
    run_parser.add_argument('--output', '-o', default='./spear_pipeline', help='工作目录')
    run_parser.add_argument('--max-rounds', type=int, default=2, help='最大轮数')
    run_parser.add_argument('--strict', action='store_true', help='严格审计模式')
    run_parser.add_argument('--auto-recheck', action='store_true', default=True,
                           help='审计失败自动进入复查轮')
    run_parser.set_defaults(func=cmd_run)
    
    # diagnose 命令
    diag_parser = subparsers.add_parser('diagnose', help='只运行诊断轮')
    diag_parser.add_argument('--data', '-d', required=True, help='perf 数据文件路径')
    diag_parser.add_argument('--symptom', '-s', required=True, help='故障症状描述')
    diag_parser.add_argument('--output', '-o', default='./spear_pipeline', help='工作目录')
    diag_parser.set_defaults(func=cmd_diagnose)
    
    # audit 命令
    audit_parser = subparsers.add_parser('audit', help='只运行审计轮')
    audit_parser.add_argument('--spear-json', required=True, help='spear JSON 文件路径')
    audit_parser.add_argument('--debug-dir', help='debug 文档目录')
    audit_parser.add_argument('--strict', action='store_true', help='严格审计模式')
    audit_parser.set_defaults(func=cmd_audit)
    
    # recheck 命令
    recheck_parser = subparsers.add_parser('recheck', help='只运行复查轮')
    recheck_parser.add_argument('--audit-report', required=True, help='审计报告路径')
    recheck_parser.add_argument('--spear-json', help='spear JSON 文件路径（自动推断）')
    recheck_parser.add_argument('--data', '-d', help='perf 数据文件路径（自动推断）')
    recheck_parser.add_argument('--output', '-o', help='输出目录')
    recheck_parser.set_defaults(func=cmd_recheck)
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看流水线状态')
    status_parser.add_argument('--state', required=True, help='pipeline_state.json 路径')
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
