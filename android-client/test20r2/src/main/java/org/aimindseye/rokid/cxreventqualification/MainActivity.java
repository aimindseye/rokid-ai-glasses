package org.aimindseye.rokid.cxreventqualification;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

public final class MainActivity extends Activity {
    private EvidenceLogger logger;
    private AuthorizationController authorizationController;
    private CxrLEventController eventController;
    private TextView statusView;
    private Button authorizationButton;
    private Button connectButton;
    private Button disconnectButton;
    private String token;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String runId = getIntent().getStringExtra("run_id");
        if (runId == null || runId.isBlank()) {
            runId = utcTimestamp();
        }
        String firmwareLabel = getIntent().getStringExtra("firmware_label");
        if (firmwareLabel == null || firmwareLabel.isBlank()) {
            firmwareLabel = "unspecified";
        }

        try {
            logger = new EvidenceLogger(this, runId, firmwareLabel);
        } catch (IOException error) {
            throw new IllegalStateException(
                    "Cannot initialize Test 20 r2 evidence",
                    error
            );
        }

        buildUi(runId, firmwareLabel);
        RuntimeAppIdentity appIdentity = runtimeAppIdentity();
        logger.event("run_started", EvidenceLogger.details(
                "app_package", getPackageName(),
                "app_version", appIdentity.versionName,
                "app_version_code", appIdentity.versionCode,
                "app_version_source", "package_manager",
                "sdk_int", Build.VERSION.SDK_INT,
                "firmware_label_operator_supplied",
                        !firmwareLabel.equals("unspecified"),
                "evidence_path",
                        logger.getOutputFile().getAbsolutePath(),
                "internet_permission_intentionally_removed", true,
                "camera_permission_intentionally_removed", true,
                "record_audio_permission_intentionally_removed", true,
                "test_app_ai_assistant_invocation_enabled", false,
                "media_operation_enabled", false,
                "custom_command_enabled", false,
                "custom_view_enabled", false,
                "app_management_enabled", false,
                "cloud_api_client_present", false,
                "apk_upload_enabled", false,
                "reboot_operation_enabled", false,
                "hi_rokid_force_stop_enabled", false
        ));
        logger.event(
                "hi_rokid_environment",
                new HiRokidInspector(this).inspect()
        );

        authorizationController = new AuthorizationController(
                this,
                logger,
                new AuthorizationController.Callback() {
                    @Override
                    public void onAuthorizationSuccess(String value) {
                        token = value;
                        authorizationButton.setEnabled(false);
                        connectButton.setEnabled(true);
                        setStatus(
                                "Authorization token received privately. "
                                        + "Tap Start exactly once."
                        );
                    }

                    @Override
                    public void onAuthorizationFailure(String outcome) {
                        authorizationButton.setEnabled(false);
                        connectButton.setEnabled(false);
                        setStatus(
                                "Authorization terminal outcome: " + outcome
                        );
                    }
                }
        );

        eventController = new CxrLEventController(
                this,
                logger,
                new CxrLEventController.Callback() {
                    @Override
                    public void onStatus(String status) {
                        setStatus(status);
                    }

                    @Override
                    public void onObservationArmed(int requiredCycles) {
                        setStatus(
                                "EVENT OBSERVATION ARMED. Use the ordinary "
                                        + "stock glasses assistant activation. "
                                        + "Do not ask a question. Cancel "
                                        + "immediately, wait two seconds, then "
                                        + "repeat once. Required cycles: "
                                        + requiredCycles + "."
                        );
                    }

                    @Override
                    public void onTerminal(
                            String outcome,
                            boolean success
                    ) {
                        connectButton.setEnabled(false);
                        disconnectButton.setEnabled(false);
                        token = null;
                        setStatus(
                                "Terminal: " + outcome
                                        + ". Automatic clean disconnect follows."
                        );
                    }
                }
        );

        requestBluetoothPermissionIfRequired();
    }

    @Override
    protected void onActivityResult(
            int requestCode,
            int resultCode,
            Intent data
    ) {
        super.onActivityResult(requestCode, resultCode, data);
        authorizationController.handleResult(requestCode, resultCode, data);
    }

    @Override
    protected void onDestroy() {
        if (eventController != null) {
            eventController.disconnect("activity_destroyed");
        }
        token = null;
        super.onDestroy();
    }

    private void buildUi(String runId, String firmwareLabel) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = Math.round(
                20 * getResources().getDisplayMetrics().density
        );
        content.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Test 20 r2 — safe CXR-L event observer");
        title.setTextSize(22);
        content.addView(title);

        TextView scope = new TextView(this);
        scope.setText(
                "Run: " + runId
                        + "\nFirmware: " + firmwareLabel
                        + "\nThe test app cannot invoke the assistant, "
                        + "camera, microphone, media streams, custom "
                        + "commands, custom views, app management, or "
                        + "cloud APIs. Do not ask a spoken question."
        );
        scope.setTextSize(15);
        scope.setPadding(0, padding / 2, 0, padding);
        content.addView(scope);

        statusView = new TextView(this);
        statusView.setText(
                "Confirm Hi Rokid is connected, then tap Authorize once."
        );
        statusView.setTextSize(17);
        statusView.setPadding(0, 0, 0, padding);
        content.addView(statusView);

        authorizationButton = button("1. Authorize through Hi Rokid");
        authorizationButton.setOnClickListener(view -> {
            authorizationButton.setEnabled(false);
            setStatus("Opening Hi Rokid authorization...");
            authorizationController.request();
        });
        content.addView(authorizationButton);

        connectButton = button("2. Start one event-observer attempt");
        connectButton.setEnabled(false);
        connectButton.setOnClickListener(view -> {
            connectButton.setEnabled(false);
            disconnectButton.setEnabled(true);
            setStatus(
                    "One connection attempt started. Do not tap again."
            );
            eventController.start(token);
        });
        content.addView(connectButton);

        disconnectButton = button("Emergency disconnect");
        disconnectButton.setEnabled(false);
        disconnectButton.setOnClickListener(view -> {
            disconnectButton.setEnabled(false);
            eventController.disconnect("operator_emergency_disconnect");
            token = null;
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", "OPERATOR_EMERGENCY_DISCONNECT",
                    "terminal_success", false,
                    "test_app_cloud_ai_request", "NONE",
                    "test_app_media_operation", "NONE"
            ));
            setStatus("Emergency disconnect completed.");
        });
        content.addView(disconnectButton);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(content);
        setContentView(scroll);
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        return button;
    }

    private void setStatus(String text) {
        statusView.setText(text);
    }

    private void requestBluetoothPermissionIfRequired() {
        if (Build.VERSION.SDK_INT >= 31
                && checkSelfPermission(
                        Manifest.permission.BLUETOOTH_CONNECT
                ) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.BLUETOOTH_CONNECT},
                    2002
            );
        }
    }

    private RuntimeAppIdentity runtimeAppIdentity() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(
                    getPackageName(),
                    0
            );
            String versionName =
                    info.versionName == null || info.versionName.isBlank()
                            ? "unknown"
                            : info.versionName;
            return new RuntimeAppIdentity(
                    versionName,
                    info.getLongVersionCode()
            );
        } catch (PackageManager.NameNotFoundException impossible) {
            logger.event("runtime_app_identity_error", EvidenceLogger.details(
                    "error_class", impossible.getClass().getName()
            ));
            return new RuntimeAppIdentity("unknown", -1L);
        }
    }

    private static final class RuntimeAppIdentity {
        private final String versionName;
        private final long versionCode;

        private RuntimeAppIdentity(
                String versionName,
                long versionCode
        ) {
            this.versionName = versionName;
            this.versionCode = versionCode;
        }
    }

    private static String utcTimestamp() {
        SimpleDateFormat format =
                new SimpleDateFormat(
                        "yyyyMMdd'T'HHmmss'Z'",
                        Locale.US
                );
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date());
    }
}
