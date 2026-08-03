#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shutil,sys
from pathlib import Path
EXPECTED_FRIDA='17.16.4'
BRIDGE_SPEC='frida-java-bridge@7.0.4'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--agent-ts',required=True);ap.add_argument('--project-root',required=True);ap.add_argument('--bundle-out',required=True);ap.add_argument('--expected-frida',default=EXPECTED_FRIDA);ap.add_argument('--bridge-spec',default=BRIDGE_SPEC);a=ap.parse_args()
 try: import frida
 except Exception: print('FRIDA_HOST_MODULE=NO',file=sys.stderr);return 3
 ver=getattr(frida,'__version__','UNRESOLVED');print('FRIDA_HOST_MODULE=YES');print('FRIDA_HOST_VERSION='+str(ver))
 if ver!=a.expected_frida: print('FRIDA17_HOST_VERSION_GATE=FAIL',file=sys.stderr);return 4
 print('FRIDA17_HOST_VERSION_GATE=PASS')
 if not hasattr(frida,'Compiler') or not hasattr(frida,'PackageManager'): print('FRIDA17_COMPILER_PACKAGE_MANAGER_API=FAIL',file=sys.stderr);return 5
 print('FRIDA17_COMPILER_PACKAGE_MANAGER_API=PASS')
 root=Path(a.project_root);root.mkdir(parents=True,exist_ok=True);src=root/'agent.ts';shutil.copyfile(a.agent_ts,src)
 pkg=root/'package.json'
 if not pkg.exists(): pkg.write_text(json.dumps({'name':'rokid-test21-r334251-agent','private':True,'version':'0.0.0'},indent=2)+'\n')
 bridge_pkg=root/'node_modules/frida-java-bridge/package.json';installed=False;cwd=os.getcwd()
 try:
  os.chdir(root)
  if not bridge_pkg.is_file(): frida.PackageManager().install(specs=[a.bridge_spec]);installed=True
 except Exception as e:
  print('FRIDA_JAVA_BRIDGE_PACKAGE_INSTALL=FAIL',file=sys.stderr);print('FRIDA_JAVA_BRIDGE_ERROR='+type(e).__name__+':'+str(e),file=sys.stderr);return 6
 finally: os.chdir(cwd)
 if not bridge_pkg.is_file(): print('FRIDA_JAVA_BRIDGE_IMPORT=FAIL',file=sys.stderr);return 7
 try: meta=json.loads(bridge_pkg.read_text())
 except Exception: meta={}
 bridge_ver=str(meta.get('version') or 'UNRESOLVED');print('FRIDA_JAVA_BRIDGE_IMPORT=PASS');print('FRIDA_JAVA_BRIDGE_VERSION='+bridge_ver);print('FRIDA_JAVA_BRIDGE_PACKAGE_INSTALL='+('HOST_PRIVATE_WORKSPACE_ONLY' if installed else 'NOT_NEEDED_ALREADY_PRESENT'))
 diags=[]
 try:
  compiler=frida.Compiler()
  try: compiler.on('diagnostics',lambda d:diags.append(str(d)))
  except Exception: pass
  bundle=compiler.build(str(src),project_root=str(root))
 except Exception as e:
  print('FRIDA_AGENT_COMPILE=FAIL',file=sys.stderr);print('FRIDA_AGENT_COMPILE_ERROR='+type(e).__name__+':'+str(e),file=sys.stderr);return 8
 bout=Path(a.bundle_out);bout.parent.mkdir(parents=True,exist_ok=True);bout.write_text(bundle)
 if not bout.is_file() or bout.stat().st_size==0: print('FRIDA_AGENT_COMPILE=FAIL',file=sys.stderr);return 9
 if "from 'frida-java-bridge'" in bundle or 'from "frida-java-bridge"' in bundle: print('FRIDA_AGENT_BUNDLE_RESOLUTION=FAIL',file=sys.stderr);return 10
 q={'schema':'rokid.test21-r3.3.4.2.5.1.compiler-qualification.v1','frida_host_version':ver,'expected_frida_version':a.expected_frida,'bridge_spec':a.bridge_spec,'bridge_version':bridge_ver,'package_install_performed':installed,'bundle_bytes':bout.stat().st_size,'diagnostics':diags[:64]};(root/'compiler-qualification-private.json').write_text(json.dumps(q,indent=2,sort_keys=True)+'\n')
 print('FRIDA_AGENT_COMPILE=PASS');print('FRIDA_AGENT_BUNDLE_RESOLUTION=PASS');print('FRIDA_AGENT_BUNDLE_BYTES='+str(bout.stat().st_size));return 0
if __name__=='__main__': raise SystemExit(main())
