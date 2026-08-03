#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,subprocess
from pathlib import Path
try:
    from source_contract import execute, load_registry, sha256_file
except ImportError:
    from scripts.research.canonical.source_contract import execute, load_registry, sha256_file

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    repo=Path(a.repo).resolve(); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    reg=load_registry(); profiles=reg['profiles']; deferred=reg.get('deferred_historical_contracts',[])
    rows=[]; failures=0; changed=0
    for p in profiles:
        path=repo/p['legacy_checker']; expected=p.get('compatibility_shim_sha256',p.get('legacy_source_sha256'))
        lock='YES' if path.is_file() and sha256_file(path)==expected else 'NO'
        if lock!='YES': changed+=1
        legacy=subprocess.run(['python3',str(path),'--repo',str(repo)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
        crc,cout,cerr,_=execute(repo,p['track'],p['revision'])
        markers='YES' if all(x in legacy.stdout for x in p.get('expected_pass_markers',[])) else 'NO'
        eq=(lock=='YES' and legacy.returncode==0 and crc==legacy.returncode and cout==legacy.stdout and cerr==legacy.stderr and markers=='YES')
        if not eq: failures+=1
        rows.append({'track':p['track'],'revision':p['revision'],'legacy_checker':p['legacy_checker'],'active_source_lock':lock,'legacy_rc':legacy.returncode,'canonical_rc':crc,'stdout_equal':'YES' if cout==legacy.stdout else 'NO','pass_markers_found':markers,'equivalent':'YES' if eq else 'NO'})
        print(f"EQUIVALENCE {p['track']}:{p['revision']} legacy_rc={legacy.returncode} canonical_rc={crc} equivalent={'YES' if eq else 'NO'}")
    for p in deferred:
        path=repo/p['legacy_checker'];lock='YES' if path.is_file() and sha256_file(path)==p['legacy_source_sha256'] else 'NO'
        rows.append({'track':p['track'],'revision':p['revision'],'legacy_checker':p['legacy_checker'],'active_source_lock':lock,'legacy_rc':'DEFERRED','canonical_rc':'DEFERRED','stdout_equal':'DEFERRED','pass_markers_found':'DEFERRED','equivalent':'DEFERRED_HISTORICAL'})
    fields=['track','revision','legacy_checker','active_source_lock','legacy_rc','canonical_rc','stdout_equal','pass_markers_found','equivalent']
    with (out/'source-contract-equivalence.tsv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
    summary={'schema':'rokid.r27.1.11.source-contract-compatibility-equivalence.v2','status':'PASS' if failures==0 and changed==0 else 'FAIL','applicable_profile_count':len(profiles),'equivalent_count':sum(r['equivalent']=='YES' for r in rows),'deferred_historical_contract_count':len(deferred),'failure_count':failures,'active_checker_source_changed_count':changed,'legacy_checker_action':'COMPATIBILITY_SHIM','repository_deletion':'NONE','device_operation':'NONE'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if summary['status']=='PASS':
        print('R27_1_3_EQUIVALENCE=PASS');print(f'TEST21_SOURCE_CONTRACT_PROFILE_COUNT={len(profiles)}');print(f"TEST21_LEGACY_CANONICAL_EQUIVALENT_COUNT={summary['equivalent_count']}");print(f'DEFERRED_TEST20_HISTORICAL_CONTRACT_COUNT={len(deferred)}');print('ACTIVE_CHECKER_SOURCE_CHANGED_COUNT=0');print('LEGACY_CHECKER_ACTION=COMPATIBILITY_SHIM');print('REPOSITORY_DELETION=NONE');print('DEVICE_OPERATION=NONE');return 0
    print('R27_1_3_EQUIVALENCE=FAIL');return 1
if __name__=='__main__': raise SystemExit(main())
