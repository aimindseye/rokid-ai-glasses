# Test 16D Runbook — Pixel Background Mode A/B

## Purpose

Compare identical paired lifecycle behavior before and after satisfying Hi
Rokid's in-app background-enable banner.

## Scope

This test does not repeat login, pairing, voice AI, visual AI, or media
transfer.

## Runner

```bash
python3 scripts/tests/run_16d_pixel_background_ab.py \
  --idle-minutes 1 \
  --observe-minutes 3 \
  --screen-off-minutes 3 \
  --control-minutes 2 \
  --snapshot-seconds 20
```

Arm A records the current banner-unsatisfied state. The runner then records
Android app-ops, standby bucket, Doze allowlist, notification permission,
companion association, and service state before and after **Go to enable**.
Arm B repeats the same Recents and screen-off behavior.

Upload only the generated `-SANITIZED-UPLOAD.zip`.
