package org.aimindseye.rokid.cxrmediapreflight;

final class Test20R31Contract {
    static final String EVENT_SCHEMA = "rokid.test20-r3.1.cxrl-no-payload.v1";
    static final String GLOBAL_HI_ROKID_PACKAGE = "com.rokid.sprite.global.aiapp";
    static final String CHINA_HI_ROKID_PACKAGE = "com.rokid.sprite.aiapp";
    static final String AUTH_ACTIVITY_CLASS =
            "com.rokid.sprite.aiapp.externalapp.auth.AuthorizationActivity";
    static final String AUTH_ACTION =
            "com.rokid.sprite.aiapp.externalapp.AUTHORIZATION";
    static final String MEDIA_SERVICE_ACTION =
            "com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE";
    static final String AUTH_TOKEN_EXTRA = "auth_token";
    static final String AUTH_PACKAGE_EXTRA = "auth_package";
    static final int AUTH_REQUEST_CODE = 5031;
    static final long MANUAL_BIND_DELAY_MS = 8_000L;
    static final long CONNECTION_TIMEOUT_MS = 90_000L;
    static final long NO_PAYLOAD_OBSERVATION_MS = 15_000L;
    static final long AUTO_DISCONNECT_DELAY_MS = 2_000L;
    private Test20R31Contract() {}
}
