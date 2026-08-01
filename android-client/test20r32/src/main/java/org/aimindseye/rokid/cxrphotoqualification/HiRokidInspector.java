package org.aimindseye.rokid.cxrphotoqualification;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.pm.ServiceInfo;
import android.os.Build;

import org.json.JSONObject;

final class HiRokidInspector {
    private final Context context;

    HiRokidInspector(Context context) {
        this.context = context;
    }

    JSONObject inspect() {
        PackageManager manager = context.getPackageManager();
        String packageName = installedPackage(manager);
        JSONObject details = EvidenceLogger.details(
                "package_present", packageName != null,
                "package_name", packageName == null ? "" : packageName
        );
        if (packageName == null) {
            return details;
        }

        try {
            PackageInfo info;
            if (Build.VERSION.SDK_INT >= 33) {
                info = manager.getPackageInfo(
                        packageName,
                        PackageManager.PackageInfoFlags.of(0)
                );
            } else {
                @SuppressWarnings("deprecation")
                PackageInfo legacy = manager.getPackageInfo(packageName, 0);
                info = legacy;
            }
            details.put("version_name", info.versionName == null ? "" : info.versionName);
            details.put("version_code", info.getLongVersionCode());
        } catch (Exception error) {
            detailsSafe(details, "package_error_class", error.getClass().getName());
        }

        Intent authIntent =
                new Intent(Test20R32Contract.AUTH_ACTION).setPackage(packageName);
        ResolveInfo auth =
                manager.resolveActivity(authIntent, PackageManager.MATCH_DEFAULT_ONLY);
        ActivityInfo authInfo = auth == null ? null : auth.activityInfo;
        detailsSafe(details, "authorization_resolved", authInfo != null);
        detailsSafe(details, "authorization_exported",
                authInfo != null && authInfo.exported);
        detailsSafe(details, "authorization_component",
                authInfo == null
                        ? ""
                        : new ComponentName(
                                authInfo.packageName,
                                authInfo.name
                        ).flattenToShortString());

        Intent serviceIntent =
                new Intent(Test20R32Contract.MEDIA_SERVICE_ACTION).setPackage(packageName);
        ResolveInfo service = manager.resolveService(serviceIntent, 0);
        ServiceInfo serviceInfo = service == null ? null : service.serviceInfo;
        detailsSafe(details, "service_resolved", serviceInfo != null);
        detailsSafe(details, "service_exported",
                serviceInfo != null && serviceInfo.exported);
        detailsSafe(details, "service_component",
                serviceInfo == null
                        ? ""
                        : new ComponentName(
                                serviceInfo.packageName,
                                serviceInfo.name
                        ).flattenToShortString());
        return details;
    }

    private String installedPackage(PackageManager manager) {
        if (isInstalled(manager, Test20R32Contract.GLOBAL_HI_ROKID_PACKAGE)) {
            return Test20R32Contract.GLOBAL_HI_ROKID_PACKAGE;
        }
        if (isInstalled(manager, Test20R32Contract.CHINA_HI_ROKID_PACKAGE)) {
            return Test20R32Contract.CHINA_HI_ROKID_PACKAGE;
        }
        return null;
    }

    private static boolean isInstalled(PackageManager manager, String packageName) {
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                manager.getPackageInfo(
                        packageName,
                        PackageManager.PackageInfoFlags.of(0)
                );
            } else {
                @SuppressWarnings("deprecation")
                PackageInfo ignored = manager.getPackageInfo(packageName, 0);
            }
            return true;
        } catch (PackageManager.NameNotFoundException error) {
            return false;
        }
    }

    private static void detailsSafe(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (Exception ignored) {
            // JSONObject accepts these scalar values.
        }
    }
}
