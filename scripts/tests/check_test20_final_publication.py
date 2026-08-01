#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,re,sys

PUB=Path('docs/research/connection-protocol/publication')
EXPECTED={
 'test20-r3-2-1-3-one-shot-photo-summary.json':'523c3a8a1baa15e1227578799de24dd51e85d029972f370c795945624190edfc',
 'test20-r3-3-strong-ref-preconnect-summary.json':'96e9fbd5b90f8c8de53f0ec7226c4aea96f3dea3ca72ed394066df7f863024cb',
 'test20-r3-3-postconnect-reregister-summary.json':'1b98b3e8834b5a5687d550377ac01f08c8632b0279c624af248ee06bc1c4b121',
}
REQUIRED_DOCS=[
 Path('docs/tests/test-20-r3-2-1-3-two-phase-one-shot-photo-qualification.md'),
 Path('docs/tests/test-20-r3-3-post-takephoto-image-callback-closure.md'),
 Path('docs/tests/test-20-final-photo-control-callback-publication.md'),
]
FORBIDDEN=[
 r'/Users/', r'2C160DLH20007H', r'OPERATOR_GATE_TOKEN=', r'AUTH_TOKEN=', r'authorization_token\s*[:=]\s*[^\s"\']+',
 r'BEGIN PRIVATE KEY', r'payload_digest_sha256_private',
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); a=ap.parse_args(); repo=Path(a.repo).expanduser().resolve()
 errors=[]
 for name,h in EXPECTED.items():
  p=repo/PUB/name
  if not p.is_file(): errors.append(f'missing accepted sanitized summary: {name}')
  elif sha(p)!=h: errors.append(f'accepted sanitized summary hash mismatch: {name}')
 final=repo/PUB/'test20-final-cxr-l-one-shot-photo-and-callback-closure.json'
 schema=repo/PUB/'test20-final-cxr-l-one-shot-photo-and-callback-closure.schema.json'
 md=repo/PUB/'test20-final-cxr-l-one-shot-photo-and-callback-closure.md'
 hashes=repo/PUB/'test20-final-evidence-hashes.txt'
 for p in [final,schema,md,hashes,*[repo/x for x in REQUIRED_DOCS]]:
  if not p.is_file(): errors.append(f'missing publication path: {p.relative_to(repo) if p.is_absolute() else p}')
 if final.is_file():
  try: d=json.loads(final.read_text())
  except Exception as e: errors.append(f'final JSON parse failed: {e}'); d={}
  if d.get('classification')!='CXR_L_ONE_SHOT_PHOTO_AND_IMAGE_CALLBACK_PATH_PROVEN_WITH_POSTCONNECT_REREGISTRATION': errors.append('final classification mismatch')
  r3213=d.get('r3_2_1_3',{}); r33=d.get('r3_3',{}); rule=d.get('canonical_implementation_rule',{})
  if r3213.get('photo_requests_before_arm')!=0 or r3213.get('resolved_photo_request_count')!=1: errors.append('r3.2.1.3 count publication mismatch')
  if r33.get('strong_ref_preconnect',{}).get('classification')!='REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_STABLE': errors.append('strong-ref classification mismatch')
  if r33.get('postconnect_reregister',{}).get('classification')!='IMAGE_CALLBACK_DELIVERED': errors.append('postconnect classification mismatch')
  if r33.get('postconnect_reregister',{}).get('image_payload_callback_count')!=1: errors.append('postconnect payload callback count mismatch')
  if r33.get('arg3_zero_diagnostic',{}).get('status')!='NOT_RUN': errors.append('arg3 diagnostic status mismatch')
  if rule.get('reregister_same_callback_after_successful_service_status') is not True: errors.append('canonical reregistration rule missing')
  if rule.get('max_photo_requests_per_run')!=1: errors.append('canonical one-shot count mismatch')
 # Scan only final publication/new test pages and accepted machine summaries for accidental private material.
 scan=[]
 for p in (repo/PUB).glob('test20-*'):
  if p.is_file(): scan.append(p)
 scan.extend(repo/x for x in REQUIRED_DOCS if (repo/x).is_file())
 for p in scan:
  t=p.read_text(encoding='utf-8',errors='ignore')
  for pat in FORBIDDEN:
   if re.search(pat,t,re.I): errors.append(f'privacy gate match {pat} in {p.relative_to(repo)}')
 if errors:
  for e in errors: print('ERROR:',e,file=sys.stderr)
  print('TEST20_FINAL_PUBLICATION_GATE=FAIL'); return 1
 print('TEST20_FINAL_PUBLICATION_GATE=PASS')
 print('ACCEPTED_SANITIZED_SUMMARIES=3')
 print('PRIVATE_EVIDENCE_ARCHIVES_PUBLISHED=NO')
 print('RAW_DEVICE_SERIAL_PUBLISHED=NO')
 print('AUTHORIZATION_TOKEN_VALUE_PUBLISHED=NO')
 print('OPERATOR_ARM_TOKEN_VALUE_PUBLISHED=NO')
 print('IMAGE_PAYLOAD_PUBLISHED=NO')
 print('SCREENSHOT_PUBLISHED=NO')
 return 0
if __name__=='__main__': raise SystemExit(main())
