# SDK and CXR Qualification

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=unverified; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Unverified |
| Last reviewed | 2026-07-30 |


## Compatibility warning

Rokid SDKs and community projects span display-equipped, enterprise, regional,
and older products. A package named CXR or YodaOS is not automatically a
supported contract for the non-display Style firmware.

## Candidate paths

| Path | Why it matters | Style status |
|---|---|---|
| CXR-M or equivalent mobile SDK | Phone discovery, connection, status, media, and control | Immediate qualification target |
| CXR-S or equivalent glasses-side SDK | Bidirectional phone/glasses bridge | Not qualified |
| AI media or agent SDK | Voice/camera workflow integration | Not qualified |
| Community companion code | Reference architecture and protocol clues | Model-specific validation required |
| Direct RFCOMM work | Fallback for unsupported interfaces | Transport foundation only; application sender not authorized |

## Test 19 entry criteria

- exact post-reset device and firmware recorded;
- Samsung Galaxy S25 Ultra used as the controlled primary phone;
- Hi Rokid retained for recovery and coexistence tests;
- Maven metadata, resolved version, POM/AAR hashes, and API identities recorded;
- no custom application payload or captured-command replay outside an approved
  API contract.

## Qualification result labels

- **Supported:** documented and physically proven on Style.
- **Works experimentally:** physically proven but not an official contract.
- **Reference only:** useful source or architecture, not Style-compatible.
- **Blocked:** unavailable artifact, package, permission, entitlement, or model support.
- **Unverified:** not yet tested.

## Sources retained by the repository

- [External resources](../../reference/external-resources.md)
- [Community ecosystem legacy page](../../development/community-ecosystem.md)

## Test 19 implementation

The repository now includes a dedicated, SDK-version-neutral qualification
client and host runner. The operator supplies an authorized AAR or exact Maven
coordinate; the app discovers the actual `CxrApi` runtime class and supported
connection overloads rather than treating a community version number as an
official Style contract.

- [Test 19 qualification runbook](../companion-app/test-19-r1-qualification.md)
- [Test 19 research record](../../tests/test-19-r1-cxr-m-maven-and-ownership.md)
- `android-client:test19` application module
- `scripts/tests/run_test19_cxr_qualification.sh`
- `scripts/research/cxr/analyze_cxr_artifact.py`

No downloaded SDK artifact or private runtime evidence is committed or published.
