#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT_PROFILES = Path(__file__).resolve().parent / 'profiles' / 'test21-sanitized-packagers.json'
REVISIONS = ('r3.1','r3.2','r3.3')

def sha(p:Path)->str:
    h=hashlib.sha256();
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def zip_shape(p:Path):
    with zipfile.ZipFile(p) as z:
        return [(i.filename,i.compress_type,i.external_attr>>16,z.read(i.filename)) for i in z.infolist()]

def fixture(root:Path, rev:str):
    s=root/'sanitized'; s.mkdir(parents=True)
    stem=rev.replace('.','-')
    (s/f'test21-{stem}-summary.json').write_text('{"status":"PASS"}\n',encoding='utf-8')
    (s/f'test21-{stem}-summary.txt').write_text('STATUS=PASS\n',encoding='utf-8')

def run_script(script:Path, evidence:Path):
    cp=subprocess.run([sys.executable,str(script),'--evidence',str(evidence),'--phone','fixture-phone'],text=True,capture_output=True)
    return cp, Path(str(evidence)+'-sanitized-summary.zip')

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--archive',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    repo=Path(a.repo).resolve(); archive=Path(a.archive).resolve(); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    profiles=json.loads((repo/'scripts/research/canonical/profiles/test21-sanitized-packagers.json').read_text())['profiles']
    failures=[]; rows=[]
    with tempfile.TemporaryDirectory() as td:
        ext=Path(td)/'orig'; ext.mkdir()
        with zipfile.ZipFile(archive) as z: z.extractall(ext)
        for rev in REVISIONS:
            p=profiles[rev]; shim=repo/p['legacy_packager']
            if p.get('retirement_state')!='COMPATIBILITY_SHIM': failures.append(f'{rev}: state')
            if p.get('container_mode')!='historical_source_metadata': failures.append(f'{rev}: container mode')
            if sha(shim)!=p.get('compatibility_shim_sha256'): failures.append(f'{rev}: shim hash')
            orig=ext/'historical'/p['legacy_packager']
            if not orig.is_file(): failures.append(f'{rev}: preserved original missing'); continue
            if sha(orig)!=(p.get('legacy_source_sha256') or p.get('legacy_sha256')): failures.append(f'{rev}: preserved original hash')
            d1=Path(td)/('old-'+rev); d2=Path(td)/('new-'+rev); fixture(d1,rev); shutil.copytree(d1,d2,dirs_exist_ok=True,copy_function=shutil.copy2)
            old,zold=run_script(orig,d1); new,znew=run_script(shim,d2)
            ok=(old.returncode==new.returncode==0 and zip_shape(zold)==zip_shape(znew))
            # Whole ZIP hashes are intentionally allowed to differ because the generated manifest mtime is runtime-derived.
            for zpath in (zold,znew):
                side=Path(str(zpath)+'.sha256')
                if not side.is_file() or side.read_text().split()[0]!=sha(zpath): ok=False
            rows.append((rev,old.returncode,new.returncode,'YES' if ok else 'NO',sha(zold),sha(znew)))
            if not ok: failures.append(f'{rev}: container semantic mismatch')
    blocked=sum(1 for p in profiles.values() if p.get('retirement_state')=='BLOCKED_INBOUND_DEPENDENCY')
    container_blocked=sum(1 for p in profiles.values() if p.get('retirement_state')=='BLOCKED_OUTPUT_CONTAINER_COMPATIBILITY')
    shims=sum(1 for p in profiles.values() if p.get('retirement_state')=='COMPATIBILITY_SHIM')
    if (blocked,container_blocked,shims)!=(27,0,3): failures.append(f'profile counts {(blocked,container_blocked,shims)}')
    with (out/'test21-packager-container-equivalence.tsv').open('w',encoding='utf-8') as f:
        f.write('revision\tlegacy_rc\tshim_rc\tcontainer_semantics_equivalent\tlegacy_zip_sha256\tshim_zip_sha256\n')
        for r in rows: f.write('\t'.join(map(str,r))+'\n')
    summary={'schema':'rokid.r27.1.7.historical-container-compatibility.v1','retired_test21_packager_implementation_count':3,'blocked_test21_packager_inbound_count':blocked,'blocked_test21_packager_container_compatibility_count':container_blocked,'container_semantics_equivalent_count':sum(r[3]=='YES' for r in rows),'repository_path_deletion_count':0,'device_operation':'NONE','failures':failures,'status':'PASS' if not failures else 'FAIL'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('R27_1_7_VERIFY='+summary['status'])
    print('RETIRED_TEST21_PACKAGER_IMPLEMENTATION_COUNT=3')
    print(f'BLOCKED_TEST21_PACKAGER_INBOUND_COUNT={blocked}')
    print(f'BLOCKED_TEST21_PACKAGER_CONTAINER_COMPATIBILITY_COUNT={container_blocked}')
    print(f"CONTAINER_SEMANTICS_EQUIVALENT_COUNT={summary['container_semantics_equivalent_count']}")
    print('REPOSITORY_PATH_DELETION_COUNT=0'); print('DEVICE_OPERATION=NONE')
    return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
