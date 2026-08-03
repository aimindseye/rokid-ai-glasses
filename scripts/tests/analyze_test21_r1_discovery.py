#!/usr/bin/env python3
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

EXPECTED_AAR_SHA256 = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"

AIUI_TERMS = ("aiui", ".aix", "jsar", "yodaos", "ink runtime", "rokid.js", "@yodaos-pkg/aiui")
HI_ROKID_HINTS = ("hirokid", "hi.rokid", "rokid", "lingzhu", "rizon")
CUSTOM_HINTS = ("org.aimindseye.rokid", "cxrphotoqualification", "test20r32")
EXPECTED_GLOBAL_HI_ROKID_PACKAGE = "com.rokid.sprite.global.aiapp"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def package_names(text: str):
    """Parse `pm list packages` and `pm list packages -f` safely.

    Modern Android /data/app paths can themselves contain '=' (for example
    the `~~token==` segment), so package extraction must split on the LAST
    equals sign rather than the first one.
    """
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        payload = line[len("package:"):]
        pkg = payload.rsplit("=", 1)[-1].strip() if "=" in payload else payload.strip()
        if pkg:
            out.append(pkg)
    return sorted(set(out))


def score_hi_rokid(pkg: str, process_text: str, services_text: str) -> int:
    p = pkg.lower()
    score = 0
    if "rokid" in p:
        score += 5
    if "hirokid" in p or "hi.rokid" in p:
        score += 6
    if "lingzhu" in p or "rizon" in p:
        score += 2
    if pkg in process_text:
        score += 3
    if pkg in services_text:
        score += 4
    return score


def has_terms(text: str):
    lower = text.lower()
    return sorted({term for term in AIUI_TERMS if term.lower() in lower})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--hi-rokid-package", default="")
    ap.add_argument("--custom-package", default="")
    args = ap.parse_args()

    root = Path(args.evidence).resolve()
    raw = root / "raw"
    sanitized = root / "sanitized"
    sanitized.mkdir(parents=True, exist_ok=True)

    packages_text = read(raw / "phone-packages.txt")
    process_text = read(raw / "phone-processes.txt")
    services_text = read(raw / "activity-services.txt")
    repo_census = read(raw / "repo-cxr-aiui-census.txt")
    aar_census = read(raw / "aar-census.txt")
    aar_strings = read(raw / "aar-strings.txt")
    collection = read(raw / "collection-status.txt")

    packages = package_names(packages_text)

    ranked = []
    for pkg in packages:
        if any(h in pkg.lower() for h in HI_ROKID_HINTS):
            s = score_hi_rokid(pkg, process_text, services_text)
            ranked.append((s, pkg))
    ranked.sort(key=lambda x: (-x[0], x[1]))

    explicit_hi = args.hi_rokid_package.strip()
    hi_candidates = [p for _, p in ranked[:10]]
    if explicit_hi:
        selected_hi = explicit_hi
        selected_hi_confidence = "operator_explicit"
    elif EXPECTED_GLOBAL_HI_ROKID_PACKAGE in packages:
        selected_hi = EXPECTED_GLOBAL_HI_ROKID_PACKAGE
        selected_hi_confidence = "official_global_package_exact"
    else:
        selected_hi = hi_candidates[0] if ranked and ranked[0][0] >= 8 else ""
        selected_hi_confidence = "heuristic_high" if selected_hi else "unresolved"

    explicit_custom = args.custom_package.strip()
    custom_candidates = [p for p in packages if any(h in p.lower() for h in CUSTOM_HINTS)]
    preferred_custom = "org.aimindseye.rokid.cxrphotoqualification"
    if explicit_custom:
        selected_custom = explicit_custom
    elif preferred_custom in packages:
        selected_custom = preferred_custom
    else:
        selected_custom = custom_candidates[0] if custom_candidates else ""

    aar_paths = []
    for line in aar_census.splitlines():
        if line.startswith("AAR_PATH="):
            aar_paths.append(line.split("=", 1)[1].strip())

    aar_path = Path(aar_paths[0]) if aar_paths else None
    aar_found = bool(aar_path and aar_path.is_file())
    aar_hash = sha256(aar_path) if aar_found else ""
    aar_hash_match = aar_hash == EXPECTED_AAR_SHA256

    aiui_repo_terms = has_terms(repo_census)
    aiui_aar_terms = has_terms(aar_strings)
    aiui_package_terms = sorted({p for p in packages if any(t in p.lower() for t in ("aiui", "jsar", "yoda", "ink"))})

    collection_failures = []
    for line in collection.splitlines():
        if line.startswith("RC_") and not line.endswith("=0"):
            collection_failures.append(line)

    if not aar_found:
        next_action = "BLOCKED_CXR_L_AAR_NOT_FOUND"
    elif not selected_hi:
        next_action = "NEEDS_HI_ROKID_PACKAGE_RESOLUTION"
    else:
        next_action = "R2_FORCE_STOP_OWNERSHIP_PROBE_READY"

    summary = {
        "schema": "rokid.test21-r1.runtime-dependency-discovery.v1",
        "scope": "read_only_preflight",
        "device_mutation": "NONE",
        "photo_operation": "NONE",
        "audio_operation": "NONE",
        "aiui_operation": "STATIC_ELIGIBILITY_CENSUS_ONLY",
        "cxr_l": {
            "coordinate": "com.rokid.cxr:client-l:1.0.1",
            "aar_found": aar_found,
            "aar_sha256": aar_hash,
            "expected_aar_sha256": EXPECTED_AAR_SHA256,
            "aar_sha256_match": aar_hash_match,
        },
        "hi_rokid": {
            "selected_package": selected_hi,
            "selection_confidence": selected_hi_confidence,
            "selected_package_installed_exact": bool(selected_hi and selected_hi in packages),
            "candidate_packages": hi_candidates,
            "selected_package_process_visible": bool(selected_hi and selected_hi in process_text),
            "selected_package_service_visible": bool(selected_hi and selected_hi in services_text),
        },
        "custom_companion": {
            "selected_package": selected_custom,
            "candidate_packages": custom_candidates,
            "installed": bool(selected_custom),
        },
        "aiui_eligibility": {
            "repo_terms": aiui_repo_terms,
            "aar_terms": aiui_aar_terms,
            "phone_package_signals": aiui_package_terms,
            "signal_present": bool(aiui_repo_terms or aiui_aar_terms or aiui_package_terms),
            "non_display_runtime_support_proven": False,
        },
        "collection": {
            "nonzero_collection_steps": collection_failures,
        },
        "next_action": next_action,
    }

    json_path = sanitized / "test21-r1-summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    txt = [
        "TEST21_R1_ANALYSIS=PASS",
        f"CXR_L_AAR_FOUND={'YES' if aar_found else 'NO'}",
        f"CXR_L_AAR_SHA256_MATCH={'YES' if aar_hash_match else 'NO'}",
        f"HI_ROKID_PACKAGE_SELECTED={selected_hi or 'UNRESOLVED'}",
        f"HI_ROKID_PACKAGE_SELECTION_CONFIDENCE={selected_hi_confidence}",
        f"CUSTOM_COMPANION_INSTALLED={'YES' if selected_custom else 'NO'}",
        f"AIUI_ELIGIBILITY_SIGNAL_PRESENT={'YES' if summary['aiui_eligibility']['signal_present'] else 'NO'}",
        "AIUI_NON_DISPLAY_RUNTIME_SUPPORT_PROVEN=NO",
        f"NEXT_ACTION={next_action}",
        "DEVICE_MUTATION=NONE",
        "PHOTO_OPERATION=NONE",
        "AUDIO_OPERATION=NONE",
    ]
    txt_path = sanitized / "test21-r1-summary.txt"
    txt_path.write_text("\n".join(txt) + "\n", encoding="utf-8")

    sums = []
    for p in (json_path, txt_path):
        sums.append(f"{sha256(p)}  {p.name}")
    (sanitized / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")

    for line in txt:
        print(line)
    if collection_failures:
        print(f"COLLECTION_NONZERO_STEP_COUNT={len(collection_failures)}")
    else:
        print("COLLECTION_NONZERO_STEP_COUNT=0")
    print(f"SANITIZED_SUMMARY={json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
