#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any

SCHEMA="rokid.test20-r3.2.cxrl-one-shot-photo.v1"
EXPECTED_PACKAGE="org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_VERSION="1.0-test20-r3.2"
EXPECTED_VERSION_CODE=1
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
EXPECTED_ARGS=(1920,1080,80)
EXPECTED_SEMANTICS="WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED"
BLUETOOTH_RE=re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
LOCAL_PATH_RE=re.compile(r"/(?:Users|home)/[^/\\s]+")
TOKEN_KEYS={"token","auth_token","authorization_token","token_value"}
RAW_MEDIA_KEYS={"payload","payload_bytes","image_bytes","media_bytes","raw_image"}

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
            if lk in RAW_MEDIA_KEYS: out.append(f'{loc}.{k}: forbidden raw-media key')
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
      'image_callback_registration_enabled':True,
      'service_status_queries_enabled':True,
      'take_photo_invocation_enabled':True,
      'image_payload_persistence_enabled':False,
      'image_preview_enabled':False,
      'audio_stream_invocation_enabled':False,
      'cloud_api_client_present':False,
    }
    for k,v in flags.items():
        if started.get(k) is not v: raise AnalysisError(f'unsafe or missing flag: {k}')
    if int(started.get('max_photo_request_count',-1))!=1: raise AnalysisError('max request count mismatch')
    if tuple(int(started.get(f'photo_arg_{i}',-1)) for i in (1,2,3))!=EXPECTED_ARGS: raise AnalysisError('start args mismatch')
    if started.get('photo_argument_semantics')!=EXPECTED_SEMANTICS: raise AnalysisError('semantics boundary mismatch')
    hi=d(one(events,'hi_rokid_environment'))
    if hi.get('package_name')!='com.rokid.sprite.global.aiapp': raise AnalysisError('Hi Rokid package mismatch')
    if hi.get('version_name')!=EXPECTED_HI_ROKID_VERSION: raise AnalysisError('Hi Rokid version mismatch')
    if hi.get('authorization_resolved') is not True or hi.get('service_resolved') is not True: raise AnalysisError('Hi Rokid surfaces unresolved')
    auth=d(one(events,'authorization_result'))
    if auth.get('token_present') is not True or auth.get('token_value_logged') is not False: raise AnalysisError('authorization gate failed')
    session=d(one(events,'session_config_result'))
    if session.get('configured') is not True or session.get('session_type')!='CUSTOMAPP': raise AnalysisError('session gate failed')
    reg=d(one(events,'image_callback_registration_result'))
    if reg.get('registration_returned') is not True: raise AnalysisError('image callback registration failed')
    if reg.get('audio_callback_registered') is not False or reg.get('media_request_issued') is not False: raise AnalysisError('registration scope failed')
    cx=[e for e in events if e.get('event_type')=='callback_cxrl_connected' and d(e).get('connected') is True]
    bt=[e for e in events if e.get('event_type')=='callback_glass_bt_connected' and d(e).get('connected') is True]
    if not cx or not bt: raise AnalysisError('connection callbacks missing')
    status=d(one(events,'service_status_result'))
    for k in ['service_version_query_returned','service_version_present','service_version_code_query_returned','service_version_code_present','glass_bt_status_query_returned','status_success']:
        if status.get(k) is not True: raise AnalysisError(f'service status gate failed: {k}')
    if status.get('glass_bt_status') is not True or status.get('photo_request_issued') is not False: raise AnalysisError('service status boundary failed')
    ready=d(one(events,'photo_ready'))
    if ready.get('explicit_operator_tap_required') is not True or int(ready.get('max_request_count',-1))!=1: raise AnalysisError('photo ready gate failed')
    if tuple(int(ready.get(f'arg_{i}',-1)) for i in (1,2,3))!=EXPECTED_ARGS: raise AnalysisError('ready args mismatch')
    if ready.get('argument_semantics')!=EXPECTED_SEMANTICS: raise AnalysisError('ready semantics mismatch')
    if ready.get('payload_persistence_enabled') is not False or ready.get('payload_preview_enabled') is not False: raise AnalysisError('ready persistence boundary failed')
    request=d(one(events,'photo_request_result'))
    if request.get('method')!='takePhoto(III)Z': raise AnalysisError('photo method mismatch')
    if int(request.get('request_count',-1))!=1: raise AnalysisError('photo request cardinality failed')
    if tuple(int(request.get(f'arg_{i}',-1)) for i in (1,2,3))!=EXPECTED_ARGS: raise AnalysisError('request args mismatch')
    if request.get('argument_semantics')!=EXPECTED_SEMANTICS: raise AnalysisError('request semantics mismatch')
    if request.get('returned') is not True or str(request.get('error_class',''))!='': raise AnalysisError('takePhoto did not return true')
    if request.get('payload_persistence_enabled') is not False or request.get('payload_preview_enabled') is not False: raise AnalysisError('request persistence boundary failed')
    payload=d(one(events,'image_payload_received'))
    if int(payload.get('callback_count',-1))!=1: raise AnalysisError('image callback cardinality failed')
    if payload.get('payload_present') is not True or int(payload.get('payload_length',0))<=0: raise AnalysisError('empty image payload')
    digest=str(payload.get('payload_digest_sha256_private',''))
    if not re.fullmatch(r'[0-9a-f]{64}',digest): raise AnalysisError('private payload digest missing')
    if payload.get('payload_bytes_logged') is not False or payload.get('payload_persisted') is not False or payload.get('payload_previewed') is not False: raise AnalysisError('payload handling boundary failed')
    if payload.get('valid_nonempty_image') is not True: raise AnalysisError('image validation failed')
    if str(payload.get('format_hint','')) not in {'JPEG','PNG','WEBP','UNKNOWN'}: raise AnalysisError('format hint invalid')
    if int(payload.get('request_to_callback_latency_ms',-1))<0: raise AnalysisError('latency missing')
    one(events,'duplicate_callback_window_armed')
    if any(e.get('event_type')=='image_error_callback' for e in events): raise AnalysisError('image error callback observed')
    terminals=d(one(events,'qualification_terminal'))
    if terminals.get('outcome')!='ONE_SHOT_PHOTO_RECEIVED' or terminals.get('success') is not True: raise AnalysisError('terminal gate failed')
    if int(terminals.get('photo_request_count',-1))!=1 or int(terminals.get('image_payload_callback_count',-1))!=1 or int(terminals.get('image_error_callback_count',-1))!=0: raise AnalysisError('terminal cardinality failed')
    disconnect=d(one(events,'disconnect_result'))
    if disconnect.get('sdk_disconnect_returned') is not True or disconnect.get('manual_unbind_attempted') is not False: raise AnalysisError('disconnect gate failed')
    completed=d(one(events,'run_completed'))
    if completed.get('terminal_success') is not True or int(completed.get('take_photo_request_count',-1))!=1: raise AnalysisError('completion cardinality failed')
    for k in ['test_app_cloud_request','start_audio_stream_invocation','stop_audio_stream_invocation','image_payload_persistence','image_payload_preview','media_upload']:
        if completed.get(k)!='NONE': raise AnalysisError(f'completion safety failed: {k}')
    op=attestation(operator_path)
    if op.get('BOUNDED_TEST_TARGET_ONLY')!='YES': raise AnalysisError('bounded target attestation failed')
    if op.get('ADDITIONAL_MEDIA_ACTION')!='NO': raise AnalysisError('additional media action attestation failed')
    if op.get('HI_ROKID_RECOVERY')!='PASS': raise AnalysisError('Hi Rokid recovery failed')
    version=str(status.get('service_version',''))
    fmt=str(payload.get('format_hint',''))
    mime=str(payload.get('decoded_mime_type',''))
    return {
      'schema':'rokid.test20-r3.2.sanitized-summary.v1',
      'run_id_sha256':hashlib.sha256(str(events[0]['run_id']).encode()).hexdigest(),
      'firmware':firmware,
      'hi_rokid_version':EXPECTED_HI_ROKID_VERSION,
      'cxr_l_coordinate':'com.rokid.cxr:client-l:1.0.1',
      'qualification':{
        'image_callback_registration':True,
        'service_version_sha256':hashlib.sha256(version.encode()).hexdigest(),
        'service_version_code':int(status['service_version_code']),
        'glass_bluetooth_status':True,
        'take_photo_method':'takePhoto(III)Z',
        'request_args':list(EXPECTED_ARGS),
        'argument_semantics_status':EXPECTED_SEMANTICS,
        'request_returned_true':True,
        'photo_request_count':1,
        'image_payload_callback_count':1,
        'image_error_callback_count':0,
        'duplicate_image_callback_count':0,
        'payload_length':int(payload['payload_length']),
        'payload_digest_disposition':'PRIVATE_EVIDENCE_ONLY',
        'format_hint':fmt,
        'decoded_width':int(payload.get('decoded_width',-1)),
        'decoded_height':int(payload.get('decoded_height',-1)),
        'decoded_mime_type':mime,
        'request_to_callback_latency_ms':int(payload['request_to_callback_latency_ms']),
        'clean_disconnect':True,
        'hi_rokid_recovery':True,
        'terminal':'ONE_SHOT_PHOTO_RECEIVED',
      },
      'safety':{
        'bounded_test_target_only':True,
        'image_payload_persistence':'NONE',
        'image_payload_preview':'NONE',
        'media_upload':'NONE',
        'start_audio_stream_invocation':'NONE',
        'stop_audio_stream_invocation':'NONE',
        'cloud_request':'NONE',
      },
      'privacy':{
        'authorization_token_value_present':False,
        'raw_bluetooth_address_present':False,
        'raw_device_serial_present':False,
        'local_user_path_present':False,
        'image_payload_bytes_present':False,
        'payload_digest_published':False,
      },
      'classification':'CXR_L_ONE_SHOT_PHOTO_CONTROL_AND_BOUNDED_IMAGE_CALLBACK_PASS',
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
    jp=out/'test20-r3-2-cxr-l-one-shot-photo.json'
    mp=out/'test20-r3-2-cxr-l-one-shot-photo.md'
    jp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    q=result['qualification']
    mp.write_text(f"""# Test 20 r3.2 CXR-L One-Shot Photo Summary

- Firmware: `{result['firmware']}`
- Hi Rokid: `{result['hi_rokid_version']}`
- SDK: `{result['cxr_l_coordinate']}`
- Method: `{q['take_photo_method']}`
- Exact request arguments: `{q['request_args']}`
- Parameter semantics: `{q['argument_semantics_status']}`
- Request returned true: PASS
- Photo requests / image callbacks / image errors: `1` / `1` / `0`
- Duplicate callbacks: `0`
- Payload length: `{q['payload_length']}` bytes
- Format hint: `{q['format_hint']}`
- Decode-bounds width/height/MIME: `{q['decoded_width']}` / `{q['decoded_height']}` / `{q['decoded_mime_type']}`
- Request-to-callback latency: `{q['request_to_callback_latency_ms']}` ms
- Payload digest: private evidence only
- Payload persisted or previewed: NO
- Audio or cloud operation: NONE
- Clean disconnect: PASS
- Hi Rokid recovery: PASS
- Terminal: `{q['terminal']}`

This result qualifies only one request using the exact argument triplet shown. It does not generalize parameter semantics, image quality, camera performance, or continuous media transport.
""",encoding='utf-8')
    print('TEST20_R3_2_MEDIA_SERVICE_CONNECTION=PASS')
    print('TEST20_R3_2_IMAGE_CALLBACK_REGISTRATION=PASS')
    print('TEST20_R3_2_ONE_SHOT_PHOTO_REQUEST=PASS')
    print('TEST20_R3_2_TAKE_PHOTO_RETURN=PASS')
    print('TEST20_R3_2_IMAGE_CALLBACK=PASS')
    print('TEST20_R3_2_IMAGE_PAYLOAD_NONEMPTY=PASS')
    print('TEST20_R3_2_IMAGE_FORMAT_INSPECTION=PASS')
    print('TEST20_R3_2_EXACTLY_ONE_REQUEST=PASS')
    print('TEST20_R3_2_EXACTLY_ONE_CALLBACK=PASS')
    print('TEST20_R3_2_DUPLICATE_CALLBACK_COUNT=0')
    print('TEST20_R3_2_IMAGE_PAYLOAD_PERSISTED=NO')
    print('TEST20_R3_2_AUDIO_OPERATION=NONE')
    print('TEST20_R3_2_CLOUD_REQUEST=NONE')
    print('TEST20_R3_2_CLEAN_DISCONNECT=PASS')
    print('TEST20_R3_2_HI_ROKID_RECOVERY=PASS')
    print('TEST20_R3_2_PRIVACY_GATE=PASS')
    print('TEST20_R3_2_QUALIFICATION=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
