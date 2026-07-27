package org.aimindseye.rokid.channelprobe;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanRecord;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.os.SystemClock;
import android.util.SparseArray;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;

final class BleStockAssistCorrelationProbe implements AutoCloseable {
    interface StatusSink {
        void setStatus(String value);
    }

    enum Phase {
        STOCK_DISABLED_BASELINE("stock_disabled_baseline", 20_000L),
        STOCK_ASSIST_WINDOW("stock_assist_window", 60_000L),
        POST_STOCK_HANDOFF("post_stock_handoff", 20_000L);

        final String wireName;
        final long durationMs;

        Phase(String wireName, long durationMs) {
            this.wireName = wireName;
            this.durationMs = durationMs;
        }
    }

    private final Context context;
    private final BluetoothAdapter adapter;
    private final EvidenceLogger logger;
    private final StatusSink statusSink;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final EnumSet<Phase> completed = EnumSet.noneOf(Phase.class);
    private final byte[] correlationKey = new byte[32];
    private final File correlationKeyFile;

    private BluetoothLeScanner scanner;
    private Phase activePhase;
    private boolean scanning;
    private long phaseStartElapsedMs;
    private long advertisementCount;
    private int uniqueDeviceCount;
    private final java.util.HashSet<String> uniqueDevicePseudonyms = new java.util.HashSet<>();
    private Runnable scheduledStop;

    BleStockAssistCorrelationProbe(
            Context context,
            BluetoothAdapter adapter,
            EvidenceLogger logger,
            StatusSink statusSink) {
        this.context = context;
        this.adapter = adapter;
        this.logger = logger;
        this.statusSink = statusSink;
        new SecureRandom().nextBytes(correlationKey);
        File parent = logger.file().getParentFile();
        correlationKeyFile = new File(parent == null ? new File(".") : parent, "r25.2.2-correlation-key-private.hex");
        writeCorrelationKey();
        JSONObject initialized = new JSONObject();
        put(initialized, "correlation_key_sha256", Hashing.sha256(correlationKey));
        put(initialized, "correlation_key_published", false);
        put(initialized, "raw_bluetooth_address_logged", false);
        logger.event("r25_2_2_session_initialized", null, initialized);
    }

    boolean isScanning() {
        return scanning;
    }

    @SuppressLint("MissingPermission")
    void startPhase(Phase phase) {
        if (scanning) {
            JSONObject details = new JSONObject();
            put(details, "requested_phase", phase.wireName);
            put(details, "active_phase", activePhase == null ? JSONObject.NULL : activePhase.wireName);
            put(details, "reason", "already_active");
            logger.event("r25_2_2_scan_start_rejected", null, details);
            statusSink.setStatus("r25.2.2: scan already active; wait or stop it first");
            return;
        }

        String sequenceError = sequenceError(phase);
        if (sequenceError != null) {
            JSONObject details = new JSONObject();
            put(details, "requested_phase", phase.wireName);
            put(details, "reason", sequenceError);
            logger.event("r25_2_2_phase_start_rejected", null, details);
            statusSink.setStatus("r25.2.2: " + sequenceError);
            return;
        }

        if (adapter == null || !adapter.isEnabled()) {
            JSONObject details = new JSONObject();
            put(details, "phase", phase.wireName);
            put(details, "reason", "adapter_unavailable_or_disabled");
            logger.event("r25_2_2_phase_start_failed", null, details);
            statusSink.setStatus("r25.2.2: Bluetooth adapter unavailable or disabled");
            return;
        }

        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            JSONObject details = new JSONObject();
            put(details, "phase", phase.wireName);
            put(details, "reason", "scanner_unavailable");
            logger.event("r25_2_2_phase_start_failed", null, details);
            statusSink.setStatus("r25.2.2: BLE scanner unavailable");
            return;
        }

        activePhase = phase;
        phaseStartElapsedMs = SystemClock.elapsedRealtime();
        advertisementCount = 0L;
        uniqueDevicePseudonyms.clear();
        uniqueDeviceCount = 0;

        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .setReportDelay(0L)
                .build();

        JSONObject requested = new JSONObject();
        put(requested, "phase", phase.wireName);
        put(requested, "duration_ms", phase.durationMs);
        logger.event("r25_2_2_scan_start_requested", null, requested);

        try {
            scanner.startScan(null, settings, scanCallback);
            scanning = true;
        } catch (RuntimeException error) {
            JSONObject details = new JSONObject();
            put(details, "phase", phase.wireName);
            put(details, "error_class", error.getClass().getName());
            put(details, "message_sha256", Hashing.sha256(String.valueOf(error.getMessage()).getBytes(StandardCharsets.UTF_8)));
            logger.event("r25_2_2_phase_start_failed", null, details);
            activePhase = null;
            statusSink.setStatus("r25.2.2: scanner start failed; see private log");
            return;
        }

        JSONObject started = new JSONObject();
        put(started, "phase", phase.wireName);
        put(started, "duration_ms", phase.durationMs);
        logger.event("r25_2_2_phase_started", null, started);
        logger.event("r25_2_2_ble_scan_started", null, started);
        statusSink.setStatus("r25.2.2: " + phase.wireName + " running for " + (phase.durationMs / 1000L) + " seconds");

        scheduledStop = () -> stopCurrentPhase("duration_complete", true);
        mainHandler.postDelayed(scheduledStop, phase.durationMs);
    }

    void abortCurrentPhase() {
        stopCurrentPhase("operator_abort", false);
    }

    void resetSession() {
        stopCurrentPhase("session_reset", false);
        completed.clear();
        JSONObject details = new JSONObject();
        put(details, "completed_phase_count", 0);
        logger.event("r25_2_2_session_reset", null, details);
        statusSink.setStatus("r25.2.2: session reset; begin with Hi Rokid disabled");
    }

    @SuppressLint("MissingPermission")
    private void stopCurrentPhase(String reason, boolean completePhase) {
        if (scheduledStop != null) {
            mainHandler.removeCallbacks(scheduledStop);
            scheduledStop = null;
        }

        Phase phase = activePhase;
        if (scanning && scanner != null) {
            try {
                scanner.stopScan(scanCallback);
            } catch (RuntimeException error) {
                JSONObject details = new JSONObject();
                put(details, "phase", phase == null ? JSONObject.NULL : phase.wireName);
                put(details, "error_class", error.getClass().getName());
                logger.event("r25_2_2_scan_stop_failed", null, details);
            }
        }

        if (!scanning && phase == null) {
            return;
        }

        scanning = false;
        long elapsed = phaseStartElapsedMs == 0L ? 0L : Math.max(0L, SystemClock.elapsedRealtime() - phaseStartElapsedMs);

        JSONObject stopped = new JSONObject();
        put(stopped, "phase", phase == null ? JSONObject.NULL : phase.wireName);
        put(stopped, "reason", reason);
        put(stopped, "elapsed_ms", elapsed);
        put(stopped, "advertisement_count", advertisementCount);
        put(stopped, "unique_device_count", uniqueDeviceCount);
        logger.event("r25_2_2_ble_scan_stopped", null, stopped);

        if (phase != null && completePhase) {
            completed.add(phase);
            logger.event("r25_2_2_phase_complete", null, stopped);
            if (phase == Phase.POST_STOCK_HANDOFF) {
                JSONObject complete = new JSONObject();
                put(complete, "phase_count", completed.size());
                put(complete, "gatt_attempted", false);
                put(complete, "rfcomm_attempted", false);
                logger.event("r25_2_2_capture_complete", null, complete);
                statusSink.setStatus("r25.2.2: all three phases complete; return to Terminal");
            } else if (phase == Phase.STOCK_DISABLED_BASELINE) {
                statusSink.setStatus("r25.2.2: OFF baseline complete; start the stock-assist window, then return to Terminal");
            } else {
                statusSink.setStatus("r25.2.2: stock-assist window complete; wait for Terminal to disable Hi Rokid");
            }
        } else {
            JSONObject aborted = new JSONObject();
            put(aborted, "phase", phase == null ? JSONObject.NULL : phase.wireName);
            put(aborted, "reason", reason);
            logger.event("r25_2_2_phase_aborted", null, aborted);
            statusSink.setStatus("r25.2.2: phase aborted; reset session before retrying");
        }

        activePhase = null;
        phaseStartElapsedMs = 0L;
        advertisementCount = 0L;
        uniqueDevicePseudonyms.clear();
        uniqueDeviceCount = 0;
    }

    private String sequenceError(Phase phase) {
        if (phase == Phase.STOCK_DISABLED_BASELINE) {
            return completed.isEmpty() ? null : "reset the session before another stock-disabled baseline";
        }
        if (phase == Phase.STOCK_ASSIST_WINDOW) {
            if (!completed.contains(Phase.STOCK_DISABLED_BASELINE)) {
                return "complete the stock-disabled baseline first";
            }
            return completed.contains(Phase.STOCK_ASSIST_WINDOW)
                    ? "transition phase already completed; reset to repeat"
                    : null;
        }
        if (!completed.contains(Phase.STOCK_ASSIST_WINDOW)) {
            return "complete the power-on transition first";
        }
        return completed.contains(Phase.POST_STOCK_HANDOFF)
                ? "steady phase already completed; reset to repeat"
                : null;
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            recordAdvertisement(callbackType, result);
        }

        @Override
        public void onBatchScanResults(List<ScanResult> results) {
            for (ScanResult result : results) {
                recordAdvertisement(ScanSettings.CALLBACK_TYPE_ALL_MATCHES, result);
            }
        }

        @Override
        public void onScanFailed(int errorCode) {
            JSONObject details = new JSONObject();
            put(details, "phase", activePhase == null ? JSONObject.NULL : activePhase.wireName);
            put(details, "error_code", errorCode);
            logger.event("r25_2_2_ble_scan_failed", null, details);
            statusSink.setStatus("r25.2.2: BLE scan failed: " + errorCode);
            stopCurrentPhase("scan_failed", false);
        }
    };

    @SuppressLint("MissingPermission")
    private void recordAdvertisement(int callbackType, ScanResult result) {
        if (!scanning || activePhase == null || result == null || result.getDevice() == null) {
            return;
        }

        BluetoothDevice device = result.getDevice();
        String pseudonym = logger.pseudonym(device.getAddress());
        if (uniqueDevicePseudonyms.add(pseudonym)) {
            uniqueDeviceCount = uniqueDevicePseudonyms.size();
        }
        advertisementCount += 1L;

        ScanRecord record = result.getScanRecord();
        byte[] raw = record == null ? null : record.getBytes();

        List<String> serviceUuids = new ArrayList<>();
        if (record != null && record.getServiceUuids() != null) {
            for (ParcelUuid uuid : record.getServiceUuids()) {
                serviceUuids.add(uuid.toString().toLowerCase(java.util.Locale.US));
            }
        }
        Collections.sort(serviceUuids);

        List<ManufacturerEntry> manufacturerEntries = manufacturerEntries(record);
        List<ServiceDataEntry> serviceDataEntries = serviceDataEntries(record);

        String payloadCanonical = payloadCanonical(serviceUuids, manufacturerEntries, serviceDataEntries);
        String structureCanonical = structureCanonical(serviceUuids, manufacturerEntries, serviceDataEntries);

        JSONObject details = new JSONObject();
        put(details, "phase", activePhase.wireName);
        put(details, "phase_elapsed_ms", Math.max(0L, SystemClock.elapsedRealtime() - phaseStartElapsedMs));
        put(details, "callback_type", callbackType);
        put(details, "rssi", result.getRssi());
        put(details, "connectable", Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && result.isConnectable());
        put(details, "device_type", device.getType());
        put(details, "bond_state", device.getBondState());
        put(details, "address_hmac_sha256", hmacAddress(device.getAddress()));
        put(details, "name_present", safeName(device) != null);
        String name = safeName(device);
        put(details, "name_length", name == null ? 0 : name.length());
        put(details, "name_sha256", name == null ? JSONObject.NULL : Hashing.sha256(name.getBytes(StandardCharsets.UTF_8)));
        put(details, "raw_record_length", raw == null ? 0 : raw.length);
        put(details, "raw_record_sha256", raw == null ? JSONObject.NULL : Hashing.sha256(raw));
        put(details, "payload_fingerprint_sha256", Hashing.sha256(payloadCanonical.getBytes(StandardCharsets.UTF_8)));
        put(details, "structure_fingerprint_sha256", Hashing.sha256(structureCanonical.getBytes(StandardCharsets.UTF_8)));
        put(details, "advertised_service_uuids", new JSONArray(serviceUuids));
        put(details, "manufacturer_data", manufacturerJson(manufacturerEntries));
        put(details, "service_data", serviceDataJson(serviceDataEntries));
        put(details, "manufacturer_data_count", manufacturerEntries.size());
        put(details, "service_data_count", serviceDataEntries.size());
        put(details, "tx_power_level", record == null ? Integer.MIN_VALUE : record.getTxPowerLevel());
        logger.event("r25_2_2_ble_advertisement", null, details);

        if (advertisementCount == 1L || advertisementCount % 250L == 0L) {
            statusSink.setStatus(
                    "r25.2.2: " + activePhase.wireName
                            + " — " + advertisementCount + " advertisements, "
                            + uniqueDeviceCount + " devices");
        }
    }

    @SuppressLint("MissingPermission")
    private String safeName(BluetoothDevice device) {
        try {
            String value = device.getName();
            return value == null || value.isBlank() ? null : value;
        } catch (SecurityException ignored) {
            return null;
        }
    }

    private static List<ManufacturerEntry> manufacturerEntries(ScanRecord record) {
        List<ManufacturerEntry> entries = new ArrayList<>();
        if (record == null) {
            return entries;
        }
        SparseArray<byte[]> values = record.getManufacturerSpecificData();
        for (int index = 0; index < values.size(); index++) {
            int companyId = values.keyAt(index);
            byte[] payload = values.valueAt(index);
            entries.add(new ManufacturerEntry(companyId, payload));
        }
        entries.sort(Comparator.comparingInt(item -> item.companyId));
        return entries;
    }

    private static List<ServiceDataEntry> serviceDataEntries(ScanRecord record) {
        List<ServiceDataEntry> entries = new ArrayList<>();
        if (record == null || record.getServiceData() == null) {
            return entries;
        }
        for (Map.Entry<ParcelUuid, byte[]> item : record.getServiceData().entrySet()) {
            entries.add(new ServiceDataEntry(
                    item.getKey().toString().toLowerCase(java.util.Locale.US),
                    item.getValue()));
        }
        entries.sort(Comparator.comparing(item -> item.uuid));
        return entries;
    }

    private static String payloadCanonical(
            List<String> serviceUuids,
            List<ManufacturerEntry> manufacturers,
            List<ServiceDataEntry> serviceData) {
        StringBuilder value = new StringBuilder("services=");
        for (String uuid : serviceUuids) {
            value.append(uuid).append(',');
        }
        value.append("|manufacturer=");
        for (ManufacturerEntry item : manufacturers) {
            value.append(item.companyId)
                    .append(':')
                    .append(item.payload == null ? 0 : item.payload.length)
                    .append(':')
                    .append(item.payload == null ? "null" : Hashing.sha256(item.payload))
                    .append(',');
        }
        value.append("|service_data=");
        for (ServiceDataEntry item : serviceData) {
            value.append(item.uuid)
                    .append(':')
                    .append(item.payload == null ? 0 : item.payload.length)
                    .append(':')
                    .append(item.payload == null ? "null" : Hashing.sha256(item.payload))
                    .append(',');
        }
        return value.toString();
    }

    private static String structureCanonical(
            List<String> serviceUuids,
            List<ManufacturerEntry> manufacturers,
            List<ServiceDataEntry> serviceData) {
        StringBuilder value = new StringBuilder("services=");
        for (String uuid : serviceUuids) {
            value.append(uuid).append(',');
        }
        value.append("|manufacturer=");
        for (ManufacturerEntry item : manufacturers) {
            value.append(item.companyId)
                    .append(':')
                    .append(item.payload == null ? 0 : item.payload.length)
                    .append(',');
        }
        value.append("|service_data=");
        for (ServiceDataEntry item : serviceData) {
            value.append(item.uuid)
                    .append(':')
                    .append(item.payload == null ? 0 : item.payload.length)
                    .append(',');
        }
        return value.toString();
    }

    private static JSONArray manufacturerJson(List<ManufacturerEntry> entries) {
        JSONArray output = new JSONArray();
        for (ManufacturerEntry item : entries) {
            JSONObject row = new JSONObject();
            put(row, "company_id", item.companyId);
            put(row, "payload_length", item.payload == null ? 0 : item.payload.length);
            put(row, "payload_sha256", item.payload == null ? JSONObject.NULL : Hashing.sha256(item.payload));
            output.put(row);
        }
        return output;
    }

    private static JSONArray serviceDataJson(List<ServiceDataEntry> entries) {
        JSONArray output = new JSONArray();
        for (ServiceDataEntry item : entries) {
            JSONObject row = new JSONObject();
            put(row, "uuid", item.uuid);
            put(row, "payload_length", item.payload == null ? 0 : item.payload.length);
            put(row, "payload_sha256", item.payload == null ? JSONObject.NULL : Hashing.sha256(item.payload));
            output.put(row);
        }
        return output;
    }

    private void writeCorrelationKey() {
        try (FileOutputStream output = new FileOutputStream(correlationKeyFile, false)) {
            output.write(hex(correlationKey).getBytes(StandardCharsets.US_ASCII));
            output.write('\n');
            output.flush();
        } catch (Exception error) {
            JSONObject details = new JSONObject();
            put(details, "error_class", error.getClass().getName());
            put(details, "message_sha256", Hashing.sha256(String.valueOf(error.getMessage()).getBytes(StandardCharsets.UTF_8)));
            logger.event("r25_2_2_correlation_key_write_failed", null, details);
        }
    }

    private String hmacAddress(String address) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(correlationKey, "HmacSHA256"));
            return hex(mac.doFinal(address.toUpperCase(java.util.Locale.US).getBytes(StandardCharsets.US_ASCII)));
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException(error);
        }
    }

    private static String hex(byte[] value) {
        StringBuilder output = new StringBuilder(value.length * 2);
        for (byte item : value) output.append(String.format(java.util.Locale.US, "%02x", item));
        return output.toString();
    }

    private static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (Exception ignored) {
        }
    }

    @Override
    public void close() {
        stopCurrentPhase("activity_destroyed", false);
        mainHandler.removeCallbacksAndMessages(null);
    }

    private static final class ManufacturerEntry {
        final int companyId;
        final byte[] payload;

        ManufacturerEntry(int companyId, byte[] payload) {
            this.companyId = companyId;
            this.payload = payload;
        }
    }

    private static final class ServiceDataEntry {
        final String uuid;
        final byte[] payload;

        ServiceDataEntry(String uuid, byte[] payload) {
            this.uuid = uuid;
            this.payload = payload;
        }
    }
}
