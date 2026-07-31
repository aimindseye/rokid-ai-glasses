package org.aimindseye.rokid.cxrqualification;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanRecord;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

final class BleDeviceScanner implements AutoCloseable {
    interface Listener {
        void onStatus(String value);
        void onCandidates(List<Candidate> candidates);
    }

    static final class Candidate {
        final BluetoothDevice device;
        final String displayName;
        final int rssi;
        final boolean service9100;
        final boolean bonded;

        Candidate(
                BluetoothDevice device,
                String displayName,
                int rssi,
                boolean service9100,
                boolean bonded) {
            this.device = device;
            this.displayName = displayName;
            this.rssi = rssi;
            this.service9100 = service9100;
            this.bonded = bonded;
        }

        boolean likelyRokid() {
            String lowered = displayName.toLowerCase(Locale.US);
            return service9100 || lowered.contains("rokid") || lowered.contains("glasses");
        }
    }

    private static final UUID SERVICE_9100 = UUID.fromString("00009100-0000-1000-8000-00805f9b34fb");
    private static final long SCAN_DURATION_MS = 20_000L;

    private final BluetoothAdapter adapter;
    private final EvidenceLogger logger;
    private final Listener listener;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, Candidate> candidates = new LinkedHashMap<>();

    private BluetoothLeScanner scanner;
    private boolean scanning;

    BleDeviceScanner(BluetoothAdapter adapter, EvidenceLogger logger, Listener listener) {
        this.adapter = adapter;
        this.logger = logger;
        this.listener = listener;
    }

    @SuppressLint("MissingPermission")
    void start() {
        if (scanning) {
            listener.onStatus("Discovery already running");
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            logger.event("discovery_blocked", null, detail("reason", "adapter_unavailable_or_disabled"));
            listener.onStatus("Bluetooth adapter unavailable or disabled");
            return;
        }

        candidates.clear();
        for (BluetoothDevice bonded : adapter.getBondedDevices()) {
            addCandidate(bonded, -127, false, true);
        }

        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            logger.event("discovery_blocked", null, detail("reason", "ble_scanner_unavailable"));
            listener.onStatus("BLE scanner unavailable");
            return;
        }

        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();
        scanning = true;
        logger.event("discovery_started", null, detail("duration_ms", SCAN_DURATION_MS));
        scanner.startScan(null, settings, callback);
        handler.postDelayed(this::stop, SCAN_DURATION_MS);
        listener.onStatus("Scanning for CXR/Style candidates for 20 seconds");
    }

    @SuppressLint("MissingPermission")
    void stop() {
        if (!scanning) {
            return;
        }
        scanning = false;
        handler.removeCallbacksAndMessages(null);
        if (scanner != null) {
            try {
                scanner.stopScan(callback);
            } catch (Exception ignored) {
            }
        }
        List<Candidate> result = sortedCandidates();
        JSONObject details = new JSONObject();
        EvidenceLogger.put(details, "candidate_count", result.size());
        EvidenceLogger.put(
                details,
                "likely_rokid_count",
                result.stream().filter(Candidate::likelyRokid).count());
        logger.event("discovery_completed", null, details);
        listener.onCandidates(result);
        listener.onStatus("Discovery complete: " + result.size() + " candidate(s)");
    }

    private final ScanCallback callback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            ScanRecord record = result.getScanRecord();
            boolean service9100 = false;
            if (record != null && record.getServiceUuids() != null) {
                for (ParcelUuid uuid : record.getServiceUuids()) {
                    if (SERVICE_9100.equals(uuid.getUuid())) {
                        service9100 = true;
                        break;
                    }
                }
            }
            addCandidate(
                    result.getDevice(),
                    result.getRssi(),
                    service9100,
                    result.getDevice().getBondState() == BluetoothDevice.BOND_BONDED);
        }

        @Override
        public void onScanFailed(int errorCode) {
            scanning = false;
            JSONObject details = new JSONObject();
            EvidenceLogger.put(details, "error_code", errorCode);
            logger.event("discovery_failed", null, details);
            listener.onStatus("BLE scan failed: " + errorCode);
        }
    };

    @SuppressLint("MissingPermission")
    private void addCandidate(BluetoothDevice device, int rssi, boolean service9100, boolean bonded) {
        String address;
        try {
            address = device.getAddress();
        } catch (SecurityException error) {
            address = "permission-denied-" + System.identityHashCode(device);
        }
        String name;
        try {
            name = device.getName();
        } catch (SecurityException error) {
            name = null;
        }
        if (name == null || name.isBlank()) {
            name = "Unnamed Bluetooth device";
        }
        Candidate candidate = new Candidate(device, name, rssi, service9100, bonded);
        Candidate previous = candidates.get(address);
        if (previous == null || rssi > previous.rssi || service9100) {
            candidates.put(address, candidate);
            JSONObject details = new JSONObject();
            EvidenceLogger.put(details, "display_name", name);
            EvidenceLogger.put(details, "rssi", rssi);
            EvidenceLogger.put(details, "service_9100", service9100);
            EvidenceLogger.put(details, "bonded", bonded);
            EvidenceLogger.put(details, "likely_rokid", candidate.likelyRokid());
            logger.event("candidate_discovered", address, details);
            listener.onCandidates(sortedCandidates());
        }
    }

    private List<Candidate> sortedCandidates() {
        List<Candidate> result = new ArrayList<>(candidates.values());
        result.sort(
                Comparator.comparing(Candidate::likelyRokid).reversed()
                        .thenComparingInt(item -> -item.rssi)
                        .thenComparing(item -> item.displayName));
        return result;
    }

    private static JSONObject detail(String key, Object value) {
        JSONObject object = new JSONObject();
        EvidenceLogger.put(object, key, value);
        return object;
    }

    @Override
    public void close() {
        stop();
    }
}
