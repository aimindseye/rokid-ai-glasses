import json, unittest
from pathlib import Path
from scripts.research.canonical.evidence_packager import load_profiles

class R2717(unittest.TestCase):
    def test_three_historical_container_profiles_are_shims(self):
        p=load_profiles()
        for rev in ('r3.1','r3.2','r3.3'):
            self.assertEqual(p[rev]['retirement_state'],'COMPATIBILITY_SHIM')
            self.assertEqual(p[rev]['container_mode'],'historical_source_metadata')
            self.assertTrue(p[rev]['compatibility_shim_sha256'])
    def test_remaining_packager_dependencies_stay_blocked(self):
        p=load_profiles()
        self.assertLessEqual(sum(x.get('retirement_state')=='BLOCKED_INBOUND_DEPENDENCY' for x in p.values()),27)
        self.assertEqual(sum(x.get('retirement_state')=='BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY' for x in p.values()),0)
    def test_default_container_remains_deterministic(self):
        p=load_profiles()
        for rev,x in p.items():
            if rev not in ('r3.1','r3.2','r3.3'):
                self.assertEqual(x.get('container_mode'),'deterministic')
if __name__=='__main__': unittest.main()
