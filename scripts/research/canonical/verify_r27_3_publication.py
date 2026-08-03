#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(repo:Path,*cmd): return subprocess.run(cmd,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--allowlist',required=True); ap.add_argument('--output'); a=ap.parse_args()
 repo=Path(a.repo).resolve(); allow=Path(a.allowlist).resolve(); out=Path(a.output).resolve() if a.output else None
 profile=json.loads((repo/'scripts/research/canonical/profiles/r27-publication.json').read_text())
 paths=[x.strip() for x in allow.read_text().splitlines() if x.strip()]; errs=[]
 if len(paths)!=len(set(paths)): errs.append('duplicate_allowlist_path')
 forbidden=set(profile['forbidden_suffixes']); allowed=set(profile['allowed_suffixes'])
 pats={'home':re.compile(r'/(?:Users|home)/[A-Za-z0-9._-]+/'),'device_serial':re.compile(r'\b2C160DLH20007H\b'),'bearer':re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}'),'jwt':re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),'private_key':re.compile(r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY'),'email':re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),'mac':re.compile(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b')}
 manifest=[]
 for rel in paths:
  p=repo/rel
  if not p.is_file(): errs.append('missing:'+rel); continue
  suf=p.suffix.lower()
  if suf in forbidden: errs.append('forbidden_suffix:'+rel)
  if suf not in allowed: errs.append('unapproved_suffix:'+rel)
  if p.stat().st_size>512*1024: errs.append('oversize:'+rel)
  try:text=p.read_text(encoding='utf-8')
  except UnicodeDecodeError: errs.append('non_utf8:'+rel); continue
  for name,rx in pats.items():
   m=rx.search(text)
   if m and not (name=='mac' and m.group(0).upper()=='AA:BB:CC:DD:EE:FF'): errs.append(f'privacy_{name}:{rel}')
  manifest.append({'path':rel,'sha256':sha(p),'size':p.stat().st_size})
 s=run(repo,'scripts/rokid-research','consolidation','status')
 if s.returncode: errs.append('consolidation_status_rc')
 req=['TOTAL_CANONICALIZED_IMPLEMENTATION_COUNT=88','PRESERVE_REGRESSION_ORACLE_COUNT=38','PRESERVE_HISTORICAL_COUNT=4','PRESERVE_DISTINCT_IMPLEMENTATION_FAMILY_COUNT=4','HOST_MULTI_MEMBER_CONSOLIDATION_CANDIDATE_COUNT=0','SOURCE_LOCK_FAILURE_COUNT=0','R27_WHOLE_HISTORY_CONSOLIDATION=COMPLETE','NEXT_DEVICE_TEST_READY=YES']
 for x in req:
  if x not in s.stdout: errs.append('missing_closure:'+x)
 if errs:
  print('R27_3_PUBLICATION_VERIFY=FAIL'); [print('ERROR='+e) for e in errs]; return 1
 print('R27_3_PUBLICATION_VERIFY=PASS'); print(f'PUBLICATION_PATH_COUNT={len(paths)}')
 for x in req: print(x)
 if out:
  out.mkdir(parents=True,exist_ok=True); (out/'public-manifest.json').write_text(json.dumps({'schema':'rokid.r27.3.public-manifest.v1','paths':manifest},indent=2,sort_keys=True)+'\n'); (out/'consolidation-status.txt').write_text(s.stdout)
 return 0
if __name__=='__main__': raise SystemExit(main())
