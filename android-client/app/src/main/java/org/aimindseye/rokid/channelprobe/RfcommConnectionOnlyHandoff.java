package org.aimindseye.rokid.channelprobe;

import android.content.Context;

import org.json.JSONObject;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Pattern;

final class RfcommConnectionOnlyHandoff {
    static final String FILE_NAME = "r25.2.2.2-connection-only-input-private.json";
    private static final String SCHEMA =
            "rokid.r25.2.2.2.connection-only-input-private.v1";
    private static final Pattern ADDRESS = Pattern.compile(
            "(?i)^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$");
    private static final Pattern SHA256 = Pattern.compile("^[0-9a-f]{64}$");
    private static final String ZERO_ADDRESS =
            String.join(":", "00", "00", "00", "00", "00", "00");
    private static final String BROADCAST_ADDRESS =
            String.join(":", "FF", "FF", "FF", "FF", "FF", "FF");

    private final String runtimeAddress;
    private final UUID runtimeUuid;
    private final String runtimeAddressSha256;
    private final String runtimeUuidSha256;
    private final String endpointBindingSha256;
    private final String sourcePrivateZipSha256;
    private final String sourceHandoffSha256;
    private final int expectedScn;
    private final int expectedDlci;
    private final int expectedMtu;

    private RfcommConnectionOnlyHandoff(
            String runtimeAddress,
            UUID runtimeUuid,
            String runtimeAddressSha256,
            String runtimeUuidSha256,
            String endpointBindingSha256,
            String sourcePrivateZipSha256,
            String sourceHandoffSha256,
            int expectedScn,
            int expectedDlci,
            int expectedMtu) {
        this.runtimeAddress = runtimeAddress;
        this.runtimeUuid = runtimeUuid;
        this.runtimeAddressSha256 = runtimeAddressSha256;
        this.runtimeUuidSha256 = runtimeUuidSha256;
        this.endpointBindingSha256 = endpointBindingSha256;
        this.sourcePrivateZipSha256 = sourcePrivateZipSha256;
        this.sourceHandoffSha256 = sourceHandoffSha256;
        this.expectedScn = expectedScn;
        this.expectedDlci = expectedDlci;
        this.expectedMtu = expectedMtu;
    }

    static RfcommConnectionOnlyHandoff load(Context context) throws Exception {
        File file = new File(new File(context.getFilesDir(), "r25"), FILE_NAME);
        if (!file.isFile()) {
            throw new IllegalStateException("private handoff file not found");
        }
        String raw = new String(
                Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        JSONObject value = new JSONObject(raw);
        if (!SCHEMA.equals(value.getString("schema"))) {
            throw new IllegalArgumentException("unexpected handoff schema");
        }
        if (!value.getBoolean("ready_for_independent_connection_only_qualification")) {
            throw new IllegalArgumentException("handoff not ready");
        }
        if (value.getBoolean("application_payload_operation_authorized")) {
            throw new IllegalArgumentException("payload authorization must be false");
        }
        if (!"cached_classic_runtime_endpoint".equals(value.getString("endpoint_type"))) {
            throw new IllegalArgumentException("unexpected endpoint type");
        }

        String address = value.getString("runtime_address").toUpperCase(Locale.US);
        if (!ADDRESS.matcher(address).matches()
                || ZERO_ADDRESS.equals(address)
                || BROADCAST_ADDRESS.equals(address)) {
            throw new IllegalArgumentException("invalid runtime address");
        }
        UUID uuid = UUID.fromString(value.getString("runtime_uuid"));
        String addressHash = value.getString("runtime_address_sha256");
        String uuidHash = value.getString("runtime_uuid_sha256");
        String bindingHash = value.getString("endpoint_binding_sha256");
        String sourceZipHash = value.getString("source_private_zip_sha256");
        String sourceHandoffHash = value.getString("source_handoff_sha256");
        for (String item : new String[]{
                addressHash, uuidHash, bindingHash, sourceZipHash, sourceHandoffHash}) {
            if (!SHA256.matcher(item).matches()) {
                throw new IllegalArgumentException("invalid SHA-256 field");
            }
        }

        String computedAddressHash = Hashing.sha256(
                address.getBytes(StandardCharsets.UTF_8));
        String normalizedUuid = uuid.toString().toLowerCase(Locale.US);
        String computedUuidHash = Hashing.sha256(
                normalizedUuid.getBytes(StandardCharsets.UTF_8));
        String computedBinding = Hashing.sha256(
                (address + "|" + normalizedUuid).getBytes(StandardCharsets.UTF_8));
        if (!computedAddressHash.equals(addressHash)
                || !computedUuidHash.equals(uuidHash)
                || !computedBinding.equals(bindingHash)) {
            throw new IllegalArgumentException("private endpoint hash mismatch");
        }

        JSONObject rfcomm = value.getJSONObject("expected_rfcomm");
        int scn = rfcomm.getInt("scn");
        int dlci = rfcomm.getInt("dlci");
        int mtu = rfcomm.getInt("mtu");
        if (!rfcomm.getBoolean("client") || scn != 3 || dlci != 6 || mtu != 990) {
            throw new IllegalArgumentException("unexpected RFCOMM contract");
        }

        return new RfcommConnectionOnlyHandoff(
                address,
                uuid,
                addressHash,
                uuidHash,
                bindingHash,
                sourceZipHash,
                sourceHandoffHash,
                scn,
                dlci,
                mtu);
    }

    String runtimeAddress() {
        return runtimeAddress;
    }

    UUID runtimeUuid() {
        return runtimeUuid;
    }

    int expectedScn() {
        return expectedScn;
    }

    int expectedDlci() {
        return expectedDlci;
    }

    int expectedMtu() {
        return expectedMtu;
    }

    JSONObject sanitizedDetails() {
        JSONObject details = new JSONObject();
        try {
            details.put("runtime_address_sha256", runtimeAddressSha256);
            details.put("runtime_address_published", false);
            details.put("runtime_uuid_sha256", runtimeUuidSha256);
            details.put("runtime_uuid_published", false);
            details.put("endpoint_binding_sha256", endpointBindingSha256);
            details.put("source_private_zip_sha256", sourcePrivateZipSha256);
            details.put("source_handoff_sha256", sourceHandoffSha256);
            details.put("expected_scn", expectedScn);
            details.put("expected_dlci", expectedDlci);
            details.put("expected_mtu", expectedMtu);
            details.put("application_payload_operation_authorized", false);
        } catch (Exception ignored) {
        }
        return details;
    }
}
