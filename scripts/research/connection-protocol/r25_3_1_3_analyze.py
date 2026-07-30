#!/usr/bin/env python3
"""Host-only exact application-frame grammar recovery for r25.3.1.3.

Consumes the accepted r25.3.1.2 private-analysis ZIP. It never contacts a
phone or glasses, never transmits or replays a captured payload, and emits a
private exact grammar analysis plus a separately sanitized publication set.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

RELEASE = "r1.3.3.2.25.3.1.3"
SCHEMA = "rokid.r25.3.1.3.exact-application-frame-grammar.v1"
PUBLIC_SCHEMA = "rokid.r25.3.1.3.public-status.v1"
SOURCE_SCHEMA = "rokid.r25.3.1.2.target-pair-scoped-rfcomm-salvage.v1"
SOURCE_RELEASE = "r1.3.3.2.25.3.1.2"
SOURCE_ACCEPTANCE = (
    "PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_"
    "UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE"
)
ACCEPTANCE = (
    "PASS_EXISTING_CAPTURE_EXACT_ADB_TOGGLE_APPLICATION_FRAME_GRAMMAR_"
    "NESTED_LENGTH_SEQUENCE_DISCRIMINATOR_AND_STRUCTURED_PAYLOAD_ROLE_CLOSURE"
)
EXPECTED_SOURCE_ZIP_SHA256 = (
    "14601a69b0893b4af5d9c0e7d7ae25d8c11e9f01a204352bf7c661c67d04d6de"
)


class AnalysisFailure(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_zip(source: Path, destination: Path) -> list[str]:
    names: list[str] = []
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            name = info.filename
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise AnalysisFailure(f"unsafe ZIP path: {name!r}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise AnalysisFailure(f"symlink ZIP member rejected: {name}")
            names.append(name)
        archive.extractall(destination)
    return names


def verify_manifest(root: Path, manifest_name: str) -> None:
    manifest = root / manifest_name
    if not manifest.is_file():
        raise AnalysisFailure(f"missing source manifest: {manifest_name}")
    rows = 0
    for line_number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw)
        if not match:
            raise AnalysisFailure(f"invalid manifest row {line_number}")
        expected, relative = match.groups()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise AnalysisFailure(f"unsafe manifest path: {relative}")
        path = root.joinpath(*pure.parts)
        if not path.is_file() or path.is_symlink():
            raise AnalysisFailure(f"manifest member missing or non-regular: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise AnalysisFailure(f"manifest hash mismatch: {relative}")
        rows += 1
    if rows == 0:
        raise AnalysisFailure("empty source manifest")


@dataclasses.dataclass(frozen=True)
class FieldSpan:
    name: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start": self.start,
            "end_exclusive": self.end,
            "length": self.length,
        }


@dataclasses.dataclass(frozen=True)
class ParsedMessage:
    payload: bytes
    outer_total_length: int
    outer_marker: int
    outer_magic: str
    envelope_class_hex: str
    sequence_value: int
    subsystem_marker: int
    subsystem: str
    nested_total_length: int
    nested_marker: int
    nested_magic: str
    operation: str
    action_discriminator: str
    structured_payload_text: str
    structured_payload: Any
    spans: tuple[FieldSpan, ...]

    def span(self, name: str) -> FieldSpan:
        for field in self.spans:
            if field.name == name:
                return field
        raise KeyError(name)

    def private_dict(self) -> dict[str, Any]:
        return {
            "payload_length": len(self.payload),
            "payload_sha256": sha256_bytes(self.payload),
            "payload_hex": self.payload.hex(),
            "outer_total_length": self.outer_total_length,
            "outer_total_length_self_inclusive": self.outer_total_length == len(self.payload),
            "outer_marker": self.outer_marker,
            "outer_magic": self.outer_magic,
            "envelope_class_hex": self.envelope_class_hex,
            "sequence_value": self.sequence_value,
            "subsystem_marker": self.subsystem_marker,
            "subsystem": self.subsystem,
            "nested_total_length": self.nested_total_length,
            "nested_total_length_self_inclusive": (
                self.nested_total_length
                == len(self.payload) - self.span("nested_total_length").start
            ),
            "nested_marker": self.nested_marker,
            "nested_magic": self.nested_magic,
            "operation": self.operation,
            "action_discriminator": self.action_discriminator,
            "structured_payload_text": self.structured_payload_text,
            "structured_payload": self.structured_payload,
            "field_spans": [field.as_dict() for field in self.spans],
        }


class Cursor:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.spans: list[FieldSpan] = []

    def take(self, length: int, name: str) -> bytes:
        if length < 0 or self.offset + length > len(self.data):
            raise AnalysisFailure(f"truncated field {name} at offset {self.offset}")
        start = self.offset
        self.offset += length
        self.spans.append(FieldSpan(name, start, self.offset))
        return self.data[start:self.offset]

    def u8(self, name: str) -> int:
        return self.take(1, name)[0]

    def u32be(self, name: str) -> int:
        return struct.unpack(">I", self.take(4, name))[0]

    def ascii(self, length: int, name: str) -> str:
        data = self.take(length, name)
        try:
            return data.decode("ascii")
        except UnicodeDecodeError as exc:
            raise AnalysisFailure(f"non-ASCII field {name}") from exc


def parse_target_message(payload: bytes) -> ParsedMessage:
    cursor = Cursor(payload)
    outer_total = cursor.u32be("outer_total_length")
    if outer_total != len(payload):
        raise AnalysisFailure(
            f"outer total length mismatch: declared {outer_total}, actual {len(payload)}"
        )
    outer_marker = cursor.u8("outer_marker")
    outer_magic_length = cursor.u8("outer_magic_length")
    outer_magic = cursor.ascii(outer_magic_length, "outer_magic")
    envelope_class = cursor.take(2, "envelope_class")
    sequence = cursor.u8("sequence_candidate")
    subsystem_marker = cursor.u8("subsystem_marker")
    subsystem_length = cursor.u8("subsystem_length")
    subsystem = cursor.ascii(subsystem_length, "subsystem")

    nested_start = cursor.offset
    nested_total = cursor.u32be("nested_total_length")
    if nested_total != len(payload) - nested_start:
        raise AnalysisFailure(
            "nested total length mismatch: "
            f"declared {nested_total}, actual {len(payload) - nested_start}"
        )
    nested_marker = cursor.u8("nested_marker")
    nested_magic_length = cursor.u8("nested_magic_length")
    nested_magic = cursor.ascii(nested_magic_length, "nested_magic")
    operation_length = cursor.u8("operation_length")
    operation = cursor.ascii(operation_length, "operation")
    discriminator = cursor.ascii(1, "action_discriminator")
    structured_start = cursor.offset
    structured_bytes = cursor.take(len(payload) - cursor.offset, "structured_payload")
    try:
        structured_text = structured_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AnalysisFailure("structured payload is not UTF-8") from exc
    try:
        structured = json.loads(structured_text)
    except json.JSONDecodeError as exc:
        raise AnalysisFailure("structured payload is not valid JSON") from exc
    if cursor.offset != len(payload):
        raise AnalysisFailure("unconsumed payload bytes")
    if structured_start >= len(payload):
        raise AnalysisFailure("empty structured payload")
    return ParsedMessage(
        payload=payload,
        outer_total_length=outer_total,
        outer_marker=outer_marker,
        outer_magic=outer_magic,
        envelope_class_hex=envelope_class.hex(),
        sequence_value=sequence,
        subsystem_marker=subsystem_marker,
        subsystem=subsystem,
        nested_total_length=nested_total,
        nested_marker=nested_marker,
        nested_magic=nested_magic,
        operation=operation,
        action_discriminator=discriminator,
        structured_payload_text=structured_text,
        structured_payload=structured,
        spans=tuple(cursor.spans),
    )


def extract_single_role(parsed: ParsedMessage) -> tuple[str, str]:
    value = parsed.structured_payload
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise AnalysisFailure("structured payload must be a one-record JSON array")
    record = value[0]
    if set(record) != {"key", "value"}:
        raise AnalysisFailure("structured record must contain exactly key and value")
    key = record["key"]
    role_value = record["value"]
    if not isinstance(key, str) or not key:
        raise AnalysisFailure("structured key must be a non-empty string")
    if not isinstance(role_value, str) or not role_value:
        raise AnalysisFailure("structured value must be a non-empty string")
    return key, role_value


def one_message_per_action(source: dict[str, Any]) -> list[dict[str, Any]]:
    observations = source.get("action_observations")
    if not isinstance(observations, list) or len(observations) != 4:
        raise AnalysisFailure("exactly four source action observations required")
    rows: list[dict[str, Any]] = []
    for observation in observations:
        action = observation.get("action")
        if action not in {"enable", "disable"}:
            raise AnalysisFailure("invalid source action")
        if observation.get("semantic_oracle_passed") is not True:
            raise AnalysisFailure(f"semantic oracle not passed: {observation.get('action_id')}")
        if observation.get("control_channel_usable") is not True:
            raise AnalysisFailure(f"control channel unusable: {observation.get('action_id')}")
        messages = observation.get("action_specific_messages")
        if not isinstance(messages, list) or len(messages) != 1:
            raise AnalysisFailure(
                f"one action-specific message required: {observation.get('action_id')}"
            )
        message = messages[0]
        payload_hex = message.get("payload_hex")
        if not isinstance(payload_hex, str) or not re.fullmatch(r"[0-9a-f]+", payload_hex):
            raise AnalysisFailure("private source payload hex missing or invalid")
        if len(payload_hex) % 2:
            raise AnalysisFailure("odd-length payload hex")
        payload = bytes.fromhex(payload_hex)
        if sha256_bytes(payload) != message.get("sha256"):
            raise AnalysisFailure("source message payload/hash mismatch")
        rows.append(
            {
                "action_id": observation.get("action_id"),
                "action": action,
                "cycle": observation.get("cycle"),
                "ui_switch_state": observation.get("ui_switch_state"),
                "persist_vendor_adb_state": observation.get("persist_vendor_adb_state"),
                "payload": payload,
                "source_message_sha256": message.get("sha256"),
            }
        )
    if [row["action"] for row in rows] != ["disable", "enable", "disable", "enable"]:
        raise AnalysisFailure("expected disable/enable/disable/enable action order")
    return rows


def normalized_without_sequence(parsed: ParsedMessage) -> bytes:
    span = parsed.span("sequence_candidate")
    result = bytearray(parsed.payload)
    result[span.start:span.end] = b"\x00" * span.length
    return bytes(result)


def byte_differences(left: bytes, right: bytes) -> list[dict[str, Any]]:
    common = min(len(left), len(right))
    rows: list[dict[str, Any]] = []
    for offset in range(common):
        if left[offset] != right[offset]:
            rows.append({"offset": offset, "left": left[offset], "right": right[offset]})
    if len(left) != len(right):
        rows.append(
            {
                "offset": common,
                "left_tail_length": len(left) - common,
                "right_tail_length": len(right) - common,
            }
        )
    return rows


def public_identifier(value: str) -> dict[str, Any]:
    encoded = value.encode("utf-8")
    return {"utf8_length": len(encoded), "sha256": sha256_bytes(encoded)}


def analyze_source(source: dict[str, Any], source_zip_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if source.get("schema") != SOURCE_SCHEMA:
        raise AnalysisFailure("unexpected source private-analysis schema")
    if source.get("release") != SOURCE_RELEASE:
        raise AnalysisFailure("unexpected source release")
    if source.get("acceptance") != SOURCE_ACCEPTANCE:
        raise AnalysisFailure("source acceptance gate not passed")
    source_gates = source.get("gates", {})
    for required in (
        "capture_semantic_transitions_complete",
        "control_channel_usable_for_all_actions",
        "final_semantic_state_restored",
        "hci_member_unique_and_lossless",
        "hci_uih_payload_attributed",
        "target_pair_scoped_rfcomm_error_qualification",
        "target_rfcomm_parse_errors_absent",
    ):
        if source_gates.get(required) is not True:
            raise AnalysisFailure(f"source gate not proven: {required}")
    if source_gates.get("custom_transmission_attempted") is not False:
        raise AnalysisFailure("source custom-transmission boundary not proven")

    rows = one_message_per_action(source)
    parsed_rows: list[dict[str, Any]] = []
    for row in rows:
        parsed = parse_target_message(row["payload"])
        key, value = extract_single_role(parsed)
        parsed_rows.append({**row, "parsed": parsed, "structured_key": key, "structured_value": value})

    # Constants across all four target messages.
    constants = {
        "outer_marker": {row["parsed"].outer_marker for row in parsed_rows},
        "outer_magic": {row["parsed"].outer_magic for row in parsed_rows},
        "envelope_class_hex": {row["parsed"].envelope_class_hex for row in parsed_rows},
        "subsystem_marker": {row["parsed"].subsystem_marker for row in parsed_rows},
        "subsystem": {row["parsed"].subsystem for row in parsed_rows},
        "nested_marker": {row["parsed"].nested_marker for row in parsed_rows},
        "nested_magic": {row["parsed"].nested_magic for row in parsed_rows},
        "operation": {row["parsed"].operation for row in parsed_rows},
        "structured_key": {row["structured_key"] for row in parsed_rows},
    }
    non_constant = [name for name, values in constants.items() if len(values) != 1]
    if non_constant:
        raise AnalysisFailure(f"target grammar constants vary: {', '.join(non_constant)}")

    # Field spans must be structurally identical through the action discriminator.
    structural_names = [field.name for field in parsed_rows[0]["parsed"].spans]
    for row in parsed_rows[1:]:
        if [field.name for field in row["parsed"].spans] != structural_names:
            raise AnalysisFailure("field ordering differs across observations")
        for name in structural_names[:-1]:
            first = parsed_rows[0]["parsed"].span(name)
            current = row["parsed"].span(name)
            if (first.start, first.end) != (current.start, current.end):
                raise AnalysisFailure(f"field span differs before structured payload: {name}")

    sequence_values = [row["parsed"].sequence_value for row in parsed_rows]
    sequence_steps = [
        (right - left) % 256 for left, right in zip(sequence_values, sequence_values[1:])
    ]
    sequence_monotonic_step_one = sequence_steps == [1, 1, 1]
    if not sequence_monotonic_step_one:
        raise AnalysisFailure(f"sequence candidate is not monotonic +1: {sequence_values}")

    disable_rows = [row for row in parsed_rows if row["action"] == "disable"]
    enable_rows = [row for row in parsed_rows if row["action"] == "enable"]
    if len(disable_rows) != 2 or len(enable_rows) != 2:
        raise AnalysisFailure("two repeated observations per action required")
    disable_repeat_equal = (
        normalized_without_sequence(disable_rows[0]["parsed"])
        == normalized_without_sequence(disable_rows[1]["parsed"])
    )
    enable_repeat_equal = (
        normalized_without_sequence(enable_rows[0]["parsed"])
        == normalized_without_sequence(enable_rows[1]["parsed"])
    )
    if not disable_repeat_equal or not enable_repeat_equal:
        raise AnalysisFailure("repeated action frames differ beyond sequence candidate")

    # Derive, rather than hard-code, discriminator and structured-value roles.
    action_roles: dict[str, dict[str, Any]] = {}
    for action, group in (("disable", disable_rows), ("enable", enable_rows)):
        discriminators = {row["parsed"].action_discriminator for row in group}
        values = {row["structured_value"] for row in group}
        ui_states = {row["ui_switch_state"] for row in group}
        property_states = {row["persist_vendor_adb_state"] for row in group}
        if len(discriminators) != 1 or len(values) != 1:
            raise AnalysisFailure(f"{action} role values are not repeat-stable")
        expected_state = "off" if action == "disable" else "on"
        if values != {expected_state} or ui_states != {expected_state} or property_states != {expected_state}:
            raise AnalysisFailure(f"{action} structured/UI/property role correlation failed")
        action_roles[action] = {
            "discriminator": next(iter(discriminators)),
            "structured_value": next(iter(values)),
            "ui_switch_state": next(iter(ui_states)),
            "persist_vendor_adb_state": next(iter(property_states)),
            "observation_count": len(group),
        }
    if action_roles["disable"]["discriminator"] == action_roles["enable"]["discriminator"]:
        raise AnalysisFailure("enable/disable action discriminator is not distinct")

    first_disable = disable_rows[0]["parsed"]
    first_enable = enable_rows[0]["parsed"]
    cross_action_differences = byte_differences(first_disable.payload, first_enable.payload)

    private_observations = []
    for row in parsed_rows:
        private_observations.append(
            {
                "action_id": row["action_id"],
                "action": row["action"],
                "cycle": row["cycle"],
                "ui_switch_state": row["ui_switch_state"],
                "persist_vendor_adb_state": row["persist_vendor_adb_state"],
                "parsed_message": row["parsed"].private_dict(),
                "structured_key": row["structured_key"],
                "structured_value": row["structured_value"],
            }
        )

    exact_constants = {name: next(iter(values)) for name, values in constants.items()}
    grammar = {
        "outer_total_length_encoding": "u32be_self_inclusive",
        "nested_total_length_encoding": "u32be_self_inclusive_from_nested_length_field",
        "outer_marker": exact_constants["outer_marker"],
        "outer_magic": exact_constants["outer_magic"],
        "envelope_class_hex": exact_constants["envelope_class_hex"],
        "sequence_candidate": {
            "offset": parsed_rows[0]["parsed"].span("sequence_candidate").start,
            "width_bytes": 1,
            "values": sequence_values,
            "steps_mod_256": sequence_steps,
            "monotonic_step_one": sequence_monotonic_step_one,
            "role": "transaction_or_sequence_candidate",
        },
        "subsystem_marker": exact_constants["subsystem_marker"],
        "subsystem": exact_constants["subsystem"],
        "nested_marker": exact_constants["nested_marker"],
        "nested_magic": exact_constants["nested_magic"],
        "operation": exact_constants["operation"],
        "structured_key": exact_constants["structured_key"],
        "action_roles": action_roles,
        "field_spans_disable": [field.as_dict() for field in first_disable.spans],
        "field_spans_enable": [field.as_dict() for field in first_enable.spans],
        "disable_repeat_normalized_equal": disable_repeat_equal,
        "enable_repeat_normalized_equal": enable_repeat_equal,
        "cross_action_byte_differences_first_pair": cross_action_differences,
    }

    gates = {
        "source_r25_3_1_2_acceptance_bound": True,
        "four_semantically_qualified_action_messages": True,
        "outer_total_length_closed": True,
        "nested_total_length_closed": True,
        "constant_envelope_and_operation_grammar": True,
        "monotonic_sequence_candidate_step_one": True,
        "disable_repeat_equal_after_sequence_normalization": disable_repeat_equal,
        "enable_repeat_equal_after_sequence_normalization": enable_repeat_equal,
        "distinct_enable_disable_discriminator": True,
        "structured_payload_json_decoded": True,
        "structured_role_correlated_to_ui_and_property": True,
        "custom_transmission_attempted": False,
        "captured_payload_replay_attempted": False,
        "device_contact": False,
    }
    if not all(value is True for key, value in gates.items() if key not in {
        "custom_transmission_attempted", "captured_payload_replay_attempted", "device_contact"
    }):
        raise AnalysisFailure("one or more exact grammar gates failed")

    private = {
        "schema": SCHEMA,
        "release": RELEASE,
        "source_private_zip_sha256": source_zip_sha256,
        "source_release": SOURCE_RELEASE,
        "source_acceptance": SOURCE_ACCEPTANCE,
        "acceptance": ACCEPTANCE,
        "qualification_outcome": (
            "EXACT_SELF_INCLUSIVE_OUTER_AND_NESTED_LENGTHS_CONSTANT_ENVELOPE_"
            "MONOTONIC_SEQUENCE_DISTINCT_ACTION_DISCRIMINATOR_AND_STRUCTURED_ROLE_PROVEN"
        ),
        "gates": gates,
        "grammar": grammar,
        "observations": private_observations,
        "boundaries": {
            "device_contact": False,
            "stock_toggle_attempted": False,
            "custom_transmission_attempted": False,
            "captured_payload_replay_attempted": False,
            "raw_payload_publication": False,
        },
    }

    public_grammar = {
        "outer_total_length_encoding": grammar["outer_total_length_encoding"],
        "nested_total_length_encoding": grammar["nested_total_length_encoding"],
        "field_order": structural_names,
        "sequence_candidate": {
            "offset": grammar["sequence_candidate"]["offset"],
            "width_bytes": 1,
            "observation_count": len(sequence_values),
            "steps_mod_256": sequence_steps,
            "monotonic_step_one": True,
            "role": "transaction_or_sequence_candidate_not_yet_code_correlated",
        },
        "constant_identifiers": {
            "outer_magic": public_identifier(exact_constants["outer_magic"]),
            "subsystem": public_identifier(exact_constants["subsystem"]),
            "nested_magic": public_identifier(exact_constants["nested_magic"]),
            "operation": public_identifier(exact_constants["operation"]),
            "structured_key": public_identifier(exact_constants["structured_key"]),
        },
        "action_roles": {
            action: {
                "discriminator": role["discriminator"],
                "structured_value": role["structured_value"],
                "ui_switch_state": role["ui_switch_state"],
                "persist_vendor_adb_state": role["persist_vendor_adb_state"],
                "observation_count": role["observation_count"],
            }
            for action, role in action_roles.items()
        },
        "repeat_normalization": {
            "disable_equal_except_sequence_candidate": disable_repeat_equal,
            "enable_equal_except_sequence_candidate": enable_repeat_equal,
        },
        "message_lengths": {
            "disable": sorted({len(row["parsed"].payload) for row in disable_rows}),
            "enable": sorted({len(row["parsed"].payload) for row in enable_rows}),
        },
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "release": RELEASE,
        "source_private_zip_sha256": source_zip_sha256,
        "source_release": SOURCE_RELEASE,
        "acceptance": ACCEPTANCE,
        "qualification_outcome": private["qualification_outcome"],
        "gates": gates,
        "grammar": public_grammar,
        "privacy": {
            "raw_payload_hex_present": False,
            "exact_application_identifiers_present": False,
            "device_serial_present": False,
            "bluetooth_address_present": False,
            "private_home_path_present": False,
        },
        "boundaries": private["boundaries"],
    }
    return private, public


def findings_markdown(public: dict[str, Any]) -> str:
    grammar = public["grammar"]
    roles = grammar["action_roles"]
    return f"""# {RELEASE} — exact ADB-toggle application-frame grammar and field-role closure

## Result

- Source: accepted r25.3.1.2 private analysis
- Qualified stock actions: **4** (two enable, two disable)
- Outer total length: **32-bit big-endian, self-inclusive**
- Nested total length: **32-bit big-endian, self-inclusive from its own field**
- Sequence/transaction candidate: **one byte, monotonic +1 across all actions**
- Repeated disable frames: **identical after sequence-field normalization**
- Repeated enable frames: **identical after sequence-field normalization**
- Enable/disable discriminator: **distinct and repeat-stable**
- Structured action value: **correlated with stock UI and `persist.vendor.adb` in all four observations**
- Device contact: **NO**
- Captured payload replay: **NO**

## Bounded grammar

The four action-specific outbound DLCI 6 UIH messages share one constant envelope,
subsystem identifier, operation identifier, structured key, and field ordering.
The public record retains identifier lengths and hashes rather than exact private
application strings or raw payload bytes. Disable observations use discriminator
`{roles['disable']['discriminator']}` with structured state `{roles['disable']['structured_value']}`;
enable observations use discriminator `{roles['enable']['discriminator']}` with
structured state `{roles['enable']['structured_value']}`.

## Boundary

The one-byte monotonic field is proven as a transaction/sequence candidate, not
as a fully code-correlated protocol counter. This release does not infer reply
semantics, authorization, checksum behavior, or generalize beyond this setting,
phone, glasses unit, firmware/app build, and paired account.

## Acceptance

`{ACCEPTANCE}`
"""


def methodology_markdown() -> str:
    return f"""# Methodology

{RELEASE} is host-only. It verifies the exact accepted r25.3.1.2 private-analysis
ZIP hash and internal manifest, reads the four action-specific private payloads,
parses a bounded length-prefixed envelope, verifies self-inclusive outer and
nested lengths, decodes the terminal UTF-8 JSON record, normalizes only the
candidate sequence byte for repeat comparison, and correlates discriminator and
structured state with the already-qualified stock UI and `persist.vendor.adb`
state. Exact identifiers and payload bytes remain private.
"""


def limitations_markdown() -> str:
    return """# Limitations

The grammar is established from four action messages in one controlled capture.
The monotonic byte is a transaction/sequence candidate but has not been tied to
application code or wrap behavior. Constant marker meanings, reply semantics,
transport authorization, error handling, and behavior for other settings remain
unresolved. Public files intentionally omit raw payloads and exact application
identifiers. No captured payload is generated, transmitted, or replayed.
"""


def write_outputs(output_dir: Path, private: dict[str, Any], public: dict[str, Any]) -> None:
    private_dir = output_dir / "analysis"
    publication_dir = output_dir / "publication"
    private_dir.mkdir(parents=True, exist_ok=False)
    publication_dir.mkdir(parents=True, exist_ok=False)
    (private_dir / "r25.3.1.3-private-analysis.json").write_text(
        json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (publication_dir / "r25.3.1.3-runtime-status-summary.json").write_text(
        json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (publication_dir / "r25.3.1.3-exact-frame-grammar-and-field-role-closure.md").write_text(
        findings_markdown(public), encoding="utf-8"
    )
    (publication_dir / "methodology.md").write_text(methodology_markdown(), encoding="utf-8")
    (publication_dir / "limitations.md").write_text(limitations_markdown(), encoding="utf-8")


def privacy_gate(publication_dir: Path, private: dict[str, Any]) -> None:
    exact_values = {
        value
        for value in (
            private["grammar"]["outer_magic"],
            private["grammar"]["subsystem"],
            private["grammar"]["nested_magic"],
            private["grammar"]["operation"],
            private["grammar"]["structured_key"],
        )
        # Short protocol markers can occur incidentally in hashes or status words;
        # the public output still carries only their hash and byte length.
        if len(value.encode("utf-8")) >= 4
    }
    prohibited_patterns = [
        re.compile(r'"payload_hex"\s*:'),
        re.compile(r"/Users/[^/\s]+/"),
        re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"),
    ]
    for path in publication_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in prohibited_patterns:
            if pattern.search(text):
                raise AnalysisFailure(f"public privacy gate failed: {path.name}")
        for value in exact_values:
            if value and value in text:
                raise AnalysisFailure(f"exact private identifier leaked publicly: {path.name}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-private-zip", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--expected-source-sha256",
        default=EXPECTED_SOURCE_ZIP_SHA256,
    )
    args = parser.parse_args(argv)

    source_zip = args.source_private_zip.resolve()
    output_dir = args.output_dir.resolve()
    if not source_zip.is_file() or source_zip.is_symlink():
        raise AnalysisFailure(f"source ZIP missing or non-regular: {source_zip}")
    if output_dir.exists():
        raise AnalysisFailure(f"output already exists: {output_dir}")
    actual_source_sha = sha256_file(source_zip)
    if actual_source_sha != args.expected_source_sha256:
        raise AnalysisFailure(
            "source private ZIP hash mismatch: "
            f"expected {args.expected_source_sha256}, got {actual_source_sha}"
        )

    with tempfile.TemporaryDirectory(prefix="r25-3-1-3-source-") as temp_name:
        extracted = Path(temp_name)
        safe_extract_zip(source_zip, extracted)
        verify_manifest(extracted, "SHA256SUMS-private-analysis.txt")
        source_json = extracted / "analysis" / "r25.3.1.2-private-analysis.json"
        if not source_json.is_file():
            raise AnalysisFailure("source private-analysis JSON missing")
        source = json.loads(source_json.read_text(encoding="utf-8"))
        private, public = analyze_source(source, actual_source_sha)
        output_dir.mkdir(parents=True)
        try:
            write_outputs(output_dir, private, public)
            privacy_gate(output_dir / "publication", private)
        except Exception:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

    print("R25_3_1_3_SOURCE_PRIVATE_ZIP_HASH_GATE=PASS")
    print("R25_3_1_3_SOURCE_INTERNAL_MANIFEST_GATE=PASS")
    print("R25_3_1_3_OUTER_LENGTH_CLOSURE=PASS")
    print("R25_3_1_3_NESTED_LENGTH_CLOSURE=PASS")
    print("R25_3_1_3_SEQUENCE_CANDIDATE_MONOTONIC_STEP_ONE=PASS")
    print("R25_3_1_3_DISABLE_REPEAT_NORMALIZED_EQUAL=PASS")
    print("R25_3_1_3_ENABLE_REPEAT_NORMALIZED_EQUAL=PASS")
    print("R25_3_1_3_ENABLE_DISABLE_DISCRIMINATOR=PASS")
    print("R25_3_1_3_STRUCTURED_PAYLOAD_ROLE_CORRELATION=PASS")
    print("R25_3_1_3_PUBLICATION_PRIVACY_GATE=PASS")
    print("R25_3_1_3_DEVICE_CONTACT=NO")
    print("R25_3_1_3_CUSTOM_TRANSMISSION_ATTEMPTED=NO")
    print("R25_3_1_3_CAPTURED_PAYLOAD_REPLAY_ATTEMPTED=NO")
    print(f"R1_3_3_2_25_3_1_3_ACCEPTANCE={ACCEPTANCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
