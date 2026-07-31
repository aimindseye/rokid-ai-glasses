#!/usr/bin/env bash
# Test 19 r2.3.2 compatibility dispatcher. Build and installation are separate
# governed stages. No default combined path is permitted.

STAGE=""
FORWARD_ARGS=()
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"

usage() {
  cat <<'TXT'
Usage:
  bash scripts/tests/prepare_test19_r2.sh --stage build [build options]
  bash scripts/tests/prepare_test19_r2.sh --stage install [install options]

The r2.3.2 workflow intentionally has no implicit or combined preparation mode.
Run Stage 1 first, review its PASS markers, then pass its evidence directory to
Stage 2. Direct scripts are also available:

  scripts/tests/build_test19_r2.sh
  scripts/tests/install_test19_r2.sh
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --stage) STAGE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) FORWARD_ARGS+=("$1"); shift ;;
  esac
done

case "$STAGE" in
  build)
    bash "$SCRIPT_DIR/build_test19_r2.sh" "${FORWARD_ARGS[@]}"
    RC=$?
    echo "TEST19_R2_PREPARE_DISPATCH_STAGE=build"
    echo "TEST19_R2_PREPARE_DISPATCH_EXIT_CODE=$RC"
    exit "$RC"
    ;;
  install)
    bash "$SCRIPT_DIR/install_test19_r2.sh" "${FORWARD_ARGS[@]}"
    RC=$?
    echo "TEST19_R2_PREPARE_DISPATCH_STAGE=install"
    echo "TEST19_R2_PREPARE_DISPATCH_EXIT_CODE=$RC"
    exit "$RC"
    ;;
  "")
    echo "ERROR: --stage build or --stage install is required" >&2
    echo "TEST19_R2_BUILD_FIRST_RESUME_REQUIRED=YES"
    usage
    exit 64
    ;;
  *)
    echo "ERROR: unsupported stage: $STAGE" >&2
    usage
    exit 64
    ;;
esac
