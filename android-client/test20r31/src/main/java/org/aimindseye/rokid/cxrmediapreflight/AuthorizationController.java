package org.aimindseye.rokid.cxrmediapreflight;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;

import org.json.JSONObject;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

final class AuthorizationController {
    interface Callback {
        void onAuthorizationSuccess(String token);
        void onAuthorizationFailure(String outcome);
    }

    private final Activity activity;
    private final EvidenceLogger logger;
    private final Callback callback;
    private boolean requested;

    AuthorizationController(Activity activity, EvidenceLogger logger, Callback callback) {
        this.activity = activity;
        this.logger = logger;
        this.callback = callback;
    }

    void request() {
        if (requested) {
            logger.event("authorization_rejected",
                    EvidenceLogger.details("reason", "already_requested"));
            callback.onAuthorizationFailure("AUTHORIZATION_ALREADY_REQUESTED");
            return;
        }
        requested = true;
        logger.event("authorization_requested", EvidenceLogger.details(
                "request_code", Test20R31Contract.AUTH_REQUEST_CODE,
                "token_value_logged", false
        ));

        Intent explicit = new Intent().setComponent(new ComponentName(
                Test20R31Contract.GLOBAL_HI_ROKID_PACKAGE,
                Test20R31Contract.AUTH_ACTIVITY_CLASS
        ));
        try {
            activity.startActivityForResult(explicit, Test20R31Contract.AUTH_REQUEST_CODE);
            logger.event("authorization_activity_started",
                    EvidenceLogger.details("mode", "explicit_global_component"));
            return;
        } catch (Exception explicitError) {
            logger.event("authorization_explicit_start_failed", EvidenceLogger.details(
                    "error_class", explicitError.getClass().getName()
            ));
        }

        Intent fallback = new Intent(Test20R31Contract.AUTH_ACTION)
                .setPackage(Test20R31Contract.GLOBAL_HI_ROKID_PACKAGE);
        try {
            activity.startActivityForResult(fallback, Test20R31Contract.AUTH_REQUEST_CODE);
            logger.event("authorization_activity_started",
                    EvidenceLogger.details("mode", "action_global_package"));
        } catch (Exception fallbackError) {
            logger.event("authorization_result", EvidenceLogger.details(
                    "outcome", "LAUNCH_FAILED",
                    "error_class", fallbackError.getClass().getName(),
                    "token_present", false,
                    "token_value_logged", false
            ));
            callback.onAuthorizationFailure("AUTHORIZATION_LAUNCH_FAILED");
        }
    }

    void handleResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != Test20R31Contract.AUTH_REQUEST_CODE) {
            return;
        }

        String token = directToken(data);
        String parserMode = "direct_extra";
        String parsedClass = "";
        if (token == null || token.isBlank()) {
            ReflectionResult reflected = reflectedToken(resultCode, data);
            token = reflected.token;
            parserMode = reflected.mode;
            parsedClass = reflected.resultClass;
        }

        boolean present = token != null && !token.isBlank();
        JSONObject details = EvidenceLogger.details(
                "result_code", resultCode,
                "token_present", present,
                "token_length", present ? token.length() : 0,
                "token_value_logged", false,
                "parser_mode", parserMode,
                "parsed_result_class", parsedClass
        );
        logger.event("authorization_result", details);

        if (present) {
            callback.onAuthorizationSuccess(token);
        } else {
            callback.onAuthorizationFailure(resultCode == Activity.RESULT_CANCELED
                    ? "AUTHORIZATION_CANCELLED"
                    : "AUTHORIZATION_TOKEN_MISSING");
        }
    }

    private static String directToken(Intent data) {
        if (data == null) {
            return null;
        }
        String token = data.getStringExtra(Test20R31Contract.AUTH_TOKEN_EXTRA);
        return token == null || token.isBlank() ? null : token;
    }

    private static ReflectionResult reflectedToken(int resultCode, Intent data) {
        try {
            Class<?> helperClass = Class.forName(
                    "com.rokid.sprite.aiapp.externalapp.auth.AuthorizationHelper"
            );
            Object helper = null;
            try {
                Field instance = helperClass.getField("INSTANCE");
                helper = instance.get(null);
            } catch (ReflectiveOperationException ignored) {
                // Static helper variants do not expose INSTANCE.
            }

            Method parser = null;
            for (Method candidate : helperClass.getMethods()) {
                Class<?>[] parameters = candidate.getParameterTypes();
                if (candidate.getName().equals("parseAuthorizationResult")
                        && parameters.length == 2
                        && parameters[0] == int.class
                        && Intent.class.isAssignableFrom(parameters[1])) {
                    parser = candidate;
                    break;
                }
            }
            if (parser == null) {
                return new ReflectionResult(null, "reflection_parser_missing", "");
            }

            Object result = parser.invoke(helper, resultCode, data);
            if (result == null) {
                return new ReflectionResult(null, "reflection_result_null", "");
            }
            String token = readToken(result);
            return new ReflectionResult(
                    token,
                    "authorization_helper_reflection",
                    result.getClass().getName()
            );
        } catch (Exception error) {
            return new ReflectionResult(
                    null,
                    "reflection_failed_" + error.getClass().getSimpleName(),
                    ""
            );
        }
    }

    private static String readToken(Object result) {
        for (String methodName : new String[]{"getToken", "component1"}) {
            try {
                Method method = result.getClass().getMethod(methodName);
                Object value = method.invoke(result);
                if (value instanceof String && !((String) value).isBlank()) {
                    return (String) value;
                }
            } catch (ReflectiveOperationException ignored) {
                // Try the next stable Kotlin/Java accessor shape.
            }
        }
        try {
            Field field = result.getClass().getDeclaredField("token");
            field.setAccessible(true);
            Object value = field.get(result);
            return value instanceof String ? (String) value : null;
        } catch (ReflectiveOperationException ignored) {
            return null;
        }
    }

    private static final class ReflectionResult {
        final String token;
        final String mode;
        final String resultClass;

        ReflectionResult(String token, String mode, String resultClass) {
            this.token = token;
            this.mode = mode;
            this.resultClass = resultClass;
        }
    }
}
