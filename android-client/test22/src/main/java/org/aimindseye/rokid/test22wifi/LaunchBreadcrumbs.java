package org.aimindseye.rokid.test22wifi;

import android.content.Context;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * TEST22_R4_3_3_PERSISTENT_LAUNCH_BREADCRUMBS
 *
 * Bounded, app-owned lifecycle journal. No Wi-Fi credentials, serial numbers,
 * Bluetooth identities, execution tokens, backend addresses, or probe payloads
 * are written.
 */
public final class LaunchBreadcrumbs {
    public static final String JOURNAL_NAME =
            "test22-r4-3-3-launch-breadcrumbs.jsonl";
    public static final String LAUNCH_ID_NAME =
            "test22-r4-3-3-current-launch-id.txt";
    public static final String SCHEMA =
            "rokid.test22.r4.3.3.launch-breadcrumb.v1";

    private static final String TAG = "Test22LaunchBreadcrumb";
    private static final Object LOCK = new Object();

    private LaunchBreadcrumbs() {
    }

    public static String beginLaunch(Context context, String action) {
        synchronized (LOCK) {
            String launchId =
                    Long.toString(System.currentTimeMillis())
                            + "-"
                            + Process.myPid();

            File directory = externalDirectory(context);
            if (directory == null) {
                return launchId;
            }

            try {
                if (!directory.isDirectory() && !directory.mkdirs()) {
                    Log.e(TAG, "breadcrumb directory create failed");
                    return launchId;
                }

                writeBytes(
                        new File(directory, LAUNCH_ID_NAME),
                        (launchId + "\n").getBytes(StandardCharsets.UTF_8),
                        false
                );

                writeEvent(
                        directory,
                        launchId,
                        "PACKAGE_REPLACED_RECEIVER_ENTERED",
                        safe(action),
                        false
                );
            } catch (Throwable error) {
                Log.e(TAG, "beginLaunch:" + error.getClass().getName());
            }

            return launchId;
        }
    }

    public static void record(
            Context context,
            String event,
            String detail
    ) {
        synchronized (LOCK) {
            File directory = externalDirectory(context);
            if (directory == null) {
                return;
            }

            try {
                if (!directory.isDirectory() && !directory.mkdirs()) {
                    Log.e(TAG, "breadcrumb directory create failed");
                    return;
                }

                writeEvent(
                        directory,
                        readLaunchId(directory),
                        safe(event),
                        safe(detail),
                        true
                );
            } catch (Throwable error) {
                Log.e(
                        TAG,
                        "record:"
                                + safe(event)
                                + ":"
                                + error.getClass().getName()
                );
            }
        }
    }

    private static File externalDirectory(Context context) {
        try {
            return context.getExternalFilesDir(null);
        } catch (Throwable error) {
            Log.e(TAG, "externalDirectory:" + error.getClass().getName());
            return null;
        }
    }

    private static String readLaunchId(File directory) {
        File file = new File(directory, LAUNCH_ID_NAME);
        if (!file.isFile()) {
            return "NO_LAUNCH_ID";
        }

        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[(int) Math.min(file.length(), 256L)];
            int count = input.read(buffer);
            if (count <= 0) {
                return "NO_LAUNCH_ID";
            }
            return new String(
                    buffer,
                    0,
                    count,
                    StandardCharsets.UTF_8
            ).trim();
        } catch (Throwable error) {
            return "NO_LAUNCH_ID";
        }
    }

    private static void writeEvent(
            File directory,
            String launchId,
            String event,
            String detail,
            boolean append
    ) throws Exception {
        JSONObject object = new JSONObject();
        object.put("schema", SCHEMA);
        object.put("source_version", "r4.3.3");
        object.put("launch_id", safe(launchId));
        object.put("event", safe(event));
        object.put("detail", safe(detail));
        object.put("wall_time_ms", System.currentTimeMillis());
        object.put("elapsed_realtime_ms", SystemClock.elapsedRealtime());
        object.put("pid", Process.myPid());
        object.put("thread", safe(Thread.currentThread().getName()));

        byte[] line =
                (object.toString() + "\n")
                        .getBytes(StandardCharsets.UTF_8);

        writeBytes(
                new File(directory, JOURNAL_NAME),
                line,
                append
        );
    }

    private static void writeBytes(
            File file,
            byte[] value,
            boolean append
    ) throws Exception {
        try (FileOutputStream output =
                     new FileOutputStream(file, append)) {
            output.write(value);
            output.flush();
            output.getFD().sync();
        }
    }

    private static String safe(String value) {
        if (value == null) {
            return "";
        }

        String cleaned =
                value.replace('\n', ' ')
                        .replace('\r', ' ')
                        .trim();

        if (cleaned.length() > 240) {
            return cleaned.substring(0, 240);
        }

        return cleaned;
    }
}
