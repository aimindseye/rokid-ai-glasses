#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_3_1_3.sh \
    --repo <rokid-ai-glasses-repo> \
    --source-private-zip <accepted-r25.3.1.2-private-analysis.zip> \
    --output <new-host-only-analysis-output>

This runner is host-only. It contains no adb, fastboot, device API, payload
transmission, or captured-payload replay operation.
EOF
}

REPO=""
SOURCE_ZIP=""
OUTPUT=""

while (($#)); do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --source-private-zip) SOURCE_ZIP="${2:-}"; shift 2 ;;
    --output) OUTPUT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$SOURCE_ZIP" && -n "$OUTPUT" ]] || {
  usage >&2
  exit 2
}

REPO="$(cd "$REPO" && pwd -P)"
SOURCE_ZIP="$(cd "$(dirname "$SOURCE_ZIP")" && pwd -P)/$(basename "$SOURCE_ZIP")"
OUTPUT_PARENT="$(dirname "$OUTPUT")"
OUTPUT_NAME="$(basename "$OUTPUT")"
mkdir -p "$OUTPUT_PARENT"
OUTPUT_PARENT="$(cd "$OUTPUT_PARENT" && pwd -P)"
OUTPUT="$OUTPUT_PARENT/$OUTPUT_NAME"

ANALYZER="$REPO/scripts/research/connection-protocol/r25_3_1_3_analyze.py"
for required in "$ANALYZER" "$SOURCE_ZIP"; do
  [[ -f "$required" && ! -L "$required" ]] || {
    echo "ERROR: missing regular file: $required" >&2
    exit 3
  }
done
[[ ! -e "$OUTPUT" ]] || {
  echo "ERROR: output already exists: $OUTPUT" >&2
  exit 3
}

mkdir -p "$OUTPUT"
RESULT="$OUTPUT/result"

python3 "$ANALYZER" \
  --source-private-zip "$SOURCE_ZIP" \
  --output-dir "$RESULT"

PRIVATE_JSON="$RESULT/analysis/r25.3.1.3-private-analysis.json"
PUBLIC_JSON="$RESULT/publication/r25.3.1.3-runtime-status-summary.json"

python3 - "$PRIVATE_JSON" "$PUBLIC_JSON" <<'PY'
from pathlib import Path
import json
import sys

private = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
public = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
expected = (
    "PASS_EXISTING_CAPTURE_EXACT_ADB_TOGGLE_APPLICATION_FRAME_GRAMMAR_"
    "NESTED_LENGTH_SEQUENCE_DISCRIMINATOR_AND_STRUCTURED_PAYLOAD_ROLE_CLOSURE"
)
if private.get("acceptance") != expected or public.get("acceptance") != expected:
    raise SystemExit("FAIL: exact frame-grammar acceptance not reached")
for gate in (
    "outer_total_length_closed",
    "nested_total_length_closed",
    "monotonic_sequence_candidate_step_one",
    "disable_repeat_equal_after_sequence_normalization",
    "enable_repeat_equal_after_sequence_normalization",
    "distinct_enable_disable_discriminator",
    "structured_payload_json_decoded",
    "structured_role_correlated_to_ui_and_property",
):
    if private.get("gates", {}).get(gate) is not True:
        raise SystemExit(f"FAIL: required grammar gate not passed: {gate}")
if public.get("privacy", {}).get("raw_payload_hex_present") is not False:
    raise SystemExit("FAIL: public output reports raw payload hex")
print("R25_3_1_3_EXACT_GRAMMAR_ACCEPTANCE_GATE=PASS")
PY

python3 - "$OUTPUT" "$RESULT" "$SOURCE_ZIP" <<'PY'
from pathlib import Path
import hashlib
import json
import zipfile
import sys

output = Path(sys.argv[1])
result = Path(sys.argv[2])
source = Path(sys.argv[3])

def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def write_manifest(root: Path, name: str, excluded: set[Path] | None = None) -> Path:
    excluded = excluded or set()
    destination = root / name
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != destination and path not in excluded:
            rows.append(f"{sha(path)}  {path.relative_to(root).as_posix()}")
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return destination

def package(root: Path, destination: Path, manifest_name: str) -> None:
    write_manifest(root, manifest_name)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())

lineage = output / "source-lineage-private.json"
lineage.write_text(
    json.dumps(
        {
            "schema": "rokid.r25.3.1.3.source-lineage.v1",
            "source_private_zip": str(source),
            "source_private_zip_sha256": sha(source),
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

package(result, output / "r25.3.1.3-private-analysis.zip", "SHA256SUMS-private-analysis.txt")
package(result / "publication", output / "r25.3.1.3-sanitized-publication.zip", "SHA256SUMS-sanitized.txt")
write_manifest(
    output,
    "SHA256SUMS-private.txt",
    excluded={output / "SHA256SUMS-private.txt"},
)
PY

PRIVATE_ZIP="$OUTPUT/r25.3.1.3-private-analysis.zip"
PUBLIC_ZIP="$OUTPUT/r25.3.1.3-sanitized-publication.zip"

echo "R25_3_1_3_DEVICE_CONTACT=NO"
echo "R25_3_1_3_STOCK_TOGGLE_ATTEMPTED=NO"
echo "R25_3_1_3_CUSTOM_TRANSMISSION_ATTEMPTED=NO"
echo "R25_3_1_3_CAPTURED_PAYLOAD_REPLAY_ATTEMPTED=NO"
echo "R25_3_1_3_PRIVATE_ANALYSIS_ZIP=$PRIVATE_ZIP"
echo "R25_3_1_3_PRIVATE_ANALYSIS_ZIP_SHA256=$(shasum -a 256 "$PRIVATE_ZIP" | awk '{print $1}')"
echo "R25_3_1_3_SANITIZED_PUBLICATION_ZIP=$PUBLIC_ZIP"
echo "R25_3_1_3_SANITIZED_PUBLICATION_ZIP_SHA256=$(shasum -a 256 "$PUBLIC_ZIP" | awk '{print $1}')"
echo "R25_3_1_3_OUTPUT=$OUTPUT"
echo "R1_3_3_2_25_3_1_3_ACCEPTANCE=PASS_EXISTING_CAPTURE_EXACT_ADB_TOGGLE_APPLICATION_FRAME_GRAMMAR_NESTED_LENGTH_SEQUENCE_DISCRIMINATOR_AND_STRUCTURED_PAYLOAD_ROLE_CLOSURE"
