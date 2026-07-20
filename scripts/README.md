# Public Scripts

These interactive tools generate **private evidence**. Their output should be
stored outside the Git worktree.

## Tests

- `tests/run_14a_r2_manual_voice.py`
- `tests/run_14b_firmware_check.py`
- `tests/run_15a_vision_workflow.py`
- `tests/run_15b_visual_routing_retention.py`

## Recovery

- `recovery/audit_recover_14a_r2_evidence.py`
- `recovery/recover_14b_d1_media.py`
- `recovery/finalize_14b_disconnected_d1.py`

## Requirements

- Python 3.10+
- Android platform tools (`adb`)
- authorized Android phone
- PCAPdroid configured for the controlled app/account

Generated evidence can include captures, TLS keys, screenshots, logs,
bugreports, session data, and precise context.
