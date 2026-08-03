#!/usr/bin/env python3
import importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('a','analyze_test21_r3_3_1_deferred_binding.py')
class T(unittest.TestCase):
 def test_kv(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_text('A=B\n');self.assertEqual(A.kv(p)['A'],'B')
 def test_event_gate_accepts_auth_only(self): A.gate([{'event_type':'authorization_result','details':{'token_present':True,'token_value_logged':False}}])
 def test_event_gate_rejects_connect(self):
  with self.assertRaises(ValueError): A.gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'connection_attempt_started','details':{}}])
 def test_event_gate_rejects_photo(self):
  with self.assertRaises(ValueError): A.gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'take_photo','details':{}}])
 def test_scan_no_files(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(A.scan(Path(d),'x')['bind'])
 def test_scan_caller_binding(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x-hi-services-private.txt';p.write_text('bound client org.aimindseye.rokid.cxrphotoqualification to com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService\n');r=A.scan(Path(d),'x');self.assertTrue(r['bind']);self.assertTrue(r['caller'])
 def test_postforce_start(self):
  with tempfile.TemporaryDirectory() as d: Path(d,'activity-manager-private.txt').write_text('Start proc com.rokid.sprite.global.aiapp\n');self.assertTrue(A.postforce(Path(d))['start'])
 def test_components(self):
  with tempfile.TemporaryDirectory() as d: Path(d,'x-hi-services-private.txt').write_text('com.rokid.sprite.global.aiapp/com.rokid.TestService bound\n');self.assertIn('com.rokid.sprite.global.aiapp/com.rokid.TestService',A.scan(Path(d),'x')['components'])
class Contract(unittest.TestCase):
 def test_runner_has_no_connection_instruction(self):
  t=(HERE/'run_test21_r3_3_1_deferred_binding.sh').read_text();self.assertNotIn('Start one photo connection',t);self.assertIn('CXR_L_CONNECTION_ATTEMPT=NONE',t)
 def test_single_hi_force_stop(self):
  t=(HERE/'run_test21_r3_3_1_deferred_binding.sh').read_text();self.assertEqual(t.count('shell am force-stop "$HI_ROKID"'),1)
 def test_profile_marker(self): self.assertIn('AUTHORIZED_FOREGROUND_DELAY_30S',(HERE/'run_test21_r3_3_1_deferred_binding.sh').read_text())
 def test_settle_checkpoints(self):
  t=(HERE/'run_test21_r3_3_1_deferred_binding.sh').read_text();self.assertTrue(all(x in t for x in ('settle-00','settle-15','settle-30')))
 def test_operator_gate_token_generated_once(self):
  t=(HERE/'run_test21_r3_3_1_deferred_binding.sh').read_text()
  self.assertEqual(t.count("secrets.token_hex(32)"),1)
  self.assertNotIn("import secrets;print(secrets.token_hex(32))\nimport secrets;print(secrets.token_hex(32))",t)
if __name__=='__main__':unittest.main(verbosity=2)
