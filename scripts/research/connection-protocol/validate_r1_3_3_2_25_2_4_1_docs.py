#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

RELEASE = "r1.3.3.2.25.2.4.1"
RESULT = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS"

REQUIRED = [
    "README.md",
    "ARCHITECTURE.md",
    "docs/README.md",
    "docs/project-status.md",
    "docs/research/README.md",
    "docs/research/connection-protocol/README.md",
    "docs/tests/test-matrix.md",
    "docs/architecture/README.md",
    "docs/architecture/non-display-system-architecture.md",
    "android-client/README.md",
]

FINAL_TARGETS = [
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md",
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json",
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-methodology.md",
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-limitations.md",
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt",
    "docs/research/connection-protocol/r1.3.3.2.25.2.4-supersession-map.json",
]

STALE = [
    "research release r1.3.3.2.24.1",
    "Project Status Through r24.1",
    "Bluetooth service/channel identity | Pending r25 live capture",
    "Independent Android companion client | Not implemented",
    "Live qualification remains pending until device evidence passes",
    "RFCOMM connect/close without payload I/O: implemented, device qualification pending",
    "Exact GATT/RFCOMM/channel framing | Partial; not independently implemented",
]

PRIVATE = [
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
    re.compile(r"(?i)(?:phone[_ -]?serial|serial[_ -]?number)\s*[:=]\s*[A-Za-z0-9._:-]{6,}"),
    re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}"),
    re.compile(r"(?i)Glasses_[A-Za-z0-9]{4,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str) -> None:
    print(f"R25_2_4_1_VALIDATION_ERROR={msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--contract")
    ap.add_argument("--allow-missing-final-targets", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").exists():
        fail("repo_not_git")

    texts: dict[str, str] = {}
    for rel in REQUIRED:
        p = repo / rel
        if not p.is_file():
            fail(f"missing_required:{rel}")
        raw = p.read_bytes()
        if b"\x00" in raw:
            fail(f"binary_document:{rel}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            fail(f"non_utf8:{rel}")
        if "\r" in text:
            fail(f"crlf:{rel}")
        for i, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                fail(f"trailing_whitespace:{rel}:{i}")
        texts[rel] = text

    combined = "\n".join(texts.values())
    for s in STALE:
        if s in combined:
            fail(f"stale_text:{s}")
    for pattern in PRIVATE:
        if pattern.search(combined):
            fail(f"private_value:{pattern.pattern}")

    required_markers = {
        "README.md": [RELEASE, RESULT, "TX 0 bytes", "RX 0 bytes", "CXR/application framing"],
        "ARCHITECTURE.md": ["Known independent RFCOMM transport", "SCN 3 / DLCI 6 / MTU 990", "Unknown authenticated ADB enable/disable command"],
        "docs/project-status.md": ["Project Status Through r1.3.3.2.25.2.4", RESULT, "r1.3.3.2.25.3"],
        "docs/research/README.md": [RESULT, "Connection-only Android client"],
        "docs/research/connection-protocol/README.md": [RESULT, "TX `0` bytes / RX `0` bytes", "Next boundary"],
        "docs/tests/test-matrix.md": ["r1.3.3.2.25.2.3.2", "r1.3.3.2.25.2.4", "Capability status after r1.3.3.2.25.2.4"],
        "android-client/README.md": ["device-qualified **connection-only RFCOMM client**", "application-payload RFCOMM reads or writes"],
        "docs/architecture/non-display-system-architecture.md": ["Independent RFCOMM transport foundation", "Proven zero in both directions"],
    }
    for rel, markers in required_markers.items():
        for marker in markers:
            if marker not in texts[rel]:
                fail(f"missing_marker:{rel}:{marker}")

    root_links = [
        "r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md",
        "r1.3.3.2.25.2.4-runtime-status-summary.json",
        "r1.3.3.2.25.2.4-methodology.md",
        "r1.3.3.2.25.2.4-limitations.md",
        "r1.3.3.2.25.2.4-evidence-hashes.txt",
        "r1.3.3.2.25.2.4-supersession-map.json",
        "docs/research/connection-protocol/README.md",
        "android-client/README.md",
    ]
    for link in root_links:
        if link not in texts["README.md"]:
            fail(f"root_navigation_missing:{link}")

    if not args.allow_missing_final_targets:
        for rel in FINAL_TARGETS:
            if not (repo / rel).is_file():
                fail(f"missing_final_target:{rel}")

    # Validate the public machine-readable result when available.
    status_path = repo / FINAL_TARGETS[1]
    if status_path.is_file():
        data = json.loads(status_path.read_text(encoding="utf-8"))
        if data.get("qualification_outcome") != RESULT:
            fail("runtime_status_result_mismatch")
        gates = data.get("gates", {})
        if gates.get("tx_payload_bytes") != 0 or gates.get("rx_payload_bytes") != 0:
            fail("runtime_status_payload_not_zero")
        if not gates.get("full_zero_payload_closure_proven"):
            fail("runtime_status_closure_not_proven")

    if args.contract:
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        for rel, expected in contract["postimage_sha256"].items():
            actual = digest(repo / rel)
            if actual != expected:
                fail(f"postimage_hash:{rel}:{actual}")
        print("R25_2_4_1_POSTIMAGE_HASH_GATE=PASS")

    if texts["ARCHITECTURE.md"].count("```mermaid") != texts["ARCHITECTURE.md"].count("```") - 0:
        # We do not require every code fence to be mermaid; just ensure all fences pair.
        pass
    for rel, text in texts.items():
        if text.count("```") % 2:
            fail(f"unbalanced_fence:{rel}")

    print("R25_2_4_1_ROOT_CURRENT_STATE_GATE=PASS")
    print("R25_2_4_1_RESEARCH_NAVIGATION_GATE=PASS")
    print("R25_2_4_1_REPLACEMENT_APP_READINESS_GATE=PASS")
    print("R25_2_4_1_PRIOR_BOUNDED_SUPERSESSION_GATE=PASS")
    print("R25_2_4_1_DOCUMENT_PRIVACY_GATE=PASS")
    print("R25_2_4_1_MARKDOWN_HYGIENE_GATE=PASS")
    print("R1_3_3_2_25_2_4_1_INSTALLED_VALIDATION=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
