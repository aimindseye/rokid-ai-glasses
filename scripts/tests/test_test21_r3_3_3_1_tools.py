#!/usr/bin/env python3
import unittest,tempfile,struct,json,importlib.util,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=load('p3331','parse_test21_r3_3_3_1_pcap.py')
class Parser(unittest.TestCase):
 def test_clean_path(self):self.assertEqual(P.clean_path('/v1/device/abcdef0123456789abcdef0123456789?token=x'),'/v1/device/:id')
 def test_dns(self):
  q=b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'+b'\x03api\x05rokid\x03com\x00\x00\x01\x00\x01';self.assertEqual(P.dns_q(q),'api.rokid.com')
 def test_trailer(self):
  d=b'x'*40+struct.pack('<I',P.MAGIC)+struct.pack('<i',10123)+b'com.example\0'+b'\0'*8;pos,uid,name=P.trailer(d);self.assertEqual(uid,10123);self.assertTrue(name.startswith('com.example'))
 def test_public_endpoint(self):self.assertTrue(P.public_endpoint('10.0.0.2','8.8.8.8'));self.assertFalse(P.public_endpoint('10.0.0.2','192.168.1.1'))
 def test_frame_mapping_priority(self):
  old=P.shutil.which;P.shutil.which=lambda x:'/fake/tshark'
  class R:returncode=0;stderr='';stdout='7\t1.000\t10.0.0.2\t\t8.8.8.8\t\t1234\t443\tGET\tapi.rokid.com\t/v1/x\t\t\t\t\t\n'
  oldrun=P.subprocess.run;P.subprocess.run=lambda *a,**k:R()
  try:
   with tempfile.TemporaryDirectory() as td:
    k=Path(td)/'k';k.write_text('x');rows,status=P.tshark_http('/tmp/x',k,{7:'org.aimindseye.rokid.cxrphotoqualification'},{})
   self.assertEqual(status,'AVAILABLE');self.assertEqual(rows[0]['package'],'org.aimindseye.rokid.cxrphotoqualification');self.assertEqual(rows[0]['attribution_method'],'FRAME_TRAILER')
  finally:P.shutil.which=old;P.subprocess.run=oldrun
class Contract(unittest.TestCase):
 def setUp(self):self.txt=(HERE/'run_test21_r3_3_3_1_network_attribution.sh').read_text()
 def test_no_hi_force_stop(self):self.assertNotRegex(self.txt,r'am\s+force-stop\s+"\$HI_ROKID"')
 def test_no_connection_action(self):self.assertNotIn('Start one photo connection',self.txt);self.assertNotIn('READY_FOR_R3_CONNECTION',self.txt)
 def test_capture_dual_app(self):
  for x in ('app_filter "$HI_ROKID,$CUSTOM_PACKAGE"','tls_decryption true','decryption_rules "$RULES"','dump_extensions true','full_payload true'):self.assertIn(x,self.txt)
 def test_stdin_secret_transport(self):self.assertIn('adb_shell_argv',self.txt);self.assertIn('shell sh',self.txt);self.assertNotIn('echo "$PCAPDROID_API_KEY_LOCAL"',self.txt)
 def test_no_abort_flags(self):
  for x in ('set -e','set -u','pipefail'):self.assertNotIn(x,self.txt)
if __name__=='__main__':unittest.main(verbosity=2)
