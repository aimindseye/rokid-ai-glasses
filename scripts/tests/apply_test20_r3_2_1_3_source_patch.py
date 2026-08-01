#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE_PATH = Path("android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification")
MAIN_REL = PACKAGE_PATH / "MainActivity.java"
CONTROLLER_REL = PACKAGE_PATH / "CxrLPhotoController.java"
GRADLE_REL = Path("android-client/test20r32/build.gradle.kts")
NEW_VERSION = "1.0-test20-r3.2.1.3"


class PatchError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_once(text: str, old: str, label: str) -> None:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: expected exactly one baseline marker, found {count}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require_once(text, old, label)
    return text.replace(old, new, 1)


def patch_main(text: str) -> str:
    if "operator_gate_host_command" in text and "PHASE 2 — ARMED: capture ONE photo" in text:
        return text

    text = replace_once(
        text,
        "import android.content.Intent;\nimport android.content.pm.PackageInfo;",
        "import android.content.BroadcastReceiver;\n"
        "import android.content.Context;\n"
        "import android.content.Intent;\n"
        "import android.content.IntentFilter;\n"
        "import android.content.pm.PackageInfo;",
        "MainActivity imports",
    )
    text = replace_once(
        text,
        "    private Button disconnectButton;\n    private String token;",
        "    private Button disconnectButton;\n"
        "    private String token;\n"
        "    private String operatorGateRunId;\n"
        "    private String operatorGateToken;\n"
        "    private BroadcastReceiver operatorGateReceiver;\n"
        "    private boolean operatorGateReceiverRegistered;\n"
        "    private static final String OPERATOR_GATE_ACTION =\n"
        "            \"org.aimindseye.rokid.cxrphotoqualification.ARM_ONE_PHOTO\";",
        "MainActivity gate fields",
    )
    text = replace_once(
        text,
        "        if (runId == null || runId.isBlank()) runId = utcTimestamp();\n"
        "        String firmwareLabel = getIntent().getStringExtra(\"firmware_label\");",
        "        if (runId == null || runId.isBlank()) runId = utcTimestamp();\n"
        "        operatorGateRunId = runId;\n"
        "        operatorGateToken = getIntent().getStringExtra(\"operator_gate_token\");\n"
        "        String firmwareLabel = getIntent().getStringExtra(\"firmware_label\");",
        "MainActivity initial gate extras",
    )
    text = replace_once(
        text,
        "        buildUi(runId, firmwareLabel);\n        RuntimeAppIdentity identity = runtimeAppIdentity();",
        "        buildUi(runId, firmwareLabel);\n"
        "        registerOperatorGateReceiver();\n"
        "        logger.event(\"operator_gate_initialized\", EvidenceLogger.details(\n"
        "                \"phase\", \"PREREQUISITE_LOCKED\",\n"
        "                \"photo_control_enabled\", false,\n"
        "                \"host_arm_granted\", false,\n"
        "                \"arm_token_present\", operatorGateToken != null && !operatorGateToken.isBlank(),\n"
        "                \"arm_token_value_logged\", false,\n"
        "                \"host_arm_action\", \"ARM_ONE_PHOTO\"));\n"
        "        RuntimeAppIdentity identity = runtimeAppIdentity();",
        "MainActivity gate initialization event",
    )
    text = replace_once(
        text,
        "                    @Override public void onPhotoReady() {\n"
        "                        captureButton.setEnabled(true);\n"
        "                        setStatus(\"ONE-SHOT PHOTO READY. Point only at the printed Test 20 r3.2 target, then tap Capture exactly once.\");\n"
        "                    }",
        "                    @Override public void onPhotoReady() {\n"
        "                        captureButton.setEnabled(false);\n"
        "                        captureButton.setText(\"3. PHASE 1 — PHOTO LOCKED (wait for host arm)\");\n"
        "                        logger.event(\"operator_gate_prerequisite_ready\", EvidenceLogger.details(\n"
        "                                \"photo_control_enabled\", false,\n"
        "                                \"host_arm_granted\", false,\n"
        "                                \"photo_request_issued\", false));\n"
        "                        setStatus(\"PHASE 1 COMPLETE — PHOTO LOCKED. Return to the host terminal. Do not tap item 3 until the host arms Phase 2.\");\n"
        "                    }",
        "MainActivity onPhotoReady lock",
    )
    text = replace_once(
        text,
        "                    @Override public void onPhotoRequestIssued() {\n"
        "                        captureButton.setEnabled(false);\n"
        "                        setStatus(\"One photo request issued. Keep the target steady and wait for the terminal result.\");\n"
        "                    }",
        "                    @Override public void onPhotoRequestIssued() {\n"
        "                        captureButton.setEnabled(false);\n"
        "                        captureButton.setText(\"3. PHOTO REQUEST CONSUMED — PERMANENTLY LOCKED\");\n"
        "                        setStatus(\"One armed photo request issued. The photo control is permanently locked for this run.\");\n"
        "                    }",
        "MainActivity post-request lock",
    )
    text = replace_once(
        text,
        "    @Override protected void onDestroy() {\n"
        "        if (controller != null) controller.disconnect(\"activity_destroyed\");",
        "    @Override protected void onDestroy() {\n"
        "        if (operatorGateReceiverRegistered && operatorGateReceiver != null) {\n"
        "            try { unregisterReceiver(operatorGateReceiver); } catch (Throwable ignored) { }\n"
        "            operatorGateReceiverRegistered = false;\n"
        "        }\n"
        "        if (controller != null) controller.disconnect(\"activity_destroyed\");",
        "MainActivity receiver cleanup",
    )
    text = replace_once(
        text,
        "        title.setText(\"Test 20 r3.2 — One-Shot Photo Qualification\");",
        "        title.setText(\"Test 20 r3.2.1.3 — Two-Phase One-Shot Photo Qualification\");",
        "MainActivity title",
    )
    text = replace_once(
        text,
        "        scope.setText(\"Exactly one takePhoto(1920,1080,80) request. Use only the printed public test target. No preview, file write, upload, audio operation, or cloud request.\");",
        "        scope.setText(\"PHASE 1: authorize/connect while PHOTO is mechanically locked. PHASE 2: only the host can arm exactly one takePhoto(1920,1080,80) request. No preview, file write, upload, audio operation, or cloud request.\");",
        "MainActivity scope",
    )
    text = replace_once(
        text,
        "        statusView.setText(\"Confirm Hi Rokid is connected, then tap Authorize once.\");",
        "        statusView.setText(\"PHASE 1 — PHOTO LOCKED. Confirm Hi Rokid is connected, then tap only Authorize and Start connection.\");",
        "MainActivity initial status",
    )
    text = replace_once(
        text,
        "            setStatus(\"One connection attempt started. Wait for ONE-SHOT PHOTO READY.\");",
        "            setStatus(\"PHASE 1 — connection started. Wait for PHASE 1 COMPLETE — PHOTO LOCKED.\");",
        "MainActivity connect status",
    )
    text = replace_once(
        text,
        "        captureButton = button(\"3. Capture exactly one bounded photo\");\n"
        "        captureButton.setEnabled(false);\n"
        "        captureButton.setOnClickListener(view -> {\n"
        "            captureButton.setEnabled(false);\n"
        "            controller.requestOnePhoto();\n"
        "        });",
        "        captureButton = button(\"3. PHASE 1 — PHOTO LOCKED (host arm required)\");\n"
        "        captureButton.setEnabled(false);\n"
        "        captureButton.setOnClickListener(view -> {\n"
        "            captureButton.setEnabled(false);\n"
        "            captureButton.setText(\"3. PHOTO REQUEST CONSUMED — PERMANENTLY LOCKED\");\n"
        "            boolean accepted = controller.requestOnePhoto();\n"
        "            logger.event(\"operator_gate_capture_dispatch\", EvidenceLogger.details(\n"
        "                    \"controller_request_accepted\", accepted,\n"
        "                    \"photo_control_enabled_after_click\", false));\n"
        "            if (!accepted) {\n"
        "                setStatus(\"Photo request blocked by the controller gate. Do not retry in this run.\");\n"
        "            }\n"
        "        });",
        "MainActivity capture listener",
    )
    text = replace_once(
        text,
        "    private Button button(String label) {",
        "    private void registerOperatorGateReceiver() {\n"
        "        operatorGateReceiver = new BroadcastReceiver() {\n"
        "            @Override public void onReceive(Context context, Intent intent) {\n"
        "                handleOperatorGateIntent(intent);\n"
        "            }\n"
        "        };\n"
        "        IntentFilter filter = new IntentFilter(OPERATOR_GATE_ACTION);\n"
        "        if (Build.VERSION.SDK_INT >= 33) {\n"
        "            registerReceiver(operatorGateReceiver, filter, Context.RECEIVER_EXPORTED);\n"
        "        } else {\n"
        "            registerReceiver(operatorGateReceiver, filter);\n"
        "        }\n"
        "        operatorGateReceiverRegistered = true;\n"
        "    }\n"
        "    private void handleOperatorGateIntent(Intent intent) {\n"
        "        String suppliedRunId = intent == null ? null : intent.getStringExtra(\"run_id\");\n"
        "        String suppliedToken = intent == null ? null : intent.getStringExtra(\"operator_gate_token\");\n"
        "        boolean actionMatch = intent != null && OPERATOR_GATE_ACTION.equals(intent.getAction());\n"
        "        boolean runIdMatch = operatorGateRunId != null && operatorGateRunId.equals(suppliedRunId);\n"
        "        boolean tokenPresent = suppliedToken != null && !suppliedToken.isBlank();\n"
        "        boolean tokenMatch = operatorGateToken != null && !operatorGateToken.isBlank()\n"
        "                && operatorGateToken.equals(suppliedToken);\n"
        "        boolean granted = actionMatch && runIdMatch && tokenMatch && controller != null\n"
        "                && controller.grantHostArm();\n"
        "        captureButton.setEnabled(granted);\n"
        "        if (granted) {\n"
        "            captureButton.setText(\"3. PHASE 2 — ARMED: capture ONE photo\");\n"
        "            setStatus(\"PHASE 2 — ARMED FOR EXACTLY ONE PHOTO. Confirm the printed target, then tap item 3 exactly once.\");\n"
        "        } else {\n"
        "            captureButton.setText(\"3. PHOTO LOCKED — host arm rejected\");\n"
        "            setStatus(\"Host arm rejected or not currently eligible. PHOTO REMAINS LOCKED. Return to the terminal.\");\n"
        "        }\n"
        "        logger.event(\"operator_gate_host_command\", EvidenceLogger.details(\n"
        "                \"action\", \"ARM_ONE_PHOTO\",\n"
        "                \"action_match\", actionMatch,\n"
        "                \"run_id_match\", runIdMatch,\n"
        "                \"token_present\", tokenPresent,\n"
        "                \"token_match\", tokenMatch,\n"
        "                \"token_value_logged\", false,\n"
        "                \"granted\", granted,\n"
        "                \"photo_control_enabled_after_command\", granted));\n"
        "    }\n"
        "    private Button button(String label) {",
        "MainActivity host-arm receiver methods",
    )
    return text


def patch_controller(text: str) -> str:
    if "operator_gate_arm_result" in text and "hostArmGranted.compareAndSet(true, false)" in text:
        return text
    text = replace_once(
        text,
        "    private final AtomicBoolean photoRequestIssued = new AtomicBoolean(false);\n"
        "    private final AtomicBoolean terminal = new AtomicBoolean(false);",
        "    private final AtomicBoolean photoRequestIssued = new AtomicBoolean(false);\n"
        "    private final AtomicBoolean hostArmGranted = new AtomicBoolean(false);\n"
        "    private final AtomicBoolean hostArmConsumed = new AtomicBoolean(false);\n"
        "    private final AtomicBoolean terminal = new AtomicBoolean(false);",
        "Controller gate atomics",
    )
    text = replace_once(
        text,
        "    boolean requestOnePhoto() {\n",
        "    boolean grantHostArm() {\n"
        "        boolean eligible = photoReady && !terminal.get() && link != null\n"
        "                && !photoRequestIssued.get() && !hostArmConsumed.get();\n"
        "        if (!eligible) {\n"
        "            logger.event(\"operator_gate_arm_result\", EvidenceLogger.details(\n"
        "                    \"granted\", false,\n"
        "                    \"disposition\", \"NOT_ELIGIBLE\",\n"
        "                    \"photo_ready\", photoReady,\n"
        "                    \"terminal\", terminal.get(),\n"
        "                    \"photo_request_issued\", photoRequestIssued.get(),\n"
        "                    \"host_arm_consumed\", hostArmConsumed.get(),\n"
        "                    \"host_arm_available\", hostArmGranted.get()));\n"
        "            return false;\n"
        "        }\n"
        "        if (hostArmGranted.get()) {\n"
        "            logger.event(\"operator_gate_arm_result\", EvidenceLogger.details(\n"
        "                    \"granted\", true,\n"
        "                    \"disposition\", \"ALREADY_ARMED\",\n"
        "                    \"photo_ready\", true,\n"
        "                    \"photo_request_issued\", false,\n"
        "                    \"host_arm_available\", true));\n"
        "            return true;\n"
        "        }\n"
        "        boolean granted = hostArmGranted.compareAndSet(false, true);\n"
        "        logger.event(\"operator_gate_arm_result\", EvidenceLogger.details(\n"
        "                \"granted\", granted,\n"
        "                \"disposition\", granted ? \"ARMED\" : \"RACE_REJECTED\",\n"
        "                \"photo_ready\", photoReady,\n"
        "                \"photo_request_issued\", photoRequestIssued.get(),\n"
        "                \"host_arm_available\", hostArmGranted.get()));\n"
        "        return granted;\n"
        "    }\n"
        "    boolean requestOnePhoto() {\n",
        "Controller grantHostArm method",
    )
    text = replace_once(
        text,
        "        if (!photoRequestIssued.compareAndSet(false, true)) {",
        "        if (!hostArmGranted.compareAndSet(true, false)) {\n"
        "            logger.event(\"photo_request_rejected\", EvidenceLogger.details(\n"
        "                    \"reason\", \"host_arm_not_granted_or_already_consumed\",\n"
        "                    \"host_arm_consumed\", hostArmConsumed.get(),\n"
        "                    \"request_count\", photoRequestCount));\n"
        "            return false;\n"
        "        }\n"
        "        hostArmConsumed.set(true);\n"
        "        if (!photoRequestIssued.compareAndSet(false, true)) {",
        "Controller atomic arm consumption",
    )
    text = replace_once(
        text,
        "                \"photo_ready\", photoReady,\n"
        "                \"photo_request_count\", photoRequestCount,",
        "                \"photo_ready\", photoReady,\n"
        "                \"host_arm_available\", hostArmGranted.get(),\n"
        "                \"host_arm_consumed\", hostArmConsumed.get(),\n"
        "                \"photo_request_count\", photoRequestCount,",
        "Controller terminal gate evidence",
    )
    return text


def patch_gradle(text: str) -> str:
    if f'versionName = "{NEW_VERSION}"' in text:
        return text
    text = replace_once(text, "        versionCode = 1\n", "        versionCode = 2\n", "Gradle versionCode")
    text = replace_once(
        text,
        '        versionName = "1.0-test20-r3.2"\n',
        f'        versionName = "{NEW_VERSION}"\n',
        "Gradle versionName",
    )
    return text


def atomic_write(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply bounded Test 20 r3.2.1.3 APK source repair.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--backup-dir")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").is_dir():
        print(f"ERROR: not a git repository: {repo}", file=sys.stderr)
        return 2

    paths = [repo / MAIN_REL, repo / CONTROLLER_REL, repo / GRADLE_REL]
    for path in paths:
        if not path.is_file():
            print(f"ERROR: required r3.2 source path missing: {path}", file=sys.stderr)
            return 1

    originals = {path: path.read_text(encoding="utf-8") for path in paths}
    try:
        updated = {
            repo / MAIN_REL: patch_main(originals[repo / MAIN_REL]),
            repo / CONTROLLER_REL: patch_controller(originals[repo / CONTROLLER_REL]),
            repo / GRADLE_REL: patch_gradle(originals[repo / GRADLE_REL]),
        }
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("REPOSITORY_MUTATION=NONE", file=sys.stderr)
        return 1

    changed = [path for path in paths if updated[path] != originals[path]]
    if args.check_only:
        print("TEST20_R3_2_1_3_APK_SOURCE_PATCH_PREFLIGHT=PASS")
        print(f"FILES_REQUIRING_PATCH={len(changed)}")
        return 0
    if not changed:
        print("TEST20_R3_2_1_3_APK_SOURCE_PATCH=ALREADY_APPLIED")
        return 0

    backup_dir = (
        Path(args.backup_dir).expanduser().resolve()
        if args.backup_dir
        else repo / ".git" / "test20-r3.2.1.3-backup"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in changed:
        rel = path.relative_to(repo)
        backup = backup_dir / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)

    try:
        for path in changed:
            atomic_write(path, updated[path])
    except Exception as exc:
        for path in changed:
            backup = backup_dir / path.relative_to(repo)
            if backup.is_file():
                shutil.copy2(backup, path)
        print(f"ERROR: source mutation failed and backups were restored: {exc}", file=sys.stderr)
        return 1

    print("TEST20_R3_2_1_3_APK_SOURCE_PATCH=PASS")
    print(f"BACKUP_DIR={backup_dir}")
    for path in changed:
        print(f"PATCHED={path.relative_to(repo)}")
        print(f"PATCHED_SHA256={sha256_bytes(path.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
