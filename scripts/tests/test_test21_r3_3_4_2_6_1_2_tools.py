#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('r3342612',HERE/'analyze_test21_r3_3_4_2_6_1_2_callback_abi.py')
M=importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; sys.modules[SPEC.name]=M; SPEC.loader.exec_module(M)

class CallbackAbiTests(unittest.TestCase):
 def test_exact_seven_callback_interfaces(self):
  self.assertEqual(M.EXPECTED_CALLBACK_INTERFACE_COUNT,7)
  self.assertEqual(len(M.CALLBACK_INTERFACES),7)
  self.assertEqual({x[0] for x in M.CALLBACK_INTERFACES},{'IMAGE','AUDIO','CUSTOM_VIEW','DEVICE_STATUS','CUSTOM_CMD','GLASS_APP','AI_EVENT'})
 def test_unique_exact_proxy_selection(self):
  rows=[{'class_name':'X','score':101,'matching_interface_method_count':3}]
  self.assertEqual(M.select_proxy(rows,3),('X','UNIQUE_EXACT_STRUCTURAL_PROXY'))
 def test_ambiguous_proxy_is_not_selected(self):
  rows=[{'class_name':'X','score':101,'matching_interface_method_count':3},{'class_name':'Y','score':101,'matching_interface_method_count':3}]
  self.assertEqual(M.select_proxy(rows,3),(None,'AMBIGUOUS_TOP_STRUCTURAL_PROXY_CANDIDATES'))
 def test_incomplete_proxy_surface_is_not_selected(self):
  rows=[{'class_name':'X','score':101,'matching_interface_method_count':2}]
  self.assertEqual(M.select_proxy(rows,3),(None,'TOP_CANDIDATE_DOES_NOT_IMPLEMENT_EXACT_INTERFACE_SURFACE'))
 def test_transact_flag_zero_is_recovered(self):
  ins=[SimpleNamespace(int_value=9),SimpleNamespace(int_value=None),SimpleNamespace(int_value=0),SimpleNamespace(int_value=None)]
  self.assertEqual(M.recover_transact_flags(ins,3)[0],0)
 def test_transact_flag_one_is_recovered(self):
  ins=[SimpleNamespace(int_value=9),SimpleNamespace(int_value=7),SimpleNamespace(int_value=1),SimpleNamespace(int_value=None)]
  self.assertEqual(M.recover_transact_flags(ins,3)[0],1)
 def test_nonstandard_transact_flag_is_not_accepted(self):
  ins=[SimpleNamespace(int_value=9),SimpleNamespace(int_value=4),SimpleNamespace(int_value=None)]
  self.assertIsNone(M.recover_transact_flags(ins,2)[0])
 def test_local_aar_resolver_has_no_network_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   home=Path(td); p=home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1/x'; p.mkdir(parents=True); aar=p/'client-l-1.0.1.aar'; aar.write_bytes(b'x')
   self.assertEqual(M.resolve_aar(None,home),[aar.resolve()])
 def test_runner_is_host_only(self):
  text=(HERE/'run_test21_r3_3_4_2_6_1_2_callback_abi.sh').read_text()
  for token in ('adb shell','adb -s','su -c','/proc/','frida-server','ptrace(','curl ','wget ','am start','am force-stop'):
   self.assertNotIn(token,text)
 def test_analyzer_has_no_device_process_or_network_execution(self):
  text=(HERE/'analyze_test21_r3_3_4_2_6_1_2_callback_abi.py').read_text()
  for token in ('subprocess.','os.system(','requests.','urllib.','socket.','import frida','frida.','/proc/'):
   self.assertNotIn(token,text)
 def test_packager_is_explicit_allow_list(self):
  text=(HERE/'package_test21_r3_3_4_2_6_1_2_sanitized.py').read_text()
  self.assertIn('ALLOWED',text); self.assertIn('callback-transaction-map.tsv',text); self.assertIn('callback-parcel-marshalling.tsv',text)

if __name__=='__main__': unittest.main(verbosity=2)
