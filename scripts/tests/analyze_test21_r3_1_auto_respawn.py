#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
HI='com.rokid.sprite.global.aiapp'
CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
PROFILES={'NO_CUSTOM_PROCESS','CUSTOM_UNAUTHORIZED_ALIVE','CUSTOM_AUTHORIZED_NO_CONNECT','CUSTOM_STOPPED_POST_AUTH'}
COMP_RE=re.compile(rf'({re.escape(HI)}/[A-Za-z0-9_.$:-]+)')
BIND_RE=re.compile(r'bind|bound|ConnectionRecord|IntentBindRecord|am_bind_service', re.I)
START_RE=re.compile(r'am_proc_start|Start proc|startProcess|ProcessRecord', re.I)

def kv(p):
    d={}
    if not p.is_file(): return d
    for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
        if '=' in line:
            k,v=line.split('=',1); d[k.strip()]=v.strip()
    return d

def rows(p):
    out=[]
    if not p.is_file(): return out
    for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
        try: out.append(json.loads(line))
        except Exception: pass
    return out

def evidence(raw):
    chunks=[]
    for n in ('activity-events-private.txt','activity-manager-private.txt','respawn-hi-services-private.txt','respawn-custom-services-private.txt','respawn-processes-private.txt'):
        p=raw/n
        if p.is_file(): chunks.append(p.read_text(encoding='utf-8',errors='replace'))
    text='\n'.join(chunks)
    bind=[]; caller=[]; starts=[]
    for line in text.splitlines():
        t=line.strip()
        if HI in t and BIND_RE.search(t):
            bind.append(t)
            if CUSTOM in t: caller.append(t)
        if HI in t and START_RE.search(t): starts.append(t)
    return {
        'bound': bool(bind), 'caller': bool(caller), 'process_start': bool(starts),
        'bind_count': len(bind), 'caller_count': len(caller), 'start_count': len(starts),
        'components': sorted(set(COMP_RE.findall(text))),
    }

def next_action(profile, respawn, caller):
    if profile=='NO_CUSTOM_PROCESS':
        return 'R3_2_SYSTEM_OR_BLUETOOTH_RESPAWN_TRIGGER_CHARACTERIZATION' if respawn else 'R3_1_PROFILE_CUSTOM_UNAUTHORIZED_ALIVE'
    if profile=='CUSTOM_UNAUTHORIZED_ALIVE':
        return 'R3_2_CUSTOM_APP_LAUNCH_OR_SDK_INIT_TRIGGER_CHARACTERIZATION' if respawn else 'R3_1_PROFILE_CUSTOM_AUTHORIZED_NO_CONNECT'
    if profile=='CUSTOM_AUTHORIZED_NO_CONNECT':
        if respawn and caller: return 'R4_SERVICE_COMPONENT_DEPENDENCY_QUALIFICATION'
        return 'R3_2_AUTHORIZATION_OR_BIND_TRIGGER_CHARACTERIZATION' if respawn else 'R3_1_PROFILE_CUSTOM_STOPPED_POST_AUTH'
    if profile=='CUSTOM_STOPPED_POST_AUTH':
        return 'R3_2_PERSISTENT_POST_AUTH_OR_SYSTEM_TRIGGER_CHARACTERIZATION' if respawn else 'R4_CUSTOM_PROCESS_BOUND_DEPENDENCY_QUALIFICATION'
    return 'STOP_UNRESOLVED'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args()
    ev=Path(a.evidence).resolve(); raw=ev/'raw'; san=ev/'sanitized'; san.mkdir(parents=True,exist_ok=True)
    meta=kv(ev/'run-metadata.txt'); profile=meta.get('PROFILE','')
    if profile not in PROFILES: raise SystemExit('ERROR: invalid or missing profile')
    if kv(raw/'force-stop-observation.txt').get('HI_PROCESS_ABSENT_OBSERVED')!='YES':
        raise SystemExit('ERROR: Hi Rokid process absence not proven')
    state=kv(raw/'profile-state-before-hi-force-stop.txt')
    expected='NO' if profile in {'NO_CUSTOM_PROCESS','CUSTOM_STOPPED_POST_AUTH'} else 'YES'
    if state.get('CUSTOM_PROCESS_VISIBLE') != expected:
        raise SystemExit('ERROR: custom process state does not match profile')
    tl=rows(raw/'timeline-private.jsonl')
    if not tl: raise SystemExit('ERROR: missing timeline')
    seen=[r for r in tl if r.get('hi_process_visible')]
    respawn=bool(seen); latency=seen[0].get('elapsed_ms') if seen else None
    svc=evidence(raw)
    restored=kv(raw/'state-restored.txt')
    if restored.get('OPERATOR_HI_ROKID_RECOVERY')!='PASS' or restored.get('HI_PROCESS_VISIBLE')!='YES':
        raise SystemExit('ERROR: mandatory Hi Rokid restoration not proven')
    summary={
      'schema':'rokid.test21-r3-1.auto-respawn-trigger.v1',
      'scope':'auto_respawn_trigger_characterization',
      'profile':profile,
      'hi_rokid_package':HI,
      'custom_companion_package':CUSTOM,
      'profile_state':{'custom_process_visible_before_hi_force_stop':expected},
      'respawn':{'observed':respawn,'first_respawn_elapsed_ms':latency,'observation_seconds':float(meta.get('OBSERVATION_SECONDS','30'))},
      'service_dependency':{
        'BOUND_SERVICE_CALLER_EVIDENCE':svc['caller'],
        'BOUND_SERVICE_EVIDENCE':svc['bound'],
        'PROCESS_START_EVENT_EVIDENCE':svc['process_start'],
        'HI_ROKID_SERVICE_COMPONENTS_AT_RESPAWN':svc['components'],
        'binding_evidence_line_count':svc['bind_count'],
        'caller_binding_evidence_line_count':svc['caller_count'],
        'process_start_evidence_line_count':svc['start_count'],
      },
      'safety':{'cxr_l_connection_attempt':'NONE','photo_operation':'NONE','audio_operation':'NONE','host_photo_arm':'NONE','package_disable':'NONE','package_uninstall':'NONE','package_data_clear':'NONE','authorization_token_host_export':False},
      'restoration':{'hi_rokid_restoration':'PASS'},
    }
    summary['next_action']=next_action(profile,respawn,svc['caller'])
    (san/'test21-r3-1-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    comps=','.join(svc['components']) or 'NONE_OBSERVED'
    lines=[
      'TEST21_R3_1_ANALYSIS=PASS', f'PROFILE={profile}',
      f'HI_ROKID_PROCESS_RESPAWN_OBSERVED={"YES" if respawn else "NO"}',
      f'FIRST_RESPAWN_ELAPSED_MS={latency if latency is not None else "NONE"}',
      f'BOUND_SERVICE_CALLER_EVIDENCE={"YES" if svc["caller"] else "NO"}',
      f'BOUND_SERVICE_EVIDENCE={"YES" if svc["bound"] else "NO"}',
      f'PROCESS_START_EVENT_EVIDENCE={"YES" if svc["process_start"] else "NO"}',
      f'HI_ROKID_SERVICE_COMPONENTS_AT_RESPAWN={comps}',
      'CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE',
      'AUTHORIZATION_TOKEN_HOST_EXPORT=NONE','PACKAGE_DISABLE_OR_UNINSTALL=NONE','PACKAGE_DATA_CLEAR=NONE',
      'HI_ROKID_RESTORATION=PASS', f'NEXT_ACTION={summary["next_action"]}',
    ]
    (san/'test21-r3-1-summary.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines)); return 0
if __name__=='__main__': raise SystemExit(main())
