# Test 10a — Face-to-Face Input Routing

## Status

Complete — PASS.

## Question

Does Face-to-Face translation consume audio from the glasses or from the
companion phone?

## Method

The routing question was tested in two ways:

1. A controlled source-placement preflight compared speech near the glasses
   with speech near the companion phone.
2. Later Local and Online runs captured application and Android audio-routing
   logs while Face to Face was active.

The companion phone remained physically separated from the external source
during the controlled comparison.

## Evidence

The controlled source near the glasses triggered translation, while the
source near the phone did not produce the same result.

Application logs during later runs reported:

- translation mode set to Local or Online,
- `translateAudioModeOmni=false`, and
- an audio listener starting from the glasses.

Android audio state showed the completed translated speech routed through
Bluetooth A2DP.

## Result

For the tested display-free glasses and application version:

```text
Face-to-Face input:
glasses microphone -> companion application
```

```text
Spoken translated output:
companion application -> Bluetooth A2DP -> glasses speakers
```

This result applies to the tested Face-to-Face profile. It should not be
generalized to every translation mode without a separate routing test.

## Privacy note

The public report excludes raw logs, device names, Bluetooth addresses,
serials, and screenshots.
