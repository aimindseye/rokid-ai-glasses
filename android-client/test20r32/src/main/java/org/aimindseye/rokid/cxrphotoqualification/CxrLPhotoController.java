package org.aimindseye.rokid.cxrphotoqualification;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import com.rokid.cxr.link.CXRLink;
import com.rokid.cxr.link.callbacks.ICXRLinkCbk;
import com.rokid.cxr.link.callbacks.IImageStreamCbk;
import com.rokid.cxr.link.utils.CxrDefs;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

final class CxrLPhotoController {
    interface Callback {
        void onStatus(String status);
        void onPhotoReady();
        void onPhotoRequestIssued();
        void onTerminal(String outcome, boolean success);
    }

    private final Activity activity;
    private final EvidenceLogger logger;
    private final Callback callback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean started = new AtomicBoolean(false);
    private final AtomicBoolean photoRequestIssued = new AtomicBoolean(false);
    private final AtomicBoolean hostArmGranted = new AtomicBoolean(false);
    private final AtomicBoolean hostArmConsumed = new AtomicBoolean(false);
    private final AtomicBoolean terminal = new AtomicBoolean(false);
    private final AtomicBoolean disconnectStarted = new AtomicBoolean(false);

    private CXRLink link;
    private ServiceConnection manualConnection;
    private boolean manualBound;
    private boolean cxrlConnected;
    private boolean glassBtConnected;
    private boolean imageCallbackRegistered;
    private boolean statusQueriesCompleted;
    private boolean photoReady;
    private boolean firstImageAccepted;
    private IImageStreamCbk imageStreamCallback;
    private long imageCallbackRegistrationElapsedMs = -1L;
    private long photoRequestReturnElapsedMs = -1L;
    private int photoRequestCount;
    private int imagePayloadCallbackCount;
    private int imageErrorCallbackCount;
    private long photoRequestElapsedMs = -1L;

    CxrLPhotoController(Activity activity, EvidenceLogger logger, Callback callback) {
        this.activity = activity;
        this.logger = logger;
        this.callback = callback;
    }

    boolean startConnection(String token) {
        if (token == null || token.isBlank()) {
            finish("AUTHORIZATION_TOKEN_MISSING", false);
            return false;
        }
        if (!started.compareAndSet(false, true)) {
            logger.event("connection_attempt_rejected", EvidenceLogger.details(
                    "reason", "single_attempt_already_started"));
            return false;
        }

        logger.event("connection_attempt_started", EvidenceLogger.details(
                "single_connection_attempt_enforced", true,
                "max_photo_request_count", 1,
                "token_present", true,
                "token_value_logged", false,
                "connection_timeout_ms", Test20R32Contract.CONNECTION_TIMEOUT_MS,
                "photo_callback_timeout_ms", Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS,
                "duplicate_callback_window_ms", Test20R32Contract.DUPLICATE_CALLBACK_WINDOW_MS,
                "photo_arg_1", Test20R32Contract.PHOTO_ARG_1,
                "photo_arg_2", Test20R32Contract.PHOTO_ARG_2,
                "photo_arg_3", Test20R32Contract.PHOTO_ARG_3,
                "photo_argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "image_payload_persistence_enabled", false,
                "image_preview_enabled", false,
                "audio_stream_invocation_enabled", false,
                "cloud_api_client_present", false,
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "callback_strong_reference_enabled", true));
        callback.onStatus("Configuring one CXR-L CUSTOMAPP photo connection...");

        try {
            link = new CXRLink(activity.getApplicationContext());
            registerImageCallback();
            link.setCXRLinkCbk(new ICXRLinkCbk() {
                @Override public void onCXRLConnected(boolean connected) {
                    activity.runOnUiThread(() -> handleCxrLinkCallback(connected));
                }
                @Override public void onGlassBtConnected(boolean connected) {
                    activity.runOnUiThread(() -> handleGlassBluetoothCallback(connected));
                }
                @Override public void onGlassAiAssistStart() {
                    logger.event("unexpected_ai_assist_callback", EvidenceLogger.details("phase", "start"));
                }
                @Override public void onGlassAiAssistStop() {
                    logger.event("unexpected_ai_assist_callback", EvidenceLogger.details("phase", "stop"));
                }
            });

            boolean configured = link.configCXRSession(new CxrDefs.CXRSession(
                    CxrDefs.CXRSessionType.CUSTOMAPP, activity.getPackageName()));
            logger.event("session_config_result", EvidenceLogger.details(
                    "configured", configured,
                    "session_type", "CUSTOMAPP",
                    "custom_app_package", activity.getPackageName()));
            if (!configured) {
                finish("SESSION_CONFIGURATION_FAILED", false);
                return false;
            }

            invokeSdkConnect(token);
            handler.postDelayed(() -> {
                if (!terminal.get() && !cxrlConnected) bindServiceFallback(token, "delayed_fallback");
            }, Test20R32Contract.MANUAL_BIND_DELAY_MS);
            handler.postDelayed(() -> {
                if (!terminal.get() && !photoReady) finish("CONNECTION_OR_STATUS_TIMEOUT", false);
            }, Test20R32Contract.CONNECTION_TIMEOUT_MS);
            return true;
        } catch (Throwable error) {
            logger.event("connection_exception", EvidenceLogger.details(
                    "error_class", error.getClass().getName(),
                    "message_sha256", EvidenceLogger.sha256(String.valueOf(error.getMessage()))));
            finish("CONNECTION_EXCEPTION", false);
            return false;
        }
    }

    boolean grantHostArm() {
        boolean eligible = photoReady && !terminal.get() && link != null
                && !photoRequestIssued.get() && !hostArmConsumed.get();
        if (!eligible) {
            logger.event("operator_gate_arm_result", EvidenceLogger.details(
                    "granted", false,
                    "disposition", "NOT_ELIGIBLE",
                    "photo_ready", photoReady,
                    "terminal", terminal.get(),
                    "photo_request_issued", photoRequestIssued.get(),
                    "host_arm_consumed", hostArmConsumed.get(),
                    "host_arm_available", hostArmGranted.get()));
            return false;
        }
        if (hostArmGranted.get()) {
            logger.event("operator_gate_arm_result", EvidenceLogger.details(
                    "granted", true,
                    "disposition", "ALREADY_ARMED",
                    "photo_ready", true,
                    "photo_request_issued", false,
                    "host_arm_available", true));
            return true;
        }
        boolean granted = hostArmGranted.compareAndSet(false, true);
        logger.event("operator_gate_arm_result", EvidenceLogger.details(
                "granted", granted,
                "disposition", granted ? "ARMED" : "RACE_REJECTED",
                "photo_ready", photoReady,
                "photo_request_issued", photoRequestIssued.get(),
                "host_arm_available", hostArmGranted.get()));
        return granted;
    }
    boolean requestOnePhoto() {
        if (!photoReady || terminal.get() || link == null) {
            logger.event("photo_request_rejected", EvidenceLogger.details(
                    "reason", "not_ready_or_terminal",
                    "photo_ready", photoReady,
                    "terminal", terminal.get()));
            return false;
        }
        if (!hostArmGranted.compareAndSet(true, false)) {
            logger.event("photo_request_rejected", EvidenceLogger.details(
                    "reason", "host_arm_not_granted_or_already_consumed",
                    "host_arm_consumed", hostArmConsumed.get(),
                    "request_count", photoRequestCount));
            return false;
        }
        hostArmConsumed.set(true);
        if (!photoRequestIssued.compareAndSet(false, true)) {
            logger.event("photo_request_rejected", EvidenceLogger.details(
                    "reason", "single_request_already_issued",
                    "request_count", photoRequestCount));
            return false;
        }

        photoRequestCount++;
        photoRequestElapsedMs = SystemClock.elapsedRealtime();
        int requestArg3 = Test20R32Contract.PHOTO_ARG_3;
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
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "arg_1", Test20R32Contract.PHOTO_ARG_1,
                "arg_2", Test20R32Contract.PHOTO_ARG_2,
                "arg_3", requestArg3,
                "argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "returned", returned,
                "return_latency_ms", returnLatencyMs,
                "error_class", errorClass,
                "callback_strong_reference_present", imageStreamCallback != null,
                "callback_identity_hash", imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback),
                "payload_persistence_enabled", false,
                "payload_preview_enabled", false));
        logCallbackPathSnapshot("POST_TAKEPHOTO_RETURN", 0L);
        callback.onPhotoRequestIssued();
        if (!returned) {
            finish(errorClass.isEmpty() ? "PHOTO_REQUEST_RETURNED_FALSE" : "PHOTO_REQUEST_EXCEPTION", false);
            return false;
        }
        schedulePostPhotoWatchdogs();
        handler.postDelayed(() -> {
            if (!terminal.get() && !firstImageAccepted) {
                logCallbackPathSnapshot("PHOTO_CALLBACK_TIMEOUT", Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS);
                finish("PHOTO_CALLBACK_TIMEOUT", false);
            }
        }, Test20R32Contract.PHOTO_CALLBACK_TIMEOUT_MS);
        return true;
    }

    private void registerImageCallback() {
        boolean returned = false;
        String errorClass = "";
        imageStreamCallback = new IImageStreamCbk() {
            @Override public void onImageReceived(byte[] payload) {
                logger.event("image_callback_dispatch", EvidenceLogger.details(
                        "kind", "PAYLOAD",
                        "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
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
                        "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
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
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "audio_callback_registered", false,
                "media_request_issued", false));
        if (!returned) finish("IMAGE_CALLBACK_REGISTRATION_FAILED", false);
    }
    private boolean reregisterImageCallbackAfterServiceStatus() {
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
        boolean sameIdentity = identityBefore >= 0 && identityBefore == identityAfter;
        imageCallbackRegistered = returned && sameIdentity;
        logger.event("canonical_image_callback_reregistration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_phase", "POST_SERVICE_STATUS",
                "canonical_requirement", true,
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "callback_identity_before", identityBefore,
                "callback_identity_after", identityAfter,
                "same_callback_identity", sameIdentity,
                "strong_reference_held", imageStreamCallback != null,
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "media_request_issued", photoRequestIssued.get()));
        return imageCallbackRegistered;
    }

    void disconnect(String reason) {
        handler.removeCallbacksAndMessages(null);
        if (!disconnectStarted.compareAndSet(false, true)) return;
        boolean manualBindStarted = manualBound && manualConnection != null;
        boolean sdkAttempted = link != null;
        boolean sdkReturned = false;
        String sdkError = "";
        if (sdkAttempted) {
            try { link.disconnect(); sdkReturned = true; }
            catch (Throwable error) { sdkError = error.getClass().getName(); }
        }
        boolean unbindAttempted = false;
        boolean unbindReturned = false;
        String unbindError = "";
        String disposition;
        if (!manualBindStarted) disposition = "NOT_BOUND";
        else if (sdkReturned) disposition = "SKIPPED_SDK_DISCONNECT_SUCCEEDED";
        else {
            unbindAttempted = true;
            try {
                activity.getApplicationContext().unbindService(manualConnection);
                unbindReturned = true;
                disposition = "UNBOUND_AFTER_SDK_NOT_COMPLETED";
            } catch (Throwable error) {
                unbindError = error.getClass().getName();
                disposition = "UNBIND_FAILED_AFTER_SDK_NOT_COMPLETED";
            }
        }
        manualBound = false;
        manualConnection = null;
        link = null;
        logger.event("disconnect_result", EvidenceLogger.details(
                "reason", reason,
                "sdk_disconnect_attempted", sdkAttempted,
                "sdk_disconnect_returned", sdkReturned,
                "sdk_disconnect_error_class", sdkError,
                "manual_bind_started", manualBindStarted,
                "manual_unbind_attempted", unbindAttempted,
                "manual_unbind_disposition", disposition,
                "manual_unbind_returned", unbindReturned,
                "manual_unbind_error_class", unbindError));
    }

    private void invokeSdkConnect(String token) {
        boolean methodFound = false;
        Boolean returned = null;
        String errorClass = "";
        try {
            Method method = link.getClass().getMethod("connect", String.class);
            methodFound = true;
            Object value = method.invoke(link, token);
            if (value instanceof Boolean) returned = (Boolean) value;
        } catch (Throwable error) { errorClass = error.getClass().getName(); }
        logger.event("sdk_connect_invoked", EvidenceLogger.details(
                "method_found", methodFound,
                "returned_boolean", returned != null,
                "return_value", returned == null ? "not_returned" : returned,
                "error_class", errorClass,
                "token_value_logged", false));
        if (returned != null && !returned) bindServiceFallback(token, "sdk_connect_returned_false");
        else if (!methodFound) bindServiceFallback(token, "sdk_connect_method_missing");
    }

    private void bindServiceFallback(String token, String reason) {
        if (manualBound || terminal.get() || link == null) return;
        try {
            manualConnection = findServiceConnection(link);
            Intent intent = new Intent(Test20R32Contract.MEDIA_SERVICE_ACTION)
                    .setPackage(Test20R32Contract.GLOBAL_HI_ROKID_PACKAGE)
                    .putExtra(Test20R32Contract.AUTH_TOKEN_EXTRA, token)
                    .putExtra(Test20R32Contract.AUTH_PACKAGE_EXTRA, activity.getPackageName());
            boolean startedBinding = activity.getApplicationContext().bindService(
                    intent, manualConnection, Context.BIND_AUTO_CREATE);
            manualBound = startedBinding;
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", startedBinding,
                    "action", Test20R32Contract.MEDIA_SERVICE_ACTION,
                    "package", Test20R32Contract.GLOBAL_HI_ROKID_PACKAGE,
                    "auth_token_present", true,
                    "auth_token_value_logged", false,
                    "photo_request_issued", photoRequestIssued.get()));
            if (!startedBinding) finish("SERVICE_BIND_FAILED", false);
        } catch (Throwable error) {
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", false,
                    "error_class", error.getClass().getName(),
                    "auth_token_value_logged", false));
            finish("SERVICE_BIND_EXCEPTION", false);
        }
    }

    private static ServiceConnection findServiceConnection(CXRLink value) throws IllegalAccessException {
        Class<?> type = value.getClass();
        while (type != null) {
            for (Field field : type.getDeclaredFields()) {
                if (ServiceConnection.class.isAssignableFrom(field.getType())) {
                    field.setAccessible(true);
                    Object candidate = field.get(value);
                    if (candidate instanceof ServiceConnection) return (ServiceConnection) candidate;
                }
            }
            type = type.getSuperclass();
        }
        throw new IllegalStateException("CXR-L ServiceConnection field not found");
    }

    private void handleCxrLinkCallback(boolean connected) {
        cxrlConnected = connected;
        logger.event("callback_cxrl_connected", EvidenceLogger.details("connected", connected));
        if (!connected && photoRequestIssued.get() && !terminal.get()) {
            finish("CXR_L_DISCONNECTED_DURING_PHOTO", false);
            return;
        }
        maybePreparePhoto();
    }

    private void handleGlassBluetoothCallback(boolean connected) {
        glassBtConnected = connected;
        logger.event("callback_glass_bt_connected", EvidenceLogger.details("connected", connected));
        if (!connected && photoRequestIssued.get() && !terminal.get()) {
            finish("GLASS_BLUETOOTH_DISCONNECTED_DURING_PHOTO", false);
            return;
        }
        maybePreparePhoto();
    }

    private void maybePreparePhoto() {
        if (!cxrlConnected || !glassBtConnected || !imageCallbackRegistered
                || statusQueriesCompleted || terminal.get()) return;
        statusQueriesCompleted = true;
        String version = null;
        Integer versionCode = null;
        Boolean btStatus = null;
        String versionError = "";
        String codeError = "";
        String btError = "";
        try { version = link.getServiceVersion(); }
        catch (Throwable error) { versionError = error.getClass().getName(); }
        try { versionCode = link.getServiceVersionCode(); }
        catch (Throwable error) { codeError = error.getClass().getName(); }
        try { btStatus = link.isGlassBtConnected(); }
        catch (Throwable error) { btError = error.getClass().getName(); }
        boolean success = version != null && !version.isBlank()
                && versionCode != null && btStatus != null && btStatus;
        logger.event("service_status_result", EvidenceLogger.details(
                "service_version_query_returned", versionError.isEmpty(),
                "service_version_present", version != null && !version.isBlank(),
                "service_version", version == null ? "" : version,
                "service_version_error_class", versionError,
                "service_version_code_query_returned", codeError.isEmpty(),
                "service_version_code_present", versionCode != null,
                "service_version_code", versionCode == null ? -1 : versionCode,
                "service_version_code_error_class", codeError,
                "glass_bt_status_query_returned", btError.isEmpty(),
                "glass_bt_status", btStatus == null ? "unknown" : btStatus,
                "glass_bt_status_error_class", btError,
                "status_success", success,
                "photo_request_issued", false));
        if (!success) {
            finish("SERVICE_STATUS_QUERY_FAILED", false);
            return;
        }
        if (!reregisterImageCallbackAfterServiceStatus()) {
            finish("IMAGE_CALLBACK_REREGISTRATION_FAILED", false);
            return;
        }
        handler.removeCallbacksAndMessages(null);
        photoReady = true;
        logger.event("photo_ready", EvidenceLogger.details(
                "explicit_operator_tap_required", true,
                "max_request_count", 1,
                "arg_1", Test20R32Contract.PHOTO_ARG_1,
                "arg_2", Test20R32Contract.PHOTO_ARG_2,
                "arg_3", Test20R32Contract.PHOTO_ARG_3,
                "argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "non_sensitive_target_required", true,
                "payload_persistence_enabled", false,
                "payload_preview_enabled", false));
        callback.onPhotoReady();
    }

    private void schedulePostPhotoWatchdogs() {
        for (long delayMs : Test20R32Contract.POST_TAKEPHOTO_WATCHDOG_DELAYS_MS) {
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
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
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
    private ImageObservation inspectImage(byte[] payload) {
        int length = payload == null ? -1 : payload.length;
        String digest = payload == null ? "" : EvidenceLogger.sha256(payload);
        String format = formatHint(payload);
        int width = -1;
        int height = -1;
        String mime = "";
        if (payload != null && payload.length > 0) {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(payload, 0, payload.length, options);
            width = options.outWidth;
            height = options.outHeight;
            mime = options.outMimeType == null ? "" : options.outMimeType;
        }
        boolean valid = payload != null && payload.length > 0
                && (!format.equals("UNKNOWN") || (width > 0 && height > 0));
        long latency = photoRequestElapsedMs < 0L
                ? -1L : Math.max(0L, SystemClock.elapsedRealtime() - photoRequestElapsedMs);
        return new ImageObservation(length, digest, format, width, height, mime, latency, valid);
    }

    private static String formatHint(byte[] payload) {
        if (payload == null) return "NONE";
        if (payload.length >= 3 && (payload[0] & 0xff) == 0xff
                && (payload[1] & 0xff) == 0xd8 && (payload[2] & 0xff) == 0xff) return "JPEG";
        if (payload.length >= 8 && (payload[0] & 0xff) == 0x89
                && payload[1] == 0x50 && payload[2] == 0x4e && payload[3] == 0x47) return "PNG";
        if (payload.length >= 12 && payload[0] == 0x52 && payload[1] == 0x49
                && payload[2] == 0x46 && payload[3] == 0x46
                && payload[8] == 0x57 && payload[9] == 0x45
                && payload[10] == 0x42 && payload[11] == 0x50) return "WEBP";
        return "UNKNOWN";
    }

    private void handleImageObservation(ImageObservation observation) {
        imagePayloadCallbackCount++;
        logger.event("image_payload_received", EvidenceLogger.details(
                "callback_count", imagePayloadCallbackCount,
                "payload_present", observation.payloadLength > 0,
                "payload_length", observation.payloadLength,
                "payload_digest_sha256_private", observation.payloadDigest,
                "payload_bytes_logged", false,
                "payload_persisted", false,
                "payload_previewed", false,
                "format_hint", observation.formatHint,
                "decoded_width", observation.decodedWidth,
                "decoded_height", observation.decodedHeight,
                "decoded_mime_type", observation.decodedMimeType,
                "request_to_callback_latency_ms", observation.latencyMs,
                "valid_nonempty_image", observation.valid));
        if (!photoRequestIssued.get()) {
            finish("UNSOLICITED_IMAGE_CALLBACK", false);
            return;
        }
        if (imagePayloadCallbackCount > 1) {
            finish("DUPLICATE_IMAGE_CALLBACK", false);
            return;
        }
        if (!observation.valid) {
            finish("INVALID_OR_EMPTY_IMAGE_PAYLOAD", false);
            return;
        }
        firstImageAccepted = true;
        handler.removeCallbacksAndMessages(null);
        logger.event("duplicate_callback_window_armed", EvidenceLogger.details(
                "window_ms", Test20R32Contract.DUPLICATE_CALLBACK_WINDOW_MS,
                "accepted_callback_count", imagePayloadCallbackCount,
                "payload_persisted", false));
        handler.postDelayed(() -> {
            if (!terminal.get()) {
                boolean exact = photoRequestCount == 1 && imagePayloadCallbackCount == 1
                        && imageErrorCallbackCount == 0;
                finish(exact ? "ONE_SHOT_PHOTO_RECEIVED" : "PHOTO_CARDINALITY_FAILURE", exact);
            }
        }, Test20R32Contract.DUPLICATE_CALLBACK_WINDOW_MS);
    }

    private void handleImageError(int code, String message) {
        imageErrorCallbackCount++;
        logger.event("image_error_callback", EvidenceLogger.details(
                "callback_count", imageErrorCallbackCount,
                "error_code", code,
                "message_present", message != null && !message.isBlank(),
                "message_sha256", EvidenceLogger.sha256(String.valueOf(message)),
                "message_logged", false));
        finish("IMAGE_ERROR_CALLBACK", false);
    }

    private void finish(String outcome, boolean success) {
        if (!terminal.compareAndSet(false, true)) return;
        handler.removeCallbacksAndMessages(null);
        logger.event("qualification_terminal", EvidenceLogger.details(
                "outcome", outcome,
                "success", success,
                "cxrl_connected", cxrlConnected,
                "glass_bt_connected", glassBtConnected,
                "image_callback_registered", imageCallbackRegistered,
                "status_queries_completed", statusQueriesCompleted,
                "photo_ready", photoReady,
                "host_arm_available", hostArmGranted.get(),
                "host_arm_consumed", hostArmConsumed.get(),
                "photo_request_count", photoRequestCount,
                "image_payload_callback_count", imagePayloadCallbackCount,
                "image_error_callback_count", imageErrorCallbackCount,
                "first_image_accepted", firstImageAccepted,
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "callback_strong_reference_present", imageStreamCallback != null,
                "callback_identity_hash", imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback)));
        callback.onTerminal(outcome, success);
        handler.postDelayed(() -> {
            disconnect("automatic_terminal_cleanup");
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", outcome,
                    "terminal_success", success,
                    "test_app_cloud_request", "NONE",
                    "take_photo_request_count", photoRequestCount,
                    "start_audio_stream_invocation", "NONE",
                    "stop_audio_stream_invocation", "NONE",
                    "image_payload_persistence", "NONE",
                    "image_payload_preview", "NONE",
                    "media_upload", "NONE"));
        }, Test20R32Contract.AUTO_DISCONNECT_DELAY_MS);
    }

    private static final class ImageObservation {
        private final int payloadLength;
        private final String payloadDigest;
        private final String formatHint;
        private final int decodedWidth;
        private final int decodedHeight;
        private final String decodedMimeType;
        private final long latencyMs;
        private final boolean valid;

        private ImageObservation(int payloadLength, String payloadDigest, String formatHint,
                int decodedWidth, int decodedHeight, String decodedMimeType,
                long latencyMs, boolean valid) {
            this.payloadLength = payloadLength;
            this.payloadDigest = payloadDigest;
            this.formatHint = formatHint;
            this.decodedWidth = decodedWidth;
            this.decodedHeight = decodedHeight;
            this.decodedMimeType = decodedMimeType;
            this.latencyMs = latencyMs;
            this.valid = valid;
        }
    }
}
