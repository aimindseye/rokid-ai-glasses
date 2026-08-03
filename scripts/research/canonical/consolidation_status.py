#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
try:
    from primitives import read_json, sha256_file
    from retirement_status import summary as retirement_summary
except ImportError:
    from scripts.research.canonical.primitives import read_json, sha256_file
    from scripts.research.canonical.retirement_status import summary as retirement_summary
BASE=Path(__file__).resolve().parent
MANIFEST=BASE/'profiles/r27-final-consolidation.json'
ANALYZERS=BASE/'profiles/test19-network-analyzers.json'

def evaluate(repo:Path)->tuple[dict,list[dict]]:
    m=read_json(MANIFEST); a=read_json(ANALYZERS)['profiles']; details=[]; failures=0
    for row in a:
        p=repo/row['legacy_path']; actual=sha256_file(p) if p.is_file() else 'MISSING'; expected=row.get('compatibility_shim_sha256','')
        ok=actual==expected; failures += 0 if ok else 1
        details.append({'category':'CANONICALIZED_SHIM','family':'test19-network-analyzers','path':row['legacy_path'],'expected_sha256':expected,'actual_sha256':actual,'status':'PASS' if ok else 'FAIL','disposition':'CANONICALIZED'})
    for fam in m['remaining_distinct_families']:
        for member in fam['members']:
            p=repo/member['path']; actual=sha256_file(p) if p.is_file() else 'MISSING'; ok=actual==member['sha256']; failures += 0 if ok else 1
            details.append({'category':'PRESERVE_DISTINCT','family':fam['family_key'],'path':member['path'],'expected_sha256':member['sha256'],'actual_sha256':actual,'status':'PASS' if ok else 'FAIL','disposition':fam['disposition']})
    retired=retirement_summary(repo)
    retire_ok=(retired['retired_compatibility_shim_count']==71 and retired['preserve_regression_oracle_count']==38 and retired['preserve_historical_count']==4 and retired['blocked_source_lock_count']==0)
    if not retire_ok: failures+=1
    summary={
      'schema':'rokid.r27.2.8.final-consolidation-status.v1',
      'status':'PASS' if failures==0 else 'FAIL',
      'r27_whole_history_consolidation':'COMPLETE' if failures==0 else 'BLOCKED',
      'total_canonicalized_implementation_count':m['canonicalized_implementation_count'],
      'preserve_regression_oracle_count':m['preserve_regression_oracle_count'],
      'preserve_historical_count':m['preserve_historical_count'],
      'preserve_distinct_implementation_family_count':m['preserve_distinct_implementation_family_count'],
      'host_multi_member_consolidation_candidate_count':m['host_multi_member_consolidation_candidate_count'],
      'source_lock_failure_count':failures,
      'repository_path_deletion_count':0,
      'next_device_test_ready':failures==0 and bool(m['next_device_test_ready']),
      'next_device_test':m['next_device_test'],
      'device_operation':'NONE','privileged_operation':'NONE','network_operation':'NONE'
    }
    return summary,details

def emit(repo:Path,output:Path|None=None)->int:
    s,d=evaluate(repo)
    if output:
        output.mkdir(parents=True,exist_ok=True)
        (output/'summary.json').write_text(json.dumps(s,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        fields=['category','family','path','expected_sha256','actual_sha256','status','disposition']
        with (output/'source-locks.tsv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(d)
        m=read_json(MANIFEST)
        with (output/'preserve-distinct-families.tsv').open('w',encoding='utf-8',newline='') as f:
            fields2=['family_key','member_count','normalized_token_similarity','disposition','reason','members']
            w=csv.DictWriter(f,fieldnames=fields2,delimiter='\t',lineterminator='\n'); w.writeheader()
            for x in m['remaining_distinct_families']:
                w.writerow({'family_key':x['family_key'],'member_count':len(x['members']),'normalized_token_similarity':x['normalized_token_similarity'],'disposition':x['disposition'],'reason':x['reason'],'members':'|'.join(y['path'] for y in x['members'])})
    print('R27_2_8_FINAL_STATUS='+s['status'])
    print('TOTAL_CANONICALIZED_IMPLEMENTATION_COUNT='+str(s['total_canonicalized_implementation_count']))
    print('PRESERVE_REGRESSION_ORACLE_COUNT='+str(s['preserve_regression_oracle_count']))
    print('PRESERVE_HISTORICAL_COUNT='+str(s['preserve_historical_count']))
    print('PRESERVE_DISTINCT_IMPLEMENTATION_FAMILY_COUNT='+str(s['preserve_distinct_implementation_family_count']))
    print('HOST_MULTI_MEMBER_CONSOLIDATION_CANDIDATE_COUNT='+str(s['host_multi_member_consolidation_candidate_count']))
    print('SOURCE_LOCK_FAILURE_COUNT='+str(s['source_lock_failure_count']))
    print('REPOSITORY_PATH_DELETION_COUNT=0')
    print('R27_WHOLE_HISTORY_CONSOLIDATION='+s['r27_whole_history_consolidation'])
    print('NEXT_DEVICE_TEST_READY='+('YES' if s['next_device_test_ready'] else 'NO'))
    print('DEVICE_OPERATION=NONE'); print('PRIVILEGED_OPERATION=NONE'); print('NETWORK_OPERATION=NONE')
    return 0 if s['status']=='PASS' else 1
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output'); a=ap.parse_args()
    raise SystemExit(emit(Path(a.repo).expanduser().resolve(),Path(a.output).expanduser().resolve() if a.output else None))
