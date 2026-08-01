#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

PKG='org.aimindseye.rokid.cxrphotoqualification'
EXPECTED_VERSION='1.0-test20-r3.3'
ALLOWED_PROFILES={'STRONG_REF_PRECONNECT','POSTCONNECT_REREGISTER','ARG3_ZERO_DIAGNOSTIC'}
MEDIA_PERMS={'android.permission.CAMERA','android.permission.RECORD_AUDIO'}

def die(msg:str)->int:
    print(f'ERROR: {msg}', file=sys.stderr); return 1

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    repo=Path(a.repo).expanduser().resolve(); out=Path(a.output).expanduser()
    root=repo/'android-client/test20r32'
    if not (repo/'.git').is_dir(): return die(f'not a git repository: {repo}')
    files=list((root/'src/main/java').rglob('*.java'))+list((root/'src/main/java').rglob('*.kt'))
    if not files: return die('test20r32 source files missing')
    texts={p:p.read_text(encoding='utf-8',errors='strict') for p in files}
    joined='\n'.join(texts.values())
    gradle=(root/'build.gradle.kts').read_text(encoding='utf-8')
    manifest=(root/'src/main/AndroidManifest.xml').read_text(encoding='utf-8')
    take_sites=len(re.findall(r'(?<![A-Za-z0-9_])(?:link|cxrLink)\.takePhoto\s*\(',joined))
    audio_sites=len(re.findall(r'\.(?:startAudioStream|stopAudioStream|setCXRAudioCbk)\s*\(',joined))
    req=[
      ('version',f'versionName = "{EXPECTED_VERSION}"' in gradle),
      ('r3213_host_arm','operator_gate_host_command' in joined and 'hostArmGranted.compareAndSet(true, false)' in joined),
      ('strong_callback_field',bool(re.search(r'private\s+IImageStreamCbk\s+imageStreamCallback\s*;',joined))),
      ('preconnect_registration','registration_phase", "PRE_CONNECT"' in joined),
      ('postconnect_reregister','image_callback_reregistration_result' in joined and 'POST_SERVICE_STATUS' in joined),
      ('watchdogs','R3_3_WATCHDOG_DELAYS_MS' in joined and 'callback_path_snapshot' in joined),
      ('callback_dispatch','image_callback_dispatch' in joined),
      ('arg3_zero_profile','ARG3_ZERO_DIAGNOSTIC' in joined and '? 0 : Test20R32Contract.PHOTO_ARG_3' in joined),
      ('no_payload_persist','payload_persistence_enabled", false' in joined),
      ('no_preview','payload_preview_enabled", false' in joined),
      ('single_take_site',take_sites==1),
      ('zero_audio_calls',audio_sites==0),
    ]
    failed=[name for name,ok in req if not ok]
    perms=sorted(set(re.findall(r'android:name="([^"]+)"',manifest)) & MEDIA_PERMS)
    summary={
      'schema':'rokid.test20-r3.3.source-contract.v1','result':'PASS' if not failed else 'FAIL',
      'expected_version':EXPECTED_VERSION,'take_photo_source_call_sites':take_sites,'audio_operation_source_call_sites':audio_sites,
      'declared_manifest_media_permissions':perms,'manifest_permission_interpretation':'ATTEST_ONLY_NOT_EXECUTION_PROOF',
      'profiles':sorted(ALLOWED_PROFILES),'checks':{name:ok for name,ok in req},'failed_checks':failed,
    }
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if failed: return die('source contract failed: '+','.join(failed))
    print('TEST20_R3_3_SOURCE_CONTRACT=PASS')
    print(f'TAKE_PHOTO_SOURCE_CALL_SITES={take_sites}')
    print(f'AUDIO_OPERATION_SOURCE_CALL_SITES={audio_sites}')
    print('CALLBACK_STRONG_REFERENCE=PASS')
    print('POSTCONNECT_REREGISTRATION_PROFILE=AVAILABLE')
    print('ARG3_ZERO_DIAGNOSTIC_PROFILE=AVAILABLE')
    print('R3_2_1_3_TWO_PHASE_ARMING=PRESERVED')
    print('DECLARED_MANIFEST_MEDIA_PERMISSIONS='+(','.join(perms) if perms else 'NONE'))
    print('MANIFEST_PERMISSION_INTERPRETATION=ATTEST_ONLY_NOT_EXECUTION_PROOF')
    return 0
if __name__=='__main__': raise SystemExit(main())
