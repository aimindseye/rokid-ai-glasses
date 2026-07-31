# Test 20 r1.1 — CXR-L Member-Level Classification Repair

## Purpose

Test 20 r1.1 repairs the withdrawn Test 20 r1 sanitized publication without
rerunning Maven resolution, SDK extraction, ADB, phone operations, media access,
cloud AI, Bluetooth actions, or glasses commands.

The original static census remains valid. The defect was limited to its
classification layer: class participation in the accepted Test 19 flow was
incorrectly propagated to unrelated public members.

## Fixed source publication

| Item | Exact value |
|---|---|
| Source sanitized ZIP SHA-256 | `30ae03d16da40a2f0045030695a7a8b58ca6cb33304ad35f117ecc82e8ce3ac7` |
| Source schema | `rokid.test20.r1.cxr-l-capability-census.public.v1` |
| Withdrawn runtime-qualified member count | `101` |
| Repaired runtime-qualified member count | `9` |
| Repaired runtime-qualified component count | `2` |

## Repaired boundary

Runtime qualification is descriptor-exact. The accepted member set is limited
to:

- `CXRLink(Context)`;
- `setCXRLinkCbk(ICXRLinkCbk)`;
- `configCXRSession(CXRSession)`;
- `connect(String)`;
- `disconnect()`;
- the two-argument `CXRSession(CXRSessionType, String)` constructor;
- `CXRSessionType.CUSTOMAPP`;
- `onCXRLConnected(boolean)`;
- `onGlassBtConnected(boolean)`.

The Hi Rokid authorization activity and fallback CXR-L service are qualified at
the component level. The exported provider remains statically observed but
runtime-untested.

The AI-assist callbacks, photo, audio, custom-command, custom-view, glass-app,
provider, native, and JNI surfaces remain untested.

## Synthetic and obfuscated surfaces

The repaired publication adds explicit origin metadata for compiler-generated,
obfuscated, native-bridge, build-generated, and example-wrapper surfaces.
Kotlin `access$...` helpers and `$default` methods are not presented as stable
directly callable API.

The `CXRSessionType` array field named `a` has descriptor
`[Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;`. It is compiler backing
storage, not a fourth session type. The supported static enum values visible in
the census are `NONE`, `CUSTOMVIEW`, and `CUSTOMAPP`; only `CUSTOMAPP` is
runtime-qualified.

## Run

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
SOURCE_PUBLICATION_ZIP="$HOME/rokid-nettest/private/test20-r1-cxr-l-capability-census-20260731T205519Z-sanitized-publication.zip"
OUTPUT="$HOME/rokid-nettest/private/test20-r1-1-cxr-l-classification-repair-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$REPO"

bash scripts/tests/run_test20_r1_1_repair.sh \
  --repo "$REPO" \
  --input-publication-zip "$SOURCE_PUBLICATION_ZIP" \
  --output "$OUTPUT"

REPAIR_RC=$?

echo
echo "TEST20_R1_1_REPAIR_EXIT_CODE=$REPAIR_RC"
echo "TEST20_R1_1_OUTPUT=$OUTPUT"
```

A complete pass requires:

```text
TEST20_R1_1_SOURCE_PUBLICATION_ZIP_SHA256=30ae03d16da40a2f0045030695a7a8b58ca6cb33304ad35f117ecc82e8ce3ac7
TEST20_R1_1_WITHDRAWN_RUNTIME_QUALIFIED_MEMBER_COUNT=101
TEST20_R1_1_RUNTIME_QUALIFIED_MEMBER_COUNT=9
TEST20_R1_1_RUNTIME_QUALIFIED_COMPONENT_COUNT=2
TEST20_R1_1_REAL_SESSION_TYPE_COUNT=3
TEST20_R1_1_ENUM_BACKING_ARRAY_RECLASSIFIED=PASS
TEST20_R1_1_SYNTHETIC_OBFUSCATED_CLASSIFICATION=PASS
TEST20_R1_1_MEMBER_LEVEL_RUNTIME_QUALIFICATION=PASS
TEST20_R1_1_PRIVACY_GATE=PASS
TEST20_R1_1_SANITIZED_PUBLICATION=PASS
TEST20_R1_1_REPAIR=PASS
MAVEN_OPERATION=NONE
GRADLE_OPERATION=NONE
ADB_OPERATION=NONE
PHONE_MUTATION=NONE
MEDIA_ACCESS=NONE
CLOUD_AI_REQUEST=NONE
GLASSES_COMMAND_EXECUTION=NONE
```

The repaired ZIP is reviewable for later publication. Do not publish the
withdrawn Test 20 r1 sanitized ZIP.
