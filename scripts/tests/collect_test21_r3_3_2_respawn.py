#!/usr/bin/env python3
import argparse,json,subprocess,time
from pathlib import Path

def run(cmd,timeout=12):
 try:
  p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout);return p.returncode,(p.stdout or '').replace('\r','')
 except subprocess.TimeoutExpired:return 124,''
def sh(adb,phone,args,timeout=12):return run([adb,'-s',phone,'shell',*args],timeout)
def ps(adb,phone):
 for args in (['ps','-A','-o','USER,PID,PPID,NAME,ARGS'],['ps','-A']):
  rc,o=sh(adb,phone,args)
  if rc==0 and o.strip():return o
 return ''
def snap(adb,phone,hi,custom,out):
 for n,args in {'first-respawn-hi-services-private.txt':['dumpsys','activity','services',hi],'first-respawn-custom-services-private.txt':['dumpsys','activity','services',custom],'first-respawn-activity-processes-private.txt':['dumpsys','activity','processes']}.items():
  rc,o=sh(adb,phone,args);(out/n).write_text(f'COLLECTION_RC={rc}\n{o}')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adb',required=True);ap.add_argument('--phone',required=True);ap.add_argument('--hi-package',required=True);ap.add_argument('--custom-package',required=True);ap.add_argument('--output',required=True);ap.add_argument('--duration-seconds',type=float,default=30);ap.add_argument('--poll-seconds',type=float,default=.2);a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 start=time.monotonic();first=None;rows=[]
 while time.monotonic()-start<a.duration_seconds:
  ms=int((time.monotonic()-start)*1000);pids=sh(a.adb,a.phone,['pidof',a.hi_package])[1].strip();rows.append({'elapsed_ms':ms,'hi_visible':bool(pids)})
  if pids and first is None:first=ms;(out/'first-respawn-ps-private.txt').write_text(ps(a.adb,a.phone));snap(a.adb,a.phone,a.hi_package,a.custom_package,out)
  time.sleep(max(.05,a.poll_seconds))
 with (out/'respawn-timeline.jsonl').open('w') as f:
  for r in rows:f.write(json.dumps(r,sort_keys=True)+'\n')
 (out/'topology-observation.txt').write_text(f'OBSERVATION_SECONDS={a.duration_seconds:g}\nHI_ROKID_RESPAWN_OBSERVED={"YES" if first is not None else "NO"}\nFIRST_RESPAWN_ELAPSED_MS={first if first is not None else "NONE"}\n')
 print(f'HI_ROKID_RESPAWN_OBSERVED={"YES" if first is not None else "NO"}');return 0
if __name__=='__main__':raise SystemExit(main())
