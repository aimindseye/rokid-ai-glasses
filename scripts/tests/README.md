# Numbered Test Runners

## Assistant, OTA, and visual AI

- `run_14a_r2_manual_voice.py`
- `run_14b_firmware_check.py`
- `run_15a_vision_workflow.py`
- `run_15b_visual_routing_retention.py`

## Background lifecycle and privacy

- `run_16a_rokid_background_service.py`
- `run_16b_pixel_clean_install.py`
- `run_16b_r2_unauthenticated_repair.py`
- `run_16c_r2_paired_background.py`
- `run_16d_pixel_background_ab.py`
- `test16_common.py`

## Glasses Android and network baseline

- `check_rokid_adb_state.sh`
- `run_rokid_test17e_visual_ai_interface.sh`
- `run_rokid_test17f_static_dev_baseline.sh`

## Validation and synthetic tests

- `validate_06c_public_findings.sh`
- `validate_10_public_findings.sh`
- `run_synthetic_fixture_tests.sh`
- `test_sanitizers.py`

Consult the matching [runbook index](../../docs/runbooks/README.md) before use.
There is no independent companion-app or Developer Mode replay runner yet.

## Replacement companion qualification

- `prepare_test19_r2.sh` — exact CXR-L 1.0.1 resolution, build, and install
- `run_test19_r2_connection.sh` — one authorization/connection/stock-recovery run
- `run_test19_r2_privacy.sh` — separate PCAPdroid metadata gate
- `record_test19_r2_firmware_transition.sh` — read-only transition evidence assembly
- `analyze_test19_r2_events.py` — sanitized connection classification
- `analyze_test19_r2_network.py` — custom-app versus stock-app destination classification
- `publish_test19_r2_comparison.py` — private-ZIP verification and sanitized final comparison publication
- `test_test19_r2_tools.py` — synthetic stage, privacy, and source-contract tests
- `run_test19_cxr_qualification.sh` — disabled historical r1 CXR-M runner
