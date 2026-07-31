# Android Services Reference

<!-- wiki-status: audience=reference; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Reference |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Phone-side components observed

| Component | Observed responsibility |
|---|---|
| Hi Rokid activity/UI | Pairing, settings, models, firmware, history, and phone-facing controls |
| `AiService` | Foreground connected-device and AI-session runtime |
| `ConnectCompanionDeviceService` | Persistent glasses transport and reconnection |
| `LocationService` | Location context for supported workflows |
| App-private cache/database | Conversation text, answers, and retained thumbnails |

## Glasses-side boundary

The glasses are a complete Android device with privileged Rokid services. A
root TEE-domain service retained a TCP 8341 listener in the tested state, while
no active non-loopback IP interface exposed it during the qualified stock AI
workflows.

## Protected companion boundary

The global Hi Rokid package uses a protected native-loader and wrapper path.
Research recovered bounded loader, JNI-registration, class-origin, and caller
facts without assigning unsupported business-feature meaning.

## Authoritative detail

- [Background services](../findings/background-services-and-data-sharing.md)
- [Local services and port 8341](../findings/glasses-local-services-and-port-8341.md)
- [Protected-application research](../research/protected-application/README.md)
