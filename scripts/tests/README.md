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

- `run_test19_cxr_qualification.sh` — Maven-resolved CXR-M compatibility, reboot, stock-recovery, ownership, and privacy qualification
- `analyze_test19_network.py` — PCAPdroid CSV local/public destination gate
- `analyze_test19_cxr_evidence.py` — sanitized result and classification generator
- `test_test19_cxr_tools.py` — synthetic resolver, artifact, network, evidence, and source-contract tests
