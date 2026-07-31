package org.aimindseye.rokid.cxrlqualification;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Handler;
import android.os.Looper;

import com.rokid.cxr.link.CXRLink;
import com.rokid.cxr.link.callbacks.ICXRLinkCbk;
import com.rokid.cxr.link.utils.CxrDefs;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

final class CxrLSessionController {
    interface Callback {
        void onStatus(String status);
        void onTerminal(String outcome, boolean success);
    }

    private final Activity activity;
    private final EvidenceLogger logger;
    private final Callback callback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean started = new AtomicBoolean(false);
    private final AtomicBoolean terminal = new AtomicBoolean(false);

    private CXRLink link;
    private ServiceConnection manualConnection;
    private boolean manualBound;
    private boolean cxrlConnected;
    private boolean glassBtConnected;

    CxrLSessionController(Activity activity, EvidenceLogger logger, Callback callback) {
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
                "timeout_ms", Test19R2Contract.CONNECTION_TIMEOUT_MS
        ));
        callback.onStatus("Configuring one CXR-L CUSTOMAPP session...");

        try {
            link = new CXRLink(activity.getApplicationContext());
            link.setCXRLinkCbk(new ICXRLinkCbk() {
                @Override
                public void onCXRLConnected(boolean connected) {
                    activity.runOnUiThread(() -> handleCxrLinkCallback(connected));
                }

                @Override
                public void onGlassBtConnected(boolean connected) {
                    activity.runOnUiThread(() -> handleGlassBluetoothCallback(connected));
                }

                @Override
                public void onGlassAiAssistStart() {
                    logger.event("callback_ai_assist_start", EvidenceLogger.details());
                }

                @Override
                public void onGlassAiAssistStop() {
                    logger.event("callback_ai_assist_stop", EvidenceLogger.details());
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
                    bindMediaService(token, "delayed_fallback");
                }
            }, Test19R2Contract.MANUAL_BIND_DELAY_MS);
            handler.postDelayed(() -> {
                if (!terminal.get()) {
                    finish("CONNECTION_CALLBACK_TIMEOUT", false);
                }
            }, Test19R2Contract.CONNECTION_TIMEOUT_MS);
            return true;
        } catch (Throwable error) {
            logger.event("connection_exception", EvidenceLogger.details(
                    "error_class", error.getClass().getName(),
                    "message_sha256", EvidenceLogger.sha256(String.valueOf(error.getMessage()))
            ));
            finish("CONNECTION_EXCEPTION", false);
            return false;
        }
    }

    void disconnect(String reason) {
        handler.removeCallbacksAndMessages(null);
        logger.event("disconnect_invoked", EvidenceLogger.details("reason", reason));
        boolean sdkReturned = false;
        String sdkError = "";
        if (link != null) {
            try {
                link.disconnect();
                sdkReturned = true;
            } catch (Throwable error) {
                sdkError = error.getClass().getName();
            }
        }

        boolean unbindReturned = false;
        String unbindError = "";
        if (manualBound && manualConnection != null) {
            try {
                activity.getApplicationContext().unbindService(manualConnection);
                unbindReturned = true;
            } catch (Throwable error) {
                unbindError = error.getClass().getName();
            }
        }
        manualBound = false;
        manualConnection = null;
        link = null;
        logger.event("disconnect_result", EvidenceLogger.details(
                "sdk_disconnect_returned", sdkReturned,
                "sdk_disconnect_error_class", sdkError,
                "manual_unbind_required", unbindReturned || !unbindError.isEmpty(),
                "manual_unbind_returned", unbindReturned,
                "manual_unbind_error_class", unbindError
        ));
    }

    private void invokeSdkConnect(String token) {
        boolean methodFound = false;
        Boolean returned = null;
        String errorClass = "";
        try {
            Method connect = link.getClass().getMethod("connect", String.class);
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
                "return_value", returned == null ? JSONObjectNull.VALUE : returned,
                "error_class", errorClass,
                "token_value_logged", false
        ));
        if (returned != null && !returned) {
            bindMediaService(token, "sdk_connect_returned_false");
        } else if (!methodFound) {
            bindMediaService(token, "sdk_connect_method_missing");
        }
    }

    private void bindMediaService(String token, String reason) {
        if (manualBound || terminal.get() || link == null) {
            return;
        }
        try {
            manualConnection = findServiceConnection(link);
            Intent intent = new Intent(Test19R2Contract.MEDIA_SERVICE_ACTION)
                    .setPackage(Test19R2Contract.GLOBAL_HI_ROKID_PACKAGE)
                    .putExtra(Test19R2Contract.AUTH_TOKEN_EXTRA, token)
                    .putExtra(Test19R2Contract.AUTH_PACKAGE_EXTRA, activity.getPackageName());
            boolean startedBinding = activity.getApplicationContext().bindService(
                    intent,
                    manualConnection,
                    Context.BIND_AUTO_CREATE
            );
            manualBound = startedBinding;
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", startedBinding,
                    "action", Test19R2Contract.MEDIA_SERVICE_ACTION,
                    "package", Test19R2Contract.GLOBAL_HI_ROKID_PACKAGE,
                    "auth_package_present", true,
                    "auth_token_present", true,
                    "auth_token_value_logged", false
            ));
            if (!startedBinding) {
                finish("MEDIA_SERVICE_BIND_FAILED", false);
            }
        } catch (Throwable error) {
            logger.event("manual_service_bind_result", EvidenceLogger.details(
                    "reason", reason,
                    "bind_started", false,
                    "error_class", error.getClass().getName(),
                    "auth_token_value_logged", false
            ));
            finish("MEDIA_SERVICE_BIND_EXCEPTION", false);
        }
    }

    private static ServiceConnection findServiceConnection(CXRLink value) throws IllegalAccessException {
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
        throw new IllegalStateException("CXR-L ServiceConnection field not found");
    }

    private void handleCxrLinkCallback(boolean connected) {
        cxrlConnected = connected;
        logger.event("callback_cxrl_connected", EvidenceLogger.details("connected", connected));
        callback.onStatus("CXR-L service connected: " + connected);
        maybeComplete();
    }

    private void handleGlassBluetoothCallback(boolean connected) {
        glassBtConnected = connected;
        logger.event("callback_glass_bt_connected", EvidenceLogger.details("connected", connected));
        callback.onStatus("Glasses Bluetooth callback: " + connected);
        maybeComplete();
    }

    private void maybeComplete() {
        if (cxrlConnected && glassBtConnected) {
            finish("CONNECTED_BOTH_CALLBACKS", true);
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
                "glass_bt_connected", glassBtConnected
        ));
        callback.onTerminal(outcome, success);
        handler.postDelayed(() -> {
            disconnect("automatic_terminal_cleanup");
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", outcome,
                    "terminal_success", success
            ));
        }, Test19R2Contract.AUTO_DISCONNECT_DELAY_MS);
    }

    private static final class JSONObjectNull {
        private static final String VALUE = "not_returned";
        private JSONObjectNull() {}
    }
}
