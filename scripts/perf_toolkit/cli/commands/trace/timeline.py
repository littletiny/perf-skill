"""
trace timeline - 查看时间线
"""
import os
from perf_toolkit.core.trace import Trace
from perf_toolkit.core.risk_config import RiskDisplayConfig, get_risk_config


def register_timeline_parser(subparsers):
    """注册 timeline 子命令参数"""
    p = subparsers.add_parser('timeline', help="Show diagnosis timeline")
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


def cmd_doc_timeline(args):
    """查看时间线"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)
    print(doc.format_timeline(cfg))
