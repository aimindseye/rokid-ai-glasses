#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
try:
    from .primitives import sha256_file, read_json
    from .verify_r27_1_2 import _fixture,_zip_member_bytes,_sidecar_valid
    from .retirement_status import summary as retirement_summary
except ImportError:
    try:
        from scripts.research.canonical.primitives import sha256_file, read_json
        from scripts.research.canonical.verify_r27_1_2 import _fixture,_zip_member_bytes,_sidecar_valid
        from scripts.research.canonical.retirement_status import summary as retirement_summary
    except ImportError:
        from primitives import sha256_file, read_json
        from verify_r27_1_2 import _fixture,_zip_member_bytes,_sidecar_valid
        from retirement_status import summary as retirement_summary
TARGET=['r1','r2','r3','r3.3.1','r3.3.2','r3.3.3','r3.3.3.1','r3.3.3.2','r3.3.3.2.1','r3.3.4','r3.3.4.1']

def run_packager(script:Path, profile:dict, evidence:Path, explicit:Path, cwd:Path):
    cmd=[sys.executable,str(script)]
    mode=profile['legacy_cli']
    cmd += ['--evidence',str(evidence)]
    if profile.get('phone_required'): cmd += ['--phone','SYNTHETIC_PHONE']
    if mode=='evidence_output': cmd += ['--output',str(explicit)]
    cp=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=60)
    out=explicit if mode=='evidence_output' else Path(str(evidence)+'-sanitized-summary.zip')
    return cp,out

def verify(repo:Path, archive:Path, baseline_path:Path, output:Path|None=None)->int:
    failures=[]; rows=[]
    profiles=read_json(repo/'scripts/research/canonical/profiles/test21-sanitized-packagers.json')['profiles']
    baseline=json.loads(baseline_path.read_text())
    with zipfile.ZipFile(archive) as az:
        names=set(az.namelist())
        for rev in TARGET:
            p=profiles[rev]; rel=p['legacy_packager']; live=repo/rel
            current=sha256_file(live) if live.is_file() else 'MISSING'
            state_ok=p.get('retirement_state')=='COMPATIBILITY_SHIM' and current==p.get('compatibility_shim_sha256')
            archived_name='historical/'+rel
            archived_ok=archived_name in names and hashlib.sha256(az.read(archived_name)).hexdigest()==p['legacy_sha256']
            with tempfile.TemporaryDirectory(prefix='r2719-') as td:
                base=Path(td); oldev=base/'old'; newev=base/'new'; _fixture(oldev,p,rev); shutil.copytree(oldev,newev)
                oldscript=base/'legacy.py'; oldscript.write_bytes(az.read(archived_name)); oldscript.chmod(0o755)
                cp1,z1=run_packager(oldscript,p,oldev,base/'old.zip',repo)
                cp2,z2=run_packager(live,p,newev,base/'new.zip',repo)
                members_equal=cp1.returncode==0 and cp2.returncode==0 and z1.is_file() and z2.is_file() and _zip_member_bytes(z1)==_zip_member_bytes(z2)
                sidecars= z1.is_file() and z2.is_file() and _sidecar_valid(z1) and _sidecar_valid(z2)
                markers=all(m in cp2.stdout for m in p.get('legacy_pass_markers',[]))
            eq=state_ok and archived_ok and members_equal and sidecars and markers
            if not eq: failures.append('packager:'+rev)
            rows.append({'revision':rev,'archive_identity':'YES' if archived_ok else 'NO','shim_identity':'YES' if state_ok else 'NO','member_content_equal':'YES' if members_equal else 'NO','sidecars_valid':'YES' if sidecars else 'NO','legacy_pass_markers':'YES' if markers else 'NO','equivalent':'YES' if eq else 'NO'})
    contracts=read_json(repo/'scripts/research/canonical/profiles/source-contracts.json')['profiles']; contract_rows=[]
    for p in contracts:
        rev=p['revision']; checker=repo/p['legacy_checker']; cp=subprocess.run([sys.executable,str(checker),'--repo',str(repo)],cwd=repo,text=True,capture_output=True,timeout=60)
        b=baseline.get(rev)
        same=bool(b) and cp.returncode==b['rc'] and cp.stdout==b['stdout']
        lock=checker.is_file() and sha256_file(checker)==p['legacy_source_sha256']
        ok=same and lock
        if not ok: failures.append('contract:'+rev)
        contract_rows.append({'revision':rev,'post_rc':cp.returncode,'stdout_equal':'YES' if same else 'NO','registry_source_lock':'YES' if lock else 'NO','equivalent':'YES' if ok else 'NO'})
    rs=retirement_summary(repo)
    count_ok=rs['retired_compatibility_shim_count']==26 and rs['blocked_inbound_dependency_count']==16 and rs['blocked_output_container_compatibility_count']==0 and rs['blocked_source_lock_count']==0
    if not count_ok: failures.append('retirement_counts')
    summary={'schema':'rokid.r27.1.9.source-contract-packager-decoupling.v1','status':'PASS' if not failures else 'FAIL','newly_retired_test21_packager_count':len(TARGET),'packager_equivalent_count':sum(x['equivalent']=='YES' for x in rows),'source_contract_profile_count':len(contract_rows),'source_contract_stdout_equivalent_count':sum(x['equivalent']=='YES' for x in contract_rows),'retired_compatibility_shim_count':rs['retired_compatibility_shim_count'],'blocked_inbound_dependency_count':rs['blocked_inbound_dependency_count'],'blocked_output_container_compatibility_count':rs['blocked_output_container_compatibility_count'],'blocked_source_lock_count':rs['blocked_source_lock_count'],'repository_path_deletion_count':0,'device_operation':'NONE','failures':failures}
    if output:
        output.mkdir(parents=True,exist_ok=True)
        with (output/'test21-source-contract-packager-equivalence.tsv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys(),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
        with (output/'source-contract-chain-equivalence.tsv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=contract_rows[0].keys(),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(contract_rows)
        (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('R27_1_9_VERIFY='+summary['status'])
    print(f'NEWLY_RETIRED_TEST21_PACKAGER_COUNT={len(TARGET)}')
    print(f'TEST21_PACKAGER_EQUIVALENT_COUNT={summary["packager_equivalent_count"]}')
    print(f'SOURCE_CONTRACT_PROFILE_COUNT={summary["source_contract_profile_count"]}')
    print(f'SOURCE_CONTRACT_STDOUT_EQUIVALENT_COUNT={summary["source_contract_stdout_equivalent_count"]}')
    print(f'RETIRED_COMPATIBILITY_SHIM_COUNT={rs["retired_compatibility_shim_count"]}')
    print(f'BLOCKED_INBOUND_DEPENDENCY_COUNT={rs["blocked_inbound_dependency_count"]}')
    print('REPOSITORY_PATH_DELETION_COUNT=0');print('DEVICE_OPERATION=NONE')
    return 0 if not failures else 1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--archive',required=True);ap.add_argument('--baseline',required=True);ap.add_argument('--output');a=ap.parse_args()
    return verify(Path(a.repo).resolve(),Path(a.archive).resolve(),Path(a.baseline).resolve(),Path(a.output).resolve() if a.output else None)
if __name__=='__main__': raise SystemExit(main())
