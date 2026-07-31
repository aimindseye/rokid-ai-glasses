# Test 19 r2: Hi Rokid CXR-L Firmware Comparison

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-31 |

## Purpose

Qualify the supported consumer-coexistence path in which a third-party Android
application obtains authorization from Hi Rokid and connects through CXR-L.
Run the same connection-only client before and after the glasses firmware
update while keeping the phone, Hi Rokid build, account, network, APK, and test
actions constant.

## Fixed baseline

| Variable | Required value |
|---|---|
| Phone | Pixel 7, ADB serial `2C160DLH20007H` |
| Hi Rokid package | `com.rokid.sprite.global.aiapp` |
| Hi Rokid version | `G1.11.11.0727` / version code `10110011` |
| CXR-L artifact | `com.rokid.cxr:client-l:1.0.1` |
| Test app | `org.aimindseye.rokid.cxrlqualification` / `2.3-test19-r2.3` |
| Run A firmware | `1.22.009-20260710-151201` |
| Run B firmware | `1.23.009-20260725-153201` |

The Test 19 app never logs the authorization token and does not upload an APK,
capture media, invoke AI, unpair Bluetooth, force-stop Hi Rokid, or reboot
anything.

## Important sequencing

1. Build and install the qualification APK.
2. Run connection-only qualification on firmware 1.22.
3. Run the separate PCAPdroid gate only after connection passes.
4. Preserve and hash all 1.22 evidence.
5. Update the glasses manually through Hi Rokid.
6. Record the firmware transition and verify stock recovery.
7. Repeat the identical connection and privacy tests on firmware 1.23.

Do not update the glasses before the 1.22 connection run is complete.

## Terminal safety

Every command below invokes a script as a child Bash process. The scripts do
not enable `set -e`, `set -u`, or `set -o pipefail`. Their exit status is
captured after the child returns, so the interactive zsh terminal remains open.

## Stage 0 — prepare

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
PHONE_SERIAL="2C160DLH20007H"

cd "$REPO"

bash scripts/tests/prepare_test19_r2.sh \
  --phone "$PHONE_SERIAL" \
  --sdk-version 1.0.1 \
  --expected-hi-rokid-version G1.11.11.0727 \
  --reset-app-data

PREPARE_RC=$?

echo "TEST19_R2_PREPARE_EXIT_CODE=$PREPARE_RC"
```

A successful preparation ends with:

```text
CXR_M_GRADLE_PROPERTY_SUPPLIED=NO
CXR_L_GRADLE_PROPERTY_SUPPLIED=YES
TEST19_R2_CXR_L_ARTIFACT_AND_API_SURFACE=PASS
TEST19_R2_APK_BUILD=PASS
TEST19_R2_GOVERNED_BUILD_EVIDENCE=PASS
TEST19_R2_APK_INSTALL=PASS
INSTALLED_TEST_APP_VERSION=2.3-test19-r2.3
TEST19_R2_PACKAGE_IDENTITY=PASS
TEST19_R2_BUILD_OUTPUT_CLEANUP=PASS
TEST19_R2_READY_FOR_CONNECTION_RUN=YES
TEST19_R2_PREPARE=PASS
TEST19_R2_PREPARE_EXIT_CODE=0
```

Downloaded proprietary SDK bytes remain under `~/rokid-nettest/private/` and
must not be committed.

## Run A — firmware 1.22 connection only

Do not start PCAPdroid yet.

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
PHONE_SERIAL="2C160DLH20007H"
FIRMWARE_SCREENSHOT="$HOME/Downloads/test19-r2-firmware-1.22.jpg"
OUTPUT="$HOME/rokid-nettest/tests/test19-r2-cxrl-fw-1.22-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$REPO"

bash scripts/tests/run_test19_r2_connection.sh \
  --phone "$PHONE_SERIAL" \
  --firmware 1.22.009-20260710-151201 \
  --firmware-screenshot "$FIRMWARE_SCREENSHOT" \
  --output "$OUTPUT"

RUN_A_RC=$?

echo "TEST19_R2_RUN_A_EXIT_CODE=$RUN_A_RC"
echo "TEST19_R2_RUN_A_OUTPUT=$OUTPUT"
```

The host runner gives three explicit checkpoints. In the Android app:

1. authorize through Hi Rokid exactly once;
2. approve only the dialog naming the Test 19 package;
3. wait for the private-token confirmation;
4. start one CXR-L attempt exactly once;
5. wait for the terminal outcome and automatic disconnect.

Connection pass requires both SDK callbacks:

```text
TEST19_R2_CXR_L_SERVICE_CONNECTION=PASS
TEST19_R2_GLASS_BLUETOOTH_CALLBACK=PASS
TEST19_R2_CLEAN_DISCONNECT=PASS
TEST19_R2_HI_ROKID_RECOVERY=PASS
TEST19_R2_QUALIFICATION=PASS
TEST19_R2_CONNECTION_RUN=PASS
```

Exit codes are bounded:

| Code | Meaning |
|---:|---|
| 0 | CXR-L connection and Hi Rokid recovery passed |
| 10 | Bounded authorization, service, or callback failure |
| 20 | Hi Rokid stock recovery failed |
| 30 | Evidence incomplete or preflight blocked |
| 64 | Invalid command usage |

## Run A privacy gate

Run this only if Run A returned 0. Configure PCAPdroid to include both the Test
19 app and Hi Rokid. Capture connection metadata only; do not capture payloads.

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
PHONE_SERIAL="2C160DLH20007H"
CONNECTION_SUMMARY="$OUTPUT/summary.json"
PCAPDROID_CSV="$HOME/Downloads/test19-r2-fw-1.22-connections.csv"
PRIVACY_OUTPUT="$HOME/rokid-nettest/tests/test19-r2-privacy-fw-1.22-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$REPO"

bash scripts/tests/run_test19_r2_privacy.sh \
  --phone "$PHONE_SERIAL" \
  --firmware 1.22.009-20260710-151201 \
  --connection-summary "$CONNECTION_SUMMARY" \
  --pcapdroid-csv "$PCAPDROID_CSV" \
  --output "$PRIVACY_OUTPUT"

PRIVACY_A_RC=$?

echo "TEST19_R2_PRIVACY_A_EXIT_CODE=$PRIVACY_A_RC"
```

The privacy gate fails only when traffic is attributed to the custom Test 19
package and reaches a public destination. Hi Rokid public traffic is reported
separately and is not misattributed to the custom app. Missing app-identity
columns block the gate rather than producing a false pass.

## Firmware transition

After Run A evidence is complete, update the glasses manually in Hi Rokid.
Keep the glasses charged above 50%, the phone on reliable Wi-Fi and power, and
do not interrupt the update. Confirm the installed target is exactly
`1.23.009-20260725-153201`.

Record the transition:

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
PHONE_SERIAL="2C160DLH20007H"
BEFORE_SUMMARY="$OUTPUT/summary.json"
BEFORE_SCREENSHOT="$HOME/Downloads/test19-r2-firmware-1.22.jpg"
AFTER_SCREENSHOT="$HOME/Downloads/test19-r2-firmware-1.23.jpg"

cd "$REPO"

bash scripts/tests/record_test19_r2_firmware_transition.sh \
  --phone "$PHONE_SERIAL" \
  --before-summary "$BEFORE_SUMMARY" \
  --before-screenshot "$BEFORE_SCREENSHOT" \
  --after-screenshot "$AFTER_SCREENSHOT"

TRANSITION_RC=$?

echo "TEST19_R2_FIRMWARE_TRANSITION_EXIT_CODE=$TRANSITION_RC"
```

The transition script performs no update. It only assembles evidence after the
operator has completed the update through Hi Rokid.

## Run B — firmware 1.23

Repeat the same client and procedure:

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
PHONE_SERIAL="2C160DLH20007H"
FIRMWARE_SCREENSHOT="$HOME/Downloads/test19-r2-firmware-1.23.jpg"
OUTPUT_B="$HOME/rokid-nettest/tests/test19-r2-cxrl-fw-1.23-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$REPO"

bash scripts/tests/run_test19_r2_connection.sh \
  --phone "$PHONE_SERIAL" \
  --firmware 1.23.009-20260725-153201 \
  --firmware-screenshot "$FIRMWARE_SCREENSHOT" \
  --output "$OUTPUT_B"

RUN_B_RC=$?

echo "TEST19_R2_RUN_B_EXIT_CODE=$RUN_B_RC"
echo "TEST19_R2_RUN_B_OUTPUT=$OUTPUT_B"
```

If Run B passes, repeat the separate privacy command with the 1.23 summary and a
new CSV/output path.

## What this test does not prove

A pass proves authorization, CXR-L service binding, the glasses-Bluetooth
callback, clean disconnect, and stock coexistence for the tested stack. It does
not prove camera, microphone, speaker, display, APK installation, custom AI,
offline operation, phone/glasses reboot recovery, or replacement of Hi Rokid.

## r2.1 exact client-l 1.0.1 API-surface repair

The first physical preparation run proved that the published `client-l:1.0.1`
AAR does not contain `com.rokid.cxr.link.utils.GlassInfo`. The original r2
synthetic stubs incorrectly invented that class and three callback methods.
r2.1 removes the unsupported callbacks, attests the real four-method
`ICXRLinkCbk` surface, preserves a private class inventory and `javap` report,
and prevents resolver failures from being misreported as APK-install failures.
No glasses or Hi Rokid operation occurs during this repair.

## r2.2 exact inherited API-surface repair

The physical `client-l:1.0.1` artifact diagnostic established that
`com.rokid.cxr.link.CXRLink` declares no connection methods itself. It extends
`com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient`, which declares
`setCXRLinkCbk`, `configCXRSession`, `connect(String)`, and `disconnect()`.

The r2.2 resolver therefore validates the exact AAR/POM hashes, walks this class
hierarchy with the selected JDK's `javap`, and checks exact JVM descriptors. A
zero direct-method count is expected and no longer treated as a failure. The
physical connection run remains blocked until preparation builds, installs, and
verifies the r2.2 APK.


## r2.3 Gradle module-isolation and governed-install repair

A physical build probe proved that the CXR-L module compiles when Gradle is
given both `rokidCxrVersion=1.2.2` and `rokidCxrLVersion=1.0.1`, but the CXR-M
property was required only because the unrelated `test19` project threw during
configuration. r2.3 makes each SDK property task-scoped: a CXR-M task requires
only `rokidCxrVersion`, and a CXR-L task requires only `rokidCxrLVersion`.

The governed preparation command now invokes `:test19r2:clean` and
`:test19r2:assembleDebug` with only `-ProkidCxrLVersion=1.0.1`, preserves the
APK and build records under the private Maven evidence directory, installs the
APK, verifies package version `2.3-test19-r2.3`, optionally clears only this
test app's data, and removes generated build output after preservation. The
repository ignores `android-client/*/build/` as a defense-in-depth hygiene
rule. Hi Rokid data, Bluetooth pairing, and glasses firmware remain unchanged.
