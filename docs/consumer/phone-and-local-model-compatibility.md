# Phone and Local-Model Compatibility

## Three separate questions

1. Can the phone install and run Hi Rokid?
2. Can it pair and operate the glasses?
3. Does it pass the local-model feature gate?

A phone can pass the first two and fail the third.

## Lab-tested phones

| Phone | Role | Result |
|---|---|---|
| Samsung Galaxy S25 Ultra | Current primary phone | Validated for Hi Rokid, TLS/network testing, AI assistant tests, firmware tests, and access to the local-model workflow |
| Motorola Razr 2024 (XT2453V) | Earlier phone | General testing worked; local-model workflow was blocked by the app's hardware gate |
| Google Pixel 7 | Network-analysis phone | PCAPdroid TLS decryption validated; not qualified here as a local-model phone |

Only the Galaxy S25 Ultra is physically validated by this project for the
current local-model workflow.

## Hi Rokid “tested and available” snapshot

Transcribed from Hi Rokid on 2026-07-20:

| Brand | Models displayed |
|---|---|
| Xiaomi | 15 Ultra; 17; 17 Max; 17 Pro Max |
| Redmi | K80 Pro; K90; K90 Pro Max |
| OPPO | Find N5; Find N6 Collector Edition; Find X7 Ultra; Find X8 Ultra; Find X9 Ultra |
| realme | Neo8 |
| OnePlus | 12; Ace 3 Pro; Ace 6T; 15R |
| vivo | X300 Ultra; X300 FE; S50 Pro Mini |
| iQOO | 13 |
| Samsung | Galaxy S25 Ultra; S26; S26+; S26 Ultra |
| Apple | iPhone 17 Pro |
| Sony | Xperia 1 VII |

![Hi Rokid local-model compatibility page](../assets/hi-rokid-local-model-phone-list-20260720.jpg)

## Interpretation limits

- This is what the app displayed, not independent validation of every phone.
- Availability may depend on app version, OS, chipset, RAM, region, and rollout.
- A listed future device name is not proof of retail availability everywhere.
- iOS and Android may use different local-model packaging.
- The list can change without a glasses firmware update.

## Reporting a result

Include phone, region, OS, Hi Rokid version, glasses firmware, feature entry
point, and exact outcome. Remove IDs and Bluetooth addresses.
