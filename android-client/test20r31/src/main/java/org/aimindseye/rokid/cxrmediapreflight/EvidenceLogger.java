package org.aimindseye.rokid.cxrmediapreflight;

import android.content.Context;
import android.os.SystemClock;
import android.util.Log;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

final class EvidenceLogger {
    private static final String TAG = "Test20R31";
    private final File outputFile;
    private final String runId;
    private final String firmwareLabel;

    EvidenceLogger(Context context, String runId, String firmwareLabel) throws IOException {
        this.runId = sanitize(runId);
        this.firmwareLabel = firmwareLabel == null ? "unspecified" : firmwareLabel.trim();
        File root = new File(context.getExternalFilesDir(null), "test20-r3-1");
        if (!root.exists() && !root.mkdirs()) {
            throw new IOException("Cannot create evidence directory: " + root);
        }
        outputFile = new File(root, "test20-r3-1-" + this.runId + ".jsonl");
    }

    File getOutputFile() { return outputFile; }

    synchronized void event(String eventType, JSONObject details) {
        JSONObject record = new JSONObject();
        try {
            record.put("schema", Test20R31Contract.EVENT_SCHEMA);
            record.put("time_epoch_ms", System.currentTimeMillis());
            record.put("elapsed_realtime_ms", SystemClock.elapsedRealtime());
            record.put("run_id", runId);
            record.put("firmware_label", firmwareLabel);
            record.put("event_type", eventType);
            record.put("details", details == null ? new JSONObject() : details);
        } catch (JSONException error) {
            Log.e(TAG, "Cannot construct evidence event", error);
            return;
        }
        String line = record.toString();
        Log.i(TAG, line);
        try (FileWriter writer = new FileWriter(outputFile, true)) {
            writer.write(line);
            writer.write('\n');
        } catch (IOException error) {
            Log.e(TAG, "Cannot append evidence event", error);
        }
    }

    static JSONObject details(Object... values) {
        JSONObject object = new JSONObject();
        for (int index = 0; index + 1 < values.length; index += 2) {
            try { object.put(String.valueOf(values[index]), values[index + 1]); }
            catch (JSONException ignored) { }
        }
        return object;
    }

    static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] output = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder text = new StringBuilder();
            for (byte item : output) text.append(String.format("%02x", item & 0xff));
            return text.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static String sanitize(String value) {
        String normalized = value == null ? "run" : value.replaceAll("[^A-Za-z0-9._-]", "_");
        return normalized.isBlank() ? "run" : normalized;
    }
}
