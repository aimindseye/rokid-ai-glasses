# Privacy and Cloud Services

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Observed stock architecture

During the tested voice and visual AI workflows, the phone was the observed
public-network gateway. Hi Rokid maintained account state, an authenticated AI
WebSocket, device context, model routing, and visual uploads.

## Data categories observed in supported workflows

Depending on the feature, session context included categories such as:

- Rokid account and device state;
- model-route configuration;
- precise location fields and weather context;
- media objects used for visual requests;
- payment-capability configuration;
- conversation text and app-private thumbnails.

The presence of payment components or capability fields is not evidence that a
card, wallet balance, or transaction was accessed.

## Background operation

Hi Rokid services and the AI WebSocket continued after the visible task was
removed from Recents in the tested paired state. Android force-stop terminated
the observed runtime until the app was launched again.

## First launch

A clean first launch contacted Rokid and Google/Firebase before Rokid login.
Observed activity included installation registration, crash-reporting
configuration, app/device metadata, and a Rokid token-bootstrap request with an
empty token value.

## Practical controls

- Review camera, microphone, location, notification, and media permissions.
- Use Android force-stop when you need a stronger stop boundary than Recents.
- Do not assume a model label means direct provider or fully local processing.
- Avoid sensitive visual or voice content unless the workflow is appropriate.

## Technical evidence

- [Security and privacy observations](../findings/security-and-privacy-observations.md)
- [Background services and data sharing](../findings/background-services-and-data-sharing.md)
- [Endpoint inventory](../findings/endpoint-inventory.md)
