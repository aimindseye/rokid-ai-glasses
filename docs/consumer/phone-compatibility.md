# Phone Compatibility

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Three different compatibility questions

1. Can the phone install and run Hi Rokid?
2. Can it pair with and operate the glasses?
3. Does it pass a specific feature gate such as local-model support?

A phone can pass the first two and fail the third.

## Phones physically used by this project

| Phone | Project role | Qualified result |
|---|---|---|
| Samsung Galaxy S25 Ultra | Current primary phone | Hi Rokid operation, network testing, AI tests, firmware checks, and access to the local-model workflow |
| Motorola Razr 2024 | Earlier test phone | General workflows worked; the local-model workflow was blocked by the app's hardware gate |
| Google Pixel 7 | Network-analysis phone | TLS-decryption workflow validated; not qualified here as a local-model phone |

Only the Galaxy S25 Ultra is physically qualified by this project for the
current local-model entry point.

## App-displayed compatibility lists

Hi Rokid displayed a list of phone names marked tested/available on
2026-07-20. That list is preserved in the historical compatibility page and is
not independent validation of every listed device. Availability can change by
app version, rollout, region, chipset, RAM, and OS.

## Reporting compatibility

Include the phone model, region, OS version, Hi Rokid version, glasses firmware,
feature entry point, exact result, and repeatability. Remove serials, account
IDs, Bluetooth addresses, and authorization data.

## Technical evidence

- [Historical app-displayed phone list](phone-and-local-model-compatibility.md#archived-compatibility-snapshot)
- [Compatibility-report instructions](../contributing/consumer-reports.md)
