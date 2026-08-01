#!/bin/bash
# Regression: generated directories under scripts/tests must never be copied.
# Intentionally no set -e/-u/pipefail.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test20-r33-installer-filter.XXXXXX")" || exit 1
SRC="$TMP/src"
DST="$TMP/dst"
mkdir -p "$SRC/__pycache__" "$SRC/nested-generated" "$DST" || { rm -rf "$TMP"; exit 1; }
printf 'alpha\n' > "$SRC/alpha.py"
printf 'beta\n' > "$SRC/beta.sh"
printf 'cache\n' > "$SRC/__pycache__/alpha.pyc"
printf 'nested\n' > "$SRC/nested-generated/file.txt"
RC=0
COPIED=0
for f in "$SRC"/*; do
  [ -f "$f" ] || continue
  name="$(basename "$f")"
  cp "$f" "$DST/$name" || RC=1
  COPIED=$((COPIED + 1))
done
[ "$COPIED" -eq 2 ] || RC=1
[ -f "$DST/alpha.py" ] || RC=1
[ -f "$DST/beta.sh" ] || RC=1
[ ! -e "$DST/__pycache__" ] || RC=1
[ ! -e "$DST/nested-generated" ] || RC=1
if [ "$RC" -eq 0 ]; then
  echo "TEST20_R3_3_INSTALLER_REGULAR_FILE_FILTER=PASS"
  echo "GENERATED_DIRECTORY_COPY=NO"
else
  echo "TEST20_R3_3_INSTALLER_REGULAR_FILE_FILTER=FAIL" >&2
fi
rm -rf "$TMP"
exit "$RC"
