"""
trace export - 导出报告
"""
import json
from perf_toolkit.core.trace import Trace


def register_export_parser(subparsers):
    """注册 export 子命令参数"""
    p = subparsers.add_parser('export', help="Export document to other formats")
    p.add_argument("--format", choices=['markdown', 'json'], default='markdown')
    p.add_argument("--output", help="Output file path (default: stdout)")


def cmd_doc_export(args):
    """导出报告"""
    doc = Trace()
    fmt = getattr(args, 'format', 'markdown')
    output = getattr(args, 'output', None)
    
    if fmt == 'markdown':
        content = doc.export_markdown()
    else:
        content = json.dumps(doc.data, indent=2, ensure_ascii=False)
    
    if output:
        with open(output, 'w') as f:
            f.write(content)
        print(f"[EXPORTED] {output}")
    else:
        print(content)
