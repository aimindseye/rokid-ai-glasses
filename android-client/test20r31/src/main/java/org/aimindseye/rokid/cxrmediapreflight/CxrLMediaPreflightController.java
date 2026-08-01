package org.aimindseye.rokid.cxrmediapreflight;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Handler;
import android.os.Looper;

import com.rokid.cxr.link.CXRLink;
import com.rokid.cxr.link.callbacks.IAudioStreamCbk;
import com.rokid.cxr.link.callbacks.ICXRLinkCbk;
import com.rokid.cxr.link.callbacks.IImageStreamCbk;
import com.rokid.cxr.link.utils.CxrDefs;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

final class CxrLMediaPreflightController {
    interface Callback {
        void onStatus(String status);
        void onObservationArmed(long durationMs);
        void onTerminal(String outcome, boolean success);
    }

    private final Activity activity;
    private final EvidenceLogger logger;
    private final Callback callback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean started = new AtomicBoolean(false);
    private final AtomicBoolean terminal = new AtomicBoolean(false);
    private final AtomicBoolean disconnectStarted = new AtomicBoolean(false);

    private CXRLink link;
    private ServiceConnection manualConnection;
    private boolean manualBound;
    private boolean cxrlConnected;
    private boolean glassBtConnected;
    private boolean callbackRegistrationCompleted;
    private boolean statusQueriesCompleted;
    private boolean observationArmed;
    private int imagePayloadCallbacks;
    private int imageErrorCallbacks;
    private int audioPayloadCallbacks;
    private int audioErrorCallbacks;
    private int audioStateTrueCallbacks;
    private int audioStateFalseCallbacks;

    CxrLMediaPreflightController(Activity activity, EvidenceLogger logger, Callback callback) {
        this.activity = activity;
        this.logger = logger;
        this.callback = callback;
    }

    boolean start(String token) {
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
                "single_attempt_enforced", true,
                "token_present", true,
                "token_value_logged", false,
                "connection_timeout_ms", Test20R31Contract.CONNECTION_TIMEOUT_MS,
                "observation_ms", Test20R31Contract.NO_PAYLOAD_OBSERVATION_MS,
                "callback_registration_enabled", true,
                "take_photo_invocation_enabled", false,
                "audio_stream_invocation_enabled", false,
                "media_payload_retention_enabled", false,
                "cloud_api_client_present", false));
        callback.onStatus("Configuring one CXR-L CUSTOMAPP no-payload preflight...");

        try {
            link = new CXRLink(activity.getApplicationContext());
            registerCallbacks();
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
            }, Test20R31Contract.MANUAL_BIND_DELAY_MS);
            handler.postDelayed(() -> {
                if (!terminal.get() && !observationArmed) finish("CONNECTION_OR_STATUS_TIMEOUT", false);
            }, Test20R31Contract.CONNECTION_TIMEOUT_MS);
            return true;
        } catch (Throwable error) {
            logger.event("connection_exception", EvidenceLogger.details(
                    "error_class", error.getClass().getName(),
                    "message_sha256", EvidenceLogger.sha256(String.valueOf(error.getMessage()))));
            finish("CONNECTION_EXCEPTION", false);
            return false;
        }
    }

    private void registerCallbacks() {
        boolean imageReturned = false;
        boolean audioReturned = false;
        String imageError = "";
        String audioError = "";
        try {
            link.setCXRImageCbk(new IImageStreamCbk() {
                @Override public void onImageReceived(byte[] payload) {
                    activity.runOnUiThread(() -> handleImagePayload(payload));
                }
                @Override public void onImageError(int code, String message) {
                    activity.runOnUiThread(() -> handleImageError(code, message));
                }
            });
            imageReturned = true;
        } catch (Throwable error) {
            imageError = error.getClass().getName();
        }
        try {
            link.setCXRAudioCbk(new IAudioStreamCbk() {
                @Override public void onAudioReceived(byte[] payload, int first, int second) {
                    activity.runOnUiThread(() -> handleAudioPayload(payload, first, second));
                }
                @Override public void onAudioError(int code, String message) {
                    activity.runOnUiThread(() -> handleAudioError(code, message));
                }
                @Override public void onAudioStreamStateChanged(boolean streaming) {
                    activity.runOnUiThread(() -> handleAudioState(streaming));
                }
            });
            audioReturned = true;
        } catch (Throwable error) {
            audioError = error.getClass().getName();
        }
        callbackRegistrationCompleted = imageReturned && audioReturned;
        logger.event("callback_registration_result", EvidenceLogger.details(
                "image_registration_method", "setCXRImageCbk(IImageStreamCbk)V",
                "image_registration_returned", imageReturned,
                "image_registration_error_class", imageError,
                "audio_registration_method", "setCXRAudioCbk(IAudioStreamCbk)V",
                "audio_registration_returned", audioReturned,
                "audio_registration_error_class", audioError,
                "registration_scope", "callback_interface_only",
                "media_request_issued", false));
        if (!callbackRegistrationCompleted) {
            finish("CALLBACK_REGISTRATION_FAILED", false);
        }
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
            Intent intent = new Intent(Test20R31Contract.MEDIA_SERVICE_ACTION)
                    .setPackage(Test20R31Contract.GLOBAL_HI_ROKID_PACKAGE)
                    .putExtra(Test20R31Contract.AUTH_TOKEN_EXTRA, token)
                    .putExtra(Test20R31Contract.AUTH_PACKAGE_EXTRA, activity.getPackageName());
            boolean startedBinding = activity.getApplicationContext().bindService(
                    intent, manualConnection, Context.BIND_AUTO_CREATE);
            manualBound = startedBinding;
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", startedBinding,
                    "action", Test20R31Contract.MEDIA_SERVICE_ACTION,
                    "package", Test20R31Contract.GLOBAL_HI_ROKID_PACKAGE,
                    "auth_token_present", true,
                    "auth_token_value_logged", false,
                    "media_request_issued", false));
            if (!startedBinding) finish("SERVICE_BIND_FAILED", false);
        } catch (Throwable error) {
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", false,
                    "error_class", error.getClass().getName(),
                    "auth_token_value_logged", false,
                    "media_request_issued", false));
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
        if (!connected && observationArmed && !terminal.get()) {
            finish("CXR_L_DISCONNECTED_DURING_OBSERVATION", false);
            return;
        }
        maybeRunStatusQueries();
    }

    private void handleGlassBluetoothCallback(boolean connected) {
        glassBtConnected = connected;
        logger.event("callback_glass_bt_connected", EvidenceLogger.details("connected", connected));
        if (!connected && observationArmed && !terminal.get()) {
            finish("GLASS_BLUETOOTH_DISCONNECTED_DURING_OBSERVATION", false);
            return;
        }
        maybeRunStatusQueries();
    }

    private void maybeRunStatusQueries() {
        if (!cxrlConnected || !glassBtConnected || !callbackRegistrationCompleted
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
                "media_request_issued", false));
        if (!success) {
            finish("SERVICE_STATUS_QUERY_FAILED", false);
            return;
        }
        armNoPayloadObservation();
    }

    private void armNoPayloadObservation() {
        observationArmed = true;
        handler.removeCallbacksAndMessages(null);
        logger.event("no_payload_observation_armed", EvidenceLogger.details(
                "observation_ms", Test20R31Contract.NO_PAYLOAD_OBSERVATION_MS,
                "image_callback_registered", true,
                "audio_callback_registered", true,
                "take_photo_invoked", false,
                "start_audio_stream_invoked", false,
                "stop_audio_stream_invoked", false,
                "operator_media_action_required", false));
        callback.onObservationArmed(Test20R31Contract.NO_PAYLOAD_OBSERVATION_MS);
        handler.postDelayed(this::completeQuietWindow, Test20R31Contract.NO_PAYLOAD_OBSERVATION_MS);
    }

    private void completeQuietWindow() {
        if (terminal.get()) return;
        boolean quiet = imagePayloadCallbacks == 0 && imageErrorCallbacks == 0
                && audioPayloadCallbacks == 0 && audioErrorCallbacks == 0
                && audioStateTrueCallbacks == 0;
        finish(quiet ? "NO_PAYLOAD_OBSERVATION_COMPLETE" : "UNEXPECTED_MEDIA_CALLBACK", quiet);
    }

    private void handleImagePayload(byte[] payload) {
        imagePayloadCallbacks++;
        logger.event("unexpected_image_payload_callback", EvidenceLogger.details(
                "payload_present", payload != null,
                "payload_length", payload == null ? -1 : payload.length,
                "payload_bytes_logged", false,
                "callback_count", imagePayloadCallbacks));
        finish("UNEXPECTED_IMAGE_PAYLOAD_CALLBACK", false);
    }

    private void handleImageError(int code, String message) {
        imageErrorCallbacks++;
        logger.event("unexpected_image_error_callback", EvidenceLogger.details(
                "error_code", code,
                "message_present", message != null && !message.isBlank(),
                "message_sha256", EvidenceLogger.sha256(String.valueOf(message)),
                "callback_count", imageErrorCallbacks));
        finish("UNEXPECTED_IMAGE_ERROR_CALLBACK", false);
    }

    private void handleAudioPayload(byte[] payload, int first, int second) {
        audioPayloadCallbacks++;
        logger.event("unexpected_audio_payload_callback", EvidenceLogger.details(
                "payload_present", payload != null,
                "payload_length", payload == null ? -1 : payload.length,
                "payload_bytes_logged", false,
                "metadata_first", first,
                "metadata_second", second,
                "callback_count", audioPayloadCallbacks));
        finish("UNEXPECTED_AUDIO_PAYLOAD_CALLBACK", false);
    }

    private void handleAudioError(int code, String message) {
        audioErrorCallbacks++;
        logger.event("unexpected_audio_error_callback", EvidenceLogger.details(
                "error_code", code,
                "message_present", message != null && !message.isBlank(),
                "message_sha256", EvidenceLogger.sha256(String.valueOf(message)),
                "callback_count", audioErrorCallbacks));
        finish("UNEXPECTED_AUDIO_ERROR_CALLBACK", false);
    }

    private void handleAudioState(boolean streaming) {
        if (streaming) audioStateTrueCallbacks++; else audioStateFalseCallbacks++;
        logger.event("audio_stream_state_callback", EvidenceLogger.details(
                "streaming", streaming,
                "true_count", audioStateTrueCallbacks,
                "false_count", audioStateFalseCallbacks,
                "audio_stream_requested", false));
        if (streaming) finish("UNEXPECTED_AUDIO_STREAM_ACTIVE", false);
    }

    private void finish(String outcome, boolean success) {
        if (!terminal.compareAndSet(false, true)) return;
        handler.removeCallbacksAndMessages(null);
        logger.event("qualification_terminal", EvidenceLogger.details(
                "outcome", outcome,
                "success", success,
                "cxrl_connected", cxrlConnected,
                "glass_bt_connected", glassBtConnected,
                "callback_registration_completed", callbackRegistrationCompleted,
                "status_queries_completed", statusQueriesCompleted,
                "observation_armed", observationArmed,
                "image_payload_callback_count", imagePayloadCallbacks,
                "image_error_callback_count", imageErrorCallbacks,
                "audio_payload_callback_count", audioPayloadCallbacks,
                "audio_error_callback_count", audioErrorCallbacks,
                "audio_state_true_callback_count", audioStateTrueCallbacks,
                "audio_state_false_callback_count", audioStateFalseCallbacks));
        callback.onTerminal(outcome, success);
        handler.postDelayed(() -> {
            disconnect("automatic_terminal_cleanup");
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", outcome,
                    "terminal_success", success,
                    "test_app_cloud_request", "NONE",
                    "take_photo_invocation", "NONE",
                    "start_audio_stream_invocation", "NONE",
                    "stop_audio_stream_invocation", "NONE",
                    "image_payload_retention", "NONE",
                    "audio_payload_retention", "NONE"));
        }, Test20R31Contract.AUTO_DISCONNECT_DELAY_MS);
    }
}
