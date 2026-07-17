#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  query_mediastore.sh --user ANDROID_USER --output PRIVATE_FILE
EOF
}

ANDROID_USER=""
OUTPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) ANDROID_USER="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$ANDROID_USER" && -n "$OUTPUT" ]] || { usage >&2; exit 2; }
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb not found" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")"

adb shell content query \
  --user "$ANDROID_USER" \
  --uri content://media/external/file \
  --projection '_id:_display_name:relative_path:mime_type:_size:date_modified' \
  > "$OUTPUT"

[[ -s "$OUTPUT" ]] || { echo "ERROR: empty MediaStore inventory" >&2; exit 1; }
printf 'MediaStore inventory: %s\n' "$OUTPUT"
