package org.aimindseye.rokid.cxrlqualification;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
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
    private CxrLSessionController sessionController;
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
            throw new IllegalStateException("Cannot initialize Test 19 r2 evidence", error);
        }

        buildUi(runId, firmwareLabel);
        HiRokidInspector inspector = new HiRokidInspector(this);
        logger.event("run_started", EvidenceLogger.details(
                "app_package", getPackageName(),
                "app_version", "2.1-test19-r2.1",
                "sdk_int", Build.VERSION.SDK_INT,
                "firmware_label_operator_supplied", !firmwareLabel.equals("unspecified"),
                "evidence_path", logger.getOutputFile().getAbsolutePath(),
                "internet_permission_declared", true,
                "media_operation_enabled", false,
                "apk_upload_enabled", false,
                "reboot_operation_enabled", false,
                "hi_rokid_force_stop_enabled", false
        ));
        logger.event("hi_rokid_environment", inspector.inspect());

        authorizationController = new AuthorizationController(this, logger,
                new AuthorizationController.Callback() {
                    @Override
                    public void onAuthorizationSuccess(String value) {
                        token = value;
                        authorizationButton.setEnabled(false);
                        connectButton.setEnabled(true);
                        setStatus("Authorization token received privately. Tap Start one time.");
                    }

                    @Override
                    public void onAuthorizationFailure(String outcome) {
                        authorizationButton.setEnabled(false);
                        connectButton.setEnabled(false);
                        setStatus("Authorization terminal outcome: " + outcome);
                    }
                });

        sessionController = new CxrLSessionController(this, logger,
                new CxrLSessionController.Callback() {
                    @Override
                    public void onStatus(String status) {
                        setStatus(status);
                    }

                    @Override
                    public void onTerminal(String outcome, boolean success) {
                        connectButton.setEnabled(false);
                        disconnectButton.setEnabled(false);
                        setStatus("Terminal: " + outcome + ". Automatic clean disconnect follows.");
                    }
                });

        requestBluetoothPermissionIfRequired();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        authorizationController.handleResult(requestCode, resultCode, data);
    }

    @Override
    protected void onDestroy() {
        if (sessionController != null) {
            sessionController.disconnect("activity_destroyed");
        }
        token = null;
        super.onDestroy();
    }

    private void buildUi(String runId, String firmwareLabel) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = Math.round(20 * getResources().getDisplayMetrics().density);
        content.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Test 19 r2 — CXR-L connection only");
        title.setTextSize(22);
        content.addView(title);

        TextView scope = new TextView(this);
        scope.setText("Run: " + runId + "\nFirmware: " + firmwareLabel
                + "\nNo upload, camera, microphone, reboot, unpairing, or Hi Rokid force-stop.");
        scope.setTextSize(15);
        scope.setPadding(0, padding / 2, 0, padding);
        content.addView(scope);

        statusView = new TextView(this);
        statusView.setText("Confirm Hi Rokid is connected, then tap Authorize once.");
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

        connectButton = button("2. Start one CXR-L attempt");
        connectButton.setEnabled(false);
        connectButton.setOnClickListener(view -> {
            connectButton.setEnabled(false);
            disconnectButton.setEnabled(true);
            setStatus("One connection attempt started. Do not tap again.");
            sessionController.start(token);
        });
        content.addView(connectButton);

        disconnectButton = button("Emergency disconnect");
        disconnectButton.setEnabled(false);
        disconnectButton.setOnClickListener(view -> {
            disconnectButton.setEnabled(false);
            sessionController.disconnect("operator_emergency_disconnect");
            logger.event("run_completed", EvidenceLogger.details(
                    "terminal_outcome", "OPERATOR_EMERGENCY_DISCONNECT",
                    "terminal_success", false
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
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 1902);
        }
    }

    private static String utcTimestamp() {
        SimpleDateFormat format = new SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date());
    }
}
