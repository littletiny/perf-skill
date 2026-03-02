#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trace v2.0 - 诊断过程追踪工具

自动记录诊断过程，无需人工干预：
- timeline: 按时间顺序记录所有命令执行
- issues: 问题聚合状态
- 双向链接: timeline 和 issues 互相引用

设计文档: docs/design-rationale-trace-v2.md
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Any

from .risk_config import RiskDisplayConfig, get_risk_config


class Trace:
    """
    Trace v2.0 - 诊断过程追踪实现

    数据文件: .perf-doc.json (当前目录)
    """

    DEFAULT_PATH = ".spear.json"
    CURRENT_VERSION = "2.0"

    def __init__(self, path: Optional[str] = None, config: RiskDisplayConfig = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self._current_seq = None
        self.config = config

    def _get_config(self, cfg: RiskDisplayConfig = None) -> RiskDisplayConfig:
        """获取有效配置（回退机制）"""
        return cfg or self.config or get_risk_config()

    def _find_doc(self) -> str:
        """查找现有文档或返回默认路径"""
        if os.path.exists(self.DEFAULT_PATH):
            return self.DEFAULT_PATH
        return self.DEFAULT_PATH

    def _load(self) -> Dict:
        """加载文档，自动迁移旧版本"""
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                data = json.load(f)
                # 版本迁移
                version = data.get('version', '1.0')
                if version == '1.0':
                    data = self._migrate_v1_to_v2(data)
                return data

        # 新文档
        return self._create_new()

    def _create_new(self) -> Dict:
        """创建新文档结构"""
        return {
            "version": self.CURRENT_VERSION,
            "data_file": None,
            "created_at": self._now(),
            "updated_at": self._now(),
            "timeline": [],
            "issues": {}
        }

    def _migrate_v1_to_v2(self, v1_data: Dict) -> Dict:
        """将 v1.0 issues 列表迁移到 v2.0 结构"""
        v2_data = {
            "version": self.CURRENT_VERSION,
            "data_file": v1_data.get('data_file'),
            "created_at": v1_data.get('created_at', self._now()),
            "updated_at": self._now(),
            "timeline": [],
            "issues": {}
        }

        # 迁移 issues，但 timeline 为空（历史命令未记录）
        for issue in v1_data.get('issues', []):
            issue_id = issue['id']
            v2_data['issues'][issue_id] = {
                "id": issue_id,
                "desc": issue['desc'],
                "level": self._infer_level(issue.get('risk', '')),
                "status": issue.get('status', 'open'),
                "created_at": issue.get('created_at', self._now()),
                "resolved_at": issue.get('completed_at'),
                "result": issue.get('result', ''),
                "hint": issue.get('hint', ''),
                "created_by_seq": None,  # 历史数据无记录
                "resolved_by_seq": None
            }

        return v2_data

    def _infer_level(self, risk: str) -> str:
        """从风险描述推断级别"""
        risk_lower = risk.lower()
        if 'critical' in risk_lower or '严重' in risk_lower:
            return 'critical'
        if 'warning' in risk_lower or '警告' in risk_lower:
            return 'warning'
        return 'info'

    def _now(self) -> str:
        """当前时间 ISO-8601"""
        return datetime.utcnow().isoformat() + "Z"

    def save(self):
        """保存文档到磁盘"""
        self.data["updated_at"] = self._now()
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # =====================================================================
    # 初始化
    # =====================================================================

    def init(self, data_file: str):
        """初始化新诊断文档"""
        self.data = self._create_new()
        self.data['data_file'] = data_file
        self.save()
        return self

    # =====================================================================
    # 自动记录 API - 供 OutputBuilder 使用
    # =====================================================================

    def begin_command(self, command: str) -> int:
        """
        命令开始时调用，创建 timeline 记录

        Returns:
            seq: 命令序号，后续 record_risk/record_resolution 使用
        """
        seq = len(self.data['timeline']) + 1
        self._current_seq = seq

        record = {
            "seq": seq,
            "type": "command",
            "command": command,
            "timestamp": self._now(),
            "findings": []
        }
        self.data['timeline'].append(record)
        self.save()
        
        # 无脑输出所有 open issues
        self._print_open_issues()
        
        return seq
    
    def _print_open_issues(self):
        """输出 issue overflow warning（当 open_issues >= 2 时）"""
        open_issues = self.get_open_issues()
        # 触发条件: open_issues >= 2
        if len(open_issues) < 2:
            return
        
        # 分类统计
        categories = self._categorize_issues(open_issues)
        category_str = ", ".join([f"{cat}x{count}" for cat, count in categories.items()]) if categories else "未知类型"
        
        # 固定警告文案
        warning = "⚠️ 用户在质疑你的专业性，这是挑战底线的行为，务必重新反思整个问题的**全局**现状"
        
        # 输出格式: [!] {总数}问题未闭环: {分类统计} | {警告文案} | 现在执行: trace issues
        print(f"[!] {len(open_issues)}问题未闭环: {category_str} | {warning} | 现在执行: trace issues")
        print()  # 空行分割
    
    def _categorize_issues(self, issues) -> dict:
        """对 issues 进行分类统计"""
        categories = {
            "内核异常": 0,
            "锁竞争": 0,
            "进程风暴": 0,
        }
        
        for issue in issues:
            desc = issue.get('desc', '').lower()
            
            if '内核' in desc or 'kernel' in desc:
                categories["内核异常"] += 1
            elif '锁竞争' in desc or 'lock_contention' in desc:
                categories["锁竞争"] += 1
            elif '进程风暴' in desc or 'process_storm' in desc:
                categories["进程风暴"] += 1
        
        # 过滤掉数量为0的分类
        return {k: v for k, v in categories.items() if v > 0}

    def add(self, desc: str, risk: str = "", hint: str = "", level: str = "warning") -> str:
        """
        添加新 issue（自动生成 ID）

        Args:
            desc: 问题描述
            risk: 风险描述
            hint: 建议操作
            level: 级别 critical/warning/info

        Returns:
            issue_id: 自动生成的 ID (ISS-001, ISS-002, ...)
        """
        # 检查是否已存在类似 issue（简单去重）
        existing_id = self._find_similar_issue(desc)
        if existing_id:
            # 添加到当前命令的 findings
            self._add_finding_to_current({
                "type": "risk_duplicate",
                "level": level,
                "desc": desc,
                "issue_id": existing_id
            })
            return existing_id

        # 创建新 issue
        issue_id = self._generate_issue_id()
        now = self._now()

        self.data['issues'][issue_id] = {
            "id": issue_id,
            "desc": desc,
            "level": level,
            "status": "open",
            "created_at": now,
            "created_by_seq": self._current_seq,
            "resolved_at": None,
            "resolved_by_seq": None,
            "result": None,
            "hint": hint
        }

        # 添加到 timeline
        self._add_finding_to_current({
            "type": "risk_created",
            "level": level,
            "desc": desc,
            "issue_id": issue_id
        })

        self.save()
        return issue_id

    def complete(self, issue_id: str, result: str):
        """
        标记 issue 为已完成

        Args:
            issue_id: Issue ID (如 ISS-001)
            result: 分析结果/结论
        """
        if issue_id not in self.data['issues']:
            # 尝试模糊匹配
            issue_id = self._fuzzy_find_issue(issue_id) or issue_id

        if issue_id in self.data['issues']:
            issue = self.data['issues'][issue_id]
            
            # 初始化 results 列表（如果不存在）
            if 'results' not in issue:
                issue['results'] = []
            
            # 追加新结果到列表
            result_entry = {
                "result": result,
                "resolved_at": self._now(),
                "resolved_by_seq": self._current_seq
            }
            issue['results'].append(result_entry)
            
            # 同时更新单字段 result（兼容性）
            issue['result'] = result
            issue['status'] = 'resolved'
            issue['resolved_at'] = result_entry['resolved_at']
            issue['resolved_by_seq'] = result_entry['resolved_by_seq']

            self._add_finding_to_current({
                "type": "issue_resolved",
                "issue_id": issue_id,
                "result": result
            })
            self.save()

    def reopen(self, issue_id: str, reason: str = ""):
        """
        重新打开已解决的 issue

        Args:
            issue_id: Issue ID (如 ISS-001)
            reason: 重新打开的原因
        """
        if issue_id not in self.data['issues']:
            # 尝试模糊匹配
            issue_id = self._fuzzy_find_issue(issue_id) or issue_id

        if issue_id in self.data['issues']:
            issue = self.data['issues'][issue_id]
            
            # 只有 resolved 的 issue 才能 reopen
            if issue['status'] != 'resolved':
                raise ValueError(f"Issue {issue_id} is not resolved (status: {issue['status']})")
            
            # 记录 reopen 历史（保留之前的解决信息）
            import copy
            reopen_record = {
                "reopened_at": self._now(),
                "reason": reason,
                "previous_result": issue.get('result'),
                "previous_resolved_at": issue.get('resolved_at'),
                "previous_resolved_by_seq": issue.get('resolved_by_seq'),
                "previous_results": copy.deepcopy(issue.get('results', []))  # 深拷贝 results 列表
            }
            
            if 'reopen_history' not in issue:
                issue['reopen_history'] = []
            issue['reopen_history'].append(reopen_record)
            
            # 更新状态为 open，但保留 result 等历史信息
            issue['status'] = 'open'
            issue['resolved_at'] = None
            issue['resolved_by_seq'] = None
            # 注意：保留 issue['result'] 不清空，便于追溯

            self._add_finding_to_current({
                "type": "issue_reopened",
                "issue_id": issue_id,
                "reason": reason
            })
            self.save()
            return issue_id
        
        raise ValueError(f"Issue not found: {issue_id}")

    def record_info(self, message: str):
        """记录一般信息"""
        self._add_finding_to_current({
            "type": "info",
            "message": message
        })
        self.save()

    def end_command(self):
        """命令结束时调用，保存文档"""
        self._current_seq = None
        self.save()

    # =====================================================================
    # 别名方法（供 OutputBuilder 自动记录使用）
    # =====================================================================

    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """OutputBuilder 用的别名"""
        return self.add(desc=desc, level=level, hint=hint)

    def record_resolution(self, issue_id: str, result: str):
        """OutputBuilder 用的别名"""
        self.complete(issue_id, result)

    # =====================================================================
    # 内部辅助方法
    # =====================================================================

    def _add_finding_to_current(self, finding: Dict):
        """添加 finding 到当前命令记录"""
        if self._current_seq and self.data['timeline']:
            # timeline 是列表，seq 从 1 开始，所以索引是 seq-1
            idx = self._current_seq - 1
            if 0 <= idx < len(self.data['timeline']):
                self.data['timeline'][idx]['findings'].append(finding)

    def _generate_issue_id(self) -> str:
        """生成新 issue ID"""
        count = len(self.data['issues']) + 1
        return f"ISS-{count:03d}"

    def _resolve_issue_id(self, identifier: str) -> Optional[str]:
        """验证 issue ID 是否存在"""
        if identifier and identifier in self.data['issues']:
            return identifier
        return None

    def _find_similar_issue(self, desc: str) -> Optional[str]:
        """查找描述相似的已存在 issue（简单实现）"""
        # 提取关键词（简单：取前10个字符）
        key = desc[:10].lower()
        for issue_id, issue in self.data['issues'].items():
            if issue['status'] == 'open' and key in issue['desc'].lower():
                return issue_id
        return None

    def _fuzzy_find_issue(self, identifier: str) -> Optional[str]:
        """模糊查找 issue"""
        # 直接匹配
        if identifier in self.data['issues']:
            return identifier

        # 按描述匹配
        identifier_lower = identifier.lower()
        for issue_id, issue in self.data['issues'].items():
            if identifier_lower in issue['desc'].lower():
                return issue_id

        return None

    # =====================================================================
    # 查询 API
    # =====================================================================

    def get_open_issues(self) -> List[Dict]:
        """获取所有待处理问题"""
        return [
            issue for issue in self.data['issues'].values()
            if issue['status'] == 'open'
        ]

    def get_resolved_issues(self) -> List[Dict]:
        """获取所有已解决问题"""
        return [
            issue for issue in self.data['issues'].values()
            if issue['status'] == 'resolved'
        ]

    def get_issue(self, issue_id: str) -> Optional[Dict]:
        """获取指定 issue"""
        return self.data['issues'].get(issue_id)

    def get_timeline(self) -> List[Dict]:
        """获取完整时间线"""
        return self.data['timeline']

    def get_summary(self) -> Dict:
        """获取摘要统计"""
        open_issues = self.get_open_issues()
        resolved_issues = self.get_resolved_issues()
        return {
            "total_commands": len(self.data['timeline']),
            "open_issues": len(open_issues),
            "resolved_issues": len(resolved_issues),
            "can_finalize": len(open_issues) == 0
        }

    # =====================================================================
    # 最终审计
    # =====================================================================

    def finalize(self, accept_risk: Optional[str] = None) -> Dict:
        """
        最终审计 - 检查是否可以结束诊断

        Returns:
            {
                "status": "ready" | "accepted" | "blocked",
                "message": str,
                "open_issues": [...]
            }
        """
        open_issues = self.get_open_issues()

        if not open_issues:
            return {
                "status": "ready",
                "message": "所有问题已处理，可以生成报告",
                "resolved_count": len(self.get_resolved_issues())
            }

        if accept_risk:
            return {
                "status": "accepted",
                "message": f"已接受风险: {accept_risk}",
                "open_count": len(open_issues),
                "resolved_count": len(self.get_resolved_issues())
            }

        return {
            "status": "blocked",
            "message": f"存在 {len(open_issues)} 个未处理问题",
            "open_issues": open_issues
        }

    # =====================================================================
    # 导出
    # =====================================================================

    # =====================================================================
    # 格式化方法（使用 RiskDisplayConfig）
    # =====================================================================

    def format_issue(self, issue: Dict, cfg: RiskDisplayConfig = None) -> str:
        """格式化单个 issue（时间线格式，原因-结果配对）"""
        cfg = self._get_config(cfg)

        issue_id = issue.get('id', '')
        level = issue.get('level', 'warning')
        desc = issue.get('desc', '')
        status = issue.get('status', 'open')
        hint = issue.get('hint', '')
        results = issue.get('results', [])
        reopen_history = issue.get('reopen_history', [])

        # 应用颜色
        color = cfg.colors.get(level, '')
        reset = cfg.colors.get('reset', '')

        # Issue 行
        if status == 'resolved':
            tpl = cfg.templates.get('issue_resolved', '[RESOLVED] [{id}] [{level}] {desc}')
        else:
            tpl = cfg.templates.get('issue_open', '[OPEN] [{id}] [{level}] {desc}')

        line = tpl.format(id=issue_id, level=level.upper(), desc=desc)
        if color:
            line = f"{color}{line}{reset}"

        lines = [line]

        # Hint
        if status != 'resolved' and hint and cfg.show.get('hint', True):
            tpl = cfg.templates.get('hint', '→ {hint}')
            lines.append(tpl.format(hint=hint))
        
        # 时间线：原因 → 结果 配对展示
        if cfg.show.get('result', True):
            # 计算有多少个 reopen，就有多少对 原因→结果
            # reopen_history[i] 对应 results[i]（第 i 次 reopen 后的解决）
            # desc 对应 results[0]（创建 issue 后的第一次解决）
            
            for i, result_entry in enumerate(results):
                result_text = result_entry.get('result', '')
                
                if i == 0:
                    # 第一对：创建 issue 的原因 → 第一次解决结果
                    cause = desc
                    prefix = "[创建]"
                else:
                    # 后续：reopen 原因 → 解决结果
                    # reopen_history[i-1] 是第 i 次 reopen 的记录
                    if i - 1 < len(reopen_history):
                        cause = reopen_history[i - 1].get('reason', '')
                    else:
                        cause = ""
                    prefix = "[重开]"
                
                if cause:
                    lines.append(f"{prefix} {cause} → [解决] {result_text}")
                else:
                    lines.append(f"[解决] {result_text}")
            
            # 如果当前是 open 状态，显示最后一次 reopen（还没有对应的解决）
            if status == 'open' and reopen_history:
                # reopen 次数 = len(reopen_history)
                # complete 次数 = len(results)
                # 如果 reopen 次数 >= complete 次数，说明最后一次 reopen 还没解决
                if len(reopen_history) >= len(results):
                    last_reopen = reopen_history[-1]
                    last_reason = last_reopen.get('reason', '')
                    lines.append(f"[重开] {last_reason} → [待解决]")
        
        # 兼容旧数据：只有 result 字符串没有 results 列表
        if not results and issue.get('result') and cfg.show.get('result', True):
            lines.append(f"[创建] {desc} → [解决] {issue['result']}")

        return '\n'.join(lines)

    def format_issue_list(self, issues: List[Dict], status_filter: str = 'all',
                          cfg: RiskDisplayConfig = None) -> str:
        """格式化 issue 列表"""
        cfg = self._get_config(cfg)

        if not issues:
            return "(No issues)"

        lines = []

        # 标题
        if status_filter == 'open':
            tpl = cfg.templates.get('list_header_open', '[OPEN] {count} issues pending')
            lines.append(tpl.format(count=len(issues)))
        elif status_filter == 'resolved':
            tpl = cfg.templates.get('list_header_resolved', '[RESOLVED] {count} issues')
            lines.append(tpl.format(count=len(issues)))
        else:
            open_count = len([i for i in issues if i.get('status') == 'open'])
            resolved_count = len([i for i in issues if i.get('status') == 'resolved'])
            tpl = cfg.templates.get('list_header_all', '[ALL] {open_count} open, {resolved_count} resolved')
            lines.append(tpl.format(open_count=open_count, resolved_count=resolved_count))

        lines.append('')

        # Issue 列表
        for issue in issues:
            lines.append(self.format_issue(issue, cfg))
            lines.append('')

        return '\n'.join(lines)

    def format_timeline(self, cfg: RiskDisplayConfig = None) -> str:
        """格式化 timeline"""
        cfg = self._get_config(cfg)
        timeline = self.get_timeline()

        if not timeline:
            return "(No timeline records)"

        lines = []

        for record in timeline:
            seq = record.get('seq', 0)
            ts = record.get('timestamp', '')
            cmd = record.get('command', '')

            # 简化时间显示
            time_str = ts.split('T')[1].split('.')[0] if 'T' in ts else ts[:8]

            # Command 行
            tpl = cfg.templates.get('timeline_command', '[{seq}] {time} {command}')
            lines.append(tpl.format(seq=seq, time=time_str, command=cmd))

            # Findings
            for finding in record.get('findings', []):
                ftype = finding.get('type', '')

                if ftype == 'risk_created':
                    level = finding.get('level', 'warning')
                    color = cfg.colors.get(level, '')
                    reset = cfg.colors.get('reset', '')
                    issue_id = finding.get('issue_id', '')
                    desc = finding.get('desc', '')

                    tpl = cfg.templates.get('timeline_finding_created', '[{level}] {issue_id}: {desc}')
                    line = tpl.format(level=level.upper(), issue_id=issue_id, desc=desc)
                    if color:
                        line = f"{color}{line}{reset}"
                    lines.append(line)

                elif ftype == 'issue_resolved':
                    issue_id = finding.get('issue_id', '')
                    result = finding.get('result', '')
                    tpl = cfg.templates.get('timeline_finding_resolved', '[RESOLVED] {issue_id}: {result}')
                    lines.append(tpl.format(issue_id=issue_id, result=result))

                elif ftype == 'info':
                    msg = finding.get('message', '')
                    tpl = cfg.templates.get('timeline_info', '[INFO] {message}')
                    lines.append(tpl.format(message=msg))

            lines.append('')

        # 摘要
        summary = self.get_summary()
        lines.append(f"Commands: {summary['total_commands']}, Open: {summary['open_issues']}, Resolved: {summary['resolved_issues']}")

        return '\n'.join(lines)

    def export_markdown(self) -> str:
        """导出为 Markdown 报告"""
        lines = ["# 性能诊断报告", ""]

        # 文档信息
        lines.append(f"**数据文件**: {self.data.get('data_file', 'N/A')}")
        lines.append(f"**创建时间**: {self.data.get('created_at', 'N/A')}")
        lines.append("")

        # 摘要
        summary = self.get_summary()
        lines.append("## 执行摘要")
        lines.append(f"- 执行命令: {summary['total_commands']} 个")
        lines.append(f"- 发现问题: {summary['open_issues'] + summary['resolved_issues']} 个")
        lines.append(f"- 已解决: {summary['resolved_issues']} 个")
        lines.append(f"- 待处理: {summary['open_issues']} 个")
        lines.append("")

        # Timeline
        if self.data['timeline']:
            lines.append("## 诊断时间线")
            for record in self.data['timeline']:
                ts = record['timestamp'].split('T')[1].split('.')[0] if 'T' in record['timestamp'] else record['timestamp']
                lines.append(f"\n### [{record['seq']}] {ts}  `{record['command']}`")

                for finding in record['findings']:
                    ftype = finding.get('type', 'info')
                    if ftype == 'risk_created':
                        lines.append(f"- ⚠️  **发现风险**: {finding['desc']} (`{finding['issue_id']}`)")
                    elif ftype == 'issue_resolved':
                        lines.append(f"- ✅ **问题解决**: {finding['issue_id']} → {finding['result']}")
                    elif ftype == 'risk_duplicate':
                        lines.append(f"- ℹ️  **关联风险**: {finding['desc']} (`{finding['issue_id']}`)")
                    elif ftype == 'info':
                        lines.append(f"- ℹ️  {finding.get('message', '')}")
            lines.append("")

        # 待处理问题
        open_issues = self.get_open_issues()
        if open_issues:
            lines.append("## ⚠️ 待处理问题")
            for issue in open_issues:
                lines.append(f"\n### {issue['id']}: {issue['desc']}")
                lines.append(f"- 级别: {issue['level']}")
                if issue.get('hint'):
                    lines.append(f"- 建议: `{issue['hint']}`")
                # 显示历史 results（如果有 reopen 历史）
                reopen_history = issue.get('reopen_history', [])
                if reopen_history:
                    lines.append("- 历史记录:")
                    for i, record in enumerate(reopen_history, 1):
                        prev_results = record.get('previous_results', [])
                        if prev_results:
                            for prev_result in prev_results:
                                result_text = prev_result.get('result', '')
                                lines.append(f"  - 之前的结论: {result_text}")
            lines.append("")

        # 已解决问题
        resolved_issues = self.get_resolved_issues()
        if resolved_issues:
            lines.append("## ✅ 已解决问题")
            for issue in resolved_issues:
                lines.append(f"\n### {issue['id']}: {issue['desc']}")
                results = issue.get('results', [])
                reopen_history = issue.get('reopen_history', [])
                
                if len(results) == 1 and not reopen_history:
                    # 简单情况：只解决过一次
                    lines.append(f"- 结果: {results[0].get('result', 'N/A')}")
                else:
                    # 复杂情况：多次解决或有过 reopen
                    lines.append("- 解决记录:")
                    for i, result_entry in enumerate(results, 1):
                        result_text = result_entry.get('result', '')
                        lines.append(f"  {i}. {result_text}")
                    
                    # 显示 reopen 历史
                    if reopen_history:
                        lines.append("- 重新打开记录:")
                        for i, record in enumerate(reopen_history, 1):
                            reason = record.get('reason', 'No reason')
                            lines.append(f"  - 第{i}次 reopen: {reason}")
            lines.append("")

        return '\n'.join(lines)


# =============================================================================
# CLI 命令
# =============================================================================

def cmd_doc_init(args):
    """初始化诊断文档"""
    doc = Trace()
    doc.init(args.data)
    print(f"[INIT] Created: {doc.path}")
    print(f"→ Data file: {args.data}")


def cmd_doc_add(args):
    """手动添加 issue（自动生成 ID）"""
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


def cmd_doc_timeline(args):
    """查看时间线（使用 RiskDisplayConfig 格式化）"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)

    print(doc.format_timeline(cfg))


def _load_risk_config_from_args(args) -> RiskDisplayConfig:
    """从 args 加载 Risk 配置"""
    cfg = get_risk_config(explicit_path=getattr(args, 'risk_config', None))

    if style := getattr(args, 'risk_style', None):
        cfg.apply_mode(style)

    # CI 环境禁用颜色
    if os.getenv('NO_COLOR') or os.getenv('SPEAR_NO_COLOR'):
        cfg.colors = {k: '' for k in cfg.colors}

    return cfg


def cmd_doc_issues(args):
    """查看 issues 状态（使用 RiskDisplayConfig 格式化）"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)

    status_filter = getattr(args, 'status', 'all')

    # 获取 issues
    if status_filter == 'open':
        issues = doc.get_open_issues()
    elif status_filter == 'resolved':
        issues = doc.get_resolved_issues()
    else:
        issues = doc.get_open_issues() + doc.get_resolved_issues()

    # 格式化输出
    print(doc.format_issue_list(issues, status_filter, cfg))

    # 提示用法
    if status_filter in ['all', 'open'] and doc.get_open_issues():
        print(f"Usage: spear trace complete --id ISS-001 --result '分析结果'")


def cmd_doc_complete(args):
    """标记 issue 为已完成（人工执行）"""
    doc = Trace()

    try:
        doc.complete(args.id, args.result)
        print(f"[COMPLETED] {args.id}")
        print(f"→ Result: {args.result}")

        # 显示剩余 open issues
        open_issues = doc.get_open_issues()
        if open_issues:
            print(f"\n→ {len(open_issues)} issues remaining")
        else:
            print("\n[ALL DONE] No more issues")
    except ValueError as e:
        print(f"[ERROR] {e}")


def cmd_doc_reopen(args):
    """重新打开已解决的 issue"""
    doc = Trace()

    # 检查参数：--id 或 --all 必须指定其一
    if not args.id and not args.all:
        print("[ERROR] Must specify --id or --all")
        return

    if args.all:
        # 重新打开所有已解决的 issue
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

        # 显示当前 open issues
        open_issues = doc.get_open_issues()
        print(f"\n→ {len(open_issues)} issues now open")
    else:
        # 重新打开单个 issue
        try:
            issue_id = doc.reopen(args.id, getattr(args, 'reason', ''))
            print(f"[REOPENED] {issue_id}")
            if args.reason:
                print(f"→ Reason: {args.reason}")

            # 显示当前 open issues
            open_issues = doc.get_open_issues()
            print(f"\n→ {len(open_issues)} issues now open")
        except ValueError as e:
            print(f"[ERROR] {e}")


def cmd_doc_finalize(args):
    """最终确认（检查 open issues，准备生成报告）"""
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)
    result = doc.finalize(getattr(args, 'accept_risk', None))

    print("=" * 65)
    print("FINALIZE - Ready to generate report?")
    print("=" * 65)
    print()

    if result['status'] == 'ready':
        print("[READY] All issues resolved")
        print(f"→ Total resolved: {result['resolved_count']}")
        print()
        print("=" * 65)
        print("Report can be generated")
        print("=" * 65)

    elif result['status'] == 'accepted':
        print(f"[ACCEPTED] Risk accepted: {args.accept_risk}")
        print(f"→ Resolved: {result['resolved_count']}, Accepted: {result['open_count']}")
        print()
        print("=" * 65)
        print("Report can be generated")
        print("=" * 65)

    else:  # blocked
        print(f"[BLOCKED] {len(result['open_issues'])} open issues remaining")
        print()
        print("Note: This is NOT an audit. Use 'spear trace audit' for quality review.")
        print()
        for issue in result['open_issues']:
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
        print("[A] Continue analysis (recommended)")
        print("[B] Accept risk and finalize: --accept-risk 'reason'")
        print("=" * 65)
        import sys
        sys.exit(1)


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


# =============================================================================
# 审计功能
# =============================================================================

def cmd_doc_audit(args):
    """
    审计 resolved issues 的分析质量
    
    检查项：
    1. 结构完整性：result 非空、非敷衍
    2. Timeline 关联：有分析命令支撑
    3. 分析深度：result 包含因果推导
    """
    cfg = _load_risk_config_from_args(args)
    doc = Trace(config=cfg)
    
    phase = getattr(args, 'phase', 'all')
    output = getattr(args, 'output', None)
    
    # 获取所有 resolved issues
    resolved_issues = doc.get_resolved_issues()
    
    if not resolved_issues:
        print("[AUDIT] No resolved issues to audit")
        return
    
    # 执行审计检查
    audit_results = []
    failed_count = 0
    warning_count = 0
    passed_count = 0
    
    for issue in resolved_issues:
        result = _audit_issue(issue, doc.data.get('timeline', []), phase)
        audit_results.append(result)
        
        if result['status'] == 'failed':
            failed_count += 1
        elif result['status'] == 'warning':
            warning_count += 1
        else:
            passed_count += 1
    
    # 生成报告
    report = {
        "audit_time": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_issues": len(resolved_issues),
            "passed": passed_count,
            "failed": failed_count,
            "warnings": warning_count
        },
        "issues": audit_results
    }
    
    # 输出格式
    fmt = getattr(args, 'format', 'text')
    
    if fmt == 'json':
        content = json.dumps(report, indent=2, ensure_ascii=False)
        if output:
            with open(output, 'w') as f:
                f.write(content)
            print(f"[AUDIT REPORT SAVED] {output}")
        else:
            print(content)
    else:
        _print_audit_report(report, cfg, output)
    
    # 如果有失败项，返回非零退出码
    if failed_count > 0 and not getattr(args, 'no_fail', False):
        import sys
        sys.exit(1)


def _audit_issue(issue: Dict, timeline: List[Dict], phase: str) -> Dict:
    """审计单个 issue"""
    issue_id = issue.get('id', 'unknown')
    result_text = issue.get('result', '') or ''
    created_seq = issue.get('created_by_seq')
    resolved_seq = issue.get('resolved_by_seq')
    created_at = issue.get('created_at', '')
    resolved_at = issue.get('resolved_at', '')
    
    checks = {}
    failures = []
    warnings = []
    
    # Phase 1: 结构完整性
    if phase in ('all', 'structural'):
        # Check has_result
        if not result_text or result_text.strip() == '':
            checks['has_result'] = False
            failures.append("Empty result")
        else:
            checks['has_result'] = True
        
        # Check敷衍标记
        perfunctory_markers = ['ok', 'done', 'fixed', 'yes', 'no', 'ok.', 'done.', 'fixed.']
        if result_text.strip().lower() in perfunctory_markers:
            checks['substantive_result'] = False
            failures.append(f"Perfunctory result: '{result_text}'")
        else:
            checks['substantive_result'] = True
    
    # Phase 2: Timeline 关联
    if phase in ('all', 'timeline'):
        # Check 分析时间间隔
        if created_at and resolved_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                resolved_dt = datetime.fromisoformat(resolved_at.replace('Z', '+00:00'))
                duration = (resolved_dt - created_dt).total_seconds()
                checks['analysis_duration_seconds'] = duration
                
                if duration < 30:  # 30秒内完成 = 可疑
                    checks['sufficient_analysis_time'] = False
                    warnings.append(f"Analysis time too short: {duration:.1f}s")
                else:
                    checks['sufficient_analysis_time'] = True
            except:
                checks['sufficient_analysis_time'] = None
        
        # Check timeline 支撑
        if created_seq and timeline:
            # 查找 created_seq 之后的命令
            analysis_commands = []
            for record in timeline:
                if record.get('seq', 0) > created_seq:
                    # 排除 trace 自身的命令
                    cmd = record.get('command', '')
                    if not cmd.startswith('trace '):
                        analysis_commands.append(cmd)
            
            if analysis_commands:
                checks['has_timeline_support'] = True
                checks['analysis_commands_count'] = len(analysis_commands)
            else:
                checks['has_timeline_support'] = False
                if resolved_seq is None:
                    failures.append("No analysis commands found (resolved_by_seq is null)")
                else:
                    warnings.append("No analysis commands in timeline")
        else:
            checks['has_timeline_support'] = None
    
    # Phase 3: 分析深度（启发式检查）
    if phase in ('all', 'depth'):
        # Check 是否包含文档引用
        has_doc_ref = 'debug/' in result_text or '.md' in result_text
        checks['has_document_reference'] = has_doc_ref
        
        # Check 是否包含因果词
        causal_words = ['根因', '原因', '导致', '因为', 'caused by', 'root cause', 
                       '排除', 'verified', 'confirmed', 'identified']
        has_causal = any(word in result_text.lower() for word in causal_words)
        checks['has_causal_analysis'] = has_causal
        
        if not has_causal and len(result_text) < 50:
            warnings.append("Result lacks causal analysis")
    
    # 确定最终状态
    if failures:
        status = 'failed'
    elif warnings:
        status = 'warning'
    else:
        status = 'passed'
    
    return {
        "id": issue_id,
        "desc": issue.get('desc', ''),
        "status": status,
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "action_required": "Reopen and add analysis" if status == 'failed' else None
    }


def _print_audit_report(report: Dict, cfg: RiskDisplayConfig, output_path: str = None):
    """打印审计报告（文本格式）"""
    lines = []
    
    # Header
    lines.append("=" * 65)
    lines.append("AUDIT REPORT")
    lines.append("=" * 65)
    lines.append(f"Audit Time: {report['audit_time']}")
    lines.append("")
    
    # Summary
    summary = report['summary']
    lines.append("SUMMARY")
    lines.append("-" * 65)
    lines.append(f"Total Issues: {summary['total_issues']}")
    lines.append(f"  ✅ Passed:   {summary['passed']}")
    lines.append(f"  ⚠️  Warnings: {summary['warnings']}")
    lines.append(f"  ❌ Failed:   {summary['failed']}")
    lines.append(f"Pass Rate: {summary['passed']/summary['total_issues']*100:.1f}%")
    lines.append("")
    
    # Failed Issues
    failed_issues = [i for i in report['issues'] if i['status'] == 'failed']
    if failed_issues:
        lines.append("FAILED ISSUES (Action Required)")
        lines.append("-" * 65)
        for issue in failed_issues:
            color = cfg.colors.get('critical', '')
            reset = cfg.colors.get('reset', '')
            lines.append(f"{color}[FAIL] {issue['id']}: {issue['desc']}{reset}")
            for failure in issue['failures']:
                lines.append(f"  └─ {failure}")
            if issue['action_required']:
                lines.append(f"  → Action: {issue['action_required']}")
            lines.append("")
    
    # Warning Issues
    warning_issues = [i for i in report['issues'] if i['status'] == 'warning']
    if warning_issues:
        lines.append("WARNINGS (Recommended to Improve)")
        lines.append("-" * 65)
        for issue in warning_issues:
            color = cfg.colors.get('warning', '')
            reset = cfg.colors.get('reset', '')
            lines.append(f"{color}[WARN] {issue['id']}: {issue['desc']}{reset}")
            for warning in issue['warnings']:
                lines.append(f"  └─ {warning}")
            lines.append("")
    
    # Passed Issues
    passed_issues = [i for i in report['issues'] if i['status'] == 'passed']
    if passed_issues:
        lines.append("PASSED ISSUES")
        lines.append("-" * 65)
        for issue in passed_issues:
            lines.append(f"[PASS] {issue['id']}: {issue['desc']}")
        lines.append("")
    
    # Footer
    lines.append("=" * 65)
    if failed_issues:
        lines.append("AUDIT FAILED - Fix issues before finalize")
        lines.append("Command: spear trace reopen --all --reason 'audit failed'")
    elif warning_issues:
        lines.append("AUDIT PASSED with warnings")
    else:
        lines.append("AUDIT PASSED - All issues meet quality standards")
    lines.append("=" * 65)
    
    content = '\n'.join(lines)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(content)
        print(f"[AUDIT REPORT SAVED] {output_path}")
    else:
        print(content)
    
    return content
