"""
trace complete - 标记 issue 为已完成
"""
from perf_toolkit.core.trace import Trace


def register_complete_parser(subparsers):
    """注册 complete 子命令参数"""
    p = subparsers.add_parser('complete', help="Mark an issue as completed")
    p.add_argument("--id", required=True, help="Issue identifier")
    p.add_argument("--result", required=True, help="Analysis result")


def cmd_doc_complete(args):
    """标记 issue 为已完成"""
    doc = Trace()
    
    try:
        doc.complete(args.id, args.result)
        print(f"[COMPLETED] {args.id}")
        print(f"→ Result: {args.result}")
        
        open_issues = doc.get_open_issues()
        if open_issues:
            print(f"\n→ {len(open_issues)} issues remaining")
        else:
            print("\n[ALL DONE] No more issues")
    except ValueError as e:
        print(f"[ERROR] {e}")
