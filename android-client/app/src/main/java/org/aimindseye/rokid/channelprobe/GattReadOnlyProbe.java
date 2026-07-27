package org.aimindseye.rokid.channelprobe;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayDeque;
import java.util.Queue;

final class GattReadOnlyProbe {
    interface Listener {
        void onStatus(String text);
    }

    private final Context context;
    private final EvidenceLogger logger;
    private final Listener listener;
    private final Queue<BluetoothGattCharacteristic> readQueue = new ArrayDeque<>();
    private BluetoothGatt gatt;
    private String address;

    GattReadOnlyProbe(Context context, EvidenceLogger logger, Listener listener) {
        this.context = context;
        this.logger = logger;
        this.listener = listener;
    }

    @SuppressLint("MissingPermission")
    void connect(BluetoothDevice device) {
        disconnect();
        address = device.getAddress();
        JSONObject details = new JSONObject();
        try {
            details.put("name", safeName(device));
        } catch (Exception ignored) {
        }
        logger.event("gatt_connect_requested", address, details);
        listener.onStatus("Connecting read-only GATT probe to " + safeName(device));
        gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE);
    }

    @SuppressLint("MissingPermission")
    void disconnect() {
        readQueue.clear();
        if (gatt != null) {
            gatt.disconnect();
            gatt.close();
            gatt = null;
        }
        address = null;
    }

    @SuppressLint("MissingPermission")
    private String safeName(BluetoothDevice device) {
        String name = device.getName();
        return name == null || name.isBlank() ? "unnamed" : name;
    }

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt bluetoothGatt, int status, int newState) {
            JSONObject details = new JSONObject();
            try {
                details.put("status", status);
                details.put("new_state", newState);
            } catch (Exception ignored) {
            }
            logger.event("gatt_connection_state", address, details);
            if (status == BluetoothGatt.GATT_SUCCESS && newState == BluetoothProfile.STATE_CONNECTED) {
                listener.onStatus("Connected; discovering services");
                discover(bluetoothGatt);
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                listener.onStatus("Disconnected");
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt bluetoothGatt, int status) {
            JSONArray services = new JSONArray();
            readQueue.clear();
            if (status == BluetoothGatt.GATT_SUCCESS) {
                for (BluetoothGattService service : bluetoothGatt.getServices()) {
                    JSONObject serviceJson = new JSONObject();
                    JSONArray characteristics = new JSONArray();
                    try {
                        serviceJson.put("uuid", service.getUuid().toString());
                        serviceJson.put("type", service.getType());
                    } catch (Exception ignored) {
                    }
                    for (BluetoothGattCharacteristic characteristic : service.getCharacteristics()) {
                        JSONObject characteristicJson = new JSONObject();
                        int properties = characteristic.getProperties();
                        try {
                            characteristicJson.put("uuid", characteristic.getUuid().toString());
                            characteristicJson.put("properties", properties);
                            characteristicJson.put("readable", (properties & BluetoothGattCharacteristic.PROPERTY_READ) != 0);
                        } catch (Exception ignored) {
                        }
                        characteristics.put(characteristicJson);
                        if ((properties & BluetoothGattCharacteristic.PROPERTY_READ) != 0) {
                            readQueue.add(characteristic);
                        }
                    }
                    try {
                        serviceJson.put("characteristics", characteristics);
                    } catch (Exception ignored) {
                    }
                    services.put(serviceJson);
                }
            }
            JSONObject details = new JSONObject();
            try {
                details.put("status", status);
                details.put("services", services);
                details.put("read_queue_count", readQueue.size());
            } catch (Exception ignored) {
            }
            logger.event("gatt_services_discovered", address, details);
            listener.onStatus("Services discovered: " + services.length() + "; readable characteristics: " + readQueue.size());
            readNext(bluetoothGatt);
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt bluetoothGatt, BluetoothGattCharacteristic characteristic, int status) {
            byte[] value = characteristic.getValue();
            JSONObject details = new JSONObject();
            try {
                details.put("service_uuid", characteristic.getService().getUuid().toString());
                details.put("characteristic_uuid", characteristic.getUuid().toString());
                details.put("status", status);
                details.put("value_length", value == null ? 0 : value.length);
                details.put("value_sha256", value == null ? JSONObject.NULL : Hashing.sha256(value));
            } catch (Exception ignored) {
            }
            logger.event("gatt_characteristic_read", address, details);
            readNext(bluetoothGatt);
        }
    };

    @SuppressLint("MissingPermission")
    private void discover(BluetoothGatt bluetoothGatt) {
        bluetoothGatt.discoverServices();
    }

    @SuppressLint("MissingPermission")
    private void readNext(BluetoothGatt bluetoothGatt) {
        BluetoothGattCharacteristic next = readQueue.poll();
        if (next == null) {
            logger.event("gatt_read_only_inventory_complete", address, new JSONObject());
            listener.onStatus("Read-only GATT inventory complete");
            return;
        }
        boolean started = bluetoothGatt.readCharacteristic(next);
        if (!started) {
            JSONObject details = new JSONObject();
            try {
                details.put("characteristic_uuid", next.getUuid().toString());
            } catch (Exception ignored) {
            }
            logger.event("gatt_characteristic_read_not_started", address, details);
            readNext(bluetoothGatt);
        }
    }
}
