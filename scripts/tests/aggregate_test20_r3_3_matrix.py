#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ORDER=['STRONG_REF_PRECONNECT','POSTCONNECT_REREGISTER','ARG3_ZERO_DIAGNOSTIC']

def die(m): print('ERROR: '+m,file=sys.stderr); return 1

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--summary',action='append',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
 docs=[]
 try:
  for p in a.summary: docs.append(json.loads(Path(p).read_text()))
 except Exception as e: return die(str(e))
 if any(d.get('schema')!='rokid.test20-r3.3.sanitized-summary.v1' or d.get('mode')!='final' for d in docs): return die('all inputs must be r3.3 final sanitized summaries')
 profiles=[d.get('profile') for d in docs]
 if len(set(profiles))!=len(profiles): return die('duplicate profile summaries')
 for k in ('firmware','package','app_version'):
  if len({d.get(k) for d in docs})!=1: return die(f'{k} differs across runs')
 by={d['profile']:d for d in docs}; result='INCOMPLETE'; nextp='STOP_REVIEW_EVIDENCE'
 classes={p:by[p]['callback_closure']['classification'] for p in by}
 if any(c=='IMAGE_CALLBACK_DELIVERED' for c in classes.values()): result='CALLBACK_PATH_PROVEN'; nextp='STOP_CALLBACK_PATH_PROVEN'
 elif any(c=='IMAGE_ERROR_CALLBACK_DELIVERED' for c in classes.values()): result='ERROR_CALLBACK_PATH_PROVEN'; nextp='STOP_ERROR_CALLBACK_PATH_PROVEN'
 elif all(p in by for p in ORDER) and all(classes[p]=='REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_STABLE' for p in ORDER): result='BOUNDED_NONDELIVERY_REPRODUCED_ACROSS_ALL_PROFILES'; nextp='STOP_ESCALATE_TO_SDK_SERVICE_OR_TRANSPORT_CLOSURE'
 else:
  for p in ORDER:
   if p not in by: nextp=p; break
 out={'schema':'rokid.test20-r3.3.profile-matrix.v1','result':result,'firmware':docs[0]['firmware'],'app_version':docs[0]['app_version'],'profiles_present':profiles,'classifications':classes,'next_profile_or_action':nextp}
 Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print('TEST20_R3_3_MATRIX='+result); print('TEST20_R3_3_MATRIX_NEXT='+nextp); return 0
if __name__=='__main__': raise SystemExit(main())
