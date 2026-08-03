#!/usr/bin/env python3
import importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('a','analyze_test21_r3_3_2_lifecycle_transition.py')
class T(unittest.TestCase):
 def test_kv(self):
  with tempfile.TemporaryDirectory() as d:p=Path(d)/'x';p.write_text('A=B\n');self.assertEqual(A.kv(p)['A'],'B')
 def test_event_gate_accepts_auth_only(self):A.gate([{'event_type':'authorization_result','details':{'token_present':True,'token_value_logged':False}}])
 def test_event_gate_rejects_connect(self):
  with self.assertRaises(ValueError):A.gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'connection_attempt_started','details':{}}])
 def test_event_gate_rejects_photo(self):
  with self.assertRaises(ValueError):A.gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'take_photo','details':{}}])
 def test_scan_caller_binding(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'background-00-hi-services-private.txt').write_text('bound client org.aimindseye.rokid.cxrphotoqualification to com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService\n');r=A.scan(Path(d),'background-00');self.assertTrue(r['caller'])
 def test_scan_no_files(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(A.scan(Path(d),'background-00')['bind'])
 def test_lifecycle_evidence(self):
  with tempfile.TemporaryDirectory() as d:Path(d,'lifecycle-activity-task-private.txt').write_text('org.aimindseye.rokid.cxrphotoqualification moved to background\n');self.assertTrue(A.lifecycle(Path(d))['custom_lifecycle_evidence'])
 def test_postforce_start(self):
  with tempfile.TemporaryDirectory() as d:Path(d,'postforce-activity-manager-private.txt').write_text('Start proc com.rokid.sprite.global.aiapp\n');self.assertTrue(A.postforce(Path(d))['start'])
class Contract(unittest.TestCase):
 def txt(self):return (HERE/'run_test21_r3_3_2_lifecycle_transition.sh').read_text()
 def test_profile_marker(self):self.assertIn('AUTHORIZED_FOREGROUND_TO_BACKGROUND_HOME_15S',self.txt())
 def test_single_home_transition(self):self.assertEqual(self.txt().count('input keyevent KEYCODE_HOME'),1)
 def test_single_hi_force_stop(self):self.assertEqual(self.txt().count('shell am force-stop "$HI_ROKID"'),1)
 def test_no_connection_instruction(self):self.assertNotIn('Start one photo connection',self.txt());self.assertIn('CXR_L_CONNECTION_ATTEMPT=NONE',self.txt())
 def test_token_generated_once(self):self.assertEqual(self.txt().count('secrets.token_hex(32)'),1)
 def test_background_machine_gates(self):
  t=self.txt();self.assertIn('CUSTOM_FOREGROUND_PROVEN=YES',t);self.assertIn('CUSTOM_FOREGROUND_PROVEN=NO',t);self.assertIn('CUSTOM_PROCESS_VISIBLE=YES',t)
if __name__=='__main__':unittest.main(verbosity=2)
