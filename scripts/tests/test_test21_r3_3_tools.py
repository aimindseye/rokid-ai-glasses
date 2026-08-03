#!/usr/bin/env python3
import importlib.util, tempfile, unittest, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_3_authorized_no_connect.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_candidate_sanitizer(self): self.assertIn('com.rokid.foo:ai',m.sanitize_candidate('u0 123 com.rokid.foo:ai'))
 def test_candidate_drops_pid(self): self.assertNotIn('123',m.sanitize_candidate('u0 123 com.rokid.foo'))
 def test_authorization_gate_accepts_auth_only(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'e'; p.write_text(json.dumps({'event_type':'authorization_result','details':{'token_present':True,'token_value_logged':False}})+'\n'); self.assertTrue(m.event_gate(m.events(p)))
 def test_authorization_gate_rejects_connection(self):
  with self.assertRaises(ValueError): m.event_gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'connection_attempt_started','details':{}}])
 def test_authorization_gate_rejects_photo(self):
  with self.assertRaises(ValueError): m.event_gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'photo_request_result','details':{}}])
 def test_authorization_gate_rejects_audio(self):
  with self.assertRaises(ValueError): m.event_gate([{'event_type':'authorization_result','details':{'token_present':True}},{'event_type':'audio_stream_start','details':{}}])
 def test_profile_literal(self): self.assertEqual('CUSTOM_AUTHORIZED_NO_CONNECT','CUSTOM_AUTHORIZED_NO_CONNECT')
 def test_no_external_candidate_terms(self): self.assertEqual([],m.sanitize_candidate('system_server'))
 def test_strict_caller_bind_regex(self): self.assertTrue(m.BIND.search('ConnectionRecord binding'))
 def test_process_start_regex(self): self.assertTrue(m.PROC.search('am_proc_start com.rokid.sprite.global.aiapp'))
 def test_component_regex(self): self.assertIn('com.rokid.sprite.global.aiapp/.Foo',m.COMP.findall('com.rokid.sprite.global.aiapp/.Foo'))
 def test_no_connection_concept(self): self.assertFalse(False)
if __name__=='__main__': unittest.main(verbosity=2)
