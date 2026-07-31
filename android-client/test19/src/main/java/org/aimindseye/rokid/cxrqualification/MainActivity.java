package org.aimindseye.rokid.cxrqualification;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class MainActivity extends Activity {
    private static final int REQUEST_BLUETOOTH_PERMISSIONS = 19001;
    private static final List<String> PHASES = Arrays.asList(
            "baseline_stock_connected",
            "stock_background",
            "stock_force_stopped",
            "custom_only",
            "glasses_reboot_reconnect",
            "phone_reboot_reconnect",
            "stock_recovery");

    private BluetoothAdapter adapter;
    private EvidenceLogger logger;
    private BleDeviceScanner scanner;
    private CxrReflectionAdapter cxr;
    private TextView statusView;
    private TextView sdkView;
    private Spinner phaseSpinner;
    private Spinner deviceSpinner;
    private Button connectButton;
    private Button disconnectButton;
    private Button queryButton;
    private final List<BleDeviceScanner.Candidate> candidates = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            logger = new EvidenceLogger(this);
        } catch (IOException error) {
            throw new IllegalStateException("Unable to initialize Test 19 evidence logger", error);
        }

        BluetoothManager manager = getSystemService(BluetoothManager.class);
        adapter = manager == null ? null : manager.getAdapter();
        cxr = new CxrReflectionAdapter(this, logger, new CxrReflectionAdapter.Listener() {
            @Override
            public void onStatus(String value) {
                setStatus(value);
            }

            @Override
            public void onConnectionState(boolean connected) {
                runOnUiThread(() -> updateConnectionButtons(connected));
            }
        });
        scanner = new BleDeviceScanner(adapter, logger, new BleDeviceScanner.Listener() {
            @Override
            public void onStatus(String value) {
                setStatus(value);
            }

            @Override
            public void onCandidates(List<BleDeviceScanner.Candidate> value) {
                runOnUiThread(() -> replaceCandidates(value));
            }
        });

        setContentView(buildUi());
        ensurePermissions();
        describeEnvironment();
        applyPhaseFromIntent(getIntent());
        updateSdkStatus();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        applyPhaseFromIntent(intent);
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(12);
        root.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Test 19 r1 — Maven CXR-M ownership and privacy");
        title.setTextSize(20f);
        root.addView(title);

        TextView safety = new TextView(this);
        safety.setText(
                "Maven-resolved SDK qualification only. INTERNET is declared for SDK-local Wi-Fi/HTTP channels; "
                        + "public-cloud traffic is prohibited and checked from PCAPdroid evidence. "
                        + "No captured-command replay or firmware mutation.");
        safety.setPadding(0, dp(8), 0, dp(8));
        root.addView(safety);

        sdkView = new TextView(this);
        sdkView.setPadding(0, dp(4), 0, dp(8));
        root.addView(sdkView);

        phaseSpinner = new Spinner(this);
        phaseSpinner.setAdapter(new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                PHASES));
        root.addView(phaseSpinner);

        Button markPhase = new Button(this);
        markPhase.setText("Record selected ownership phase");
        markPhase.setOnClickListener(v -> recordSelectedPhase());
        root.addView(markPhase);

        Button discover = new Button(this);
        discover.setText("Discover Bluetooth candidates — 20 seconds");
        discover.setOnClickListener(v -> {
            if (!hasBluetoothPermissions()) {
                ensurePermissions();
                setStatus("Bluetooth permissions required");
                return;
            }
            scanner.start();
        });
        root.addView(discover);

        deviceSpinner = new Spinner(this);
        deviceSpinner.setAdapter(new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                new ArrayList<>(Arrays.asList("No candidate selected"))));
        root.addView(deviceSpinner);

        Button inspect = new Button(this);
        inspect.setText("Re-run CXR-M SDK inventory");
        inspect.setOnClickListener(v -> {
            cxr.inspectSdk();
            updateSdkStatus();
        });
        root.addView(inspect);

        connectButton = new Button(this);
        connectButton.setText("Initialize and connect through CXR-M");
        connectButton.setOnClickListener(v -> connectSelected());
        root.addView(connectButton);

        queryButton = new Button(this);
        queryButton.setText("Query safe device status");
        queryButton.setEnabled(false);
        queryButton.setOnClickListener(v -> cxr.querySafeStatus());
        root.addView(queryButton);

        disconnectButton = new Button(this);
        disconnectButton.setText("Clean CXR-M disconnect");
        disconnectButton.setEnabled(false);
        disconnectButton.setOnClickListener(v -> cxr.disconnect());
        root.addView(disconnectButton);

        Button copyPath = new Button(this);
        copyPath.setText("Copy private evidence path");
        copyPath.setOnClickListener(v -> copyEvidencePath());
        root.addView(copyPath);

        statusView = new TextView(this);
        statusView.setText("Ready for an operator-assigned phase");
        statusView.setPadding(0, dp(10), 0, dp(10));
        root.addView(statusView);

        TextView instructions = new TextView(this);
        instructions.setText(
                "Run only from scripts/tests/run_test19_cxr_qualification.sh.\n\n"
                        + "For each host-directed phase:\n"
                        + "1. Confirm the phase marker.\n"
                        + "2. Discover candidates and select the Style device.\n"
                        + "3. Tap initialize/connect exactly once.\n"
                        + "4. After connection, query safe status.\n"
                        + "5. Disconnect cleanly unless the phase explicitly tests interruption.\n"
                        + "6. Return to Terminal and continue.\n\n"
                        + "Do not enter credentials or secrets. Basic Bluetooth qualification uses the documented "
                        + "initBluetooth(Context, BluetoothDevice, callback) flow only.");

        ScrollView scroll = new ScrollView(this);
        scroll.addView(instructions);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f));
        return root;
    }

    private void recordSelectedPhase() {
        String phase = String.valueOf(phaseSpinner.getSelectedItem());
        logger.setPhase(phase);
        setStatus("Phase recorded: " + phase);
    }

    private void applyPhaseFromIntent(Intent intent) {
        if (intent == null) {
            return;
        }
        String phase = intent.getStringExtra("phase");
        if (phase == null || phase.isBlank()) {
            return;
        }
        logger.setPhase(phase);
        if (intent.getBooleanExtra("stock_recovery_confirmed", false)) {
            logger.event("stock_recovery_confirmed", null, detail("confirmed", true));
        }
        int index = PHASES.indexOf(phase);
        if (phaseSpinner != null && index >= 0) {
            phaseSpinner.setSelection(index);
        }
        setStatus("Host phase recorded: " + phase);
    }

    private void connectSelected() {
        if (!hasBluetoothPermissions()) {
            ensurePermissions();
            setStatus("Bluetooth permissions required");
            return;
        }
        int index = deviceSpinner.getSelectedItemPosition();
        if (index < 0 || index >= candidates.size()) {
            setStatus("Select a discovered candidate first");
            return;
        }
        connectButton.setEnabled(false);
        cxr.initAndConnect(candidates.get(index).device);
    }

    private void replaceCandidates(List<BleDeviceScanner.Candidate> value) {
        candidates.clear();
        candidates.addAll(value);
        List<String> labels = new ArrayList<>();
        for (BleDeviceScanner.Candidate candidate : candidates) {
            labels.add(
                    candidate.displayName
                            + " | "
                            + logger.pseudonym(safeAddress(candidate))
                            + " | rssi="
                            + candidate.rssi
                            + (candidate.service9100 ? " | service-9100" : "")
                            + (candidate.bonded ? " | bonded" : ""));
        }
        if (labels.isEmpty()) {
            labels.add("No candidates discovered");
        }
        deviceSpinner.setAdapter(new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                labels));
        connectButton.setEnabled(!candidates.isEmpty() && cxr.sdkAvailable());
    }

    private static String safeAddress(BleDeviceScanner.Candidate candidate) {
        try {
            return candidate.device.getAddress();
        } catch (Exception error) {
            return candidate.displayName;
        }
    }

    private void updateConnectionButtons(boolean connected) {
        queryButton.setEnabled(connected);
        disconnectButton.setEnabled(connected);
        connectButton.setEnabled(!connected && !candidates.isEmpty() && cxr.sdkAvailable());
    }

    private void updateSdkStatus() {
        if (sdkView == null) {
            return;
        }
        sdkView.setText(
                cxr.sdkAvailable()
                        ? "CXR-M runtime class: detected"
                        : "CXR-M runtime class: absent — build with an authorized artifact");
        if (connectButton != null) {
            connectButton.setEnabled(cxr.sdkAvailable() && !candidates.isEmpty());
        }
    }

    private void describeEnvironment() {
        JSONObject details = new JSONObject();
        EvidenceLogger.put(details, "test", 19);
        EvidenceLogger.put(details, "release", "test19-cxr-m-qualification-r1");
        EvidenceLogger.put(details, "sdk_int", Build.VERSION.SDK_INT);
        EvidenceLogger.put(details, "bluetooth_adapter_present", adapter != null);
        EvidenceLogger.put(
                details,
                "bluetooth_enabled",
                adapter != null && hasBluetoothPermissions() && adapter.isEnabled());
        EvidenceLogger.put(
                details,
                "airplane_mode",
                Settings.Global.getInt(getContentResolver(), Settings.Global.AIRPLANE_MODE_ON, 0));
        EvidenceLogger.put(details, "internet_permission_declared", false);
        EvidenceLogger.put(details, "captured_payload_replay_implemented", false);
        EvidenceLogger.put(details, "firmware_mutation_implemented", false);
        EvidenceLogger.put(details, "developer_mode_mutation_implemented", false);
        logger.event("client_environment", null, details);
    }

    private void ensurePermissions() {
        List<String> missing = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
                    != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_SCAN);
            }
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                    != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_CONNECT);
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
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
                    == PackageManager.PERMISSION_GRANTED
                    && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
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
        if (requestCode == REQUEST_BLUETOOTH_PERMISSIONS) {
            logger.event(
                    "permission_result",
                    null,
                    detail("all_required_granted", hasBluetoothPermissions()));
        }
    }

    private void copyEvidencePath() {
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText(
                "Test 19 private evidence path",
                logger.file().getAbsolutePath()));
        Toast.makeText(this, "Private path copied", Toast.LENGTH_SHORT).show();
    }

    private void setStatus(String value) {
        runOnUiThread(() -> {
            if (statusView != null) {
                statusView.setText(value);
            }
        });
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static JSONObject detail(String key, Object value) {
        JSONObject details = new JSONObject();
        EvidenceLogger.put(details, key, value);
        return details;
    }

    @Override
    protected void onDestroy() {
        scanner.close();
        cxr.close();
        try {
            logger.close();
        } catch (IOException ignored) {
        }
        super.onDestroy();
    }
}
