#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

try:
    from .source_contract import execute,load_registry,sha256_file
    from .retirement_status import summary as retirement_summary
except ImportError:
    from scripts.research.canonical.source_contract import execute,load_registry,sha256_file
    from scripts.research.canonical.retirement_status import summary as retirement_summary


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',required=True)
    ap.add_argument('--archive',required=True)
    ap.add_argument('--baseline',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    repo=Path(a.repo).resolve(); archive=Path(a.archive).resolve(); baseline_path=Path(a.baseline).resolve(); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    reg=load_registry(); profiles=reg['profiles']; baseline=json.loads(baseline_path.read_text())
    base_by_rev={x['revision']:x for x in baseline['profiles']}
    failures=[]; rows=[]
    if len(profiles)!=29: failures.append(f'profile_count={len(profiles)}')
    if baseline.get('profile_count')!=29: failures.append(f'baseline_profile_count={baseline.get("profile_count")}')
    if not archive.is_file(): failures.append('originals_archive_missing')
    z=zipfile.ZipFile(archive) if archive.is_file() else None
    snapshot_file_total=0; dependency_edge_total=0
    try:
        for p in profiles:
            rev=p['revision']; legacy=p['legacy_checker']; b=base_by_rev.get(rev)
            if b is None:
                failures.append(f'baseline_missing:{rev}'); continue
            oracle_sha=p.get('oracle_source_sha256','')
            archive_ok='NO'
            if z is not None:
                member='historical/'+legacy
                try: archive_ok='YES' if hashlib.sha256(z.read(member)).hexdigest()==oracle_sha else 'NO'
                except KeyError: archive_ok='NO'
            shim=repo/legacy
            shim_ok='YES' if shim.is_file() and sha256_file(shim)==p.get('compatibility_shim_sha256') else 'NO'
            cp=subprocess.run(['python3',str(shim),'--repo',str(repo)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            crc,cout,cerr,_=execute(repo,p['track'],rev)
            baseline_ok=(b['rc']==0 and b['stdout']==p.get('legacy_success_stdout','') and b['stderr']=='')
            equiv=(archive_ok=='YES' and shim_ok=='YES' and baseline_ok and cp.returncode==0 and crc==0 and cp.stdout==b['stdout']==cout and cp.stderr==b['stderr']==cerr)
            if not equiv: failures.append(f'equivalence:{rev}')
            snapshot_file_total+=len(p.get('required_file_sha256',{})); dependency_edge_total+=len(p.get('contract_dependencies',[]))
            rows.append({'revision':rev,'legacy_checker':legacy,'oracle_archived':archive_ok,'shim_source_lock':shim_ok,'baseline_rc':b['rc'],'shim_rc':cp.returncode,'canonical_rc':crc,'stdout_equal':'YES' if cp.stdout==b['stdout']==cout else 'NO','stderr_equal':'YES' if cp.stderr==b['stderr']==cerr else 'NO','snapshot_file_count':len(p.get('required_file_sha256',{})),'dependency_count':len(p.get('contract_dependencies',[])),'equivalent':'YES' if equiv else 'NO'})
    finally:
        if z is not None: z.close()
    engine=(repo/'scripts/research/canonical/source_contract.py').read_text(encoding='utf-8')
    independent=('subprocess' not in engine and 'run_text(' not in engine and 'required_file_sha256' in engine and 'contract_dependencies' in engine)
    if not independent: failures.append('canonical_engine_not_independent')
    rs=retirement_summary(repo)
    expected_counts=(rs['retired_compatibility_shim_count']==71 and rs['not_retirement_ready_count']==38 and rs['preserve_historical_count']==4 and rs['blocked_source_lock_count']==0 and rs['blocked_inbound_dependency_count']==0 and rs['blocked_output_container_compatibility_count']==0)
    if not expected_counts: failures.append('retirement_counts')
    fields=['revision','legacy_checker','oracle_archived','shim_source_lock','baseline_rc','shim_rc','canonical_rc','stdout_equal','stderr_equal','snapshot_file_count','dependency_count','equivalent']
    with (out/'source-contract-snapshot-equivalence.tsv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
    summary={'schema':'rokid.r27.1.11.source-contract-snapshot-reduction.v1','status':'PASS' if not failures else 'FAIL','profile_count':len(profiles),'newly_retired_source_contract_checker_count':29,'source_contract_equivalent_count':sum(r['equivalent']=='YES' for r in rows),'snapshot_file_reference_count':snapshot_file_total,'contract_dependency_edge_count':dependency_edge_total,'independent_snapshot_engine':'YES' if independent else 'NO','retired_compatibility_shim_count':rs['retired_compatibility_shim_count'],'not_retirement_ready_count':rs['not_retirement_ready_count'],'preserve_historical_count':rs['preserve_historical_count'],'blocked_source_lock_count':rs['blocked_source_lock_count'],'repository_path_deletion_count':0,'device_operation':'NONE','failures':failures}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if failures:
        print('R27_1_11_VERIFY=FAIL');[print('ERROR='+x) for x in failures];return 1
    print('R27_1_11_VERIFY=PASS')
    print('TEST21_SOURCE_CONTRACT_PROFILE_COUNT=29')
    print('NEWLY_RETIRED_SOURCE_CONTRACT_CHECKER_COUNT=29')
    print('SOURCE_CONTRACT_SNAPSHOT_EQUIVALENT_COUNT=29')
    print(f'SNAPSHOT_FILE_REFERENCE_COUNT={snapshot_file_total}')
    print(f'CONTRACT_DEPENDENCY_EDGE_COUNT={dependency_edge_total}')
    print('INDEPENDENT_SOURCE_CONTRACT_ENGINE=PASS')
    print('RETIRED_COMPATIBILITY_SHIM_COUNT=71')
    print('NOT_RETIREMENT_READY_COUNT=38')
    print('PRESERVE_HISTORICAL_COUNT=4')
    print('BLOCKED_SOURCE_LOCK_COUNT=0')
    print('REPOSITORY_PATH_DELETION_COUNT=0')
    print('DEVICE_OPERATION=NONE')
    return 0

if __name__=='__main__': raise SystemExit(main())
