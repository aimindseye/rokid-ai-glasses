#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, tempfile, unittest, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('r334261',HERE/'analyze_test21_r3_3_4_2_6_1_aar_contract.py')
M=importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; sys.modules[SPEC.name]=M; SPEC.loader.exec_module(M)

class ContractLogic(unittest.TestCase):
 def methods(self):
  return [{'name':s.split('(',1)[0],'proto':'('+s.split('(',1)[1],'signature':s,'access':1} for s in sorted(M.EXPECTED_METHODS)]
 def test_expected_surface_is_33(self):
  self.assertEqual(len(M.EXPECTED_METHODS),33)
  self.assertIn('takePhoto(III)Z',M.EXPECTED_METHODS)
 def test_complete_two_source_contract_ready(self):
  methods=self.methods(); constants={m['name']:i for i,m in enumerate(methods,1)}
  proxy={m['signature']:[i] for i,m in enumerate(methods,1)}
  on={m['signature']:[i] for i,m in enumerate(methods,1)}
  parcel={m['signature']:['writeInterfaceToken(Ljava/lang/String;)V','readException()V'] for m in methods}
  found={m['signature']:True for m in methods}
  rows,c=M.merge_contract(methods,constants,proxy,on,parcel,found,[],{})
  self.assertTrue(c['transaction_map_complete']); self.assertTrue(c['transaction_contract_ready']); self.assertEqual(c['transaction_source_agreement_count'],33); self.assertEqual(c['parcel_contract_recovered_method_count'],33)
 def test_single_source_does_not_close_exact_contract(self):
  methods=self.methods(); constants={m['name']:i for i,m in enumerate(methods,1)}
  rows,c=M.merge_contract(methods,constants,{}, {}, {}, {}, [], {})
  self.assertTrue(c['transaction_map_complete']); self.assertFalse(c['transaction_contract_ready']); self.assertEqual(c['transaction_source_agreement_count'],0)
 def test_mismatch_blocks_contract(self):
  methods=self.methods(); constants={m['name']:i for i,m in enumerate(methods,1)}; proxy={m['signature']:[i] for i,m in enumerate(methods,1)}; proxy[methods[0]['signature']]=[99]
  rows,c=M.merge_contract(methods,constants,proxy,{}, {}, {m['signature']:True for m in methods}, [], {})
  self.assertGreater(c['transaction_source_mismatch_count'],0); self.assertFalse(c['transaction_contract_ready'])
 def test_local_aar_resolver_does_not_use_network(self):
  with tempfile.TemporaryDirectory() as td:
   home=Path(td); p=home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1/x'; p.mkdir(parents=True); aar=p/'client-l-1.0.1.aar'; aar.write_bytes(b'x')
   self.assertEqual(M.resolve_aar(None,home),[aar.resolve()])
 def test_runner_contains_no_device_or_network_commands(self):
  text=(HERE/'run_test21_r3_3_4_2_6_1_aar_contract.sh').read_text()
  for token in ('adb shell','adb -s','su -c','/proc/','frida-server','curl ','wget ','am start','am force-stop'):
   self.assertNotIn(token,text)
 def test_analyzer_contains_no_process_or_network_exec(self):
  text=(HERE/'analyze_test21_r3_3_4_2_6_1_aar_contract.py').read_text()
  for token in ('subprocess.','os.system(','requests.','urllib.','socket.','import frida'):
   self.assertNotIn(token,text)

if __name__=='__main__': unittest.main(verbosity=2)
