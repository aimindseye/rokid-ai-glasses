package org.aimindseye.rokid.cxrphotoqualification;

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
    private CxrLPhotoController controller;
    private TextView statusView;
    private Button authorizationButton;
    private Button connectButton;
    private Button captureButton;
    private Button disconnectButton;
    private String token;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        String runId = getIntent().getStringExtra("run_id");
        if (runId == null || runId.isBlank()) runId = utcTimestamp();
        String firmwareLabel = getIntent().getStringExtra("firmware_label");
        if (firmwareLabel == null || firmwareLabel.isBlank()) firmwareLabel = "unspecified";
        try { logger = new EvidenceLogger(this, runId, firmwareLabel); }
        catch (IOException error) { throw new IllegalStateException("Cannot initialize Test 20 r3.2 evidence", error); }
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
                "image_callback_registration_enabled", true,
                "service_status_queries_enabled", true,
                "take_photo_invocation_enabled", true,
                "max_photo_request_count", 1,
                "photo_arg_1", Test20R32Contract.PHOTO_ARG_1,
                "photo_arg_2", Test20R32Contract.PHOTO_ARG_2,
                "photo_arg_3", Test20R32Contract.PHOTO_ARG_3,
                "photo_argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,
                "image_payload_persistence_enabled", false,
                "image_preview_enabled", false,
                "audio_stream_invocation_enabled", false,
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
                        connectButton.setEnabled(true);
                        setStatus("Authorization token received privately. Start the connection once.");
                    }
                    @Override public void onAuthorizationFailure(String outcome) {
                        authorizationButton.setEnabled(false);
                        connectButton.setEnabled(false);
                        captureButton.setEnabled(false);
                        setStatus("Authorization terminal outcome: " + outcome);
                    }
                });

        controller = new CxrLPhotoController(this, logger,
                new CxrLPhotoController.Callback() {
                    @Override public void onStatus(String status) { setStatus(status); }
                    @Override public void onPhotoReady() {
                        captureButton.setEnabled(true);
                        setStatus("ONE-SHOT PHOTO READY. Point only at the printed Test 20 r3.2 target, then tap Capture exactly once.");
                    }
                    @Override public void onPhotoRequestIssued() {
                        captureButton.setEnabled(false);
                        setStatus("One photo request issued. Keep the target steady and wait for the terminal result.");
                    }
                    @Override public void onTerminal(String outcome, boolean success) {
                        connectButton.setEnabled(false);
                        captureButton.setEnabled(false);
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
        title.setText("Test 20 r3.2 — One-Shot Photo Qualification");
        title.setTextSize(22); title.setPadding(0,0,0,padding/2); content.addView(title);
        TextView identity = new TextView(this);
        identity.setText("Run: " + runId + "\nFirmware: " + firmwareLabel);
        identity.setTextSize(13); identity.setPadding(0,0,0,padding/2); content.addView(identity);
        TextView scope = new TextView(this);
        scope.setText("Exactly one takePhoto(1920,1080,80) request. Use only the printed public test target. No preview, file write, upload, audio operation, or cloud request.");
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
        connectButton = button("2. Start one photo connection");
        connectButton.setEnabled(false);
        connectButton.setOnClickListener(view -> {
            connectButton.setEnabled(false);
            disconnectButton.setEnabled(true);
            setStatus("One connection attempt started. Wait for ONE-SHOT PHOTO READY.");
            controller.startConnection(token);
        });
        content.addView(connectButton);
        captureButton = button("3. Capture exactly one bounded photo");
        captureButton.setEnabled(false);
        captureButton.setOnClickListener(view -> {
            captureButton.setEnabled(false);
            controller.requestOnePhoto();
        });
        content.addView(captureButton);
        disconnectButton = button("Emergency disconnect");
        disconnectButton.setEnabled(false);
        disconnectButton.setOnClickListener(view -> {
            disconnectButton.setEnabled(false);
            captureButton.setEnabled(false);
            controller.disconnect("operator_emergency_disconnect");
            token = null;
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", "OPERATOR_EMERGENCY_DISCONNECT",
                    "terminal_success", false,
                    "test_app_cloud_request", "NONE",
                    "take_photo_request_count", 0,
                    "start_audio_stream_invocation", "NONE",
                    "stop_audio_stream_invocation", "NONE",
                    "image_payload_persistence", "NONE",
                    "image_payload_preview", "NONE",
                    "media_upload", "NONE"));
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
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 2032);
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
