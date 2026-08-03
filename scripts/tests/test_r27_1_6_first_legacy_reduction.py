from __future__ import annotations
import unittest
from pathlib import Path
from scripts.research.canonical import retirement_dependencies, retirement_status
from scripts.research.canonical.connection_validator import load_profiles
from scripts.research.canonical.primitives import sha256_file
REPO=Path(__file__).resolve().parents[2]
class FirstLegacyReduction(unittest.TestCase):
    def test_ten_r25_shims_and_two_publication_locks(self):
        ps=load_profiles(); shims=[(r,p) for r,p in ps.items() if p.get('retirement_state')=='COMPATIBILITY_SHIM']; blocked=[(r,p) for r,p in ps.items() if p.get('retirement_state')=='BLOCKED_PUBLICATION_HASH_LOCK']
        self.assertGreaterEqual(len(shims),10); self.assertIn(len(blocked),(0,2)); self.assertEqual(len(shims)+len(blocked),12)
        for r,p in shims: self.assertEqual(sha256_file(REPO/p['legacy_validator']),p['compatibility_shim_sha256'])
        for r,p in blocked: self.assertEqual(sha256_file(REPO/p['legacy_validator']),p['legacy_source_sha256'])
    def test_dependency_states(self):
        rs=retirement_dependencies.rows(REPO)
        r25=[r for r in rs if r['family']=='r25-package-validators']
        self.assertTrue(all(int(r['inbound_reference_count'])==0 for r in r25 if r['retirement_state']=='COMPATIBILITY_SHIM'))
        self.assertIn(sum(r['retirement_state']=='BLOCKED_PUBLICATION_HASH_LOCK' for r in r25),(0,2))
        packs=[r for r in rs if r['family']=='test21-sanitized-packagers']
        self.assertLessEqual(sum(r['retirement_state']=='BLOCKED_INBOUND_DEPENDENCY' for r in packs),27)
        self.assertEqual(sum(r['retirement_state']=='BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY' for r in packs),0)
        self.assertGreaterEqual(sum(r['retirement_state']=='COMPATIBILITY_SHIM' for r in packs),3)
    def test_retirement_status(self):
        s=retirement_status.summary(REPO)
        self.assertGreaterEqual(s['retired_compatibility_shim_count'],13); self.assertLessEqual(s['blocked_inbound_dependency_count'],29); self.assertEqual(s['blocked_output_container_compatibility_count'],0); self.assertEqual(s['retirement_candidate_count'],0); self.assertEqual(s['blocked_source_lock_count'],0)
    def test_no_path_deletion_model(self):
        for _,p in load_profiles().items(): self.assertTrue((REPO/p['legacy_validator']).is_file())
if __name__=='__main__': unittest.main()
