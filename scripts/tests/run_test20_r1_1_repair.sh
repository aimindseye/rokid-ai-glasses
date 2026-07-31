#!/usr/bin/env bash
# Repair Test 20 r1 sanitized classification without changing shell options.

REPO=""
INPUT_ZIP=""
OUTPUT=""
EXPECTED_SHA256="30ae03d16da40a2f0045030695a7a8b58ca6cb33304ad35f117ecc82e8ce3ac7"
RESULT=0

usage() {
  cat <<'TXT'
Usage:
  bash scripts/tests/run_test20_r1_1_repair.sh \
    --repo PATH \
    --input-publication-zip PATH \
    --output PATH

This operation reclassifies an already sanitized Test 20 r1 publication. It
performs no Maven, Gradle, ADB, phone, media, cloud AI, Bluetooth, or glasses
operation and does not require proprietary artifacts.
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --input-publication-zip) INPUT_ZIP="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --expected-input-sha256) EXPECTED_SHA256="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage; exit 64 ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$INPUT_ZIP" ] || [ -z "$OUTPUT" ]; then
  usage >&2
  exit 64
fi
REPO="$(cd "$REPO" 2>/dev/null && pwd)"
INPUT_ZIP="$(cd "$(dirname "$INPUT_ZIP")" 2>/dev/null && pwd)/$(basename "$INPUT_ZIP")"
OUTPUT_PARENT="$(cd "$(dirname "$OUTPUT")" 2>/dev/null && pwd)"
OUTPUT="$OUTPUT_PARENT/$(basename "$OUTPUT")"
REPAIR="$REPO/scripts/research/cxr/repair_test20_r1_publication.py"
PUBLIC_ZIP="${OUTPUT}-sanitized-publication-repaired.zip"
PUBLIC_SHA="${PUBLIC_ZIP}.sha256.txt"

fail() { echo "FAIL: $*" >&2; RESULT=1; }
pass() { echo "PASS: $*"; }

privacy_gate() {
  python3 - "$1" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); errors=[]
patterns=[
    re.compile(r'/Users/'),
    re.compile(r'/home/[^/]+/'),
    re.compile(r'(?:PHONE_SERIAL|device_serial)\s*[:=]\s*[A-Za-z0-9-]{8,}',re.I),
    re.compile(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}',re.I),
]
for path in root.rglob('*'):
    if not path.is_file(): continue
    text=path.read_text(encoding='utf-8',errors='replace')
    for pattern in patterns:
        if pattern.search(text): errors.append(f'{path.name}: {pattern.pattern}')
for suffix in ('.aar','.apk','.so','.dex','.jar','.pcap'):
    for path in root.rglob(f'*{suffix}'):
        errors.append(f'proprietary/binary suffix present: {path.name}')
if errors:
    print('TEST20_R1_1_PRIVACY_GATE=FAIL')
    for error in errors: print(error)
    raise SystemExit(1)
print('TEST20_R1_1_PRIVACY_GATE=PASS')
PY
}

echo "Test 20 r1.1 — sanitized publication classification repair"
echo "============================================================="
echo "REPO=$REPO"
echo "INPUT_PUBLICATION_ZIP=$INPUT_ZIP"
echo "EXPECTED_INPUT_SHA256=$EXPECTED_SHA256"
echo "OUTPUT=$OUTPUT"
echo "MAVEN_OPERATION=NONE"
echo "GRADLE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "PHONE_MUTATION=NONE"
echo "MEDIA_ACCESS=NONE"
echo "CLOUD_AI_REQUEST=NONE"
echo "GLASSES_COMMAND_EXECUTION=NONE"
echo

if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
if [ -n "$(git -C "$REPO" status --porcelain=v1 --untracked-files=no 2>/dev/null)" ]; then
  fail "tracked repository changes are present"
  git -C "$REPO" status --short --untracked-files=no >&2
fi
if [ ! -f "$INPUT_ZIP" ]; then fail "input publication ZIP is missing"; fi
if [ ! -f "$REPAIR" ]; then fail "repair tool is missing"; fi
if [ -e "$OUTPUT" ] || [ -e "$PUBLIC_ZIP" ] || [ -e "$PUBLIC_SHA" ]; then
  fail "output path or output ZIP already exists"
fi

if [ "$RESULT" -ne 0 ]; then
  echo "TEST20_R1_1_REPAIR=FAIL"
  exit "$RESULT"
fi

python3 "$REPAIR" \
  --input-publication-zip "$INPUT_ZIP" \
  --expected-input-sha256 "$EXPECTED_SHA256" \
  --output "$OUTPUT"
REPAIR_RC=$?
echo "TEST20_R1_1_REPAIR_TOOL_EXIT_CODE=$REPAIR_RC"
if [ "$REPAIR_RC" -eq 0 ]; then pass "member-level publication repair completed"; else fail "repair tool failed"; fi

if [ "$RESULT" -eq 0 ]; then
  privacy_gate "$OUTPUT"
  PRIVACY_RC=$?
  if [ "$PRIVACY_RC" -ne 0 ]; then fail "privacy gate failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  (
    cd "$OUTPUT" || exit 91
    find . -type f ! -name SHA256SUMS.txt -print0 |
      LC_ALL=C sort -z |
      xargs -0 shasum -a 256 >SHA256SUMS.txt
  )
  HASH_RC=$?
  echo "TEST20_R1_1_HASH_MANIFEST_EXIT_CODE=$HASH_RC"
  if [ "$HASH_RC" -ne 0 ]; then fail "hash manifest creation failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  (
    cd "$OUTPUT" || exit 91
    shasum -a 256 -c SHA256SUMS.txt
  ) >"$OUTPUT/hash-verification.txt" 2>&1
  VERIFY_RC=$?
  echo "TEST20_R1_1_HASH_VERIFICATION_EXIT_CODE=$VERIFY_RC"
  if [ "$VERIFY_RC" -eq 0 ]; then pass "repaired publication hashes verified"; else fail "hash verification failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  python3 - "$OUTPUT" "$PUBLIC_ZIP" <<'PY'
from pathlib import Path
import sys,zipfile
root=Path(sys.argv[1]); target=Path(sys.argv[2])
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for path in sorted(root.rglob('*')):
        if path.is_file(): z.write(path,path.relative_to(root.parent).as_posix())
PY
  ZIP_RC=$?
  echo "TEST20_R1_1_PUBLIC_ZIP_EXIT_CODE=$ZIP_RC"
  if [ "$ZIP_RC" -ne 0 ]; then fail "repaired publication ZIP creation failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  PUBLIC_ZIP_SHA256="$(shasum -a 256 "$PUBLIC_ZIP" | awk '{print $1}')"
  printf '%s  %s\n' "$PUBLIC_ZIP_SHA256" "$PUBLIC_ZIP" >"$PUBLIC_SHA"
  echo "TEST20_R1_1_REPAIRED_PUBLICATION_ZIP_SHA256=$PUBLIC_ZIP_SHA256"
  echo "TEST20_R1_1_REPAIRED_PUBLICATION_ZIP=$PUBLIC_ZIP"
  echo "TEST20_R1_1_REPAIRED_PUBLICATION_SHA256_FILE=$PUBLIC_SHA"
fi

if [ "$RESULT" -eq 0 ]; then
  echo "TEST20_R1_1_MEMBER_LEVEL_RUNTIME_QUALIFICATION=PASS"
  echo "TEST20_R1_1_SYNTHETIC_OBFUSCATED_SURFACE_CLASSIFICATION=PASS"
  echo "TEST20_R1_1_SANITIZED_PUBLICATION=PASS"
  echo "TEST20_R1_1_REPAIR=PASS"
else
  echo "TEST20_R1_1_REPAIR=FAIL"
fi

echo "SOURCE_REPOSITORY_MUTATION=NONE"
echo "MAVEN_OPERATION=NONE"
echo "GRADLE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "PHONE_MUTATION=NONE"
echo "MEDIA_ACCESS=NONE"
echo "CLOUD_AI_REQUEST=NONE"
echo "GLASSES_COMMAND_EXECUTION=NONE"
exit "$RESULT"
