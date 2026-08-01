# Test 20 r3 — CXR-L Media-Plane Contract, Callback, and Privacy Feasibility Qualification

## Purpose

Test 20 r3 narrows the accepted Test 20 r1.2 capability census to the stable,
declared public image, audio, and media-service contracts needed before any
runtime media work is approved.

The test is read-only. It does not build or install an application and does not
invoke any media API.

## Fixed baseline

- Repository: `91b9922ad7a3b7e8ee6f882e1b7f498069e926a0`
- CXR-L: `com.rokid.cxr:client-l:1.0.1`
- AAR SHA-256: `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`
- POM SHA-256: `d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a`
- Accepted census JSON SHA-256: `a3f261e830910a1664e004feb91af339ea1518230a4c1c6bc8d2205e1075dcc9`
- Hi Rokid: `G1.11.11.0727`
- Firmware context: `1.23.009-20260725-153201`

## Descriptor-exact boundary

The analyzer requires 23 stable declared public members:

- eight client entry points, including callback registration, photo request,
  audio start/stop, service version, and Bluetooth status;
- five image/audio callbacks; and
- ten `IMediaStreamService` contract members.

Every member must remain `untested`, must not be `runtime-qualified`, and must
have `surface_origin=declared-public-api`. Compiler-generated, obfuscated, and
native bridge members are excluded from the stable contract.

The exported `CXRLinkService` connection lifecycle is already qualified by Test
19, but this does not qualify any media operation carried by that service.

## Qualified conclusion

```text
IMAGE_CONTROL_PATH=STATICALLY_PRESENT
IMAGE_CALLBACK_PATH=STATICALLY_PRESENT
AUDIO_CONTROL_PATH=STATICALLY_PRESENT
AUDIO_CALLBACK_PATH=STATICALLY_PRESENT
MEDIA_SERVICE_CONTRACT=STATICALLY_PRESENT
PARAMETER_SEMANTICS=UNRESOLVED
PAYLOAD_FORMATS=UNRESOLVED
RUNTIME_QUALIFICATION=NOT_GRANTED
```

A passing result does not prove that a photo or audio frame can be captured,
that parameter values are safe, or that returned bytes use a particular
encoding.

## Safety boundary

```text
RUNTIME_MEDIA_INVOCATION=NONE
PHONE_OPERATION=NONE
GLASSES_OPERATION=NONE
ADB_OPERATION=NONE
MAVEN_OPERATION=NONE
GRADLE_OPERATION=NONE
CLOUD_REQUEST=NONE
```

## Run

```bash
OUTPUT="$HOME/rokid-nettest/private/test20-r3-media-feasibility-$(date -u +%Y%m%dT%H%M%SZ)"

bash scripts/tests/run_test20_r3_media_feasibility.sh \
  --repo "$HOME/Documents/projects/rokid-ai-glasses" \
  --output "$OUTPUT"
```

Upload only `${OUTPUT}-sanitized-publication.zip` and its SHA-256 sidecar.

## Next stage

A passing result permits design of
`TEST20_R3_1_SERVICE_STATUS_AND_NO_PAYLOAD_PREFLIGHT`. It does not authorize
photo capture, image callback payload collection, or audio streaming.


## Accepted publication closure

Test 20 r3.0.1 publishes the reviewed sanitized census and closes this static
feasibility phase.

```text
SANITIZED_PUBLICATION_ZIP_SHA256=5e3190657a65565cf91c9711cb25e7c0d269fa46287bbafee72e8a03e71b1333
PUBLICATION_JSON_SHA256=848114e60720b3014a5ec8b361ca1223f636437e9f976733af129630a944aa5d
PUBLICATION_MARKDOWN_SHA256=3999fc2e1d321896bba6c4636b71e0a0cf8a24ac039036058469af0941177ef8
MEDIA_SURFACE_COUNT=23
RUNTIME_MEDIA_INVOCATION=NONE
RUNTIME_QUALIFICATION=NOT_GRANTED
TEST20_R3_FINAL_STATUS=COMPLETE
```

- [Final publication closure](test-20-r3-0-1-final-media-plane-feasibility-publication.md)
- [Published feasibility census](../research/connection-protocol/publication/test20-r3-cxr-l-media-plane-feasibility.md)
- [Evidence identities](../research/connection-protocol/publication/test20-r3-cxr-l-evidence-hashes.txt)

The next gate remains Test 20 r3.1 service-status and no-payload preflight.
