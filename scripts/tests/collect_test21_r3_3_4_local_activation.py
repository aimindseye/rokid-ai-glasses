#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,time
from pathlib import Path
from typing import Any
WATCH=("connection_attempt_started","callback_cxrl_connected","callback_glass_bt_connected","service_status_result","canonical_image_callback_reregistration_result","photo_ready","operator_gate_prerequisite_ready","qualification_terminal")
def now_ms(): return time.time_ns()//1_000_000
def run(argv,timeout=5.0):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,check=False)
        return p.returncode,(p.stdout or '')+(p.stderr or '')
    except subprocess.TimeoutExpired:return 124,''
def shell(adb,phone,cmd,timeout=5.0): return run([adb,'-s',phone,'shell',cmd],timeout)
def pidof(adb,phone,pkg):
    rc,out=shell(adb,phone,f'pidof {pkg}',3.0); return out.strip() if rc==0 else ''
def events(adb,phone,path):
    safe=path.replace("'","'\\''");rc,out=shell(adb,phone,f"tail -n 160 '{safe}' 2>/dev/null",5.0)
    if rc:return []
    ans=[]
    for line in out.splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict):ans.append(x)
        except Exception:pass
    return ans
def snap(adb,phone,hi,custom,out,stem):
    cmds={
      'hi-services':f'dumpsys activity services {hi}',
      'hi-providers':f'dumpsys activity providers {hi}',
      'custom-services':f'dumpsys activity services {custom}',
      'activity-processes':'dumpsys activity processes',
    }
    for suffix,cmd in cmds.items():
        rc,text=shell(adb,phone,cmd,12.0)
        (out/f'{stem}-{suffix}-private.txt').write_text(f'COLLECTION_RC={rc}\n{text}',encoding='utf-8')
def main():
    a=argparse.ArgumentParser();
    for k in ('adb','phone','hi-package','custom-package','remote-events','output'):a.add_argument('--'+k,required=True)
    a.add_argument('--duration-seconds',type=float,default=18);a.add_argument('--poll-seconds',type=float,default=.10);a.add_argument('--snapshot-seconds',type=float,default=.75);a.add_argument('--ready-file',required=True)
    x=a.parse_args();out=Path(x.output).resolve();out.mkdir(parents=True,exist_ok=True)
    tl=out/'local-activation-timeline-private.jsonl';samples=out/'runtime-component-samples-private.txt'
    first={};prior_hi=bool(pidof(x.adb,x.phone,x.hi_package));resp=None;lastsnap=0.0;start=time.monotonic();deadline=start+max(3,x.duration_seconds)
    ready=Path(x.ready_file).resolve();ready.parent.mkdir(parents=True,exist_ok=True)
    with tl.open('w',encoding='utf-8') as f:
      stamp0=now_ms();f.write(json.dumps({'kind':'collector_started','host_epoch_ms':stamp0,'hi_process_visible':prior_hi},sort_keys=True)+'\n');f.flush()
      ready.write_text(f'COLLECTOR_READY=YES\nHI_PROCESS_VISIBLE={"YES" if prior_hi else "NO"}\nHOST_EPOCH_MS={stamp0}\n',encoding='utf-8')
      while time.monotonic()<deadline:
        stamp=now_ms();hp=pidof(x.adb,x.phone,x.hi_package);cp=pidof(x.adb,x.phone,x.custom_package);hi=bool(hp);cu=bool(cp)
        f.write(json.dumps({'kind':'sample','host_epoch_ms':stamp,'hi_process_visible':hi,'hi_pids':hp,'custom_process_visible':cu},sort_keys=True)+'\n');f.flush()
        if hi and not prior_hi and resp is None:
          resp=stamp;f.write(json.dumps({'kind':'hi_process_first_respawn','host_epoch_ms':stamp,'hi_pids':hp},sort_keys=True)+'\n');f.flush();snap(x.adb,x.phone,x.hi_package,x.custom_package,out,'at-respawn')
        prior_hi=hi
        for ev in events(x.adb,x.phone,x.remote_events):
          et=str(ev.get('event_type','')).strip()
          if et in WATCH and et not in first:
            first[et]=stamp;f.write(json.dumps({'kind':'event_first_seen','host_epoch_ms':stamp,'event_type':et},sort_keys=True)+'\n');f.flush()
        now=time.monotonic()
        if now-lastsnap>=x.snapshot_seconds:
          rc1,s1=shell(x.adb,x.phone,f'dumpsys activity services {x.hi_package}',10.0);rc2,s2=shell(x.adb,x.phone,f'dumpsys activity providers {x.hi_package}',10.0)
          with samples.open('a',encoding='utf-8') as sf:
            sf.write(f'\n=== SAMPLE host_epoch_ms={stamp} service_rc={rc1} provider_rc={rc2} ===\n--- SERVICES ---\n{s1}\n--- PROVIDERS ---\n{s2}\n')
          lastsnap=now
        time.sleep(max(.05,x.poll_seconds))
    snap(x.adb,x.phone,x.hi_package,x.custom_package,out,'collector-final')
    (out/'local-activation-collector-summary-private.json').write_text(json.dumps({'schema':'rokid.test21-r3-3-4.collector.v1','first_hi_respawn_host_epoch_ms':resp,'event_first_seen_host_epoch_ms':first},indent=2,sort_keys=True)+'\n')
    print('TEST21_R3_3_4_LOCAL_ACTIVATION_COLLECTION=PASS');print('HI_RESPAWN_OBSERVED='+('YES' if resp is not None else 'NO'))
    return 0
if __name__=='__main__':raise SystemExit(main())
