# Network Endpoints

<!-- wiki-status: audience=reference; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Reference |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Public endpoint categories observed

| Category | Example retained by the repository |
|---|---|
| Rokid AI WebSocket | `wss://ai-cloud-global.rokid.com/ws/ai` |
| Model catalog | `/manager/v3/api/model/aggregate` |
| Visual object storage | Rokid-managed object upload and URL reference |
| Firmware/OTA | Rokid firmware-check and policy services |
| App telemetry | Google/Firebase installation and crash-reporting services |

## Glasses network boundary

The glasses contain Wi-Fi, Wi-Fi Direct, Wi-Fi Aware, and Bluetooth software.
During the qualified idle, voice, and fresh-image visual states, glasses Wi-Fi
interfaces remained down and the phone was the observed public-network gateway.

## Interpretation boundary

This is a qualified observation, not proof that every mode, region, firmware,
or custom workflow uses the same network path.

## Authoritative detail

- [Endpoint inventory](../findings/endpoint-inventory.md)
- [AI routing](../findings/ai-assistant-routing.md)
- [Firmware update path](../findings/firmware-update-path.md)
