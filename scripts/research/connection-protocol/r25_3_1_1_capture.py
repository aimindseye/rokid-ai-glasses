#!/usr/bin/env python3
"""Controlled stock Hi Rokid ADB-toggle capture for r1.3.3.2.25.3.1.1.

The operator uses only the stock Hi Rokid Developer control. The repaired oracle
classifies the toggle by the glasses persist.vendor.adb property and the stock UI
switch state. Host ADB transport disappearance is explicitly not required.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
hci_preflight = None
analyzer = None

UTC = dt.timezone.utc
RELEASE = "r1.3.3.2.25.3.1.1"
MARKER_TAG = "R25_3_1_1_CAPTURE"
DEFAULT_STOCK_PACKAGE = "com.rokid.sprite.global.aiapp"
DEFAULT_PROBE_PACKAGE = "org.aimindseye.rokid.channelprobe"
GLASSES_TOKENS = ("model:rg_glasses", "product:glasses", "device:glasses")


class CaptureFailure(RuntimeError):
    pass


def run(cmd: Sequence[str], *, check: bool = True, timeout: Optional[float] = None, text: bool = True):
    proc = subprocess.run(
        list(map(str, cmd)), check=False, timeout=timeout, text=text,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise CaptureFailure(
            f"command failed rc={proc.returncode}: {' '.join(map(str, cmd))}\n{proc.stderr or ''}"
        )
    return proc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iso_epoch(value: float) -> str:
    return dt.datetime.fromtimestamp(value, tz=UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def package_tree(root: Path, dest: Path, manifest_name: str) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CaptureFailure(f"symlink rejected: {path}")
        if path.is_file() and path.name != manifest_name:
            lines.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    (root / manifest_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root.parent).as_posix())


class Device:
    def __init__(self, adb: str, serial: str):
        self.adb = adb
        self.serial = serial

    def cmd(self, *args: str, check: bool = True, timeout: Optional[float] = None):
        return run([self.adb, "-s", self.serial, *args], check=check, timeout=timeout)

    def shell(self, *args: str, check: bool = True, timeout: Optional[float] = None):
        return self.cmd("shell", *args, check=check, timeout=timeout)

    def get_state(self, *, check: bool = True) -> str:
        return self.cmd("get-state", check=check, timeout=10).stdout.strip()

    def package_installed(self, package: str) -> bool:
        return f"package:{package}" in self.shell("pm", "list", "packages", package, check=False).stdout

    def package_enabled(self, package: str) -> bool:
        output = self.shell("dumpsys", "package", package, check=False).stdout
        match = re.search(r"\benabled=(\d+)", output)
        return not match or match.group(1) in {"0", "1"}

    def force_stop(self, package: str) -> None:
        self.shell("am", "force-stop", package, check=False)

    def launch(self, package: str) -> None:
        self.shell("monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1", check=False)

    def marker(self, text: str) -> None:
        self.shell("log", "-t", MARKER_TAG, text, check=False)

    def epoch(self) -> float:
        proc = self.shell("date", "+%s.%N", check=False)
        value = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        if not re.fullmatch(r"\d{10}(?:\.\d+)?", value):
            value = self.shell("date", "+%s").stdout.strip().splitlines()[-1]
        try:
            return float(value)
        except ValueError as exc:
            raise CaptureFailure(f"invalid phone epoch: {value!r}") from exc

    def dump_ui(self, local: Path) -> str:
        remote = f"/sdcard/r25_3_1_1_ui_{os.getpid()}.xml"
        self.shell("uiautomator", "dump", remote, check=False, timeout=20)
        proc = self.cmd("exec-out", "cat", remote, check=False, timeout=15)
        self.shell("rm", "-f", remote, check=False)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
        return proc.stdout or ""

    def foreground(self) -> str:
        return "\n".join([
            self.shell("dumpsys", "window", "windows", check=False).stdout,
            self.shell("dumpsys", "activity", "activities", check=False).stdout,
        ])


def page_attested(xml_text: str, foreground_text: str, stock_package: str) -> Dict[str, Any]:
    corpus = re.sub(r"\s+", " ", xml_text)
    patterns = [r"(?i)developer(?:\s*mode)?", r"(?i)glasses\s*adb\s*debug", r"(?i)usb\s*(?:adb|debug)", r"开发者模式"]
    matched = [pattern for pattern in patterns if re.search(pattern, corpus)]
    foreground_ok = stock_package in foreground_text or stock_package in xml_text
    switch = parse_switch_state(xml_text)
    return {
        "foreground_stock_app": foreground_ok,
        "matched_page_patterns": matched,
        "switch_state": switch,
        "attested": foreground_ok and bool(matched) and switch in {"on", "off"},
    }


def parse_switch_state(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "unknown"
    candidates = []
    for node in root.iter("node"):
        resource_id = node.attrib.get("resource-id", "")
        if resource_id.endswith("/switch_developer_adb") or resource_id == "switch_developer_adb":
            candidates.append(node)
    if len(candidates) != 1:
        return "unknown"
    checked = candidates[0].attrib.get("checked", "").lower()
    return {"true": "on", "false": "off"}.get(checked, "unknown")


def normalize_vendor_adb(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "on", "enabled"}:
        return "on"
    if lowered in {"0", "false", "off", "disabled"}:
        return "off"
    return "unknown"


def host_adb_devices(adb: str) -> str:
    return run([adb, "devices", "-l"], check=False, timeout=15).stdout or ""


def parse_glasses_rows(output: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for line in output.splitlines():
        lowered = line.lower()
        if any(token in lowered for token in GLASSES_TOKENS):
            fields = line.split()
            if fields:
                rows.append((fields[0], line.strip()))
    return rows


def discover_glasses_serial(adb: str, override: Optional[str]) -> Tuple[str, str]:
    rows = parse_glasses_rows(host_adb_devices(adb))
    if override:
        matches = [row for row in rows if row[0] == override]
        if len(matches) != 1:
            raise CaptureFailure("explicit glasses serial is not the unique connected RG_glasses row")
        return matches[0]
    if len(rows) != 1:
        raise CaptureFailure(f"exactly one connected RG_glasses ADB row required; found {len(rows)}")
    return rows[0]


def read_glasses_probe(glasses: Device) -> Dict[str, Any]:
    state_proc = glasses.cmd("get-state", check=False, timeout=10)
    control_state = state_proc.stdout.strip() if state_proc.returncode == 0 else "unavailable"
    def shell_value(*args: str) -> str:
        proc = glasses.shell(*args, check=False, timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    raw_vendor = shell_value("getprop", "persist.vendor.adb") if control_state == "device" else ""
    return {
        "control_channel_state": control_state,
        "control_channel_usable": control_state == "device",
        "persist_vendor_adb_raw": raw_vendor,
        "persist_vendor_adb_state": normalize_vendor_adb(raw_vendor),
        "global_adb_enabled": shell_value("settings", "get", "global", "adb_enabled"),
        "sys_usb_config": shell_value("getprop", "sys.usb.config"),
        "sys_usb_state": shell_value("getprop", "sys.usb.state"),
        "persist_sys_usb_config": shell_value("getprop", "persist.sys.usb.config"),
        "init_svc_adbd": shell_value("getprop", "init.svc.adbd"),
    }


def semantic_sample(phone: Device, glasses: Device, adb: str, evidence: Path, sample_id: str) -> Dict[str, Any]:
    xml_text = phone.dump_ui(evidence / "ui" / f"{sample_id}.xml")
    probe = read_glasses_probe(glasses)
    output = host_adb_devices(adb)
    rows = parse_glasses_rows(output)
    sample = {
        "utc": iso_epoch(time.time()),
        "ui_switch_state": parse_switch_state(xml_text),
        "host_glasses_transport_present": any(serial == glasses.serial for serial, _ in rows),
        "host_glasses_row_count": len(rows),
        "semantic_state": "unknown",
        **probe,
    }
    if sample["ui_switch_state"] == sample["persist_vendor_adb_state"] and sample["ui_switch_state"] in {"on", "off"}:
        sample["semantic_state"] = sample["ui_switch_state"]
    return sample


def wait_for_semantic_state(phone: Device, glasses: Device, adb: str, target: Optional[str], timeout: float, evidence: Path, action_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    samples: List[Dict[str, Any]] = []
    while time.monotonic() < deadline:
        sample = semantic_sample(phone, glasses, adb, evidence, f"{action_id}-sample-{len(samples):03d}")
        samples.append(sample)
        coherent = sample["semantic_state"] in {"on", "off"} and sample["control_channel_usable"]
        if coherent and (target is None or sample["semantic_state"] == target):
            path = evidence / "semantic-state" / f"{action_id}-samples-private.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return sample | {"sample_count": len(samples), "semantic_oracle_passed": True}
        time.sleep(0.5)
    path = evidence / "semantic-state" / f"{action_id}-samples-private.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    expected = target or "coherent on/off"
    raise CaptureFailure(f"semantic ADB state did not reach {expected} for {action_id}")


def operator_confirm(prompt: str, input_prompt: str, test_auto: bool) -> None:
    print(prompt, flush=True)
    if test_auto:
        return
    try:
        input(input_prompt)
    except EOFError as exc:
        raise CaptureFailure("operator input ended before confirmation") from exc


def prepare_stock_action(
    phone: Device,
    glasses: Device,
    adb: str,
    evidence: Path,
    action_id: str,
    action: str,
    current_state: str,
    test_auto: bool,
) -> Dict[str, Any]:
    """Attest the unchanged state before arming the operator action.

    The pre-action semantic sample must be complete before the prompt that tells
    the operator to toggle. This two-stage sequence closes the r25.3.1 race in
    which a compliant operator could toggle immediately after Enter and cause
    that changed state to be misclassified as the pre-action sample.
    """
    operator_confirm(
        f"\nPRE-ACTION ATTESTATION {action_id.upper()}\n"
        f"Expected semantic state: {current_state.upper()}\n"
        "Do not toggle the stock switch yet.\n",
        "Press Enter to capture the unchanged pre-action state: ",
        test_auto,
    )
    before = semantic_sample(phone, glasses, adb, evidence, f"{action_id}-before")
    if before["semantic_state"] != current_state or not before["control_channel_usable"]:
        raise CaptureFailure(f"pre-action semantic state mismatch for {action_id}")

    marker = action_id.upper().replace("-", "_")
    print(f"R25_3_1_1_{marker}_PRE_ACTION_ATTESTATION=PASS")
    operator_confirm(
        f"\nACTION {action_id.upper()}\n"
        f"Verified semantic state: {current_state.upper()}\n"
        f"After Enter, perform exactly one stock {action.upper()} action. "
        "Complete the stock dialog if shown.\n",
        "Press Enter to arm capture, then perform the stock action: ",
        test_auto,
    )
    return before


def action_plan(initial: str, cycles: int) -> List[Tuple[int, str, str]]:
    state = initial
    sequence: List[Tuple[int, str, str]] = []
    for cycle in range(1, cycles + 1):
        for _ in range(2):
            action = "disable" if state == "on" else "enable"
            target = "off" if state == "on" else "on"
            sequence.append((cycle, action, target))
            state = target
    if state != initial:
        raise CaptureFailure("internal action sequence does not restore the initial semantic state")
    return sequence


def print_plan(initial: str, cycles: int) -> int:
    sequence = action_plan(initial, cycles)
    print(f"R25_3_1_1_PLAN_RELEASE={RELEASE}")
    print("R25_3_1_1_PLAN_DEVICE_CONTACT=NO")
    print("R25_3_1_1_DISABLE_ORACLE=PERSIST_VENDOR_ADB_FALSE_AND_UI_SWITCH_OFF")
    print("R25_3_1_1_ENABLE_ORACLE=PERSIST_VENDOR_ADB_TRUE_AND_UI_SWITCH_ON")
    print("R25_3_1_1_ADB_TRANSPORT_DISAPPEARANCE_REQUIRED=NO")
    print("R25_3_1_1_CONTROL_CHANNEL_USABLE_REQUIRED=YES")
    for index, (cycle, action, target) in enumerate(sequence, 1):
        print(f"R25_3_1_1_PLAN_ACTION_{index}=cycle:{cycle},action:{action},target:{target}")
    print("R25_3_1_1_PLAN_FINAL_STATE_RESTORED=YES")
    print("R25_3_1_1_NO_DEVICE_DRY_RUN=PASS")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--phone-serial")
    parser.add_argument("--glasses-serial")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--adb", default=os.environ.get("ADB", "adb"))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--stock-package", default=DEFAULT_STOCK_PACKAGE)
    parser.add_argument("--probe-package", default=DEFAULT_PROBE_PACKAGE)
    parser.add_argument("--baseline-seconds", type=float, default=8.0)
    parser.add_argument("--action-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--initial-semantic-state", choices=("on", "off"), default="off")
    parser.add_argument("--test-auto-actions", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.cycles < 2 or args.cycles > 3:
        raise CaptureFailure("cycles must be 2 or 3")
    if args.plan_only:
        return print_plan(args.initial_semantic_state, args.cycles)
    if not args.phone_serial or not args.output:
        raise CaptureFailure("--phone-serial and --output are required unless --plan-only is used")
    if args.test_auto_actions and os.environ.get("R25_3_1_1_ALLOW_TEST_MODE") != "1":
        raise CaptureFailure("test-auto-actions is disabled outside the test harness")

    repo = args.repo.expanduser().resolve()
    scripts = repo / "scripts/research/connection-protocol"
    sys.path.insert(0, str(scripts))
    global hci_preflight, analyzer
    import r25_2_3_2_hci_preflight as hci_preflight_module  # type: ignore
    import r25_3_1_1_analyze as analyzer_module  # type: ignore
    hci_preflight = hci_preflight_module
    analyzer = analyzer_module
    out = args.output.expanduser().resolve()
    if out.exists() or any(Path(str(out) + suffix).exists() for suffix in ("-private-evidence.zip", "-private-analysis.zip", "-sanitized-publication.zip")):
        raise CaptureFailure(f"output already exists: {out}")
    required = [scripts / "r25_2_3_2_capture.py", scripts / "r25_2_3_2_hci_preflight.py", scripts / "r25_3_1_1_analyze.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise CaptureFailure(f"required installed dependencies missing: {missing}")

    evidence = out / "evidence"
    analysis = out / "analysis-output"
    evidence.mkdir(parents=True, exist_ok=False)
    phone = Device(args.adb, args.phone_serial)
    if phone.get_state() != "device":
        raise CaptureFailure("Pixel ADB transport is not in device state")
    if not phone.package_installed(args.stock_package):
        raise CaptureFailure(f"stock package not installed: {args.stock_package}")
    if not phone.package_enabled(args.stock_package):
        raise CaptureFailure(f"stock package disabled: {args.stock_package}; enable it before capture")

    glasses_serial, glasses_row = discover_glasses_serial(args.adb, args.glasses_serial)
    glasses = Device(args.adb, glasses_serial)
    (evidence / "adb-devices-initial-private.txt").write_text(host_adb_devices(args.adb), encoding="utf-8")
    (evidence / "glasses-row-initial-private.txt").write_text(glasses_row + "\n", encoding="utf-8")

    probes = {
        "secure_bluetooth_hci_log": phone.shell("settings", "get", "secure", "bluetooth_hci_log", check=False).stdout.strip(),
        "global_btsnoop_default_mode": phone.shell("settings", "get", "global", "bluetooth_btsnoop_default_mode", check=False).stdout.strip(),
        "persist_btsnooplogmode": phone.shell("getprop", "persist.bluetooth.btsnooplogmode", check=False).stdout.strip(),
        "persist_btsnoopdefaultmode": phone.shell("getprop", "persist.bluetooth.btsnoopdefaultmode", check=False).stdout.strip(),
        "persist_btsnoopenable": phone.shell("getprop", "persist.bluetooth.btsnoopenable", check=False).stdout.strip(),
        "dumpsys_bluetooth": phone.shell("dumpsys", "bluetooth_manager", check=False).stdout,
    }
    preflight = hci_preflight.classify(probes)
    (evidence / "hci-preflight-probes-private.json").write_text(json.dumps(probes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evidence / "hci-preflight-private.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not preflight.get("capture_allowed"):
        raise CaptureFailure(f"HCI capture not allowed: {preflight.get('status')}")
    print(f"R25_3_1_1_HCI_PREFLIGHT_STATUS={preflight.get('status')}")
    print("R25_3_1_1_HCI_CAPTURE_ALLOWED=YES")

    phone.force_stop(args.probe_package)
    phone.launch(args.stock_package)
    operator_confirm(
        "\nOn the Pixel 7, navigate Hi Rokid to Developer > Glasses ADB debugging.\n"
        "Keep the original data/debug cable connected. Do not toggle yet.\n",
        "Press Enter only after the stock Developer page and ADB switch are visible: ",
        args.test_auto_actions,
    )
    ui_text = phone.dump_ui(evidence / "ui" / "00-stock-developer-page.xml")
    foreground = phone.foreground()
    (evidence / "ui" / "00-foreground-private.txt").write_text(foreground, encoding="utf-8")
    attestation = page_attested(ui_text, foreground, args.stock_package)
    (evidence / "ui" / "00-page-attestation.json").write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not attestation["attested"]:
        raise CaptureFailure("Hi Rokid Developer page and ADB switch were not attested")
    print("R25_3_1_1_STOCK_DEVELOPER_MODE_PAGE_ATTESTED=YES")

    initial_probe = wait_for_semantic_state(phone, glasses, args.adb, None, 20.0, evidence, "initial")
    initial_state = initial_probe["semantic_state"]
    action_sequence = action_plan(initial_state, args.cycles)
    print(f"R25_3_1_1_INITIAL_SEMANTIC_STATE={initial_state.upper()}")
    print("R25_3_1_1_ADB_TRANSPORT_DISAPPEARANCE_REQUIRED=NO")

    log_path = evidence / "logcat-all-epoch.txt"
    log_out = log_path.open("wb")
    log_err = (evidence / "logcat.stderr.txt").open("wb")
    logcat_proc = subprocess.Popen(
        [args.adb, "-s", args.phone_serial, "logcat", "-b", "all", "-v", "epoch"],
        stdout=log_out, stderr=log_err, preexec_fn=os.setsid,
    )
    aborted = False

    def cleanup(_signum=None, _frame=None):
        nonlocal aborted
        aborted = True
        if logcat_proc.poll() is None:
            try:
                os.killpg(os.getpgid(logcat_proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        (out / "ABORTED.txt").write_text(
            "Capture aborted. The script did not attempt to change or restore the stock toggle automatically.\n",
            encoding="utf-8",
        )
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    try:
        time.sleep(float(os.environ.get("R25_3_1_1_LOGCAT_STARTUP_SECONDS", "1")))
        if logcat_proc.poll() is not None:
            raise CaptureFailure("bounded logcat exited before capture")
        capture_start = phone.epoch()
        phone.marker(f"event=capture_start release={RELEASE}")
        baseline_windows = []
        baseline_start = phone.epoch(); phone.marker("event=baseline_start id=baseline-before")
        print(f"R25_3_1_1_BASELINE_IDLE_SECONDS={args.baseline_seconds}")
        time.sleep(args.baseline_seconds)
        baseline_end = phone.epoch(); phone.marker("event=baseline_end id=baseline-before")
        baseline_windows.append({"window_id": "baseline-before", "start_utc": iso_epoch(baseline_start), "end_utc": iso_epoch(baseline_end), "time_source": "phone_epoch"})

        action_windows = []
        current_state = initial_state
        for cycle, action, target in action_sequence:
            action_id = f"{action}-{cycle}"
            before = prepare_stock_action(
                phone, glasses, args.adb, evidence, action_id, action,
                current_state, args.test_auto_actions,
            )
            start_epoch = phone.epoch()
            phone.marker(f"event=action_start id={action_id} action={action} cycle={cycle} target={target}")
            transition = wait_for_semantic_state(phone, glasses, args.adb, target, args.action_timeout_seconds, evidence, action_id)
            phone.marker(f"event=semantic_transition id={action_id} action={action} cycle={cycle} result={target}")
            time.sleep(args.settle_seconds)
            end_epoch = phone.epoch()
            phone.marker(f"event=action_end id={action_id} action={action} cycle={cycle} result={target}")
            action_windows.append({
                "action_id": action_id, "action": action, "cycle": cycle,
                "start_utc": iso_epoch(start_epoch), "end_utc": iso_epoch(end_epoch), "time_source": "phone_epoch",
                "initial_semantic_state": current_state, "target_semantic_state": target,
                "semantic_oracle_passed": True,
                "persist_vendor_adb_state": transition["persist_vendor_adb_state"],
                "ui_switch_state": transition["ui_switch_state"],
                "control_channel_usable": transition["control_channel_usable"],
                "host_glasses_transport_present": transition["host_glasses_transport_present"],
                "global_adb_enabled": transition["global_adb_enabled"],
                "sys_usb_config": transition["sys_usb_config"],
                "persist_sys_usb_config": transition["persist_sys_usb_config"],
                "init_svc_adbd": transition["init_svc_adbd"],
            })
            print(f"R25_3_1_1_{action_id.upper().replace('-', '_')}_SEMANTIC_TRANSITION=PASS")
            print(f"R25_3_1_1_{action_id.upper().replace('-', '_')}_CONTROL_CHANNEL_USABLE=YES")
            current_state = target

        baseline_after_start = phone.epoch(); phone.marker("event=baseline_start id=baseline-after")
        time.sleep(args.baseline_seconds)
        baseline_after_end = phone.epoch(); phone.marker("event=baseline_end id=baseline-after")
        baseline_windows.append({"window_id": "baseline-after", "start_utc": iso_epoch(baseline_after_start), "end_utc": iso_epoch(baseline_after_end), "time_source": "phone_epoch"})
        final_probe = wait_for_semantic_state(phone, glasses, args.adb, initial_state, 20.0, evidence, "final")
        final_state = final_probe["semantic_state"]
        capture_end = phone.epoch(); phone.marker(f"event=capture_end release={RELEASE}")
    finally:
        if logcat_proc.poll() is None:
            try:
                os.killpg(os.getpgid(logcat_proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                logcat_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(logcat_proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                logcat_proc.wait(timeout=3)
        log_out.close(); log_err.close()
    if aborted:
        return 130

    bugreport = evidence / "bugreport.zip"
    proc = phone.cmd("bugreport", str(bugreport), check=False, timeout=360)
    (evidence / "bugreport.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (evidence / "bugreport.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0 or not bugreport.is_file() or bugreport.stat().st_size == 0:
        raise CaptureFailure("post-toggle bugreport was not created")
    print("R25_3_1_1_POST_ACTION_BUGREPORT=PASS")

    metadata = {
        "schema": "rokid.r25.3.1.1.capture-metadata.v1", "release": RELEASE,
        "capture_start_utc": iso_epoch(capture_start), "capture_end_utc": iso_epoch(capture_end),
        "phone_serial_sha256": hashlib.sha256(args.phone_serial.encode()).hexdigest(),
        "glasses_serial_sha256": hashlib.sha256(glasses_serial.encode()).hexdigest(),
        "stock_package": args.stock_package, "cycle_count": args.cycles, "expected_dlci": 6,
        "initial_semantic_state": initial_state, "final_semantic_state": final_state,
        "initial_semantic_probe": initial_probe, "final_semantic_probe": final_probe,
        "action_windows": action_windows, "baseline_windows": baseline_windows,
        "hci_preflight": preflight, "stock_ui_page_attested": True,
        "semantic_oracle": {
            "enable": "persist.vendor.adb=true and stock UI switch checked=true",
            "disable": "persist.vendor.adb=false and stock UI switch checked=false",
            "adb_transport_disappearance_required": False,
            "control_channel_usable_required": True,
        },
        "custom_rfcomm_client_used": False, "custom_transmission_attempted": False,
        "captured_payload_replay_attempted": False,
    }
    (evidence / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    private = analyzer.analyze(evidence, analysis)

    publication = analysis / "publication"
    public_hashes = [f"{sha256_file(path)}  {path.relative_to(publication).as_posix()}" for path in sorted(publication.rglob("*")) if path.is_file() and path.name != "evidence-hashes.txt"]
    (publication / "evidence-hashes.txt").write_text("\n".join(public_hashes) + "\n", encoding="utf-8")
    package_tree(evidence, Path(str(out) + "-private-evidence.zip"), "SHA256SUMS-private.txt")
    package_tree(analysis, Path(str(out) + "-private-analysis.zip"), "SHA256SUMS-private-analysis.txt")
    package_tree(publication, Path(str(out) + "-sanitized-publication.zip"), "SHA256SUMS-sanitized.txt")

    print(f"R25_3_1_1_INITIAL_SEMANTIC_STATE={initial_state.upper()}")
    print(f"R25_3_1_1_FINAL_SEMANTIC_STATE={final_state.upper()}")
    print("R25_3_1_1_FINAL_STATE_RESTORED=YES")
    print("R25_3_1_1_ADB_TRANSPORT_DISAPPEARANCE_REQUIRED=NO")
    print("R25_3_1_1_CONTROL_CHANNEL_USABLE=YES")
    print("R25_3_1_1_CUSTOM_TRANSMISSION_ATTEMPTED=NO")
    print(f"R25_3_1_1_QUALIFICATION_OUTCOME={private['qualification_outcome']}")
    print(f"R1_3_3_2_25_3_1_1_ACCEPTANCE={private['acceptance']}")
    for suffix in ("-private-evidence.zip", "-private-analysis.zip", "-sanitized-publication.zip"):
        path = Path(str(out) + suffix)
        print(f"R25_3_1_1_ARTIFACT={path}")
        print(f"R25_3_1_1_ARTIFACT_SHA256={sha256_file(path)}")
    print(f"R25_3_1_1_OUTPUT={out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("R25_3_1_1_CAPTURE_ABORTED=YES", file=sys.stderr)
        raise SystemExit(130)
    except CaptureFailure as exc:
        print(f"R25_3_1_1_CAPTURE_FAILURE={exc}", file=sys.stderr)
        raise SystemExit(1)
