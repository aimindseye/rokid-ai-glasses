#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,time
from pathlib import Path

WATCH=('connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','canonical_image_callback_reregistration_result','photo_ready','operator_gate_prerequisite_ready','qualification_terminal')
SERVICE_COMPONENT='com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
def now_ms():return time.time_ns()//1_000_000
def run(argv,timeout=6.0):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,check=False);return p.returncode,(p.stdout or '')+(p.stderr or '')
    except subprocess.TimeoutExpired:return 124,''
def shell(adb,phone,cmd,timeout=6.0):return run([adb,'-s',phone,'shell',cmd],timeout)
def pidof(adb,phone,pkg):
    rc,out=shell(adb,phone,f'pidof {pkg}',3.0);return out.strip() if rc==0 else ''
def events(adb,phone,path):
    safe=path.replace("'","'\\''");rc,out=shell(adb,phone,f"tail -n 180 '{safe}' 2>/dev/null",5.0)
    if rc:return []
    ans=[]
    for line in out.splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict):ans.append(x)
        except Exception:pass
    return ans

def capture(adb,phone,hi,custom,out,stem):
    cmds={
      'activity-services-global':'dumpsys activity services',
      'hi-services':f'dumpsys activity services {hi}',
      'cxrlinkservice':f'dumpsys activity service {SERVICE_COMPONENT}',
      'hi-providers':f'dumpsys activity providers {hi}',
      'activity-processes':'dumpsys activity processes',
      'hi-package':f'dumpsys package {hi}',
      'custom-package':f'dumpsys package {custom}',
    }
    for suffix,cmd in cmds.items():
        rc,text=shell(adb,phone,cmd,15.0)
        (out/f'{stem}-{suffix}-private.txt').write_text(f'COLLECTION_RC={rc}\n{text}',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser()
    for k in ('adb','phone','hi-package','custom-package','remote-events','output','ready-file'):ap.add_argument('--'+k,required=True)
    ap.add_argument('--duration-seconds',type=float,default=16);ap.add_argument('--poll-seconds',type=float,default=.075);ap.add_argument('--snapshot-seconds',type=float,default=.35)
    a=ap.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);ready=Path(a.ready_file).resolve();ready.parent.mkdir(parents=True,exist_ok=True)
    timeline=out/'binding-contract-timeline-private.jsonl';samples=out/'binding-contract-samples-private.txt'
    first={};resp=None;prior=bool(pidof(a.adb,a.phone,a.hi_package));stamp0=now_ms()
    ready.write_text(f'COLLECTOR_READY=YES\nHI_PROCESS_VISIBLE={"YES" if prior else "NO"}\nHOST_EPOCH_MS={stamp0}\n',encoding='utf-8')
    if prior:
        print('ERROR: Hi Rokid visible at collector start');return 3
    start=time.monotonic();deadline=start+max(3.0,a.duration_seconds);lastsnap=0.0;sample_no=0
    with timeline.open('w',encoding='utf-8') as f:
      f.write(json.dumps({'kind':'collector_started','host_epoch_ms':stamp0,'hi_process_visible':False},sort_keys=True)+'\n');f.flush()
      while time.monotonic()<deadline:
        stamp=now_ms();hp=pidof(a.adb,a.phone,a.hi_package);cp=pidof(a.adb,a.phone,a.custom_package);hi=bool(hp)
        f.write(json.dumps({'kind':'sample','host_epoch_ms':stamp,'hi_process_visible':hi,'hi_pids':hp,'custom_process_visible':bool(cp),'custom_pids':cp},sort_keys=True)+'\n');f.flush()
        if hi and not prior and resp is None:
            resp=stamp;f.write(json.dumps({'kind':'hi_process_first_respawn','host_epoch_ms':stamp,'hi_pids':hp},sort_keys=True)+'\n');f.flush();capture(a.adb,a.phone,a.hi_package,a.custom_package,out,'at-respawn')
        prior=hi
        for ev in events(a.adb,a.phone,a.remote_events):
            et=str(ev.get('event_type','')).strip()
            if et in WATCH and et not in first:
                first[et]=stamp;f.write(json.dumps({'kind':'event_first_seen','host_epoch_ms':stamp,'event_type':et},sort_keys=True)+'\n');f.flush()
        now=time.monotonic()
        if now-lastsnap>=a.snapshot_seconds:
            sample_no+=1
            rc1,s1=shell(a.adb,a.phone,'dumpsys activity services',15.0)
            rc2,s2=shell(a.adb,a.phone,f'dumpsys activity services {a.hi_package}',15.0)
            rc3,s3=shell(a.adb,a.phone,f'dumpsys activity service {SERVICE_COMPONENT}',15.0)
            with samples.open('a',encoding='utf-8') as sf:
                sf.write(f'\n=== SAMPLE {sample_no} host_epoch_ms={stamp} global_rc={rc1} hi_rc={rc2} service_rc={rc3} ===\n--- GLOBAL SERVICES ---\n{s1}\n--- HI SERVICES ---\n{s2}\n--- EXACT SERVICE DUMP ---\n{s3}\n')
            lastsnap=now
        time.sleep(max(.04,a.poll_seconds))
    capture(a.adb,a.phone,a.hi_package,a.custom_package,out,'collector-final')
    (out/'binding-contract-collector-summary-private.json').write_text(json.dumps({'schema':'rokid.test21-r3-3-4-1.collector.v1','first_hi_respawn_host_epoch_ms':resp,'event_first_seen_host_epoch_ms':first},indent=2,sort_keys=True)+'\n')
    print('TEST21_R3_3_4_1_BINDING_COLLECTION=PASS');print('HI_RESPAWN_OBSERVED='+('YES' if resp is not None else 'NO'))
    return 0
if __name__=='__main__':raise SystemExit(main())
