#!/usr/bin/env python3
import importlib.util,tempfile,unittest,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_3_4_1_binding_contract.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
sp2=importlib.util.spec_from_file_location('s',HERE/'inspect_test21_r3_3_4_1_apk_strings.py');S=importlib.util.module_from_spec(sp2);sp2.loader.exec_module(S)
class T(unittest.TestCase):
 def test_uid(self):
  self.assertEqual(M.package_uid('  userId=10456\n'),10456);self.assertEqual(M.uid_token(10456),'u0a456')
 def test_intent_explicit(self):
  b='IntentBindRecord x intent={act=com.rokid.cxr.BIND cmp=com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService flg=0x1}'
  x=M.parse_intent(b);self.assertTrue(x['explicit_component']);self.assertEqual(x['action'],'com.rokid.cxr.BIND');self.assertEqual(x['flags'],'0x1')
 def test_binding_caller(self):
  b='IntentBindRecord{}\nClient AppBindRecord ProcessRecord{ 333:org.aimindseye.rokid.cxrphotoqualification/u0a456}\nConnectionRecord{ x org.aimindseye.rokid.cxrphotoqualification:@abc }'
  x=M.caller_evidence(b,10456);self.assertTrue(x['exact_custom_binding_client']);self.assertTrue(M.binding_records(b))
 def test_runtime_descriptor(self):
  self.assertEqual(M.descriptor_from_runtime('interfaceDescriptor=com.rokid.sprite.aiapp.external.ICXRLinkService'),['com.rokid.sprite.aiapp.external.ICXRLinkService'])
 def test_disposition_exact(self):
  i={'explicit_component':True};self.assertEqual(M.disposition(True,True,True,i,True),'EXACT_CUSTOM_TO_CXRLINKSERVICE_BOUND_DEPENDENCY')
 def test_disposition_caller_unresolved(self):
  i={'explicit_component':True};self.assertEqual(M.disposition(True,True,False,i,True),'EXACT_CXRLINKSERVICE_BOUND_MECHANISM_CALLER_UNRESOLVED')
 def test_ascii_census(self):
  vals=[('classes.dex',['com.rokid.sprite.aiapp.external.ICXRLinkService','com.rokid.cxr.BIND','com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'])]
  b,a,m=S.classify(vals);self.assertIn('com.rokid.sprite.aiapp.external.ICXRLinkService',b);self.assertIn('com.rokid.cxr.BIND',a);self.assertTrue(m)
 def test_runner_no_abort_flags(self):
  t=(HERE/'run_test21_r3_3_4_1_binding_contract.sh').read_text();self.assertNotIn('set -e',t);self.assertNotIn('set -u',t);self.assertNotIn('set -o pipefail',t)
 def test_collector_ready(self):
  t=(HERE/'collect_test21_r3_3_4_1_binding_contract.py').read_text();self.assertIn("'ready-file'",t);self.assertIn('HI_PROCESS_VISIBLE=',t)
if __name__=='__main__':unittest.main(verbosity=2)
