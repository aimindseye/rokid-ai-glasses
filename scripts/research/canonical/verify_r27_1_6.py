#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,io,json,subprocess,zipfile
from pathlib import Path
try:
    from .connection_validator import load_profiles, validate
    from .primitives import sha256_file
    from .retirement_dependencies import rows as dependency_rows
    from .retirement_status import summary as retirement_summary
except ImportError:
    from connection_validator import load_profiles, validate
    from primitives import sha256_file
    from retirement_dependencies import rows as dependency_rows
    from retirement_status import summary as retirement_summary


def verify_archive(archive:Path, profiles:dict)->list[str]:
    failures=[]
    if not archive.is_file(): return [f'missing-preservation-archive:{archive}']
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist())
        if 'historical-validator-manifest.tsv' not in names: return ['archive-manifest-missing']
        rows=list(csv.DictReader(io.StringIO(z.read('historical-validator-manifest.tsv').decode()),delimiter='\t'))
        if len(rows)!=10: failures.append(f'archive-row-count:{len(rows)}!=10')
        for r in rows:
            rel=r['path']; rev=r['revision']; expected=profiles[rev]['legacy_source_sha256']
            if r['sha256']!=expected: failures.append(f'archive-manifest-hash:{rev}')
            arc='historical/'+rel
            if arc not in names: failures.append(f'archive-member-missing:{rel}'); continue
            actual=hashlib.sha256(z.read(arc)).hexdigest()
            if actual!=expected: failures.append(f'archive-member-hash:{rev}')
    return failures


def verify(repo:Path,output:Path,archive:Path|None)->int:
    output.mkdir(parents=True,exist_ok=True); failures=[]; profiles=load_profiles()
    deps=dependency_rows(repo)
    depmap={(r['family'],r['revision']):r for r in deps}
    shim_count=blocked_pub=0
    detail=[]
    for rev,p in sorted(profiles.items()):
        state=p.get('retirement_state')
        path=repo/p['legacy_validator']
        d=depmap[('r25-package-validators',rev)]
        if state=='COMPATIBILITY_SHIM':
            shim_count+=1
            if sha256_file(path)!=p.get('compatibility_shim_sha256'): failures.append(f'shim-hash:{rev}')
            if int(d['inbound_reference_count'])!=0: failures.append(f'shim-inbound-ref:{rev}:{d["inbound_references"]}')
            proc=subprocess.run(['bash',str(path),str(repo)],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
            expected='\n'.join(p.get('pass_lines',[]))+'\n'
            if proc.returncode!=0 or proc.stdout!=expected: failures.append(f'shim-output:{rev}:rc={proc.returncode}')
            if validate(repo,rev,quiet=True)!=0: failures.append(f'canonical-validator:{rev}')
            detail.append({'revision':rev,'state':state,'shim_rc':proc.returncode,'exact_legacy_stdout':'YES' if proc.stdout==expected else 'NO','inbound_reference_count':d['inbound_reference_count']})
        elif state=='BLOCKED_PUBLICATION_HASH_LOCK':
            blocked_pub+=1
            if sha256_file(path)!=p['legacy_source_sha256']: failures.append(f'blocked-original-hash:{rev}')
            if int(d['inbound_reference_count'])<1: failures.append(f'publication-blocker-missing:{rev}')
            detail.append({'revision':rev,'state':state,'shim_rc':'NA','exact_legacy_stdout':'NA','inbound_reference_count':d['inbound_reference_count']})
        else: failures.append(f'unexpected-r25-state:{rev}:{state}')
    if shim_count!=10: failures.append(f'shim-count:{shim_count}')
    if blocked_pub!=2: failures.append(f'blocked-publication-count:{blocked_pub}')
    packdeps=[r for r in deps if r['family']=='test21-sanitized-packagers']
    inbound=sum(r['retirement_state']=='BLOCKED_INBOUND_DEPENDENCY' for r in packdeps)
    container=sum(r['retirement_state']=='BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY' for r in packdeps)
    if inbound!=27: failures.append(f'packager-inbound-count:{inbound}')
    if container!=3: failures.append(f'packager-container-count:{container}')
    for r in packdeps:
        if r['retirement_state']=='BLOCKED_INBOUND_DEPENDENCY' and int(r['inbound_reference_count'])<1: failures.append(f'packager-blocker-missing:{r["revision"]}')
        if r['retirement_state']=='BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY' and int(r['inbound_reference_count'])!=0: failures.append(f'packager-unexpected-ref:{r["revision"]}')
    if archive: failures.extend(verify_archive(archive,profiles))
    s=retirement_summary(repo)
    expected={'retired_compatibility_shim_count':10,'blocked_inbound_dependency_count':29,'blocked_output_container_compatibility_count':3,'not_retirement_ready_count':67,'preserve_historical_count':4,'retirement_candidate_count':0,'blocked_source_lock_count':0}
    for k,v in expected.items():
        if s.get(k)!=v: failures.append(f'{k}:{s.get(k)}!={v}')
    with (output/'r25-validator-shim-verification.tsv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['revision','state','shim_rc','exact_legacy_stdout','inbound_reference_count'],delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(detail)
    with (output/'retirement-dependencies.tsv').open('w',encoding='utf-8',newline='') as f:
        fields=['family','revision','legacy_path','retirement_state','inbound_reference_count','inbound_references']; w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(deps)
    summary={'schema':'rokid.r27.1.6.first-legacy-reduction.v1','status':'PASS' if not failures else 'FAIL','retired_r25_validator_implementation_count':shim_count,'blocked_r25_publication_validator_count':blocked_pub,'blocked_test21_packager_inbound_count':inbound,'blocked_test21_packager_container_compatibility_count':container,'repository_path_deletion_count':0,'historical_preservation_archive_verified':bool(archive and not verify_archive(archive,profiles)),'device_operation':'NONE','failures':failures}
    (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if failures:
        for x in failures: print('FAIL='+x)
        print('R27_1_6_VERIFY=FAIL'); return 1
    print('R27_1_6_VERIFY=PASS'); print('RETIRED_R25_VALIDATOR_IMPLEMENTATION_COUNT=10'); print('BLOCKED_R25_PUBLICATION_VALIDATOR_COUNT=2'); print('BLOCKED_TEST21_PACKAGER_INBOUND_COUNT=27'); print('BLOCKED_TEST21_PACKAGER_CONTAINER_COMPATIBILITY_COUNT=3'); print('REPOSITORY_PATH_DELETION_COUNT=0'); print('DEVICE_OPERATION=NONE'); return 0

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--output',required=True); ap.add_argument('--archive'); a=ap.parse_args()
    raise SystemExit(verify(Path(a.repo).resolve(),Path(a.output).resolve(),Path(a.archive).resolve() if a.archive else None))
