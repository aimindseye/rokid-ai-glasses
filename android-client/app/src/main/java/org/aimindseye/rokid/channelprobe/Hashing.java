package org.aimindseye.rokid.channelprobe;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

final class Hashing {
    private Hashing() {
    }

    static String sha256(byte[] value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value);
            StringBuilder out = new StringBuilder();
            for (byte item : digest) {
                out.append(String.format(Locale.US, "%02x", item));
            }
            return out.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }
}
