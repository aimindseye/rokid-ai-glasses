from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel); assert spec and spec.loader
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
MOD=load('r2727_network','scripts/research/canonical/network_privacy_analyzer.py')
class R2727Tests(unittest.TestCase):
    def test_profiles_and_source_locks(self):
        rows=json.loads((ROOT/'scripts/research/canonical/profiles/test19-network-analyzers.json').read_text())['profiles']
        self.assertEqual([r['revision'] for r in rows],['test19-r1','test19-r2'])
        import hashlib
        for row in rows:
            actual=hashlib.sha256((ROOT/row['legacy_path']).read_bytes()).hexdigest()
            expected=row.get('compatibility_shim_sha256') if row.get('retirement_state')=='COMPATIBILITY_SHIM' else row['legacy_sha256']
            self.assertEqual(actual,expected)
            self.assertEqual(row.get('original_source_sha256',row['legacy_sha256']),row['legacy_sha256'])
    def test_r1_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.csv'; p.write_text('remote_host,remote_ip\nrouter.local,192.168.1.2\n'); self.assertEqual(MOD.analyze_r1(p)['gate'],'PASS')
            p.write_text('remote_host,remote_ip\napi.example.test,8.8.8.8\n'); self.assertEqual(MOD.analyze_r1(p)['gate'],'FAIL')
    def test_r2_separates_stock_public(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.csv'; p.write_text('package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,router.local,192.168.1.2\ncom.rokid.sprite.global.aiapp,api.example.test,8.8.8.8\n')
            r=MOD.analyze_r2(p); self.assertEqual(r['gate'],'PASS'); self.assertEqual(r['counts']['custom_public'],0); self.assertEqual(r['counts']['hi_rokid_public'],1)
    def test_r2_fail_and_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.csv'; p.write_text('package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,api.example.test,8.8.8.8\n'); self.assertEqual(MOD.analyze_r2(p)['exit_code'],10)
            p.write_text('remote_host,remote_ip\nrouter.local,192.168.1.2\n'); self.assertEqual(MOD.analyze_r2(p)['exit_code'],30)
if __name__=='__main__': unittest.main()
