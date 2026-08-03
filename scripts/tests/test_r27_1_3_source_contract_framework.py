import hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.research.canonical import source_contract

class SourceContractFramework(unittest.TestCase):
    def test_profile_counts(self):
        r=source_contract.load_registry()
        self.assertEqual(len(r['profiles']),29)
        self.assertEqual(len(r['deferred_historical_contracts']),3)
        self.assertEqual({p['track'] for p in r['profiles']},{'test21'})

    def test_final_test21_profile_present(self):
        p=source_contract.find_profile('test21','r3.3.4.2.6.1.2')
        self.assertIsNotNone(p)
        self.assertIn('TEST21_R3_3_4_2_6_1_2_SOURCE_CONTRACT=PASS',p['expected_pass_markers'])

    def test_deferred_test20_contracts_are_explicit(self):
        r=source_contract.load_registry()
        keys={(p['track'],p['revision']) for p in r['deferred_historical_contracts']}
        self.assertEqual(keys,{('test20','final'),('test20','r3.2.1'),('test20','r3.3')})

    def test_identity_lock_rejects_modified_checker(self):
        repo=Path(__file__).resolve().parents[2]
        p=source_contract.find_profile('test21','r3.3.4.1')
        self.assertEqual(source_contract.sha256_file(repo/p['legacy_checker']),p.get('compatibility_shim_sha256',p.get('legacy_source_sha256')))

if __name__=='__main__': unittest.main()
