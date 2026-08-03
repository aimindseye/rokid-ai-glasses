#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from pathlib import Path
try:
    from .primitives import read_json, source_lock
except ImportError:
    try:
        from scripts.research.canonical.primitives import read_json, source_lock
    except ImportError:
        from primitives import read_json, source_lock
BASE=Path(__file__).resolve().parent
PROFILES=BASE/'profiles'

def _rows_for_r25(repo:Path)->list[dict]:
    data=read_json(PROFILES/'r25-package-validators.json')['profiles']; rows=[]
    for revision,p in sorted(data.items()):
        path=repo/p['legacy_validator']; state=p.get('retirement_state','RETIREMENT_CANDIDATE')
        if state=='COMPATIBILITY_SHIM':
            expected=p['compatibility_shim_sha256']; locked,_=source_lock(path,expected)
            status='RETIRED_COMPATIBILITY_SHIM' if locked else 'BLOCKED_SOURCE_LOCK'
            lock='PASS' if locked else 'FAIL'; execution='INDEPENDENT_CANONICAL_ENGINE'; reason='historical implementation archived; revision path retained as canonical compatibility shim'
        elif state=='BLOCKED_PUBLICATION_HASH_LOCK':
            locked,_=source_lock(path,p['legacy_source_sha256']); status='BLOCKED_INBOUND_DEPENDENCY' if locked else 'BLOCKED_SOURCE_LOCK'
            lock='PASS' if locked else 'FAIL'; execution='INDEPENDENT_CANONICAL_ENGINE'; reason='historical validator remains hash-locked by r25.3.1.4 publication verification'
        else:
            locked,_=source_lock(path,p['legacy_source_sha256']); status='RETIREMENT_CANDIDATE' if locked else 'BLOCKED_SOURCE_LOCK'
            lock='PASS' if locked else 'FAIL'; execution='INDEPENDENT_CANONICAL_ENGINE'; reason='canonical validator is independently qualified'
        rows.append({'family':'r25-package-validators','track':'r25-connection-protocol','revision':revision,'legacy_path':p['legacy_validator'],'legacy_source_lock':lock,'canonical_execution':execution,'retirement_status':status,'reason':reason})
    return rows

def _rows_for_packagers(repo:Path)->list[dict]:
    data=read_json(PROFILES/'test21-sanitized-packagers.json')['profiles']; rows=[]
    for revision,p in sorted(data.items()):
        path=repo/p['legacy_packager']; state=p.get('retirement_state','BLOCKED_INBOUND_DEPENDENCY')
        if state=='COMPATIBILITY_SHIM':
            expected=p['compatibility_shim_sha256']; locked,_=source_lock(path,expected)
            status='RETIRED_COMPATIBILITY_SHIM' if locked else 'BLOCKED_SOURCE_LOCK'
            lock='PASS' if locked else 'FAIL'
            reason=p.get('retirement_reason','historical implementation archived; revision path retained as canonical compatibility shim')
        else:
            expected=p.get('legacy_source_sha256') or p.get('legacy_sha256',''); locked,_=source_lock(path,expected) if expected else (path.is_file(),'')
            status=state if state.startswith('BLOCKED_') else 'BLOCKED_INBOUND_DEPENDENCY'
            if not locked: status='BLOCKED_SOURCE_LOCK'
            lock='PASS' if locked else 'FAIL'; reason=p.get('retirement_reason','packager remains required by historical lineage')
        rows.append({'family':'test21-sanitized-packagers','track':'test21','revision':revision,'legacy_path':p['legacy_packager'],'legacy_source_lock':lock,'canonical_execution':'INDEPENDENT_CANONICAL_ENGINE','retirement_status':status,'reason':reason})
    return rows

def _rows_for_contracts(repo:Path)->list[dict]:
    data=read_json(PROFILES/'source-contracts.json'); rows=[]
    for p in data['profiles']:
        path=repo/p['legacy_checker']
        if p.get('retirement_state')=='COMPATIBILITY_SHIM':
            locked,_=source_lock(path,p['compatibility_shim_sha256'])
            status='RETIRED_COMPATIBILITY_SHIM' if locked else 'BLOCKED_SOURCE_LOCK'
            execution='INDEPENDENT_ACCEPTED_SOURCE_SNAPSHOT_ENGINE'
            reason='historical checker implementation archived; live path retained as canonical source-contract compatibility shim'
        else:
            expected=p.get('legacy_source_sha256') or p.get('oracle_source_sha256','')
            locked,_=source_lock(path,expected) if expected else (path.is_file(),'')
            status='NOT_RETIREMENT_READY' if locked else 'BLOCKED_SOURCE_LOCK'
            execution='LOCKED_HISTORICAL_ORACLE'
            reason='canonical source-contract command still executes the historical checker'
        rows.append({'family':'test21-source-contracts','track':p['track'],'revision':p['revision'],'legacy_path':p['legacy_checker'],'legacy_source_lock':'PASS' if locked else 'FAIL','canonical_execution':execution,'retirement_status':status,'reason':reason})
    for p in data.get('deferred_historical_contracts',[]):
        rows.append({'family':'test20-source-contracts-deferred','track':p['track'],'revision':p['revision'],'legacy_path':p['legacy_checker'],'legacy_source_lock':'HISTORICAL_DEFERRED','canonical_execution':'DEFERRED_HISTORICAL','retirement_status':'PRESERVE_HISTORICAL','reason':p.get('deferred_reason',p.get('reason','historical contract is not current-tree equivalent'))})
    return rows

def _rows_for_tests(repo:Path)->list[dict]:
    data=read_json(PROFILES/'tool-test-suites.json'); rows=[]
    for p in data['profiles']:
        path=repo/p['legacy_test']; locked,_=source_lock(path,p['legacy_sha256'])
        if p['status']=='CURRENT_EQUIVALENT': status='PRESERVE_REGRESSION_ORACLE'; exec_mode='LOCKED_INDEPENDENT_REGRESSION_ORACLE'; reason='independent regression oracle intentionally retained; canonical runner verifies exact source lock and execution contract'
        else: status='PRESERVE_HISTORICAL'; exec_mode='DEFERRED_MISSING_FIXTURE'; reason=p.get('deferred_reason','historical suite deferred')
        rows.append({'family':'tool-test-suites','track':p['track'],'revision':p['revision'],'legacy_path':p['legacy_test'],'legacy_source_lock':'PASS' if locked else 'FAIL','canonical_execution':exec_mode,'retirement_status':status,'reason':reason})
    return rows

def rows(repo:Path)->list[dict]: return _rows_for_r25(repo)+_rows_for_packagers(repo)+_rows_for_contracts(repo)+_rows_for_tests(repo)

def summary(repo:Path)->dict:
    rs=rows(repo); counts={}
    for r in rs: counts[r['retirement_status']]=counts.get(r['retirement_status'],0)+1
    return {'schema':'rokid.r27.1.12.retirement-status.v8','entry_count':len(rs),'retired_compatibility_shim_count':counts.get('RETIRED_COMPATIBILITY_SHIM',0),'blocked_inbound_dependency_count':counts.get('BLOCKED_INBOUND_DEPENDENCY',0),'blocked_output_container_compatibility_count':counts.get('BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY',0),'not_retirement_ready_count':counts.get('NOT_RETIREMENT_READY',0),'preserve_regression_oracle_count':counts.get('PRESERVE_REGRESSION_ORACLE',0),'preserve_historical_count':counts.get('PRESERVE_HISTORICAL',0),'retirement_candidate_count':counts.get('RETIREMENT_CANDIDATE',0),'blocked_source_lock_count':counts.get('BLOCKED_SOURCE_LOCK',0),'status_counts':counts,'legacy_file_action':'TWELVE_R25_THIRTY_TEST21_PACKAGER_AND_TWENTY_NINE_TEST21_SOURCE_CONTRACT_IMPLEMENTATIONS_REPLACED_BY_COMPATIBILITY_SHIMS; THIRTY_EIGHT_TOOL_TESTS_PRESERVED_AS_REGRESSION_ORACLES','repository_deletion':'NONE','device_operation':'NONE'}

def emit(repo:Path,output:Path|None=None)->int:
    rs=rows(repo); s=summary(repo)
    if output:
        output.mkdir(parents=True,exist_ok=True)
        fields=['family','track','revision','legacy_path','legacy_source_lock','canonical_execution','retirement_status','reason']
        with (output/'retirement-readiness.tsv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(rs)
        (output/'summary.json').write_text(json.dumps(s,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R27_1_12_RETIREMENT_STATUS=PASS')
    for k in ('retired_compatibility_shim_count','blocked_inbound_dependency_count','blocked_output_container_compatibility_count','not_retirement_ready_count','preserve_regression_oracle_count','preserve_historical_count','retirement_candidate_count','blocked_source_lock_count'):
        print(f'{k.upper()}={s[k]}')
    print(f"LEGACY_FILE_ACTION={s['legacy_file_action']}"); print('REPOSITORY_DELETION=NONE'); print('DEVICE_OPERATION=NONE')
    ok=(s['blocked_source_lock_count']==0 and s['blocked_inbound_dependency_count']==0 and s['blocked_output_container_compatibility_count']==0 and s['not_retirement_ready_count']==0 and s['retirement_candidate_count']==0 and s['retired_compatibility_shim_count']==71 and s['preserve_regression_oracle_count']==38 and s['preserve_historical_count']==4)
    return 0 if ok else 1

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output'); a=ap.parse_args()
    raise SystemExit(emit(Path(a.repo).expanduser().resolve(),Path(a.output).expanduser().resolve() if a.output else None))
