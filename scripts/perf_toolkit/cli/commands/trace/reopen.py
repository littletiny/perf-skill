"""
trace reopen - 重新打开已解决的 issue
"""
from perf_toolkit.core.trace import Trace


def register_reopen_parser(subparsers):
    """注册 reopen 子命令参数"""
    p = subparsers.add_parser('reopen', help="Reopen a resolved issue")
    p.add_argument("--id", help="Issue identifier")
    p.add_argument("--all", action="store_true", help="Reopen all resolved issues")
    p.add_argument("--reason", default="", help="Reason for reopening")


def cmd_doc_reopen(args):
    """重新打开已解决的 issue"""
    doc = Trace()
    
    if not args.id and not args.all:
        print("[ERROR] Must specify --id or --all")
        return
    
    if args.all:
        resolved_issues = doc.get_resolved_issues()
        if not resolved_issues:
            print("[INFO] No resolved issues to reopen")
            return
        
        reopened_count = 0
        for issue in resolved_issues:
            try:
                doc.reopen(issue['id'], getattr(args, 'reason', ''))
                reopened_count += 1
            except ValueError as e:
                print(f"[WARNING] Failed to reopen {issue['id']}: {e}")
        
        print(f"[REOPENED] {reopened_count} issues")
        if args.reason:
            print(f"→ Reason: {args.reason}")
        
        open_issues = doc.get_open_issues()
        print(f"\n→ {len(open_issues)} issues now open")
    else:
        try:
            issue_id = doc.reopen(args.id, getattr(args, 'reason', ''))
            print(f"[REOPENED] {issue_id}")
            if args.reason:
                print(f"→ Reason: {args.reason}")
            
            open_issues = doc.get_open_issues()
            print(f"\n→ {len(open_issues)} issues now open")
        except ValueError as e:
            print(f"[ERROR] {e}")
