from __future__ import annotations
import unittest
from pathlib import Path
from scripts.research.canonical import retirement_status, tool_test_runner

ROOT = Path(__file__).resolve().parents[2]


class R27112ToolTestOracleFinalization(unittest.TestCase):
    def test_registry_finalizes_38_current_oracles(self):
        reg = tool_test_runner.load_registry()
        self.assertEqual(reg['schema'], 'rokid.r27.1.12.tool-test-suites.v2')
        self.assertEqual(len(reg['profiles']), 39)
        self.assertEqual(sum(p.get('oracle_state') == 'PRESERVE_REGRESSION_ORACLE' for p in reg['profiles']), 38)
        self.assertEqual(sum(p.get('oracle_state') == 'PRESERVE_HISTORICAL' for p in reg['profiles']), 1)

    def test_all_oracle_source_locks_hold(self):
        rc, detail = tool_test_runner.verify_oracle_locks(ROOT, emit_output=False)
        self.assertEqual(rc, 0, detail['summary'])
        self.assertEqual(detail['summary']['source_lock_failure_count'], 0)
        self.assertEqual(detail['summary']['preserve_regression_oracle_count'], 38)

    def test_retirement_queue_is_closed_without_rewriting_tests(self):
        s = retirement_status.summary(ROOT)
        self.assertEqual(s['retired_compatibility_shim_count'], 71)
        self.assertEqual(s['not_retirement_ready_count'], 0)
        self.assertEqual(s['preserve_regression_oracle_count'], 38)
        self.assertEqual(s['preserve_historical_count'], 4)
        self.assertEqual(s['retirement_candidate_count'], 0)
        self.assertEqual(s['blocked_source_lock_count'], 0)

    def test_deferred_missing_fixture_remains_explicit(self):
        deferred = [p for p in tool_test_runner.profiles() if p.get('oracle_state') == 'PRESERVE_HISTORICAL']
        self.assertEqual(len(deferred), 1)
        p = deferred[0]
        self.assertEqual(p['track'], 'test21')
        self.assertEqual(p['revision'], 'r3.3.4.2.6.1.1')
        self.assertEqual(p['status'], 'DEFERRED_MISSING_FIXTURE')
        self.assertTrue(p['required_fixture_paths'])
        self.assertTrue(any(not (ROOT / rel).exists() for rel in p['required_fixture_paths']))

    def test_catalog_exposes_oracle_verification(self):
        text = (ROOT / 'scripts/research/canonical/r27_catalog.py').read_text(encoding='utf-8')
        self.assertIn('verify-oracles', text)
        self.assertIn('verify_oracle_locks', text)


if __name__ == '__main__':
    unittest.main()
