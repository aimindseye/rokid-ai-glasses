import json,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class R2718(unittest.TestCase):
 def test_profiles_are_shims(self):
  d=json.loads((ROOT/'scripts/research/canonical/profiles/r25-package-validators.json').read_text())['profiles']
  for r in ('r25.3.1','r25.3.1.1'):
   self.assertEqual(d[r]['retirement_state'],'COMPATIBILITY_SHIM')
   self.assertEqual(len(d[r]['compatibility_shim_sha256']),64)
   self.assertEqual(d[r]['historical_implementation_sha256'],d[r]['legacy_source_sha256'])
 def test_publication_verifier_uses_profile_lineage(self):
  t=(ROOT/'scripts/research/verify_r25_3_1_4_publication.py').read_text()
  self.assertIn('CANONICAL_VALIDATOR_PROFILE',t)
  self.assertIn('HISTORICAL_VALIDATOR_LINEAGE',t)
  self.assertIn('git", "-C", str(repo), "ls-files"',t)
 def test_retirement_schema(self):
  t=(ROOT/'scripts/research/canonical/retirement_status.py').read_text()
  self.assertRegex(t,r'rokid\.r27\.1\.(?:8|9|10|11|12)\.retirement-status\.v[45678]')

if __name__=='__main__':unittest.main()
