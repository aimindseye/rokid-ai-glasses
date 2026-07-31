package org.aimindseye.rokid.cxrqualification;

import android.bluetooth.BluetoothDevice;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

final class CxrReflectionAdapter implements AutoCloseable {
    interface Listener {
        void onStatus(String value);
        void onConnectionState(boolean connected);
    }

    private static final String[] API_CLASS_CANDIDATES = {
            "com.rokid.cxr.client.extend.CxrApi",
            "com.rokid.cxr.api.CxrApi",
            "com.rokid.cxr.m.CxrApi"
    };

    private static final Set<String> SAFE_ZERO_ARG_STATUS_METHODS = new HashSet<>(Arrays.asList(
            "isBluetoothConnected",
            "getDeviceType",
            "getGlassesType",
            "getGlassType",
            "getDeviceName",
            "getDeviceVersion",
            "getFirmwareVersion",
            "getSystemVersion",
            "getBattery",
            "getBatteryLevel",
            "getGlassesBattery",
            "getGlassBattery"
    ));

    private final Context context;
    private final EvidenceLogger logger;
    private final Listener listener;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private Class<?> apiClass;
    private Object api;
    private Object callbackProxy;
    private String socketUuid;
    private String classicAddress;
    private Integer glassesType;
    private boolean connected;

    CxrReflectionAdapter(
            Context context,
            EvidenceLogger logger,
            Listener listener) {
        this.context = context.getApplicationContext();
        this.logger = logger;
        this.listener = listener;
        inspectSdk();
    }

    boolean sdkAvailable() {
        return apiClass != null && api != null;
    }

    boolean connected() {
        return connected;
    }

    void inspectSdk() {
        JSONObject details = new JSONObject();
        JSONArray searched = new JSONArray();
        for (String name : API_CLASS_CANDIDATES) {
            searched.put(name);
            try {
                Class<?> candidate = Class.forName(name);
                Method getInstance = candidate.getMethod("getInstance");
                if (!Modifier.isStatic(getInstance.getModifiers())) {
                    continue;
                }
                Object instance = getInstance.invoke(null);
                if (instance != null) {
                    apiClass = candidate;
                    api = instance;
                    break;
                }
            } catch (Exception ignored) {
            }
        }

        EvidenceLogger.put(details, "searched_api_classes", searched);
        EvidenceLogger.put(details, "sdk_class_found", apiClass != null);
        EvidenceLogger.put(
                details,
                "api_class",
                apiClass == null ? JSONObject.NULL : apiClass.getName());
        EvidenceLogger.put(details, "init_bluetooth_found", findInitBluetoothMethod() != null);
        EvidenceLogger.put(details, "connect_bluetooth_overload_count", findConnectMethods().size());
        EvidenceLogger.put(details, "deinit_bluetooth_found", findZeroArgMethod("deinitBluetooth") != null);
        EvidenceLogger.put(details, "safe_status_method_count", safeStatusMethods().size());
        logger.event("sdk_inventory", null, details);
    }

    void initAndConnect(BluetoothDevice device) {
        if (!sdkAvailable()) {
            logger.event("cxr_init_blocked", null, detail("reason", "sdk_class_unavailable"));
            listener.onStatus("CXR-M class unavailable; build with an authorized SDK artifact");
            return;
        }
        Method init = findInitBluetoothMethod();
        if (init == null) {
            logger.event("cxr_init_blocked", null, detail("reason", "init_bluetooth_missing"));
            listener.onStatus("CXR-M initBluetooth API not found");
            return;
        }
        try {
            Class<?> callbackType = init.getParameterTypes()[2];
            callbackProxy = Proxy.newProxyInstance(
                    callbackType.getClassLoader(),
                    new Class<?>[] {callbackType},
                    new BluetoothCallbackHandler());
            socketUuid = null;
            classicAddress = null;
            glassesType = null;
            connected = false;

            JSONObject details = new JSONObject();
            EvidenceLogger.put(details, "method", signature(init));
            logger.event("cxr_init_invoked", safeAddress(device), details);
            init.invoke(api, context, device, callbackProxy);
            listener.onStatus("CXR-M initialization invoked; waiting for connection info");
        } catch (Exception error) {
            logError("cxr_init_failed", device, error);
            listener.onStatus("CXR-M initialization failed: " + error.getClass().getSimpleName());
        }
    }

    void querySafeStatus() {
        if (!sdkAvailable()) {
            logger.event("hardware_status_query_blocked", null, detail("reason", "sdk_class_unavailable"));
            listener.onStatus("SDK unavailable");
            return;
        }

        int successCount = 0;
        int failureCount = 0;
        for (Method method : safeStatusMethods()) {
            JSONObject details = new JSONObject();
            EvidenceLogger.put(details, "method", signature(method));
            try {
                Object value = method.invoke(api);
                appendSafeValue(details, method.getName(), value);
                EvidenceLogger.put(details, "result", "success");
                successCount += 1;
                logger.event("hardware_status_value", null, details);
            } catch (Exception error) {
                EvidenceLogger.put(details, "result", "failure");
                EvidenceLogger.put(details, "error_class", rootCause(error).getClass().getName());
                failureCount += 1;
                logger.event("hardware_status_value", null, details);
            }
        }

        JSONObject summary = new JSONObject();
        EvidenceLogger.put(summary, "safe_method_success_count", successCount);
        EvidenceLogger.put(summary, "safe_method_failure_count", failureCount);
        EvidenceLogger.put(summary, "connection_info_glasses_type_present", glassesType != null);
        if (glassesType != null) {
            EvidenceLogger.put(summary, "connection_info_glasses_type", glassesType);
        }
        EvidenceLogger.put(
                summary,
                "qualified",
                successCount > 0 || glassesType != null);
        logger.event("hardware_status_query_completed", null, summary);
        listener.onStatus(
                "Safe status query complete: " + successCount + " success, " + failureCount + " failure");
    }

    void disconnect() {
        if (!sdkAvailable()) {
            logger.event("cxr_disconnect_blocked", null, detail("reason", "sdk_class_unavailable"));
            return;
        }
        Method method = findZeroArgMethod("deinitBluetooth");
        if (method == null) {
            logger.event("cxr_disconnect_blocked", null, detail("reason", "deinit_bluetooth_missing"));
            listener.onStatus("CXR-M deinitBluetooth API not found");
            return;
        }
        try {
            logger.event("cxr_disconnect_invoked", classicAddress, detail("method", signature(method)));
            method.invoke(api);
            connected = false;
            listener.onConnectionState(false);
            logger.event("cxr_disconnect_returned", classicAddress, detail("connected", false));
            listener.onStatus("CXR-M disconnect invoked");
        } catch (Exception error) {
            logError("cxr_disconnect_failed", null, error);
            listener.onStatus("CXR-M disconnect failed: " + error.getClass().getSimpleName());
        }
    }

    private Method findInitBluetoothMethod() {
        if (apiClass == null) {
            return null;
        }
        for (Method method : apiClass.getMethods()) {
            Class<?>[] types = method.getParameterTypes();
            if (!method.getName().equals("initBluetooth") || types.length != 3) {
                continue;
            }
            if (Context.class.isAssignableFrom(types[0])
                    && BluetoothDevice.class.isAssignableFrom(types[1])
                    && types[2].isInterface()) {
                return method;
            }
        }
        return null;
    }

    private List<Method> findConnectMethods() {
        List<Method> methods = new ArrayList<>();
        if (apiClass == null) {
            return methods;
        }
        for (Method method : apiClass.getMethods()) {
            if (method.getName().equals("connectBluetooth")) {
                methods.add(method);
            }
        }
        methods.sort(Comparator.comparingInt(Method::getParameterCount));
        return methods;
    }

    private Method findZeroArgMethod(String name) {
        if (apiClass == null) {
            return null;
        }
        for (Method method : apiClass.getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == 0) {
                return method;
            }
        }
        return null;
    }

    private List<Method> safeStatusMethods() {
        List<Method> methods = new ArrayList<>();
        if (apiClass == null) {
            return methods;
        }
        for (Method method : apiClass.getMethods()) {
            if (method.getParameterCount() == 0
                    && SAFE_ZERO_ARG_STATUS_METHODS.contains(method.getName())) {
                methods.add(method);
            }
        }
        methods.sort(Comparator.comparing(Method::getName));
        return methods;
    }

    private final class BluetoothCallbackHandler implements InvocationHandler {
        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            String name = method.getName();
            if (name.equals("toString")) {
                return "Test19BluetoothStatusCallback";
            }
            if (name.equals("hashCode")) {
                return System.identityHashCode(proxy);
            }
            if (name.equals("equals")) {
                return proxy == (args == null ? null : args[0]);
            }

            JSONObject details = new JSONObject();
            EvidenceLogger.put(details, "callback_method", name);
            EvidenceLogger.put(details, "argument_count", args == null ? 0 : args.length);

            if (name.equals("onConnectionInfo") && args != null && args.length >= 2) {
                socketUuid = stringValue(args[0]);
                classicAddress = stringValue(args[1]);
                if (args.length >= 3 && args[2] != null) {
                    EvidenceLogger.put(details, "account_pseudonym", logger.pseudonym(String.valueOf(args[2])));
                }
                if (args.length >= 4 && args[3] instanceof Number) {
                    glassesType = ((Number) args[3]).intValue();
                    EvidenceLogger.put(details, "glasses_type", glassesType);
                }
                EvidenceLogger.put(details, "socket_uuid_present", socketUuid != null);
                EvidenceLogger.put(details, "classic_address_present", classicAddress != null);
                if (socketUuid != null) {
                    EvidenceLogger.put(details, "socket_uuid_sha256", Hashing.sha256(socketUuid));
                }
                logger.event("cxr_connection_info", classicAddress, details);
                return defaultReturn(method.getReturnType());
            }

            if (name.equals("onConnected")) {
                connected = true;
                logger.event("cxr_connected", classicAddress, details);
                mainHandler.post(() -> {
                    listener.onConnectionState(true);
                    listener.onStatus("CXR-M connected");
                });
                return defaultReturn(method.getReturnType());
            }

            if (name.equals("onDisconnected")) {
                connected = false;
                logger.event("cxr_disconnected", classicAddress, details);
                mainHandler.post(() -> {
                    listener.onConnectionState(false);
                    listener.onStatus("CXR-M disconnected");
                });
                return defaultReturn(method.getReturnType());
            }

            if (name.equals("onFailed")) {
                if (args != null && args.length > 0 && args[0] != null) {
                    EvidenceLogger.put(details, "error_class", args[0].getClass().getName());
                    EvidenceLogger.put(details, "error_value", String.valueOf(args[0]));
                }
                logger.event("cxr_failed", classicAddress, details);
                mainHandler.post(() -> listener.onStatus("CXR-M callback reported failure"));
                return defaultReturn(method.getReturnType());
            }

            logger.event("cxr_callback_observed", classicAddress, details);
            return defaultReturn(method.getReturnType());
        }
    }

    private void appendSafeValue(JSONObject details, String methodName, Object value) {
        if (value == null) {
            EvidenceLogger.put(details, "value", JSONObject.NULL);
            return;
        }
        String lowered = methodName.toLowerCase(Locale.US);
        if (value instanceof Boolean || value instanceof Number || value.getClass().isEnum()) {
            EvidenceLogger.put(details, "value", String.valueOf(value));
            return;
        }
        String text = String.valueOf(value);
        if (lowered.contains("address") || lowered.contains("mac") || lowered.contains("account")) {
            EvidenceLogger.put(details, "value_pseudonym", logger.pseudonym(text));
        } else if (text.length() <= 160) {
            EvidenceLogger.put(details, "value", text);
        } else {
            EvidenceLogger.put(details, "value_sha256", Hashing.sha256(text.getBytes(StandardCharsets.UTF_8)));
        }
        EvidenceLogger.put(details, "value_class", value.getClass().getName());
    }

    private void logError(String event, BluetoothDevice device, Exception error) {
        Throwable root = rootCause(error);
        JSONObject details = new JSONObject();
        EvidenceLogger.put(details, "error_class", root.getClass().getName());
        EvidenceLogger.put(details, "message_sha256", Hashing.sha256(String.valueOf(root.getMessage())));
        logger.event(event, device == null ? classicAddress : safeAddress(device), details);
    }

    private static Throwable rootCause(Throwable value) {
        Throwable current = value;
        while (current.getCause() != null && current.getCause() != current) {
            current = current.getCause();
        }
        return current;
    }

    private static String signature(Method method) {
        StringBuilder out = new StringBuilder(method.getName()).append('(');
        Class<?>[] types = method.getParameterTypes();
        for (int index = 0; index < types.length; index++) {
            if (index > 0) {
                out.append(',');
            }
            out.append(types[index].getName());
        }
        return out.append(')').append(':').append(method.getReturnType().getName()).toString();
    }

    private static JSONObject detail(String key, Object value) {
        JSONObject object = new JSONObject();
        EvidenceLogger.put(object, key, value);
        return object;
    }

    private static String stringValue(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    private static Object defaultReturn(Class<?> type) {
        if (!type.isPrimitive() || type == Void.TYPE) {
            return null;
        }
        if (type == Boolean.TYPE) {
            return false;
        }
        if (type == Character.TYPE) {
            return '\0';
        }
        if (type == Byte.TYPE) {
            return (byte) 0;
        }
        if (type == Short.TYPE) {
            return (short) 0;
        }
        if (type == Integer.TYPE) {
            return 0;
        }
        if (type == Long.TYPE) {
            return 0L;
        }
        if (type == Float.TYPE) {
            return 0f;
        }
        if (type == Double.TYPE) {
            return 0d;
        }
        return null;
    }

    @SuppressWarnings("MissingPermission")
    private static String safeAddress(BluetoothDevice device) {
        try {
            return device.getAddress();
        } catch (Exception error) {
            return "unavailable-device-identity";
        }
    }

    @Override
    public void close() {
        if (connected) {
            disconnect();
        }
    }
}
