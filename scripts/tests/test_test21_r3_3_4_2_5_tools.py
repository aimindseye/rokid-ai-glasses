#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_agent_observation_only(self):
  s=(HERE/'test21_r3_3_4_2_5_frida_agent.js').read_text();self.assertIn('Java.enumerateClassLoaders',s);self.assertIn('Memory.scanSync',s);self.assertNotIn('Interceptor.replace',s);self.assertNotIn('onBind.implementation',s)
 def test_runner_no_connection_mutation(self):
  s=(HERE/'run_test21_r3_3_4_2_5_runtime_classloader.sh').read_text();
  for x in ['force-stop','am start','monkey ',' pm clear','svc bluetooth','set -e','set -u','set -o pipefail']:self.assertNotIn(x,s)
 def test_memory_cap(self):
  s=(HERE/'collect_test21_r3_3_4_2_5_frida.py').read_text();self.assertIn('67108864',s);self.assertIn('268435456',s)
 def test_exact_classdef_gate_present(self):
  s=(HERE/'analyze_test21_r3_3_4_2_5_runtime.py').read_text();self.assertIn("classdefs(hits,SERVICE)",s);self.assertIn("CXRLINKSERVICE_CLASS_DEF_CONFIRMED",s)
 def test_sanitizer_excludes_raw(self):
  s=(HERE/'package_test21_r3_3_4_2_5_sanitized.py').read_text();self.assertIn('RAW_MEMORY_DEX_INCLUDED=NO',s);self.assertNotIn('r3-3-4-2-5-private.json',s)
 def test_frida_required_gate(self):
  s=(HERE/'run_test21_r3_3_4_2_5_runtime_classloader.sh').read_text();self.assertIn('INSTRUMENTATION_MODE',s);self.assertIn('required',s)
 def test_no_onbind_invocation(self):
  s=(HERE/'test21_r3_3_4_2_5_frida_agent.js').read_text();self.assertNotIn('.onBind(',s)
 def test_transient_server_cleanup(self):
  s=(HERE/'run_test21_r3_3_4_2_5_runtime_classloader.sh').read_text();self.assertIn('trap cleanup EXIT INT TERM',s);self.assertIn('kill $STARTED_PID',s)
if __name__=='__main__':unittest.main(verbosity=2)
