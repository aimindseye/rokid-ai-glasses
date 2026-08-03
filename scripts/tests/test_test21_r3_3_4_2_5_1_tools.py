#!/usr/bin/env python3
from __future__ import annotations
import os,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class T(unittest.TestCase):
 def test_agent_imports_java_bridge(self):
  s=(HERE/'test21_r3_3_4_2_5_1_frida17_agent.ts').read_text();self.assertIn('import Java from "frida-java-bridge"',s);self.assertIn('Java.performNow',s);self.assertNotIn('Interceptor.replace',s);self.assertNotIn('onBind.implementation',s)
 def test_preparer_pins_versions(self):
  s=(HERE/'prepare_test21_r3_3_4_2_5_1_frida17_agent.py').read_text();self.assertIn("EXPECTED_FRIDA='17.16.4'",s);self.assertIn("BRIDGE_SPEC='frida-java-bridge@7.0.4'",s);self.assertIn('frida.Compiler()',s);self.assertIn('frida.PackageManager()',s)
 def test_collector_uses_compiled_bundle(self):
  s=(HERE/'collect_test21_r3_3_4_2_5_1_frida17.py').read_text();self.assertIn("ap.add_argument('--bundle'",s);self.assertNotIn("--agent'",s);self.assertIn('healthcheck()',s)
 def test_runner_no_connection_mutation(self):
  s=(HERE/'run_test21_r3_3_4_2_5_1_resume.sh').read_text()
  for x in ['force-stop','am start','monkey ',' pm clear','svc bluetooth','set -e','set -u','set -o pipefail']:self.assertNotIn(x,s)
 def test_memory_caps_preserved(self):
  s=(HERE/'collect_test21_r3_3_4_2_5_1_frida17.py').read_text();self.assertIn('67108864',s);self.assertIn('268435456',s)
 def test_sanitizer_excludes_bundle_and_bridge(self):
  s=(HERE/'package_test21_r3_3_4_2_5_1_sanitized.py').read_text();self.assertIn('COMPILED_FRIDA_AGENT_INCLUDED=NO',s);self.assertIn('FRIDA_JAVA_BRIDGE_PACKAGE_INCLUDED=NO',s)
 def test_fake_compiler_preparation(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);fake=d/'fake';fake.mkdir();agent=d/'agent.ts';agent.write_text('import Java from "frida-java-bridge";\nrpc.exports={healthcheck(){return {java_available:Java.available};}};\n')
   fake_code='''__version__="17.16.4"\nimport json, pathlib\nclass PackageManager:\n def install(self,specs):\n  p=pathlib.Path.cwd()/"node_modules/frida-java-bridge";p.mkdir(parents=True,exist_ok=True);(p/"package.json").write_text(json.dumps({"version":"7.0.4"}))\nclass Compiler:\n def on(self,*a): pass\n def build(self,path,project_root=None):\n  s=pathlib.Path(path).read_text();assert "frida-java-bridge" in s;return "/* bundled bridge */\\nrpc.exports={};\\n"\n'''
   (fake/'frida.py').write_text(fake_code);env=os.environ.copy();env['PYTHONPATH']=str(fake);bundle=d/'proj/agent.bundle.js'
   p=subprocess.run([sys.executable,str(HERE/'prepare_test21_r3_3_4_2_5_1_frida17_agent.py'),'--agent-ts',str(agent),'--project-root',str(d/'proj'),'--bundle-out',str(bundle)],env=env,text=True,capture_output=True)
   self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(bundle.is_file());self.assertIn('FRIDA_AGENT_COMPILE=PASS',p.stdout);self.assertIn('FRIDA_JAVA_BRIDGE_IMPORT=PASS',p.stdout)
 def test_fake_collector_compiled_bundle(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);fake=d/'fake';fake.mkdir();bundle=d/'bundle.js';bundle.write_text('compiled');out=d/'out'
   fake_code='''__version__="17.16.4"\nclass Exports:\n def healthcheck(self): return {"java_available":True}\n def snapshot(self): return {"java_available":True,"targets":{},"memory_dex_candidates":[]}\n def readmemory(self,*a): return b""\nclass Script:\n exports_sync=Exports()\n def load(self): pass\nclass Session:\n def create_script(self,s): assert s=="compiled";return Script()\n def detach(self): pass\nclass Dev:\n def attach(self,pid): return Session()\ndef get_usb_device(timeout=8): return Dev()\n'''
   (fake/'frida.py').write_text(fake_code);env=os.environ.copy();env['PYTHONPATH']=str(fake)
   p=subprocess.run([sys.executable,str(HERE/'collect_test21_r3_3_4_2_5_1_frida17.py'),'--pid','123','--bundle',str(bundle),'--output',str(out)],env=env,text=True,capture_output=True)
   self.assertEqual(p.returncode,0,p.stderr);self.assertIn('FRIDA17_JAVA_RUNTIME_GATE=PASS',p.stdout);self.assertIn('FRIDA_RUNTIME_SNAPSHOT=PASS',p.stdout);self.assertTrue((out/'frida-runtime-private.json').is_file())
if __name__=='__main__':unittest.main(verbosity=2)
