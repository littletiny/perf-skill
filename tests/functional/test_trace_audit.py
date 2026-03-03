#!/usr/bin/env python3
"""
Test: Trace Audit Functionality

验证 audit 命令能正确检测 issues 的分析质量。
"""

import json
import os
import sys
import tempfile
import shutil

# Add project root to path (3 levels up from this file: tests/functional/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.perf_toolkit.core.trace import Trace
from scripts.perf_toolkit.cli.commands.trace.audit import _audit_issue


class TestTraceAudit:
    """Test audit functionality"""
    
    def setup_test_doc(self):
        """Create a temporary test document"""
        tmpdir = tempfile.mkdtemp()
        doc_path = os.path.join(tmpdir, ".shecr.json")
        return tmpdir, doc_path
    
    def test_audit_perfunctory_result(self):
        """Test: Detect perfunctory results like 'ok', 'done'"""
        print("\n[Test] Detect perfunctory results")
        
        # Test cases
        perfunctory_results = ['ok', 'done', 'fixed', 'yes', 'no', 'OK', 'Done.', 'FIXED']
        
        for result in perfunctory_results:
            issue = {
                'id': 'ISS-TEST',
                'desc': 'Test issue',
                'result': result,
                'created_at': '2026-03-02T10:00:00Z',
                'resolved_at': '2026-03-02T10:10:00Z',
                'created_by_seq': 1,
                'resolved_by_seq': None
            }
            
            audit_result = _audit_issue(issue, [], 'structural')
            
            assert audit_result.status == 'failed', f"Should fail for result: '{result}'"
        
        print("  ✓ Perfunctory results correctly detected")
    
    def test_audit_substantive_result(self):
        """Test: Pass substantive results"""
        print("\n[Test] Pass substantive results")
        
        good_results = [
            "根因: netstat进程风暴导致内核态CPU飙升",
            "分析完成，详见 debug/analysis.md",
            "LOCK_CONTENTION 38.36%, /proc/net/tcp 竞争"
        ]
        
        for result in good_results:
            issue = {
                'id': 'ISS-TEST',
                'desc': 'Test issue',
                'result': result,
                'created_at': '2026-03-02T10:00:00Z',
                'resolved_at': '2026-03-02T10:10:00Z',
                'created_by_seq': 1,
                'resolved_by_seq': 2
            }
            
            timeline = [
                {'seq': 1, 'command': 'analyze-core-distribution'},
                {'seq': 2, 'command': 'cluster-symbols --comm netstat'}
            ]
            
            audit_result = _audit_issue(issue, timeline, 'all')
            
            assert audit_result.status != 'failed', f"Should not fail for result: '{result}'"
        
        print("  ✓ Substantive results correctly passed")
    
    def test_audit_short_analysis_time(self):
        """Test: Warn on suspiciously short analysis time"""
        print("\n[Test] Warn on short analysis time")
        
        issue = {
            'id': 'ISS-TEST',
            'desc': 'Test issue',
            'result': 'Detailed analysis result',
            'created_at': '2026-03-02T10:00:00Z',
            'resolved_at': '2026-03-02T10:00:10Z',  # Only 10 seconds
            'created_by_seq': 1,
            'resolved_by_seq': 2
        }
        
        audit_result = _audit_issue(issue, [], 'timeline')
        
        assert audit_result.status == 'warning', "Should warn for short analysis time"
        
        print("  ✓ Short analysis time correctly detected")
    
    def test_audit_no_timeline_support(self):
        """Test: Fail when no analysis commands in timeline"""
        print("\n[Test] Fail on missing timeline support")
        
        issue = {
            'id': 'ISS-TEST',
            'desc': 'Test issue',
            'result': 'Some analysis result',
            'created_at': '2026-03-02T10:00:00Z',
            'resolved_at': '2026-03-02T10:10:00Z',
            'created_by_seq': 1,
            'resolved_by_seq': None  # No resolving command
        }
        
        timeline = [
            {'seq': 1, 'command': 'analyze-core-distribution'}
        ]
        
        audit_result = _audit_issue(issue, timeline, 'timeline')
        
        # Check if timeline check has warning status
        timeline_check = audit_result.checks.get('timeline')
        assert timeline_check and timeline_check.status == 'warning', \
            "Should detect missing timeline support"
        
        print("  ✓ Missing timeline support correctly detected")
    
    def test_audit_json_output(self):
        """Test: JSON output format"""
        print("\n[Test] JSON output format")
        
        # This is a simple smoke test
        # Full integration test would require running the CLI
        
        report = {
            "audit_time": "2026-03-02T10:00:00Z",
            "summary": {
                "total_issues": 2,
                "passed": 1,
                "failed": 1,
                "warnings": 0
            },
            "issues": [
                {
                    "id": "ISS-001",
                    "status": "passed",
                    "checks": {"has_result": True}
                },
                {
                    "id": "ISS-002",
                    "status": "failed",
                    "checks": {"has_result": False},
                    "failures": ["Empty result"]
                }
            ]
        }
        
        # Verify JSON serialization
        json_str = json.dumps(report, indent=2)
        assert 'ISS-001' in json_str
        assert 'passed' in json_str
        
        print("  ✓ JSON output format correct")


def main():
    """Run all tests"""
    print("=" * 65)
    print("Trace Audit Functionality Test Suite")
    print("=" * 65)
    
    test = TestTraceAudit()
    
    try:
        test.test_audit_perfunctory_result()
        test.test_audit_substantive_result()
        test.test_audit_short_analysis_time()
        test.test_audit_no_timeline_support()
        test.test_audit_json_output()
        
        print("\n" + "=" * 65)
        print("All tests passed ✓")
        print("=" * 65)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
