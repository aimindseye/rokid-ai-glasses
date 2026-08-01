package org.aimindseye.rokid.cxrmediapreflight;

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
    private CxrLMediaPreflightController controller;
    private TextView statusView;
    private Button authorizationButton;
    private Button startButton;
    private Button disconnectButton;
    private String token;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        String runId = getIntent().getStringExtra("run_id");
        if (runId == null || runId.isBlank()) runId = utcTimestamp();
        String firmwareLabel = getIntent().getStringExtra("firmware_label");
        if (firmwareLabel == null || firmwareLabel.isBlank()) firmwareLabel = "unspecified";
        try { logger = new EvidenceLogger(this, runId, firmwareLabel); }
        catch (IOException error) { throw new IllegalStateException("Cannot initialize Test 20 r3.1 evidence", error); }
        buildUi(runId, firmwareLabel);
        RuntimeAppIdentity identity = runtimeAppIdentity();
        logger.event("run_started", EvidenceLogger.details(
                "app_package", getPackageName(),
                "app_version", identity.versionName,
                "app_version_code", identity.versionCode,
                "app_version_source", "package_manager",
                "sdk_int", Build.VERSION.SDK_INT,
                "evidence_path", logger.getOutputFile().getAbsolutePath(),
                "internet_permission_intentionally_removed", true,
                "camera_permission_intentionally_removed", true,
                "record_audio_permission_intentionally_removed", true,
                "callback_registration_enabled", true,
                "service_status_queries_enabled", true,
                "take_photo_invocation_enabled", false,
                "audio_stream_invocation_enabled", false,
                "media_payload_retention_enabled", false,
                "cloud_api_client_present", false,
                "custom_command_enabled", false,
                "custom_view_enabled", false,
                "app_management_enabled", false));
        logger.event("hi_rokid_environment", new HiRokidInspector(this).inspect());

        authorizationController = new AuthorizationController(this, logger,
                new AuthorizationController.Callback() {
                    @Override public void onAuthorizationSuccess(String value) {
                        token = value;
                        authorizationButton.setEnabled(false);
                        startButton.setEnabled(true);
                        setStatus("Authorization token received privately. Tap Start exactly once.");
                    }
                    @Override public void onAuthorizationFailure(String outcome) {
                        authorizationButton.setEnabled(false);
                        startButton.setEnabled(false);
                        setStatus("Authorization terminal outcome: " + outcome);
                    }
                });

        controller = new CxrLMediaPreflightController(this, logger,
                new CxrLMediaPreflightController.Callback() {
                    @Override public void onStatus(String status) { setStatus(status); }
                    @Override public void onObservationArmed(long durationMs) {
                        setStatus("NO-PAYLOAD OBSERVATION ARMED for " + durationMs
                                + " ms. Do not invoke camera, audio, assistant, or media controls. Wait.");
                    }
                    @Override public void onTerminal(String outcome, boolean success) {
                        startButton.setEnabled(false);
                        disconnectButton.setEnabled(false);
                        token = null;
                        setStatus("Terminal: " + outcome + ". Automatic clean disconnect follows.");
                    }
                });
        requestBluetoothPermissionIfRequired();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        authorizationController.handleResult(requestCode, resultCode, data);
    }

    @Override protected void onDestroy() {
        if (controller != null) controller.disconnect("activity_destroyed");
        token = null;
        super.onDestroy();
    }

    private void buildUi(String runId, String firmwareLabel) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = Math.round(20 * getResources().getDisplayMetrics().density);
        content.setPadding(padding, padding, padding, padding);
        TextView title = new TextView(this);
        title.setText("Test 20 r3.1 — Media Service No-Payload Preflight");
        title.setTextSize(22); title.setPadding(0,0,0,padding/2); content.addView(title);
        TextView identity = new TextView(this);
        identity.setText("Run: " + runId + "\nFirmware: " + firmwareLabel);
        identity.setTextSize(13); identity.setPadding(0,0,0,padding/2); content.addView(identity);
        TextView scope = new TextView(this);
        scope.setText("Registers image/audio callbacks and queries service status only. "
                + "No photo request, audio stream request, payload retention, or cloud request.");
        scope.setTextSize(15); scope.setPadding(0,0,0,padding); content.addView(scope);
        statusView = new TextView(this);
        statusView.setText("Confirm Hi Rokid is connected, then tap Authorize once.");
        statusView.setTextSize(17); statusView.setPadding(0,0,0,padding); content.addView(statusView);
        authorizationButton = button("1. Authorize through Hi Rokid");
        authorizationButton.setOnClickListener(view -> {
            authorizationButton.setEnabled(false);
            setStatus("Opening Hi Rokid authorization...");
            authorizationController.request();
        });
        content.addView(authorizationButton);
        startButton = button("2. Start one no-payload preflight");
        startButton.setEnabled(false);
        startButton.setOnClickListener(view -> {
            startButton.setEnabled(false);
            disconnectButton.setEnabled(true);
            setStatus("One preflight attempt started. Do not tap again.");
            controller.start(token);
        });
        content.addView(startButton);
        disconnectButton = button("Emergency disconnect");
        disconnectButton.setEnabled(false);
        disconnectButton.setOnClickListener(view -> {
            disconnectButton.setEnabled(false);
            controller.disconnect("operator_emergency_disconnect");
            token = null;
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", "OPERATOR_EMERGENCY_DISCONNECT",
                    "terminal_success", false,
                    "test_app_cloud_request", "NONE",
                    "take_photo_invocation", "NONE",
                    "start_audio_stream_invocation", "NONE",
                    "stop_audio_stream_invocation", "NONE",
                    "image_payload_retention", "NONE",
                    "audio_payload_retention", "NONE"));
            setStatus("Emergency disconnect completed.");
        });
        content.addView(disconnectButton);
        ScrollView scroll = new ScrollView(this); scroll.addView(content); setContentView(scroll);
    }

    private Button button(String label) {
        Button button = new Button(this); button.setText(label); button.setAllCaps(false); return button;
    }
    private void setStatus(String text) { statusView.setText(text); }
    private void requestBluetoothPermissionIfRequired() {
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 2031);
        }
    }
    private RuntimeAppIdentity runtimeAppIdentity() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            String name = info.versionName == null || info.versionName.isBlank() ? "unknown" : info.versionName;
            return new RuntimeAppIdentity(name, info.getLongVersionCode());
        } catch (PackageManager.NameNotFoundException impossible) {
            logger.event("runtime_app_identity_error", EvidenceLogger.details("error_class", impossible.getClass().getName()));
            return new RuntimeAppIdentity("unknown", -1L);
        }
    }
    private static final class RuntimeAppIdentity {
        private final String versionName; private final long versionCode;
        private RuntimeAppIdentity(String versionName, long versionCode) {
            this.versionName = versionName; this.versionCode = versionCode;
        }
    }
    private static String utcTimestamp() {
        SimpleDateFormat format = new SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date());
    }
}
