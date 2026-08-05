package org.aimindseye.rokid.test22wifi;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;

/**
 * Emergency/manual entry only. The normal r4.3 start path is ACTION_MY_PACKAGE_REPLACED.
 * No Wi-Fi API is touched by this activity.
 */
public final class MainActivity extends Activity {
    static final String CONTROL_PLANE_MARKER = "test22-r4.3-loopback-control-v1";
    static final String EXECUTE_TOKEN = "TEST22_R4_3_ISOLATED_DIRECT_SOCKET";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Intent service = new Intent(this, Test22ControlService.class)
                .setAction(Test22ControlService.ACTION_MANUAL_START);
        if (Build.VERSION.SDK_INT >= 26) {
            startForegroundService(service);
        } else {
            startService(service);
        }
        finish();
    }
}
