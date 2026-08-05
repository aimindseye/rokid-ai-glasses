package org.aimindseye.rokid.test22wifi;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * TEST22_R4_3_3_PERSISTENT_LAUNCH_BREADCRUMBS
 *
 * Starts the dormant control service after the already-installed Test22 package
 * is replaced and persists the receiver -> service-start boundary.
 */
public final class PackageReplacedReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent == null ? "" : intent.getAction();
        LaunchBreadcrumbs.beginLaunch(context, action);

        if (!Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
            LaunchBreadcrumbs.record(
                    context,
                    "PACKAGE_REPLACED_ACTION_REJECTED",
                    action
            );
            return;
        }

        LaunchBreadcrumbs.record(
                context,
                "PACKAGE_REPLACED_ACTION_VALIDATED",
                "MY_PACKAGE_REPLACED"
        );

        Intent service = new Intent(context, Test22ControlService.class)
                .setAction(Test22ControlService.ACTION_PACKAGE_REPLACED);

        String call =
                Build.VERSION.SDK_INT >= 26
                        ? "startForegroundService"
                        : "startService";

        LaunchBreadcrumbs.record(
                context,
                "CONTROL_SERVICE_START_REQUESTED",
                call
        );

        try {
            if (Build.VERSION.SDK_INT >= 26) {
                context.startForegroundService(service);
            } else {
                context.startService(service);
            }

            LaunchBreadcrumbs.record(
                    context,
                    "CONTROL_SERVICE_START_RETURNED",
                    call
            );
        } catch (Throwable error) {
            LaunchBreadcrumbs.record(
                    context,
                    "CONTROL_SERVICE_START_THROWN",
                    error.getClass().getName()
            );
        }
    }
}
