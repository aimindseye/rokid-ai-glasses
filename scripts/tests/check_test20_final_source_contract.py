#!/usr/bin/env python3
from pathlib import Path
import argparse,re,sys
P=Path('android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); a=ap.parse_args(); repo=Path(a.repo).expanduser().resolve()
 c=repo/P/'CxrLPhotoController.java'; m=repo/P/'MainActivity.java'; k=repo/P/'Test20R32Contract.java'; g=repo/'android-client/test20r32/build.gradle.kts'
 for p in (c,m,k,g):
  if not p.is_file(): print(f'ERROR: missing {p}',file=sys.stderr); return 1
 ct=c.read_text(errors='ignore'); mt=m.read_text(errors='ignore'); kt=k.read_text(errors='ignore'); gt=g.read_text(errors='ignore')
 errors=[]
 take=len(re.findall(r'\blink\.takePhoto\s*\(',ct)); audio=len(re.findall(r'\.(?:startAudioStream|stopAudioStream)\s*\(',ct+mt))
 if take!=1: errors.append(f'takePhoto call sites={take}, expected 1')
 if audio!=0: errors.append(f'audio operation call sites={audio}, expected 0')
 required=[
  ('strong callback reference','IImageStreamCbk imageStreamCallback'),
  ('preconnect registration','link.setCXRImageCbk(imageStreamCallback)'),
  ('canonical reregistration event','canonical_image_callback_reregistration_result'),
  ('canonical reregistration method','reregisterImageCallbackAfterServiceStatus()'),
  ('same identity check','same_callback_identity'),
  ('two-phase arm','hostArmGranted.compareAndSet(true, false)'),
 ]
 for label,s in required:
  if s not in ct: errors.append(f'missing {label}')
 if 'IMAGE_CALLBACK_LIFECYCLE' not in kt or 'POST_TAKEPHOTO_WATCHDOG_DELAYS_MS' not in kt: errors.append('canonical contract constants missing')
 if 'rokid.test20-final.cxrl-one-shot-photo.v1' not in kt: errors.append('final event schema missing')
 direct_client_l = 'implementation("com.rokid.cxr:client-l:1.0.1")' in gt
 property_client_l = all(s in gt for s in (
  'gradleProperty("rokidCxrLVersion")',
  'implementation("com.rokid.cxr:client-l:$cxrLVersion")',
  'cxrLVersion != "1.0.1"',
 ))
 if not (direct_client_l or property_client_l):
  errors.append('client-l:1.0.1 dependency is not semantically pinned')
 if 'versionName = "1.0-test20-final"' not in gt: errors.append('final app version missing')
 if 'versionCode = 4' not in gt: errors.append('final app versionCode missing')
 forbidden=['\"ARG3_ZERO_DIAGNOSTIC\"','\"STRONG_REF_PRECONNECT\"','\"POSTCONNECT_REREGISTER\"','callbackProfile']
 for s in forbidden:
  if s in ct or s in mt: errors.append(f'diagnostic profile residue: {s}')
 # Require reregistration call to appear after service status success test and before photoReady assignment.
 i=ct.find('if (!reregisterImageCallbackAfterServiceStatus())'); j=ct.find('photoReady = true;')
 if i<0 or j<0 or i>j: errors.append('post-service reregistration is not before photo readiness')
 if errors:
  for e in errors: print('ERROR:',e,file=sys.stderr)
  print('TEST20_FINAL_SOURCE_CONTRACT=FAIL'); return 1
 print('TEST20_FINAL_SOURCE_CONTRACT=PASS')
 print(f'TAKE_PHOTO_SOURCE_CALL_SITES={take}')
 print(f'AUDIO_OPERATION_SOURCE_CALL_SITES={audio}')
 print('CALLBACK_STRONG_REFERENCE=PASS')
 print('POST_SERVICE_STATUS_REREGISTRATION=MANDATORY')
 print('SAME_CALLBACK_IDENTITY_GATE=PASS')
 print('R3_2_1_3_TWO_PHASE_ARMING=PRESERVED')
 print('DIAGNOSTIC_PROFILE_SELECTION=REMOVED')
 print('ARG3_ZERO_DIAGNOSTIC=NOT_IN_CANONICAL_PATH')
 print('CLIENT_L_DEPENDENCY_DECLARATION=' + ('DIRECT_LITERAL_PINNED' if direct_client_l else 'GRADLE_PROPERTY_PINNED'))
 print('CLIENT_L_EFFECTIVE_VERSION=1.0.1')
 return 0
if __name__=='__main__': raise SystemExit(main())
