package org.aimindseye.rokid.channelprobe;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;

import org.json.JSONObject;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

final class RfcommConnectionOnlyProbe implements AutoCloseable {
    interface Listener {
        void onStatus(String text);
    }

    private static final int CONNECT_TIMEOUT_SECONDS = 12;
    private static final int OPEN_HOLD_MILLIS = 1500;

    private final BluetoothAdapter adapter;
    private final EvidenceLogger logger;
    private final Listener listener;
    private final ExecutorService connectionExecutor =
            Executors.newSingleThreadExecutor();
    private final ScheduledExecutorService timeoutExecutor =
            Executors.newSingleThreadScheduledExecutor();

    private BluetoothSocket socket;
    private boolean started;

    RfcommConnectionOnlyProbe(
            BluetoothAdapter adapter,
            EvidenceLogger logger,
            Listener listener) {
        this.adapter = adapter;
        this.logger = logger;
        this.listener = listener;
    }

    @SuppressLint("MissingPermission")
    synchronized void start(RfcommConnectionOnlyHandoff handoff) {
        if (started) {
            listener.onStatus("r25.2.2.2: connection-only attempt already started");
            return;
        }
        started = true;
        if (adapter == null || !adapter.isEnabled()) {
            failBeforeSocket(handoff, "bluetooth adapter unavailable or disabled");
            return;
        }
        if (adapter.isDiscovering()) {
            adapter.cancelDiscovery();
        }

        JSONObject requested = handoff.sanitizedDetails();
        try {
            requested.put("connect_timeout_seconds", CONNECT_TIMEOUT_SECONDS);
            requested.put("open_hold_millis", OPEN_HOLD_MILLIS);
            requested.put("application_payload_read_count", 0);
            requested.put("application_payload_write_count", 0);
            requested.put("application_data_streams_obtained", false);
        } catch (Exception ignored) {
        }
        logger.event(
                "r25_2_2_2_rfcomm_connect_requested",
                handoff.runtimeAddress(),
                requested);
        listener.onStatus("r25.2.2.2: opening private-handoff RFCOMM socket");

        connectionExecutor.execute(() -> connectOnly(handoff));
    }

    @SuppressLint("MissingPermission")
    private void connectOnly(RfcommConnectionOnlyHandoff handoff) {
        BluetoothSocket localSocket = null;
        long startedAt = System.currentTimeMillis();
        boolean opened = false;
        try {
            BluetoothDevice device = adapter.getRemoteDevice(handoff.runtimeAddress());
            localSocket = device.createRfcommSocketToServiceRecord(handoff.runtimeUuid());
            synchronized (this) {
                socket = localSocket;
            }
            BluetoothSocket timeoutTarget = localSocket;
            timeoutExecutor.schedule(
                    () -> closeQuietly(timeoutTarget),
                    CONNECT_TIMEOUT_SECONDS,
                    TimeUnit.SECONDS);

            localSocket.connect();
            opened = localSocket.isConnected();
            JSONObject details = handoff.sanitizedDetails();
            details.put("connected", opened);
            details.put("connect_elapsed_ms", System.currentTimeMillis() - startedAt);
            details.put("max_receive_packet_size", localSocket.getMaxReceivePacketSize());
            details.put("max_transmit_packet_size", localSocket.getMaxTransmitPacketSize());
            details.put("application_payload_read_count", 0);
            details.put("application_payload_write_count", 0);
            details.put("application_data_streams_obtained", false);
            logger.event(
                    "r25_2_2_2_rfcomm_socket_open",
                    handoff.runtimeAddress(),
                    details);
            listener.onStatus("r25.2.2.2: socket open; zero payload; closing shortly");
            Thread.sleep(OPEN_HOLD_MILLIS);
        } catch (Exception error) {
            JSONObject details = handoff.sanitizedDetails();
            try {
                details.put("error_class", error.getClass().getName());
                details.put("message_sha256", Hashing.sha256(
                        String.valueOf(error.getMessage()).getBytes(StandardCharsets.UTF_8)));
                details.put("connect_elapsed_ms", System.currentTimeMillis() - startedAt);
                details.put("application_payload_read_count", 0);
                details.put("application_payload_write_count", 0);
                details.put("application_data_streams_obtained", false);
            } catch (Exception ignored) {
            }
            logger.event(
                    "r25_2_2_2_rfcomm_connect_failed",
                    handoff.runtimeAddress(),
                    details);
            listener.onStatus("r25.2.2.2: bounded RFCOMM failure; see private log");
        } finally {
            closeQuietly(localSocket);
            synchronized (this) {
                if (socket == localSocket) {
                    socket = null;
                }
            }
            JSONObject details = handoff.sanitizedDetails();
            try {
                details.put("socket_had_opened", opened);
                details.put("application_payload_read_count", 0);
                details.put("application_payload_write_count", 0);
                details.put("application_data_streams_obtained", false);
            } catch (Exception ignored) {
            }
            logger.event(
                    "r25_2_2_2_rfcomm_socket_closed",
                    handoff.runtimeAddress(),
                    details);
            listener.onStatus("r25.2.2.2: zero-payload socket lifecycle complete");
        }
    }

    private void failBeforeSocket(
            RfcommConnectionOnlyHandoff handoff,
            String message) {
        JSONObject details = handoff.sanitizedDetails();
        try {
            details.put("message_sha256", Hashing.sha256(
                    message.getBytes(StandardCharsets.UTF_8)));
            details.put("application_payload_read_count", 0);
            details.put("application_payload_write_count", 0);
            details.put("application_data_streams_obtained", false);
        } catch (Exception ignored) {
        }
        logger.event(
                "r25_2_2_2_probe_failed",
                handoff.runtimeAddress(),
                details);
        listener.onStatus("r25.2.2.2: probe unavailable; see private log");
    }

    private static void closeQuietly(BluetoothSocket target) {
        if (target == null) {
            return;
        }
        try {
            target.close();
        } catch (IOException ignored) {
        }
    }

    @Override
    public synchronized void close() {
        closeQuietly(socket);
        socket = null;
        connectionExecutor.shutdownNow();
        timeoutExecutor.shutdownNow();
    }
}
