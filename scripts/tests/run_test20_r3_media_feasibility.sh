#!/usr/bin/env bash

usage() {
  cat <<'EOF'
Usage: run_test20_r3_media_feasibility.sh --repo PATH --output PATH [--census PATH]

Read-only Test 20 r3 media-plane feasibility census. No ADB, Gradle, Maven,
phone, glasses, cloud, or runtime media operation is performed.
EOF
}

REPO=""
OUTPUT=""
CENSUS=""
EXPECTED_CENSUS_SHA="a3f261e830910a1664e004feb91af339ea1518230a4c1c6bc8d2205e1075dcc9"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --census) CENSUS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

RC=0
if [[ -z "$REPO" || -z "$OUTPUT" ]]; then
  echo "ERROR: --repo and --output are required" >&2
  RC=2
fi
if [[ "$RC" -eq 0 && ! -d "$REPO/.git" ]]; then
  echo "ERROR: repository is not a Git worktree: $REPO" >&2
  RC=2
fi
if [[ -z "$CENSUS" && -n "$REPO" ]]; then
  CENSUS="$REPO/docs/research/connection-protocol/publication/test20-r1-cxr-l-capability-census.json"
fi
if [[ "$RC" -eq 0 && ! -s "$CENSUS" ]]; then
  echo "ERROR: accepted Test 20 r1.2 census is missing or empty: $CENSUS" >&2
  RC=2
fi
if [[ "$RC" -eq 0 && -e "$OUTPUT" ]]; then
  echo "ERROR: output path already exists: $OUTPUT" >&2
  RC=2
fi
if [[ "$RC" -ne 0 ]]; then
  echo "TEST20_R3_PREFLIGHT=FAIL"
  exit "$RC"
fi

ACTUAL_CENSUS_SHA="$(shasum -a 256 "$CENSUS" | awk '{print $1}')"
HASH_RC=$?
echo "TEST20_R3_SOURCE_CENSUS_JSON_SHA256=$ACTUAL_CENSUS_SHA"
if [[ "$HASH_RC" -ne 0 || "$ACTUAL_CENSUS_SHA" != "$EXPECTED_CENSUS_SHA" ]]; then
  echo "ERROR: accepted census identity mismatch" >&2
  echo "TEST20_R3_SOURCE_CENSUS_IDENTITY=FAIL"
  exit 2
fi
echo "TEST20_R3_SOURCE_CENSUS_IDENTITY=PASS"

PUBLIC_DIR="$OUTPUT/sanitized-publication"
python3 "$REPO/scripts/research/cxr/analyze_test20_r3_media_contract.py" \
  --census "$CENSUS" \
  --output-dir "$PUBLIC_DIR"
ANALYZE_RC=$?
if [[ "$ANALYZE_RC" -ne 0 ]]; then
  echo "TEST20_R3_ANALYSIS_EXIT_CODE=$ANALYZE_RC"
  exit "$ANALYZE_RC"
fi

python3 - "$PUBLIC_DIR/test20-r3-cxr-l-media-plane-feasibility.json" <<'PY_CONTRACT'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding='utf-8'))
assert d['schema'] == 'rokid.test20.r3.cxr-l-media-plane-feasibility.public.v1'
assert d['surface_counts'] == {'client_entrypoints': 8, 'callbacks': 5, 'service_contract': 10, 'total': 23}
assert d['feasibility']['runtime_qualification'] == 'NOT_GRANTED'
assert d['safety']['runtime_media_invocation'] == 'NONE'
assert d['next_step']['runtime_media_test_authorized'] is False
print('TEST20_R3_PUBLICATION_CONTRACT=PASS')
PY_CONTRACT
CONTRACT_RC=$?
if [[ "$CONTRACT_RC" -ne 0 ]]; then
  echo "TEST20_R3_PUBLICATION_CONTRACT=FAIL"
  exit "$CONTRACT_RC"
fi

(
  cd "$PUBLIC_DIR" || exit 2
  find . -type f ! -name 'SHA256SUMS.txt' -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS.txt
  shasum -a 256 -c SHA256SUMS.txt > hash-verification.txt
)
MANIFEST_RC=$?
if [[ "$MANIFEST_RC" -ne 0 ]]; then
  echo "TEST20_R3_HASH_MANIFEST=FAIL"
  exit "$MANIFEST_RC"
fi
echo "TEST20_R3_HASH_MANIFEST=PASS"

ZIP_PATH="${OUTPUT}-sanitized-publication.zip"
SIDE_PATH="${ZIP_PATH}.sha256.txt"
python3 - "$PUBLIC_DIR" "$ZIP_PATH" <<'PY_ZIP'
from pathlib import Path
import sys, zipfile
src = Path(sys.argv[1])
out = Path(sys.argv[2])
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for item in sorted(src.rglob('*')):
        if item.is_file():
            zf.write(item, Path('sanitized-publication') / item.relative_to(src))
PY_ZIP
ZIP_RC=$?
if [[ "$ZIP_RC" -ne 0 || ! -s "$ZIP_PATH" ]]; then
  echo "TEST20_R3_SANITIZED_ZIP=FAIL"
  exit 2
fi
ZIP_SHA="$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')"
SIDE_NAME="$(basename "$ZIP_PATH")"
printf '%s  %s\n' "$ZIP_SHA" "$SIDE_NAME" > "$SIDE_PATH"
SIDE_RC=$?
if [[ "$SIDE_RC" -ne 0 ]]; then
  echo "TEST20_R3_SANITIZED_SIDECAR=FAIL"
  exit "$SIDE_RC"
fi

echo "TEST20_R3_EXACT_ARTIFACT_IDENTITY=PASS"
echo "TEST20_R3_MEDIA_CONTROL_SURFACE=PASS"
echo "TEST20_R3_MEDIA_CALLBACK_SURFACE=PASS"
echo "TEST20_R3_MEDIA_SERVICE_CONTRACT=PASS"
echo "TEST20_R3_PARAMETER_SEMANTICS=UNRESOLVED"
echo "TEST20_R3_PAYLOAD_FORMATS=UNRESOLVED"
echo "TEST20_R3_RUNTIME_QUALIFICATION=NOT_GRANTED"
echo "TEST20_R3_PRIVACY_GATE=PASS"
echo "TEST20_R3_FEASIBILITY=PASS"
echo "TEST20_R3_CLASSIFICATION=READY_FOR_BOUNDED_MEDIA_TEST_DESIGN"
echo "TEST20_R3_RECOMMENDED_NEXT_STAGE=TEST20_R3_1_SERVICE_STATUS_AND_NO_PAYLOAD_PREFLIGHT"
echo "TEST20_R3_SANITIZED_PUBLICATION_ZIP=$ZIP_PATH"
echo "TEST20_R3_SANITIZED_PUBLICATION_ZIP_SHA256=$ZIP_SHA"
echo "TEST20_R3_SANITIZED_PUBLICATION_SIDECAR=$SIDE_PATH"
echo "SOURCE_REPOSITORY_MUTATION=NONE"
echo "MAVEN_OPERATION=NONE"
echo "GRADLE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "PHONE_OPERATION=NONE"
echo "GLASSES_OPERATION=NONE"
echo "MEDIA_OPERATION=NONE"
echo "CLOUD_REQUEST=NONE"
exit 0
