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
import copy
from datetime import datetime
from typing import List, Dict, Optional, Any, Optional
from dataclasses import asdict

from .risk_config import RiskDisplayConfig, get_risk_config
from .output_models import TimelineRecord, Issue, ResolutionResult, ReopenRecord, TraceSummary, FinalizeResult


class Trace:
    """
    Trace v2.0 - 诊断过程追踪实现

    数据文件: .perf-doc.json (当前目录)
    """

    DEFAULT_PATH = ".shecr.json"
    CURRENT_VERSION = "2.0"

    def __init__(self, path: Optional[str] = None, config: RiskDisplayConfig = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self._current_seq = None
        self._current_fingerprint: Optional[str] = None  # 当前命令指纹
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
        """加载文档"""
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)

        # 新文档
        return self._create_new_dict()

    def _create_new_dict(self) -> Dict:
        """创建新文档结构（返回 dict 用于 JSON 序列化）"""
        now = self._now()
        return {
            "version": self.CURRENT_VERSION,
            "data_file": None,
            "created_at": now,
            "updated_at": now,
            "timeline": [],
            "issues": {}
        }

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
        self.data = self._create_new_dict()
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
        self._current_fingerprint = command  # 保存完整命令作为指纹

        # 使用 TimelineRecord dataclass，然后转换为 dict
        record = TimelineRecord(
            seq=seq,
            type="command",
            command=command,
            timestamp=self._now(),
            findings=[]
        )
        self.data['timeline'].append(asdict(record))
        self.save()
        
        # 无脑输出所有 open issues
        self._print_issue_overflow_warning()
        
        return seq
    
    def _print_issue_overflow_warning(self):
        """统一的问题未闭环警告入口（当前禁用）"""
        pass
    
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

    def add(self, desc: str, risk: str = "", hint: str = "", level: str = "warning") -> Optional[str]:
        """
        添加新 issue（自动生成 ID）
        
        命令指纹去重：如果相同指纹且相同描述的 open issue 已存在，则不创建新 issue，
        而是在 timeline 中记录为关联风险。

        Args:
            desc: 问题描述
            risk: 风险描述
            hint: 建议操作
            level: 级别 critical/warning/info

        Returns:
            issue_id: 创建的 issue ID，如果去重跳过则返回 None
        """
        # 检查是否有相同指纹和相同描述的 open issue
        fingerprint = getattr(self, '_current_fingerprint', None)
        if fingerprint:
            for existing_id, existing_issue in self.data['issues'].items():
                if (existing_issue.get('status') == 'open' and
                    existing_issue.get('command_fingerprint') == fingerprint and
                    existing_issue.get('desc') == desc):
                    # 存在相同指纹且相同描述的 open issue，记录为关联风险而非新建
                    self._add_finding_to_current({
                        "type": "risk_duplicate",
                        "level": level,
                        "desc": desc,
                        "issue_id": existing_id,
                        "message": f"关联到已存在的 {existing_id}"
                    })
                    self.save()
                    return None  # 返回 None 表示已存在，跳过创建
        
        # 创建新 issue
        issue_id = self._generate_issue_id()
        now = self._now()

        # 使用 Issue dataclass，然后转换为 dict
        # 添加 command_fingerprint 字段用于后续去重
        issue_dict = asdict(Issue(
            id=issue_id,
            desc=desc,
            level=level,
            status="open",
            created_at=now,
            created_by_seq=self._current_seq,
            resolved_at=None,
            resolved_by_seq=None,
            result=None,
            hint=hint
        ))
        issue_dict['command_fingerprint'] = fingerprint  # 添加指纹字段
        
        self.data['issues'][issue_id] = issue_dict

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
            
            # 使用 ResolutionResult dataclass，然后转换为 dict
            result_entry = ResolutionResult(
                result=result,
                resolved_at=self._now(),
                resolved_by_seq=self._current_seq
            )
            issue['results'].append(asdict(result_entry))
            
            # 同时更新单字段 result（兼容性）
            issue['result'] = result
            issue['status'] = 'resolved'
            issue['resolved_at'] = result_entry.resolved_at
            issue['resolved_by_seq'] = result_entry.resolved_by_seq

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
            
            # 使用 ReopenRecord dataclass，然后转换为 dict
            reopen_record = ReopenRecord(
                reopened_at=self._now(),
                reason=reason,
                previous_result=issue.get('result'),
                previous_resolved_at=issue.get('resolved_at'),
                previous_resolved_by_seq=issue.get('resolved_by_seq'),
                previous_results=copy.deepcopy(issue.get('results', []))  # 深拷贝 results 列表
            )
            
            if 'reopen_history' not in issue:
                issue['reopen_history'] = []
            issue['reopen_history'].append(asdict(reopen_record))
            
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
        self._current_fingerprint = None  # 清除指纹
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

    def get_summary(self) -> TraceSummary:
        """获取摘要统计（返回 TraceSummary dataclass）"""
        open_issues = self.get_open_issues()
        resolved_issues = self.get_resolved_issues()
        return TraceSummary(
            total_commands=len(self.data['timeline']),
            open_issues=len(open_issues),
            resolved_issues=len(resolved_issues),
            can_finalize=len(open_issues) == 0
        )

    # =====================================================================
    # 最终审计
    # =====================================================================

    def finalize(self, accept_risk: Optional[str] = None) -> FinalizeResult:
        """
        最终审计 - 检查是否可以结束诊断

        Returns:
            FinalizeResult dataclass
        """
        open_issues = self.get_open_issues()

        if not open_issues:
            return FinalizeResult(
                status="ready",
                message="All issues resolved, ready to generate report",
                resolved_count=len(self.get_resolved_issues())
            )

        if accept_risk:
            return FinalizeResult(
                status="accepted",
                message=f"Accepted risk: {accept_risk}",
                open_count=len(open_issues),
                resolved_count=len(self.get_resolved_issues())
            )

        return FinalizeResult(
            status="blocked",
            message=f"Found {len(open_issues)} open issues",
            open_issues=open_issues
        )

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
        lines.append(f"Commands: {summary.total_commands}, Open: {summary.open_issues}, Resolved: {summary.resolved_issues}")

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
        lines.append(f"- 执行命令: {summary.total_commands} 个")
        lines.append(f"- 发现问题: {summary.open_issues + summary.resolved_issues} 个")
        lines.append(f"- 已解决: {summary.resolved_issues} 个")
        lines.append(f"- 待处理: {summary.open_issues} 个")
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



# NOTE: CLI commands have been migrated to cli/commands/trace/*.py
