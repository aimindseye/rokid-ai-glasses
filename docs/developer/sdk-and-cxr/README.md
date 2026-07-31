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
- SDK source, license, credentials, and package identities recorded;
- no custom application payload or captured-command replay outside an approved
  API contract.

## Qualification result labels

- **Supported:** documented and physically proven on Style.
- **Works experimentally:** physically proven but not an official contract.
- **Reference only:** useful source or architecture, not Style-compatible.
- **Blocked:** unavailable credentials, package, permission, or model support.
- **Unverified:** not yet tested.

## Sources retained by the repository

- [External resources](../../reference/external-resources.md)
- [Community ecosystem legacy page](../../development/community-ecosystem.md)
