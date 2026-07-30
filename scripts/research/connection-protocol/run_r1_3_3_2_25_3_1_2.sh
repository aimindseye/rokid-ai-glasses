#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_3_1_2.sh \
    --repo <rokid-ai-glasses-repo> \
    --source-output <completed-r25.3.1.1-output> \
    --output <new-offline-analysis-output>

This runner is host-only. It does not invoke adb, fastboot, or any device API.
EOF
}

REPO=""
SOURCE_OUTPUT=""
OUTPUT=""

while (($#)); do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --source-output) SOURCE_OUTPUT="${2:-}"; shift 2 ;;
    --output) OUTPUT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$SOURCE_OUTPUT" && -n "$OUTPUT" ]] || {
  usage >&2
  exit 2
}

REPO="$(cd "$REPO" && pwd -P)"
SOURCE_OUTPUT="$(cd "$SOURCE_OUTPUT" && pwd -P)"
OUTPUT_PARENT="$(dirname "$OUTPUT")"
OUTPUT_NAME="$(basename "$OUTPUT")"
mkdir -p "$OUTPUT_PARENT"
OUTPUT_PARENT="$(cd "$OUTPUT_PARENT" && pwd -P)"
OUTPUT="$OUTPUT_PARENT/$OUTPUT_NAME"

ANALYZER="$REPO/scripts/research/connection-protocol/r25_3_1_2_analyze.py"
CAPTURE="$SOURCE_OUTPUT/evidence"
METADATA="$CAPTURE/metadata.json"
BUGREPORT="$CAPTURE/bugreport.zip"

for required in "$ANALYZER" "$METADATA" "$BUGREPORT"; do
  [[ -f "$required" && ! -L "$required" ]] || {
    echo "ERROR: missing regular file: $required" >&2
    exit 3
  }
done

[[ ! -e "$OUTPUT" ]] || {
  echo "ERROR: output already exists: $OUTPUT" >&2
  exit 3
}

python3 - "$METADATA" <<'PY'
from pathlib import Path
import json
import sys

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if metadata.get("schema") != "rokid.r25.3.1.1.capture-metadata.v1":
    raise SystemExit("FAIL: unexpected source metadata schema")
if metadata.get("release") != "r1.3.3.2.25.3.1.1":
    raise SystemExit("FAIL: unexpected source capture release")
if metadata.get("custom_transmission_attempted") is not False:
    raise SystemExit("FAIL: source does not prove custom_transmission_attempted=false")
if metadata.get("captured_payload_replay_attempted") is not False:
    raise SystemExit("FAIL: source does not prove captured_payload_replay_attempted=false")
print("R25_3_1_2_SOURCE_CAPTURE_METADATA_GATE=PASS")
PY

mkdir -p "$OUTPUT"
LINEAGE="$OUTPUT/source-lineage-private.json"
python3 - "$SOURCE_OUTPUT" "$METADATA" "$BUGREPORT" "$LINEAGE" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

source = Path(sys.argv[1])
metadata = Path(sys.argv[2])
bugreport = Path(sys.argv[3])
lineage = Path(sys.argv[4])

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

lineage.write_text(
    json.dumps(
        {
            "schema": "rokid.r25.3.1.2.source-lineage.v1",
            "source_output": str(source),
            "source_metadata_sha256": sha(metadata),
            "source_bugreport_sha256": sha(bugreport),
            "device_contact": False,
            "stock_toggle_attempted": False,
            "custom_transmission_attempted": False,
            "captured_payload_replay_attempted": False,
        },
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
PY

ANALYSIS_OUTPUT="$OUTPUT/result"
python3 "$ANALYZER" \
  --capture-dir "$CAPTURE" \
  --output-dir "$ANALYSIS_OUTPUT"

PRIVATE_JSON="$ANALYSIS_OUTPUT/analysis/r25.3.1.2-private-analysis.json"
PUBLIC_JSON="$ANALYSIS_OUTPUT/publication/r25.3.1.2-runtime-status-summary.json"

python3 - "$PRIVATE_JSON" "$PUBLIC_JSON" <<'PY'
from pathlib import Path
import json
import sys

private = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
public = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
expected = "PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE"
if private.get("acceptance") != expected or public.get("acceptance") != expected:
    raise SystemExit("FAIL: offline salvage did not reach required acceptance")
selected = private["selected_hci_member"]
if selected.get("target_rfcomm_parse_error_count") != 0:
    raise SystemExit("FAIL: target-pair RFCOMM parse errors remain")
if selected.get("non_target_rfcomm_errors_excluded_from_qualification") is not True:
    raise SystemExit("FAIL: non-target error scoping not proven")
if private["gates"].get("final_semantic_state_restored") is not True:
    raise SystemExit("FAIL: final semantic state restoration not proven")
print("R25_3_1_2_OFFLINE_SALVAGE_ACCEPTANCE_GATE=PASS")
print(f"R25_3_1_2_TARGET_PAIR_COUNT={len(selected.get('target_pairs', []))}")
print(f"R25_3_1_2_TARGET_RFCOMM_PARSE_ERROR_COUNT={selected.get('target_rfcomm_parse_error_count', 0)}")
print(f"R25_3_1_2_NON_TARGET_RFCOMM_PARSE_ERROR_COUNT={selected.get('non_target_rfcomm_parse_error_count', 0)}")
PY

python3 - "$OUTPUT" "$ANALYSIS_OUTPUT" <<'PY'
from pathlib import Path
import hashlib
import zipfile
import sys

output = Path(sys.argv[1])
analysis = Path(sys.argv[2])

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def manifest(root: Path, filename: str) -> Path:
    path = root / filename
    rows = []
    for item in sorted(root.rglob("*")):
        if item.is_file() and item != path:
            rows.append(f"{sha(item)}  {item.relative_to(root).as_posix()}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path

def package(root: Path, destination: Path, manifest_name: str) -> None:
    manifest(root, manifest_name)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(root.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(root).as_posix())

package(analysis, output / "r25.3.1.2-private-analysis.zip", "SHA256SUMS-private-analysis.txt")
package(analysis / "publication", output / "r25.3.1.2-sanitized-publication.zip", "SHA256SUMS-sanitized.txt")
manifest(output, "SHA256SUMS-private.txt")
PY

PRIVATE_ZIP="$OUTPUT/r25.3.1.2-private-analysis.zip"
PUBLIC_ZIP="$OUTPUT/r25.3.1.2-sanitized-publication.zip"

echo "R25_3_1_2_DEVICE_CONTACT=NO"
echo "R25_3_1_2_STOCK_TOGGLE_ATTEMPTED=NO"
echo "R25_3_1_2_CUSTOM_TRANSMISSION_ATTEMPTED=NO"
echo "R25_3_1_2_CAPTURED_PAYLOAD_REPLAY_ATTEMPTED=NO"
echo "R25_3_1_2_PRIVATE_ANALYSIS_ZIP=$PRIVATE_ZIP"
echo "R25_3_1_2_PRIVATE_ANALYSIS_ZIP_SHA256=$(shasum -a 256 "$PRIVATE_ZIP" | awk '{print $1}')"
echo "R25_3_1_2_SANITIZED_PUBLICATION_ZIP=$PUBLIC_ZIP"
echo "R25_3_1_2_SANITIZED_PUBLICATION_ZIP_SHA256=$(shasum -a 256 "$PUBLIC_ZIP" | awk '{print $1}')"
echo "R25_3_1_2_OUTPUT=$OUTPUT"
echo "R1_3_3_2_25_3_1_2_ACCEPTANCE=PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE"
