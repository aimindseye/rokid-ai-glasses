#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, sys, tempfile, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('r3342611',HERE/'analyze_test21_r3_3_4_2_6_1_1_proxy_closure.py')
M=importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; sys.modules[SPEC.name]=M; SPEC.loader.exec_module(M)

class ProxyClosureTests(unittest.TestCase):
 def test_expected_surface_is_33(self):
  self.assertEqual(M.EXPECTED_METHOD_COUNT,33); self.assertIn('takePhoto(III)Z',M.EXPECTED_METHODS)
 def test_obfuscated_fixture_finds_structural_proxy_and_closes_two_sources(self):
  aar=(HERE.parent.parent/'fixtures/synthetic-obfuscated-client-l-1.0.1.aar').resolve()
  r=M.analyze_aar(aar,fixture_mode=True)
  self.assertFalse(r['proxy_discovery']['literal_proxy_class_present'])
  self.assertTrue(r['proxy_discovery']['structural_proxy_found'])
  self.assertEqual(r['proxy_discovery']['implemented_interface_method_count'],33)
  self.assertEqual(r['transactions']['proxy_transaction_method_count'],33)
  self.assertEqual(r['transactions']['ontransact_transaction_method_count'],33)
  self.assertEqual(r['transactions']['proxy_ontransact_agreement_count'],33)
  self.assertEqual(r['transactions']['proxy_ontransact_mismatch_count'],0)
  self.assertTrue(r['transactions']['transaction_contract_ready'])
 def test_obfuscated_fixture_recovers_exact_parcel_contracts(self):
  aar=(HERE.parent.parent/'fixtures/synthetic-obfuscated-client-l-1.0.1.aar').resolve(); r=M.analyze_aar(aar,fixture_mode=True)
  self.assertEqual(r['transactions']['parcel_request_contract_count'],33)
  self.assertEqual(r['transactions']['parcel_reply_contract_count'],33)
  self.assertEqual(r['transactions']['parcel_contract_recovered_method_count'],33)
  self.assertTrue(r['clean_room']['binder_abi_ready'])
  photo=next(x for x in r['method_contract'] if x['signature']=='takePhoto(III)Z')
  self.assertEqual(photo['proxy_codes'],photo['ontransact_codes']); self.assertEqual(len(photo['proxy_codes']),1)
  self.assertTrue(any(x.startswith('writeInterfaceToken') for x in photo['request_operations']))
  self.assertTrue(any(x.startswith('readException') for x in photo['reply_operations']))
 def test_wrapper_classification_does_not_require_cxr_namespace(self):
  bridges=[]
  for i in range(4):
   bridges.append({'caller_class':'com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient','caller_method':f'm{i}','caller_proto':'()V','caller_public':True,'binder_signature':f'b{i}()V'})
  facades=M.structural_facades(bridges)
  self.assertIn('com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient',facades)
  self.assertEqual(facades['com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient']['public_unique_binder_method_count'],4)
 def test_single_bridge_class_is_not_overclassified_as_facade(self):
  bridges=[{'caller_class':'x.Helper','caller_method':'m','caller_proto':'()V','caller_public':True,'binder_signature':'b()V'}]
  self.assertEqual(M.structural_facades(bridges),{})
 def test_local_aar_resolver_has_no_network_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   home=Path(td); p=home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1/x'; p.mkdir(parents=True); aar=p/'client-l-1.0.1.aar'; aar.write_bytes(b'x')
   self.assertEqual(M.resolve_aar(None,home),[aar.resolve()])
 def test_runner_is_host_only(self):
  text=(HERE/'run_test21_r3_3_4_2_6_1_1_proxy_closure.sh').read_text()
  for token in ('adb shell','adb -s','su -c','/proc/','frida-server','curl ','wget ','am start','am force-stop'):
   self.assertNotIn(token,text)
 def test_analyzer_has_no_device_process_or_network_execution(self):
  text=(HERE/'analyze_test21_r3_3_4_2_6_1_1_proxy_closure.py').read_text()
  for token in ('subprocess.','os.system(','requests.','urllib.','socket.','import frida'):
   self.assertNotIn(token,text)
 def test_mismatch_blocks_two_source_contract(self):
  methods=[{'name':s.split('(',1)[0],'proto':'('+s.split('(',1)[1],'signature':s,'access':1} for s in sorted(M.EXPECTED_METHODS)]
  on={m['signature']:[i] for i,m in enumerate(methods,1)}
  pc={m['signature']:{'transaction_codes':[i],'request_contract_recovered':True,'reply_contract_recovered':True,'parcel_contract_recovered':True} for i,m in enumerate(methods,1)}
  pc[methods[0]['signature']]['transaction_codes']=[999]
  rows,c=M.merge(methods,on,pc,[],{})
  self.assertEqual(c['proxy_ontransact_mismatch_count'],1); self.assertFalse(c['transaction_contract_ready'])
 def test_sanitized_outputs_do_not_contain_local_input_paths(self):
  aar=(HERE.parent.parent/'fixtures/synthetic-obfuscated-client-l-1.0.1.aar').resolve(); r=M.analyze_aar(aar,fixture_mode=True)
  s=M.sanitized(r); blob=str(s)
  self.assertNotIn(str(aar),blob); self.assertNotIn('/Users/',blob)

if __name__=='__main__': unittest.main(verbosity=2)
