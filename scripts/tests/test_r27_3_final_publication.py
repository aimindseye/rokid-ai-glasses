import json, unittest
from pathlib import Path
class R273PublicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.repo=Path(__file__).resolve().parents[2]
 def test_profile_closure(self):
  p=json.loads((self.repo/'scripts/research/canonical/profiles/r27-publication.json').read_text()); self.assertEqual(p['schema'],'rokid.r27.3.publication.v1'); r=p['required_closure']; self.assertEqual(r['total_canonicalized_implementation_count'],88); self.assertEqual(r['host_multi_member_consolidation_candidate_count'],0); self.assertEqual(r['next_device_test_ready'],'YES')
 def test_public_doc(self):
  t=(self.repo/'docs/research/r27.3-final-publication.md').read_text(); self.assertIn('NEXT_DEVICE_TEST_READY=YES',t); self.assertIn('Test 22',t)
 def test_verifier_has_privacy_gates(self):
  t=(self.repo/'scripts/research/canonical/verify_r27_3_publication.py').read_text(); [self.assertIn(x,t) for x in ('private_key','device_serial','forbidden_suffix','consolidation')]
if __name__=='__main__': unittest.main()
