import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class R27110(unittest.TestCase):
    def test_all_test21_packagers_are_shims(self):
        p=json.loads((ROOT/'scripts/research/canonical/profiles/test21-sanitized-packagers.json').read_text())['profiles']
        self.assertEqual(len(p),30)
        self.assertEqual(sum(x.get('retirement_state')=='COMPATIBILITY_SHIM' for x in p.values()),30)
        self.assertEqual(sum(x.get('retirement_state')=='BLOCKED_INBOUND_DEPENDENCY' for x in p.values()),0)
    def test_retirement_status_has_zero_implementation_blockers(self):
        from scripts.research.canonical.retirement_status import summary
        s=summary(ROOT)
        self.assertGreaterEqual(s['retired_compatibility_shim_count'],42)
        self.assertEqual(s['blocked_inbound_dependency_count'],0)
        self.assertEqual(s['blocked_output_container_compatibility_count'],0)
        self.assertEqual(s['blocked_source_lock_count'],0)
    def test_dependency_scan_marks_shim_callers_compatible(self):
        from scripts.research.canonical.retirement_dependencies import rows
        p=[r for r in rows(ROOT) if r['family']=='test21-sanitized-packagers']
        self.assertEqual(len(p),30)
        self.assertTrue(all(int(r['blocking_inbound_reference_count'])==0 for r in p))
    def test_final_packager_compatibility_api(self):
        import importlib.util
        path=ROOT/'scripts/research/cxr/package_test21_r3_3_4_2_6_1_3_sanitized.py'
        spec=importlib.util.spec_from_file_location('r613packcompat',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertIsNone(m.privacy_violation('r3.3.4.2.6.1.3'))
        self.assertEqual(m.privacy_violation('peer=10.0.0.1'),'ipv4')
if __name__=='__main__': unittest.main()
