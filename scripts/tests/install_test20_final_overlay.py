#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, importlib.util, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
SRC=load('test20_final_src_patch',HERE/'apply_test20_final_source_patch.py')
DOC=load('test20_final_doc_patch',HERE/'apply_test20_final_docs_patch.py')

def atomic_bytes(path:Path,data:bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as h:
            h.write(data); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def run(cmd):
    p=subprocess.run(cmd,text=True)
    return p.returncode

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); a=ap.parse_args()
    repo=Path(a.repo).expanduser().resolve()
    if not (repo/'.git').is_dir(): print(f'ERROR: not git repository: {repo}',file=sys.stderr); return 2

    # Compute every governed edit before the first repository mutation.
    source_paths=[repo/SRC.MAIN_REL,repo/SRC.CONTROLLER_REL,repo/SRC.CONTRACT_REL,repo/SRC.GRADLE_REL]
    doc_paths=[repo/p for p in DOC.FILES]
    for p in source_paths+doc_paths:
        if not p.is_file(): print(f'ERROR: required baseline path missing: {p}',file=sys.stderr); print('REPOSITORY_MUTATION=NONE'); return 1
    try:
        src_orig={p:p.read_text(encoding='utf-8') for p in source_paths}
        src_new={
            repo/SRC.MAIN_REL:SRC.patch_main(src_orig[repo/SRC.MAIN_REL]),
            repo/SRC.CONTROLLER_REL:SRC.patch_controller(src_orig[repo/SRC.CONTROLLER_REL]),
            repo/SRC.CONTRACT_REL:SRC.patch_contract(src_orig[repo/SRC.CONTRACT_REL]),
            repo/SRC.GRADLE_REL:SRC.patch_gradle(src_orig[repo/SRC.GRADLE_REL]),
        }
        doc_orig={p:p.read_text(encoding='utf-8') for p in doc_paths}
        doc_new={p:f(doc_orig[p]) for p,f in zip(doc_paths,DOC.PATCHERS)}
    except Exception as e:
        print(f'ERROR: preflight refused current repository state: {e}',file=sys.stderr); print('REPOSITORY_MUTATION=NONE'); return 1

    updates={p:t.encode('utf-8') for p,t in src_new.items()}
    updates.update({p:t.encode('utf-8') for p,t in doc_new.items()})
    for p in sorted((ROOT/'overlay').rglob('*')):
        if p.is_file(): updates[repo/p.relative_to(ROOT/'overlay')]=p.read_bytes()
    for p in sorted(HERE.glob('*')):
        if p.is_file() and p.suffix in {'.py','.sh'}: updates[repo/'scripts/tests'/p.name]=p.read_bytes()

    # Create the backup directory atomically with a unique suffix. Second-resolution
    # timestamps are useful for operator readability but are not unique enough for
    # immediate idempotent reinstallation or concurrent bounded validation.
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path(tempfile.mkdtemp(
        prefix=f'test20-final-overlay-backup-{stamp}-',
        dir=str(repo/'.git'),
    ))
    existed={}
    try:
        for target in updates:
            existed[target]=target.exists()
            if target.exists():
                b=backup/target.relative_to(repo); b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,b)
        (backup/'new-paths.txt').write_text('\n'.join(str(p.relative_to(repo)) for p,v in existed.items() if not v)+'\n',encoding='utf-8')
        for target,data in updates.items(): atomic_bytes(target,data)

        gates=[
            [sys.executable,str(repo/'scripts/tests/check_test20_final_source_contract.py'),'--repo',str(repo)],
            [sys.executable,str(repo/'scripts/tests/check_test20_final_publication.py'),'--repo',str(repo)],
            [sys.executable,str(repo/'scripts/tests/apply_test20_final_source_patch.py'),'--repo',str(repo),'--check-only'],
            [sys.executable,str(repo/'scripts/tests/apply_test20_final_docs_patch.py'),'--repo',str(repo),'--check-only'],
        ]
        for cmd in gates:
            if run(cmd)!=0: raise RuntimeError('post-install gate failed: '+' '.join(cmd))
    except Exception as e:
        for target,was in existed.items():
            b=backup/target.relative_to(repo)
            try:
                if was and b.is_file():
                    target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(b,target)
                elif not was and target.exists():
                    target.unlink()
            except Exception as re:
                print(f'ROLLBACK_WARNING: {target}: {re}',file=sys.stderr)
        print(f'ERROR: installation failed; governed paths rolled back: {e}',file=sys.stderr)
        print(f'ROLLBACK_BACKUP={backup}')
        return 1

    print('TEST20_FINAL_OVERLAY_INSTALL=PASS')
    print('CANONICAL_IMAGE_CALLBACK_LIFECYCLE=STRONG_REFERENCE_PRECONNECT_PLUS_POST_SERVICE_STATUS_REREGISTRATION')
    print('R3_2_1_3_TWO_PHASE_ARMING=PRESERVED')
    print('MAX_PHOTO_REQUESTS_PER_RUN=1')
    print('ACCEPTED_SANITIZED_SUMMARIES_PUBLISHED=3')
    print('ARG3_ZERO_DIAGNOSTIC=NOT_RUN_NOT_JUSTIFIED')
    print('DEVICE_OPERATION=NONE')
    print('PHOTO_OPERATION=NONE')
    print(f'BACKUP={backup}')
    return 0
if __name__=='__main__': raise SystemExit(main())
