"""
trace issues - 查看 issues 状态
"""
import os
from perf_toolkit.core.trace import Trace
from perf_toolkit.core.risk_config import RiskDisplayConfig, get_risk_config


def register_issues_parser(subparsers):
    """注册 issues 子命令参数"""
    p = subparsers.add_parser('issues', help="List all issues")
    p.add_argument("--status", choices=['open', 'resolved', 'all'], default='all')
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


def cmd_doc_issues(args):
    """查看 issues 状态"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)
    
    status_filter = getattr(args, 'status', 'all')
    
    if status_filter == 'open':
        issues = doc.get_open_issues()
    elif status_filter == 'resolved':
        issues = doc.get_resolved_issues()
    else:
        issues = doc.get_open_issues() + doc.get_resolved_issues()
    
    print(doc.format_issue_list(issues, status_filter, cfg))
    
    # XT Protocol: Trace-Todo 联动提示
    open_issues = doc.get_open_issues()
    if status_filter in ['all', 'open'] and open_issues:
        print("")
        print("=" * 65)
        print(f"<XT0> 发现 {len(open_issues)} 个待处理问题需要同步到 Todo")
        print("")
        print("<XT0> 同步要求: 每个 open issue 必须创建对应 Todo")
        print("<XT-A> SetTodoList 格式: '[Trace] {ISS-ID}: {简要描述}'")
        print("")
        for issue in open_issues[:3]:
            issue_id = issue.get('id', 'unknown')
            desc = issue.get('desc', 'No description')[:30]
            print(f"  <XT-A> {{'title': '[Trace] {issue_id}: {desc}...', 'status': 'pending'}}")
        if len(open_issues) > 3:
            print(f"  ... 还有 {len(open_issues) - 3} 个")
        print("=" * 65)
    elif not open_issues:
        print("")
        print("<XT0> 所有 issues 已解决")
        print("<XT-A> 确认所有 [Trace] 前缀的 Todo 已标记为 done")
