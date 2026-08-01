#!/bin/bash
# Read-only local inspection of Maven-resolved client-l:1.0.1. No device operation.
# macOS Bash 3.2 compatible. Intentionally no set -e/-u/pipefail.
REPO=""; EXPECTED_SHA="c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"; VERSION="1.0.1"
die(){ echo "ERROR: $*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[ -n "$REPO" ] || die "--repo is required"
[ -d "$REPO/.git" ] || die "not a git repository: $REPO"
CACHE="$HOME/.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/$VERSION"
AAR="$(find "$CACHE" -type f -name 'client-l-1.0.1.aar' 2>/dev/null | head -n 1)"
[ -n "$AAR" ] && [ -s "$AAR" ] || die "client-l:1.0.1 AAR not found in Gradle cache"
AAR_SHA="$(shasum -a 256 "$AAR" | awk '{print $1}')"
if [ "$AAR_SHA" != "$EXPECTED_SHA" ]; then
  echo "ERROR: resolved client-l:1.0.1 AAR hash differs from accepted Test 20 environment" >&2
  echo "EXPECTED_AAR_SHA256=$EXPECTED_SHA" >&2
  echo "ACTUAL_AAR_SHA256=$AAR_SHA" >&2
  exit 1
fi
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test20-final-sdk.XXXXXX")" || die "mktemp failed"
cleanup(){ rm -rf "$TMP"; }
trap cleanup EXIT INT TERM
unzip -q "$AAR" -d "$TMP/aar" || die "cannot extract AAR"
[ -s "$TMP/aar/classes.jar" ] || die "classes.jar missing from AAR"
JAR="$(command -v jar 2>/dev/null)"; JAVAP="$(command -v javap 2>/dev/null)"
if [ -z "$JAR" ] && [ -x "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/jar" ]; then JAR="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/jar"; fi
if [ -z "$JAVAP" ] && [ -x "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/javap" ]; then JAVAP="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/javap"; fi
[ -n "$JAR" ] && [ -x "$JAR" ] || die "jar unavailable"
[ -n "$JAVAP" ] && [ -x "$JAVAP" ] || die "javap unavailable"
"$JAR" tf "$TMP/aar/classes.jar" > "$TMP/classes.txt" 2>&1 || die "cannot list classes.jar"
CLASSES="$(grep -E '(^|/)(CXRLink|ExternalAppClient|IImageStreamCbk|IMediaStreamService|IImageStreamCallback).*\.class$' "$TMP/classes.txt" | sed 's#/#.#g;s#\.class$##' | sort -u)"
: > "$TMP/javap.txt"
for C in $CLASSES; do "$JAVAP" -classpath "$TMP/aar/classes.jar" -p -s "$C" >> "$TMP/javap.txt" 2>&1; done
TAKE=NO; IMG=NO; REG=NO; UNREG=NO
grep -q 'takePhoto' "$TMP/javap.txt" && TAKE=YES
grep -q 'setCXRImageCbk' "$TMP/javap.txt" && IMG=YES
grep -q 'registerImageCallback' "$TMP/javap.txt" && REG=YES
grep -q 'unregisterImageCallback' "$TMP/javap.txt" && UNREG=YES
[ "$TAKE" = YES ] || die "takePhoto symbol missing"
[ "$IMG" = YES ] || die "setCXRImageCbk symbol missing"
echo "TEST20_FINAL_SDK_CONTRACT_INSPECTION=PASS"
echo "MAVEN_COORDINATE=com.rokid.cxr:client-l:1.0.1"
echo "AAR_SHA256=$AAR_SHA"
echo "CXR_TAKEPHOTO_SYMBOL_PRESENT=$TAKE"
echo "SET_CXR_IMAGE_CALLBACK_SYMBOL_PRESENT=$IMG"
echo "REGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$REG"
echo "UNREGISTER_IMAGE_CALLBACK_SYMBOL_PRESENT=$UNREG"
echo "DEVICE_OPERATION=NONE"
echo "PHOTO_OPERATION=NONE"
