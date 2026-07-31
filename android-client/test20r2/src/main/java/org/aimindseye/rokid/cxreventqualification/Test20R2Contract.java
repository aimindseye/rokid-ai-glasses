package org.aimindseye.rokid.cxreventqualification;

final class Test20R2Contract {
    static final String EVENT_SCHEMA = "rokid.test20-r2.cxrl-event.v1";
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
    static final int AUTH_REQUEST_CODE = 5020;
    static final int REQUIRED_AI_ASSIST_CYCLES = 2;
    static final long MANUAL_BIND_DELAY_MS = 8_000L;
    static final long CONNECTION_TIMEOUT_MS = 90_000L;
    static final long EVENT_OBSERVATION_TIMEOUT_MS = 180_000L;
    static final long AUTO_DISCONNECT_DELAY_MS = 2_000L;

    private Test20R2Contract() {}
}
