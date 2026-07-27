#!/usr/bin/env bash
set -euo pipefail

REPO=""
SOURCE_RUN=""
SOURCE_PRIVATE_ZIP=""
OUTPUT=""
TEMP_DIR=""

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_2_2_1.sh \
    --repo PATH \
    (--source-run PATH | --source-private-zip PATH) \
    --output PATH

Performs offline bounded reanalysis of accepted r25.2.2 evidence. It invokes no
ADB, Bluetooth connection, GATT, RFCOMM, or application-payload operation.
EOF
}

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT INT TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:?missing repo}"; shift 2 ;;
    --source-run) SOURCE_RUN="${2:?missing source run}"; shift 2 ;;
    --source-private-zip) SOURCE_PRIVATE_ZIP="${2:?missing source ZIP}"; shift 2 ;;
    --output) OUTPUT="${2:?missing output}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$OUTPUT" ]] || { usage >&2; exit 2; }
if [[ -n "$SOURCE_RUN" && -n "$SOURCE_PRIVATE_ZIP" ]] || \
   [[ -z "$SOURCE_RUN" && -z "$SOURCE_PRIVATE_ZIP" ]]; then
  echo "ERROR: specify exactly one source input" >&2
  exit 2
fi

REPO="$(cd "$REPO" && pwd -P)"
OUTPUT="$(python3 - "$OUTPUT" <<'PY'
import os
import sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
)"
case "$OUTPUT" in
  ""|"."|"/"|"$REPO"|"$REPO"/*)
    echo "ERROR: unsafe output path: $OUTPUT" >&2
    exit 1
    ;;
esac
[[ ! -e "$OUTPUT" ]] || {
  echo "ERROR: output already exists: $OUTPUT" >&2
  exit 1
}

SOURCE_ZIP_HASH=""
if [[ -n "$SOURCE_PRIVATE_ZIP" ]]; then
  SOURCE_PRIVATE_ZIP="$(python3 - "$SOURCE_PRIVATE_ZIP" <<'PY'
import os
import sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
)"
  [[ -f "$SOURCE_PRIVATE_ZIP" ]] || {
    echo "ERROR: source private ZIP not found" >&2
    exit 1
  }
  SOURCE_ZIP_HASH="$(shasum -a 256 "$SOURCE_PRIVATE_ZIP" | awk '{print $1}')"
  TEMP_DIR="$(mktemp -d)"
  unzip -q "$SOURCE_PRIVATE_ZIP" -d "$TEMP_DIR"
  ROOT_COUNT="$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d -print | wc -l | tr -d ' ')"
  [[ "$ROOT_COUNT" == "1" ]] || {
    echo "ERROR: source ZIP must contain exactly one run root" >&2
    exit 1
  }
  SOURCE_RUN="$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d -print | head -n1)"
else
  SOURCE_RUN="$(cd "$SOURCE_RUN" && pwd -P)"
fi

for relative in \
  client-probe-private.jsonl \
  stock-assist-logcat-private.txt \
  run-metadata-private.json
do
  [[ -f "$SOURCE_RUN/$relative" ]] || {
    echo "ERROR: source evidence missing: $relative" >&2
    exit 1
  }
done

mkdir -p "$OUTPUT/analysis" "$OUTPUT/publication" "$OUTPUT/handoff"

python3 - "$SOURCE_RUN" "$SOURCE_ZIP_HASH" "$OUTPUT/source-lineage-private.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

source = Path(sys.argv[1]).resolve()
zip_hash = sys.argv[2] or None
out = Path(sys.argv[3])
files = []
for relative in (
    "client-probe-private.jsonl",
    "stock-assist-logcat-private.txt",
    "run-metadata-private.json",
    "correlation-key-private.hex",
    "phone-bugreport-private.zip",
    "analysis/r25.2.2-private-analysis.json",
    "publication/r25.2.2-stock-assisted-attribution.json",
):
    path = source / relative
    if not path.is_file():
        continue
    files.append({
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
value = {
    "schema": "rokid.r25.2.2.1.source-lineage-private.v1",
    "release": "r1.3.3.2.25.2.2.1",
    "source_release": "r1.3.3.2.25.2.2",
    "source_run_name": source.name,
    "source_private_zip_sha256": zip_hash,
    "source_files": files,
    "offline_reanalysis_only": True,
}
out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

SCRIPT_DIR="$REPO/scripts/research/connection-protocol"
ARGS=(
  --client-log "$SOURCE_RUN/client-probe-private.jsonl"
  --stock-logcat "$SOURCE_RUN/stock-assist-logcat-private.txt"
  --run-metadata "$SOURCE_RUN/run-metadata-private.json"
  --private-output "$OUTPUT/analysis/r25.2.2.1-private-analysis.json"
  --public-output "$OUTPUT/publication/r25.2.2.1-cached-runtime-attribution.json"
  --handoff-output "$OUTPUT/handoff/r25.2.2.1-connection-only-handoff-private.json"
)
[[ -f "$SOURCE_RUN/correlation-key-private.hex" ]] && \
  ARGS+=(--correlation-key "$SOURCE_RUN/correlation-key-private.hex")
[[ -f "$SOURCE_RUN/phone-bugreport-private.zip" ]] && \
  ARGS+=(--bugreport "$SOURCE_RUN/phone-bugreport-private.zip")

python3 "$SCRIPT_DIR/analyze_r25_2_2_1_cached_runtime.py" "${ARGS[@]}"
python3 "$SCRIPT_DIR/verify_r25_2_2_1_publication.py" \
  --publication "$OUTPUT/publication/r25.2.2.1-cached-runtime-attribution.json"
python3 "$SCRIPT_DIR/finalize_r25_2_2_1.py" --run "$OUTPUT"

ACCEPTANCE="$(python3 - "$OUTPUT/publication/r25.2.2.1-cached-runtime-attribution.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["acceptance"])
PY
)"

echo "R1_3_3_2_25_2_2_1_RUN=PASS"
echo "R1_3_3_2_25_2_2_1_ACCEPTANCE=$ACCEPTANCE"
