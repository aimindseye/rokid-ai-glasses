#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_HI = "com.rokid.sprite.global.aiapp"
EXPECTED_CUSTOM = "org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_VERSION = "1.0-test20-final"

PHOTO_EVENT_RE = re.compile(r"(?i)(?:take[_ -]?photo|photo_request|operator_gate_capture_dispatch)")
AUDIO_EVENT_RE = re.compile(r"(?i)(?:audio.*(?:start|stop|stream)|(?:start|stop).*audio)")

class GateError(RuntimeError):
    pass

def read_kv(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise GateError(f"required phase file missing: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out

def yes(value: str) -> bool:
    return str(value).strip().upper() == "YES"

def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise GateError(f"event stream missing or empty: {path}")
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as e:
            raise GateError(f"invalid JSONL at line {lineno}: {e}") from e
        if not isinstance(item, dict):
            raise GateError(f"event line {lineno} is not an object")
        out.append(item)
    if not out:
        raise GateError("event stream contains no JSON objects")
    return out

def event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type", "")).strip()

def details(event: dict[str, Any]) -> dict[str, Any]:
    d = event.get("details", {})
    return d if isinstance(d, dict) else {}

def find(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [e for e in events if event_type(e) == name]

def last(events: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = find(events, name)
    return matches[-1] if matches else None

def boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes"}

def event_identity(events: list[dict[str, Any]]) -> tuple[str, str]:
    run_ids = {str(e.get("run_id", "")).strip() for e in events if str(e.get("run_id", "")).strip()}
    packages = {str(e.get("package", "")).strip() for e in events if str(e.get("package", "")).strip()}
    if len(run_ids) != 1:
        raise GateError(f"expected one run_id, found {sorted(run_ids)}")
    if packages and packages != {EXPECTED_CUSTOM}:
        raise GateError(f"unexpected event package(s): {sorted(packages)}")
    return next(iter(run_ids)), EXPECTED_CUSTOM

def media_gate(events: list[dict[str, Any]]) -> dict[str, Any]:
    photo_hits = []
    audio_hits = []
    arm_granted = False
    for e in events:
        et = event_type(e)
        d = details(e)
        if PHOTO_EVENT_RE.search(et):
            # photo_ready is deliberately not a media operation.
            if et not in {"photo_ready"}:
                photo_hits.append(et)
        if AUDIO_EVENT_RE.search(et):
            audio_hits.append(et)
        if et in {"operator_gate_host_command", "operator_gate_arm_result"} and boolish(d.get("granted")):
            arm_granted = True
        for k in ("photo_request_count", "take_photo_request_count", "photo_requests"):
            try:
                if int(d.get(k, 0)) > 0:
                    photo_hits.append(f"{et}:{k}={d.get(k)}")
            except (TypeError, ValueError):
                pass
    if photo_hits:
        raise GateError(f"photo operation/request evidence observed: {photo_hits}")
    if audio_hits:
        raise GateError(f"audio operation evidence observed: {audio_hits}")
    if arm_granted:
        raise GateError("host photo arm was granted during Test21 r2")
    return {"photo_operation": "NONE", "audio_operation": "NONE", "host_photo_arm": "NONE"}

def verify_preforce(events: list[dict[str, Any]]) -> dict[str, Any]:
    run_id, _ = event_identity(events)
    media_gate(events)

    auth = last(events, "authorization_result")
    if auth is None:
        raise GateError("authorization_result not observed before force-stop")
    ad = details(auth)
    if not boolish(ad.get("token_present")):
        raise GateError("authorization token was not present before force-stop")
    if boolish(ad.get("token_value_logged")):
        raise GateError("authorization token value was reported logged")

    if find(events, "connection_attempt_started"):
        raise GateError("connection attempt started before Hi Rokid force-stop")
    if find(events, "callback_cxrl_connected"):
        raise GateError("CXR-L callback observed before force-stop")
    if find(events, "photo_ready"):
        raise GateError("photo-ready state observed before force-stop")

    started = last(events, "run_started")
    if started:
        sd = details(started)
        version = str(sd.get("app_version", "")).strip()
        if version and version != EXPECTED_VERSION:
            raise GateError(f"unexpected custom companion version: {version}")

    return {
        "run_id": run_id,
        "authorization_token_present": True,
        "authorization_token_value_logged": False,
        "connection_started_before_force_stop": False,
        "photo_operation": "NONE",
        "audio_operation": "NONE",
    }

def connection_signals(events: list[dict[str, Any]]) -> dict[str, Any]:
    started = bool(find(events, "connection_attempt_started"))
    cxr = last(events, "callback_cxrl_connected")
    glass = last(events, "callback_glass_bt_connected")
    service = last(events, "service_status_result")
    ready = last(events, "operator_gate_prerequisite_ready")
    photo_ready = last(events, "photo_ready")
    terminal = last(events, "qualification_terminal")

    cxr_connected = bool(cxr and boolish(details(cxr).get("connected")))
    glass_connected = bool(glass and boolish(details(glass).get("connected")))
    service_success = bool(service and boolish(details(service).get("status_success")))
    gate_ready = bool(ready)
    photo_ready_seen = bool(photo_ready)

    connected = started and cxr_connected and glass_connected and service_success and gate_ready and photo_ready_seen

    terminal_outcome = ""
    if terminal:
        terminal_outcome = str(details(terminal).get("outcome", "") or details(terminal).get("terminal_outcome", "")).strip()

    return {
        "connection_attempt_started": started,
        "cxrl_connected": cxr_connected,
        "glass_bt_connected": glass_connected,
        "service_status_success": service_success,
        "photo_ready_machine_state": photo_ready_seen,
        "operator_gate_prerequisite_ready": gate_ready,
        "session_connected": connected,
        "terminal_outcome": terminal_outcome,
    }

def classify(pre: dict[str,str], stopped: dict[str,str], settled: dict[str,str],
             post: dict[str,str], restored: dict[str,str], observation: dict[str,str],
             events: list[dict[str,Any]]) -> tuple[str, dict[str,Any]]:
    media = media_gate(events)
    signals = connection_signals(events)

    pre_hi = yes(pre.get("HI_PROCESS_VISIBLE", "NO"))
    stopped_hi = yes(stopped.get("HI_PROCESS_VISIBLE", "NO"))
    settled_hi = yes(settled.get("HI_PROCESS_VISIBLE", "NO"))
    post_hi = yes(post.get("HI_PROCESS_VISIBLE", "NO"))
    custom_alive_stopped = yes(settled.get("CUSTOM_PROCESS_VISIBLE", "NO"))
    restored_hi = yes(restored.get("HI_PROCESS_VISIBLE", "NO"))
    restoration_operator = restored.get("OPERATOR_HI_ROKID_RECOVERY", "") == "PASS"

    absent_observed = yes(observation.get("HI_PROCESS_ABSENT_OBSERVED", "NO"))
    if not pre_hi:
        raise GateError("Hi Rokid was not running in the normal pre-force-stop baseline")
    if not absent_observed:
        disposition = "FORCE_STOP_ABSENCE_NOT_OBSERVED"
    elif not custom_alive_stopped:
        disposition = "CUSTOM_APP_DIED_DURING_FORCE_STOP"
    elif settled_hi:
        disposition = "AUTO_RESPAWN_BEFORE_CUSTOM_CONNECT"
    else:
        if signals["session_connected"]:
            disposition = ("CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED"
                           if post_hi else "CUSTOM_SESSION_CONNECTED_HI_ROKID_REMAINED_STOPPED")
        else:
            disposition = ("CUSTOM_SESSION_FAILED_HI_ROKID_RESPAWNED"
                           if post_hi else "CUSTOM_SESSION_FAILED_HI_ROKID_REMAINED_STOPPED")

    restoration_ok = restored_hi and restoration_operator
    result = {
        "disposition": disposition,
        "pre_force_hi_process_visible": pre_hi,
        "immediate_post_force_hi_process_visible": stopped_hi,
        "force_stop_process_absence_observed": absent_observed,
        "settled_pre_connect_hi_process_visible": settled_hi,
        "post_connect_hi_process_visible": post_hi,
        "custom_process_survived_force_stop": custom_alive_stopped,
        "restored_hi_process_visible": restored_hi,
        "operator_restoration_confirmed": restoration_operator,
        "restoration_ok": restoration_ok,
        "connection": signals,
        "media": media,
    }
    return disposition, result

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--mode", choices=["preforce","final"], default="final")
    args = ap.parse_args()
    root = Path(args.evidence).expanduser().resolve()
    raw = root / "raw"
    sanitized = root / "sanitized"
    sanitized.mkdir(parents=True, exist_ok=True)

    try:
        if args.mode == "preforce":
            events = load_events(raw / "pre-force-events-private.jsonl")
            result = verify_preforce(events)
            print("TEST21_R2_PREFORCE_GATE=PASS")
            print(f"RUN_ID={result['run_id']}")
            print("AUTHORIZATION_TOKEN_PRESENT=YES")
            print("AUTHORIZATION_TOKEN_VALUE_EXPORTED=NO")
            print("CONNECTION_ATTEMPT_BEFORE_FORCE_STOP=NO")
            print("PHOTO_OPERATION=NONE")
            print("AUDIO_OPERATION=NONE")
            return 0

        pre = read_kv(raw / "state-pre-force.txt")
        immediate = read_kv(raw / "state-post-force-immediate.txt")
        settled = read_kv(raw / "state-post-force-settled.txt")
        post = read_kv(raw / "state-post-connect.txt")
        restored = read_kv(raw / "state-restored.txt")
        observation = read_kv(raw / "force-stop-observation.txt")
        pre_events = load_events(raw / "pre-force-events-private.jsonl")
        events = load_events(raw / "final-events-private.jsonl")

        verify_preforce(pre_events)
        media_gate(events)
        event_identity(events)
        disposition, classification = classify(pre, immediate, settled, post, restored, observation, events)

        summary = {
            "schema": "rokid.test21-r2.hi-rokid-force-stop-ownership.v1",
            "scope": "controlled_force_stop_session_ownership",
            "hi_rokid_package": EXPECTED_HI,
            "custom_companion_package": EXPECTED_CUSTOM,
            "custom_companion_version": EXPECTED_VERSION,
            "authorization_token_handling": {
                "obtained_before_force_stop": True,
                "retained_in_existing_app_memory_only": True,
                "host_exported": False,
                "persisted_by_test21": False,
            },
            "mutation": {
                "hi_rokid_force_stop": "ONE_CONTROLLED_ATTEMPT",
                "package_disable": "NONE",
                "package_uninstall": "NONE",
                "package_data_clear": "NONE",
                "firmware_operation": "NONE",
            },
            "media": classification["media"],
            "runtime": classification,
            "next_action": {
                "CUSTOM_SESSION_CONNECTED_HI_ROKID_REMAINED_STOPPED":
                    "R3_COLD_START_OR_REBOOT_STANDALONE_BOOTSTRAP_CANDIDATE",
                "CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED":
                    "R3_BOUND_SERVICE_RESPAWN_DEPENDENCY_CHARACTERIZATION",
                "CUSTOM_SESSION_FAILED_HI_ROKID_REMAINED_STOPPED":
                    "R3_HI_ROKID_RUNTIME_REQUIREMENT_CHARACTERIZATION",
                "CUSTOM_SESSION_FAILED_HI_ROKID_RESPAWNED":
                    "R3_SERVICE_RESPAWN_BUT_SESSION_FAILURE_CHARACTERIZATION",
                "AUTO_RESPAWN_BEFORE_CUSTOM_CONNECT":
                    "R3_HI_ROKID_AUTO_RESPAWN_TRIGGER_CHARACTERIZATION",
                "CUSTOM_APP_DIED_DURING_FORCE_STOP":
                    "R3_CUSTOM_APP_PROCESS_COUPLING_CHARACTERIZATION",
                "FORCE_STOP_ABSENCE_NOT_OBSERVED":
                    "R2_1_FORCE_STOP_OBSERVABILITY_REPAIR",
            }[disposition],
        }

        if not classification["restoration_ok"]:
            raise GateError("Hi Rokid restoration gate did not pass; preserve evidence and restore before further testing")

        json_path = sanitized / "test21-r2-summary.json"
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        txt_lines = [
            "TEST21_R2_ANALYSIS=PASS",
            f"SESSION_OWNERSHIP_DISPOSITION={disposition}",
            f"HI_ROKID_PROCESS_PRE_FORCE={'YES' if classification['pre_force_hi_process_visible'] else 'NO'}",
            f"HI_ROKID_PROCESS_IMMEDIATE_POST_FORCE={'YES' if classification['immediate_post_force_hi_process_visible'] else 'NO'}",
            f"HI_ROKID_PROCESS_ABSENCE_OBSERVED={'YES' if classification['force_stop_process_absence_observed'] else 'NO'}",
            f"HI_ROKID_PROCESS_SETTLED_PRE_CONNECT={'YES' if classification['settled_pre_connect_hi_process_visible'] else 'NO'}",
            f"CUSTOM_PROCESS_SURVIVED_FORCE_STOP={'YES' if classification['custom_process_survived_force_stop'] else 'NO'}",
            f"CXR_L_CONNECTION_ATTEMPT_STARTED={'YES' if classification['connection']['connection_attempt_started'] else 'NO'}",
            f"CXR_L_CONNECTED={'YES' if classification['connection']['cxrl_connected'] else 'NO'}",
            f"GLASS_BT_CONNECTED={'YES' if classification['connection']['glass_bt_connected'] else 'NO'}",
            f"SERVICE_STATUS_SUCCESS={'YES' if classification['connection']['service_status_success'] else 'NO'}",
            f"PHOTO_READY_MACHINE_STATE={'YES' if classification['connection']['photo_ready_machine_state'] else 'NO'}",
            f"HI_ROKID_PROCESS_POST_CONNECT={'YES' if classification['post_connect_hi_process_visible'] else 'NO'}",
            "PHOTO_OPERATION=NONE",
            "AUDIO_OPERATION=NONE",
            "AUTHORIZATION_TOKEN_HOST_EXPORT=NONE",
            "PACKAGE_DISABLE_OR_UNINSTALL=NONE",
            "PACKAGE_DATA_CLEAR=NONE",
            f"HI_ROKID_RESTORATION={'PASS' if classification['restoration_ok'] else 'FAIL'}",
            f"NEXT_ACTION={summary['next_action']}",
        ]
        txt_path = sanitized / "test21-r2-summary.txt"
        txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
        sums = [f"{sha256(p)}  {p.name}" for p in (json_path, txt_path)]
        (sanitized/"SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")

        for line in txt_lines:
            print(line)
        print(f"SANITIZED_SUMMARY={json_path}")
        return 0
    except GateError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if args.mode == "final":
            print("TEST21_R2_ANALYSIS=FAIL")
        else:
            print("TEST21_R2_PREFORCE_GATE=FAIL")
        return 1

if __name__ == "__main__":
    sys.exit(main())
