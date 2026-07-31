# Test 20 r1.2 — Final Corrected CXR-L Capability Census Publication

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->

## Purpose

Test 20 r1.2 publishes the reviewed Test 20 r1.1 sanitized capability census
and closes the static CXR-L 1.0.1 census track. It changes documentation and
sanitized publication files only. It performs no Maven, Gradle, ADB, phone,
Bluetooth, media, cloud-AI, or glasses operation.

The original Test 20 r1 sanitized publication remains withdrawn. This closure
promotes only the descriptor-exact r1.1 repair.

## Accepted publication identity

| Item | Exact value |
|---|---|
| Repaired sanitized ZIP SHA-256 | `613c832706422a1cba485ae70e5eac15825692db358fa5fa0006766972849c96` |
| Publication JSON SHA-256 | `a3f261e830910a1664e004feb91af339ea1518230a4c1c6bc8d2205e1075dcc9` |
| Publication Markdown SHA-256 | `41df94552b3348a9cf91a8ff10fa75975ba1f55da3ada0049f7e189a1a9a2ce8` |
| Evidence-hash file SHA-256 | `abe3b505a4290a9a49e9f62a0c682f92b0176f43180126d9821a3f5b5ca65484` |
| Withdrawn source ZIP SHA-256 | `30ae03d16da40a2f0045030695a7a8b58ca6cb33304ad35f117ecc82e8ce3ac7` |
| Withdrawn source JSON SHA-256 | `6e2d05747e88a71a15cd83d5f0549b49f9d35a749e9619f958a704780e650c86` |

## Final corrected boundary

The accepted static census contains:

- 72 public classes or interfaces;
- 56 public constructors;
- 429 public methods;
- 106 public fields;
- three real `CXRSessionType` constants;
- ten native-library instances across two ABIs;
- four JNI exports;
- nine descriptor-exact runtime-qualified members;
- two runtime-qualified Hi Rokid components.

Class participation does not qualify every member of that class. Compiler
helpers, obfuscated members, native bridges, and example-wrapper implementation
surfaces retain explicit origin labels and remain untested unless individually
qualified.

## Runtime-qualified boundary

The nine qualified members are:

- `CXRLink(Context)`;
- `CXRSession(CXRSessionType, String)`;
- `CXRSessionType.CUSTOMAPP`;
- `setCXRLinkCbk(ICXRLinkCbk)`;
- `configCXRSession(CXRSession)`;
- `connect(String)`;
- `disconnect()`;
- `onCXRLConnected(boolean)`;
- `onGlassBtConnected(boolean)`.

The qualified Hi Rokid components are the authorization activity and the
fallback CXR-L service. The exported provider remains statically observed but
runtime-untested.

Camera, audio, AI-assist callbacks, custom commands, custom views, glass-app
management, provider access, and native/JNI behavior remain untested.

## Published files

- [Machine-readable census](../research/connection-protocol/publication/test20-r1-cxr-l-capability-census.json)
- [Human-readable census](../research/connection-protocol/publication/test20-r1-cxr-l-capability-census.md)
- [Evidence identities](../research/connection-protocol/publication/test20-r1-cxr-l-evidence-hashes.txt)
- [Publication schema](../research/connection-protocol/publication/test20-r1-cxr-l-capability-census.schema.json)

## Closure status

```text
TEST20_R1_STATIC_CENSUS=PASS
TEST20_R1_MEMBER_LEVEL_CLASSIFICATION=PASS
TEST20_R1_SANITIZED_PUBLICATION=ACCEPTED
TEST20_R1_GITHUB_PUBLICATION=READY
TEST20_R1_FINAL_STATUS=COMPLETE
PHONE_MUTATION=NONE
MEDIA_ACCESS=NONE
CLOUD_AI_REQUEST=NONE
GLASSES_COMMAND_EXECUTION=NONE
```

The next gate is a separately approved Test 20 r2 control-plane qualification.
Existence in the static census is not authorization to invoke a surface.
