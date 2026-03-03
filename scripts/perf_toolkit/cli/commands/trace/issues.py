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
    
    if status_filter in ['all', 'open'] and doc.get_open_issues():
        print(f"Usage: shecr trace complete --id ISS-001 --result '分析结果'")
