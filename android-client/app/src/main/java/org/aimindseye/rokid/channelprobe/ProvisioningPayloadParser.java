package org.aimindseye.rokid.channelprobe;

import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class ProvisioningPayloadParser {
    private static final Pattern UUID_PATTERN = Pattern.compile(
            "(?i)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})");
    private static final Pattern MAC_PATTERN = Pattern.compile(
            "(?i)([0-9a-f]{2}(?::[0-9a-f]{2}){5})");
    private static final Pattern BASE64_PATTERN = Pattern.compile(
            "([A-Za-z0-9+/]{16,}={0,2})");

    record Result(
            UUID runtimeUuid,
            String classicAddress,
            String runtimeUuidSha256,
            int accountMaterialLength,
            String accountMaterialSha256,
            int rawLength,
            String rawSha256) {
    }

    private ProvisioningPayloadParser() {
    }

    static Result parse(byte[] value) {
        if (value == null || value.length == 0) {
            throw new IllegalArgumentException("0x9301 value is empty");
        }

        String text = new String(value, StandardCharsets.ISO_8859_1);
        Matcher uuidMatcher = UUID_PATTERN.matcher(text);
        if (!uuidMatcher.find()) {
            throw new IllegalArgumentException("runtime UUID not found in 0x9301 value");
        }
        String uuidText = uuidMatcher.group(1).toLowerCase(Locale.US);

        Matcher macMatcher = MAC_PATTERN.matcher(text);
        if (!macMatcher.find(uuidMatcher.end())) {
            throw new IllegalArgumentException("Classic Bluetooth address not found after runtime UUID");
        }
        String classicAddress = macMatcher.group(1).toUpperCase(Locale.US);

        String accountText = "";
        Matcher accountMatcher = BASE64_PATTERN.matcher(text.substring(macMatcher.end()));
        if (accountMatcher.find()) {
            accountText = accountMatcher.group(1);
        }

        byte[] accountBytes = accountText.getBytes(StandardCharsets.US_ASCII);
        return new Result(
                UUID.fromString(uuidText),
                classicAddress,
                Hashing.sha256(uuidText.getBytes(StandardCharsets.US_ASCII)),
                accountBytes.length,
                Hashing.sha256(accountBytes),
                value.length,
                Hashing.sha256(value));
    }
}
