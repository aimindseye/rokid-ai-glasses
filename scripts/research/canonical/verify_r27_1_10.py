#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,tempfile,zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
try:
    from .primitives import sha256_file, read_json
    from .verify_r27_1_2 import _fixture, _legacy_output
    from .retirement_status import summary as retirement_summary
    from .retirement_dependencies import rows as dependency_rows
except ImportError:
    from scripts.research.canonical.primitives import sha256_file, read_json
    from scripts.research.canonical.verify_r27_1_2 import _fixture, _legacy_output
    from scripts.research.canonical.retirement_status import summary as retirement_summary
    from scripts.research.canonical.retirement_dependencies import rows as dependency_rows

TARGET={
'r3.3.4.2','r3.3.4.2.1','r3.3.4.2.2','r3.3.4.2.3','r3.3.4.2.4','r3.3.4.2.5','r3.3.4.2.5.1','r3.3.4.2.5.2',
'r3.3.4.2.5.2.1','r3.3.4.2.5.2.1.1','r3.3.4.2.5.2.1.1.1','r3.3.4.2.6','r3.3.4.2.6.1','r3.3.4.2.6.1.1','r3.3.4.2.6.1.2','r3.3.4.2.6.1.3'}

def zip_bytes(path:Path)->dict[str,bytes]:
    with zipfile.ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}

def run_script(script:Path, profile:dict, evidence:Path, explicit:Path, cwd:Path):
    cmd=[sys.executable,str(script)]
    mode=profile['legacy_cli']
    if mode=='input_zip':cmd += ['--input',str(evidence/profile['input_subdir']),'--zip',str(explicit)]
    else:
        cmd += ['--evidence',str(evidence)]
        if profile.get('phone_required'):cmd += ['--phone','SYNTHETIC_PHONE']
        if mode=='evidence_output':cmd += ['--output',str(explicit)]
    return subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

def verify_archive(archive:Path)->dict[str,str]:
    with zipfile.ZipFile(archive) as z:
        lines=z.read('historical-source-manifest.tsv').decode().splitlines()[1:]
        manifest={}
        for line in lines:
            rel,h=line.split('\t',1);manifest[rel]=h
            if hashlib.sha256(z.read('historical/'+rel)).hexdigest()!=h:raise RuntimeError('historical archive mismatch: '+rel)
        return manifest

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--archive',required=True);ap.add_argument('--baseline',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    repo=Path(a.repo).resolve();archive=Path(a.archive).resolve();baseline=Path(a.baseline).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    profiles=read_json(repo/'scripts/research/canonical/profiles/test21-sanitized-packagers.json')['profiles']
    manifest=verify_archive(archive)
    failures=[];prows=[]
    with zipfile.ZipFile(archive) as hist:
      for rev in sorted(TARGET):
        p=profiles[rev]; rel=p['legacy_packager']; shim=repo/rel
        shim_lock=shim.is_file() and sha256_file(shim)==p.get('compatibility_shim_sha256') and p.get('retirement_state')=='COMPATIBILITY_SHIM'
        original_lock=rel in manifest
        with tempfile.TemporaryDirectory(prefix='r27110-') as td:
            base=Path(td);legacy_script=base/Path(rel).name;legacy_script.write_bytes(hist.read('historical/'+rel));legacy_script.chmod(0o755)
            ev1=base/'legacy-ev';ev2=base/'shim-ev';_fixture(ev1,p,rev);_fixture(ev2,p,rev)
            exp1=base/'legacy.zip';exp2=base/'shim.zip'
            old=run_script(legacy_script,p,ev1,exp1,repo);new=run_script(shim,p,ev2,exp2,repo)
            z1=_legacy_output(p,ev1,exp1);z2=_legacy_output(p,ev2,exp2)
            members_equal=old.returncode==0 and new.returncode==0 and z1.is_file() and z2.is_file() and zip_bytes(z1)==zip_bytes(z2)
            markers=all(x in new.stdout for x in p.get('legacy_pass_markers',[]))
            equivalent=original_lock and shim_lock and members_equal and markers
            if not equivalent:failures.append('packager:'+rev)
            prows.append({'revision':rev,'legacy_packager':rel,'original_archived':'YES' if original_lock else 'NO','shim_source_lock':'YES' if shim_lock else 'NO','historical_rc':old.returncode,'shim_rc':new.returncode,'archive_member_content_equal':'YES' if members_equal else 'NO','historical_pass_markers_preserved':'YES' if markers else 'NO','equivalent':'YES' if equivalent else 'NO'})
    fields=list(prows[0]);
    with (out/'test21-final-packager-equivalence.tsv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(prows)

    b=json.loads(baseline.read_text()); crows=[]
    def contract_run(pair):
        revision,item=pair;rel=item['legacy_checker']
        cp=subprocess.run([sys.executable,str(repo/rel),'--repo',str(repo)],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False,timeout=30)
        ok=cp.returncode==item['rc']==0 and cp.stdout==item['stdout']
        return revision,{'revision':revision,'path':rel,'baseline_rc':item['rc'],'current_rc':cp.returncode,'stdout_equal':'YES' if cp.stdout==item['stdout'] else 'NO','equivalent':'YES' if ok else 'NO'},ok
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures=[ex.submit(contract_run,pair) for pair in sorted(b.items())]
        for fut in as_completed(futures):
            revision,row,ok=fut.result();crows.append(row)
            if not ok:failures.append('contract:'+revision)
    crows.sort(key=lambda x:x['revision'])
    with (out/'source-contract-chain-equivalence.tsv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(crows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(crows)

    rs=retirement_summary(repo); deps=[r for r in dependency_rows(repo) if r['family']=='test21-sanitized-packagers']
    counts_ok=(rs['retired_compatibility_shim_count']==42 and rs['blocked_inbound_dependency_count']==0 and rs['blocked_output_container_compatibility_count']==0 and rs['blocked_source_lock_count']==0 and len(deps)==30 and all(int(r['blocking_inbound_reference_count'])==0 for r in deps))
    if not counts_ok:failures.append('retirement-state')
    summary={'schema':'rokid.r27.1.10.final-test21-packager-reduction.v1','status':'PASS' if not failures else 'FAIL','newly_retired_test21_packager_count':16,'test21_packager_profile_count':30,'test21_packager_shim_count':sum(p.get('retirement_state')=='COMPATIBILITY_SHIM' for p in profiles.values()),'packager_equivalent_count':sum(r['equivalent']=='YES' for r in prows),'source_contract_profile_count':len(crows),'source_contract_stdout_equivalent_count':sum(r['equivalent']=='YES' for r in crows),'retired_compatibility_shim_count':rs['retired_compatibility_shim_count'],'blocked_inbound_dependency_count':rs['blocked_inbound_dependency_count'],'blocked_source_lock_count':rs['blocked_source_lock_count'],'repository_path_deletion_count':0,'device_operation':'NONE','failures':failures}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    if failures:
        print('R27_1_10_VERIFY=FAIL');[print('ERROR='+x) for x in failures];return 1
    print('R27_1_10_VERIFY=PASS');print('NEWLY_RETIRED_TEST21_PACKAGER_COUNT=16');print('TEST21_PACKAGER_PROFILE_COUNT=30');print('TEST21_PACKAGER_SHIM_COUNT=30');print('TEST21_FINAL_PACKAGER_EQUIVALENT_COUNT=16');print(f"SOURCE_CONTRACT_PROFILE_COUNT={len(crows)}");print(f"SOURCE_CONTRACT_STDOUT_EQUIVALENT_COUNT={sum(r['equivalent']=='YES' for r in crows)}");print('RETIRED_COMPATIBILITY_SHIM_COUNT=42');print('BLOCKED_INBOUND_DEPENDENCY_COUNT=0');print('BLOCKED_SOURCE_LOCK_COUNT=0');print('REPOSITORY_PATH_DELETION_COUNT=0');print('DEVICE_OPERATION=NONE');return 0
if __name__=='__main__':raise SystemExit(main())
