package org.aimindseye.rokid.cxrqualification;

import android.content.Context;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

final class EvidenceLogger implements AutoCloseable {
    private static final String TAG = "Test19Cxr";
    private final String runId = UUID.randomUUID().toString();
    private final String salt = UUID.randomUUID().toString();
    private final File file;
    private final BufferedWriter writer;
    private String phase = "unassigned";

    EvidenceLogger(Context context) throws IOException {
        File directory = new File(context.getFilesDir(), "test19");
        if (!directory.exists() && !directory.mkdirs()) {
            throw new IOException("Unable to create Test 19 evidence directory");
        }
        file = new File(directory, "test19-client-" + System.currentTimeMillis() + ".jsonl");
        writer = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, false));
        JSONObject details = new JSONObject();
        put(details, "privacy", "Bluetooth addresses and account-like values are per-run pseudonyms");
        put(details, "internet_permission_declared", false);
        event("run_started", null, details);
    }

    synchronized void setPhase(String value) {
        phase = value == null || value.isBlank() ? "unassigned" : value;
        JSONObject details = new JSONObject();
        put(details, "phase", phase);
        event("phase_marker", null, details);
    }

    synchronized String phase() {
        return phase;
    }

    synchronized void event(String eventType, String sensitiveIdentity, JSONObject details) {
        JSONObject record = new JSONObject();
        try {
            record.put("schema", "rokid.test19.cxr-client-event.v1");
            record.put("time_epoch_ms", System.currentTimeMillis());
            record.put("event_type", eventType);
            record.put("run_id", runId);
            record.put("phase", phase);
            if (sensitiveIdentity != null && !sensitiveIdentity.isBlank()) {
                record.put("device_id", pseudonym(sensitiveIdentity));
            }
            record.put("details", details == null ? new JSONObject() : details);
            writer.write(record.toString());
            writer.newLine();
            writer.flush();
            Log.i(TAG, eventType + " phase=" + phase);
        } catch (Exception error) {
            Log.e(TAG, "Unable to write Test 19 evidence event", error);
        }
    }

    String pseudonym(String value) {
        return "id-" + Hashing.sha256(salt + "\n" + value).substring(0, 16);
    }

    File file() {
        return file;
    }

    static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (Exception ignored) {
        }
    }

    @Override
    public synchronized void close() throws IOException {
        writer.close();
    }
}
