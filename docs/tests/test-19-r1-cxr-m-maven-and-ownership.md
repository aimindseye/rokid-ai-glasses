# Test 19 r1 — Maven-Resolved CXR-M Build and Ownership Qualification

<!-- wiki-status: audience=research; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Research |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Harness implemented; physical run pending |
| Last reviewed | 2026-07-30 |

## Preflight only: verify Maven resolution

```bash
cd "$HOME/Documents/projects/rokid-ai-glasses"

OUT="$HOME/rokid-nettest/private/test19-r1-maven-preflight-$(date -u +%Y%m%dT%H%M%SZ)"

python3 scripts/research/cxr/resolve_cxr_m_maven.py \
  --output "$OUT"

cat "$OUT/resolution.json"
```

A working repository produces `"working": true`, an exact version, coordinate,
POM/AAR sizes, and SHA-256 values. Use `--version VERSION` only to qualify a
specific version listed in the downloaded metadata.

## Physical run

Choose a CSV destination whose parent directory already exists, then start a
PCAPdroid capture filtered to the Test 19 package. Run the qualification with
that intended export path. After the Bluetooth ownership phases, the runner
pauses so you can stop PCAPdroid and export the connections CSV before the
privacy gate executes:

```bash
cd "$HOME/Documents/projects/rokid-ai-glasses"

PCAPDROID_CSV="$HOME/Downloads/test19-r1-pcapdroid-connections.csv"

bash scripts/tests/run_test19_cxr_qualification.sh \
  --phone '<S25_ULTRA_ADB_SERIAL>' \
  --pcapdroid-csv "$PCAPDROID_CSV"
```

To pin a metadata-listed version:

```bash
bash scripts/tests/run_test19_cxr_qualification.sh \
  --phone '<S25_ULTRA_ADB_SERIAL>' \
  --sdk-version '<EXACT_VERSION>' \
  --pcapdroid-csv '<PCAPDROID_CONNECTIONS_CSV>'
```

## Evidence

Private evidence includes Maven metadata, POM, AAR, API inventory, Android
package/Bluetooth snapshots, app JSONL, logcat, and the PCAPdroid CSV. Do not
publish the downloaded SDK bytes, raw identifiers, logcat, or private ZIP.
The sanitized summaries contain hashes, marker states, ownership
classification, and destination counts only.

## Safety

- No firmware, bootloader, partition, or Developer Mode mutation.
- No captured command or direct RFCOMM replay.
- No camera, microphone, audio, AI, or file-transfer action.
- Hi Rokid stock recovery is mandatory.
- Public network destinations fail the local-network privacy gate.

See the [developer qualification page](../developer/companion-app/test-19-r1-qualification.md).
