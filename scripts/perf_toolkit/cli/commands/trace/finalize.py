"""
trace finalize - 最终审计
"""
import sys
import os
from perf_toolkit.core.trace import Trace
from perf_toolkit.core.risk_config import RiskDisplayConfig, get_risk_config


def register_finalize_parser(subparsers):
    """注册 finalize 子命令参数"""
    p = subparsers.add_parser('finalize', help="Final audit before generating report")
    p.add_argument("--accept-risk", help="Reason for accepting remaining risks")
    p.add_argument("--format", choices=['text', 'json'], default='text')
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


def cmd_doc_finalize(args):
    """最终审计"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)
    result = doc.finalize(getattr(args, 'accept_risk', None))
    
    print("=" * 65)
    print("FINALIZE - Ready to generate report?")
    print("=" * 65)
    print()
    
    if result.status == 'ready':
        print("<XT0> [READY] All issues resolved")
        print(f"→ Total resolved: {result.resolved_count}")
        print()
        print("<XT0> Trace 审计通过")
        print("<XT-A> 确认所有 [Trace] 前缀的 Todo 已标记为 done")
        print()
        print("=" * 65)
        print("Report can be generated")
        print("=" * 65)

    elif result.status == 'accepted':
        print(f"<XT1> [ACCEPTED] Risk accepted: {args.accept_risk}")
        print(f"→ Resolved: {result.resolved_count}, Accepted: {result.open_count}")
        print()
        print("<XT1> 风险已接受，可以生成报告")
        print("=" * 65)
        print("Report can be generated")
        print("=" * 65)

    else:  # blocked
        print(f"<XT0> [BLOCKED] {len(result.open_issues)} open issues remaining")
        print()
        print("Note: This is NOT an audit. Use 'shecr trace audit' for quality review.")
        print()
        for issue in result.open_issues:
            color = cfg.colors.get(issue['level'], '')
            reset = cfg.colors.get('reset', '')
            line = f"[{issue['level'].upper()}] {issue['id']}: {issue['desc']}"
            if color:
                line = f"{color}{line}{reset}"
            print(line)
            if issue.get('hint'):
                print(f"→ {issue['hint']}")
            print()
        print("-" * 65)
        print("<XT0> 存在未解决的 Trace issues")
        print("<XT-A> 选项1: 继续分析并执行 trace complete")
        print("<XT-A> 选项2: 接受风险: --accept-risk '原因'")
        print("<XT-A> 选项3: 创建对应 Todo 跟踪: '[Trace] ISS-XXX: ...'")
        print("=" * 65)
        sys.exit(1)
