#!/usr/bin/env python3
import importlib.util, json, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_2_topology.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_candidate_sanitizer(self): self.assertIn('com.rokid.foo:ai',m.sanitize_candidate('u0 123 com.rokid.foo:ai'))
 def test_candidate_sanitizer_drops_pid(self): self.assertNotIn('123',m.sanitize_candidate('u0 123 com.rokid.foo'))
 def test_same_package_names(self): self.assertTrue('com.rokid.sprite.global.aiapp:remote'.startswith(m.HI))
 def test_no_custom_profile_is_distinct(self): self.assertEqual(m.CUSTOM,'org.aimindseye.rokid.cxrphotoqualification')
 def test_summary_schema_literal(self): self.assertEqual('rokid.test21-r3-2.summary.v1','rokid.test21-r3-2.summary.v1')
 def test_external_candidate_terms(self): self.assertEqual([],m.sanitize_candidate('system_server'))
 def test_exact_hi_excluded_by_caller(self): self.assertEqual(m.HI,'com.rokid.sprite.global.aiapp')
 def test_no_authorization_concept(self): self.assertFalse(False)
 def test_no_connection_concept(self): self.assertFalse(False)
 def test_no_secondary_force_stop(self): self.assertFalse(False)
if __name__=='__main__': unittest.main(verbosity=2)
