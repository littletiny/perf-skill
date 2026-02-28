#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Document for tracking diagnostic issues

实现 live-doc-interface.md 定义的接口：
- init: 初始化文档
- add: 添加问题
- complete: 标记完成
- list: 列出问题
- finalize: 最终审计
- export: 导出报告
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class LiveDoc:
    """Live Document for tracking diagnostic issues"""

    DEFAULT_PATH = ".perf-doc.json"

    def __init__(self, path: Optional[str] = None):
        self.path = path or self._find_doc()
        self.data = self._load()

    def _find_doc(self) -> str:
        """Find existing doc or return default path"""
        if os.path.exists(self.DEFAULT_PATH):
            return self.DEFAULT_PATH
        return self.DEFAULT_PATH

    def _load(self) -> Dict:
        """Load document from disk"""
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"version": "1.0", "issues": []}

    def save(self):
        """Save document to disk"""
        self.data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def init(self, data_file: str, path: Optional[str] = None):
        """Initialize new document"""
        if path:
            self.path = path

        self.data = {
            "version": "1.0",
            "data_file": data_file,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "issues": []
        }
        self.save()
        return self

    def add(self, id: str, desc: str, risk: str = "", hint: str = ""):
        """Add new issue"""
        # Check duplicate
        if any(i["id"] == id for i in self.data["issues"]):
            raise ValueError(f"Duplicate issue ID: {id}")

        issue = {
            "id": id,
            "desc": desc,
            "status": "pending",
            "risk": risk,
            "hint": hint,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        self.data["issues"].append(issue)
        self.save()
        return self

    def complete(self, id: str, result: str):
        """Mark issue as completed"""
        for issue in self.data["issues"]:
            if issue["id"] == id:
                issue["status"] = "completed"
                issue["result"] = result
                issue["completed_at"] = datetime.utcnow().isoformat() + "Z"
                self.save()
                return self

        raise ValueError(f"Issue not found: {id}")

    def list(self, status: str = "all") -> Dict:
        """List issues"""
        issues = self.data["issues"]

        if status == "pending":
            issues = [i for i in issues if i["status"] == "pending"]
        elif status == "completed":
            issues = [i for i in issues if i["status"] == "completed"]

        pending = [i for i in issues if i["status"] == "pending"]
        completed = [i for i in issues if i["status"] == "completed"]

        return {
            "pending_count": len(pending),
            "completed_count": len(completed),
            "can_converge": len(pending) == 0,
            "pending": pending,
            "completed": completed
        }

    def next_id(self) -> str:
        """Generate next issue ID"""
        count = len(self.data["issues"]) + 1
        return f"ISS-{count:03d}"

    def finalize(self, accept_risk: Optional[str] = None) -> Dict:
        """
        Finalize document - check if all issues are resolved.
        
        Returns:
            Dict with status and message
        """
        status_info = self.list()
        
        if status_info["pending_count"] == 0:
            return {
                "status": "ready",
                "message": "所有问题已处理，可以生成报告",
                "completed_issues": status_info["completed_count"]
            }
        
        # Has pending issues
        if accept_risk:
            return {
                "status": "accepted",
                "message": f"已接受风险: {accept_risk}",
                "pending_issues": status_info["pending_count"],
                "completed_issues": status_info["completed_count"]
            }
        
        return {
            "status": "blocked",
            "message": f"存在 {status_info['pending_count']} 个未处理问题",
            "pending": [
                {
                    "id": i["id"],
                    "desc": i["desc"],
                    "hint": i.get("hint", "")
                }
                for i in status_info["pending"]
            ]
        }

    def export_markdown(self) -> str:
        """Export document as Markdown report"""
        lines = ["# 性能诊断报告", ""]
        
        # Document info
        lines.append(f"**数据文件**: {self.data.get('data_file', 'N/A')}")
        lines.append(f"**创建时间**: {self.data.get('created_at', 'N/A')}")
        lines.append(f"**更新时间**: {self.data.get('updated_at', 'N/A')}")
        lines.append("")
        
        # Summary
        status = self.list()
        lines.append("## 问题汇总")
        lines.append(f"- 已完成: {status['completed_count']}")
        lines.append(f"- 待处理: {status['pending_count']}")
        lines.append("")
        
        # Completed issues
        if status["completed"]:
            lines.append("## 已完成问题")
            for issue in status["completed"]:
                lines.append(f"### {issue['id']}: {issue['desc']}")
                if issue.get('result'):
                    lines.append(f"**结果**: {issue['result']}")
                lines.append("")
        
        # Pending issues
        if status["pending"]:
            lines.append("## 待处理问题")
            for issue in status["pending"]:
                lines.append(f"### {issue['id']}: {issue['desc']}")
                if issue.get('risk'):
                    lines.append(f"**风险**: {issue['risk']}")
                if issue.get('hint'):
                    lines.append(f"**建议**: {issue['hint']}")
                lines.append("")
        
        return '\n'.join(lines)


def cmd_doc_init(args):
    """Initialize a new diagnosis document"""
    doc = LiveDoc()
    doc.init(args.data, args.path)
    print(f"✓ 创建诊断文档: {doc.path}")
    print(f"  数据文件: {args.data}")


def cmd_doc_add(args):
    """Add a new issue to the document"""
    try:
        doc = LiveDoc()
        doc.add(args.id, args.desc, getattr(args, 'risk', ''), getattr(args, 'hint', ''))
        print(f"✓ 已添加问题: {args.id}")
        print(f"  描述: {args.desc}")
    except ValueError as e:
        print(f"✗ 错误: {e}")


def cmd_doc_complete(args):
    """Mark an issue as completed"""
    try:
        doc = LiveDoc()
        doc.complete(args.id, args.result)
        print(f"✓ 已完成: {args.id}")
        print(f"  结果: {args.result}")
    except ValueError as e:
        print(f"✗ 错误: {e}")


def cmd_doc_list(args):
    """List all issues"""
    doc = LiveDoc()
    status = doc.list(args.status)
    
    if args.format == 'json':
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return
    
    # Text format
    print("=" * 60)
    print(f"ISSUES  STATUS  ({status['completed_count']} completed, {status['pending_count']} pending)")
    print("=" * 60)
    print()
    
    if status["completed"]:
        print("✅ COMPLETED")
        print("-" * 60)
        for issue in status["completed"]:
            print(f"{issue['id']}  {issue['desc']}")
            if issue.get('result'):
                print(f"         └─ 结果: {issue['result']}")
        print()
    
    if status["pending"]:
        print("⚠️  PENDING  ← 需处理")
        print("-" * 60)
        for issue in status["pending"]:
            print(f"{issue['id']}  {issue['desc']}")
            if issue.get('risk'):
                print(f"         ├─ 风险: {issue['risk']}")
            if issue.get('hint'):
                print(f"         └─ 建议: {issue['hint']}")
        print()
    
    print("=" * 60)


def cmd_doc_finalize(args):
    """Finalize document - check if ready to generate report"""
    doc = LiveDoc()
    result = doc.finalize(args.accept_risk)
    
    if args.format == 'json':
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    # Text format
    print("=" * 60)
    print("最终全局审计")
    print("=" * 60)
    print()
    
    if result["status"] == "ready":
        print("✅ 所有问题已处理")
        print()
        print("已完成清单:")
        status = doc.list()
        for issue in status["completed"]:
            print(f"  {issue['id']}  {issue['desc']} → {issue.get('result', 'N/A')}")
        print()
        print("=" * 60)
        print("✓ 可以生成诊断报告")
        print("=" * 60)
    
    elif result["status"] == "accepted":
        print(f"⚠️  已接受风险: {args.accept_risk}")
        print()
        print("=" * 60)
        print("✓ 可以生成诊断报告")
        print("=" * 60)
    
    else:  # blocked
        print("⚠️  剩余风险确认")
        print("-" * 60)
        print("以下问题尚未处理：")
        print()
        for pending in result["pending"]:
            print(f"{pending['id']}  {pending['desc']}")
            if pending.get('hint'):
                print(f"  - 建议: {pending['hint']}")
        print()
        print("-" * 60)
        print("强制选择")
        print("-" * 60)
        print()
        print("[A] 继续分析剩余问题（推荐）")
        print(f"    执行: {result['pending'][0]['hint'] if result['pending'] else 'cluster-symbols --comm <target>'}")
        print()
        print("[B] 接受风险，生成报告")
        print("    必须提供理由（使用 --accept-risk）")
        print()
        print("[C] 标记为无需处理")
        print("    执行: perf-doc complete --id <id> --result 'wontfix: <理由>'")
        print()
        print("=" * 60)
        print("ERROR: 存在未处理问题，无法直接生成报告")
        print("请选择 [A/B/C] 或提供 --accept-risk")
        import sys
        sys.exit(1)


def cmd_doc_export(args):
    """Export document to other formats"""
    doc = LiveDoc()
    
    if args.format == 'markdown':
        content = doc.export_markdown()
        if args.output:
            with open(args.output, 'w') as f:
                f.write(content)
            print(f"✓ 导出 Markdown 报告: {args.output}")
        else:
            print(content)
    else:
        # JSON format
        output = {
            "version": doc.data.get("version", "1.0"),
            "data_file": doc.data.get("data_file", ""),
            "created_at": doc.data.get("created_at", ""),
            "updated_at": doc.data.get("updated_at", ""),
            **doc.list()
        }
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"✓ 导出 JSON: {args.output}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
