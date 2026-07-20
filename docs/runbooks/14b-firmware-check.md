# Runbook — Test 14B

## Hardware rule

Do not power-cycle the glasses between phases. Run disconnected and connected
groups separately.

## Disconnected

Only D1 is meaningful:

- relaunch Hi Rokid;
- keep glasses disconnected;
- wait 60 seconds;
- collect capture, key log, logs, screenshot, and UI XML.

The firmware page is disabled while disconnected.

## Connected

Begin with glasses already powered on and stable.

| Phase | Action |
|---|---|
| C1 | Connected cold app launch |
| C2 | Open Devices/firmware page without pressing check |
| C3 | First manual check |
| C4 | Repeated manual check in same session |
| C5 | Optional phone-internet-offline check |

## Runner

```bash
python3 scripts/tests/run_14b_firmware_check.py --mode connected --zip --bugreport
```

Every phase requires a PCAP and SSL key log. Raw evidence remains private.
