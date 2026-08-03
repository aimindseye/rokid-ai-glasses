#!/usr/bin/env python3
import argparse, json, subprocess, time
from pathlib import Path

def run(cmd, timeout=8):
 try:
  p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  return p.returncode,(p.stdout or '').replace('\r','')
 except subprocess.TimeoutExpired:
  return 124,''

def shell(adb,phone,args,timeout=8): return run([adb,'-s',phone,'shell',*args],timeout)
def ps(adb,phone):
 for args in (['ps','-A','-o','USER,PID,PPID,NAME,ARGS'],['ps','-A']):
  rc,out=shell(adb,phone,args)
  if rc==0 and out.strip(): return out
 return ''
def classify(text,hi,custom):
 same=[]; ext=[]
 for line in text.splitlines():
  low=line.lower()
  if hi in line: same.append(line.strip())
  elif custom in line: continue
  elif any(t in low for t in ('rokid','cxr','aiui','sprite')): ext.append(line.strip())
 return same,ext
def snapshot(adb,phone,hi,custom,out,prefix):
 for name,args in {f'{prefix}-hi-services-private.txt':['dumpsys','activity','services',hi],f'{prefix}-custom-services-private.txt':['dumpsys','activity','services',custom],f'{prefix}-activity-processes-private.txt':['dumpsys','activity','processes']}.items():
  rc,txt=shell(adb,phone,args,12); (out/name).write_text(f'COLLECTION_RC={rc}\n{txt}')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--adb',required=True); ap.add_argument('--phone',required=True); ap.add_argument('--hi-package',required=True); ap.add_argument('--custom-package',required=True); ap.add_argument('--output',required=True); ap.add_argument('--duration-seconds',type=float,default=30); ap.add_argument('--poll-seconds',type=float,default=.2)
 a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
 start=time.monotonic(); first=None; records=[]; ext_union=set(); same_union=set()
 while time.monotonic()-start < a.duration_seconds:
  elapsed=int((time.monotonic()-start)*1000); rc,pids=shell(a.adb,a.phone,['pidof',a.hi_package]); pids=pids.strip(); pst=ps(a.adb,a.phone); same,ext=classify(pst,a.hi_package,a.custom_package); same_union.update(same); ext_union.update(ext)
  records.append({'elapsed_ms':elapsed,'hi_visible':bool(pids),'same_package_process_count':len(same),'external_candidate_count':len(ext)})
  if pids and first is None:
   first=elapsed; (out/'first-respawn-ps-private.txt').write_text(pst); snapshot(a.adb,a.phone,a.hi_package,a.custom_package,out,'first-respawn')
  time.sleep(max(.05,a.poll_seconds))
 with (out/'authorized-topology-timeline.jsonl').open('w') as f:
  for rec in records: f.write(json.dumps(rec,sort_keys=True)+'\n')
 (out/'topology-observation.txt').write_text('SCHEMA=rokid.test21-r3-3.authorized-topology.v1\n'+f'OBSERVATION_SECONDS={a.duration_seconds:g}\n'+f'HI_ROKID_RESPAWN_OBSERVED={"YES" if first is not None else "NO"}\n'+f'FIRST_RESPAWN_ELAPSED_MS={first if first is not None else "NONE"}\n'+f'SAME_PACKAGE_PROCESS_LINES_SEEN={len(same_union)}\n'+f'EXTERNAL_ROKID_AI_CANDIDATE_LINES_SEEN={len(ext_union)}\n')
 (out/'external-candidates-private.txt').write_text('\n'.join(sorted(ext_union))+'\n' if ext_union else '')
 print(f'HI_ROKID_RESPAWN_OBSERVED={"YES" if first is not None else "NO"}'); print(f'FIRST_RESPAWN_ELAPSED_MS={first if first is not None else "NONE"}'); print(f'EXTERNAL_ROKID_AI_CANDIDATE_LINES_SEEN={len(ext_union)}'); return 0
if __name__=='__main__': raise SystemExit(main())
