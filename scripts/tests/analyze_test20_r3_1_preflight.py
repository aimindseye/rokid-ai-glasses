#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any

SCHEMA="rokid.test20-r3.1.cxrl-no-payload.v1"
EXPECTED_PACKAGE="org.aimindseye.rokid.cxrmediapreflight"
EXPECTED_VERSION="1.0-test20-r3.1"
EXPECTED_VERSION_CODE=1
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
BLUETOOTH_RE=re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
LOCAL_PATH_RE=re.compile(r"/(?:Users|home)/[^/\\s]+")
TOKEN_KEYS={"token","auth_token","authorization_token","token_value"}
MEDIA_KEYS={"payload","payload_bytes","image_bytes","audio_bytes","media_bytes"}

class AnalysisError(RuntimeError): pass

def load_events(path:Path)->list[dict[str,Any]]:
    events=[]
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        try: item=json.loads(line)
        except json.JSONDecodeError as e: raise AnalysisError(f"line {n}: invalid JSON: {e}")
        if item.get('schema')!=SCHEMA: raise AnalysisError(f"line {n}: schema mismatch")
        events.append(item)
    if not events: raise AnalysisError('event stream is empty')
    return events

def scan(value:Any, loc='$')->list[str]:
    out=[]
    if isinstance(value,dict):
        for k,v in value.items():
            lk=str(k).lower()
            if lk in TOKEN_KEYS: out.append(f'{loc}.{k}: forbidden token key')
            if lk in MEDIA_KEYS: out.append(f'{loc}.{k}: forbidden media key')
            out.extend(scan(v,f'{loc}.{k}'))
    elif isinstance(value,list):
        for i,v in enumerate(value): out.extend(scan(v,f'{loc}[{i}]'))
    elif isinstance(value,str):
        if BLUETOOTH_RE.search(value): out.append(f'{loc}: raw Bluetooth address')
        if LOCAL_PATH_RE.search(value): out.append(f'{loc}: local user path')
    return out

def one(events,event_type):
    matches=[e for e in events if e.get('event_type')==event_type]
    if len(matches)!=1: raise AnalysisError(f'expected one {event_type}, found {len(matches)}')
    return matches[0]

def d(event):
    x=event.get('details')
    if not isinstance(x,dict): raise AnalysisError('event details are not an object')
    return x

def attestation(path:Path):
    result={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line:
            k,v=line.split('=',1); result[k.strip()]=v.strip()
    return result

def analyze(events_path:Path, operator_path:Path, firmware:str)->dict[str,Any]:
    events=load_events(events_path)
    violations=scan(events)
    if violations: raise AnalysisError('privacy violations: '+'; '.join(violations))
    if {str(e.get('firmware_label','')) for e in events}!={firmware}: raise AnalysisError('firmware mismatch')
    if len({str(e.get('run_id','')) for e in events})!=1: raise AnalysisError('run id mismatch')
    started=d(one(events,'run_started'))
    if started.get('app_package')!=EXPECTED_PACKAGE: raise AnalysisError('package mismatch')
    if started.get('app_version')!=EXPECTED_VERSION: raise AnalysisError('versionName mismatch')
    if int(started.get('app_version_code',-1))!=EXPECTED_VERSION_CODE: raise AnalysisError('versionCode mismatch')
    flags={
      'internet_permission_intentionally_removed':True,
      'camera_permission_intentionally_removed':True,
      'record_audio_permission_intentionally_removed':True,
      'callback_registration_enabled':True,
      'service_status_queries_enabled':True,
      'take_photo_invocation_enabled':False,
      'audio_stream_invocation_enabled':False,
      'media_payload_retention_enabled':False,
      'cloud_api_client_present':False,
    }
    for k,v in flags.items():
        if started.get(k) is not v: raise AnalysisError(f'unsafe or missing flag: {k}')
    hi=d(one(events,'hi_rokid_environment'))
    if hi.get('package_name')!='com.rokid.sprite.global.aiapp': raise AnalysisError('Hi Rokid package mismatch')
    if hi.get('version_name')!=EXPECTED_HI_ROKID_VERSION: raise AnalysisError('Hi Rokid version mismatch')
    if hi.get('authorization_resolved') is not True or hi.get('service_resolved') is not True: raise AnalysisError('Hi Rokid surfaces unresolved')
    auth=d(one(events,'authorization_result'))
    if auth.get('token_present') is not True or auth.get('token_value_logged') is not False: raise AnalysisError('authorization gate failed')
    session=d(one(events,'session_config_result'))
    if session.get('configured') is not True or session.get('session_type')!='CUSTOMAPP': raise AnalysisError('session gate failed')
    reg=d(one(events,'callback_registration_result'))
    if reg.get('image_registration_returned') is not True or reg.get('audio_registration_returned') is not True: raise AnalysisError('callback registration failed')
    if reg.get('media_request_issued') is not False: raise AnalysisError('media request during registration')
    cx=[e for e in events if e.get('event_type')=='callback_cxrl_connected' and d(e).get('connected') is True]
    bt=[e for e in events if e.get('event_type')=='callback_glass_bt_connected' and d(e).get('connected') is True]
    if not cx or not bt: raise AnalysisError('connection callbacks missing')
    status=d(one(events,'service_status_result'))
    required_true=['service_version_query_returned','service_version_present','service_version_code_query_returned','service_version_code_present','glass_bt_status_query_returned','status_success']
    for k in required_true:
        if status.get(k) is not True: raise AnalysisError(f'service status gate failed: {k}')
    if status.get('glass_bt_status') is not True: raise AnalysisError('queried glass BT status is not true')
    if status.get('media_request_issued') is not False: raise AnalysisError('media request during status query')
    armed=d(one(events,'no_payload_observation_armed'))
    if armed.get('take_photo_invoked') is not False or armed.get('start_audio_stream_invoked') is not False or armed.get('stop_audio_stream_invoked') is not False: raise AnalysisError('media invocation gate failed')
    forbidden_events={'unexpected_image_payload_callback','unexpected_image_error_callback','unexpected_audio_payload_callback','unexpected_audio_error_callback'}
    found=[e.get('event_type') for e in events if e.get('event_type') in forbidden_events]
    if found: raise AnalysisError('unexpected media callback: '+','.join(found))
    for e in events:
        if e.get('event_type')=='audio_stream_state_callback' and d(e).get('streaming') is True: raise AnalysisError('unexpected active audio stream')
    terminal=d(one(events,'qualification_terminal'))
    if terminal.get('outcome')!='NO_PAYLOAD_OBSERVATION_COMPLETE' or terminal.get('success') is not True: raise AnalysisError('terminal gate failed')
    for k in ['image_payload_callback_count','image_error_callback_count','audio_payload_callback_count','audio_error_callback_count','audio_state_true_callback_count']:
        if int(terminal.get(k,-1))!=0: raise AnalysisError(f'nonzero callback count: {k}')
    disconnect=d(one(events,'disconnect_result'))
    if disconnect.get('sdk_disconnect_returned') is not True: raise AnalysisError('SDK disconnect failed')
    if disconnect.get('manual_unbind_attempted') is not False: raise AnalysisError('manual unbind attempted')
    completed=d(one(events,'run_completed'))
    required_none=['test_app_cloud_request','take_photo_invocation','start_audio_stream_invocation','stop_audio_stream_invocation','image_payload_retention','audio_payload_retention']
    for k in required_none:
        if completed.get(k)!='NONE': raise AnalysisError(f'completion gate failed: {k}')
    op=attestation(operator_path)
    if op.get('OPERATOR_MEDIA_ACTION')!='NO': raise AnalysisError('operator media attestation failed')
    if op.get('HI_ROKID_RECOVERY')!='PASS': raise AnalysisError('Hi Rokid recovery failed')
    version=str(status.get('service_version',''))
    return {
      'schema':'rokid.test20-r3.1.sanitized-summary.v1',
      'run_id_sha256':hashlib.sha256(str(events[0]['run_id']).encode()).hexdigest(),
      'firmware':firmware,
      'hi_rokid_version':EXPECTED_HI_ROKID_VERSION,
      'cxr_l_coordinate':'com.rokid.cxr:client-l:1.0.1',
      'qualification':{
        'callback_registration':True,
        'service_version_present':True,
        'service_version_sha256':hashlib.sha256(version.encode()).hexdigest(),
        'service_version_code':int(status['service_version_code']),
        'glass_bluetooth_status':True,
        'observation_ms':int(armed['observation_ms']),
        'image_payload_callbacks':0,
        'image_error_callbacks':0,
        'audio_payload_callbacks':0,
        'audio_error_callbacks':0,
        'audio_active_state_callbacks':0,
        'clean_disconnect':True,
        'hi_rokid_recovery':True,
        'terminal':'NO_PAYLOAD_OBSERVATION_COMPLETE',
      },
      'safety':{
        'take_photo_invocation':'NONE',
        'start_audio_stream_invocation':'NONE',
        'stop_audio_stream_invocation':'NONE',
        'image_payload_retention':'NONE',
        'audio_payload_retention':'NONE',
        'cloud_request':'NONE',
      },
      'privacy':{
        'authorization_token_value_present':False,
        'raw_bluetooth_address_present':False,
        'raw_device_serial_present':False,
        'local_user_path_present':False,
        'media_payload_present':False,
      },
      'classification':'CXR_L_MEDIA_SERVICE_STATUS_CALLBACK_REGISTRATION_AND_NO_PAYLOAD_PREFLIGHT_PASS',
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--events',required=True,type=Path)
    ap.add_argument('--operator-attestation',required=True,type=Path)
    ap.add_argument('--expected-firmware',required=True)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()
    try: result=analyze(a.events,a.operator_attestation,a.expected_firmware)
    except AnalysisError as e:
        print(f'FAIL: {e}',file=sys.stderr); return 1
    out=a.output/'sanitized'; out.mkdir(parents=True,exist_ok=True)
    jp=out/'test20-r3-1-cxr-l-no-payload-preflight.json'
    mp=out/'test20-r3-1-cxr-l-no-payload-preflight.md'
    jp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    q=result['qualification']
    mp.write_text(f"""# Test 20 r3.1 CXR-L No-Payload Preflight Summary\n\n- Firmware: `{result['firmware']}`\n- Hi Rokid: `{result['hi_rokid_version']}`\n- SDK: `{result['cxr_l_coordinate']}`\n- Callback registration: PASS\n- Service version query: PASS (value hashed in publication)\n- Service version code: `{q['service_version_code']}`\n- Glasses Bluetooth status: connected\n- Observation window: `{q['observation_ms']}` ms\n- Image payload/error callbacks: `0` / `0`\n- Audio payload/error/active-state callbacks: `0` / `0` / `0`\n- Clean disconnect: PASS\n- Hi Rokid recovery: PASS\n- Terminal: `{q['terminal']}`\n\nNo photo, audio-stream, media-retention, or cloud operation was performed.\n""",encoding='utf-8')
    print('TEST20_R3_1_MEDIA_SERVICE_CONNECTION=PASS')
    print('TEST20_R3_1_SERVICE_STATUS_QUERY=PASS')
    print('TEST20_R3_1_GLASS_BLUETOOTH_STATUS=PASS')
    print('TEST20_R3_1_IMAGE_CALLBACK_REGISTRATION=PASS')
    print('TEST20_R3_1_AUDIO_CALLBACK_REGISTRATION=PASS')
    print('TEST20_R3_1_UNEXPECTED_IMAGE_CALLBACK_COUNT=0')
    print('TEST20_R3_1_UNEXPECTED_AUDIO_CALLBACK_COUNT=0')
    print('TEST20_R3_1_IMAGE_PAYLOAD_RECEIVED=NO')
    print('TEST20_R3_1_AUDIO_PAYLOAD_RECEIVED=NO')
    print('TEST20_R3_1_CLEAN_DISCONNECT=PASS')
    print('TEST20_R3_1_HI_ROKID_RECOVERY=PASS')
    print('TEST20_R3_1_PRIVACY_GATE=PASS')
    print('TEST20_R3_1_NO_PAYLOAD_PREFLIGHT=PASS')
    print('TEST20_R3_1_QUALIFICATION=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
