#!/usr/bin/env bash
# Test 20 r1: exact read-only CXR-L SDK and Hi Rokid capability census.
# This script never enables errexit, nounset, or pipefail and performs no ADB.

RESULT=0
REPO=""
CXR_L_VERSION="1.0.1"
HI_ROKID_PRIVATE_ZIP=""
OUTPUT=""
EXPECTED_BASELINE_SHA256="b75e7ea3da7c164493c24efdcd411ef70d51c214e82f2b99af7a69ab2cab134e"

usage() {
  cat <<'TXT'
Usage: bash scripts/tests/run_test20_r1_census.sh [options]

Required:
  --hi-rokid-private-zip PATH   Exact installed Hi Rokid baseline ZIP

Options:
  --repo PATH                   Repository root
  --sdk-version 1.0.1           Exact attested CXR-L version
  --output PATH                 New private output directory
  --help                        Show this help

The run resolves the exact Maven artifact, verifies AAR/POM hashes, inventories
all public SDK and JNI surfaces, compares the three exported Hi Rokid CXR-L
components, classifies surfaces, and produces a sanitized publication. It does
not call adb, access media, invoke cloud AI, or send a command to the glasses.
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --sdk-version) CXR_L_VERSION="$2"; shift 2 ;;
    --hi-rokid-private-zip) HI_ROKID_PRIVATE_ZIP="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage; exit 64 ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
fi
REPO="$(cd "$REPO" 2>/dev/null && pwd)"
if [ -z "$REPO" ]; then echo "ERROR: repository path cannot be resolved" >&2; exit 1; fi

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
JAVA_CANDIDATE="${TEST20_JAVA_HOME:-$HOME/Library/Java/JavaVirtualMachines/temurin-23.0.2/Contents/Home}"
if [ ! -x "$JAVA_CANDIDATE/bin/java" ] && [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  JAVA_CANDIDATE="$JAVA_HOME"
fi
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUTPUT" ]; then
  OUTPUT="$HOME/rokid-nettest/private/test20-r1-cxr-l-capability-census-$STAMP"
fi

MAVEN_DIR="$OUTPUT/maven"
PRIVATE_DIR="$OUTPUT/census-private"
PUBLIC_DIR="$OUTPUT/sanitized-publication"
RUNTIME_PUBLICATION="$REPO/docs/research/connection-protocol/publication/test19-r2-cxr-l-firmware-comparison.json"
RESOLVER="$REPO/scripts/research/cxr/resolve_cxr_l_maven.py"
SDK_CENSUS="$REPO/scripts/research/cxr/census_cxr_l_sdk.py"
HI_CENSUS="$REPO/scripts/research/cxr/census_hi_rokid_cxrl.py"
CLASSIFIER="$REPO/scripts/research/cxr/classify_cxr_l_capabilities.py"
PRIVATE_ZIP="${OUTPUT}-private-evidence.zip"
PUBLIC_ZIP="${OUTPUT}-sanitized-publication.zip"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; RESULT=1; }

find_aapt() {
  python3 - "$ANDROID_HOME" <<'PY'
from pathlib import Path
import re, sys
root=Path(sys.argv[1])/'build-tools'
items=[]
if root.is_dir():
    for child in root.iterdir():
        tool=child/'aapt'
        if tool.is_file():
            parts=tuple(int(x) for x in re.findall(r'\d+', child.name))
            items.append((parts, str(tool)))
if items:
    print(max(items)[1])
PY
}

hash_tree() {
  root="$1"
  manifest="$2"
  verification="$3"
  rm -f "$manifest" "$verification"
  (
    cd "$root" || exit 91
    find . -type f \
      ! -name "$(basename "$manifest")" \
      ! -name "$(basename "$verification")" \
      -print0 |
      LC_ALL=C sort -z |
      xargs -0 shasum -a 256 >"$(basename "$manifest")"
  ) || return 1
  (
    cd "$root" || exit 91
    shasum -a 256 -c "$(basename "$manifest")"
  ) >"$verification" 2>&1 || return 1
  return 0
}

make_zip() {
  source="$1"
  destination="$2"
  python3 - "$source" "$destination" <<'PY'
from pathlib import Path
import sys, zipfile
source=Path(sys.argv[1]).resolve(); destination=Path(sys.argv[2]).resolve()
with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(source.rglob('*')):
        if path.is_file():
            archive.write(path, arcname=f"{source.name}/{path.relative_to(source).as_posix()}")
PY
}

sanitize_gate() {
  python3 - "$PUBLIC_DIR" <<'PY'
from pathlib import Path
import re, sys
root=Path(sys.argv[1]); errors=[]
patterns=[
    re.compile(r'/Users/[A-Za-z0-9._-]+'),
    re.compile(r'\b(?:[0-9A-F]{2}:){5}[0-9A-F]{2}\b', re.I),
    re.compile(r'\bBearer\s+[A-Za-z0-9._~-]{12,}', re.I),
    re.compile(r'PHONE_SERIAL_PRIVATE'),
    re.compile(r'PHONE_SERIAL='),
]
for path in root.rglob('*'):
    if not path.is_file(): continue
    text=path.read_text(encoding='utf-8', errors='replace')
    for pattern in patterns:
        if pattern.search(text): errors.append(f'{path.name}:{pattern.pattern}')
if errors:
    print('SANITIZED_PUBLICATION_PRIVACY_GATE=FAIL')
    for item in errors: print(item)
    raise SystemExit(1)
print('SANITIZED_PUBLICATION_PRIVACY_GATE=PASS')
PY
}

echo "Test 20 r1 — CXR-L SDK and Runtime Capability Census"
echo "======================================================="
echo "REPO=$REPO"
echo "CXR_L_VERSION=$CXR_L_VERSION"
echo "HI_ROKID_PRIVATE_ZIP=$HI_ROKID_PRIVATE_ZIP"
echo "OUTPUT=$OUTPUT"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME_SELECTED=$JAVA_CANDIDATE"
echo "ADB_OPERATION=NONE"
echo "PHONE_MUTATION=NONE"
echo "MEDIA_ACCESS=NONE"
echo "CLOUD_AI_REQUEST=NONE"
echo "GLASSES_COMMAND_EXECUTION=NONE"
echo

if [ "$CXR_L_VERSION" != "1.0.1" ]; then fail "only CXR-L 1.0.1 is accepted"; fi
if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
if [ -n "$(git -C "$REPO" status --porcelain=v1 --untracked-files=no 2>/dev/null)" ]; then
  fail "tracked repository changes are present"
  git -C "$REPO" status --short --untracked-files=no >&2
fi
if [ -z "$HI_ROKID_PRIVATE_ZIP" ] || [ ! -f "$HI_ROKID_PRIVATE_ZIP" ]; then fail "--hi-rokid-private-zip is required"; fi
if [ -e "$OUTPUT" ] || [ -e "$PRIVATE_ZIP" ] || [ -e "$PUBLIC_ZIP" ]; then fail "output or output ZIP already exists"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/javap" ]; then fail "javap is unavailable"; fi
for required in "$RESOLVER" "$SDK_CENSUS" "$HI_CENSUS" "$CLASSIFIER" "$RUNTIME_PUBLICATION"; do
  if [ ! -f "$required" ]; then fail "required input is missing: $required"; fi
done
AAPT="${TEST20_AAPT:-$(find_aapt)}"
if [ ! -x "$AAPT" ]; then fail "aapt is unavailable under Android build-tools"; fi
if [ -f "$HI_ROKID_PRIVATE_ZIP" ]; then
  BASELINE_SHA="$(shasum -a 256 "$HI_ROKID_PRIVATE_ZIP" | awk '{print $1}')"
  echo "HI_ROKID_BASELINE_ZIP_SHA256=$BASELINE_SHA"
  if [ "$BASELINE_SHA" != "$EXPECTED_BASELINE_SHA256" ]; then fail "Hi Rokid baseline ZIP hash mismatch"; fi
fi

if [ "$RESULT" -ne 0 ]; then
  echo "TEST20_R1_CENSUS=FAIL"
  echo "ADB_OPERATION=NONE"
  echo "PHONE_MUTATION=NONE"
  echo "GLASSES_COMMAND_EXECUTION=NONE"
  exit "$RESULT"
fi

mkdir -p "$MAVEN_DIR" "$PRIVATE_DIR" "$PUBLIC_DIR"
CREATE_RC=$?
echo "TEST20_R1_OUTPUT_CREATE_EXIT_CODE=$CREATE_RC"
if [ "$CREATE_RC" -ne 0 ]; then fail "output creation failed"; fi

if [ "$RESULT" -eq 0 ]; then
  python3 "$RESOLVER" \
    --version "$CXR_L_VERSION" \
    --output "$MAVEN_DIR" \
    --javap "$JAVA_CANDIDATE/bin/javap"
  RESOLVE_RC=$?
  echo "TEST20_R1_MAVEN_RESOLVE_EXIT_CODE=$RESOLVE_RC"
  if [ "$RESOLVE_RC" -eq 0 ]; then pass "exact CXR-L Maven artifacts resolved and attested"; else fail "Maven attestation failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  python3 "$SDK_CENSUS" \
    --aar "$MAVEN_DIR/client-l-1.0.1.aar" \
    --pom "$MAVEN_DIR/client-l-1.0.1.pom" \
    --javap "$JAVA_CANDIDATE/bin/javap" \
    --version "$CXR_L_VERSION" \
    --output "$PRIVATE_DIR"
  SDK_RC=$?
  echo "TEST20_R1_SDK_CENSUS_EXIT_CODE=$SDK_RC"
  if [ "$SDK_RC" -eq 0 ]; then pass "complete public SDK and native/JNI census created"; else fail "SDK census failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  python3 "$HI_CENSUS" \
    --baseline-zip "$HI_ROKID_PRIVATE_ZIP" \
    --aapt "$AAPT" \
    --output "$PRIVATE_DIR"
  HI_RC=$?
  echo "TEST20_R1_HI_ROKID_CENSUS_EXIT_CODE=$HI_RC"
  if [ "$HI_RC" -eq 0 ]; then pass "Hi Rokid exported CXR-L component census created"; else fail "Hi Rokid census failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  python3 "$CLASSIFIER" \
    --sdk-census "$PRIVATE_DIR/test20-r1-sdk-census-private.json" \
    --hi-rokid-census "$PRIVATE_DIR/test20-r1-hi-rokid-cxrl-private.json" \
    --runtime-publication "$RUNTIME_PUBLICATION" \
    --output "$PUBLIC_DIR"
  CLASSIFY_RC=$?
  echo "TEST20_R1_CLASSIFICATION_EXIT_CODE=$CLASSIFY_RC"
  if [ "$CLASSIFY_RC" -eq 0 ]; then pass "capability classification and sanitized publication created"; else fail "classification failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  sanitize_gate
  PRIVACY_RC=$?
  echo "TEST20_R1_PRIVACY_GATE_EXIT_CODE=$PRIVACY_RC"
  if [ "$PRIVACY_RC" -ne 0 ]; then fail "sanitized publication privacy gate failed"; fi
fi

cat >"$OUTPUT/run-metadata.txt" <<EOF
SCHEMA=rokid.test20.r1.capability-census.run.v1
CAPTURE_UTC=$STAMP
SOURCE_BRANCH=$(git -C "$REPO" branch --show-current)
SOURCE_HEAD=$(git -C "$REPO" rev-parse HEAD)
CXR_L_VERSION=$CXR_L_VERSION
HI_ROKID_BASELINE_ZIP_SHA256=${BASELINE_SHA:-UNAVAILABLE}
ADB_OPERATION=NONE
PHONE_MUTATION=NONE
MEDIA_ACCESS=NONE
CLOUD_AI_REQUEST=NONE
GLASSES_COMMAND_EXECUTION=NONE
EOF

if [ "$RESULT" -eq 0 ]; then
  hash_tree "$OUTPUT" "$OUTPUT/SHA256SUMS-private.txt" "$OUTPUT/hash-verification.txt"
  HASH_RC=$?
  echo "TEST20_R1_PRIVATE_HASH_EXIT_CODE=$HASH_RC"
  if [ "$HASH_RC" -ne 0 ]; then fail "private evidence hash verification failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  make_zip "$OUTPUT" "$PRIVATE_ZIP"
  PRIVATE_ZIP_RC=$?
  echo "TEST20_R1_PRIVATE_ZIP_EXIT_CODE=$PRIVATE_ZIP_RC"
  if [ "$PRIVATE_ZIP_RC" -ne 0 ]; then fail "private evidence ZIP creation failed"; fi
  make_zip "$PUBLIC_DIR" "$PUBLIC_ZIP"
  PUBLIC_ZIP_RC=$?
  echo "TEST20_R1_SANITIZED_ZIP_EXIT_CODE=$PUBLIC_ZIP_RC"
  if [ "$PUBLIC_ZIP_RC" -ne 0 ]; then fail "sanitized publication ZIP creation failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  PRIVATE_ZIP_SHA="$(shasum -a 256 "$PRIVATE_ZIP" | awk '{print $1}')"
  PUBLIC_ZIP_SHA="$(shasum -a 256 "$PUBLIC_ZIP" | awk '{print $1}')"
  printf '%s  %s\n' "$PRIVATE_ZIP_SHA" "$PRIVATE_ZIP" >"$PRIVATE_ZIP.sha256.txt"
  printf '%s  %s\n' "$PUBLIC_ZIP_SHA" "$PUBLIC_ZIP" >"$PUBLIC_ZIP.sha256.txt"
  echo "TEST20_R1_PRIVATE_EVIDENCE_ZIP_SHA256=$PRIVATE_ZIP_SHA"
  echo "TEST20_R1_SANITIZED_PUBLICATION_ZIP_SHA256=$PUBLIC_ZIP_SHA"
fi

echo
echo "TEST20_R1_OUTPUT=$OUTPUT"
echo "TEST20_R1_PRIVATE_EVIDENCE_ZIP=$PRIVATE_ZIP"
echo "TEST20_R1_SANITIZED_PUBLICATION_DIRECTORY=$PUBLIC_DIR"
echo "TEST20_R1_SANITIZED_PUBLICATION_ZIP=$PUBLIC_ZIP"

if [ "$RESULT" -eq 0 ]; then
  echo "TEST20_R1_EXACT_ARTIFACT_IDENTITY=PASS"
  echo "TEST20_R1_PUBLIC_API_CENSUS=PASS"
  echo "TEST20_R1_INHERITANCE_AND_DEPENDENCY_GRAPH=PASS"
  echo "TEST20_R1_SESSION_TYPE_CENSUS=PASS"
  echo "TEST20_R1_HI_ROKID_COMPONENT_COMPARISON=PASS"
  echo "TEST20_R1_NATIVE_AND_JNI_CENSUS=PASS"
  echo "TEST20_R1_CAPABILITY_CLASSIFICATION=PASS"
  echo "TEST20_R1_SANITIZED_PUBLICATION=PASS"
  echo "TEST20_R1_CENSUS=PASS"
else
  echo "TEST20_R1_CENSUS=FAIL"
fi

echo "ADB_OPERATION=NONE"
echo "PHONE_MUTATION=NONE"
echo "MEDIA_ACCESS=NONE"
echo "CLOUD_AI_REQUEST=NONE"
echo "GLASSES_COMMAND_EXECUTION=NONE"
exit "$RESULT"
