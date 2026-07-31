package org.aimindseye.rokid.cxreventqualification;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import com.rokid.cxr.link.CXRLink;
import com.rokid.cxr.link.callbacks.ICXRLinkCbk;
import com.rokid.cxr.link.utils.CxrDefs;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

final class CxrLEventController {
    interface Callback {
        void onStatus(String status);
        void onObservationArmed(int requiredCycles);
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
    private boolean observationArmed;
    private boolean aiAssistActive;
    private int callbackSequence;
    private int acceptedStartCount;
    private int acceptedStopCount;
    private int completedCycleCount;
    private int duplicateStartCount;
    private int outOfOrderStopCount;
    private long activeCycleStartElapsedMs = -1L;

    CxrLEventController(
            Activity activity,
            EvidenceLogger logger,
            Callback callback
    ) {
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
                    "reason", "single_attempt_already_started"
            ));
            return false;
        }

        logger.event("connection_attempt_started", EvidenceLogger.details(
                "single_attempt_enforced", true,
                "token_present", true,
                "token_value_logged", false,
                "connection_timeout_ms", Test20R2Contract.CONNECTION_TIMEOUT_MS,
                "required_ai_assist_cycles",
                        Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES,
                "test_app_ai_assistant_invocation_enabled", false,
                "media_api_invocation_enabled", false,
                "cloud_api_client_present", false
        ));
        callback.onStatus("Configuring one CXR-L CUSTOMAPP event-observer session...");

        try {
            link = new CXRLink(activity.getApplicationContext());
            link.setCXRLinkCbk(new ICXRLinkCbk() {
                @Override
                public void onCXRLConnected(boolean connected) {
                    activity.runOnUiThread(
                            () -> handleCxrLinkCallback(connected)
                    );
                }

                @Override
                public void onGlassBtConnected(boolean connected) {
                    activity.runOnUiThread(
                            () -> handleGlassBluetoothCallback(connected)
                    );
                }

                @Override
                public void onGlassAiAssistStart() {
                    activity.runOnUiThread(
                            CxrLEventController.this::handleAiAssistStart
                    );
                }

                @Override
                public void onGlassAiAssistStop() {
                    activity.runOnUiThread(
                            CxrLEventController.this::handleAiAssistStop
                    );
                }
            });

            boolean configured = link.configCXRSession(
                    new CxrDefs.CXRSession(
                            CxrDefs.CXRSessionType.CUSTOMAPP,
                            activity.getPackageName()
                    )
            );
            logger.event("session_config_result", EvidenceLogger.details(
                    "configured", configured,
                    "session_type", "CUSTOMAPP",
                    "custom_app_package", activity.getPackageName()
            ));
            if (!configured) {
                finish("SESSION_CONFIGURATION_FAILED", false);
                return false;
            }

            invokeSdkConnect(token);
            handler.postDelayed(() -> {
                if (!terminal.get() && !cxrlConnected) {
                    bindServiceFallback(token, "delayed_fallback");
                }
            }, Test20R2Contract.MANUAL_BIND_DELAY_MS);

            handler.postDelayed(() -> {
                if (!terminal.get() && !observationArmed) {
                    finish("CONNECTION_CALLBACK_TIMEOUT", false);
                }
            }, Test20R2Contract.CONNECTION_TIMEOUT_MS);
            return true;
        } catch (Throwable error) {
            logger.event("connection_exception", EvidenceLogger.details(
                    "error_class", error.getClass().getName(),
                    "message_sha256",
                            EvidenceLogger.sha256(String.valueOf(error.getMessage()))
            ));
            finish("CONNECTION_EXCEPTION", false);
            return false;
        }
    }

    void disconnect(String reason) {
        handler.removeCallbacksAndMessages(null);
        if (!disconnectStarted.compareAndSet(false, true)) {
            logger.event("disconnect_skipped", EvidenceLogger.details(
                    "reason", reason,
                    "disposition", "ALREADY_COMPLETED"
            ));
            return;
        }

        boolean manualBindStarted =
                manualBound && manualConnection != null;
        logger.event("disconnect_invoked", EvidenceLogger.details(
                "reason", reason,
                "manual_bind_started", manualBindStarted
        ));

        boolean sdkAttempted = link != null;
        boolean sdkReturned = false;
        String sdkError = "";
        if (sdkAttempted) {
            try {
                link.disconnect();
                sdkReturned = true;
            } catch (Throwable error) {
                sdkError = error.getClass().getName();
            }
        }

        boolean unbindAttempted = false;
        boolean unbindReturned = false;
        String unbindError = "";
        String unbindDisposition;
        if (!manualBindStarted) {
            unbindDisposition = "NOT_BOUND";
        } else if (sdkReturned) {
            unbindDisposition = "SKIPPED_SDK_DISCONNECT_SUCCEEDED";
        } else {
            unbindAttempted = true;
            try {
                activity.getApplicationContext().unbindService(manualConnection);
                unbindReturned = true;
                unbindDisposition = "UNBOUND_AFTER_SDK_NOT_COMPLETED";
            } catch (Throwable error) {
                unbindError = error.getClass().getName();
                unbindDisposition =
                        "UNBIND_FAILED_AFTER_SDK_NOT_COMPLETED";
            }
        }

        manualBound = false;
        manualConnection = null;
        link = null;
        logger.event("disconnect_result", EvidenceLogger.details(
                "sdk_disconnect_attempted", sdkAttempted,
                "sdk_disconnect_returned", sdkReturned,
                "sdk_disconnect_error_class", sdkError,
                "manual_bind_started", manualBindStarted,
                "manual_unbind_required", unbindAttempted,
                "manual_unbind_attempted", unbindAttempted,
                "manual_unbind_disposition", unbindDisposition,
                "manual_unbind_returned", unbindReturned,
                "manual_unbind_error_class", unbindError
        ));
    }

    private void invokeSdkConnect(String token) {
        boolean methodFound = false;
        Boolean returned = null;
        String errorClass = "";
        try {
            Method connect = link.getClass().getMethod(
                    "connect",
                    String.class
            );
            methodFound = true;
            Object value = connect.invoke(link, token);
            if (value instanceof Boolean) {
                returned = (Boolean) value;
            }
        } catch (NoSuchMethodException error) {
            errorClass = error.getClass().getName();
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }

        logger.event("sdk_connect_invoked", EvidenceLogger.details(
                "method_found", methodFound,
                "returned_boolean", returned != null,
                "return_value",
                        returned == null ? "not_returned" : returned,
                "error_class", errorClass,
                "token_value_logged", false
        ));

        if (returned != null && !returned) {
            bindServiceFallback(token, "sdk_connect_returned_false");
        } else if (!methodFound) {
            bindServiceFallback(token, "sdk_connect_method_missing");
        }
    }

    private void bindServiceFallback(String token, String reason) {
        if (manualBound || terminal.get() || link == null) {
            return;
        }
        try {
            manualConnection = findServiceConnection(link);
            Intent intent =
                    new Intent(Test20R2Contract.MEDIA_SERVICE_ACTION)
                            .setPackage(
                                    Test20R2Contract.GLOBAL_HI_ROKID_PACKAGE
                            )
                            .putExtra(
                                    Test20R2Contract.AUTH_TOKEN_EXTRA,
                                    token
                            )
                            .putExtra(
                                    Test20R2Contract.AUTH_PACKAGE_EXTRA,
                                    activity.getPackageName()
                            );
            boolean startedBinding =
                    activity.getApplicationContext().bindService(
                            intent,
                            manualConnection,
                            Context.BIND_AUTO_CREATE
                    );
            manualBound = startedBinding;
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", startedBinding,
                    "action", Test20R2Contract.MEDIA_SERVICE_ACTION,
                    "package",
                            Test20R2Contract.GLOBAL_HI_ROKID_PACKAGE,
                    "auth_package_present", true,
                    "auth_token_present", true,
                    "auth_token_value_logged", false,
                    "media_stream_requested", false
            ));
            if (!startedBinding) {
                finish("SERVICE_BIND_FAILED", false);
            }
        } catch (Throwable error) {
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", false,
                    "error_class", error.getClass().getName(),
                    "auth_token_value_logged", false,
                    "media_stream_requested", false
            ));
            finish("SERVICE_BIND_EXCEPTION", false);
        }
    }

    private static ServiceConnection findServiceConnection(CXRLink value)
            throws IllegalAccessException {
        Class<?> type = value.getClass();
        while (type != null) {
            for (Field field : type.getDeclaredFields()) {
                if (ServiceConnection.class.isAssignableFrom(field.getType())) {
                    field.setAccessible(true);
                    Object candidate = field.get(value);
                    if (candidate instanceof ServiceConnection) {
                        return (ServiceConnection) candidate;
                    }
                }
            }
            type = type.getSuperclass();
        }
        throw new IllegalStateException(
                "CXR-L ServiceConnection field not found"
        );
    }

    private void handleCxrLinkCallback(boolean connected) {
        cxrlConnected = connected;
        logger.event("callback_cxrl_connected",
                EvidenceLogger.details("connected", connected));
        callback.onStatus("CXR-L service connected: " + connected);
        if (!connected && observationArmed && !terminal.get()) {
            finish("CXR_L_DISCONNECTED_DURING_OBSERVATION", false);
            return;
        }
        maybeArmObservation();
    }

    private void handleGlassBluetoothCallback(boolean connected) {
        glassBtConnected = connected;
        logger.event("callback_glass_bt_connected",
                EvidenceLogger.details("connected", connected));
        callback.onStatus("Glasses Bluetooth callback: " + connected);
        if (!connected && observationArmed && !terminal.get()) {
            finish("GLASS_BLUETOOTH_DISCONNECTED_DURING_OBSERVATION", false);
            return;
        }
        maybeArmObservation();
    }

    private void maybeArmObservation() {
        if (!cxrlConnected || !glassBtConnected || observationArmed
                || terminal.get()) {
            return;
        }

        observationArmed = true;
        handler.removeCallbacksAndMessages(null);
        logger.event("event_observation_armed", EvidenceLogger.details(
                "required_cycles",
                        Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES,
                "timeout_ms",
                        Test20R2Contract.EVENT_OBSERVATION_TIMEOUT_MS,
                "test_app_invokes_ai_assistant", false,
                "operator_must_not_speak_query", true,
                "operator_must_cancel_before_response", true
        ));
        callback.onObservationArmed(
                Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES
        );
        handler.postDelayed(
                this::handleObservationTimeout,
                Test20R2Contract.EVENT_OBSERVATION_TIMEOUT_MS
        );
    }

    private void handleAiAssistStart() {
        callbackSequence++;
        long now = SystemClock.elapsedRealtime();
        boolean activeBeforeCallback = aiAssistActive;
        boolean accepted =
                observationArmed && !terminal.get() && !activeBeforeCallback;
        if (accepted) {
            aiAssistActive = true;
            activeCycleStartElapsedMs = now;
            acceptedStartCount++;
        } else if (observationArmed && activeBeforeCallback) {
            duplicateStartCount++;
        }

        logger.event("callback_ai_assist_start", EvidenceLogger.details(
                "sequence", callbackSequence,
                "accepted", accepted,
                "observation_armed", observationArmed,
                "active_before_callback", activeBeforeCallback,
                "accepted_start_count", acceptedStartCount,
                "duplicate_start_count", duplicateStartCount
        ));
        callback.onStatus(
                "AI-assist start callback " + acceptedStartCount
                        + " of "
                        + Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES
                        + ". Cancel without asking a question."
        );

        if (!observationArmed && !terminal.get()) {
            finish("AI_ASSIST_START_BEFORE_OBSERVATION_ARMED", false);
        } else if (duplicateStartCount > 0) {
            finish("AI_ASSIST_DUPLICATE_START_CALLBACK", false);
        }
    }

    private void handleAiAssistStop() {
        callbackSequence++;
        long now = SystemClock.elapsedRealtime();
        boolean accepted =
                observationArmed && !terminal.get() && aiAssistActive;
        long durationMs = -1L;
        if (accepted) {
            durationMs = Math.max(0L, now - activeCycleStartElapsedMs);
            aiAssistActive = false;
            activeCycleStartElapsedMs = -1L;
            acceptedStopCount++;
            completedCycleCount++;
        } else if (observationArmed) {
            outOfOrderStopCount++;
        }

        logger.event("callback_ai_assist_stop", EvidenceLogger.details(
                "sequence", callbackSequence,
                "accepted", accepted,
                "observation_armed", observationArmed,
                "cycle_duration_ms", durationMs,
                "accepted_stop_count", acceptedStopCount,
                "completed_cycle_count", completedCycleCount,
                "out_of_order_stop_count", outOfOrderStopCount
        ));

        if (!observationArmed && !terminal.get()) {
            finish("AI_ASSIST_STOP_BEFORE_OBSERVATION_ARMED", false);
            return;
        }
        if (outOfOrderStopCount > 0) {
            finish("AI_ASSIST_STOP_WITHOUT_ORDERED_START", false);
            return;
        }

        if (completedCycleCount
                >= Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES) {
            finish("AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED", true);
            return;
        }

        callback.onStatus(
                "Ordered AI-assist cycle " + completedCycleCount
                        + " of "
                        + Test20R2Contract.REQUIRED_AI_ASSIST_CYCLES
                        + " observed. Repeat once without asking a question."
        );
    }

    private void handleObservationTimeout() {
        if (terminal.get()) {
            return;
        }
        if (aiAssistActive) {
            finish("AI_ASSIST_CALLBACK_TIMEOUT_INCOMPLETE_CYCLE", false);
        } else if (completedCycleCount == 0) {
            finish("AI_ASSIST_CALLBACK_TIMEOUT_NO_EVENTS", false);
        } else {
            finish("AI_ASSIST_CALLBACK_TIMEOUT_PARTIAL_REPEAT", false);
        }
    }

    private void finish(String outcome, boolean success) {
        if (!terminal.compareAndSet(false, true)) {
            return;
        }
        handler.removeCallbacksAndMessages(null);
        logger.event("qualification_terminal", EvidenceLogger.details(
                "outcome", outcome,
                "success", success,
                "cxrl_connected", cxrlConnected,
                "glass_bt_connected", glassBtConnected,
                "observation_armed", observationArmed,
                "accepted_start_count", acceptedStartCount,
                "accepted_stop_count", acceptedStopCount,
                "completed_cycle_count", completedCycleCount,
                "duplicate_start_count", duplicateStartCount,
                "out_of_order_stop_count", outOfOrderStopCount,
                "ai_assist_active_at_terminal", aiAssistActive
        ));
        callback.onTerminal(outcome, success);
        handler.postDelayed(() -> {
            disconnect("automatic_terminal_cleanup");
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", outcome,
                    "terminal_success", success,
                    "test_app_cloud_ai_request", "NONE",
                    "test_app_media_operation", "NONE"
            ));
        }, Test20R2Contract.AUTO_DISCONNECT_DELAY_MS);
    }
}
