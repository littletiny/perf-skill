#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Document v2.0 - Tracing 工具

自动记录诊断过程，无需人工干预：
- timeline: 按时间顺序记录所有命令执行
- issues: 问题聚合状态
- 双向链接: timeline 和 issues 互相引用

设计文档: docs/design-rationale-livedoc-tracing-v2.md
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Any


class LiveDoc:
    """
    Live Document v2.0 - 自动 Tracing 实现
    
    数据文件: .perf-doc.json (当前目录)
    """

    DEFAULT_PATH = ".spear.json"
    CURRENT_VERSION = "2.0"

    def __init__(self, path: Optional[str] = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self._current_seq = None

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
        return seq

    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """
        记录发现的风险，自动创建 issue
        
        Args:
            level: critical/warning/info
            desc: 风险描述
            hint: 建议操作
            
        Returns:
            issue_id: 创建的 issue ID
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

    def record_resolution(self, issue_id: str, result: str):
        """
        标记 issue 已解决
        
        Args:
            issue_id: 要解决的 issue ID
            result: 分析结果/结论
        """
        if issue_id not in self.data['issues']:
            # 尝试模糊匹配
            issue_id = self._fuzzy_find_issue(issue_id) or issue_id
        
        if issue_id in self.data['issues']:
            issue = self.data['issues'][issue_id]
            issue['status'] = 'resolved'
            issue['result'] = result
            issue['resolved_at'] = self._now()
            issue['resolved_by_seq'] = self._current_seq
            
            self._add_finding_to_current({
                "type": "issue_resolved",
                "issue_id": issue_id,
                "result": result
            })
            self.save()

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
            lines.append("")
        
        # 已解决问题
        resolved_issues = self.get_resolved_issues()
        if resolved_issues:
            lines.append("## ✅ 已解决问题")
            for issue in resolved_issues:
                lines.append(f"\n### {issue['id']}: {issue['desc']}")
                lines.append(f"- 结果: {issue.get('result', 'N/A')}")
            lines.append("")
        
        return '\n'.join(lines)


# =============================================================================
# CLI 命令
# =============================================================================

def cmd_doc_init(args):
    """初始化诊断文档"""
    doc = LiveDoc()
    doc.init(args.data)
    print(f"✓ 创建诊断文档: {doc.path}")
    print(f"  数据文件: {args.data}")


def cmd_doc_add(args):
    """手动添加 issue（用户主动添加）"""
    try:
        doc = LiveDoc()
        doc.add(args.id, args.desc, getattr(args, 'risk', ''), getattr(args, 'hint', ''))
        print(f"✓ 已添加问题: {args.id}")
        print(f"  描述: {args.desc}")
    except ValueError as e:
        print(f"✗ 错误: {e}")


def cmd_doc_timeline(args):
    """查看时间线"""
    doc = LiveDoc()
    timeline = doc.get_timeline()
    
    if not timeline:
        print("尚无命令执行记录")
        return
    
    print("=" * 65)
    print(f"DIAGNOSIS TIMELINE  ({len(timeline)} commands executed)")
    print("=" * 65)
    print()
    
    for record in timeline:
        ts = record['timestamp'].split('T')[1].split('.')[0] if 'T' in record['timestamp'] else record['timestamp']
        print(f"[{record['seq']}] {ts}  {record['command']}")
        
        for finding in record['findings']:
            ftype = finding.get('type', 'info')
            if ftype == 'risk_created':
                level_icon = "🔴" if finding['level'] == 'critical' else "🟡"
                print(f"    {level_icon} RISK_CREATED: {finding['issue_id']} - {finding['desc']}")
            elif ftype == 'issue_resolved':
                print(f"    ✅ RESOLVED: {finding['issue_id']} → {finding['result'][:40]}...")
            elif ftype == 'risk_duplicate':
                print(f"    ℹ️  RELATED: {finding['issue_id']}")
        print()
    
    # 摘要
    summary = doc.get_summary()
    print("=" * 65)
    print(f"ISSUES: {summary['resolved_issues']} resolved, {summary['open_issues']} open")
    print("=" * 65)


def cmd_doc_issues(args):
    """查看 issues 状态"""
    doc = LiveDoc()
    
    status_filter = getattr(args, 'status', 'all')
    
    if status_filter in ['all', 'open']:
        open_issues = doc.get_open_issues()
        if open_issues:
            print("\n⚠️  OPEN ISSUES (待处理)")
            print("-" * 65)
            for issue in open_issues:
                level_icon = "🔴" if issue['level'] == 'critical' else "🟡"
                print(f"{level_icon} {issue['id']}: {issue['desc']}")
                if issue.get('hint'):
                    print(f"   └─ 建议: {issue['hint']}")
            print()
    
    if status_filter in ['all', 'resolved']:
        resolved_issues = doc.get_resolved_issues()
        if resolved_issues:
            print("\n✅ RESOLVED ISSUES")
            print("-" * 65)
            for issue in resolved_issues:
                print(f"{issue['id']}: {issue['desc']}")
                print(f"   └─ 结果: {issue.get('result', 'N/A')}")
            print()


def cmd_doc_complete(args):
    """标记 issue 为已完成（人工执行）"""
    doc = LiveDoc()
    
    try:
        doc.complete(args.id, args.result)
        print(f"✓ 已完成: {args.id}")
        print(f"  结果: {args.result}")
        
        # 显示剩余 open issues
        open_issues = doc.get_open_issues()
        if open_issues:
            print(f"\n  剩余 {len(open_issues)} 个待处理 issue")
        else:
            print("\n  🎉 所有 issue 已处理完毕")
    except ValueError as e:
        print(f"✗ 错误: {e}")


def cmd_doc_finalize(args):
    """最终审计"""
    doc = LiveDoc()
    result = doc.finalize(getattr(args, 'accept_risk', None))
    
    print("=" * 65)
    print("最终全局审计")
    print("=" * 65)
    print()
    
    if result['status'] == 'ready':
        print("✅ 所有问题已处理")
        print(f"   共解决 {result['resolved_count']} 个问题")
        print()
        print("=" * 65)
        print("可以生成诊断报告")
        print("=" * 65)
    
    elif result['status'] == 'accepted':
        print(f"⚠️  已接受风险: {args.accept_risk}")
        print(f"   已解决: {result['resolved_count']}, 接受: {result['open_count']}")
        print()
        print("=" * 65)
        print("可以生成诊断报告")
        print("=" * 65)
    
    else:  # blocked
        print(f"⚠️  存在 {len(result['open_issues'])} 个未处理问题")
        print()
        for issue in result['open_issues']:
            level_icon = "🔴" if issue['level'] == 'critical' else "🟡"
            print(f"{level_icon} {issue['id']}: {issue['desc']}")
            if issue.get('hint'):
                print(f"   └─ 建议: {issue['hint']}")
        print()
        print("-" * 65)
        print("[A] 继续分析剩余问题（推荐）")
        print("[B] 接受风险: --accept-risk '理由'")
        print("=" * 65)
        import sys
        sys.exit(1)


def cmd_doc_export(args):
    """导出报告"""
    doc = LiveDoc()
    fmt = getattr(args, 'format', 'markdown')
    output = getattr(args, 'output', None)
    
    if fmt == 'markdown':
        content = doc.export_markdown()
    else:
        content = json.dumps(doc.data, indent=2, ensure_ascii=False)
    
    if output:
        with open(output, 'w') as f:
            f.write(content)
        print(f"✓ 导出报告: {output}")
    else:
        print(content)
