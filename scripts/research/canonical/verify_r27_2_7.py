#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,subprocess,sys,tempfile
from pathlib import Path
try:
    from primitives import sha256_file, read_json
except ImportError:
    from scripts.research.canonical.primitives import sha256_file, read_json

PROFILE_PATH=Path(__file__).resolve().parent/'profiles/test19-network-analyzers.json'

def write_tsv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(rows)

def run(argv,cwd):
    return subprocess.run(argv,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False,check=False,timeout=30)

def cases():
    return [
      ('test19-r1','r1_local_pass','remote_host,remote_ip\nrouter.local,192.168.1.5\n'),
      ('test19-r1','r1_public_fail','remote_host,remote_ip\napi.example.test,8.8.8.8\n'),
      ('test19-r2','r2_stock_public_pass','package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,router.local,192.168.1.5\ncom.rokid.sprite.global.aiapp,api.example.test,8.8.8.8\n'),
      ('test19-r2','r2_custom_public_fail','package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,api.example.test,8.8.8.8\n'),
      ('test19-r2','r2_missing_app_identity_blocked','remote_host,remote_ip\nrouter.local,192.168.1.5\n'),
    ]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    repo=Path(a.repo).resolve(); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    profiles=read_json(PROFILE_PATH)['profiles']; by={p['revision']:p for p in profiles}
    locks=[]; lock_fail=0
    for rev in ('test19-r1','test19-r2'):
        p=by[rev]; src=repo/p['legacy_path']; actual=sha256_file(src) if src.is_file() else ''; ok=actual==p['legacy_sha256']; lock_fail+=0 if ok else 1
        locks.append({'revision':rev,'legacy_path':p['legacy_path'],'expected_sha256':p['legacy_sha256'],'actual_sha256':actual,'source_lock':'PASS' if ok else 'FAIL'})
    write_tsv(out/'source-locks.tsv',locks,['revision','legacy_path','expected_sha256','actual_sha256','source_lock'])
    if lock_fail:
        print('R27_2_7_EQUIVALENCE=FAIL'); print(f'LEGACY_SOURCE_LOCK_FAILURE_COUNT={lock_fail}'); return 1
    rows=[]
    with tempfile.TemporaryDirectory(prefix='r2727-') as td:
        root=Path(td)
        for rev,name,text in cases():
            case=root/name; case.mkdir(); src=case/'input.csv'; src.write_text(text,encoding='utf-8')
            oldout=case/'legacy.json'; newout=case/'canonical.json'; legacy=by[rev]['legacy_path']
            old=run([sys.executable,str(repo/legacy),'--csv',str(src),'--output',str(oldout)],repo)
            new=run([str(repo/'scripts/rokid-research'),'--repo',str(repo),'network','analyze-csv','--revision',rev,'--csv',str(src),'--output',str(newout)],repo)
            out_equal=oldout.is_file() and newout.is_file() and oldout.read_bytes()==newout.read_bytes()
            equivalent=(old.returncode==new.returncode and old.stdout==new.stdout and old.stderr==new.stderr and out_equal)
            rows.append({'revision':rev,'case':name,'legacy_rc':old.returncode,'canonical_rc':new.returncode,'stdout_equal':'YES' if old.stdout==new.stdout else 'NO','stderr_equal':'YES' if old.stderr==new.stderr else 'NO','output_json_equal':'YES' if out_equal else 'NO','equivalent':'YES' if equivalent else 'NO'})
    write_tsv(out/'analyzer-equivalence.tsv',rows,['revision','case','legacy_rc','canonical_rc','stdout_equal','stderr_equal','output_json_equal','equivalent'])
    failures=sum(r['equivalent']!='YES' for r in rows)
    eq_profiles=sum(all(r['equivalent']=='YES' for r in rows if r['revision']==rev) for rev in ('test19-r1','test19-r2'))
    summary={'schema':'rokid.r27.2.7.test19-network-analyzer-equivalence.v1','status':'PASS' if not failures and eq_profiles==2 else 'FAIL','network_analyzer_profile_count':2,'network_analyzer_equivalent_profile_count':eq_profiles,'behavioral_case_count':len(rows),'behavioral_failure_count':failures,'r1_pass_fail_case_count':2,'r2_pass_fail_blocked_case_count':3,'legacy_source_lock_failure_count':lock_fail,'historical_file_action':'NONE','repository_deletion':'NONE','device_operation':'NONE','privileged_operation':'NONE','network_operation':'NONE'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R27_2_7_EQUIVALENCE='+summary['status']); print('NETWORK_ANALYZER_PROFILE_COUNT=2'); print(f'NETWORK_ANALYZER_EQUIVALENT_PROFILE_COUNT={eq_profiles}'); print(f'BEHAVIORAL_CASE_COUNT={len(rows)}'); print(f'BEHAVIORAL_FAILURE_COUNT={failures}'); print('R1_PASS_FAIL_CASE_COUNT=2'); print('R2_PASS_FAIL_BLOCKED_CASE_COUNT=3'); print(f'LEGACY_SOURCE_LOCK_FAILURE_COUNT={lock_fail}'); print('HISTORICAL_FILE_ACTION=NONE'); print('REPOSITORY_DELETION=NONE'); print('DEVICE_OPERATION=NONE'); print('PRIVILEGED_OPERATION=NONE'); print('NETWORK_OPERATION=NONE')
    return 0 if summary['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
