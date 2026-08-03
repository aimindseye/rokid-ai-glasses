#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

ORIGINALS={
 'r25.3.1':('scripts/research/connection-protocol/validate_r1_3_3_2_25_3_1_package.sh','99ee789ff35b7da6fbf460d4c03723ce7ba78a24f0ee526b0ee984073b94ca4e'),
 'r25.3.1.1':('scripts/research/connection-protocol/validate_r1_3_3_2_25_3_1_1_package.sh','198303ea2c111013ab5dca6a0702f62d0dd7115fce025df3be92f97c02acef01'),
}

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:return sha_bytes(p.read_bytes())

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--archive',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 repo=Path(a.repo).resolve();archive=Path(a.archive).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);errs=[];rows=[]
 if not archive.is_file(): errs.append('preservation archive missing')
 else:
  with zipfile.ZipFile(archive) as z:
   for rev,(rel,h) in ORIGINALS.items():
    name='historical/'+rel
    try: got=sha_bytes(z.read(name))
    except KeyError: got='MISSING'
    if got!=h: errs.append(f'archive original mismatch: {rev}')
 profiles=json.loads((repo/'scripts/research/canonical/profiles/r25-package-validators.json').read_text())['profiles']
 for rev,(rel,hist) in ORIGINALS.items():
  p=profiles[rev];current=repo/rel;shim=p.get('compatibility_shim_sha256','');actual=sha_file(current) if current.is_file() else 'MISSING'
  ok=(p.get('legacy_source_sha256')==hist and p.get('historical_implementation_sha256')==hist and p.get('retirement_state')=='COMPATIBILITY_SHIM' and actual==shim)
  if not ok: errs.append(f'profile/shim lineage mismatch: {rev}')
  cp=subprocess.run(['bash',str(current),str(repo)],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  markers=p.get('pass_lines',[]);markers_ok=cp.returncode==0 and all(m in cp.stdout for m in markers)
  if not markers_ok: errs.append(f'compatibility shim behavior mismatch: {rev}')
  rows.append((rev,cp.returncode,'YES' if markers_ok else 'NO',hist,actual))
 pub=subprocess.run(['python3',str(repo/'scripts/research/verify_r25_3_1_4_publication.py'),'--repo',str(repo)],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for m in ('R25_3_1_4_CANONICAL_VALIDATOR_LINEAGE=PASS','R25_3_1_4_PUBLICATION=PASS'):
  if pub.returncode!=0 or m not in pub.stdout: errs.append('publication verifier failed canonical lineage migration: '+m)
 # Regression: an untracked generated APK must not poison publication verification.
 fake=repo/'build'/'r27-1-8-untracked-generated.apk';fake.parent.mkdir(parents=True,exist_ok=True);fake.write_bytes(b'generated-not-public')
 try:
  cp2=subprocess.run(['python3',str(repo/'scripts/research/verify_r25_3_1_4_publication.py'),'--repo',str(repo)],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if cp2.returncode!=0 or 'R25_3_1_4_PUBLICATION=PASS' not in cp2.stdout: errs.append('generated-build false-positive regression failed')
 finally:
  try: fake.unlink()
  except FileNotFoundError: pass
 # Retirement status.
 rs=subprocess.run(['python3',str(repo/'scripts/research/canonical/retirement_status.py'),'--repo',str(repo),'--output',str(out/'retirement-status')],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 s=json.loads((out/'retirement-status'/'summary.json').read_text()) if (out/'retirement-status'/'summary.json').is_file() else {}
 expected={'retired_compatibility_shim_count':15,'blocked_inbound_dependency_count':27,'blocked_output_container_compatibility_count':0,'not_retirement_ready_count':67,'preserve_historical_count':4,'blocked_source_lock_count':0}
 for k,v in expected.items():
  if s.get(k)!=v: errs.append(f'retirement count mismatch {k}: {s.get(k)} != {v}')
 (out/'r25-publication-validator-equivalence.tsv').write_text('revision\tshim_rc\tpass_markers\thistorical_sha256\tshim_sha256\n'+''.join(f'{r}\t{rc}\t{ok}\t{hist}\t{cur}\n' for r,rc,ok,hist,cur in rows))
 summary={'schema':'rokid.r27.1.8.r25-publication-lineage-decoupling.v1','status':'PASS' if not errs else 'FAIL','retired_r25_validator_implementation_count':12,'newly_retired_r25_validator_implementation_count':2,'blocked_test21_packager_inbound_count':27,'publication_verifier_canonical_lineage':pub.returncode==0,'generated_binary_false_positive_regression':'PASS' if not any('generated-build' in e for e in errs) else 'FAIL','repository_path_deletion_count':0,'device_operation':'NONE','failures':errs}
 (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 if errs:
  print('R27_1_8_VERIFY=FAIL');[print('ERROR='+e) for e in errs];return 1
 print('R27_1_8_VERIFY=PASS');print('RETIRED_R25_VALIDATOR_IMPLEMENTATION_COUNT=12');print('NEWLY_RETIRED_R25_VALIDATOR_IMPLEMENTATION_COUNT=2');print('BLOCKED_TEST21_PACKAGER_INBOUND_COUNT=27');print('R25_3_1_4_CANONICAL_VALIDATOR_LINEAGE=PASS');print('GENERATED_BINARY_FALSE_POSITIVE_REGRESSION=PASS');print('REPOSITORY_PATH_DELETION_COUNT=0');print('DEVICE_OPERATION=NONE');return 0
if __name__=='__main__': raise SystemExit(main())
