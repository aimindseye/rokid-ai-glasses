from __future__ import annotations
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel); assert spec and spec.loader
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
STATUS=load('r2728_status','scripts/research/canonical/consolidation_status.py')
class R2728FinalClosureTests(unittest.TestCase):
    def test_analyzers_are_compatibility_shims(self):
        rows=json.loads((ROOT/'scripts/research/canonical/profiles/test19-network-analyzers.json').read_text())['profiles']
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(row['retirement_state'],'COMPATIBILITY_SHIM')
            self.assertEqual(hashlib.sha256((ROOT/row['legacy_path']).read_bytes()).hexdigest(),row['compatibility_shim_sha256'])
            self.assertEqual(row['original_source_sha256'],row['legacy_sha256'])
    def test_final_manifest_closes_only_true_candidates(self):
        m=json.loads((ROOT/'scripts/research/canonical/profiles/r27-final-consolidation.json').read_text())
        self.assertEqual(m['canonicalized_implementation_count'],88)
        self.assertEqual(m['preserve_distinct_implementation_family_count'],4)
        self.assertEqual(m['host_multi_member_consolidation_candidate_count'],0)
        self.assertTrue(m['next_device_test_ready'])
        self.assertEqual(len(m['remaining_distinct_families']),4)
    def test_final_status_locks_every_disposition(self):
        summary,details=STATUS.evaluate(ROOT)
        self.assertEqual(summary['status'],'PASS')
        self.assertEqual(summary['source_lock_failure_count'],0)
        self.assertTrue(summary['next_device_test_ready'])
        self.assertEqual(len(details),10)  # 2 new shims + 8 preserved-distinct members
    def test_shim_import_api_and_semantics(self):
        r1=load('r2728_r1','scripts/tests/analyze_test19_network.py'); r2=load('r2728_r2','scripts/tests/analyze_test19_r2_network.py')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.csv'; p.write_text('remote_host,remote_ip\nrouter.local,192.168.1.2\n',encoding='utf-8'); self.assertEqual(r1.analyze(p)['gate'],'PASS')
            p.write_text('package,remote_host,remote_ip\ncom.rokid.sprite.global.aiapp,api.example.test,8.8.8.8\n',encoding='utf-8'); self.assertEqual(r2.analyze(p)['gate'],'PASS')
if __name__=='__main__': unittest.main()
