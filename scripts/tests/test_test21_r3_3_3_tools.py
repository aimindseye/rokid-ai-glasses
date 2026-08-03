#!/usr/bin/env python3
import unittest,tempfile,struct,json,importlib.util,subprocess,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=load('p','parse_test21_r3_3_3_pcap.py')
class T(unittest.TestCase):
 def test_clean_path_redacts_ids(self):self.assertEqual(P.clean_path('/v1/device/abcdef0123456789abcdef0123456789?token=x'),'/v1/device/:id')
 def test_dns(self):
  q=b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'+b'\x03api\x05rokid\x03com\x00\x00\x01\x00\x01';self.assertEqual(P.dns_q(q),'api.rokid.com')
 def test_http_marker(self):
  self.assertEqual(P.clean_path('/api/session/ABCDEF0123456789ABCDEF0123456789?q=1'),'/api/session/:id')
 def test_trailer(self):
  d=b'x'*40+struct.pack('<I',P.MAGIC)+struct.pack('<i',10123)+b'com.example\0'+b'\0'*8;pos,uid,name=P.trailer(d);self.assertEqual(uid,10123);self.assertTrue(name.startswith('com.example'))
 def test_tshark_unavailable_without_keylog(self):
  rows,status=P.tshark_http('/nope',None,{});self.assertEqual(status,'UNAVAILABLE');self.assertEqual(rows,[])
class Contract(unittest.TestCase):
 def setUp(self):self.txt=(HERE/'run_test21_r3_3_3_network_differential.sh').read_text()
 def test_original_r3_markers(self):
  for x in ('READY_FOR_R3_CONNECTION','Start one photo connection','button2_now_prompt','hi_force_stop_issued'):self.assertIn(x,self.txt)
 def test_pcap_settings(self):
  for x in ('tls_decryption true','block_quic to_decrypt','dump_extensions true','full_payload true','decryption_rules'):self.assertIn(x,self.txt)
 def test_no_shell_abort_flags(self):
  for x in ('set -e','set -u','pipefail'):self.assertNotIn(x,self.txt)
 def test_api_key_not_echoed(self):self.assertNotIn('echo "$PCAPDROID_API_KEY_LOCAL"',self.txt)

 def test_remote_quote_selftest_preserves_json_as_one_argument(self):
  env=dict(os.environ);env['TEST21_R3_3_3_QUOTE_SELFTEST']='1'
  p=subprocess.run(['bash',str(HERE/'run_test21_r3_3_3_network_differential.sh')],env=env,text=True,capture_output=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('TEST21_R3_3_3_REMOTE_QUOTE_SELFTEST=PASS',p.stdout)
  self.assertIn('REMOTE_ARGUMENT_COUNT=1',p.stdout)
 def test_pcap_control_uses_stdin_remote_shell(self):
  self.assertIn("printf '%s\\n' \"$remote_cmd\" | \"$ADB\" -s \"$PHONE\" shell sh",self.txt)
  self.assertIn('pcap_ctrl -e action start',self.txt)
  self.assertNotIn('shell am start -W -e action start -e api_key',self.txt)
 def test_start_failure_is_redacted_and_visible(self):
  self.assertIn('PCAPdroid API start failed rc=',self.txt)
  self.assertIn('PCAPdroid CaptureCtrl did not resolve',self.txt)
if __name__=='__main__':unittest.main(verbosity=2)
