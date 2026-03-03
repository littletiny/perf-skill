"""
trace add - 手动添加 issue
"""
from perf_toolkit.core.trace import Trace


def register_add_parser(subparsers):
    """注册 add 子命令参数"""
    p = subparsers.add_parser('add', help="Add a new issue (auto-generate ID)")
    p.add_argument("--desc", required=True, help="Issue description")
    p.add_argument("--level", choices=['critical', 'warning', 'info'], default='warning')
    p.add_argument("--risk", default="", help="Risk of not handling")
    p.add_argument("--hint", default="", help="Recommended action")


def cmd_doc_add(args):
    """手动添加 issue"""
    doc = Trace()
    level = getattr(args, 'level', 'warning')
    issue_id = doc.add(
        desc=args.desc,
        risk=getattr(args, 'risk', ''),
        hint=getattr(args, 'hint', ''),
        level=level
    )
    print(f"[ADDED] {issue_id}")
    print(f"→ Desc: {args.desc}")
    if args.hint:
        print(f"→ Hint: {args.hint}")
