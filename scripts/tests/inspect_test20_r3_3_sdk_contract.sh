#!/bin/bash
# Read-only local inspection of Maven-resolved client-l:1.0.1.
# macOS Bash 3.2 compatible. Intentionally no set -e/-u/pipefail.
REPO=""; OUTPUT=""; VERSION="1.0.1"
usage(){ cat <<'EOF'
Usage: bash scripts/tests/inspect_test20_r3_3_sdk_contract.sh --repo PATH --output DIR
EOF
}
die(){ echo "ERROR: $*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2"; shift 2;; --output) OUTPUT="$2"; shift 2;; -h|--help) usage; exit 0;; *) die "unknown argument: $1";; esac; done
[ -n "$REPO" ] || die "--repo is required"; [ -n "$OUTPUT" ] || die "--output is required"; [ -d "$REPO/.git" ] || die "not a git repository: $REPO"
mkdir -p "$OUTPUT/private" "$OUTPUT/sanitized" || die "cannot create output"
CACHE="$HOME/.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/$VERSION"
AAR="$(find "$CACHE" -type f -name 'client-l-1.0.1.aar' 2>/dev/null | head -n 1)"
[ -n "$AAR" ] && [ -s "$AAR" ] || die "client-l:1.0.1 AAR not found in Gradle cache; run the r3.3 APK prepare/build first"
AAR_SHA="$(shasum -a 256 "$AAR" | awk '{print $1}')"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test20-r33-sdk.XXXXXX")" || die "mktemp failed"
cleanup(){ rm -rf "$TMP"; }
trap cleanup EXIT INT TERM
unzip -q "$AAR" -d "$TMP/aar" || die "cannot extract AAR"
[ -s "$TMP/aar/classes.jar" ] || die "classes.jar missing from AAR"
JAVAP="$(command -v javap 2>/dev/null)"
if [ -z "$JAVAP" ] && [ -x "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/javap" ]; then JAVAP="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/javap"; fi
[ -n "$JAVAP" ] && [ -x "$JAVAP" ] || die "javap unavailable; install/use JDK or Android Studio JBR"
JAR="$(command -v jar 2>/dev/null)"; if [ -z "$JAR" ] && [ -x "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/jar" ]; then JAR="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/jar"; fi
[ -n "$JAR" ] && [ -x "$JAR" ] || die "jar unavailable"
"$JAR" tf "$TMP/aar/classes.jar" > "$OUTPUT/private/classes-list-private.txt" 2>&1
CLASSES="$(grep -E '(^|/)(CXRLink|ExternalAppClient|IImageStreamCbk|IMediaStreamService|IImageStreamCallback).*\.class$' "$OUTPUT/private/classes-list-private.txt" | sed 's#/#.#g;s#\.class$##' | sort -u)"
: > "$OUTPUT/private/javap-private.txt"
for C in $CLASSES; do echo "===== $C =====" >> "$OUTPUT/private/javap-private.txt"; "$JAVAP" -classpath "$TMP/aar/classes.jar" -p -c -s "$C" >> "$OUTPUT/private/javap-private.txt" 2>&1; done
TAKE="NO"; IMG="NO"; REG="NO"; UNREG="NO"; grep -q 'takePhoto' "$OUTPUT/private/javap-private.txt" && TAKE="YES"; grep -q 'setCXRImageCbk' "$OUTPUT/private/javap-private.txt" && IMG="YES"; grep -q 'registerImageCallback' "$OUTPUT/private/javap-private.txt" && REG="YES"; grep -q 'unregisterImageCallback' "$OUTPUT/private/javap-private.txt" && UNREG="YES"
cat > "$OUTPUT/sanitized/sdk-contract-summary.txt" <<EOF
TEST20_R3_3_SDK_INSPECTION_SCHEMA=rokid.test20-r3.3.sdk-contract.v1
MAVEN_COORDINATE=com.rokid.cxr:client-l:1.0.1
AAR_SHA256=$AAR_SHA
CXR_TAKEPHOTO_SYMBOL_PRESENT=$TAKE
SET_CXR_IMAGE_CALLBACK_SYMBOL_PRESENT=$IMG
REGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$REG
UNREGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$UNREG
THIRD_PARAMETER_SEMANTICS=NOT_INFERRED_FROM_BYTECODE_SYMBOLS
AAR_LOCAL_PATH_EXPORTED=NO
DEVICE_OPERATION=NONE
PHOTO_OPERATION=NONE
EOF
[ "$TAKE" = YES ] || die "takePhoto symbol not found in resolved SDK"
[ "$IMG" = YES ] || die "setCXRImageCbk symbol not found in resolved SDK"
echo "TEST20_R3_3_SDK_CONTRACT_INSPECTION=PASS"
echo "MAVEN_COORDINATE=com.rokid.cxr:client-l:1.0.1"
echo "AAR_SHA256=$AAR_SHA"
echo "CXR_TAKEPHOTO_SYMBOL_PRESENT=$TAKE"
echo "SET_CXR_IMAGE_CALLBACK_SYMBOL_PRESENT=$IMG"
echo "REGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$REG"
echo "UNREGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$UNREG"
echo "DEVICE_OPERATION=NONE"
echo "PHOTO_OPERATION=NONE"
