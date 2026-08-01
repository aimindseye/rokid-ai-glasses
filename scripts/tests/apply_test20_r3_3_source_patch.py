#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE_PATH = Path("android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification")
MAIN_REL = PACKAGE_PATH / "MainActivity.java"
CONTROLLER_REL = PACKAGE_PATH / "CxrLPhotoController.java"
CONTRACT_REL = PACKAGE_PATH / "Test20R32Contract.java"
GRADLE_REL = Path("android-client/test20r32/build.gradle.kts")
NEW_VERSION = "1.0-test20-r3.3"


class PatchError(RuntimeError):
    pass


def require_once(text: str, old: str, label: str) -> None:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: expected exactly one baseline marker, found {count}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require_once(text, old, label)
    return text.replace(old, new, 1)


def patch_main(text: str) -> str:
    if "Test 20 r3.3 — Callback Non-Delivery Closure" in text and "callback_profile" in text:
        return text
    if "operator_gate_host_command" not in text or "PHASE 2 — ARMED: capture ONE photo" not in text:
        raise PatchError("MainActivity is not at the accepted r3.2.1.3 two-phase baseline")

    text = replace_once(
        text,
        "    private String operatorGateRunId;\n    private String operatorGateToken;",
        "    private String operatorGateRunId;\n"
        "    private String operatorGateToken;\n"
        "    private String callbackProfile;",
        "MainActivity callback profile field",
    )
    text = replace_once(
        text,
        "        operatorGateRunId = runId;\n"
        "        operatorGateToken = getIntent().getStringExtra(\"operator_gate_token\");\n"
        "        String firmwareLabel = getIntent().getStringExtra(\"firmware_label\");",
        "        operatorGateRunId = runId;\n"
        "        operatorGateToken = getIntent().getStringExtra(\"operator_gate_token\");\n"
        "        callbackProfile = getIntent().getStringExtra(\"callback_profile\");\n"
        "        if (callbackProfile == null || callbackProfile.isBlank()) {\n"
        "            callbackProfile = \"STRONG_REF_PRECONNECT\";\n"
        "        }\n"
        "        String firmwareLabel = getIntent().getStringExtra(\"firmware_label\");",
        "MainActivity callback profile extra",
    )
    text = replace_once(
        text,
        "        logger.event(\"operator_gate_initialized\", EvidenceLogger.details(\n"
        "                \"phase\", \"PREREQUISITE_LOCKED\",",
        "        logger.event(\"callback_profile_selected\", EvidenceLogger.details(\n"
        "                \"profile\", callbackProfile,\n"
        "                \"one_photo_request_per_run\", true,\n"
        "                \"audio_operation_enabled\", false,\n"
        "                \"payload_persistence_enabled\", false));\n"
        "        logger.event(\"operator_gate_initialized\", EvidenceLogger.details(\n"
        "                \"phase\", \"PREREQUISITE_LOCKED\",",
        "MainActivity profile event",
    )
    text = replace_once(
        text,
        "        controller = new CxrLPhotoController(this, logger,\n"
        "                new CxrLPhotoController.Callback() {",
        "        controller = new CxrLPhotoController(this, logger, callbackProfile,\n"
        "                new CxrLPhotoController.Callback() {",
        "MainActivity controller profile argument",
    )
    text = replace_once(
        text,
        "        title.setText(\"Test 20 r3.2.1.3 — Two-Phase One-Shot Photo Qualification\");",
        "        title.setText(\"Test 20 r3.3 — Callback Non-Delivery Closure\");",
        "MainActivity title",
    )
    text = replace_once(
        text,
        "        scope.setText(\"PHASE 1: authorize/connect while PHOTO is mechanically locked. PHASE 2: only the host can arm exactly one takePhoto(1920,1080,80) request. No preview, file write, upload, audio operation, or cloud request.\");",
        "        scope.setText(\"r3.3 preserves the r3.2.1.3 two-phase one-shot gate and instruments the post-takePhoto callback path. Exactly one photo request per run; no preview, file write, upload, audio operation, or cloud request. Profile: \" + callbackProfile);",
        "MainActivity scope",
    )
    return text


def patch_contract(text: str) -> str:
    if "R3_3_WATCHDOG_DELAYS_MS" in text:
        return text
    text = replace_once(
        text,
        "    static final long PHOTO_CALLBACK_TIMEOUT_MS = 30_000L;\n"
        "    static final long DUPLICATE_CALLBACK_WINDOW_MS = 3_000L;",
        "    static final long PHOTO_CALLBACK_TIMEOUT_MS = 30_000L;\n"
        "    static final long[] R3_3_WATCHDOG_DELAYS_MS = new long[] {\n"
        "            1_000L, 5_000L, 10_000L, 20_000L, 29_000L\n"
        "    };\n"
        "    static final long DUPLICATE_CALLBACK_WINDOW_MS = 3_000L;",
        "Contract watchdog delays",
    )
    return text


def patch_controller(text: str) -> str:
    if "image_callback_reregistration_result" in text and "R3_3_WATCHDOG_DELAYS_MS" in text:
        return text
    if "operator_gate_arm_result" not in text or "hostArmGranted.compareAndSet(true, false)" not in text:
        raise PatchError("CxrLPhotoController is not at the accepted r3.2.1.3 two-phase baseline")

    text = replace_once(
        text,
        "    private final EvidenceLogger logger;\n"
        "    private final Callback callback;\n"
        "    private final Handler handler = new Handler(Looper.getMainLooper());",
        "    private final EvidenceLogger logger;\n"
        "    private final Callback callback;\n"
        "    private final String callbackProfile;\n"
        "    private final Handler handler = new Handler(Looper.getMainLooper());",
        "Controller profile field",
    )
    text = replace_once(
        text,
        "    private boolean firstImageAccepted;\n"
        "    private int photoRequestCount;",
        "    private boolean firstImageAccepted;\n"
        "    private IImageStreamCbk imageStreamCallback;\n"
        "    private long imageCallbackRegistrationElapsedMs = -1L;\n"
        "    private long photoRequestReturnElapsedMs = -1L;\n"
        "    private int photoRequestCount;",
        "Controller callback lifetime fields",
    )
    text = replace_once(
        text,
        "    CxrLPhotoController(Activity activity, EvidenceLogger logger, Callback callback) {\n"
        "        this.activity = activity;\n"
        "        this.logger = logger;\n"
        "        this.callback = callback;\n"
        "    }",
        "    CxrLPhotoController(Activity activity, EvidenceLogger logger, String callbackProfile, Callback callback) {\n"
        "        this.activity = activity;\n"
        "        this.logger = logger;\n"
        "        this.callbackProfile = normalizeProfile(callbackProfile);\n"
        "        this.callback = callback;\n"
        "    }\n"
        "    private static String normalizeProfile(String value) {\n"
        "        String normalized = value == null ? \"\" : value.trim().toUpperCase();\n"
        "        if (normalized.equals(\"STRONG_REF_PRECONNECT\")\n"
        "                || normalized.equals(\"POSTCONNECT_REREGISTER\")\n"
        "                || normalized.equals(\"ARG3_ZERO_DIAGNOSTIC\")) {\n"
        "            return normalized;\n"
        "        }\n"
        "        throw new IllegalArgumentException(\"Unsupported r3.3 callback profile: \" + value);\n"
        "    }",
        "Controller profile constructor",
    )
    text = replace_once(
        text,
        "                \"cloud_api_client_present\", false));",
        "                \"cloud_api_client_present\", false,\n"
        "                \"callback_profile\", callbackProfile,\n"
        "                \"callback_strong_reference_enabled\", true));",
        "Controller connection profile evidence",
    )

    old_register = '''    private void registerImageCallback() {
        boolean returned = false;
        String errorClass = "";
        try {
            link.setCXRImageCbk(new IImageStreamCbk() {
                @Override public void onImageReceived(byte[] payload) {
                    ImageObservation observation = inspectImage(payload);
                    activity.runOnUiThread(() -> handleImageObservation(observation));
                }
                @Override public void onImageError(int code, String message) {
                    activity.runOnUiThread(() -> handleImageError(code, message));
                }
            });
            returned = true;
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        imageCallbackRegistered = returned;
        logger.event("image_callback_registration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "audio_callback_registered", false,
                "media_request_issued", false));
        if (!returned) finish("IMAGE_CALLBACK_REGISTRATION_FAILED", false);
    }
'''
    new_register = '''    private void registerImageCallback() {
        boolean returned = false;
        String errorClass = "";
        imageStreamCallback = new IImageStreamCbk() {
            @Override public void onImageReceived(byte[] payload) {
                logger.event("image_callback_dispatch", EvidenceLogger.details(
                        "kind", "PAYLOAD",
                        "profile", callbackProfile,
                        "callback_identity_hash", System.identityHashCode(imageStreamCallback),
                        "strong_reference_present", imageStreamCallback != null,
                        "on_main_looper", Looper.myLooper() == Looper.getMainLooper(),
                        "thread_name_sha256", EvidenceLogger.sha256(Thread.currentThread().getName()),
                        "payload_present", payload != null,
                        "payload_length", payload == null ? -1 : payload.length));
                ImageObservation observation = inspectImage(payload);
                activity.runOnUiThread(() -> handleImageObservation(observation));
            }
            @Override public void onImageError(int code, String message) {
                logger.event("image_callback_dispatch", EvidenceLogger.details(
                        "kind", "ERROR",
                        "profile", callbackProfile,
                        "callback_identity_hash", System.identityHashCode(imageStreamCallback),
                        "strong_reference_present", imageStreamCallback != null,
                        "on_main_looper", Looper.myLooper() == Looper.getMainLooper(),
                        "thread_name_sha256", EvidenceLogger.sha256(Thread.currentThread().getName()),
                        "error_code", code,
                        "message_present", message != null && !message.isBlank(),
                        "message_sha256", EvidenceLogger.sha256(String.valueOf(message)),
                        "message_logged", false));
                activity.runOnUiThread(() -> handleImageError(code, message));
            }
        };
        try {
            link.setCXRImageCbk(imageStreamCallback);
            returned = true;
            imageCallbackRegistrationElapsedMs = SystemClock.elapsedRealtime();
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        imageCallbackRegistered = returned;
        logger.event("image_callback_registration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_phase", "PRE_CONNECT",
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "callback_identity_hash", System.identityHashCode(imageStreamCallback),
                "strong_reference_held", imageStreamCallback != null,
                "callback_profile", callbackProfile,
                "audio_callback_registered", false,
                "media_request_issued", false));
        if (!returned) finish("IMAGE_CALLBACK_REGISTRATION_FAILED", false);
    }
    private boolean maybeReregisterImageCallbackAfterServiceStatus() {
        boolean requested = callbackProfile.equals("POSTCONNECT_REREGISTER")
                || callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC");
        if (!requested) {
            logger.event("image_callback_reregistration_skipped", EvidenceLogger.details(
                    "profile", callbackProfile,
                    "reason", "PROFILE_PRECONNECT_ONLY",
                    "strong_reference_held", imageStreamCallback != null,
                    "media_request_issued", photoRequestIssued.get()));
            return true;
        }
        boolean returned = false;
        String errorClass = "";
        int identityBefore = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        try {
            if (imageStreamCallback == null) throw new IllegalStateException("image callback strong reference missing");
            link.setCXRImageCbk(imageStreamCallback);
            returned = true;
            imageCallbackRegistrationElapsedMs = SystemClock.elapsedRealtime();
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        int identityAfter = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        logger.event("image_callback_reregistration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_phase", "POST_SERVICE_STATUS",
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "callback_identity_before", identityBefore,
                "callback_identity_after", identityAfter,
                "same_callback_identity", identityBefore >= 0 && identityBefore == identityAfter,
                "strong_reference_held", imageStreamCallback != null,
                "callback_profile", callbackProfile,
                "media_request_issued", photoRequestIssued.get()));
        return returned;
    }
'''
    text = replace_once(text, old_register, new_register, "Controller callback registration implementation")

    text = replace_once(
        text,
        "        if (!success) {\n"
        "            finish(\"SERVICE_STATUS_QUERY_FAILED\", false);\n"
        "            return;\n"
        "        }\n"
        "        handler.removeCallbacksAndMessages(null);",
        "        if (!success) {\n"
        "            finish(\"SERVICE_STATUS_QUERY_FAILED\", false);\n"
        "            return;\n"
        "        }\n"
        "        if (!maybeReregisterImageCallbackAfterServiceStatus()) {\n"
        "            finish(\"IMAGE_CALLBACK_REREGISTRATION_FAILED\", false);\n"
        "            return;\n"
        "        }\n"
        "        handler.removeCallbacksAndMessages(null);",
        "Controller post-connect re-registration gate",
    )

    old_take = '''        photoRequestCount++;
        photoRequestElapsedMs = SystemClock.elapsedRealtime();
        boolean returned = false;
        String errorClass = "";
        try {
            returned = link.takePhoto(
                    Test20R32Contract.PHOTO_ARG_1,
                    Test20R32Contract.PHOTO_ARG_2,
                    Test20R32Contract.PHOTO_ARG_3);
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        logger.event("photo_request_result", EvidenceLogger.details(
                "method", "takePhoto(III)Z",
                "request_count", photoRequestCount,
                "arg_1", Test20R32Contract.PHOTO_ARG_1,
                "arg_2", Test20R32Contract.PHOTO_ARG_2,
                "arg_3", Test20R32Contract.PHOTO_ARG_3,
                "argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "returned", returned,
                "error_class", errorClass,
                "payload_persistence_enabled", false,
                "payload_preview_enabled", false));
'''
    new_take = '''        photoRequestCount++;
        photoRequestElapsedMs = SystemClock.elapsedRealtime();
        int requestArg3 = callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC")
                ? 0 : Test20R32Contract.PHOTO_ARG_3;
        logCallbackPathSnapshot("PRE_TAKEPHOTO", 0L);
        boolean returned = false;
        String errorClass = "";
        try {
            returned = link.takePhoto(
                    Test20R32Contract.PHOTO_ARG_1,
                    Test20R32Contract.PHOTO_ARG_2,
                    requestArg3);
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        photoRequestReturnElapsedMs = SystemClock.elapsedRealtime();
        long returnLatencyMs = Math.max(0L, photoRequestReturnElapsedMs - photoRequestElapsedMs);
        logger.event("photo_request_result", EvidenceLogger.details(
                "method", "takePhoto(III)Z",
                "request_count", photoRequestCount,
                "callback_profile", callbackProfile,
                "arg_1", Test20R32Contract.PHOTO_ARG_1,
                "arg_2", Test20R32Contract.PHOTO_ARG_2,
                "arg_3", requestArg3,
                "argument_semantics", requestArg3 == 0
                        ? "DIAGNOSTIC_THIRD_ARGUMENT_ZERO_SEMANTICS_NOT_ASSUMED"
                        : Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "returned", returned,
                "return_latency_ms", returnLatencyMs,
                "error_class", errorClass,
                "callback_strong_reference_present", imageStreamCallback != null,
                "callback_identity_hash", imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback),
                "payload_persistence_enabled", false,
                "payload_preview_enabled", false));
        logCallbackPathSnapshot("POST_TAKEPHOTO_RETURN", 0L);
'''
    text = replace_once(text, old_take, new_take, "Controller takePhoto instrumentation")

    text = replace_once(
        text,
        "        handler.postDelayed(() -> {\n"
        "            if (!terminal.get() && !firstImageAccepted) finish(\"PHOTO_CALLBACK_TIMEOUT\", false);\n"
        "        }, Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS);",
        "        schedulePostPhotoWatchdogs();\n"
        "        handler.postDelayed(() -> {\n"
        "            if (!terminal.get() && !firstImageAccepted) {\n"
        "                logCallbackPathSnapshot(\"PHOTO_CALLBACK_TIMEOUT\", Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS);\n"
        "                finish(\"PHOTO_CALLBACK_TIMEOUT\", false);\n"
        "            }\n"
        "        }, Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS);",
        "Controller timeout instrumentation",
    )

    text = replace_once(
        text,
        "    private ImageObservation inspectImage(byte[] payload) {",
        '''    private void schedulePostPhotoWatchdogs() {
        for (long delayMs : Test20R32Contract.R3_3_WATCHDOG_DELAYS_MS) {
            final long checkpointMs = delayMs;
            handler.postDelayed(() -> {
                if (!terminal.get() && !firstImageAccepted) {
                    logCallbackPathSnapshot("POST_TAKEPHOTO_WATCHDOG", checkpointMs);
                }
            }, delayMs);
        }
    }
    private void logCallbackPathSnapshot(String phase, long checkpointMs) {
        Boolean sdkBt = null;
        String btError = "";
        String serviceVersion = null;
        String serviceError = "";
        if (link != null) {
            try { sdkBt = link.isGlassBtConnected(); }
            catch (Throwable error) { btError = error.getClass().getName(); }
            try { serviceVersion = link.getServiceVersion(); }
            catch (Throwable error) { serviceError = error.getClass().getName(); }
        }
        long now = SystemClock.elapsedRealtime();
        long sinceRequestMs = photoRequestElapsedMs < 0L ? -1L : Math.max(0L, now - photoRequestElapsedMs);
        long sinceRegistrationMs = imageCallbackRegistrationElapsedMs < 0L
                ? -1L : Math.max(0L, now - imageCallbackRegistrationElapsedMs);
        logger.event("callback_path_snapshot", EvidenceLogger.details(
                "phase", phase,
                "checkpoint_ms", checkpointMs,
                "callback_profile", callbackProfile,
                "photo_request_count", photoRequestCount,
                "photo_request_issued", photoRequestIssued.get(),
                "since_photo_request_ms", sinceRequestMs,
                "since_callback_registration_ms", sinceRegistrationMs,
                "cxrl_connected", cxrlConnected,
                "glass_bt_connected", glassBtConnected,
                "sdk_glass_bt_query_returned", btError.isEmpty(),
                "sdk_glass_bt_connected", sdkBt == null ? "unknown" : sdkBt,
                "sdk_glass_bt_error_class", btError,
                "service_version_query_returned", serviceError.isEmpty(),
                "service_version_present", serviceVersion != null && !serviceVersion.isBlank(),
                "service_version_error_class", serviceError,
                "callback_registered", imageCallbackRegistered,
                "callback_strong_reference_present", imageStreamCallback != null,
                "callback_identity_hash", imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback),
                "image_payload_callback_count", imagePayloadCallbackCount,
                "image_error_callback_count", imageErrorCallbackCount,
                "terminal", terminal.get(),
                "audio_operation", "NONE",
                "media_request_count", photoRequestCount));
    }
    private ImageObservation inspectImage(byte[] payload) {''',
        "Controller watchdog methods",
    )

    text = replace_once(
        text,
        "                \"first_image_accepted\", firstImageAccepted));",
        "                \"first_image_accepted\", firstImageAccepted,\n"
        "                \"callback_profile\", callbackProfile,\n"
        "                \"callback_strong_reference_present\", imageStreamCallback != null,\n"
        "                \"callback_identity_hash\", imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback)));",
        "Controller terminal callback evidence",
    )
    return text


def patch_gradle(text: str) -> str:
    if f'versionName = "{NEW_VERSION}"' in text:
        return text
    if 'versionName = "1.0-test20-r3.2.1.3"' not in text:
        raise PatchError("build.gradle.kts is not at the r3.2.1.3 baseline")
    text = replace_once(text, "        versionCode = 2\n", "        versionCode = 3\n", "Gradle versionCode")
    text = replace_once(
        text,
        '        versionName = "1.0-test20-r3.2.1.3"\n',
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
    parser = argparse.ArgumentParser(description="Apply bounded Test 20 r3.3 callback closure instrumentation.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--backup-dir")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").is_dir():
        print(f"ERROR: not a git repository: {repo}", file=sys.stderr)
        return 2

    paths = [repo / MAIN_REL, repo / CONTROLLER_REL, repo / CONTRACT_REL, repo / GRADLE_REL]
    for path in paths:
        if not path.is_file():
            print(f"ERROR: required Test 20 source path missing: {path}", file=sys.stderr)
            return 1

    originals = {path: path.read_text(encoding="utf-8") for path in paths}
    try:
        updated = {
            repo / MAIN_REL: patch_main(originals[repo / MAIN_REL]),
            repo / CONTROLLER_REL: patch_controller(originals[repo / CONTROLLER_REL]),
            repo / CONTRACT_REL: patch_contract(originals[repo / CONTRACT_REL]),
            repo / GRADLE_REL: patch_gradle(originals[repo / GRADLE_REL]),
        }
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("REPOSITORY_MUTATION=NONE", file=sys.stderr)
        return 1

    changed = [path for path in paths if updated[path] != originals[path]]
    if args.check_only:
        print("TEST20_R3_3_APK_SOURCE_PATCH_PREFLIGHT=PASS")
        print(f"FILES_REQUIRING_PATCH={len(changed)}")
        print("ONE_SHOT_BASELINE_REQUIRED=r3.2.1.3")
        return 0
    if not changed:
        print("TEST20_R3_3_APK_SOURCE_PATCH=ALREADY_APPLIED")
        return 0

    backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else repo / ".git" / "test20-r3.3-backup"
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
        print(f"ERROR: write failed and known files were restored: {exc}", file=sys.stderr)
        return 1

    print("TEST20_R3_3_APK_SOURCE_PATCH=PASS")
    print(f"FILES_PATCHED={len(changed)}")
    print(f"BACKUP_DIR={backup_dir}")
    print("PROFILE_1=STRONG_REF_PRECONNECT")
    print("PROFILE_2=POSTCONNECT_REREGISTER")
    print("PROFILE_3=ARG3_ZERO_DIAGNOSTIC")
    print("MAX_PHOTO_REQUEST_COUNT_PER_RUN=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
