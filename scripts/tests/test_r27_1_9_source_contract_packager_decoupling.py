import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class R2719(unittest.TestCase):
    def test_packager_states(self):
        p=json.loads((ROOT/'scripts/research/canonical/profiles/test21-sanitized-packagers.json').read_text())['profiles']
        self.assertGreaterEqual(sum(x.get('retirement_state')=='COMPATIBILITY_SHIM' for x in p.values()),14)
        self.assertLessEqual(sum(x.get('retirement_state')=='BLOCKED_INBOUND_DEPENDENCY' for x in p.values()),16)
    def test_source_contract_registry_locks_current_checkers(self):
        import hashlib
        data=json.loads((ROOT/'scripts/research/canonical/profiles/source-contracts.json').read_text())['profiles']
        self.assertEqual(len(data),29)
        for x in data:
            q=ROOT/x['legacy_checker']; self.assertTrue(q.is_file()); self.assertEqual(hashlib.sha256(q.read_bytes()).hexdigest(),x.get('compatibility_shim_sha256',x.get('legacy_source_sha256')))
    def test_new_shims_have_no_blocking_inbound_references(self):
        from scripts.research.canonical import retirement_dependencies
        targets={'r1','r2','r3','r3.3.1','r3.3.2','r3.3.3','r3.3.3.1','r3.3.3.2','r3.3.3.2.1','r3.3.4','r3.3.4.1'}
        rows=[r for r in retirement_dependencies.rows(ROOT) if r['family']=='test21-sanitized-packagers' and r['revision'] in targets]
        self.assertEqual(len(rows),11)
        self.assertTrue(all(int(r['blocking_inbound_reference_count'])==0 for r in rows))
    def test_retirement_status_schema(self):
        t=(ROOT/'scripts/research/canonical/retirement_status.py').read_text()
        self.assertTrue(any(x in t for x in ('rokid.r27.1.9.retirement-status.v5','rokid.r27.1.10.retirement-status.v6','rokid.r27.1.11.retirement-status.v7','rokid.r27.1.12.retirement-status.v8')))
if __name__=='__main__':unittest.main()
