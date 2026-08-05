package org.aimindseye.rokid.test22wifi;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * TEST22_R4_3_3_PERSISTENT_LAUNCH_BREADCRUMBS
 *
 * Dormant, loopback-only control service. The host reaches it only through USB
 * ADB port forwarding. It never enables Wi-Fi until an exact one-time execution
 * token is received.
 */
public final class Test22ControlService extends Service {
    public static final int CONTROL_PORT = 37122;
    public static final String ACTION_PACKAGE_REPLACED =
            "org.aimindseye.rokid.test22wifi.action.PACKAGE_REPLACED";
    public static final String ACTION_MANUAL_START =
            "org.aimindseye.rokid.test22wifi.action.MANUAL_START";

    private static final String CHANNEL_ID = "test22-control";
    private static final int NOTIFICATION_ID = 22043;
    private static final AtomicBoolean PROBE_EXECUTION_STARTED =
            new AtomicBoolean(false);
    private static final AtomicBoolean WIFI_API_TOUCHED =
            new AtomicBoolean(false);
    private static final AtomicBoolean ONE_SHOT_USED =
            new AtomicBoolean(false);

    private volatile boolean stopRequested;
    private volatile String startReason = "SERVICE_CREATE";
    private ServerSocket serverSocket;
    private Thread serverThread;

    @Override
    public void onCreate() {
        super.onCreate();

        LaunchBreadcrumbs.record(
                this,
                "CONTROL_SERVICE_ON_CREATE",
                ""
        );

        LaunchBreadcrumbs.record(
                this,
                "FOREGROUND_START_REQUESTED",
                ""
        );

        startForeground(NOTIFICATION_ID, buildNotification());

        LaunchBreadcrumbs.record(
                this,
                "FOREGROUND_ESTABLISHED",
                ""
        );

        scheduleSurvivalBreadcrumbs();
        startServer();
    }

    @Override
    public int onStartCommand(
            Intent intent,
            int flags,
            int startId
    ) {
        if (
                intent != null
                        && ACTION_PACKAGE_REPLACED.equals(
                                intent.getAction()
                        )
        ) {
            startReason = "MY_PACKAGE_REPLACED";
        } else if (
                intent != null
                        && ACTION_MANUAL_START.equals(
                                intent.getAction()
                        )
        ) {
            startReason = "MANUAL_ACTIVITY";
        }

        LaunchBreadcrumbs.record(
                this,
                "CONTROL_SERVICE_ON_START_COMMAND",
                startReason
        );

        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        LaunchBreadcrumbs.record(
                this,
                "CONTROL_SERVICE_ON_DESTROY",
                ""
        );

        stopRequested = true;

        try {
            if (serverSocket != null) {
                serverSocket.close();
            }
        } catch (Exception ignored) {
        }

        super.onDestroy();
    }

    static void noteWifiApiTouched() {
        WIFI_API_TOUCHED.set(true);
    }

    private Notification buildNotification() {
        NotificationManager manager =
                (NotificationManager)
                        getSystemService(
                                NOTIFICATION_SERVICE
                        );

        if (
                Build.VERSION.SDK_INT >= 26
                        && manager != null
        ) {
            NotificationChannel channel =
                    new NotificationChannel(
                            CHANNEL_ID,
                            "Test22 control",
                            NotificationManager.IMPORTANCE_LOW
                    );

            channel.setDescription(
                    "Dormant Test22 host control; "
                            + "Wi-Fi probe has not started"
            );

            manager.createNotificationChannel(channel);
        }

        Notification.Builder builder =
                Build.VERSION.SDK_INT >= 26
                        ? new Notification.Builder(
                                this,
                                CHANNEL_ID
                        )
                        : new Notification.Builder(this);

        return builder
                .setSmallIcon(
                        android.R.drawable.stat_sys_data_bluetooth
                )
                .setContentTitle("Test22 control ready")
                .setContentText(
                        "Dormant until the isolated host "
                                + "execution token is received"
                )
                .setOngoing(true)
                .build();
    }

    private void startServer() {
        serverThread =
                new Thread(
                        () -> {
                            try (
                                    ServerSocket server =
                                            new ServerSocket()
                            ) {
                                serverSocket = server;
                                server.setReuseAddress(true);

                                LaunchBreadcrumbs.record(
                                        this,
                                        "CONTROL_SOCKET_BIND_ATTEMPT",
                                        "127.0.0.1:37122"
                                );

                                server.bind(
                                        new InetSocketAddress(
                                                InetAddress
                                                        .getLoopbackAddress(),
                                                CONTROL_PORT
                                        )
                                );

                                LaunchBreadcrumbs.record(
                                        this,
                                        "CONTROL_SOCKET_BOUND_"
                                                + "127_0_0_1_37122",
                                        ""
                                );

                                while (!stopRequested) {
                                    try (
                                            Socket socket =
                                                    server.accept()
                                    ) {
                                        socket.setSoTimeout(120_000);
                                        handleClient(socket);
                                    } catch (Exception ignored) {
                                        if (stopRequested) {
                                            break;
                                        }
                                    }
                                }
                            } catch (Exception error) {
                                LaunchBreadcrumbs.record(
                                        this,
                                        "CONTROL_SOCKET_TERMINATED",
                                        error.getClass().getName()
                                );
                            }
                        },
                        "test22-control-loopback"
                );

        serverThread.setDaemon(true);
        serverThread.start();
    }

    private void scheduleSurvivalBreadcrumbs() {
        Handler handler =
                new Handler(Looper.getMainLooper());

        handler.postDelayed(
                () ->
                        LaunchBreadcrumbs.record(
                                this,
                                "FOREGROUND_SERVICE_SURVIVED_5S",
                                ""
                        ),
                5_000L
        );

        handler.postDelayed(
                () ->
                        LaunchBreadcrumbs.record(
                                this,
                                "FOREGROUND_SERVICE_SURVIVED_30S",
                                ""
                        ),
                30_000L
        );
    }

    private void handleClient(Socket socket) throws Exception {
        BufferedReader reader =
                new BufferedReader(
                        new InputStreamReader(
                                socket.getInputStream(),
                                StandardCharsets.UTF_8
                        )
                );

        OutputStreamWriter writer =
                new OutputStreamWriter(
                        socket.getOutputStream(),
                        StandardCharsets.UTF_8
                );

        String line = reader.readLine();
        JSONObject response;

        try {
            JSONObject request =
                    new JSONObject(
                            line == null ? "{}" : line
                    );

            String command =
                    request.optString(
                            "command",
                            ""
                    ).trim();

            if ("PING".equals(command)) {
                response = pingResponse();
            } else if ("EXECUTE".equals(command)) {
                response = executeResponse(request);
            } else {
                response = errorResponse(
                        "UNKNOWN_COMMAND"
                );
            }
        } catch (Throwable error) {
            response = errorResponse(
                    error.getClass().getName()
            );
        }

        writer.write(response.toString());
        writer.write("\n");
        writer.flush();
    }

    private JSONObject pingResponse() throws Exception {
        JSONObject response = new JSONObject();

        response.put(
                "schema",
                "rokid.test22.r4.3.control-response.v1"
        );
        response.put("status", "READY");
        response.put(
                "control_plane_marker",
                MainActivity.CONTROL_PLANE_MARKER
        );
        response.put(
                "package_name",
                getPackageName()
        );
        response.put(
                "installed_apk_sha256",
                sha256File(
                        new File(
                                getPackageCodePath()
                        )
                )
        );
        response.put(
                "control_transport",
                "loopback_tcp_via_adb_forward"
        );
        response.put(
                "listen_address",
                "127.0.0.1"
        );
        response.put(
                "listen_port",
                CONTROL_PORT
        );
        response.put(
                "service_start_reason",
                startReason
        );
        response.put(
                "probe_execution_started",
                PROBE_EXECUTION_STARTED.get()
        );
        response.put(
                "wifi_api_touched",
                WIFI_API_TOUCHED.get()
        );
        response.put(
                "one_shot_used",
                ONE_SHOT_USED.get()
        );
        response.put(
                "bluetooth_api_used",
                false
        );
        response.put(
                "cxr_api_used",
                false
        );

        return response;
    }

    private JSONObject executeResponse(
            JSONObject request
    ) throws Exception {
        String token =
                request.optString(
                        "execute_token",
                        ""
                );

        if (!MainActivity.EXECUTE_TOKEN.equals(token)) {
            return errorResponse(
                    "EXECUTION_TOKEN_REJECTED"
            );
        }

        if (
                !ONE_SHOT_USED.compareAndSet(
                        false,
                        true
                )
        ) {
            return errorResponse(
                    "ONE_SHOT_ALREADY_USED"
            );
        }

        PROBE_EXECUTION_STARTED.set(true);
        JSONObject result;

        try {
            result =
                    new Test22Probe(
                            this,
                            request
                    ).run();
        } catch (Throwable error) {
            result = new JSONObject();
            result.put(
                    "schema",
                    "rokid.test22.app-result.v1"
            );
            result.put(
                    "completed",
                    false
            );
            result.put(
                    "terminal_error_class",
                    error.getClass().getName()
            );
            result.put(
                    "control_plane_marker",
                    MainActivity.CONTROL_PLANE_MARKER
            );
            result.put(
                    "probe_execution_started",
                    true
            );
            result.put(
                    "wifi_api_touched",
                    WIFI_API_TOUCHED.get()
            );
        }

        JSONObject response = new JSONObject();
        response.put(
                "schema",
                "rokid.test22.r4.3.control-response.v1"
        );
        response.put(
                "status",
                "EXECUTION_COMPLETE"
        );
        response.put(
                "result",
                result
        );

        return response;
    }

    private static JSONObject errorResponse(
            String error
    ) throws Exception {
        JSONObject response = new JSONObject();
        response.put(
                "schema",
                "rokid.test22.r4.3.control-response.v1"
        );
        response.put(
                "status",
                "ERROR"
        );
        response.put(
                "error",
                error
        );
        return response;
    }

    private static String sha256File(
            File file
    ) throws Exception {
        MessageDigest digest =
                MessageDigest.getInstance(
                        "SHA-256"
                );

        byte[] buffer =
                new byte[64 * 1024];

        try (
                FileInputStream input =
                        new FileInputStream(file)
        ) {
            for (
                    int count;
                    (count = input.read(buffer)) >= 0;
            ) {
                if (count > 0) {
                    digest.update(
                            buffer,
                            0,
                            count
                    );
                }
            }
        }

        StringBuilder output =
                new StringBuilder(64);

        for (byte item : digest.digest()) {
            output.append(
                    String.format(
                            "%02x",
                            item & 0xff
                    )
            );
        }

        return output.toString();
    }
}
