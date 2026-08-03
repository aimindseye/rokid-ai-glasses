#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
try:
    from primitives import sha256_file
    from r25_finalizer import load_profiles as load_finalizer_profiles
    from r25_publication_verifier import load_profiles as load_publication_profiles
except ImportError:
    from scripts.research.canonical.primitives import sha256_file
    from scripts.research.canonical.r25_finalizer import load_profiles as load_finalizer_profiles
    from scripts.research.canonical.r25_publication_verifier import load_profiles as load_publication_profiles

def rows(repo:Path)->list[dict]:
    out=[]
    for family,profiles in (("r25-finalizers",load_finalizer_profiles()),("r25-publication-verifiers",load_publication_profiles())):
        for p in profiles:
            live=repo/p["legacy_path"]
            expected=p.get("compatibility_shim_sha256","")
            locked=live.is_file() and bool(expected) and sha256_file(live)==expected
            out.append({
                "family":family,"revision":p["revision"],"path":p["legacy_path"],
                "retirement_state":p.get("retirement_state",""),
                "historical_source_sha256":p.get("historical_source_sha256",p.get("legacy_sha256","")),
                "compatibility_shim_sha256":expected,
                "live_shim_lock":"PASS" if locked else "FAIL",
            })
    return out

def main(argv=None)->int:
    ap=argparse.ArgumentParser();ap.add_argument("--repo",required=True,type=Path);ap.add_argument("--output",type=Path)
    ns=ap.parse_args(argv);repo=ns.repo.expanduser().resolve();rs=rows(repo)
    fin=sum(r["family"]=="r25-finalizers" and r["live_shim_lock"]=="PASS" and r["retirement_state"]=="COMPATIBILITY_SHIM" for r in rs)
    pub=sum(r["family"]=="r25-publication-verifiers" and r["live_shim_lock"]=="PASS" and r["retirement_state"]=="COMPATIBILITY_SHIM" for r in rs)
    fail=sum(r["live_shim_lock"]!="PASS" for r in rs)
    summary={
        "schema":"rokid.r27.2.2.r25-lifecycle-status.v1",
        "status":"PASS" if fin==7 and pub==6 and fail==0 else "FAIL",
        "r25_finalizer_compatibility_shim_count":fin,
        "r25_publication_verifier_compatibility_shim_count":pub,
        "r27_2_2_canonicalized_implementation_count":fin+pub,
        "r27_1_canonicalized_implementation_count":71,
        "total_canonicalized_implementation_count":71+fin+pub,
        "source_lock_failure_count":fail,
        "remaining_r25_finalization_publication_implementation_count":13-(fin+pub),
        "repository_deletion":"NONE","device_operation":"NONE","privileged_operation":"NONE",
    }
    if ns.output:
        out=ns.output.expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
        with (out/"r25-lifecycle-status.tsv").open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]),delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(rs)
        (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print("R27_2_2_LIFECYCLE_STATUS="+summary["status"])
    print(f"R25_FINALIZER_COMPATIBILITY_SHIM_COUNT={fin}")
    print(f"R25_PUBLICATION_VERIFIER_COMPATIBILITY_SHIM_COUNT={pub}")
    print(f"R27_2_2_CANONICALIZED_IMPLEMENTATION_COUNT={fin+pub}")
    print(f"TOTAL_CANONICALIZED_IMPLEMENTATION_COUNT={71+fin+pub}")
    print(f"REMAINING_R25_FINALIZATION_PUBLICATION_IMPLEMENTATION_COUNT={13-(fin+pub)}")
    print(f"SOURCE_LOCK_FAILURE_COUNT={fail}")
    print("REPOSITORY_DELETION=NONE")
    print("DEVICE_OPERATION=NONE")
    print("PRIVILEGED_OPERATION=NONE")
    return 0 if summary["status"]=="PASS" else 1
if __name__=="__main__": raise SystemExit(main())
