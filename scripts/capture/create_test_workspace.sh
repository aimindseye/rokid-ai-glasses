#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  create_test_workspace.sh --root PRIVATE_ROOT --test-id TEST_ID

Creates a private capture workspace and a capture.env file.
EOF
}

ROOT=""
TEST_ID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --test-id) TEST_ID="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$ROOT" && -n "$TEST_ID" ]] || { usage >&2; exit 2; }
[[ "$TEST_ID" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "ERROR: unsafe test id" >&2
  exit 2
}

TEST_ROOT="${ROOT%/}/$TEST_ID"
mkdir -p "$TEST_ROOT"/{pcap,decrypted,logcat,screenshots,notes,manifests}

ENV_FILE="$TEST_ROOT/notes/capture.env"
if [[ ! -e "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF
export TEST_ID=$(printf '%q' "$TEST_ID")
export TEST_ROOT=$(printf '%q' "$TEST_ROOT")
export PCAP_NAME=$(printf '%q' "$TEST_ID.pcap")
export KEYLOG_NAME=$(printf '%q' "$TEST_ID.sslkeylog")
export CSV_NAME=$(printf '%q' "$TEST_ID-connections.csv")
export LOGCAT_NAME=$(printf '%q' "$TEST_ID-logcat.txt")
EOF
fi

printf 'Workspace: %s\nEnvironment: %s\n' "$TEST_ROOT" "$ENV_FILE"
