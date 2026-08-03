from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path
from scripts.research.canonical import source_contract, retirement_status

ROOT=Path(__file__).resolve().parents[2]

class R27111SourceContractSnapshotEngine(unittest.TestCase):
    def test_all_29_test21_profiles_are_independent_snapshot_shims(self):
        reg=source_contract.load_registry(); profiles=reg['profiles']
        self.assertEqual(len(profiles),29)
        self.assertEqual(sum(p.get('retirement_state')=='COMPATIBILITY_SHIM' for p in profiles),29)
        for p in profiles:
            self.assertEqual(p['contract_mode'],'ACCEPTED_SOURCE_SNAPSHOT_V1')
            self.assertEqual(p['lineage_state'],'INDEPENDENT_ACCEPTED_SNAPSHOT_ENGINE')
            self.assertTrue(p['legacy_success_stdout'])
            self.assertEqual(source_contract.sha256_file(ROOT/p['legacy_checker']),p['compatibility_shim_sha256'])
            self.assertEqual(len(p['oracle_source_sha256']),64)

    def test_engine_does_not_execute_historical_checker(self):
        text=(ROOT/'scripts/research/canonical/source_contract.py').read_text(encoding='utf-8')
        self.assertNotIn('subprocess',text)
        self.assertNotIn('run_text(',text)
        self.assertIn('required_file_sha256',text)
        self.assertIn('contract_dependencies',text)

    def test_snapshot_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td); f=repo/'x.txt'; f.write_text('changed',encoding='utf-8')
            expected=hashlib.sha256(b'accepted').hexdigest()
            profile={'track':'x','revision':'r','legacy_checker':'shim.py','required_file_sha256':{'x.txt':expected},'required_directories':[],'contract_dependencies':[]}
            (repo/'shim.py').write_text('x',encoding='utf-8')
            errors=source_contract._validate_profile(repo,profile)
            self.assertTrue(any('accepted source snapshot identity mismatch' in e for e in errors))

    def test_retirement_status_reflects_checker_migration(self):
        s=retirement_status.summary(ROOT)
        self.assertEqual(s['retired_compatibility_shim_count'],71)
        self.assertEqual(s['not_retirement_ready_count'],0)
        self.assertEqual(s['preserve_regression_oracle_count'],38)
        self.assertEqual(s['preserve_historical_count'],4)
        self.assertEqual(s['blocked_source_lock_count'],0)

if __name__=='__main__': unittest.main()
