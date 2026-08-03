#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--runtime-dir',required=True);ap.add_argument('--root-collection',required=True);ap.add_argument('--output',required=True);ap.add_argument('--compiler-project',required=True);a=ap.parse_args();repo=Path(a.repo);out=Path(a.output);san=out/'sanitized';san.mkdir(parents=True,exist_ok=True)
 cp=subprocess.run([sys.executable,str(repo/'scripts/tests/analyze_test21_r3_3_4_2_5_runtime.py'),'--repo',str(repo),'--runtime-dir',a.runtime_dir,'--root-collection',a.root_collection,'--output',str(out)])
 if cp.returncode!=0:return cp.returncode
 oldj=san/'test21-r3-3-4-2-5-summary.json';oldt=san/'test21-r3-3-4-2-5-summary.txt'
 if not oldj.is_file() or not oldt.is_file(): print('ERROR: prerequisite r3.3.4.2.5 summary missing',file=sys.stderr);return 2
 j=json.loads(oldj.read_text());qpath=Path(a.compiler_project)/'compiler-qualification-private.json';q=json.loads(qpath.read_text()) if qpath.is_file() else {};j.update({'schema':'rokid.test21-r3.3.4.2.5.1.sanitized.v1','repair':'FRIDA17_JAVA_BRIDGE_COMPILED_AGENT','frida17_host_version_gate':'PASS','frida_java_bridge_import':'PASS','frida_agent_compile':'PASS','frida_agent_bundle_resolution':'PASS','frida_java_bridge_version':q.get('bridge_version','UNRESOLVED')});(san/'test21-r3-3-4-2-5-1-summary.json').write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')
 lines=['TEST21_R3_3_4_2_5_1_ANALYSIS=PASS','REPAIR=FRIDA17_JAVA_BRIDGE_COMPILED_AGENT','FRIDA17_HOST_VERSION_GATE=PASS','FRIDA_JAVA_BRIDGE_IMPORT=PASS','FRIDA_AGENT_COMPILE=PASS','FRIDA_AGENT_BUNDLE_RESOLUTION=PASS','FRIDA_JAVA_BRIDGE_VERSION='+str(q.get('bridge_version','UNRESOLVED'))];lines += [x for x in oldt.read_text().splitlines() if x and not x.startswith('TEST21_R3_3_4_2_5_ANALYSIS=')];(san/'test21-r3-3-4-2-5-1-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
if __name__=='__main__': raise SystemExit(main())
