#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any

EXPECTED_PACKAGE='org.aimindseye.rokid.cxrphotoqualification'
EXPECTED_VERSION='1.0-test20-r3.3'
PROFILES=('STRONG_REF_PRECONNECT','POSTCONNECT_REREGISTER','ARG3_ZERO_DIAGNOSTIC')
FW_SCHEMA='rokid.test20-r3.2.1.firmware-attestation.v1'
OP_SCHEMA='rokid.test20-r3.3.operator-attestation.v1'
MAC_RE=re.compile(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b')
PATH_RE=re.compile(r'/(?:Users|home)/[^/\s]+/')
TOKEN_RE=re.compile(r'(?i)\b(?:authorization|bearer|access[_-]?token|refresh[_-]?token|session[_-]?token)\b\s*[:=]\s*[^\s,}\]]{8,}')
class GateError(RuntimeError): pass

def evtype(e): return str(e.get('event_type','')).strip()
def det(e): return e.get('details') if isinstance(e.get('details'),dict) else {}
def boolish(v):
    if isinstance(v,bool): return v
    if isinstance(v,int) and v in (0,1): return bool(v)
    if isinstance(v,str):
        x=v.strip().lower()
        if x in ('true','yes','1','pass','passed','success','connected'): return True
        if x in ('false','no','0','fail','failed','error','disconnected'): return False
    return None
def intish(v):
    if isinstance(v,bool): return None
    if isinstance(v,int): return v
    if isinstance(v,str) and re.fullmatch(r'[0-9]+',v.strip()): return int(v.strip())
    return None
def load(path:Path):
    if not path.is_file() or path.stat().st_size==0: raise GateError(f'event stream missing/empty: {path}')
    out=[]
    for n,line in enumerate(path.read_text(encoding='utf-8',errors='strict').splitlines(),1):
        if not line.strip(): continue
        try: x=json.loads(line)
        except Exception as e: raise GateError(f'invalid JSONL line {n}: {e}')
        if not isinstance(x,dict): raise GateError(f'line {n} not object')
        out.append(x)
    if not out: raise GateError('no events')
    return out
def matches(events,name): return [e for e in events if evtype(e)==name]
def req(events,name):
    m=matches(events,name)
    if not m: raise GateError(f'required event missing: {name}')
    return m[-1]
def readkv(path:Path):
    if not path.is_file(): raise GateError(f'missing attestation: {path}')
    d={}
    for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1); d[k.strip()]=v.strip()
    return d

def identity(events,firmware,profile):
    run_ids={str(e.get('run_id','')).strip() for e in events if str(e.get('run_id','')).strip()}
    if len(run_ids)!=1: raise GateError(f'exactly one run_id required, got {sorted(run_ids)}')
    started=det(req(events,'run_started'))
    if str(started.get('app_package','')).strip()!=EXPECTED_PACKAGE: raise GateError('unexpected app package')
    if str(started.get('app_version','')).strip()!=EXPECTED_VERSION: raise GateError(f'app version is not {EXPECTED_VERSION}')
    selected=det(req(events,'callback_profile_selected'))
    if str(selected.get('profile','')).strip()!=profile: raise GateError('callback profile event mismatch')
    if boolish(selected.get('one_photo_request_per_run')) is not True: raise GateError('profile event did not prove one request/run')
    fw={str(e.get('firmware_label','')).strip() for e in events if str(e.get('firmware_label','')).strip()}
    if fw and fw!={firmware}: raise GateError(f'firmware mismatch in events: {sorted(fw)}')
    return next(iter(run_ids))

def firmware_attestation(path,fw):
    d=readkv(path)
    for k,v in {'TEST20_R3_2_1_SCHEMA':FW_SCHEMA,'FIRMWARE_LABEL':fw,'OPERATOR_VISIBLE_FIRMWARE':fw,'OPERATOR_EXACT_MATCH':'PASS','OCR_USED':'NO'}.items():
        if d.get(k)!=v: raise GateError(f'firmware attestation {k} mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}',d.get('SCREENSHOT_SHA256','')): raise GateError('bad screenshot sha')
    if (intish(d.get('SCREENSHOT_BYTES')) or 0)<=0: raise GateError('bad screenshot size')
    return d

def photo_count(events):
    vals=[]; result_count=0
    for e in events:
        d=det(e); t=evtype(e)
        if t=='photo_request_result':
            result_count+=1
            v=intish(d.get('request_count'))
            if v is not None: vals.append(v)
        for k in ('photo_request_count','take_photo_request_count','take_photo_count','photo_requests'):
            v=intish(d.get(k))
            if v is not None: vals.append(v)
    return max(vals,default=(1 if result_count else 0)), vals, result_count

def gate_locked(events):
    d=det(req(events,'operator_gate_initialized'))
    if d.get('phase')!='PREREQUISITE_LOCKED' or boolish(d.get('photo_control_enabled')) is not False: raise GateError('operator gate not locked')
    ready=det(req(events,'operator_gate_prerequisite_ready'))
    if boolish(ready.get('photo_control_enabled')) is not False: raise GateError('photo control enabled during prerequisite')
    return True

def callback_registration(events,profile):
    d=det(req(events,'image_callback_registration_result'))
    if boolish(d.get('registration_returned')) is not True: raise GateError('initial callback registration failed')
    if d.get('method')!='setCXRImageCbk(IImageStreamCbk)V': raise GateError('unexpected callback registration method')
    if d.get('registration_phase')!='PRE_CONNECT': raise GateError('initial registration phase not PRE_CONNECT')
    if boolish(d.get('strong_reference_held')) is not True: raise GateError('strong callback reference not proven')
    if boolish(d.get('audio_callback_registered')) is not False: raise GateError('audio callback registered')
    if boolish(d.get('media_request_issued')) is not False: raise GateError('media issued during registration')
    ident=intish(d.get('callback_identity_hash'))
    if ident is None: raise GateError('callback identity missing')
    if profile=='STRONG_REF_PRECONNECT':
        s=det(req(events,'image_callback_reregistration_skipped'))
        if s.get('reason')!='PROFILE_PRECONNECT_ONLY': raise GateError('preconnect profile did not skip re-registration')
        return {'initial':'PASS','reregistration':'SKIPPED_BY_PROFILE','callback_identity_hash':ident}
    r=det(req(events,'image_callback_reregistration_result'))
    if boolish(r.get('registration_returned')) is not True: raise GateError('postconnect re-registration failed')
    if r.get('registration_phase')!='POST_SERVICE_STATUS': raise GateError('wrong re-registration phase')
    if boolish(r.get('same_callback_identity')) is not True: raise GateError('re-registration did not use same callback object')
    if boolish(r.get('strong_reference_held')) is not True: raise GateError('strong ref missing at re-registration')
    if boolish(r.get('media_request_issued')) is not False: raise GateError('media already issued at re-registration')
    return {'initial':'PASS','reregistration':'PASS','callback_identity_hash':ident}

def prerequisite(events,profile):
    a=det(req(events,'authorization_result'))
    if boolish(a.get('token_present')) is not True or boolish(a.get('token_value_logged')) is not False: raise GateError('authorization evidence invalid')
    s=det(req(events,'session_config_result'))
    if boolish(s.get('configured')) is not True: raise GateError('session config failed')
    c=det(req(events,'callback_cxrl_connected')); b=det(req(events,'callback_glass_bt_connected'))
    if boolish(c.get('connected')) is not True: raise GateError('CXR-L not connected')
    if boolish(b.get('connected')) is not True: raise GateError('glass BT not connected')
    ss=det(req(events,'service_status_result'))
    if boolish(ss.get('status_success')) is not True or boolish(ss.get('glass_bt_status')) is not True: raise GateError('service status failed')
    reg=callback_registration(events,profile)
    gate_locked(events)
    count,_,_=photo_count(events)
    if count!=0: raise GateError(f'pre-arm photo count is {count}')
    return {'authorization':'PASS','session':'PASS','callback_registration':reg,'cxrl_connected':'PASS','glass_bt_connected':'PASS','service_status':'PASS','photo_requests_before_arm':0,'operator_gate':'PREREQUISITE_LOCKED'}

def armed(events,profile):
    pre=prerequisite(events,profile)
    h=det(req(events,'operator_gate_host_command')); ar=det(req(events,'operator_gate_arm_result'))
    if not (boolish(h.get('action_match')) and boolish(h.get('run_id_match')) and boolish(h.get('token_match')) and boolish(h.get('granted'))): raise GateError('host arm command invalid')
    if boolish(h.get('token_value_logged')) is not False or boolish(h.get('photo_control_enabled_after_command')) is not True: raise GateError('host arm safety fields invalid')
    if boolish(ar.get('granted')) is not True or boolish(ar.get('host_arm_available')) is not True: raise GateError('controller arm invalid')
    count,_,_=photo_count(events)
    if count!=0: raise GateError(f'photo count before operator tap is {count}')
    pre['operator_gate']='HOST_ARMED_ONE_SHOT'; pre['photo_requests_before_operator_tap']=0
    return pre

def operator(path):
    d=readkv(path)
    required={'TEST20_R3_3_SCHEMA':OP_SCHEMA,'PREREQUISITE_GATE':'PASS','FIRMWARE_EXACT_MATCH':'PASS','HOST_ARM_GATE':'PASS','APK_ARMED_UI_CONFIRMED':'PASS','PHOTO_ARM_GRANTED':'YES','ADDITIONAL_MEDIA_ACTION':'NO','HI_ROKID_RECOVERY':'PASS'}
    for k,v in required.items():
        if d.get(k)!=v: raise GateError(f'operator attestation {k} mismatch')
    return d

def final_gate(events,profile):
    # Re-check immutable prerequisite presence without requiring zero photo count.
    for n in ('authorization_result','session_config_result','image_callback_registration_result','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','operator_gate_host_command','operator_gate_arm_result','operator_gate_capture_dispatch'): req(events,n)
    callback_registration(events,profile)
    cap=det(req(events,'operator_gate_capture_dispatch'))
    if boolish(cap.get('controller_request_accepted')) is not True or boolish(cap.get('photo_control_enabled_after_click')) is not False: raise GateError('one-shot dispatch not accepted/locked')
    count,vals,result_count=photo_count(events)
    if count!=1 or any(v>1 for v in vals): raise GateError(f'expected exactly one request, count={count}, values={vals}')
    pr=det(req(events,'photo_request_result'))
    returned=boolish(pr.get('returned')); err=str(pr.get('error_class','')).strip(); arg3=intish(pr.get('arg_3'))
    expected_arg3=0 if profile=='ARG3_ZERO_DIAGNOSTIC' else 80
    if arg3!=expected_arg3: raise GateError(f'profile {profile} expected arg3={expected_arg3}, observed {arg3}')
    if boolish(pr.get('callback_strong_reference_present')) is not True: raise GateError('callback strong ref missing at takePhoto')
    snapshots=[det(e) for e in matches(events,'callback_path_snapshot')]
    phases=[str(x.get('phase','')) for x in snapshots]
    if 'PRE_TAKEPHOTO' not in phases or 'POST_TAKEPHOTO_RETURN' not in phases: raise GateError('missing pre/post takePhoto snapshots')
    payload=len(matches(events,'image_payload_received')); errors=len(matches(events,'image_error_callback')); dispatches=matches(events,'image_callback_dispatch')
    terminal=det(req(events,'qualification_terminal')); outcome=str(terminal.get('outcome',''))
    if payload>1 or errors>1 or payload+errors>1: raise GateError('more than one terminal image callback observed')
    if returned is False or err:
        cls='SDK_REQUEST_REJECTED_OR_EXCEPTION'; nextp='STOP_FIX_REQUEST_ACCEPTANCE_BEFORE_MORE_MEDIA'
    elif payload==1:
        cls='IMAGE_CALLBACK_DELIVERED'; nextp='STOP_CALLBACK_PATH_PROVEN'
    elif errors==1:
        cls='IMAGE_ERROR_CALLBACK_DELIVERED'; nextp='STOP_ERROR_CALLBACK_PATH_PROVEN'
    else:
        unstable_conn=False; unstable_service=False
        for x in snapshots:
            if boolish(x.get('cxrl_connected')) is False or boolish(x.get('glass_bt_connected')) is False or boolish(x.get('sdk_glass_bt_connected')) is False: unstable_conn=True
            if boolish(x.get('service_version_query_returned')) is False or boolish(x.get('service_version_present')) is False: unstable_service=True
        if unstable_conn:
            cls='REQUEST_ACCEPTED_NO_CALLBACK_CONNECTION_UNSTABLE'; nextp='STOP_REPAIR_CONNECTION_STABILITY_BEFORE_MORE_MEDIA'
        elif unstable_service:
            cls='REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_UNSTABLE'; nextp='STOP_REPAIR_SERVICE_STABILITY_BEFORE_MORE_MEDIA'
        else:
            cls='REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_STABLE'
            if profile=='STRONG_REF_PRECONNECT': nextp='POSTCONNECT_REREGISTER'
            elif profile=='POSTCONNECT_REREGISTER': nextp='ARG3_ZERO_DIAGNOSTIC'
            else: nextp='STOP_BOUNDED_NONDELIVERY_REPRODUCED_ACROSS_DIAGNOSTIC_PROFILES'
    watchdogs=[x for x in snapshots if x.get('phase')=='POST_TAKEPHOTO_WATCHDOG']
    if payload==0 and errors==0 and returned is True:
        if outcome!='PHOTO_CALLBACK_TIMEOUT': raise GateError(f'no callback but terminal outcome is {outcome!r}, expected PHOTO_CALLBACK_TIMEOUT')
        if len(watchdogs)<4: raise GateError(f'no-callback run has insufficient watchdog checkpoints: {len(watchdogs)}')
    audio_events=[evtype(e) for e in events if re.search(r'(?i)(audio.*(?:start|stop|stream)|(?:start|stop).*audio)',evtype(e))]
    if audio_events: raise GateError(f'audio events observed: {audio_events}')
    return {
      'resolved_photo_request_count':count,'reported_photo_counts':vals,'photo_result_event_count':result_count,
      'take_photo_returned':returned,'take_photo_error_class':err,'arg3':arg3,'callback_profile':profile,
      'image_payload_callback_count':payload,'image_error_callback_count':errors,'callback_dispatch_event_count':len(dispatches),
      'watchdog_checkpoint_count':len(watchdogs),'terminal_outcome':outcome,'classification':cls,'next_profile_or_action':nextp,
      'audio_operation':'NONE','one_shot_gate':'PASS'
    }

def write_summary(path,mode,fw,fwkv,run_id,profile,body):
    obj={'schema':'rokid.test20-r3.3.sanitized-summary.v1','mode':mode,'firmware':fw,'package':EXPECTED_PACKAGE,'app_version':EXPECTED_VERSION,'profile':profile,'run_id_sha256':hashlib.sha256(run_id.encode()).hexdigest(),'firmware_attestation':{'operator_exact_match':True,'ocr_used':False,'screenshot_sha256':fwkv['SCREENSHOT_SHA256'],'screenshot_bytes':int(fwkv['SCREENSHOT_BYTES'])},**body}
    txt=json.dumps(obj,indent=2,sort_keys=True)+'\n'
    problems=[]
    if MAC_RE.search(txt): problems.append('MAC')
    if PATH_RE.search(txt): problems.append('HOME_PATH')
    if TOKEN_RE.search(txt): problems.append('TOKEN')
    if problems: raise GateError('privacy gate failed: '+','.join(problems))
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(txt,encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=('prerequisite','armed','final'),required=True); ap.add_argument('--events',required=True); ap.add_argument('--firmware',required=True); ap.add_argument('--firmware-attestation',required=True); ap.add_argument('--operator-attestation'); ap.add_argument('--profile',choices=PROFILES,required=True); ap.add_argument('--summary',required=True); a=ap.parse_args()
    try:
        events=load(Path(a.events)); run_id=identity(events,a.firmware,a.profile); fwkv=firmware_attestation(Path(a.firmware_attestation),a.firmware)
        if a.mode=='prerequisite':
            pre=prerequisite(events,a.profile); write_summary(Path(a.summary),'prerequisite',a.firmware,fwkv,run_id,a.profile,{'control_path_prerequisite':pre,'TEST20_R3_3_PREREQUISITE_GATE':'PASS'}); print('TEST20_R3_3_PREREQUISITE_GATE=PASS'); print('PHOTO_REQUESTS_BEFORE_ARM=0'); return 0
        if a.mode=='armed':
            pre=armed(events,a.profile); write_summary(Path(a.summary),'armed',a.firmware,fwkv,run_id,a.profile,{'control_path_prerequisite':pre,'TEST20_R3_3_ARMED_GATE':'PASS'}); print('TEST20_R3_3_ARMED_GATE=PASS'); print('PHOTO_REQUESTS_BEFORE_OPERATOR_TAP=0'); return 0
        if not a.operator_attestation: raise GateError('--operator-attestation required')
        operator(Path(a.operator_attestation)); result=final_gate(events,a.profile)
        write_summary(Path(a.summary),'final',a.firmware,fwkv,run_id,a.profile,{'callback_closure':result,'TEST20_R3_3_RUN_VALID':'PASS'})
        print('TEST20_R3_3_RUN_VALID=PASS'); print('TEST20_R3_3_ONE_SHOT_BOUNDING=PASS'); print('TEST20_R3_3_CALLBACK_CLOSURE='+result['classification']); print('TEST20_R3_3_NEXT_PROFILE_OR_ACTION='+result['next_profile_or_action']); print('AUDIO_OPERATION=NONE'); return 0
    except GateError as e:
        print('ERROR: '+str(e),file=sys.stderr); print('TEST20_R3_3_RUN_VALID=FAIL',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
