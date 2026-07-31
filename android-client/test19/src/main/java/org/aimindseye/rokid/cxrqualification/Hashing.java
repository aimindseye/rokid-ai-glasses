package org.aimindseye.rokid.cxrqualification;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

final class Hashing {
    private Hashing() {
    }

    static String sha256(byte[] value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashed = digest.digest(value);
            StringBuilder out = new StringBuilder();
            for (byte item : hashed) {
                out.append(String.format(Locale.US, "%02x", item));
            }
            return out.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    static String sha256(String value) {
        return sha256(String.valueOf(value).getBytes(StandardCharsets.UTF_8));
    }
}
