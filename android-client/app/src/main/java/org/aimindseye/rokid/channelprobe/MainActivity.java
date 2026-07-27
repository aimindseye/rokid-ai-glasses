package org.aimindseye.rokid.channelprobe;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.ParcelUuid;
import android.provider.Settings;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class MainActivity extends Activity {
    private static final int REQUEST_BLUETOOTH_PERMISSIONS = 2501;

    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private EvidenceLogger logger;
    private GattReadOnlyProbe gattProbe;
    private TextView statusView;
    private ArrayAdapter<String> listAdapter;
    private final List<BluetoothDevice> visibleDevices = new ArrayList<>();
    private final Map<String, BluetoothDevice> uniqueDevices = new LinkedHashMap<>();
    private boolean scanning;

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
        gattProbe = new GattReadOnlyProbe(this, logger, this::setStatus);
        registerReceiver(sdpReceiver, new IntentFilter(BluetoothDevice.ACTION_UUID));
        setContentView(buildUi());
        ensurePermissions();
        describeEnvironment();
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Rokid Channel Probe — read-only r25 bootstrap");
        title.setTextSize(20f);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setText("Initializing");
        statusView.setPadding(0, dp(8), 0, dp(8));
        root.addView(statusView);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);

        Button scan = new Button(this);
        scan.setText("Start BLE scan");
        scan.setOnClickListener(v -> startScan());
        buttons.addView(scan, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button stop = new Button(this);
        stop.setText("Stop");
        stop.setOnClickListener(v -> stopScan());
        buttons.addView(stop, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button bonded = new Button(this);
        bonded.setText("Bonded + SDP");
        bonded.setOnClickListener(v -> inventoryBondedDevices());
        buttons.addView(bonded, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        root.addView(buttons);

        Button disconnect = new Button(this);
        disconnect.setText("Disconnect read-only probe");
        disconnect.setOnClickListener(v -> gattProbe.disconnect());
        root.addView(disconnect);

        Button copyPath = new Button(this);
        copyPath.setText("Copy private log path");
        copyPath.setOnClickListener(v -> copyEvidencePath());
        root.addView(copyPath);

        TextView instructions = new TextView(this);
        instructions.setText("Tap a discovered device to run a read-only GATT inventory. No Bluetooth writes or Internet access are implemented.");
        instructions.setPadding(0, dp(8), 0, dp(8));
        root.addView(instructions);

        ListView list = new ListView(this);
        listAdapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, new ArrayList<>());
        list.setAdapter(listAdapter);
        list.setOnItemClickListener((parent, view, position, id) -> {
            if (position >= 0 && position < visibleDevices.size()) {
                stopScan();
                gattProbe.connect(visibleDevices.get(position));
            }
        });
        root.addView(list, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        return root;
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
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_SCAN);
            }
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                missing.add(Manifest.permission.BLUETOOTH_CONNECT);
            }
        } else if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            missing.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (!missing.isEmpty()) {
            requestPermissions(missing.toArray(new String[0]), REQUEST_BLUETOOTH_PERMISSIONS);
        }
    }

    private boolean hasBluetoothPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                    && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void describeEnvironment() {
        JSONObject details = new JSONObject();
        try {
            details.put("sdk_int", Build.VERSION.SDK_INT);
            details.put("bluetooth_adapter_present", adapter != null);
            details.put("bluetooth_enabled", adapter != null && hasBluetoothPermissions() && adapter.isEnabled());
            details.put("airplane_mode", Settings.Global.getInt(getContentResolver(), Settings.Global.AIRPLANE_MODE_ON, 0));
        } catch (Exception ignored) {
        }
        logger.event("client_environment", null, details);
        setStatus("Private log: " + logger.file().getAbsolutePath());
    }

    @SuppressLint("MissingPermission")
    private void startScan() {
        if (!hasBluetoothPermissions()) {
            ensurePermissions();
            setStatus("Bluetooth permission required");
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            setStatus("Bluetooth adapter unavailable or disabled");
            return;
        }
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            setStatus("BLE scanner unavailable");
            return;
        }
        uniqueDevices.clear();
        visibleDevices.clear();
        listAdapter.clear();
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();
        scanner.startScan(null, settings, scanCallback);
        scanning = true;
        logger.event("ble_scan_started", null, new JSONObject());
        setStatus("Scanning BLE advertisements");
    }

    @SuppressLint("MissingPermission")
    private void stopScan() {
        if (scanning && scanner != null && hasBluetoothPermissions()) {
            scanner.stopScan(scanCallback);
        }
        if (scanning) {
            logger.event("ble_scan_stopped", null, new JSONObject());
        }
        scanning = false;
    }

    @SuppressLint("MissingPermission")
    private void inventoryBondedDevices() {
        if (!hasBluetoothPermissions()) {
            ensurePermissions();
            return;
        }
        if (adapter == null) {
            return;
        }
        Set<BluetoothDevice> bonded = adapter.getBondedDevices();
        JSONArray rows = new JSONArray();
        for (BluetoothDevice device : bonded) {
            JSONObject row = new JSONObject();
            try {
                row.put("device_id", logger.pseudonym(device.getAddress()));
                row.put("name", safeName(device));
                row.put("type", device.getType());
                row.put("bond_state", device.getBondState());
                ParcelUuid[] known = device.getUuids();
                JSONArray uuids = new JSONArray();
                if (known != null) {
                    for (ParcelUuid uuid : known) {
                        uuids.put(uuid.toString());
                    }
                }
                row.put("cached_uuids", uuids);
            } catch (Exception ignored) {
            }
            rows.put(row);
            device.fetchUuidsWithSdp();
            addOrUpdateDevice(device, "bonded");
        }
        JSONObject details = new JSONObject();
        try {
            details.put("count", bonded.size());
            details.put("devices", rows);
        } catch (Exception ignored) {
        }
        logger.event("bonded_device_inventory", null, details);
        setStatus("Bonded devices inventoried; SDP UUID refresh requested");
    }

    @SuppressLint("MissingPermission")
    private String safeName(BluetoothDevice device) {
        String name = device.getName();
        return name == null || name.isBlank() ? "unnamed" : name;
    }

    @SuppressLint("MissingPermission")
    private void addOrUpdateDevice(BluetoothDevice device, String source) {
        String key = device.getAddress();
        uniqueDevices.put(key, device);
        visibleDevices.clear();
        visibleDevices.addAll(uniqueDevices.values());
        listAdapter.clear();
        for (BluetoothDevice item : visibleDevices) {
            listAdapter.add(safeName(item) + "  [" + logger.pseudonym(item.getAddress()) + "]");
        }
        listAdapter.notifyDataSetChanged();

        JSONObject details = new JSONObject();
        try {
            details.put("source", source);
            details.put("name", safeName(device));
            details.put("type", device.getType());
            details.put("bond_state", device.getBondState());
        } catch (Exception ignored) {
        }
        logger.event("device_observed", device.getAddress(), details);
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            BluetoothDevice device = result.getDevice();
            JSONObject details = new JSONObject();
            try {
                details.put("callback_type", callbackType);
                details.put("rssi", result.getRssi());
                details.put("connectable", Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && result.isConnectable());
                JSONArray serviceUuids = new JSONArray();
                if (result.getScanRecord() != null && result.getScanRecord().getServiceUuids() != null) {
                    for (ParcelUuid uuid : result.getScanRecord().getServiceUuids()) {
                        serviceUuids.put(uuid.toString());
                    }
                }
                details.put("advertised_service_uuids", serviceUuids);
                details.put("manufacturer_data_count", result.getScanRecord() == null ? 0 : result.getScanRecord().getManufacturerSpecificData().size());
            } catch (Exception ignored) {
            }
            logger.event("ble_advertisement", device.getAddress(), details);
            runOnUiThread(() -> addOrUpdateDevice(device, "ble_scan"));
        }

        @Override
        public void onScanFailed(int errorCode) {
            JSONObject details = new JSONObject();
            try {
                details.put("error_code", errorCode);
            } catch (Exception ignored) {
            }
            logger.event("ble_scan_failed", null, details);
            setStatus("BLE scan failed: " + errorCode);
        }
    };

    private final BroadcastReceiver sdpReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (!BluetoothDevice.ACTION_UUID.equals(intent.getAction())) {
                return;
            }
            BluetoothDevice device;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice.class);
            } else {
                device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
            }
            if (device == null) {
                return;
            }
            ParcelUuid[] uuids;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                uuids = intent.getParcelableArrayExtra(BluetoothDevice.EXTRA_UUID, ParcelUuid.class);
            } else {
                Object[] raw = intent.getParcelableArrayExtra(BluetoothDevice.EXTRA_UUID);
                if (raw == null) {
                    uuids = null;
                } else {
                    uuids = new ParcelUuid[raw.length];
                    for (int i = 0; i < raw.length; i++) {
                        uuids[i] = (ParcelUuid) raw[i];
                    }
                }
            }
            JSONArray list = new JSONArray();
            if (uuids != null) {
                for (ParcelUuid uuid : uuids) {
                    list.put(uuid.toString());
                }
            }
            JSONObject details = new JSONObject();
            try {
                details.put("uuids", list);
            } catch (Exception ignored) {
            }
            logger.event("sdp_uuid_result", device.getAddress(), details);
            setStatus("SDP UUID result for " + safeName(device) + ": " + list.length());
        }
    };

    private void copyEvidencePath() {
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText("r25 evidence path", logger.file().getAbsolutePath()));
        Toast.makeText(this, "Private log path copied", Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onDestroy() {
        stopScan();
        gattProbe.disconnect();
        unregisterReceiver(sdpReceiver);
        try {
            logger.close();
        } catch (IOException ignored) {
        }
        super.onDestroy();
    }
}
