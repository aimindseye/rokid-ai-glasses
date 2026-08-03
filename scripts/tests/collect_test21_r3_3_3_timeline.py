#!/usr/bin/env python3
import argparse,json,subprocess,time
from pathlib import Path
WATCH=("connection_attempt_started","callback_cxrl_connected","callback_glass_bt_connected","service_status_result","canonical_image_callback_reregistration_result","photo_ready","operator_gate_prerequisite_ready","qualification_terminal")
def now(): return time.time_ns()//1_000_000
def run(argv,timeout=6):
 try:
  p=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout);return p.returncode,(p.stdout or '').replace('\r','')
 except subprocess.TimeoutExpired:return 124,''
def sh(adb,phone,cmd,timeout=6):return run([adb,'-s',phone,'shell',cmd],timeout)
def visible(adb,phone,pkg):return bool(sh(adb,phone,f'pidof {pkg}')[1].strip())
def tail(adb,phone,path):
 q=path.replace("'","'\\''");rc,o=sh(adb,phone,f"tail -n 160 '{q}' 2>/dev/null",5);out=[]
 if rc: return out
 for line in o.splitlines():
  try:
   x=json.loads(line)
   if isinstance(x,dict):out.append(x)
  except:pass
 return out
def dump(adb,phone,cmd,path):
 rc,o=sh(adb,phone,cmd,12);path.write_text(f'COLLECTION_RC={rc}\n{o}',encoding='utf-8')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adb',required=True);ap.add_argument('--phone',required=True);ap.add_argument('--hi-package',required=True);ap.add_argument('--custom-package',required=True);ap.add_argument('--remote-events',required=True);ap.add_argument('--output',required=True);ap.add_argument('--duration-seconds',type=float,default=22);ap.add_argument('--poll-seconds',type=float,default=.2);a=ap.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True);timeline=out/'timeline-private.jsonl';first={};respawn=None;prior=visible(a.adb,a.phone,a.hi_package);start=time.monotonic();deadline=start+max(2,a.duration_seconds);sampled=False
 with timeline.open('w',encoding='utf-8') as f:
  while time.monotonic()<deadline:
   stamp=now();hi=visible(a.adb,a.phone,a.hi_package);cu=visible(a.adb,a.phone,a.custom_package)
   row={'kind':'sample','host_epoch_ms':stamp,'hi_process_visible':hi,'custom_process_visible':cu};f.write(json.dumps(row,sort_keys=True)+'\n');f.flush()
   if not sampled:f.write(json.dumps({'kind':'collector_started','host_epoch_ms':stamp,'hi_process_visible':hi,'custom_process_visible':cu},sort_keys=True)+'\n');f.flush();sampled=True
   if hi and not prior and respawn is None:
    respawn=stamp;f.write(json.dumps({'kind':'hi_process_first_respawn','host_epoch_ms':stamp},sort_keys=True)+'\n');f.flush();dump(a.adb,a.phone,f'dumpsys activity services {a.hi_package}',out/'respawn-hi-services-private.txt');dump(a.adb,a.phone,f'dumpsys activity services {a.custom_package}',out/'respawn-custom-services-private.txt');dump(a.adb,a.phone,'dumpsys activity processes',out/'respawn-activity-processes-private.txt');dump(a.adb,a.phone,'ps -A -o USER,PID,PPID,NAME,ARGS',out/'respawn-processes-private.txt')
   prior=hi
   for e in tail(a.adb,a.phone,a.remote_events):
    et=str(e.get('event_type','')).strip()
    if et in WATCH and et not in first:first[et]=stamp;f.write(json.dumps({'kind':'event_first_seen','host_epoch_ms':stamp,'event_type':et},sort_keys=True)+'\n');f.flush()
   time.sleep(max(.05,a.poll_seconds))
 summary={'schema':'rokid.test21-r3-3-3.collector.v1','first_hi_respawn_host_epoch_ms':respawn,'event_first_seen_host_epoch_ms':first,'duration_seconds':a.duration_seconds,'poll_seconds':a.poll_seconds}
 (out/'collector-summary-private.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 print('TEST21_R3_3_3_TIMELINE_COLLECTION=PASS');print('HI_RESPAWN_OBSERVED='+('YES' if respawn else 'NO'))
 return 0
if __name__=='__main__':raise SystemExit(main())
