#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_test20_r3_2_1_photo_repair.py"
FW = "1.23.009-20260725-151201"
RUN_ID = "synthetic-r3.2.1"


def event(event_type: str, details: dict | None = None) -> dict:
    return {
        "schema": "rokid.test20-r3.2.event.v1",
        "run_id": RUN_ID,
        "firmware": FW,
        "package": "org.aimindseye.rokid.cxrphotoqualification",
        "event_type": event_type,
        "details": details or {},
    }


def prerequisite_events() -> list[dict]:
    return [
        event("authorization_result", {"token_present": True, "token_value_logged": False}),
        event("session_config_result", {"configured": True, "session_type": "CUSTOMAPP"}),
        event("image_callback_registration_result", {
            "audio_callback_registered": False,
            "media_request_issued": False,
            "method": "setCXRImageCbk(IImageStreamCbk)V",
            "registration_error_class": "",
            "registration_returned": True,
        }),
        event("callback_cxrl_connected", {"connected": True}),
        event("callback_glass_bt_connected", {"connected": True}),
        event("service_status_result", {"status_success": True, "glass_bt_status": True}),
        event("operator_gate_initialized", {
            "phase": "PREREQUISITE_LOCKED",
            "photo_control_enabled": False,
            "host_arm_granted": False,
            "arm_token_present": True,
            "arm_token_value_logged": False,
        }),
        event("operator_gate_prerequisite_ready", {
            "photo_control_enabled": False,
            "host_arm_granted": False,
            "photo_request_issued": False,
        }),
        event("photo_request_result", {"request_count": 0, "returned": False}),
        event("qualification_terminal", {
            "photo_request_count": 0,
            "image_payload_callback_count": 0,
            "image_error_callback_count": 0,
        }),
        event("run_completed", {
            "take_photo_request_count": 0,
            "start_audio_stream_invocation": 0,
            "stop_audio_stream_invocation": 0,
        }),
    ]


def armed_events() -> list[dict]:
    return prerequisite_events() + [
        event("operator_gate_arm_result", {
            "granted": True,
            "photo_ready": True,
            "photo_request_issued": False,
            "host_arm_available": True,
        }),
        event("operator_gate_host_command", {
            "action": "ARM_ONE_PHOTO",
            "run_id_match": True,
            "token_present": True,
            "token_match": True,
            "token_value_logged": False,
            "granted": True,
            "photo_control_enabled_after_command": True,
        }),
    ]


def final_events() -> list[dict]:
    return armed_events() + [
        event("photo_request_result", {
            "method": "takePhoto(III)Z",
            "request_count": 1,
            "returned": True,
        }),
        event("operator_gate_capture_dispatch", {
            "controller_request_accepted": True,
            "photo_control_enabled_after_click": False,
        }),
    ]


class AnalyzerTests(unittest.TestCase):
    def run_case(self, events: list[dict], *, mode: str, operator: dict[str, str] | None = None, visible_fw: str = FW):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            events_path = root / "events.jsonl"
            events_path.write_text("\n".join(json.dumps(x) for x in events) + "\n", encoding="utf-8")
            fw = root / "firmware-attestation.txt"
            fw.write_text(
                "\n".join(
                    [
                        "TEST20_R3_2_1_SCHEMA=rokid.test20-r3.2.1.firmware-attestation.v1",
                        f"FIRMWARE_LABEL={FW}",
                        f"OPERATOR_VISIBLE_FIRMWARE={visible_fw}",
                        "OPERATOR_EXACT_MATCH=PASS",
                        "OCR_USED=NO",
                        "SCREENSHOT_SHA256=" + "a" * 64,
                        "SCREENSHOT_BYTES=12345",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = root / "summary.json"
            cmd = [
                "python3",
                str(ANALYZER),
                "--mode",
                mode,
                "--events",
                str(events_path),
                "--firmware",
                FW,
                "--firmware-attestation",
                str(fw),
                "--summary",
                str(summary),
            ]
            if operator is not None:
                op = root / "operator.txt"
                op.write_text("\n".join(f"{k}={v}" for k, v in operator.items()) + "\n", encoding="utf-8")
                cmd += ["--operator-attestation", str(op)]
            result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            payload = json.loads(summary.read_text()) if summary.exists() else None
            return result, payload

    @staticmethod
    def good_operator() -> dict[str, str]:
        return {
            "TEST20_R3_2_1_SCHEMA": "rokid.test20-r3.2.1.3.operator-attestation.v1",
            "PREREQUISITE_GATE": "PASS",
            "FIRMWARE_EXACT_MATCH": "PASS",
            "HOST_ARM_GATE": "PASS",
            "APK_ARMED_UI_CONFIRMED": "PASS",
            "PHOTO_ARM_GRANTED": "YES",
            "ADDITIONAL_MEDIA_ACTION": "NO",
            "HI_ROKID_RECOVERY": "PASS",
        }

    def test_prerequisite_passes_before_photo(self):
        result, payload = self.run_case(prerequisite_events(), mode="prerequisite")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["TEST20_R3_2_1_PREREQUISITE_GATE"], "PASS")

    def test_prerequisite_fails_if_photo_already_issued(self):
        events = prerequisite_events() + [event("take_photo_invocation", {"photo_request_count": 1})]
        result, _ = self.run_case(events, mode="prerequisite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already issued", result.stderr)

    def test_final_passes_with_exactly_one_request(self):
        events = final_events() + [
            event("image_payload_received", {"image_payload_callback_count": 1}),
            event("qualification_terminal", {"photo_request_count": 1, "image_callback_count": 1, "audio_start_count": 0}),
        ]
        result, payload = self.run_case(events, mode="final", operator=self.good_operator())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["photo_request"]["resolved_count"], 1)
        self.assertEqual(payload["callback_result"]["classification"], "ONE_IMAGE_CALLBACK")
        self.assertEqual(payload["operator_gate"]["bounded_test_target_derived"], "PASS")

    def test_invocation_plus_result_is_still_one_request(self):
        events = final_events() + [
            event("take_photo_invocation", {"photo_request_count": 1}),
        ]
        result, payload = self.run_case(events, mode="final", operator=self.good_operator())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["photo_request"]["resolved_count"], 1)
        self.assertEqual(payload["photo_request"]["result_event_count"], 2)

    def test_final_fails_on_two_requests(self):
        events = final_events() + [
            event("take_photo_invocation", {"photo_request_count": 1}),
            event("take_photo_invocation", {"photo_request_count": 2}),
        ]
        result, _ = self.run_case(events, mode="final", operator=self.good_operator())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected exactly one photo request", result.stderr)

    def test_final_fails_when_operator_reports_other_media(self):
        events = final_events()
        operator = self.good_operator()
        operator["ADDITIONAL_MEDIA_ACTION"] = "YES_OR_UNRESOLVED"
        result, _ = self.run_case(events, mode="final", operator=operator)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("operator gate mismatch", result.stderr)

    def test_prerequisite_fails_if_registration_returned_false(self):
        events = prerequisite_events()
        for item in events:
            if item["event_type"] == "image_callback_registration_result":
                item["details"]["registration_returned"] = False
        result, _ = self.run_case(events, mode="prerequisite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("registration_returned=true", result.stderr)

    def test_prerequisite_fails_if_registration_event_says_media_already_issued(self):
        events = prerequisite_events()
        for item in events:
            if item["event_type"] == "image_callback_registration_result":
                item["details"]["media_request_issued"] = True
        result, _ = self.run_case(events, mode="prerequisite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("media_request_issued=false", result.stderr)

    def test_prerequisite_fails_if_audio_callback_registered(self):
        events = prerequisite_events()
        for item in events:
            if item["event_type"] == "image_callback_registration_result":
                item["details"]["audio_callback_registered"] = True
        result, _ = self.run_case(events, mode="prerequisite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("audio_callback_registered=false", result.stderr)

    def test_armed_gate_passes_before_operator_tap(self):
        result, payload = self.run_case(armed_events(), mode="armed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["TEST20_R3_2_1_3_ARMED_GATE"], "PASS")

    def test_armed_gate_fails_on_bad_token_match(self):
        events = armed_events()
        for item in events:
            if item["event_type"] == "operator_gate_host_command":
                item["details"]["token_match"] = False
        result, _ = self.run_case(events, mode="armed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("token_match=true", result.stderr)

    def test_prerequisite_fails_if_photo_control_enabled_early(self):
        events = prerequisite_events()
        for item in events:
            if item["event_type"] == "operator_gate_prerequisite_ready":
                item["details"]["photo_control_enabled"] = True
        result, _ = self.run_case(events, mode="prerequisite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("photo control disabled", result.stderr)

    def test_firmware_visible_string_must_exactly_match(self):
        result, _ = self.run_case(prerequisite_events(), mode="prerequisite", visible_fw="1.23")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("firmware attestation mismatch", result.stderr)

    def test_final_fails_on_audio_operation(self):
        events = final_events() + [
            event("audio_stream_start", {"audio_start_count": 1}),
        ]
        result, _ = self.run_case(events, mode="final", operator=self.good_operator())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("audio operation evidence", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
