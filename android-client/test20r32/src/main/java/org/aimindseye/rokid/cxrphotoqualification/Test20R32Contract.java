package org.aimindseye.rokid.cxrphotoqualification;

final class Test20R32Contract {
    static final String EVENT_SCHEMA = "rokid.test20-final.cxrl-one-shot-photo.v1";
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
    static final int AUTH_REQUEST_CODE = 5032;
    static final int PHOTO_ARG_1 = 1920;
    static final int PHOTO_ARG_2 = 1080;
    static final int PHOTO_ARG_3 = 80;
    static final String PHOTO_ARGUMENT_SEMANTICS =
            "WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED";
    static final String IMAGE_CALLBACK_LIFECYCLE =
            "STRONG_REFERENCE_PRECONNECT_PLUS_POST_SERVICE_STATUS_REREGISTRATION";
    static final long MANUAL_BIND_DELAY_MS = 8_000L;
    static final long CONNECTION_TIMEOUT_MS = 90_000L;
    static final long PHOTO_CALLBACK_TIMEOUT_MS = 30_000L;
    static final long[] POST_TAKEPHOTO_WATCHDOG_DELAYS_MS = new long[] {
            1_000L, 5_000L, 10_000L, 20_000L, 29_000L
    };
    static final long DUPLICATE_CALLBACK_WINDOW_MS = 3_000L;
    static final long AUTO_DISCONNECT_DELAY_MS = 2_000L;
    private Test20R32Contract() {}
}
