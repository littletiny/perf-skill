"""
Trace 命令注册表
"""

COMMANDS = {
    'trace init': 'cli.commands.trace.init.cmd_doc_init',
    'trace add': 'cli.commands.trace.add.cmd_doc_add',
    'trace timeline': 'cli.commands.trace.timeline.cmd_doc_timeline',
    'trace issues': 'cli.commands.trace.issues.cmd_doc_issues',
    'trace complete': 'cli.commands.trace.complete.cmd_doc_complete',
    'trace reopen': 'cli.commands.trace.reopen.cmd_doc_reopen',
    'trace finalize': 'cli.commands.trace.finalize.cmd_doc_finalize',
    'trace export': 'cli.commands.trace.export.cmd_doc_export',
    'trace audit': 'cli.commands.trace.audit.cmd_doc_audit',
}
