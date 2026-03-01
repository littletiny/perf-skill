#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Risk Display Configuration

Test cases:
1. Default config loading
2. Config file merging
3. Mode application (ci/compact)
4. Issue formatting
5. Timeline formatting
6. JSON config file parsing

Usage:
    cd tests
    python3 test_risk_display_config.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from perf_toolkit.core.risk_config import RiskDisplayConfig, get_risk_config, clear_risk_config_cache, DEFAULT_CONFIG


class TestRiskDisplayConfig(unittest.TestCase):
    """Test RiskDisplayConfig functionality"""

    def setUp(self):
        """Setup before each test"""
        clear_risk_config_cache()
        self.temp_dir = tempfile.mkdtemp(prefix="risk_config_test_")

    def tearDown(self):
        """Cleanup after each test"""
        clear_risk_config_cache()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_config_file(self, filename, content):
        """Helper to create config file"""
        path = Path(self.temp_dir) / filename
        with open(path, 'w') as f:
            json.dump(content, f)
        return path

    def test_01_default_config(self):
        """Test: Default config has correct structure"""
        print("\n[Test 01] Default config structure")

        config = RiskDisplayConfig()

        # Check colors
        self.assertIn('critical', config.colors)
        self.assertIn('warning', config.colors)
        self.assertIn('info', config.colors)
        self.assertIn('reset', config.colors)

        # Check templates
        self.assertIn('issue_open', config.templates)
        self.assertIn('issue_resolved', config.templates)
        self.assertIn('hint', config.templates)

        # Check show flags
        self.assertIn('hint', config.show)
        self.assertIn('result', config.show)

        print("  ✓ Default config structure valid")

    def test_02_default_templates_no_emoji(self):
        """Test: Default templates have no emoji"""
        print("\n[Test 02] Default templates have no emoji")

        config = RiskDisplayConfig()

        # Check no emoji in templates
        for key, template in config.templates.items():
            self.assertNotIn('🔴', template, f"Template {key} should not contain 🔴")
            self.assertNotIn('🟡', template, f"Template {key} should not contain 🟡")
            self.assertNotIn('✅', template, f"Template {key} should not contain ✅")
            self.assertNotIn('✓', template, f"Template {key} should not contain ✓")

        print("  ✓ No emoji in default templates")

    def test_03_default_templates_format(self):
        """Test: Default templates use correct format"""
        print("\n[Test 03] Default templates format")

        config = RiskDisplayConfig()

        # Check issue format: [STATUS] [ID] [LEVEL] desc
        self.assertEqual(
            config.templates['issue_open'],
            "[OPEN] [{id}] [{level}] {desc}"
        )
        self.assertEqual(
            config.templates['issue_resolved'],
            "[RESOLVED] [{id}] [{level}] {desc}"
        )

        # Check hint format: arrow prefix
        self.assertEqual(config.templates['hint'], "→ {hint}")

        print("  ✓ Default templates format correct")

    def test_04_config_file_loading(self):
        """Test: Config file loading and merging"""
        print("\n[Test 04] Config file loading")

        # Create a config file
        config_content = {
            "risk": {
                "colors": {
                    "critical": "",
                    "warning": "",
                    "reset": ""
                },
                "templates": {
                    "issue_open": "[OPEN] {id} [{level}] {desc}"
                },
                "show": {
                    "hint": False
                }
            }
        }

        config_path = self._create_config_file("test_risk.json", config_content)

        # Load config
        config = RiskDisplayConfig.load(explicit_path=str(config_path))

        # Verify merged values
        self.assertEqual(config.colors['critical'], "")  # From file
        self.assertEqual(config.templates['issue_open'], "[OPEN] {id} [{level}] {desc}")  # From file
        self.assertEqual(config.show['hint'], False)  # From file
        self.assertIn('issue_resolved', config.templates)  # From default

        print("  ✓ Config file loading and merging works")

    def test_05_mode_application(self):
        """Test: Mode application (ci/compact)"""
        print("\n[Test 05] Mode application")

        # Create config with modes in current directory (.spear/risk.json)
        # so apply_mode can find it
        spear_dir = Path(self.temp_dir) / ".spear"
        spear_dir.mkdir(exist_ok=True)
        config_path = spear_dir / "risk.json"

        config_content = {
            "risk": {
                "colors": {
                    "critical": "\033[91m",
                    "warning": "\033[93m"
                }
            },
            "modes": {
                "ci": {
                    "colors": {
                        "critical": "",
                        "warning": ""
                    }
                },
                "compact": {
                    "show": {
                        "hint": False
                    }
                }
            }
        }

        with open(config_path, 'w') as f:
            json.dump(config_content, f)

        # Save original cwd and change to temp dir
        import os
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            # Load from .spear/risk.json
            config = RiskDisplayConfig.load()
            config.apply_mode('ci')

            self.assertEqual(config.colors['critical'], "")
            self.assertEqual(config.colors['warning'], "")

            # Test compact mode - reload fresh config
            config2 = RiskDisplayConfig.load()
            config2.apply_mode('compact')
            self.assertEqual(config2.show['hint'], False)
        finally:
            os.chdir(original_cwd)

        print("  ✓ Mode application works")

    def test_06_global_config_cache(self):
        """Test: Global config cache"""
        print("\n[Test 06] Global config cache")

        # First call should create cache
        config1 = get_risk_config()
        config2 = get_risk_config()

        # Should be same object (cached)
        self.assertIs(config1, config2)

        # Clear cache
        clear_risk_config_cache()
        config3 = get_risk_config()

        # Should be different object
        self.assertIsNot(config1, config3)

        print("  ✓ Global config cache works")

    def test_07_format_issue_simulation(self):
        """Test: Simulated issue formatting"""
        print("\n[Test 07] Issue formatting simulation")

        config = RiskDisplayConfig()

        # Simulate formatting an open issue
        issue = {
            'id': 'ISS-001',
            'level': 'warning',
            'desc': 'Test issue',
            'status': 'open',
            'hint': 'Do something'
        }

        # Format using templates
        tpl = config.templates['issue_open']
        line = tpl.format(id=issue['id'], level=issue['level'].upper(), desc=issue['desc'])

        self.assertIn('[OPEN]', line)
        self.assertIn('[ISS-001]', line)
        self.assertIn('[WARNING]', line)
        self.assertIn('Test issue', line)

        # Check hint format
        hint_line = config.templates['hint'].format(hint=issue['hint'])
        self.assertEqual(hint_line, '→ Do something')

        print("  ✓ Issue formatting simulation works")

    def test_08_json_parsing_error_handling(self):
        """Test: JSON parsing error handling"""
        print("\n[Test 08] JSON parsing error handling")

        # Create invalid JSON file
        config_path = Path(self.temp_dir) / "invalid.json"
        with open(config_path, 'w') as f:
            f.write("{invalid json}")

        # Should not crash, use defaults
        config = RiskDisplayConfig.load(explicit_path=str(config_path))
        self.assertIn('issue_open', config.templates)  # Should have defaults

        print("  ✓ Error handling works")

    def test_09_no_risk_section(self):
        """Test: Config file without risk section"""
        print("\n[Test 09] Config without risk section")

        config_content = {"other_section": {}}
        config_path = self._create_config_file("no_risk.json", config_content)

        # Should use defaults
        config = RiskDisplayConfig.load(explicit_path=str(config_path))
        self.assertIn('issue_open', config.templates)

        print("  ✓ Handles missing risk section")

    def test_10_environment_variable(self):
        """Test: SPEAR_RISK_CONFIG environment variable"""
        print("\n[Test 10] Environment variable")

        # Create config file
        config_content = {
            "risk": {
                "colors": {
                    "critical": ""
                }
            }
        }
        config_path = self._create_config_file("env_config.json", config_content)

        # Set environment variable
        old_env = os.environ.get('SPEAR_RISK_CONFIG')
        os.environ['SPEAR_RISK_CONFIG'] = str(config_path)

        try:
            clear_risk_config_cache()
            config = get_risk_config()
            self.assertEqual(config.colors['critical'], "")
        finally:
            # Restore environment
            if old_env is not None:
                os.environ['SPEAR_RISK_CONFIG'] = old_env
            else:
                del os.environ['SPEAR_RISK_CONFIG']

        print("  ✓ Environment variable works")


class TestTraceFormatting(unittest.TestCase):
    """Test Trace formatting with RiskDisplayConfig"""

    @classmethod
    def setUpClass(cls):
        """Setup"""
        cls.repo_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(cls.repo_root / "scripts"))

    def setUp(self):
        """Setup before each test"""
        clear_risk_config_cache()

    def tearDown(self):
        """Cleanup"""
        clear_risk_config_cache()

    def test_11_trace_format_issue(self):
        """Test: Trace.format_issue with config"""
        print("\n[Test 11] Trace.format_issue")

        from perf_toolkit.core.trace import Trace

        config = RiskDisplayConfig()
        doc = Trace(config=config)

        issue = {
            'id': 'ISS-001',
            'level': 'warning',
            'desc': 'Test issue description',
            'status': 'open',
            'hint': 'Test hint'
        }

        output = doc.format_issue(issue)

        # Check format
        self.assertIn('[OPEN]', output)
        self.assertIn('[ISS-001]', output)
        self.assertIn('[WARNING]', output)
        self.assertIn('Test issue description', output)
        self.assertIn('→ Test hint', output)

        # Check no emoji
        self.assertNotIn('🔴', output)
        self.assertNotIn('🟡', output)

        print("  ✓ Trace.format_issue works")

    def test_12_trace_format_issue_resolved(self):
        """Test: Trace.format_issue for resolved issue"""
        print("\n[Test 12] Trace.format_issue resolved")

        from perf_toolkit.core.trace import Trace

        config = RiskDisplayConfig()
        doc = Trace(config=config)

        issue = {
            'id': 'ISS-002',
            'level': 'critical',
            'desc': 'Resolved issue',
            'status': 'resolved',
            'result': 'Fixed by restart'
        }

        output = doc.format_issue(issue)

        self.assertIn('[RESOLVED]', output)
        self.assertIn('[ISS-002]', output)
        self.assertIn('[CRITICAL]', output)
        self.assertIn('→ Fixed by restart', output)

        print("  ✓ Resolved issue formatting works")

    def test_13_trace_format_timeline(self):
        """Test: Trace.format_timeline with config"""
        print("\n[Test 13] Trace.format_timeline")

        from perf_toolkit.core.trace import Trace

        config = RiskDisplayConfig()
        doc = Trace(config=config)

        # Mock timeline data
        doc.data['timeline'] = [
            {
                'seq': 1,
                'timestamp': '2026-03-02T10:05:00.000Z',
                'command': 'get-comm-top --data test.data',
                'findings': [
                    {
                        'type': 'risk_created',
                        'level': 'warning',
                        'issue_id': 'ISS-001',
                        'desc': 'High kernel usage'
                    }
                ]
            }
        ]

        output = doc.format_timeline()

        self.assertIn('[1]', output)
        self.assertIn('10:05:00', output)
        self.assertIn('get-comm-top', output)
        self.assertIn('[WARNING]', output)
        self.assertIn('ISS-001', output)

        # Check no emoji
        self.assertNotIn('🔴', output)

        print("  ✓ Trace.format_timeline works")


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("Risk Display Configuration Test Suite")
    print("=" * 70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRiskDisplayConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestTraceFormatting))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
