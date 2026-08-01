#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

EXPECTED_PACKAGE = "org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_VERSION = "1.0-test20-r3.2.1.3"
EXPECTED_FW_SCHEMA = "rokid.test20-r3.2.1.firmware-attestation.v1"
EXPECTED_OPERATOR_SCHEMA = "rokid.test20-r3.2.1.3.operator-attestation.v1"

AUTH_EVENT = "authorization_result"
SESSION_EVENT = "session_config_result"
REG_EVENT = "image_callback_registration_result"
CXRL_CONNECTED_EVENT = "callback_cxrl_connected"
BT_CONNECTED_EVENT = "callback_glass_bt_connected"
SERVICE_EVENT = "service_status_result"
GATE_INIT_EVENT = "operator_gate_initialized"
GATE_READY_EVENT = "operator_gate_prerequisite_ready"
GATE_HOST_COMMAND_EVENT = "operator_gate_host_command"
GATE_ARM_EVENT = "operator_gate_arm_result"
GATE_CAPTURE_EVENT = "operator_gate_capture_dispatch"

PHOTO_REQUEST_EVENTS = {
    "photo_request_issued",
    "take_photo_invocation",
    "take_photo_invoked",
    "take_photo_request",
    "take_photo_request_issued",
}
PHOTO_RESULT_EVENTS = {
    "photo_request_result",
    "take_photo_result",
}
IMAGE_CALLBACK_EVENTS = {
    "callback_image",
    "image_callback",
    "image_payload_callback",
    "photo_callback",
    "photo_success_callback",
    "callback_photo",
    "image_payload_received",
}
IMAGE_ERROR_EVENTS = {
    "callback_image_error",
    "image_error_callback",
    "photo_error_callback",
    "callback_photo_error",
}
AUDIO_EVENTS_RE = re.compile(r"(?i)(audio.*(?:start|stop|stream)|(?:start|stop).*audio)")

PHOTO_COUNT_KEYS = {
    "photo_request_count",
    "photo_requests",
    "take_photo_count",
    "take_photo_request_count",
    "take_photo_invocation_count",
    "photo_invocation_count",
}
IMAGE_CALLBACK_COUNT_KEYS = {
    "image_callback_count",
    "photo_callback_count",
    "image_payload_callback_count",
}
IMAGE_ERROR_COUNT_KEYS = {
    "image_error_callback_count",
    "photo_error_callback_count",
}
AUDIO_COUNT_KEYS = {
    "audio_request_count",
    "audio_start_count",
    "audio_stop_count",
    "audio_stream_start_count",
    "audio_stream_stop_count",
}

MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
LOCAL_PATH_RE = re.compile(r"/(?:Users|home)/[^/\s]+/")
TOKEN_VALUE_RE = re.compile(
    r"(?i)\b(?:authorization|bearer|access[_-]?token|refresh[_-]?token|session[_-]?token)\b\s*[:=]\s*[^\s,}\]]{8,}"
)


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_kv(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise GateError(f"required attestation file is missing: {path}")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise GateError(f"event stream is missing or empty: {path}")
    events: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GateError(f"invalid JSONL at line {lineno}: {exc}") from exc
        if not isinstance(item, dict):
            raise GateError(f"event line {lineno} is not a JSON object")
        events.append(item)
    if not events:
        raise GateError("event stream contained no JSON objects")
    return events


def details(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("details")
    return value if isinstance(value, dict) else {}


def event_type(event: dict[str, Any]) -> str:
    value = event.get("event_type")
    return str(value).strip() if value is not None else ""


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "pass", "passed", "success", "connected"}:
            return True
        if normalized in {"false", "no", "n", "0", "fail", "failed", "error", "disconnected"}:
            return False
    return None


def intish(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


def find_events(events: Iterable[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [event for event in events if event_type(event) == name]


def require_event(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = find_events(events, name)
    if not matches:
        raise GateError(f"required control-path event not observed: {name}")
    return matches[-1]


def require_true_if_present(d: dict[str, Any], keys: Iterable[str], *, label: str, require_one: bool = True) -> None:
    found = False
    for key in keys:
        if key not in d:
            continue
        found = True
        value = boolish(d[key])
        if value is not True:
            raise GateError(f"{label}: {key} was not true")
    if require_one and not found:
        raise GateError(f"{label}: no recognized success field was present")


def verify_event_identity(events: list[dict[str, Any]], expected_firmware: str) -> dict[str, Any]:
    run_ids = {str(event.get("run_id", "")).strip() for event in events if str(event.get("run_id", "")).strip()}
    if len(run_ids) != 1:
        raise GateError(f"event stream must contain exactly one non-empty run_id; found {sorted(run_ids)}")

    firmware_values = {
        str(event.get("firmware", "")).strip()
        for event in events
        if str(event.get("firmware", "")).strip()
    }
    if firmware_values and firmware_values != {expected_firmware}:
        raise GateError(
            "event firmware label does not match the exact attested firmware: "
            + ", ".join(sorted(firmware_values))
        )

    packages = {
        str(event.get("package", "")).strip()
        for event in events
        if str(event.get("package", "")).strip()
    }
    if packages and packages != {EXPECTED_PACKAGE}:
        raise GateError(f"unexpected package identity in event stream: {sorted(packages)}")

    return {"run_id": next(iter(run_ids)), "firmware_values": sorted(firmware_values)}


def verify_firmware_attestation(path: Path, expected_firmware: str) -> dict[str, str]:
    kv = read_kv(path)
    required = {
        "TEST20_R3_2_1_SCHEMA": EXPECTED_FW_SCHEMA,
        "FIRMWARE_LABEL": expected_firmware,
        "OPERATOR_VISIBLE_FIRMWARE": expected_firmware,
        "OPERATOR_EXACT_MATCH": "PASS",
        "OCR_USED": "NO",
    }
    for key, expected in required.items():
        actual = kv.get(key)
        if actual != expected:
            raise GateError(f"firmware attestation mismatch: {key}={actual!r}, expected {expected!r}")
    digest = kv.get("SCREENSHOT_SHA256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise GateError("firmware screenshot SHA-256 is missing or malformed")
    size = intish(kv.get("SCREENSHOT_BYTES", ""))
    if size is None or size <= 0:
        raise GateError("firmware screenshot size is missing or invalid")
    return kv


def verify_gate_locked(events: list[dict[str, Any]]) -> dict[str, Any]:
    initialized = details(require_event(events, GATE_INIT_EVENT))
    if str(initialized.get("phase", "")).strip() != "PREREQUISITE_LOCKED":
        raise GateError("operator gate did not initialize in PREREQUISITE_LOCKED phase")
    if boolish(initialized.get("photo_control_enabled")) is not False:
        raise GateError("operator gate initialization did not prove photo_control_enabled=false")
    if boolish(initialized.get("host_arm_granted")) is not False:
        raise GateError("operator gate initialization did not prove host_arm_granted=false")
    if boolish(initialized.get("arm_token_present")) is not True:
        raise GateError("operator gate initialization did not prove arm_token_present=true")
    if boolish(initialized.get("arm_token_value_logged")) is not False:
        raise GateError("operator gate initialization did not prove arm_token_value_logged=false")

    ready = details(require_event(events, GATE_READY_EVENT))
    if boolish(ready.get("photo_control_enabled")) is not False:
        raise GateError("prerequisite-ready gate did not keep the photo control disabled")
    if boolish(ready.get("host_arm_granted")) is not False:
        raise GateError("prerequisite-ready gate unexpectedly reported host arm granted")
    if boolish(ready.get("photo_request_issued")) is not False:
        raise GateError("prerequisite-ready gate reported a photo request before host arm")
    return {
        "phase": "PREREQUISITE_LOCKED",
        "photo_control_enabled": False,
        "host_arm_granted": False,
        "arm_token_present": True,
        "arm_token_value_logged": False,
    }


def verify_gate_armed(events: list[dict[str, Any]]) -> dict[str, Any]:
    verify_gate_locked(events)
    host = details(require_event(events, GATE_HOST_COMMAND_EVENT))
    if str(host.get("action", "")).strip() != "ARM_ONE_PHOTO":
        raise GateError("host gate command action was not ARM_ONE_PHOTO")
    if boolish(host.get("run_id_match")) is not True:
        raise GateError("host gate command did not prove run_id_match=true")
    if boolish(host.get("token_present")) is not True:
        raise GateError("host gate command did not prove token_present=true")
    if boolish(host.get("token_match")) is not True:
        raise GateError("host gate command did not prove token_match=true")
    if boolish(host.get("token_value_logged")) is not False:
        raise GateError("host gate command did not prove token_value_logged=false")
    if boolish(host.get("granted")) is not True:
        raise GateError("host gate command was not granted")
    if boolish(host.get("photo_control_enabled_after_command")) is not True:
        raise GateError("host gate command did not enable the photo control")

    armed = details(require_event(events, GATE_ARM_EVENT))
    if boolish(armed.get("granted")) is not True:
        raise GateError("controller arm result was not granted")
    if boolish(armed.get("photo_ready")) is not True:
        raise GateError("controller arm result did not prove photo_ready=true")
    if boolish(armed.get("photo_request_issued")) is not False:
        raise GateError("controller arm result reported a photo request before the operator tap")
    if boolish(armed.get("host_arm_available")) is not True:
        raise GateError("controller arm result did not prove a one-shot host arm was available")

    operator_gate = verify_gate_locked(events)

    pre_photo = photo_request_signals(events)
    if pre_photo["resolved_count"] != 0:
        raise GateError(
            "photo request was already issued before the armed-phase gate "
            f"(resolved_count={pre_photo['resolved_count']})"
        )
    return {
        "phase": "HOST_ARMED_ONE_SHOT",
        "run_id_match": True,
        "token_match": True,
        "photo_control_enabled": True,
        "photo_requests_before_operator_tap": 0,
    }


def verify_prerequisite(events: list[dict[str, Any]]) -> dict[str, Any]:
    auth = details(require_event(events, AUTH_EVENT))
    if auth.get("token_present") is not True:
        raise GateError("authorization_result did not prove token_present=true")
    if auth.get("token_value_logged") is not False:
        raise GateError("authorization_result did not prove token_value_logged=false")

    session = details(require_event(events, SESSION_EVENT))
    require_true_if_present(session, ("configured", "success", "returned"), label=SESSION_EVENT)
    session_type = str(session.get("session_type", session.get("type", ""))).upper()
    if session_type and "CUSTOM" not in session_type:
        raise GateError(f"unexpected CXR-L session type: {session_type}")

    registration = details(require_event(events, REG_EVENT))
    if boolish(registration.get("registration_returned")) is not True:
        raise GateError("image_callback_registration_result did not prove registration_returned=true")
    if str(registration.get("method", "")).strip() != "setCXRImageCbk(IImageStreamCbk)V":
        raise GateError("image callback registration method was not the expected setCXRImageCbk(IImageStreamCbk)V")
    if boolish(registration.get("audio_callback_registered")) is not False:
        raise GateError("image callback registration did not prove audio_callback_registered=false")
    if boolish(registration.get("media_request_issued")) is not False:
        raise GateError("image callback registration did not prove media_request_issued=false before arm")

    cxrl = details(require_event(events, CXRL_CONNECTED_EVENT))
    if cxrl:
        values = [boolish(v) for k, v in cxrl.items() if "connect" in k.lower() or k.lower() in {"value", "status"}]
        if values and True not in values:
            raise GateError("CXR-L connected callback did not report a connected/success state")

    glass = details(require_event(events, BT_CONNECTED_EVENT))
    if glass:
        values = [boolish(v) for k, v in glass.items() if "connect" in k.lower() or "status" in k.lower() or k.lower() == "value"]
        if values and True not in values:
            raise GateError("glasses Bluetooth callback did not report a connected state")

    service = details(require_event(events, SERVICE_EVENT))
    require_true_if_present(
        service,
        ("status_success", "success", "returned"),
        label=SERVICE_EVENT,
    )
    if "glass_bt_status" in service and boolish(service["glass_bt_status"]) is not True:
        raise GateError("service_status_result glass_bt_status was not true")

    operator_gate = verify_gate_locked(events)

    pre_photo = photo_request_signals(events)
    if pre_photo["resolved_count"] != 0:
        raise GateError(
            "photo request was already issued before the prerequisite gate "
            f"(resolved_count={pre_photo['resolved_count']})"
        )
    return {
        "authorization": "PASS",
        "session": "PASS",
        "callback_registration": "PASS",
        "cxrl_connected": "PASS",
        "glass_bt_connected": "PASS",
        "service_status": "PASS",
        "operator_gate": operator_gate,
        "photo_requests_before_arm": 0,
    }


def collect_counter_values(events: list[dict[str, Any]], keys: set[str]) -> list[int]:
    values: list[int] = []
    for event in events:
        sources = [event, details(event)]
        for source in sources:
            for key, raw in source.items():
                if str(key) not in keys:
                    continue
                value = intish(raw)
                if value is not None:
                    values.append(value)
    return values


def photo_request_signals(events: list[dict[str, Any]]) -> dict[str, Any]:
    direct = sum(1 for event in events if event_type(event) in PHOTO_REQUEST_EVENTS)
    result_events = sum(1 for event in events if event_type(event) in PHOTO_RESULT_EVENTS)
    counters = collect_counter_values(events, PHOTO_COUNT_KEYS)
    for event in events:
        if event_type(event) not in PHOTO_RESULT_EVENTS:
            continue
        value = intish(details(event).get("request_count"))
        if value is not None:
            counters.append(value)
    if any(value < 0 for value in counters):
        raise GateError("negative photo request counter observed")

    # A single request may produce both an invocation event and a result event.
    # Result events are therefore only a fallback machine signal when no explicit
    # invocation event/counter is available; they are never added to invocation
    # events as if they were another request.
    if direct or counters:
        resolved = max([direct, *counters], default=0)
    else:
        resolved = result_events
    return {
        "direct_event_count": direct,
        "result_event_count": result_events,
        "reported_counts": counters,
        "resolved_count": resolved,
        "machine_signal_present": bool(direct or result_events or counters),
    }


def callback_signals(events: list[dict[str, Any]]) -> dict[str, Any]:
    image_direct = sum(1 for event in events if event_type(event) in IMAGE_CALLBACK_EVENTS)
    error_direct = sum(1 for event in events if event_type(event) in IMAGE_ERROR_EVENTS)
    image_counters = collect_counter_values(events, IMAGE_CALLBACK_COUNT_KEYS)
    error_counters = collect_counter_values(events, IMAGE_ERROR_COUNT_KEYS)
    image_count = max([image_direct, *image_counters], default=0)
    error_count = max([error_direct, *error_counters], default=0)
    total = image_count + error_count
    if total > 1:
        raise GateError(
            "more than one terminal image callback/error was observed "
            f"(image={image_count}, error={error_count})"
        )
    if image_count == 1:
        classification = "ONE_IMAGE_CALLBACK"
    elif error_count == 1:
        classification = "ONE_IMAGE_ERROR_CALLBACK"
    else:
        classification = "NO_IMAGE_CALLBACK"
    return {
        "image_callback_count": image_count,
        "image_error_callback_count": error_count,
        "terminal_callback_count": total,
        "classification": classification,
    }


def verify_gate_armed_before_final(events: list[dict[str, Any]]) -> dict[str, Any]:
    verify_gate_locked(events)
    host = details(require_event(events, GATE_HOST_COMMAND_EVENT))
    if str(host.get("action", "")).strip() != "ARM_ONE_PHOTO":
        raise GateError("final stream host gate command action was not ARM_ONE_PHOTO")
    for key in ("run_id_match", "token_present", "token_match", "granted", "photo_control_enabled_after_command"):
        if boolish(host.get(key)) is not True:
            raise GateError(f"final stream host gate command did not prove {key}=true")
    if boolish(host.get("token_value_logged")) is not False:
        raise GateError("final stream host gate command did not prove token_value_logged=false")
    armed = details(require_event(events, GATE_ARM_EVENT))
    if boolish(armed.get("granted")) is not True:
        raise GateError("final stream controller arm result was not granted")
    dispatch = details(require_event(events, GATE_CAPTURE_EVENT))
    if boolish(dispatch.get("controller_request_accepted")) is not True:
        raise GateError("final stream did not prove the armed capture dispatch was accepted")
    if boolish(dispatch.get("photo_control_enabled_after_click")) is not False:
        raise GateError("final stream did not prove the photo control disabled after the one tap")
    return {
        "phase": "HOST_ARMED_ONE_SHOT",
        "run_id_match": True,
        "token_match": True,
        "capture_dispatch": "ACCEPTED_ONCE",
        "photo_control_disabled_after_click": True,
    }


def verify_no_audio(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_hits = [event_type(event) for event in events if AUDIO_EVENTS_RE.search(event_type(event))]
    counters = collect_counter_values(events, AUDIO_COUNT_KEYS)
    nonzero = [value for value in counters if value != 0]
    if event_hits or nonzero:
        raise GateError(f"audio operation evidence was observed: events={event_hits}, counters={counters}")
    return {"audio_event_hits": 0, "reported_audio_counts": counters, "audio_operation": "NONE"}


def verify_operator_attestation(path: Path) -> dict[str, str]:
    kv = read_kv(path)
    required = {
        "TEST20_R3_2_1_SCHEMA": EXPECTED_OPERATOR_SCHEMA,
        "PREREQUISITE_GATE": "PASS",
        "FIRMWARE_EXACT_MATCH": "PASS",
        "HOST_ARM_GATE": "PASS",
        "APK_ARMED_UI_CONFIRMED": "PASS",
        "PHOTO_ARM_GRANTED": "YES",
        "ADDITIONAL_MEDIA_ACTION": "NO",
        "HI_ROKID_RECOVERY": "PASS",
    }
    for key, expected in required.items():
        actual = kv.get(key)
        if actual != expected:
            raise GateError(f"operator gate mismatch: {key}={actual!r}, expected {expected!r}")
    return kv


def privacy_gate_text(text: str) -> list[str]:
    problems: list[str] = []
    if MAC_RE.search(text):
        problems.append("Bluetooth/MAC-like identifier")
    if LOCAL_PATH_RE.search(text):
        problems.append("local home-directory path")
    if TOKEN_VALUE_RE.search(text):
        problems.append("token/auth value")
    return problems


def write_summary(
    destination: Path,
    *,
    mode: str,
    expected_firmware: str,
    identity: dict[str, Any],
    prerequisite: dict[str, Any],
    firmware: dict[str, str],
    photo: dict[str, Any] | None = None,
    callbacks: dict[str, Any] | None = None,
    audio: dict[str, Any] | None = None,
) -> None:
    summary: dict[str, Any] = {
        "schema": "rokid.test20-r3.2.1.sanitized-summary.v1",
        "mode": mode,
        "firmware": expected_firmware,
        "firmware_attestation": {
            "operator_exact_match": True,
            "ocr_used": False,
            "screenshot_sha256": firmware["SCREENSHOT_SHA256"],
            "screenshot_bytes": int(firmware["SCREENSHOT_BYTES"]),
        },
        "control_path_prerequisite": prerequisite,
        "run_id_sha256": hashlib.sha256(identity["run_id"].encode("utf-8")).hexdigest(),
        "package": EXPECTED_PACKAGE,
        "base_app_version": EXPECTED_VERSION,
    }
    if mode == "armed":
        summary["operator_gate"] = prerequisite.get("operator_gate", {})
        summary["TEST20_R3_2_1_3_ARMED_GATE"] = "PASS"
    elif mode == "final":
        summary.update(
            {
                "photo_request": photo,
                "callback_result": callbacks,
                "audio": audio,
                "operator_gate": {
                    "additional_media_action": "NO",
                    "hi_rokid_recovery": "PASS",
                    "host_arm_gate": "PASS",
                    "apk_armed_ui_confirmed": "PASS",
                    "bounded_test_target_derived": "PASS",
                    "decision_source": "MACHINE_EVIDENCE_PLUS_TWO_PHASE_HOST_APK_GATE_PLUS_CONCRETE_OPERATOR_ATTESTATION",
                },
                "TEST20_R3_2_1_3_RESULT": "PASS",
                "TEST20_R3_2_1_RESULT": "PASS",
            }
        )
    else:
        summary["TEST20_R3_2_1_PREREQUISITE_GATE"] = "PASS"

    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    problems = privacy_gate_text(text)
    if problems:
        raise GateError("sanitized-summary privacy gate failed: " + ", ".join(problems))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Test 20 r3.2.1 repaired one-shot photo evidence.")
    parser.add_argument("--mode", choices=("prerequisite", "armed", "final"), required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--firmware", required=True)
    parser.add_argument("--firmware-attestation", required=True)
    parser.add_argument("--operator-attestation")
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    events_path = Path(args.events)
    firmware_path = Path(args.firmware_attestation)
    summary_path = Path(args.summary)

    try:
        events = load_events(events_path)
        identity = verify_event_identity(events, args.firmware)
        firmware = verify_firmware_attestation(firmware_path, args.firmware)
        prerequisite = verify_prerequisite(events) if args.mode == "prerequisite" else None

        if args.mode == "prerequisite":
            assert prerequisite is not None
            write_summary(
                summary_path,
                mode="prerequisite",
                expected_firmware=args.firmware,
                identity=identity,
                prerequisite=prerequisite,
                firmware=firmware,
            )
            print("TEST20_R3_2_1_PREREQUISITE_GATE=PASS")
            print(f"SANITIZED_SUMMARY={summary_path}")
            return 0

        if args.mode == "armed":
            prerequisite_armed = verify_prerequisite(events)
            gate = verify_gate_armed(events)
            prerequisite_armed["operator_gate"] = gate
            write_summary(
                summary_path,
                mode="armed",
                expected_firmware=args.firmware,
                identity=identity,
                prerequisite=prerequisite_armed,
                firmware=firmware,
            )
            print("TEST20_R3_2_1_3_ARMED_GATE=PASS")
            print("PHOTO_REQUESTS_BEFORE_OPERATOR_TAP=0")
            print(f"SANITIZED_SUMMARY={summary_path}")
            return 0

        # Final mode validates the prerequisite events existed, but does not require
        # photo count == 0 because the stream now includes the armed request.
        auth = details(require_event(events, AUTH_EVENT))
        if auth.get("token_present") is not True or auth.get("token_value_logged") is not False:
            raise GateError("authorization prerequisite was not preserved in final stream")
        require_event(events, SESSION_EVENT)
        require_event(events, REG_EVENT)
        require_event(events, CXRL_CONNECTED_EVENT)
        require_event(events, BT_CONNECTED_EVENT)
        service = details(require_event(events, SERVICE_EVENT))
        if "glass_bt_status" in service and boolish(service["glass_bt_status"]) is not True:
            raise GateError("final stream no longer proves glass Bluetooth status")
        gate_final = verify_gate_armed_before_final(events)
        prerequisite_final = {
            "authorization": "PASS",
            "session": "PASS",
            "callback_registration": "PASS",
            "cxrl_connected": "PASS",
            "glass_bt_connected": "PASS",
            "service_status": "PASS",
            "operator_gate": gate_final,
            "pre_photo_gate_was_separately_enforced": "PASS",
        }

        if not args.operator_attestation:
            raise GateError("--operator-attestation is required in final mode")
        verify_operator_attestation(Path(args.operator_attestation))

        photo = photo_request_signals(events)
        if not photo["machine_signal_present"]:
            raise GateError("machine photo-request count is unresolved; refusing operator-only qualification")
        if photo["resolved_count"] != 1:
            raise GateError(f"expected exactly one photo request, observed {photo['resolved_count']}")
        if any(value > 1 for value in photo["reported_counts"]):
            raise GateError(f"reported photo counter exceeded one: {photo['reported_counts']}")

        callbacks = callback_signals(events)
        audio = verify_no_audio(events)

        write_summary(
            summary_path,
            mode="final",
            expected_firmware=args.firmware,
            identity=identity,
            prerequisite=prerequisite_final,
            firmware=firmware,
            photo=photo,
            callbacks=callbacks,
            audio=audio,
        )
        print("TEST20_R3_2_1_PHOTO_REQUEST_BOUNDING=PASS")
        print(f"TEST20_R3_2_1_CALLBACK_CLASS={callbacks['classification']}")
        print("TEST20_R3_2_1_OPERATOR_GATE=PASS")
        print("TEST20_R3_2_1_3_TWO_PHASE_ARMING=PASS")
        print("TEST20_R3_2_1_3_RESULT=PASS")
        print("TEST20_R3_2_1_RESULT=PASS")
        print(f"SANITIZED_SUMMARY={summary_path}")
        return 0
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if args.mode == "prerequisite":
            print("TEST20_R3_2_1_PREREQUISITE_GATE=FAIL", file=sys.stderr)
        elif args.mode == "armed":
            print("TEST20_R3_2_1_3_ARMED_GATE=FAIL", file=sys.stderr)
        else:
            print("TEST20_R3_2_1_3_RESULT=FAIL", file=sys.stderr)
            print("TEST20_R3_2_1_RESULT=FAIL", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
