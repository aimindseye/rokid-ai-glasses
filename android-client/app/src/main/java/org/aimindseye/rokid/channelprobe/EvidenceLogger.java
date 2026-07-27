package org.aimindseye.rokid.channelprobe;

import android.content.Context;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.UUID;

final class EvidenceLogger implements AutoCloseable {
    private static final String TAG = "R25Evidence";
    private final String runId = UUID.randomUUID().toString();
    private final String salt = UUID.randomUUID().toString();
    private final File file;
    private final BufferedWriter writer;

    EvidenceLogger(Context context) throws IOException {
        File dir = new File(context.getFilesDir(), "r25");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Unable to create evidence directory");
        }
        file = new File(dir, "r25-client-" + System.currentTimeMillis() + ".jsonl");
        writer = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, false));
        JSONObject details = new JSONObject();
        try {
            details.put("privacy", "device addresses pseudonymized with per-run salt");
        } catch (org.json.JSONException error) {
            throw new IOException("Unable to initialize evidence metadata", error);
        }
        event("run_started", null, details);
    }

    synchronized void event(String eventType, String deviceAddress, JSONObject details) {
        JSONObject record = new JSONObject();
        try {
            record.put("schema", "rokid.r25.client-event.v1");
            record.put("time_epoch_ms", System.currentTimeMillis());
            record.put("event_type", eventType);
            record.put("run_id", runId);
            if (deviceAddress != null && !deviceAddress.isBlank()) {
                record.put("device_id", pseudonym(deviceAddress));
            }
            record.put("details", details == null ? new JSONObject() : details);
            writer.write(record.toString());
            writer.newLine();
            writer.flush();
        } catch (Exception error) {
            Log.e(TAG, "Unable to write evidence event", error);
        }
    }

    String pseudonym(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest((salt + "\n" + value).getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder("dev-");
            for (int i = 0; i < 8; i++) {
                out.append(String.format(Locale.US, "%02x", bytes[i]));
            }
            return out.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    File file() {
        return file;
    }

    @Override
    public synchronized void close() throws IOException {
        writer.close();
    }
}
