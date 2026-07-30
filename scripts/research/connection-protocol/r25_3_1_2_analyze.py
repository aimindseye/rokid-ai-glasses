#!/usr/bin/env python3
"""Offline r25.3.1.2 target-pair-scoped RFCOMM qualification and existing-capture salvage analyzer.

This analyzer never contacts a device. It consumes one capture directory produced
by r25_3_1_1_capture.py, reuses the accepted r25.2.3.2 btsnoop parser, attributes
non-control RFCOMM UIH bytes to repeated stock enable/disable windows, and emits
private raw analysis plus publication-safe hashes/lengths only.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r25_2_3_2_capture as base  # type: ignore

UTC = dt.timezone.utc
RELEASE = "r1.3.3.2.25.3.1.2"
SCHEMA = "rokid.r25.3.1.2.target-pair-scoped-rfcomm-salvage.v1"
TARGET_DLCI = 6


class AnalysisFailure(RuntimeError):
    pass


def iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclasses.dataclass(frozen=True)
class Window:
    window_id: str
    kind: str
    action: Optional[str]
    cycle: Optional[int]
    start: dt.datetime
    end: dt.datetime
    source: str

    def contains(self, ts: dt.datetime) -> bool:
        return self.start <= ts <= self.end


def load_windows(metadata: Dict[str, Any]) -> Tuple[List[Window], List[Window]]:
    action_windows: List[Window] = []
    baseline_windows: List[Window] = []
    for row in metadata.get("action_windows", []):
        action = str(row.get("action", "")).lower()
        if action not in {"enable", "disable"}:
            raise AnalysisFailure(f"invalid action window: {row!r}")
        start = parse_iso(row["start_utc"])
        end = parse_iso(row["end_utc"])
        if end <= start:
            raise AnalysisFailure(f"non-positive action window: {row.get('action_id')}")
        action_windows.append(
            Window(
                window_id=str(row["action_id"]),
                kind="action",
                action=action,
                cycle=int(row["cycle"]),
                start=start,
                end=end,
                source=str(row.get("time_source", "phone_epoch")),
            )
        )
    for row in metadata.get("baseline_windows", []):
        start = parse_iso(row["start_utc"])
        end = parse_iso(row["end_utc"])
        if end <= start:
            raise AnalysisFailure(f"non-positive baseline window: {row.get('window_id')}")
        baseline_windows.append(
            Window(
                window_id=str(row["window_id"]),
                kind="baseline",
                action=None,
                cycle=None,
                start=start,
                end=end,
                source=str(row.get("time_source", "phone_epoch")),
            )
        )
    if len(action_windows) < 4:
        raise AnalysisFailure("at least four action windows are required")
    action_windows.sort(key=lambda w: w.start)
    baseline_windows.sort(key=lambda w: w.start)
    for left, right in zip(action_windows, action_windows[1:]):
        if right.start <= left.end:
            raise AnalysisFailure(f"overlapping action windows: {left.window_id}, {right.window_id}")
    return action_windows, baseline_windows


def parse_hci_member(name: str, data: bytes, capture_start: dt.datetime, capture_end: dt.datetime) -> Dict[str, Any]:
    """Parse one rolling HCI member with target-pair-scoped RFCOMM error gating.

    RFCOMM CIDs are discovered from the whole rolling snoop because the channel may
    predate the measured action interval. Dynamic CIDs can later be reused by other
    L2CAP services, so parse errors on a handle/CID pair that never yields target
    DLCI 6 traffic are retained as diagnostics but do not disqualify the target
    channel. Errors on any pair that yields DLCI 6 remain blocking.
    """
    result: Dict[str, Any] = {
        "member": name,
        "member_sha256": sha256_bytes(data),
        "qualifies": False,
        "errors": [],
        "target_pair_scoped_rfcomm_error_qualification": True,
    }
    try:
        datalink, records, parse_errors = base.parse_btsnoop(data)
    except Exception as exc:
        result["errors"] = [f"parse_error:{type(exc).__name__}:{exc}"]
        return result
    window_records = [
        record
        for record in records
        if capture_start - dt.timedelta(seconds=5) <= record.timestamp <= capture_end + dt.timedelta(seconds=5)
    ]
    # RFCOMM may already be established before the measured stock-toggle window.
    # Discover candidate L2CAP CIDs from the complete rolling snoop stream, then
    # parse only PDUs near the bounded capture interval.
    all_pdus, all_reassembly_errors = base.reassemble_l2cap(datalink, records)
    cids = base.discover_rfcomm_cids(all_pdus)
    window_pdus = [
        pdu
        for pdu in all_pdus
        if capture_start - dt.timedelta(seconds=5) <= pdu.timestamp <= capture_end + dt.timedelta(seconds=5)
    ]
    frames = []
    rfcomm_error_rows: List[Dict[str, Any]] = []
    for pdu in window_pdus:
        if pdu.cid not in cids.get(pdu.handle, set()):
            continue
        parsed, errors = base.parse_rfcomm_frames(pdu)
        frames.extend(parsed)
        for error in errors:
            rfcomm_error_rows.append(
                {
                    "source_record_index": pdu.source_record_index,
                    "timestamp_utc": iso(pdu.timestamp),
                    "direction": pdu.direction,
                    "handle": pdu.handle,
                    "cid": pdu.cid,
                    "error": error,
                }
            )
    target_frames = sorted(
        (frame for frame in frames if frame.dlci == TARGET_DLCI),
        key=lambda frame: frame.timestamp,
    )
    target_pairs = sorted({(frame.handle, frame.cid) for frame in target_frames})
    target_pair_set = set(target_pairs)
    target_rfcomm_error_rows = [
        row for row in rfcomm_error_rows if (int(row["handle"]), int(row["cid"])) in target_pair_set
    ]
    non_target_rfcomm_error_rows = [
        row for row in rfcomm_error_rows if (int(row["handle"]), int(row["cid"])) not in target_pair_set
    ]
    target_rfcomm_parse_errors = [
        f"pdu_{row['source_record_index']}:handle_{row['handle']}:cid_{row['cid']}:{row['error']}"
        for row in target_rfcomm_error_rows
    ]
    non_target_rfcomm_parse_errors = [
        f"pdu_{row['source_record_index']}:handle_{row['handle']}:cid_{row['cid']}:{row['error']}"
        for row in non_target_rfcomm_error_rows
    ]
    drops = max((record.drops for record in window_records), default=0)
    truncations = sum(1 for record in window_records if record.included_length != record.original_length)
    first_ts = min((record.timestamp for record in window_records), default=None)
    last_ts = max((record.timestamp for record in window_records), default=None)
    coverage = bool(
        first_ts
        and last_ts
        and first_ts <= capture_start + dt.timedelta(seconds=5)
        and last_ts >= capture_end - dt.timedelta(seconds=5)
    )
    # Structural btsnoop errors and RFCOMM errors on target DLCI 6 pairs block
    # qualification. Non-target-pair RFCOMM errors are retained but excluded.
    errors = list(parse_errors) + list(target_rfcomm_parse_errors)
    unique_handles = sorted({frame.handle for frame in target_frames})
    result.update(
        {
            "datalink": datalink,
            "record_count": len(records),
            "window_record_count": len(window_records),
            "first_window_timestamp_utc": iso(first_ts) if first_ts else None,
            "last_window_timestamp_utc": iso(last_ts) if last_ts else None,
            "coverage": coverage,
            "drops": drops,
            "truncated_record_count": truncations,
            "parse_errors": parse_errors,
            "reassembly_errors": all_reassembly_errors,
            "rfcomm_parse_errors": target_rfcomm_parse_errors + non_target_rfcomm_parse_errors,
            "rfcomm_error_rows": rfcomm_error_rows,
            "target_rfcomm_parse_errors": target_rfcomm_parse_errors,
            "target_rfcomm_error_rows": target_rfcomm_error_rows,
            "target_rfcomm_parse_error_count": len(target_rfcomm_parse_errors),
            "non_target_rfcomm_parse_errors": non_target_rfcomm_parse_errors,
            "non_target_rfcomm_error_rows": non_target_rfcomm_error_rows,
            "non_target_rfcomm_parse_error_count": len(non_target_rfcomm_parse_errors),
            "non_target_rfcomm_errors_excluded_from_qualification": True,
            "rfcomm_cids": {str(handle): sorted(values) for handle, values in cids.items()},
            "target_pairs": [
                {"handle": handle, "cid": cid} for handle, cid in target_pairs
            ],
            "target_handle_candidates": unique_handles,
            "target_frame_count": len(target_frames),
            "payload_frame_count": sum(
                1 for frame in target_frames if frame.frame_type == "UIH" and frame.information_length > 0
            ),
            "errors": errors,
            "qualifies": coverage
            and drops == 0
            and truncations == 0
            and not errors
            and len(unique_handles) == 1
            and bool(target_frames),
            "frames": [
                dataclasses.asdict(frame) | {"timestamp": iso(frame.timestamp)} for frame in target_frames
            ],
        }
    )
    fingerprint_rows = [
        [
            iso(frame.timestamp),
            frame.direction,
            frame.handle,
            frame.cid,
            frame.dlci,
            frame.frame_type,
            frame.information_length,
            frame.payload_hex,
        ]
        for frame in target_frames
    ]
    result["frame_fingerprint_sha256"] = sha256_bytes(
        json.dumps(fingerprint_rows, separators=(",", ":")).encode("utf-8")
    )
    return result

def choose_hci_member(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = candidate.get("frame_fingerprint_sha256") or candidate["member_sha256"]
        current = dedup.get(key)
        if current is None or (candidate.get("qualifies") and not current.get("qualifies")):
            dedup[key] = candidate
    qualifying = [candidate for candidate in dedup.values() if candidate.get("qualifies")]
    if len(qualifying) != 1:
        raise AnalysisFailure(f"unique qualifying HCI member required; found {len(qualifying)}")
    return qualifying[0]


def frame_payload(frame: Dict[str, Any]) -> bytes:
    return bytes.fromhex(frame.get("payload_hex", ""))


def payload_frames_for_window(frames: List[Dict[str, Any]], window: Window) -> List[Dict[str, Any]]:
    selected = []
    for frame in frames:
        if frame.get("frame_type") != "UIH" or int(frame.get("information_length", 0)) <= 0:
            continue
        timestamp = parse_iso(frame["timestamp"])
        if window.contains(timestamp):
            selected.append(frame)
    return selected


def group_messages(frames: List[Dict[str, Any]], window: Window, gap_ms: int = 250) -> List[Dict[str, Any]]:
    ordered = sorted(frames, key=lambda frame: parse_iso(frame["timestamp"]))
    groups: List[List[Dict[str, Any]]] = []
    for frame in ordered:
        if not groups:
            groups.append([frame])
            continue
        prev = groups[-1][-1]
        gap = (parse_iso(frame["timestamp"]) - parse_iso(prev["timestamp"])).total_seconds() * 1000
        if frame["direction"] == prev["direction"] and gap <= gap_ms:
            groups[-1].append(frame)
        else:
            groups.append([frame])
    messages = []
    for index, group in enumerate(groups):
        payload = b"".join(frame_payload(frame) for frame in group)
        start = parse_iso(group[0]["timestamp"])
        end = parse_iso(group[-1]["timestamp"])
        messages.append(
            {
                "message_index": index,
                "direction": group[0]["direction"],
                "frame_count": len(group),
                "start_utc": iso(start),
                "end_utc": iso(end),
                "relative_start_ms": round((start - window.start).total_seconds() * 1000, 3),
                "length": len(payload),
                "sha256": sha256_bytes(payload),
                "payload_hex": payload.hex(),
                "frame_lengths": [int(frame["information_length"]) for frame in group],
            }
        )
    return messages


def message_signature(message: Dict[str, Any]) -> Tuple[str, int, str]:
    return message["direction"], int(message["length"]), str(message["sha256"])


def subtract_baseline(action_messages: List[Dict[str, Any]], baseline_counter: Counter) -> List[Dict[str, Any]]:
    remaining = baseline_counter.copy()
    output = []
    for message in action_messages:
        signature = message_signature(message)
        is_baseline = remaining[signature] > 0
        if is_baseline:
            remaining[signature] -= 1
        output.append(message | {"baseline_signature_match": is_baseline})
    return output


def common_prefix(values: Sequence[bytes]) -> bytes:
    if not values:
        return b""
    limit = min(len(value) for value in values)
    index = 0
    while index < limit and len({value[index] for value in values}) == 1:
        index += 1
    return values[0][:index]


def common_suffix(values: Sequence[bytes]) -> bytes:
    if not values:
        return b""
    reversed_prefix = common_prefix([value[::-1] for value in values])
    return reversed_prefix[::-1]


def stable_mask(values: Sequence[bytes]) -> List[bool]:
    if not values or len({len(value) for value in values}) != 1:
        return []
    return [len({value[index] for value in values}) == 1 for index in range(len(values[0]))]


def length_prefix_candidates(payloads: Sequence[bytes]) -> List[Dict[str, Any]]:
    candidates = []
    if not payloads:
        return candidates
    for width in (1, 2, 4):
        for endian in ("big", "little"):
            for relation in ("total", "remaining"):
                if any(len(payload) < width for payload in payloads):
                    continue
                good = True
                values = []
                for payload in payloads:
                    value = int.from_bytes(payload[:width], endian)
                    expected = len(payload) if relation == "total" else len(payload) - width
                    values.append(value)
                    if value != expected:
                        good = False
                        break
                if good:
                    candidates.append(
                        {
                            "width_bytes": width,
                            "endianness": endian,
                            "relation": relation,
                            "observed_values": values,
                        }
                    )
    return candidates


def compare_action_groups(observations: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    enable = observations.get("enable", [])
    disable = observations.get("disable", [])
    result: Dict[str, Any] = {
        "enable_observation_count": len(enable),
        "disable_observation_count": len(disable),
        "paired_message_comparisons": [],
        "sequence_shape_consistent": False,
        "differential_proven": False,
        "framing_candidate_status": "UNRESOLVED",
    }
    if len(enable) < 2 or len(disable) < 2:
        return result
    shapes = {
        action: [
            [(message["direction"], message["length"]) for message in observation["action_specific_messages"]]
            for observation in rows
        ]
        for action, rows in observations.items()
    }
    enable_consistent = len({json.dumps(shape) for shape in shapes["enable"]}) == 1
    disable_consistent = len({json.dumps(shape) for shape in shapes["disable"]}) == 1
    result["enable_sequence_shape_consistent"] = enable_consistent
    result["disable_sequence_shape_consistent"] = disable_consistent
    if not enable_consistent or not disable_consistent:
        return result
    enable_shape = shapes["enable"][0]
    disable_shape = shapes["disable"][0]
    result["sequence_shape_consistent"] = True
    result["enable_sequence_shape"] = enable_shape
    result["disable_sequence_shape"] = disable_shape
    if enable_shape != disable_shape:
        result["differential_proven"] = True
        result["framing_candidate_status"] = "SEQUENCE_SHAPE_DIFFERENTIAL"
        return result
    comparisons = []
    differential_positions_total = 0
    framing_candidates = []
    for index, (direction, length) in enumerate(enable_shape):
        enable_payloads = [
            bytes.fromhex(observation["action_specific_messages"][index]["payload_hex"]) for observation in enable
        ]
        disable_payloads = [
            bytes.fromhex(observation["action_specific_messages"][index]["payload_hex"]) for observation in disable
        ]
        all_payloads = enable_payloads + disable_payloads
        enable_stable = stable_mask(enable_payloads)
        disable_stable = stable_mask(disable_payloads)
        differential_positions = [
            position
            for position in range(length)
            if enable_stable[position]
            and disable_stable[position]
            and enable_payloads[0][position] != disable_payloads[0][position]
        ]
        differential_positions_total += len(differential_positions)
        comparison = {
            "message_index": index,
            "direction": direction,
            "length": length,
            "common_prefix_hex": common_prefix(all_payloads).hex(),
            "common_suffix_hex": common_suffix(all_payloads).hex(),
            "enable_stable_positions": [i for i, value in enumerate(enable_stable) if value],
            "disable_stable_positions": [i for i, value in enumerate(disable_stable) if value],
            "enable_disable_differential_positions": differential_positions,
            "enable_representative_hex": enable_payloads[0].hex(),
            "disable_representative_hex": disable_payloads[0].hex(),
            "length_prefix_candidates": length_prefix_candidates(all_payloads),
        }
        comparisons.append(comparison)
        framing_candidates.extend(comparison["length_prefix_candidates"])
    result["paired_message_comparisons"] = comparisons
    result["differential_position_count"] = differential_positions_total
    result["differential_proven"] = differential_positions_total > 0
    if result["differential_proven"]:
        result["framing_candidate_status"] = (
            "BOUNDED_LENGTH_PREFIX_AND_MESSAGE_BOUNDARY_CANDIDATE"
            if framing_candidates
            else "BOUNDED_MESSAGE_BOUNDARY_CANDIDATE"
        )
    return result


def sanitize_message(message: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in message.items() if key != "payload_hex"}


def sanitize_comparison(comparison: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in comparison.items()
        if key not in {"enable_representative_hex", "disable_representative_hex", "common_prefix_hex", "common_suffix_hex"}
    }


def build_markdown(public: Dict[str, Any]) -> str:
    gates = public["gates"]
    differential = public["differential"]
    return f"""# {RELEASE} — target-pair-scoped RFCOMM qualification and existing-capture salvage

## Result

- Stock enable observations: **{differential['enable_observation_count']}**
- Stock disable observations: **{differential['disable_observation_count']}**
- Disable semantic oracle: **{'PASS' if gates['disable_semantic_oracle_proven'] else 'FAIL'}**
- Enable semantic oracle: **{'PASS' if gates['enable_semantic_oracle_proven'] else 'FAIL'}**
- ADB transport disappearance required: **NO**
- Control channel usable for all actions: **{'PASS' if gates['control_channel_usable_for_all_actions'] else 'FAIL'}**
- Target-pair-scoped HCI UIH payload attribution: **{'PASS' if gates['hci_uih_payload_attributed'] else 'FAIL'}**
- Enable/disable differential: **{'PROVEN' if gates['enable_disable_differential_proven'] else 'NOT PROVEN'}**
- Application framing: **{differential['framing_candidate_status']}**
- Custom RFCOMM transmission attempted: **NO**

## Boundary

This release observes the stock Hi Rokid workflow only. Enable and disable are
classified by `persist.vendor.adb` plus the stock UI switch. Host ADB transport
disappearance is not an acceptance condition. RFCOMM parse errors on non-target dynamic CIDs are retained as diagnostics and excluded from target-channel qualification. Raw UIH bytes remain private. Public artifacts contain directions, lengths, counts, hashes, and
bounded differential positions. No captured payload is replayed, generated, or
sent by the research client.

## Acceptance

`{public['acceptance']}`
"""


def analyze(capture_dir: Path, output_dir: Path) -> Dict[str, Any]:
    metadata_path = capture_dir / "metadata.json"
    if not metadata_path.is_file():
        raise AnalysisFailure(f"missing metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema") != "rokid.r25.3.1.1.capture-metadata.v1":
        raise AnalysisFailure(f"unexpected metadata schema: {metadata.get('schema')}")
    if metadata.get("custom_transmission_attempted") is not False:
        raise AnalysisFailure("capture metadata does not prove custom_transmission_attempted=false")
    action_windows, baseline_windows = load_windows(metadata)
    counts = Counter(window.action for window in action_windows)
    if counts["enable"] < 2 or counts["disable"] < 2:
        raise AnalysisFailure(f"two enable and two disable observations required: {dict(counts)}")
    capture_start = parse_iso(metadata["capture_start_utc"])
    capture_end = parse_iso(metadata["capture_end_utc"])
    hci_members = [
        parse_hci_member(name, data, capture_start, capture_end)
        for name, data in base.iter_bugreport_btsnoop(capture_dir)
    ]
    selected = choose_hci_member(hci_members)
    frames = selected["frames"]
    baseline_messages = []
    for window in baseline_windows:
        baseline_messages.extend(group_messages(payload_frames_for_window(frames, window), window))
    baseline_counter = Counter(message_signature(message) for message in baseline_messages)
    observations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    action_metadata = {str(row.get("action_id")): row for row in metadata.get("action_windows", [])}
    action_rows = []
    for window in action_windows:
        messages = group_messages(payload_frames_for_window(frames, window), window)
        annotated = subtract_baseline(messages, baseline_counter)
        action_specific = [message for message in annotated if not message["baseline_signature_match"]]
        semantic = action_metadata.get(window.window_id, {})
        row = {
            "action_id": window.window_id,
            "action": window.action,
            "cycle": window.cycle,
            "start_utc": iso(window.start),
            "end_utc": iso(window.end),
            "semantic_oracle_passed": semantic.get("semantic_oracle_passed") is True,
            "persist_vendor_adb_state": semantic.get("persist_vendor_adb_state"),
            "ui_switch_state": semantic.get("ui_switch_state"),
            "control_channel_usable": semantic.get("control_channel_usable") is True,
            "host_glasses_transport_present": semantic.get("host_glasses_transport_present") is True,
            "adb_transport_disappearance_required": False,
            "all_messages": annotated,
            "action_specific_messages": action_specific,
            "payload_frame_count": sum(message["frame_count"] for message in annotated),
            "payload_byte_count": sum(message["length"] for message in annotated),
            "action_specific_message_count": len(action_specific),
        }
        action_rows.append(row)
        observations[window.action].append(row)
    missing = [row["action_id"] for row in action_rows if row["action_specific_message_count"] == 0]
    differential = compare_action_groups(observations)
    enable_semantic = [
        row for row in action_rows
        if row["action"] == "enable"
    ]
    disable_semantic = [
        row for row in action_rows
        if row["action"] == "disable"
    ]
    semantic_oracle = metadata.get("semantic_oracle", {})
    gates = {
        "capture_semantic_transitions_complete": all(row["semantic_oracle_passed"] for row in action_rows),
        "enable_semantic_oracle_proven": bool(enable_semantic) and all(
            row["persist_vendor_adb_state"] == "on"
            and row["ui_switch_state"] == "on"
            and row["control_channel_usable"]
            for row in enable_semantic
        ),
        "disable_semantic_oracle_proven": bool(disable_semantic) and all(
            row["persist_vendor_adb_state"] == "off"
            and row["ui_switch_state"] == "off"
            and row["control_channel_usable"]
            for row in disable_semantic
        ),
        "adb_transport_disappearance_not_required": semantic_oracle.get(
            "adb_transport_disappearance_required"
        ) is False,
        "control_channel_usable_for_all_actions": all(row["control_channel_usable"] for row in action_rows),
        "source_capture_release_is_r25_3_1_1": metadata.get("release") == "r1.3.3.2.25.3.1.1",
        "target_pair_scoped_rfcomm_error_qualification": selected.get(
            "target_pair_scoped_rfcomm_error_qualification"
        ) is True,
        "target_rfcomm_parse_errors_absent": int(
            selected.get("target_rfcomm_parse_error_count", 0)
        ) == 0,
        "non_target_rfcomm_errors_retained": "non_target_rfcomm_parse_errors" in selected,
        "hci_member_unique_and_lossless": bool(selected.get("qualifies")),
        "hci_uih_payload_attributed": not missing,
        "repeated_enable_disable_observations": counts["enable"] >= 2 and counts["disable"] >= 2,
        "enable_disable_differential_proven": bool(differential.get("differential_proven")),
        "custom_transmission_attempted": False,
        "final_semantic_state_restored": metadata.get("initial_semantic_state")
        == metadata.get("final_semantic_state")
        and metadata.get("final_semantic_probe", {}).get("control_channel_usable") is True,
    }
    pass_capture = all(
        [
            gates["capture_semantic_transitions_complete"],
            gates["enable_semantic_oracle_proven"],
            gates["disable_semantic_oracle_proven"],
            gates["adb_transport_disappearance_not_required"],
            gates["control_channel_usable_for_all_actions"],
            gates["source_capture_release_is_r25_3_1_1"],
            gates["target_pair_scoped_rfcomm_error_qualification"],
            gates["target_rfcomm_parse_errors_absent"],
            gates["non_target_rfcomm_errors_retained"],
            gates["hci_member_unique_and_lossless"],
            gates["hci_uih_payload_attributed"],
            gates["repeated_enable_disable_observations"],
            gates["enable_disable_differential_proven"],
            gates["final_semantic_state_restored"],
        ]
    )
    acceptance = (
        "PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE"
        if pass_capture
        else "FAIL_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_OR_DIFFERENTIAL_CLOSURE"
    )
    qualification = (
        "EXISTING_R25_3_1_1_CAPTURE_SALVAGED_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_PROVEN"
        if pass_capture
        else "EXISTING_R25_3_1_1_CAPTURE_SALVAGE_OR_DIFFERENTIAL_NOT_PROVEN"
    )
    private = {
        "schema": SCHEMA,
        "release": RELEASE,
        "source_capture_metadata_sha256": sha256_file(metadata_path),
        "metadata": metadata,
        "hci_member_census": hci_members,
        "selected_hci_member": selected,
        "baseline_messages": baseline_messages,
        "action_observations": action_rows,
        "differential": differential,
        "gates": gates,
        "qualification_outcome": qualification,
        "acceptance": acceptance,
    }
    public_differential = {
        key: value for key, value in differential.items() if key != "paired_message_comparisons"
    }
    public_differential["paired_message_comparisons"] = [
        sanitize_comparison(row) for row in differential.get("paired_message_comparisons", [])
    ]
    public = {
        "schema": "rokid.r25.3.1.2.public-status.v1",
        "release": RELEASE,
        "capture": {
            "cycle_count": metadata.get("cycle_count"),
            "initial_semantic_state": metadata.get("initial_semantic_state"),
            "final_semantic_state": metadata.get("final_semantic_state"),
            "adb_transport_disappearance_required": False,
            "control_channel_usable_required": True,
            "action_count": len(action_rows),
            "custom_transmission_attempted": False,
        },
        "selected_hci_member": {
            key: value
            for key, value in selected.items()
            if key not in {
                "frames",
                "member",
                "rfcomm_error_rows",
                "target_rfcomm_error_rows",
                "non_target_rfcomm_error_rows",
                "rfcomm_parse_errors",
                "target_rfcomm_parse_errors",
                "non_target_rfcomm_parse_errors",
            }
        },
        "action_observations": [
            {
                **{key: value for key, value in row.items() if key not in {"all_messages", "action_specific_messages"}},
                "all_messages": [sanitize_message(message) for message in row["all_messages"]],
                "action_specific_messages": [
                    sanitize_message(message) for message in row["action_specific_messages"]
                ],
            }
            for row in action_rows
        ],
        "differential": public_differential,
        "gates": gates,
        "qualification_outcome": qualification,
        "acceptance": acceptance,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    private_dir = output_dir / "analysis"
    public_dir = output_dir / "publication"
    private_dir.mkdir()
    public_dir.mkdir()
    (private_dir / "r25.3.1.2-private-analysis.json").write_text(
        json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (public_dir / "r25.3.1.2-runtime-status-summary.json").write_text(
        json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (public_dir / "r25.3.1.2-target-pair-scoped-rfcomm-qualification-and-offline-salvage.md").write_text(
        build_markdown(public), encoding="utf-8"
    )
    (public_dir / "methodology.md").write_text(
        "# Methodology\n\nThis release reanalyzes an existing r25.3.1.1 capture without contacting a device. It reuses the accepted r25.2.3.2 btsnoop ACL/L2CAP/RFCOMM parser, discovers candidate RFCOMM CIDs from the rolling snoop, scopes blocking RFCOMM parse errors to handle/CID pairs that actually yield DLCI 6 frames, retains non-target-pair errors as private diagnostics, attributes non-control DLCI 6 UIH bytes to non-overlapping action windows, subtracts exact idle-baseline signatures, and compares repeated enable and disable observations. Raw payload bytes remain private.\n",
        encoding="utf-8",
    )
    (public_dir / "limitations.md").write_text(
        "# Limitations\n\nDynamic CID reuse is inferred from target-pair locality and does not identify the non-target L2CAP service. A differential byte position is a bounded command-field candidate, not semantic proof. One phone, one glasses unit, one firmware/app build, and one paired account are in scope. Encryption, checksums, sequence fields, authorization, and reply semantics remain unresolved until independent captures and code correlation explain them. No captured payload is replayed.\n",
        encoding="utf-8",
    )
    print(f"R25_3_1_2_HCI_MEMBER_COUNT={len(hci_members)}")
    print(f"R25_3_1_2_TARGET_PAIR_COUNT={len(selected.get('target_pairs', []))}")
    print(
        "R25_3_1_2_TARGET_RFCOMM_PARSE_ERROR_COUNT="
        + str(selected.get("target_rfcomm_parse_error_count", 0))
    )
    print(
        "R25_3_1_2_NON_TARGET_RFCOMM_PARSE_ERROR_COUNT="
        + str(selected.get("non_target_rfcomm_parse_error_count", 0))
    )
    print("R25_3_1_2_NON_TARGET_RFCOMM_ERRORS_EXCLUDED_FROM_QUALIFICATION=YES")
    print("R25_3_1_2_HCI_UIH_ATTRIBUTION=" + ("PASS" if gates["hci_uih_payload_attributed"] else "FAIL"))
    print(f"R25_3_1_2_ENABLE_OBSERVATION_COUNT={counts['enable']}")
    print(f"R25_3_1_2_DISABLE_OBSERVATION_COUNT={counts['disable']}")
    print("R25_3_1_2_ENABLE_DISABLE_DIFFERENTIAL=" + ("PASS" if gates["enable_disable_differential_proven"] else "FAIL"))
    print(f"R25_3_1_2_APPLICATION_FRAMING_STATUS={differential['framing_candidate_status']}")
    print("R25_3_1_2_CUSTOM_TRANSMISSION_ATTEMPTED=NO")
    print(f"R25_3_1_2_QUALIFICATION_OUTCOME={qualification}")
    print(f"R1_3_3_2_25_3_1_2_ACCEPTANCE={acceptance}")
    return private


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise AnalysisFailure(f"output already exists: {args.output_dir}")
    analyze(args.capture_dir.resolve(), args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AnalysisFailure as exc:
        print(f"R25_3_1_2_ANALYSIS_FAILURE={exc}", file=sys.stderr)
        raise SystemExit(1)
