# Test 16A Runbook — Existing-Install Background Lifecycle

## Purpose

Compare task dismissal, package force-stop, screen-off behavior, and app
relaunch on an already paired phone.

## Safety

- Keep the glasses powered and stable.
- Do not restart, power-cycle, factory-reset, or unbind them.
- Treat every output as private evidence.

## Phases

1. Remove Hi Rokid from Recents; observe process, services, notifications,
   Bluetooth, sockets, and network.
2. Force-stop Hi Rokid; observe with the screen on.
3. Keep Hi Rokid force-stopped; observe with the screen off.
4. Relaunch as a positive control and verify glasses/battery reconnection.

## Runner

```bash
python3 scripts/tests/run_16a_rokid_background_service.py \
  --observe-minutes 10 \
  --control-minutes 5 \
  --snapshot-seconds 30 \
  --bugreport \
  --zip
```

The runner is the original private-evidence workflow. Do not upload its output.
For new work, prefer the privacy-first Test 16B–16D scripts.
