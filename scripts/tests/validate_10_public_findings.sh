#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-.}"
cd "$REPO"

required=(
  "README.md"
  "docs/methodology/test-methodology.md"
  "docs/tests/test-matrix.md"
  "docs/tests/10-translation-overview.md"
  "docs/tests/10a-face-to-face-input-routing.md"
  "docs/tests/10b-online-translation-services.md"
  "docs/tests/10c1-local-model-download.md"
  "docs/tests/10c2-local-model-package.md"
  "docs/tests/10c3-offline-local-execution.md"
  "docs/tests/10c4-local-vs-online-flow.md"
  "docs/findings/translation-architecture.md"
  "docs/findings/local-model-wend.md"
  "docs/findings/translation-network-routing.md"
  "docs/runbooks/10-translation.md"
  "evidence/README.md"
  "evidence/sanitized/10/README.md"
  "evidence/sanitized/10/endpoint-summary.md"
  "evidence/sanitized/10/local-model-metadata.md"
  "evidence/sanitized/10/offline-execution-summary.md"
  "evidence/sanitized/10/local-vs-online-summary.md"
  "evidence/manifests/10-private-evidence-sha256.json"
)

for path in "${required[@]}"; do
  [[ -f "$path" ]] || {
    echo "ERROR: missing required Test 10 file: $path" >&2
    exit 1
  }
done

grep -q -F 'Validated through **Test 10c4**' README.md
grep -q -F 'centralus.api.cognitive.microsoft.com' docs/tests/10b-online-translation-services.md
grep -q -F '1,019,916,502 bytes' docs/tests/10c1-local-model-download.md
grep -q -F '596,049,920' docs/tests/10c2-local-model-package.md
grep -q -F 'Google Android offline TTS' docs/tests/10c4-local-vs-online-flow.md
grep -q -F 'Microsoft Azure Speech' docs/findings/translation-architecture.md

python3 - "$PWD" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
manifest_path = root / "evidence/manifests/10-private-evidence-sha256.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

assert manifest["schema"] == "rokid.private-evidence-archive-manifest.v1"
assert manifest["public_test"] == "10"
assert manifest["classification"] == "private-hash-only"
entries = manifest["entries"]
assert len(entries) == 7

for entry in entries:
    assert entry["classification"] == "private-hash-only"
    assert isinstance(entry["size_bytes"], int) and entry["size_bytes"] > 0
    assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
    assert entry["filename"].endswith(".zip")
    assert entry["public_test"].startswith("10")

sanitized = root / "evidence/sanitized/10"
for path in sanitized.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix.lower() in {
        ".pcap", ".pcapng", ".zip", ".log", ".png", ".jpg", ".jpeg",
        ".bin", ".gguf", ".onnx", ".apk", ".apks"
    }:
        raise AssertionError(f"forbidden Test 10 public artifact: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    forbidden = [
        r"/Users/",
        r"/sdcard/",
        r"(?i)\bdevice_sn\b",
        r"(?i)\buser_id\b",
        r"(?i)\blatitude\b",
        r"(?i)\blongitude\b",
        r"(?i)\baccess_token\b",
        r"(?i)\bauthorization:\s",
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])",
    ]
    for pattern in forbidden:
        if re.search(pattern, text):
            raise AssertionError(f"private pattern {pattern!r} in {path}")

link_files = [
    root / "README.md",
    root / "docs/tests/10-translation-overview.md",
    root / "evidence/sanitized/10/README.md",
]
link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
for source in link_files:
    text = source.read_text(encoding="utf-8")
    for target in link_re.findall(text):
        if "://" in target or target.startswith("#"):
            continue
        resolved = (source.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            raise AssertionError(f"broken relative link in {source}: {target}")

print("Test 10 structure and manifest validation: PASS")
PY

if [[ -x scripts/validate_public_tree.py ]]; then
  python3 scripts/validate_public_tree.py --root .
fi

git diff --check

echo "Test 10 public findings validation: PASS"
