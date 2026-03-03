"""
trace init - 初始化诊断文档
"""
from perf_toolkit.core.trace import Trace


def register_init_parser(subparsers):
    """注册 init 子命令参数"""
    p = subparsers.add_parser('init', help="Initialize a new diagnosis document")
    p.add_argument("--data", required=True, help="Path to perf data file")
    p.add_argument("--path", default=".shecr.json", help="Document storage path")


def cmd_doc_init(args):
    """初始化诊断文档"""
    doc = Trace()
    doc.init(args.data)
    print(f"[INIT] Created: {doc.path}")
    print(f"→ Data file: {args.data}")
