#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
EXPECTED='17.16.4'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--bundle',required=True);ap.add_argument('--output',required=True);ap.add_argument('--expected-frida',default=EXPECTED);ap.add_argument('--max-total-bytes',type=int,default=268435456);a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);mem=out/'memory-dex';mem.mkdir(exist_ok=True)
 try: import frida
 except Exception: print('FRIDA_HOST_MODULE=UNAVAILABLE',file=sys.stderr);return 3
 if getattr(frida,'__version__','UNRESOLVED')!=a.expected_frida: print('FRIDA17_HOST_VERSION_GATE=FAIL',file=sys.stderr);return 4
 session=None
 try:
  session=frida.get_usb_device(timeout=8).attach(a.pid);script=session.create_script(Path(a.bundle).read_text());script.load();health=script.exports_sync.healthcheck()
  if not isinstance(health,dict) or not health.get('java_available'): print('FRIDA17_JAVA_RUNTIME_GATE=FAIL',file=sys.stderr);return 5
  print('FRIDA17_JAVA_RUNTIME_GATE=PASS');snap=script.exports_sync.snapshot()
  if not isinstance(snap,dict) or not snap.get('java_available'): print('FRIDA_RUNTIME_SNAPSHOT=FAIL_JAVA_UNAVAILABLE',file=sys.stderr);return 6
  (out/'frida-runtime-private.json').write_text(json.dumps(snap,indent=2,sort_keys=True)+'\n');total=0;rows=[]
  for i,c in enumerate(snap.get('memory_dex_candidates') or []):
   size=int(c.get('size') or 0)
   if size<112 or size>67108864 or total+size>a.max_total_bytes: continue
   addr=str(c['address']);p=mem/f'memory-dex-{i:03d}.dex'
   try:
    with p.open('wb') as f:
     off=0
     while off<size:
      n=min(1024*1024,size-off);b=script.exports_sync.readmemory(addr,off,n)
      if not isinstance(b,(bytes,bytearray)): b=bytes(b)
      if len(b)!=n: raise RuntimeError('short read')
      f.write(b);off+=n
    h=hashlib.sha256(p.read_bytes()).hexdigest();rows.append({'candidate_index':i,'size':size,'sha256':h,'local_rel':'memory-dex/'+p.name});total+=size
   except Exception:
    try:p.unlink()
    except Exception:pass
    rows.append({'candidate_index':i,'size':size,'status':'READ_FAILED'})
  (out/'memory-dex-manifest.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n');print('FRIDA_RUNTIME_SNAPSHOT=PASS');print('MEMORY_DEX_CANDIDATE_COUNT='+str(len(snap.get('memory_dex_candidates') or [])));print('MEMORY_DEX_DUMP_PASS_COUNT='+str(sum(1 for r in rows if 'sha256' in r)));return 0
 finally:
  try:
   if session is not None: session.detach()
  except Exception: pass
if __name__=='__main__': raise SystemExit(main())
