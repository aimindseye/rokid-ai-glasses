#!/usr/bin/env python3
"""Generic early-exit-aware Frida 17 Android loader-event collector."""
from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import frida


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--package", required=True)
    p.add_argument("--agent", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--class-prefix", action="append", default=[])
    p.add_argument("--hook-registered-native-targets", action="store_true")
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    events: list[dict] = []
    detached = threading.Event()
    detach_record: dict[str, object] = {}

    device = frida.get_usb_device(timeout=10)
    pid = device.spawn([args.package])
    session = device.attach(pid)

    def record(payload: dict) -> None:
        payload = {"received_at": now(), **payload}
        events.append(payload)
        with args.output.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")

    def on_detached(reason, crash=None) -> None:
        detach_record.update({"event": "session_detached", "reason": str(reason), "crash": crash})
        record(detach_record.copy())
        detached.set()

    def on_message(message, data) -> None:
        if message.get("type") == "send":
            payload = message.get("payload")
            record(payload if isinstance(payload, dict) else {"event": "agent_message", "payload": payload})
        else:
            record({"event": "frida_message", "message": message})

    session.on("detached", on_detached)
    script = session.create_script(args.agent.read_text(encoding="utf-8"))
    script.on("message", on_message)
    script.load()
    prefixes = args.class_prefix or ["com.rokid.", "com.netease.nis.wrapper."]
    script.exports_sync.configure({
        "classPrefixes": prefixes,
        "hookRegisteredNativeTargets": args.hook_registered_native_targets,
    })
    device.resume(pid)

    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline and not detached.wait(0.25):
        pass

    if not detached.is_set():
        try:
            session.detach()
        except frida.InvalidOperationError:
            pass

    print(f"TARGET_PID={pid}")
    print(f"EVENT_COUNT={len(events)}")
    print(f"DETACHED={str(detached.is_set()).lower()}")
    print(f"OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
