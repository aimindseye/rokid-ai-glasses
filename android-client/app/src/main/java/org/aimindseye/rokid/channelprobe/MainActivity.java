package org.aimindseye.rokid.channelprobe;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public final class MainActivity extends Activity {
    private static final int REQUEST_BLUETOOTH_PERMISSIONS = 25222;

    private BluetoothAdapter adapter;
    private EvidenceLogger logger;
    private RfcommConnectionOnlyProbe connectionProbe;
    private RfcommConnectionOnlyHandoff handoff;
    private TextView statusView;
    private Button connectButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            logger = new EvidenceLogger(this);
        } catch (IOException error) {
            throw new IllegalStateException("Unable to initialize evidence logger", error);
        }

        BluetoothManager manager = getSystemService(BluetoothManager.class);
        adapter = manager == null ? null : manager.getAdapter();
        connectionProbe = new RfcommConnectionOnlyProbe(
                adapter,
                logger,
                this::setStatus);

        setContentView(buildUi());
        ensurePermissions();
        loadPrivateHandoff();
        describeEnvironment();
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Rokid RFCOMM Connection-Only — r25.2.2.2");
        title.setTextSize(20f);
        root.addView(title);

        TextView safety = new TextView(this);
        safety.setText(
                "Private-handoff mode. This build may open one RFCOMM socket and close it. "
                        + "It implements no GATT operation and obtains no application data streams.");
        safety.setPadding(0, dp(8), 0, dp(8));
        root.addView(safety);

        statusView = new TextView(this);
        statusView.setText("Initializing private handoff");
        statusView.setPadding(0, dp(8), 0, dp(12));
        root.addView(statusView);

        connectButton = new Button(this);
        connectButton.setText("Open RFCOMM socket — zero payload");
        connectButton.setEnabled(false);
        connectButton.setOnClickListener(v -> startConnectionOnly());
        root.addView(connectButton);

        Button copyPath = new Button(this);
        copyPath.setText("Copy private log path");
        copyPath.setOnClickListener(v -> copyEvidencePath());
        root.addView(copyPath);

        TextView instructions = new TextView(this);
        instructions.setText(
                "Operator sequence:\n\n"
                        + "1. Start only through the strict r25.2.2.2 host runner.\n"
                        + "2. Confirm Hi Rokid is disabled and the private handoff reports ready.\n"
                        + "3. Tap the connection-only button exactly once.\n"
                        + "4. Wait for socket-open success or a bounded failure.\n"
                        + "5. Return to Terminal and press Enter.\n\n"
                        + "The client never reads from or writes to the RFCOMM application channel.");
        instructions.setPadding(0, dp(12), 0, dp(8));

        ScrollView scroll = new ScrollView(this);
        scroll.addView(instructions);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f));

        return root;
    }

    private void loadPrivateHandoff() {
        try {
            handoff = RfcommConnectionOnlyHandoff.load(this);
            connectButton.setEnabled(hasBluetoothPermissions());
            JSONObject details = handoff.sanitizedDetails();
            logger.event("r25_2_2_2_handoff_loaded", handoff.runtimeAddress(), details);
            setStatus("Private handoff validated; connection-only probe ready");
        } catch (Exception error) {
            handoff = null;
            connectButton.setEnabled(false);
            JSONObject details = new JSONObject();
            try {
                details.put("error_class", error.getClass().getName());
                details.put("message_sha256", Hashing.sha256(
                        String.valueOf(error.getMessage()).getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            } catch (Exception ignored) {
            }
            logger.event("r25_2_2_2_handoff_rejected", null, details);
            setStatus("Private handoff missing or invalid; use the strict host runner");
        }
    }

    private void startConnectionOnly() {
        if (!hasBluetoothPermissions()) {
            ensurePermissions();
            setStatus("Bluetooth permissions required");
            return;
        }
        if (handoff == null) {
            setStatus("Private handoff unavailable");
            return;
        }
        connectButton.setEnabled(false);
        connectionProbe.start(handoff);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void setStatus(String text) {
        runOnUiThread(() -> statusView.setText(text));
    }

    private void ensurePermissions() {
        List<String> missing = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                    != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_CONNECT);
            }
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
                    != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_SCAN);
            }
        } else if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            missing.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (!missing.isEmpty()) {
            requestPermissions(missing.toArray(new String[0]), REQUEST_BLUETOOTH_PERMISSIONS);
        }
    }

    private boolean hasBluetoothPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                    == PackageManager.PERMISSION_GRANTED
                    && checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
                    == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_BLUETOOTH_PERMISSIONS && connectButton != null) {
            connectButton.setEnabled(handoff != null && hasBluetoothPermissions());
        }
    }

    private void describeEnvironment() {
        JSONObject details = new JSONObject();
        try {
            details.put("release", "r1.3.3.2.25.2.2.2");
            details.put("mode", "private_handoff_rfcomm_connection_only");
            details.put("sdk_int", Build.VERSION.SDK_INT);
            details.put("bluetooth_adapter_present", adapter != null);
            details.put("bluetooth_enabled", adapter != null
                    && hasBluetoothPermissions() && adapter.isEnabled());
            details.put("airplane_mode", Settings.Global.getInt(
                    getContentResolver(), Settings.Global.AIRPLANE_MODE_ON, 0));
            details.put("gatt_available_in_ui", false);
            details.put("rfcomm_socket_open_available_in_ui", true);
            details.put("application_payload_read_implemented", false);
            details.put("application_payload_write_implemented", false);
            details.put("stock_app_assist_in_scope", false);
        } catch (Exception ignored) {
        }
        logger.event("client_environment", null, details);
    }

    private void copyEvidencePath() {
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText(
                "r25.2.2.2 evidence path",
                logger.file().getAbsolutePath()));
        Toast.makeText(this, "Private log path copied", Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onDestroy() {
        connectionProbe.close();
        try {
            logger.close();
        } catch (IOException ignored) {
        }
        super.onDestroy();
    }
}
