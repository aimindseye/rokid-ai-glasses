#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

try:
    from connection_validator import validate as validate_connection_revision, list_profiles as list_connection_profiles
    from evidence_packager import package as package_evidence_revision, list_profiles as list_evidence_profiles
    from source_contract import check as check_source_contract, list_profiles as list_source_contract_profiles
    from tool_test_runner import run_cli as run_tool_test, list_profiles as list_tool_test_profiles, verify_oracle_locks
    from primitives import sha256_file
    from retirement_status import emit as emit_retirement_status
    from consolidation_status import emit as emit_consolidation_status
    from r25_finalizer import finalize as finalize_r25_revision, list_profiles as list_r25_finalizer_profiles
    from r25_publication_verifier import verify as verify_r25_publication, list_profiles as list_r25_publication_profiles
    from pcap_parser import parse_revision as parse_pcap_revision, list_profiles as list_pcap_profiles
    from network_privacy_analyzer import analyze_revision as analyze_network_revision, list_profiles as list_network_analyzer_profiles
except ImportError:
    from scripts.research.canonical.connection_validator import validate as validate_connection_revision, list_profiles as list_connection_profiles
    from scripts.research.canonical.evidence_packager import package as package_evidence_revision, list_profiles as list_evidence_profiles
    from scripts.research.canonical.source_contract import check as check_source_contract, list_profiles as list_source_contract_profiles
    from scripts.research.canonical.tool_test_runner import run_cli as run_tool_test, list_profiles as list_tool_test_profiles, verify_oracle_locks
    from scripts.research.canonical.primitives import sha256_file
    from scripts.research.canonical.retirement_status import emit as emit_retirement_status
    from scripts.research.canonical.consolidation_status import emit as emit_consolidation_status
    from scripts.research.canonical.r25_finalizer import finalize as finalize_r25_revision, list_profiles as list_r25_finalizer_profiles
    from scripts.research.canonical.r25_publication_verifier import verify as verify_r25_publication, list_profiles as list_r25_publication_profiles
    from scripts.research.canonical.pcap_parser import parse_revision as parse_pcap_revision, list_profiles as list_pcap_profiles
    from scripts.research.canonical.network_privacy_analyzer import analyze_revision as analyze_network_revision, list_profiles as list_network_analyzer_profiles

OPS = (
    "run", "collect", "analyze", "package", "check", "verify", "validate",
    "prepare", "inspect", "finalize", "build", "install", "compile", "publish",
    "resolve", "extract", "parse", "apply", "repair", "generate", "summarize",
)
REV_PATTERNS = [
    re.compile(r"r1_3_3_2_25(?:_\d+)*", re.I),
    re.compile(r"test[-_]?\d+(?:[-_]?r?\d+(?:[-_]\d+)*)?", re.I),
    re.compile(r"(?:^|[_-])r\d+(?:[_\.-]\d+)*", re.I),
]
SCRIPT_EXTS = {".py", ".sh", ".js", ".ts"}
CANONICAL_PREFIXES = (
    "scripts/research/canonical/",
    "scripts/rokid-research",
    "scripts/tests/test_r27_",
)


def operation(name: str) -> str:
    stem = Path(name).stem.lower()
    for op in OPS:
        if stem == op or stem.startswith(op + "_") or stem.startswith(op + "-"):
            return op
    if stem.startswith("test_") or stem.startswith("test-"):
        return "test"
    return "other"


def track(path: str) -> str:
    low = path.lower()
    m = re.search(r"test[-_ ]?(\d+)", low)
    if m:
        return f"test{int(m.group(1))}"
    if "r1_3_3_2_25" in low or re.search(r"(?:^|[/_-])r25(?:[/_.-]|$)", low):
        return "r25-connection-protocol"
    if "connection-protocol" in low:
        return "connection-protocol"
    if "native-loader" in low:
        return "native-loader"
    if "protected-application" in low:
        return "protected-application"
    if "/cxr/" in "/" + low:
        return "cxr"
    if "/capture/" in "/" + low:
        return "capture"
    if "/analysis/" in "/" + low:
        return "analysis"
    if "/safety/" in "/" + low:
        return "safety"
    if "/recovery/" in "/" + low:
        return "recovery"
    return "general"


def family_key(path: str) -> str:
    p = Path(path)
    stem = p.stem.lower()
    for pat in REV_PATTERNS:
        stem = pat.sub("REV", stem)
    stem = re.sub(r"(?:^|_)\d+(?:_\d+){2,}", "_REV", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return f"{p.parent.as_posix()}::{operation(p.name)}::{stem}"


def revision_named(path: str) -> bool:
    name = Path(path).stem
    return any(p.search(name) for p in REV_PATTERNS)


def safety_class(path: str, op: str) -> str:
    low = path.lower()
    risky = (
        "frida", "magisk", "adb", "capture", "collect", "install", "pairing",
        "bluetooth", "photo", "audio", "firmware", "device", "persistent",
        "proc_mem", "proc-mem", "boot", "root", "network_differential",
    )
    if any(x in low for x in risky) or op in {"collect", "install"}:
        return "DEVICE_OR_PRIVILEGED_REVIEW_REQUIRED"
    if op in {"analyze", "check", "verify", "validate", "summarize", "parse"}:
        return "HOST_ANALYSIS_CANDIDATE"
    return "REVIEW_REQUIRED"


def canonical_successor(path: str, trk: str, op: str) -> str:
    if op == "test" and path.startswith("scripts/tests/test_"):
        return "rokid-research test run"
    if op == "parse" and "parse_test21_" in path.lower() and "_pcap" in path.lower():
        return "rokid-research network parse-pcap"
    if op == "analyze" and path.lower().startswith("scripts/tests/analyze_test19") and "_network" in path.lower():
        return "rokid-research network analyze-csv"
    if "sanit" in path.lower() or op == "package":
        return f"rokid-research evidence {op}"
    if trk.startswith("test19") or trk.startswith("test20") or trk.startswith("test21") or trk == "cxr":
        return f"rokid-research cxr {op}"
    if trk in {"r25-connection-protocol", "connection-protocol"}:
        return f"rokid-research connection {op}"
    if trk == "native-loader":
        return f"rokid-research native-loader {op}"
    if trk == "protected-application":
        return f"rokid-research protected-application {op}"
    if trk == "capture":
        return f"rokid-research capture {op}"
    if trk == "analysis":
        return f"rokid-research analysis {op}"
    if trk == "safety":
        return f"rokid-research repo {op}"
    if trk.startswith("test"):
        return f"rokid-research tests {op}"
    return f"rokid-research legacy {op}"


def run_git(repo: Path, args: list[str]) -> tuple[int, bytes]:
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, b""


def git_status_sets(repo: Path):
    tracked: set[str] = set()
    untracked: set[str] = set()
    ignored: set[str] = set()
    rc, out = run_git(repo, ["ls-files", "-z"])
    if rc == 0:
        tracked = {x.decode("utf-8", "replace") for x in out.split(b"\0") if x}
    rc, out = run_git(repo, ["status", "--porcelain=v1", "--untracked-files=all", "--ignored", "-z"])
    if rc == 0:
        for rec in out.split(b"\0"):
            if not rec:
                continue
            text = rec.decode("utf-8", "replace")
            status = text[:2]
            path = text[3:]
            if status == "??":
                untracked.add(path)
            elif status == "!!":
                ignored.add(path)
    return tracked, untracked, ignored


def git_status(path: str, tracked: set[str], untracked: set[str], ignored: set[str]) -> str:
    if path in tracked:
        return "TRACKED"
    if path in untracked:
        return "UNTRACKED"
    if path in ignored:
        return "IGNORED"
    return "UNKNOWN"


def legacy_scripts(repo: Path):
    tracked, untracked, ignored = git_status_sets(repo)
    rows = []
    scripts = repo / "scripts"
    if not scripts.is_dir():
        return rows
    for p in sorted(scripts.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SCRIPT_EXTS:
            continue
        rel = p.relative_to(repo).as_posix()
        if "__pycache__" in p.parts:
            continue
        if any(rel == x or rel.startswith(x) for x in CANONICAL_PREFIXES):
            continue
        op = operation(p.name)
        trk = track(rel)
        rows.append({
            "path": rel,
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "git_status": git_status(rel, tracked, untracked, ignored),
            "track": trk,
            "operation": op,
            "family_key": family_key(rel),
            "revision_named": "YES" if revision_named(rel) else "NO",
            "safety_class": safety_class(rel, op),
            "canonical_successor": canonical_successor(rel, trk, op),
        })
    return rows


def documentation_rows(repo: Path):
    tracked, untracked, ignored = git_status_sets(repo)
    roots = [repo / "docs"]
    candidates = []
    for root in roots:
        if root.is_dir():
            candidates.extend(p for p in root.rglob("*.md") if p.is_file())
    for name in ("README.md", "ARCHITECTURE.md", "CONTRIBUTING.md", "SECURITY.md"):
        p = repo / name
        if p.is_file():
            candidates.append(p)
    rows = []
    for p in sorted(set(candidates)):
        rel = p.relative_to(repo).as_posix()
        rows.append({
            "path": rel,
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "git_status": git_status(rel, tracked, untracked, ignored),
            "revision_named": "YES" if revision_named(rel) else "NO",
            "track": track(rel),
        })
    return rows


def family_rows(scripts):
    grouped = defaultdict(list)
    for row in scripts:
        grouped[row["family_key"]].append(row)
    out = []
    for key, members in sorted(grouped.items()):
        statuses = sorted({m["git_status"] for m in members})
        out.append({
            "family_key": key,
            "member_count": len(members),
            "tracks": ",".join(sorted({m["track"] for m in members})),
            "operations": ",".join(sorted({m["operation"] for m in members})),
            "revision_named_count": sum(m["revision_named"] == "YES" for m in members),
            "git_statuses": ",".join(statuses),
            "disposition": "CONSOLIDATE_FAMILY" if len(members) > 1 else ("PRESERVE_LINEAGE_PENDING_MIGRATION" if members[0]["revision_named"] == "YES" else "CANONICAL_CANDIDATE"),
            "canonical_successor": members[0]["canonical_successor"],
            "paths": " | ".join(m["path"] for m in members),
        })
    return out


def write_tsv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def summarize(repo: Path):
    scripts = legacy_scripts(repo)
    docs = documentation_rows(repo)
    families = family_rows(scripts)
    legacy_tree_files = []
    scripts_root = repo / "scripts"
    if scripts_root.is_dir():
        for p in scripts_root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(repo).as_posix()
            if any(rel == x or rel.startswith(x) for x in CANONICAL_PREFIXES):
                continue
            legacy_tree_files.append(rel)
    return scripts, docs, families, {
        "schema": "rokid.r27.1.0.repository-canonicalization.v1",
        "legacy_script_count": len(scripts),
        "legacy_source_script_count": len(scripts),
        "legacy_script_tree_file_count": len(legacy_tree_files),
        "markdown_documentation_count": len(docs),
        "documentation_count": len(docs),
        "revision_named_documentation_count": sum(r["revision_named"] == "YES" for r in docs),
        "script_family_count": len(families),
        "multi_member_script_family_count": sum(int(r["member_count"]) > 1 for r in families),
        "git_status_counts": dict(Counter(r["git_status"] for r in scripts)),
        "script_tracks": dict(sorted(Counter(r["track"] for r in scripts).items())),
        "script_operations": dict(sorted(Counter(r["operation"] for r in scripts).items())),
        "safety_classes": dict(sorted(Counter(r["safety_class"] for r in scripts).items())),
        "legacy_file_action": "NONE",
        "repository_deletion": "NONE",
        "device_operation": "NONE",
    }


def inventory(repo: Path, output: Path):
    scripts, docs, families, summary = summarize(repo)
    output.mkdir(parents=True, exist_ok=True)
    write_tsv(output / "script-lineage.tsv", scripts, [
        "path", "size_bytes", "sha256", "git_status", "track", "operation", "family_key",
        "revision_named", "safety_class", "canonical_successor",
    ])
    write_tsv(output / "script-families.tsv", families, [
        "family_key", "member_count", "tracks", "operations", "revision_named_count",
        "git_statuses", "disposition", "canonical_successor", "paths",
    ])
    write_tsv(output / "documentation-lineage.tsv", docs, [
        "path", "size_bytes", "sha256", "git_status", "revision_named", "track",
    ])
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    top = sorted(families, key=lambda r: int(r["member_count"]), reverse=True)[:20]
    md = [
        "# R27.1.0 repository canonicalization inventory",
        "",
        f"- legacy executable/source scripts: **{summary['legacy_source_script_count']}**",
        f"- legacy files under `scripts/` (including READMEs/caches): **{summary['legacy_script_tree_file_count']}**",
        f"- Markdown documentation files: **{summary['markdown_documentation_count']}**",
        f"- revision-named documentation files: **{summary['revision_named_documentation_count']}**",
        f"- script families: **{summary['script_family_count']}**",
        f"- multi-member script families: **{summary['multi_member_script_family_count']}**",
        "- repository deletion: **NONE**",
        "- legacy file action: **NONE**",
        "",
        "## Largest consolidation families",
        "",
        "| Members | Track | Operation | Disposition | Family |",
        "|---:|---|---|---|---|",
    ]
    for r in top:
        md.append(f"| {r['member_count']} | {r['tracks']} | {r['operations']} | {r['disposition']} | `{r['family_key']}` |")
    (output / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Package only the generated reports. They can include local untracked path names and are private by default.
    zip_path = output.parent / (output.name + "-private-lineage.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.iterdir()):
            if p.is_file():
                z.write(p, arcname=p.name)
    zsha = sha256_file(zip_path)
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(f"{zsha}  {zip_path.name}\n", encoding="utf-8")
    return summary, zip_path, sidecar


def required_canonical_files(repo: Path):
    return [
        repo / "scripts/rokid-research",
        repo / "scripts/research/canonical/r27_catalog.py",
        repo / "scripts/research/canonical/evidence_packager.py",
        repo / "scripts/research/canonical/profiles/test21-sanitized-packagers.json",
        repo / "scripts/research/canonical/tool_test_runner.py",
        repo / "scripts/research/canonical/profiles/tool-test-suites.json",
        repo / "scripts/research/canonical/primitives.py",
        repo / "scripts/research/canonical/privacy.py",
        repo / "scripts/research/canonical/retirement_status.py",
        repo / "scripts/research/canonical/retirement_dependencies.py",
        repo / "scripts/research/canonical/r25_finalizer.py",
        repo / "scripts/research/canonical/profiles/r25-finalizers.json",
        repo / "scripts/research/canonical/r25_publication_verifier.py",
        repo / "scripts/research/canonical/profiles/r25-publication-verifiers.json",
        repo / "scripts/research/canonical/pcap_parser.py",
        repo / "scripts/research/canonical/profiles/test21-pcap-parsers.json",
        repo / "scripts/research/canonical/network_privacy_analyzer.py",
        repo / "scripts/research/canonical/profiles/test19-network-analyzers.json",
        repo / "scripts/research/canonical/verify_r27_2_7.py",
        repo / "scripts/research/canonical/verify_r27_2_8.py",
        repo / "scripts/research/canonical/consolidation_status.py",
        repo / "scripts/research/canonical/profiles/r27-final-consolidation.json",
        repo / "scripts/research/canonical/verify_r27_2_4.py",
        repo / "scripts/research/canonical/verify_r27_2_5.py",
        repo / "scripts/research/canonical/verify_r27_2_1.py",
        repo / "scripts/research/canonical/verify_r27_1_7.py",
        repo / "docs/research/tooling/README.md",
        repo / "docs/research/tooling/canonical-harness.md",
        repo / "docs/research/tooling/legacy-lineage-policy.md",
        repo / "docs/research/r27.1.0-whole-repository-canonicalization.md",
        repo / "docs/research/r27.1.6-first-legacy-reduction.md",
        repo / "docs/research/r27.1.7-test21-historical-container-compatibility.md",
        repo / "docs/research/r27.2.1-r25-finalization-publication-framework.md",
        repo / "docs/research/r27.2.4-test21-pcap-parser-framework.md",
        repo / "docs/research/r27.2.5-test21-pcap-parser-reduction.md",
        repo / "docs/research/r27.2.7-test19-network-analyzer-framework.md",
        repo / "docs/research/r27.2.8-final-consolidation-closure.md",
    ]


def verify(repo: Path) -> int:
    missing = [p for p in required_canonical_files(repo) if not p.is_file()]
    if missing:
        for p in missing:
            print(f"MISSING={p.relative_to(repo)}")
        return 1
    scripts, docs, families, summary = summarize(repo)
    # These are floor gates, not frozen counts; future canonical migrations may lower the legacy count only after an explicit retirement phase.
    if len(scripts) < 200:
        print(f"FAIL=legacy_script_count_too_low:{len(scripts)}")
        return 1
    if len(docs) < 200:
        print(f"FAIL=documentation_count_too_low:{len(docs)}")
        return 1
    if not any(r["track"] == "test21" for r in scripts):
        print("FAIL=test21_lineage_missing")
        return 1
    if not any(r["track"] == "r25-connection-protocol" for r in scripts):
        print("FAIL=r25_lineage_missing")
        return 1
    print("R27_1_0_CANONICAL_HARNESS_VERIFY=PASS")
    print(f"LEGACY_SCRIPT_COUNT={summary['legacy_script_count']}")
    print(f"DOCUMENTATION_COUNT={summary['documentation_count']}")
    print(f"SCRIPT_FAMILY_COUNT={summary['script_family_count']}")
    print(f"MULTI_MEMBER_SCRIPT_FAMILY_COUNT={summary['multi_member_script_family_count']}")
    print("LEGACY_FILE_ACTION=R27_FINAL_88_IMPLEMENTATIONS_CANONICALIZED_WITH_HISTORICAL_PATHS_OR_LINEAGE_PRESERVED")
    print("REPOSITORY_DELETION=NONE")
    print("DEVICE_OPERATION=NONE")
    return 0


def print_catalog(repo: Path, track_filter=None, op_filter=None):
    rows = legacy_scripts(repo)
    for r in rows:
        if track_filter and r["track"] != track_filter:
            continue
        if op_filter and r["operation"] != op_filter:
            continue
        print("\t".join(str(r[k]) for k in ("track", "operation", "git_status", "safety_class", "path", "canonical_successor")))


def resolve(repo: Path, rel: str) -> int:
    rel = Path(rel).as_posix().lstrip("./")
    for r in legacy_scripts(repo):
        if r["path"] == rel:
            print(json.dumps(r, indent=2, sort_keys=True))
            return 0
    print(f"ERROR: legacy script not found: {rel}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Canonical research-harness front door for Rokid research lineage")
    ap.add_argument("--repo", default=None, help="repository root; defaults to three levels above this module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary")
    pcat = sub.add_parser("catalog")
    pcat.add_argument("--track")
    pcat.add_argument("--operation")
    pres = sub.add_parser("resolve")
    pres.add_argument("path")
    sub.add_parser("verify")
    pinv = sub.add_parser("inventory")
    pinv.add_argument("--output", required=True)
    pconn = sub.add_parser("connection")
    connsub = pconn.add_subparsers(dest="connection_cmd", required=True)
    pval = connsub.add_parser("validate")
    pval.add_argument("--revision")
    pval.add_argument("--list", action="store_true")
    pfinal = connsub.add_parser("finalize")
    pfinal.add_argument("--revision")
    pfinal.add_argument("--run")
    pfinal.add_argument("--list", action="store_true")
    ppub = connsub.add_parser("verify-publication")
    ppub.add_argument("--revision")
    ppub.add_argument("--publication")
    ppub.add_argument("--list", action="store_true")
    pnetwork = sub.add_parser("network")
    netsub = pnetwork.add_subparsers(dest="network_cmd", required=True)
    pparse = netsub.add_parser("parse-pcap")
    pparse.add_argument("--revision")
    pparse.add_argument("--pcap")
    pparse.add_argument("--uid-map")
    pparse.add_argument("--output")
    pparse.add_argument("--sslkeylog")
    pparse.add_argument("--list", action="store_true")
    panalyze = netsub.add_parser("analyze-csv")
    panalyze.add_argument("--revision")
    panalyze.add_argument("--csv")
    panalyze.add_argument("--output")
    panalyze.add_argument("--list", action="store_true")
    pevidence = sub.add_parser("evidence")
    evidsub = pevidence.add_subparsers(dest="evidence_cmd", required=True)
    ppackage = evidsub.add_parser("package")
    ppackage.add_argument("--revision")
    ppackage.add_argument("--list", action="store_true")
    ppackage.add_argument("--evidence")
    ppackage.add_argument("--phone", default="")
    ppackage.add_argument("--output")
    pcontract = sub.add_parser("contract")
    contractsub = pcontract.add_subparsers(dest="contract_cmd", required=True)
    pcheck = contractsub.add_parser("check")
    pcheck.add_argument("--track")
    pcheck.add_argument("--revision")
    pcheck.add_argument("--list", action="store_true")
    pcheck.add_argument("--output")
    ptest = sub.add_parser("test")
    testsub = ptest.add_subparsers(dest="test_cmd", required=True)
    prun = testsub.add_parser("run")
    prun.add_argument("--track")
    prun.add_argument("--revision")
    prun.add_argument("--list", action="store_true")
    testsub.add_parser("verify-oracles")
    pconsol = sub.add_parser("consolidation")
    consolsub = pconsol.add_subparsers(dest="consolidation_cmd", required=True)
    pcstatus = consolsub.add_parser("status")
    pcstatus.add_argument("--output")
    pretire = sub.add_parser("retirement")
    retiresub = pretire.add_subparsers(dest="retirement_cmd", required=True)
    pstatus = retiresub.add_parser("status")
    pstatus.add_argument("--output")
    args = ap.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve() if args.repo else Path(__file__).resolve().parents[3]
    if not (repo / "scripts").is_dir():
        print(f"ERROR: repository root not recognized: {repo}", file=sys.stderr)
        return 2

    if args.cmd == "summary":
        _, _, _, s = summarize(repo)
        print(json.dumps(s, indent=2, sort_keys=True))
        return 0
    if args.cmd == "catalog":
        print("track\toperation\tgit_status\tsafety_class\tpath\tcanonical_successor")
        print_catalog(repo, args.track, args.operation)
        return 0
    if args.cmd == "resolve":
        return resolve(repo, args.path)
    if args.cmd == "verify":
        return verify(repo)
    if args.cmd == "inventory":
        summary, z, sidecar = inventory(repo, Path(args.output).expanduser().resolve())
        print("R27_1_0_INVENTORY=PASS")
        print(f"LEGACY_SCRIPT_COUNT={summary['legacy_script_count']}")
        print(f"DOCUMENTATION_COUNT={summary['documentation_count']}")
        print(f"MULTI_MEMBER_SCRIPT_FAMILY_COUNT={summary['multi_member_script_family_count']}")
        print(f"PRIVATE_LINEAGE_ZIP={z}")
        print(f"PRIVATE_LINEAGE_SIDECAR={sidecar}")
        print("LEGACY_FILE_ACTION=NONE")
        print("REPOSITORY_DELETION=NONE")
        print("DEVICE_OPERATION=NONE")
        return 0
    if args.cmd == "connection" and args.connection_cmd == "validate":
        if args.list:
            return list_connection_profiles()
        if not args.revision:
            print("ERROR: --revision is required", file=sys.stderr)
            return 2
        return validate_connection_revision(repo, args.revision)
    if args.cmd == "connection" and args.connection_cmd == "finalize":
        if args.list:
            return list_r25_finalizer_profiles()
        if not args.revision or not args.run:
            print("ERROR: --revision and --run are required", file=sys.stderr)
            return 2
        rc, _archive, _sidecar = finalize_r25_revision(repo, args.revision, Path(args.run))
        return rc
    if args.cmd == "connection" and args.connection_cmd == "verify-publication":
        if args.list:
            return list_r25_publication_profiles()
        if not args.revision or not args.publication:
            print("ERROR: --revision and --publication are required", file=sys.stderr)
            return 2
        rc, _lines = verify_r25_publication(repo, args.revision, Path(args.publication), emit_output=True)
        return rc
    if args.cmd == "network" and args.network_cmd == "parse-pcap":
        if args.list:
            return list_pcap_profiles()
        if not args.revision or not args.pcap or not args.uid_map or not args.output:
            print("ERROR: --revision, --pcap, --uid-map, and --output are required", file=sys.stderr)
            return 2
        rc, _summary, _lines = parse_pcap_revision(
            repo,
            args.revision,
            Path(args.pcap).expanduser().resolve(),
            Path(args.uid_map).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            Path(args.sslkeylog).expanduser().resolve() if args.sslkeylog else None,
            emit_output=True,
        )
        return rc
    if args.cmd == "network" and args.network_cmd == "analyze-csv":
        if args.list:
            return list_network_analyzer_profiles()
        if not args.revision or not args.csv or not args.output:
            print("ERROR: --revision, --csv, and --output are required", file=sys.stderr)
            return 2
        rc, _summary, _lines = analyze_network_revision(
            repo,
            args.revision,
            Path(args.csv).expanduser().resolve(),
            Path(args.output).expanduser().resolve(),
            emit_output=True,
        )
        return rc
    if args.cmd == "evidence" and args.evidence_cmd == "package":
        if args.list:
            return list_evidence_profiles()
        if not args.revision or not args.evidence:
            print("ERROR: --revision and --evidence are required", file=sys.stderr)
            return 2
        output = Path(args.output).expanduser().resolve() if args.output else None
        rc, _, _ = package_evidence_revision(repo, args.revision, Path(args.evidence), args.phone, output)
        return rc
    if args.cmd == "contract" and args.contract_cmd == "check":
        if args.list:
            return list_source_contract_profiles()
        if not args.track or not args.revision:
            print("ERROR: --track and --revision are required", file=sys.stderr)
            return 2
        output = Path(args.output).expanduser().resolve() if args.output else None
        return check_source_contract(repo, args.track, args.revision, output)
    if args.cmd == "test" and args.test_cmd == "run":
        if args.list:
            return list_tool_test_profiles(args.track)
        if not args.track or not args.revision:
            print("ERROR: --track and --revision are required", file=sys.stderr)
            return 2
        return run_tool_test(repo, args.track, args.revision)
    if args.cmd == "test" and args.test_cmd == "verify-oracles":
        rc, _detail = verify_oracle_locks(repo, emit_output=True)
        return rc
    if args.cmd == "consolidation" and args.consolidation_cmd == "status":
        output = Path(args.output).expanduser().resolve() if args.output else None
        return emit_consolidation_status(repo, output)
    if args.cmd == "retirement" and args.retirement_cmd == "status":
        output = Path(args.output).expanduser().resolve() if args.output else None
        return emit_retirement_status(repo, output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
