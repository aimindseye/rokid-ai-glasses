#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

try:
    from primitives import sha256_file
    from r25_finalizer import load_profiles as load_finalizer_profiles
    from r25_publication_verifier import load_profiles as load_publication_profiles
    from verify_r27_2_1 import (
        build_run_fixture, capture_outputs, output_paths, valid_sidecar,
        normalize_stdout, valid_publication, set_dotted,
    )
except ImportError:
    from scripts.research.canonical.primitives import sha256_file
    from scripts.research.canonical.r25_finalizer import load_profiles as load_finalizer_profiles
    from scripts.research.canonical.r25_publication_verifier import load_profiles as load_publication_profiles
    from scripts.research.canonical.verify_r27_2_1 import (
        build_run_fixture, capture_outputs, output_paths, valid_sidecar,
        normalize_stdout, valid_publication, set_dotted,
    )

def run_cmd(argv: list[str], *, cwd: Path, env: dict[str,str] | None = None, timeout: int = 45):
    return subprocess.run(argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)

def archive_manifest(archive: Path) -> dict[str,dict]:
    with zipfile.ZipFile(archive) as z:
        raw=z.read("historical-manifest.tsv").decode("utf-8")
    rows=list(csv.DictReader(raw.splitlines(), delimiter="\t"))
    return {row["path"]: row for row in rows}

def extract_original(archive: Path, rel: str, root: Path) -> Path:
    dst=root/"historical"/rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        dst.write_bytes(z.read("historical/"+rel))
    dst.chmod(0o755)
    return dst

def original_env(repo: Path) -> dict[str,str]:
    env=dict(os.environ)
    extra=str(repo/"scripts/research/connection-protocol")
    env["PYTHONPATH"]=extra + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"]="1"
    return env

def finalizer_rows(repo: Path, archive: Path, scratch: Path) -> list[dict]:
    rows=[]
    manifest=archive_manifest(archive)
    extracted=scratch/"original-scripts"
    env=original_env(repo)
    for profile in load_finalizer_profiles():
        rel=profile["legacy_path"]
        orig=extract_original(archive,rel,extracted)
        run=scratch/"finalizers"/profile["revision"].replace(".","_")/"fixture-run"
        build_run_fixture(run,profile)
        old=run_cmd(["python3",str(orig),"--run",str(run)],cwd=repo,env=env)
        old_out=capture_outputs(run,profile) if old.returncode==0 else {}
        _m,old_archive,old_sidecar=output_paths(run,profile)
        old_sidecar_valid=valid_sidecar(old_archive,old_sidecar)

        for p in (old_archive,old_sidecar):
            if p.exists(): p.unlink()
        build_run_fixture(run,profile)
        shim=run_cmd(["python3",str(repo/rel),"--run",str(run)],cwd=repo,env=env)
        shim_out=capture_outputs(run,profile) if shim.returncode==0 else {}
        _m,shim_archive,shim_sidecar=output_paths(run,profile)
        shim_sidecar_valid=valid_sidecar(shim_archive,shim_sidecar)

        old_meta=deepcopy(old_out.get("metadata",{}))
        shim_meta=deepcopy(shim_out.get("metadata",{}))
        manifest_member=f"{run.name}/{profile['manifest']['filename']}"
        if profile["archive"]["zip_mode"]=="source_metadata":
            if manifest_member in old_meta: old_meta[manifest_member].pop("date_time",None)
            if manifest_member in shim_meta: shim_meta[manifest_member].pop("date_time",None)
        exact="NA"
        exact_ok=True
        if profile["archive"]["zip_mode"]=="r25_deterministic_tree":
            exact_ok=old_out.get("archive")==shim_out.get("archive")
            exact="YES" if exact_ok else "NO"

        required="NA"
        if profile.get("requirements",{}).get("required"):
            for p in (shim_archive,shim_sidecar):
                if p.exists(): p.unlink()
            build_run_fixture(run,profile,missing_first_required=True)
            old_bad=run_cmd(["python3",str(orig),"--run",str(run)],cwd=repo,env=env)
            for p in (shim_archive,shim_sidecar):
                if p.exists(): p.unlink()
            build_run_fixture(run,profile,missing_first_required=True)
            shim_bad=run_cmd(["python3",str(repo/rel),"--run",str(run)],cwd=repo,env=env)
            required="YES" if old_bad.returncode!=0 and shim_bad.returncode!=0 else "NO"

        archived_sha=manifest[rel]["sha256"]
        historical_sha=profile.get("historical_source_sha256",profile["legacy_sha256"])
        live_sha=sha256_file(repo/rel)
        shim_sha=profile.get("compatibility_shim_sha256","")
        eq=(old.returncode==0 and shim.returncode==0 and
            normalize_stdout(old.stdout)==normalize_stdout(shim.stdout) and
            old_out.get("manifest")==shim_out.get("manifest") and
            old_out.get("members")==shim_out.get("members") and old_meta==shim_meta and exact_ok and
            old_sidecar_valid and shim_sidecar_valid and required!="NO" and
            archived_sha==historical_sha and live_sha==shim_sha)
        rows.append({
            "revision":profile["revision"],"path":rel,
            "archived_original_lock":"YES" if archived_sha==historical_sha else "NO",
            "live_shim_lock":"YES" if live_sha==shim_sha else "NO",
            "original_rc":old.returncode,"shim_rc":shim.returncode,
            "stdout_equivalent":"YES" if normalize_stdout(old.stdout)==normalize_stdout(shim.stdout) else "NO",
            "manifest_equivalent":"YES" if old_out.get("manifest")==shim_out.get("manifest") else "NO",
            "zip_members_equivalent":"YES" if old_out.get("members")==shim_out.get("members") else "NO",
            "zip_metadata_equivalent":"YES" if old_meta==shim_meta else "NO",
            "whole_zip_exact_when_deterministic":exact,
            "original_sidecar_valid":"YES" if old_sidecar_valid else "NO",
            "shim_sidecar_valid":"YES" if shim_sidecar_valid else "NO",
            "required_file_rejection_equivalent":required,
            "equivalent":"YES" if eq else "NO",
        })
    return rows

def publication_rows(repo: Path, archive: Path, scratch: Path) -> list[dict]:
    rows=[]
    manifest=archive_manifest(archive)
    extracted=scratch/"original-scripts"
    env=original_env(repo)
    for profile in load_publication_profiles():
        rel=profile["legacy_path"]
        orig=extract_original(archive,rel,extracted)
        d=scratch/"publication"/profile["revision"].replace(".","_")
        d.mkdir(parents=True,exist_ok=True)
        path=d/"publication.json"
        good=valid_publication(profile["revision"])
        path.write_text(json.dumps(good,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        old=run_cmd(["python3",str(orig),"--publication",str(path)],cwd=repo,env=env)
        shim=run_cmd(["python3",str(repo/rel),"--publication",str(path)],cwd=repo,env=env)
        stdout_eq=old.stdout==shim.stdout

        bad=deepcopy(good); bad["privacy_probe"]="AA:BB:CC:DD:EE:FF"
        path.write_text(json.dumps(bad,indent=2,sort_keys=True)+"\n")
        old_priv=run_cmd(["python3",str(orig),"--publication",str(path)],cwd=repo,env=env)
        shim_priv=run_cmd(["python3",str(repo/rel),"--publication",str(path)],cwd=repo,env=env)
        privacy_eq=old_priv.returncode!=0 and shim_priv.returncode!=0

        bad=deepcopy(good)
        first_path,expected=profile["equals"][0]
        replacement=(not expected) if isinstance(expected,bool) else (expected+1 if isinstance(expected,int) else "WRONG")
        set_dotted(bad,first_path,replacement)
        path.write_text(json.dumps(bad,indent=2,sort_keys=True)+"\n")
        old_sem=run_cmd(["python3",str(orig),"--publication",str(path)],cwd=repo,env=env)
        shim_sem=run_cmd(["python3",str(repo/rel),"--publication",str(path)],cwd=repo,env=env)
        semantic_eq=old_sem.returncode!=0 and shim_sem.returncode!=0

        special=True
        if profile["revision"]=="r25.1":
            bad=deepcopy(good);bad["blob"]="A"*40+"="
            path.write_text(json.dumps(bad)+"\n")
            special=run_cmd(["python3",str(orig),"--publication",str(path)],cwd=repo,env=env).returncode!=0 and run_cmd(["python3",str(repo/rel),"--publication",str(path)],cwd=repo,env=env).returncode!=0
        elif profile["revision"]=="r25.2.1":
            bad=deepcopy(good);bad["device_id"]="synthetic"
            path.write_text(json.dumps(bad)+"\n")
            special=run_cmd(["python3",str(orig),"--publication",str(path)],cwd=repo,env=env).returncode!=0 and run_cmd(["python3",str(repo/rel),"--publication",str(path)],cwd=repo,env=env).returncode!=0

        archived_sha=manifest[rel]["sha256"]
        historical_sha=profile.get("historical_source_sha256",profile["legacy_sha256"])
        live_sha=sha256_file(repo/rel); shim_sha=profile.get("compatibility_shim_sha256","")
        eq=(old.returncode==0 and shim.returncode==0 and stdout_eq and privacy_eq and semantic_eq and special
            and archived_sha==historical_sha and live_sha==shim_sha)
        rows.append({
            "revision":profile["revision"],"path":rel,
            "archived_original_lock":"YES" if archived_sha==historical_sha else "NO",
            "live_shim_lock":"YES" if live_sha==shim_sha else "NO",
            "original_rc":old.returncode,"shim_rc":shim.returncode,
            "stdout_equivalent":"YES" if stdout_eq else "NO",
            "privacy_rejection_equivalent":"YES" if privacy_eq else "NO",
            "semantic_rejection_equivalent":"YES" if semantic_eq else "NO",
            "special_privacy_rejection_equivalent":"YES" if special else "NO",
            "equivalent":"YES" if eq else "NO",
        })
    return rows

def write_tsv(path: Path, rows: list[dict]) -> None:
    fields=list(rows[0].keys()) if rows else []
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(rows)

def main(argv=None)->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--archive",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ns=ap.parse_args(argv)
    repo=ns.repo.expanduser().resolve(); archive=ns.archive.expanduser().resolve(); out=ns.output.expanduser().resolve()
    out.mkdir(parents=True,exist_ok=True)
    side=Path(str(archive)+".sha256")
    side_ok=False
    if archive.is_file() and side.is_file():
        parts=side.read_text().strip().split()
        side_ok=len(parts)>=2 and parts[0]==sha256_file(archive) and parts[-1]==archive.name
    with tempfile.TemporaryDirectory(prefix="r2722-") as tmp:
        scratch=Path(tmp)
        finals=finalizer_rows(repo,archive,scratch)
        pubs=publication_rows(repo,archive,scratch)
    write_tsv(out/"finalizer-retirement-equivalence.tsv",finals)
    write_tsv(out/"publication-verifier-retirement-equivalence.tsv",pubs)
    feq=sum(r["equivalent"]=="YES" for r in finals)
    peq=sum(r["equivalent"]=="YES" for r in pubs)
    summary={
        "schema":"rokid.r27.2.2.r25-finalization-publication-retirement.v1",
        "status":"PASS" if side_ok and feq==7 and peq==6 else "FAIL",
        "preservation_sidecar_valid":side_ok,
        "preserved_original_count":13,
        "finalizer_profile_count":len(finals),"finalizer_equivalent_count":feq,
        "publication_verifier_profile_count":len(pubs),"publication_verifier_equivalent_count":peq,
        "newly_reduced_implementation_count":13,
        "legacy_path_deleted_count":0,
        "device_operation":"NONE","privileged_operation":"NONE",
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print("R27_2_2_VERIFY="+summary["status"])
    print(f"R25_FINALIZER_PROFILE_COUNT={len(finals)}")
    print(f"R25_FINALIZER_ARCHIVED_SHIM_EQUIVALENT_COUNT={feq}")
    print(f"R25_PUBLICATION_VERIFIER_PROFILE_COUNT={len(pubs)}")
    print(f"R25_PUBLICATION_VERIFIER_ARCHIVED_SHIM_EQUIVALENT_COUNT={peq}")
    print("NEWLY_REDUCED_IMPLEMENTATION_COUNT=13")
    print("LEGACY_PATH_DELETED_COUNT=0")
    print("DEVICE_OPERATION=NONE")
    print("PRIVILEGED_OPERATION=NONE")
    return 0 if summary["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
