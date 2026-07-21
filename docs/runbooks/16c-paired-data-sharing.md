# Test 16C-r2 Runbook — Pairing and Paired Data Sharing

## Purpose

Capture the transition from logged-in/unpaired to paired operation, one voice
request, one visual request, task dismissal, force-stop controls, and relaunch.

## Safety

- Use the same Rokid account for the controlled phone comparison.
- Do not restart, power-cycle, or factory-reset the glasses.
- Unbind the prior phone only when the runner reaches the pairing phase.
- Do not capture login credentials; complete login before controlled capture.

## Runner

```bash
python3 scripts/tests/run_16c_r2_paired_background.py \
  --observe-minutes 3 \
  --control-minutes 2 \
  --snapshot-seconds 20
```

PCAPdroid must use a Hi Rokid app filter, app-based decryption rule, TLS
decryption, QUIC blocking, and PCAP-file output.

Upload only the privacy-gated sanitized ZIP.
