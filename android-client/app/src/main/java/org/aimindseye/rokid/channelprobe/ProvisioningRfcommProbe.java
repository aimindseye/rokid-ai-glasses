package org.aimindseye.rokid.channelprobe;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothSocket;
import android.content.Context;

import org.json.JSONObject;

import java.io.IOException;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

final class ProvisioningRfcommProbe implements AutoCloseable {
    interface Listener {
        void onStatus(String text);
    }

    private static final UUID SERVICE_UUID = UUID.fromString("00009100-0000-1000-8000-00805f9b34fb");
    private static final UUID CONNECTION_INFO_UUID = UUID.fromString("00009301-0000-1000-8000-00805f9b34fb");
    private static final int CONNECT_TIMEOUT_SECONDS = 10;
    private static final int CONNECT_HOLD_MILLIS = 2000;

    private final Context context;
    private final BluetoothAdapter adapter;
    private final EvidenceLogger logger;
    private final Listener listener;
    private final ExecutorService connectionExecutor = Executors.newSingleThreadExecutor();
    private final ScheduledExecutorService timeoutExecutor = Executors.newSingleThreadScheduledExecutor();

    private BluetoothGatt gatt;
    private BluetoothSocket socket;
    private String sourceAddress;
    private boolean mtuHandled;

    ProvisioningRfcommProbe(
            Context context,
            BluetoothAdapter adapter,
            EvidenceLogger logger,
            Listener listener) {
        this.context = context;
        this.adapter = adapter;
        this.logger = logger;
        this.listener = listener;
    }

    @SuppressLint("MissingPermission")
    synchronized void start(BluetoothDevice bleDevice) {
        disconnectInternal("restart");
        sourceAddress = bleDevice.getAddress();
        mtuHandled = false;
        JSONObject details = new JSONObject();
        try {
            details.put("service_uuid", SERVICE_UUID.toString());
            details.put("characteristic_uuid", CONNECTION_INFO_UUID.toString());
            details.put("gatt_writes_implemented", false);
            details.put("descriptor_writes_implemented", false);
            details.put("application_payload_reads_implemented", false);
            details.put("application_payload_writes_implemented", false);
        } catch (Exception ignored) {
        }
        logger.event("r25_2_provisioning_started", sourceAddress, details);
        listener.onStatus("r25.2: connecting LE for read-only 0x9301 provisioning");
        gatt = bleDevice.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
    }

    @SuppressLint("MissingPermission")
    synchronized void disconnect() {
        disconnectInternal("operator");
    }

    @SuppressLint("MissingPermission")
    private synchronized void disconnectInternal(String reason) {
        if (gatt != null) {
            gatt.disconnect();
            gatt.close();
            gatt = null;
        }
        if (socket != null) {
            try {
                socket.close();
            } catch (IOException ignored) {
            }
            socket = null;
        }
        JSONObject details = new JSONObject();
        try {
            details.put("reason", reason);
        } catch (Exception ignored) {
        }
        logger.event("r25_2_probe_disconnected", sourceAddress, details);
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt bluetoothGatt, int status, int newState) {
            JSONObject details = new JSONObject();
            try {
                details.put("status", status);
                details.put("new_state", newState);
            } catch (Exception ignored) {
            }
            logger.event("r25_2_gatt_connection_state", sourceAddress, details);
            if (status == BluetoothGatt.GATT_SUCCESS && newState == BluetoothProfile.STATE_CONNECTED) {
                listener.onStatus("r25.2: LE connected; discovering 0x9100 service");
                bluetoothGatt.discoverServices();
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                listener.onStatus("r25.2: LE disconnected");
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt bluetoothGatt, int status) {
            JSONObject details = new JSONObject();
            try {
                details.put("status", status);
                details.put("target_service_present", bluetoothGatt.getService(SERVICE_UUID) != null);
            } catch (Exception ignored) {
            }
            logger.event("r25_2_services_discovered", sourceAddress, details);
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("GATT service discovery failed: " + status, null);
                return;
            }
            BluetoothGattService service = bluetoothGatt.getService(SERVICE_UUID);
            if (service == null || service.getCharacteristic(CONNECTION_INFO_UUID) == null) {
                fail("0x9100/0x9301 provisioning endpoint not found", null);
                return;
            }
            boolean requested = bluetoothGatt.requestMtu(512);
            if (!requested) {
                readConnectionInfo(bluetoothGatt);
            }
        }

        @Override
        public void onMtuChanged(BluetoothGatt bluetoothGatt, int mtu, int status) {
            JSONObject details = new JSONObject();
            try {
                details.put("mtu", mtu);
                details.put("status", status);
            } catch (Exception ignored) {
            }
            logger.event("r25_2_gatt_mtu", sourceAddress, details);
            readConnectionInfo(bluetoothGatt);
        }

        @Override
        public void onCharacteristicRead(
                BluetoothGatt bluetoothGatt,
                BluetoothGattCharacteristic characteristic,
                int status) {
            if (!CONNECTION_INFO_UUID.equals(characteristic.getUuid())) {
                return;
            }
            byte[] value = characteristic.getValue();
            JSONObject readDetails = new JSONObject();
            try {
                readDetails.put("service_uuid", characteristic.getService().getUuid().toString());
                readDetails.put("characteristic_uuid", characteristic.getUuid().toString());
                readDetails.put("status", status);
                readDetails.put("value_length", value == null ? 0 : value.length);
                readDetails.put("value_sha256", value == null ? JSONObject.NULL : Hashing.sha256(value));
                readDetails.put("raw_value_published", false);
            } catch (Exception ignored) {
            }
            logger.event("r25_2_provisioning_characteristic_read", sourceAddress, readDetails);
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("0x9301 read failed: " + status, null);
                return;
            }

            final ProvisioningPayloadParser.Result endpoint;
            try {
                endpoint = ProvisioningPayloadParser.parse(value);
            } catch (RuntimeException error) {
                fail("0x9301 parse failed", error);
                return;
            }

            JSONObject endpointDetails = new JSONObject();
            try {
                endpointDetails.put("runtime_uuid_sha256", endpoint.runtimeUuidSha256());
                endpointDetails.put("runtime_uuid_published", false);
                endpointDetails.put("classic_address_published", false);
                endpointDetails.put("account_material_length", endpoint.accountMaterialLength());
                endpointDetails.put("account_material_sha256", endpoint.accountMaterialSha256());
                endpointDetails.put("account_material_published", false);
                endpointDetails.put("raw_value_length", endpoint.rawLength());
                endpointDetails.put("raw_value_sha256", endpoint.rawSha256());
            } catch (Exception ignored) {
            }
            logger.event("r25_2_runtime_endpoint_acquired", sourceAddress, endpointDetails);

            closeGattOnly();
            connectRfcomm(endpoint);
        }
    };

    @SuppressLint("MissingPermission")
    private synchronized void readConnectionInfo(BluetoothGatt bluetoothGatt) {
        if (mtuHandled) {
            return;
        }
        mtuHandled = true;
        BluetoothGattService service = bluetoothGatt.getService(SERVICE_UUID);
        BluetoothGattCharacteristic characteristic = service == null
                ? null
                : service.getCharacteristic(CONNECTION_INFO_UUID);
        if (characteristic == null) {
            fail("0x9301 characteristic disappeared", null);
            return;
        }
        boolean started = bluetoothGatt.readCharacteristic(characteristic);
        JSONObject details = new JSONObject();
        try {
            details.put("started", started);
            details.put("characteristic_uuid", CONNECTION_INFO_UUID.toString());
        } catch (Exception ignored) {
        }
        logger.event("r25_2_provisioning_read_requested", sourceAddress, details);
        if (!started) {
            fail("0x9301 read did not start", null);
        }
    }

    @SuppressLint("MissingPermission")
    private synchronized void closeGattOnly() {
        if (gatt != null) {
            gatt.disconnect();
            gatt.close();
            gatt = null;
        }
    }

    @SuppressLint("MissingPermission")
    private void connectRfcomm(ProvisioningPayloadParser.Result endpoint) {
        JSONObject details = new JSONObject();
        try {
            details.put("runtime_uuid_sha256", endpoint.runtimeUuidSha256());
            details.put("expected_scn_from_r25_1", 3);
            details.put("expected_dlci_from_r25_1", 6);
            details.put("application_payload_read_count", 0);
            details.put("application_payload_write_count", 0);
        } catch (Exception ignored) {
        }
        logger.event("r25_2_rfcomm_connect_requested", endpoint.classicAddress(), details);
        listener.onStatus("r25.2: runtime endpoint acquired; opening connection-only RFCOMM");

        connectionExecutor.execute(() -> {
            BluetoothSocket localSocket = null;
            try {
                BluetoothDevice classicDevice = adapter.getRemoteDevice(endpoint.classicAddress());
                localSocket = classicDevice.createRfcommSocketToServiceRecord(endpoint.runtimeUuid());
                synchronized (this) {
                    socket = localSocket;
                }
                BluetoothSocket timeoutTarget = localSocket;
                timeoutExecutor.schedule(() -> closeQuietly(timeoutTarget), CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                localSocket.connect();

                JSONObject openDetails = new JSONObject();
                try {
                    openDetails.put("runtime_uuid_sha256", endpoint.runtimeUuidSha256());
                    openDetails.put("connected", localSocket.isConnected());
                    openDetails.put("max_receive_packet_size", localSocket.getMaxReceivePacketSize());
                    openDetails.put("max_transmit_packet_size", localSocket.getMaxTransmitPacketSize());
                    openDetails.put("application_payload_read_count", 0);
                    openDetails.put("application_payload_write_count", 0);
                    openDetails.put("input_stream_obtained", false);
                    openDetails.put("output_stream_obtained", false);
                } catch (Exception ignored) {
                }
                logger.event("r25_2_rfcomm_socket_open", endpoint.classicAddress(), openDetails);
                listener.onStatus("r25.2: RFCOMM open; no payload I/O; closing shortly");
                Thread.sleep(CONNECT_HOLD_MILLIS);
            } catch (Exception error) {
                JSONObject failure = new JSONObject();
                try {
                    failure.put("error_class", error.getClass().getName());
                    failure.put("message_sha256", Hashing.sha256(
                            String.valueOf(error.getMessage()).getBytes(java.nio.charset.StandardCharsets.UTF_8)));
                    failure.put("application_payload_read_count", 0);
                    failure.put("application_payload_write_count", 0);
                } catch (Exception ignored) {
                }
                logger.event("r25_2_rfcomm_connect_failed", endpoint.classicAddress(), failure);
                listener.onStatus("r25.2: RFCOMM connection failed; see private log");
            } finally {
                closeQuietly(localSocket);
                synchronized (this) {
                    if (socket == localSocket) {
                        socket = null;
                    }
                }
                JSONObject closed = new JSONObject();
                try {
                    closed.put("application_payload_read_count", 0);
                    closed.put("application_payload_write_count", 0);
                } catch (Exception ignored) {
                }
                logger.event("r25_2_rfcomm_socket_closed", endpoint.classicAddress(), closed);
                listener.onStatus("r25.2: connection-only RFCOMM probe complete");
            }
        });
    }

    private void fail(String message, Exception error) {
        JSONObject details = new JSONObject();
        try {
            details.put("message_sha256", Hashing.sha256(
                    message.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            details.put("error_class", error == null ? JSONObject.NULL : error.getClass().getName());
        } catch (Exception ignored) {
        }
        logger.event("r25_2_probe_failed", sourceAddress, details);
        listener.onStatus("r25.2 failed; see private log");
        closeGattOnly();
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
    public void close() {
        disconnect();
        connectionExecutor.shutdownNow();
        timeoutExecutor.shutdownNow();
    }
}
