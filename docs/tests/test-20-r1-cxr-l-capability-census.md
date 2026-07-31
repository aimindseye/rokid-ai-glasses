# Test 20 r1 — CXR-L SDK and Runtime Capability Census

## Purpose

Test 20 r1 performs a read-only census of the exact attested
`com.rokid.cxr:client-l:1.0.1` artifact and the matching Hi Rokid CXR-L
integration surface. It does not call ADB, mutate the phone, access media, send
a cloud AI request, or execute a command on the glasses.

The census is the selection gate for later bounded Test 20 runtime work. A
surface is not considered supported merely because it exists in the AAR.

## Fixed baseline

| Item | Exact value |
|---|---|
| CXR-L coordinate | `com.rokid.cxr:client-l:1.0.1` |
| AAR SHA-256 | `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e` |
| POM SHA-256 | `d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a` |
| Hi Rokid package | `com.rokid.sprite.global.aiapp` |
| Hi Rokid version | `G1.11.11.0727` |
| Hi Rokid version code | `10110011` |
| Hi Rokid baseline ZIP SHA-256 | `b75e7ea3da7c164493c24efdcd411ef70d51c214e82f2b99af7a69ab2cab134e` |
| Runtime qualification | Accepted Test 19 r2.4.1 publication |

## Census coverage

The private census records:

- every class entry in `classes.jar`;
- every public class, interface, constructor, method, field, and enum constant;
- exact JVM descriptors and inheritance/interface relationships;
- callback interfaces and callback methods;
- POM dependencies;
- `CXRSessionType` values and `CXRSession` configuration shapes;
- AAR native libraries by ABI, size, SHA-256, ELF class, dynamic-symbol count,
  and JNI export name;
- the Hi Rokid authorization activity, CXR-L service, and provider, including
  exported state, intent actions, authority, and runtime package corroboration;
- classification of each public surface as one or more of:
  `directly-callable`, `callback-only`, `service/provider-mediated`,
  `internal-or-implementation-detail`, `runtime-qualified`, and `untested`.

The sanitized publication omits proprietary binary bytes, full non-JNI native
symbol tables, local paths, device serials, Bluetooth addresses, authorization
tokens, and media payloads.

## Run

```bash
REPO="$HOME/Documents/projects/rokid-ai-glasses"
HI_ROKID_PRIVATE_ZIP="$HOME/rokid-nettest/private/hi-rokid-installed-version-baseline-20260731T145647Z-private-evidence.zip"
OUTPUT="$HOME/rokid-nettest/private/test20-r1-cxr-l-capability-census-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$REPO"

bash scripts/tests/run_test20_r1_census.sh \
  --repo "$REPO" \
  --sdk-version 1.0.1 \
  --hi-rokid-private-zip "$HI_ROKID_PRIVATE_ZIP" \
  --output "$OUTPUT"

CENSUS_RC=$?

echo
echo "TEST20_R1_CENSUS_EXIT_CODE=$CENSUS_RC"
echo "TEST20_R1_OUTPUT=$OUTPUT"
```

The script must end with:

```text
TEST20_R1_EXACT_ARTIFACT_IDENTITY=PASS
TEST20_R1_PUBLIC_API_CENSUS=PASS
TEST20_R1_INHERITANCE_AND_DEPENDENCY_GRAPH=PASS
TEST20_R1_SESSION_TYPE_CENSUS=PASS
TEST20_R1_HI_ROKID_COMPONENT_COMPARISON=PASS
TEST20_R1_NATIVE_AND_JNI_CENSUS=PASS
TEST20_R1_CAPABILITY_CLASSIFICATION=PASS
TEST20_R1_SANITIZED_PUBLICATION=PASS
TEST20_R1_CENSUS=PASS
ADB_OPERATION=NONE
PHONE_MUTATION=NONE
MEDIA_ACCESS=NONE
CLOUD_AI_REQUEST=NONE
GLASSES_COMMAND_EXECUTION=NONE
```

## Outputs

The output root contains private Maven artifacts and private machine-readable
analysis. Do not publish that directory or its private ZIP.

The `sanitized-publication` subdirectory contains only:

- `test20-r1-cxr-l-capability-census.json`;
- `test20-r1-cxr-l-capability-census.md`;
- `test20-r1-cxr-l-evidence-hashes.txt`.

Review the sanitized files before publication. A later publication-only closure
may promote those exact files into the repository after their hashes and
privacy gates are verified.

## Interpretation boundary

`runtime-qualified` is limited to surfaces exercised by the accepted Test 19
path: authorization, CUSTOMAPP session configuration, CXR-L connection and
Bluetooth callbacks, fallback-assisted service connection, disconnect, and
stock Hi Rokid recovery. Image, audio, custom-command, custom-view, glass-app,
and remaining native/JNI surfaces remain `untested` until separately approved.
