#!/usr/bin/env python3
"""Compile Test 19 r2 Java sources against bounded Android and CXR-L stubs."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "android-client/test19r2/src/main/java/org/aimindseye/rokid/cxrlqualification"

STUBS = {
    "android/Manifest.java": 'package android; public final class Manifest { public static final class permission { public static final String BLUETOOTH_CONNECT=""; } }',
    "android/util/Log.java": 'package android.util; public class Log { public static int i(String a,String b){return 0;} public static int e(String a,String b,Throwable t){return 0;} }',
    "android/util/DisplayMetrics.java": 'package android.util; public class DisplayMetrics { public float density=1f; }',
    "android/content/res/Resources.java": 'package android.content.res; public class Resources { public android.util.DisplayMetrics getDisplayMetrics(){return new android.util.DisplayMetrics();} }',
    "android/content/pm/ActivityInfo.java": 'package android.content.pm; public class ActivityInfo { public String packageName=""; public String name=""; public boolean exported=true; }',
    "android/content/pm/ServiceInfo.java": 'package android.content.pm; public class ServiceInfo { public String packageName=""; public String name=""; public boolean exported=true; }',
    "android/content/pm/ResolveInfo.java": 'package android.content.pm; public class ResolveInfo { public ActivityInfo activityInfo; public ServiceInfo serviceInfo; }',
    "android/content/pm/PackageInfo.java": 'package android.content.pm; public class PackageInfo { public String versionName=""; public long getLongVersionCode(){return 1L;} }',
    "android/content/pm/PackageManager.java": '''package android.content.pm; import android.content.Intent; public class PackageManager { public static final int PERMISSION_GRANTED=0; public static final int MATCH_DEFAULT_ONLY=0; public static class NameNotFoundException extends Exception {} public static class PackageInfoFlags { public static PackageInfoFlags of(long v){return new PackageInfoFlags();} } public PackageInfo getPackageInfo(String p,int f) throws NameNotFoundException{return new PackageInfo();} public PackageInfo getPackageInfo(String p,PackageInfoFlags f) throws NameNotFoundException{return new PackageInfo();} public ResolveInfo resolveActivity(Intent i,int f){return new ResolveInfo();} public ResolveInfo resolveService(Intent i,int f){return new ResolveInfo();} }''',
    "android/content/ComponentName.java": 'package android.content; public class ComponentName { public ComponentName(String p,String c){} public String flattenToShortString(){return "";} }',
    "android/content/Intent.java": '''package android.content; public class Intent { public Intent(){} public Intent(String a){} public Intent setComponent(ComponentName c){return this;} public Intent setPackage(String p){return this;} public Intent putExtra(String k,String v){return this;} public String getStringExtra(String k){return null;} }''',
    "android/content/ServiceConnection.java": 'package android.content; public interface ServiceConnection {}',
    "android/content/Context.java": '''package android.content; import java.io.File; import android.content.pm.PackageManager; public class Context { public static final int BIND_AUTO_CREATE=1; public File getExternalFilesDir(String s){return new File(".");} public Context getApplicationContext(){return this;} public PackageManager getPackageManager(){return new PackageManager();} public String getPackageName(){return "pkg";} public android.content.res.Resources getResources(){return new android.content.res.Resources();} public boolean bindService(Intent i,ServiceConnection c,int f){return true;} public void unbindService(ServiceConnection c){} }''',
    "android/app/Activity.java": '''package android.app; public class Activity extends android.content.Context { public static final int RESULT_CANCELED=0; protected void onCreate(android.os.Bundle b){} protected void onDestroy(){} protected void onActivityResult(int a,int b,android.content.Intent c){} public android.content.Intent getIntent(){return new android.content.Intent();} public void startActivityForResult(android.content.Intent i,int c){} public void setContentView(android.view.View v){} public void runOnUiThread(Runnable r){r.run();} public int checkSelfPermission(String p){return 0;} public void requestPermissions(String[] p,int r){} }''',
    "android/os/Bundle.java": 'package android.os; public class Bundle {}',
    "android/os/Build.java": 'package android.os; public class Build { public static class VERSION { public static int SDK_INT=36; } }',
    "android/os/Looper.java": 'package android.os; public class Looper { public static Looper getMainLooper(){return new Looper();} }',
    "android/os/Handler.java": 'package android.os; public class Handler { public Handler(Looper l){} public boolean postDelayed(Runnable r,long m){return true;} public void removeCallbacksAndMessages(Object o){} }',
    "android/view/View.java": 'package android.view; public class View { public interface OnClickListener { void onClick(View v); } }',
    "android/widget/TextView.java": 'package android.widget; public class TextView extends android.view.View { public TextView(android.content.Context c){} public void setText(CharSequence s){} public void setTextSize(float s){} public void setPadding(int a,int b,int c,int d){} }',
    "android/widget/Button.java": 'package android.widget; public class Button extends TextView { public Button(android.content.Context c){super(c);} public void setEnabled(boolean b){} public void setOnClickListener(android.view.View.OnClickListener l){} public void setAllCaps(boolean b){} }',
    "android/widget/LinearLayout.java": 'package android.widget; public class LinearLayout extends android.view.View { public static final int VERTICAL=1; public LinearLayout(android.content.Context c){} public void setOrientation(int o){} public void setPadding(int a,int b,int c,int d){} public void addView(android.view.View v){} }',
    "android/widget/ScrollView.java": 'package android.widget; public class ScrollView extends android.view.View { public ScrollView(android.content.Context c){} public void addView(android.view.View v){} }',
    "org/json/JSONException.java": 'package org.json; public class JSONException extends Exception { public JSONException(){} }',
    "org/json/JSONObject.java": 'package org.json; public class JSONObject { public JSONObject(){} public JSONObject put(String k,Object v) throws JSONException{return this;} public String toString(){return "{}";} }',
    "com/rokid/cxr/link/utils/CxrDefs.java": '''package com.rokid.cxr.link.utils; public class CxrDefs { public enum CXRSessionType { NONE,CUSTOMVIEW,CUSTOMAPP } public static class CXRSession { public CXRSession(CXRSessionType t,String p){} } }''',
    "com/rokid/cxr/link/callbacks/ICXRLinkCbk.java": '''package com.rokid.cxr.link.callbacks; public interface ICXRLinkCbk { void onCXRLConnected(boolean b); void onGlassBtConnected(boolean b); void onGlassAiAssistStart(); void onGlassAiAssistStop(); }''',
    "com/rokid/sprite/aiapp/externalapp/example/ExternalAppClient.java": '''package com.rokid.sprite.aiapp.externalapp.example; import android.content.Context; import com.rokid.cxr.link.callbacks.ICXRLinkCbk; import com.rokid.cxr.link.utils.CxrDefs; public class ExternalAppClient { public static int disconnectCalls=0; public static boolean throwOnDisconnect=false; public ExternalAppClient(Context c){} public final void setCXRLinkCbk(ICXRLinkCbk c){} public final boolean configCXRSession(CxrDefs.CXRSession s){return true;} public final boolean connect(String t){return true;} public final void disconnect(){disconnectCalls++; if(throwOnDisconnect) throw new RuntimeException("synthetic");} }''',
    "com/rokid/cxr/link/CXRLink.java": '''package com.rokid.cxr.link; import android.content.Context; import com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient; public class CXRLink extends ExternalAppClient { public CXRLink(Context c){super(c);} }''',
}

RUNTIME_HARNESS = r'''
package org.aimindseye.rokid.cxrlqualification;

import android.app.Activity;
import android.content.ServiceConnection;
import com.rokid.cxr.link.CXRLink;
import com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient;
import java.lang.reflect.Field;

public final class RuntimeRepairHarness {
    private static final class CountingActivity extends Activity {
        int unbindCalls;
        @Override
        public void unbindService(ServiceConnection connection) {
            unbindCalls++;
        }
    }

    private static void set(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(target, value);
    }

    private static CxrLSessionController controller(CountingActivity activity) throws Exception {
        EvidenceLogger logger = new EvidenceLogger(activity, "runtime-repair", "synthetic");
        return new CxrLSessionController(activity, logger, new CxrLSessionController.Callback() {
            @Override public void onStatus(String status) {}
            @Override public void onTerminal(String outcome, boolean success) {}
        });
    }

    public static void main(String[] args) throws Exception {
        CountingActivity firstActivity = new CountingActivity();
        CxrLSessionController first = controller(firstActivity);
        set(first, "link", new CXRLink(firstActivity));
        set(first, "manualConnection", new ServiceConnection() {});
        set(first, "manualBound", true);
        ExternalAppClient.disconnectCalls = 0;
        ExternalAppClient.throwOnDisconnect = false;
        first.disconnect("first");
        first.disconnect("duplicate");
        if (ExternalAppClient.disconnectCalls != 1) {
            throw new IllegalStateException("duplicate SDK disconnect was not suppressed");
        }
        if (firstActivity.unbindCalls != 0) {
            throw new IllegalStateException("manual unbind ran after successful SDK disconnect");
        }

        CountingActivity secondActivity = new CountingActivity();
        CxrLSessionController second = controller(secondActivity);
        set(second, "link", new CXRLink(secondActivity));
        set(second, "manualConnection", new ServiceConnection() {});
        set(second, "manualBound", true);
        ExternalAppClient.disconnectCalls = 0;
        ExternalAppClient.throwOnDisconnect = true;
        second.disconnect("sdk-failure");
        if (ExternalAppClient.disconnectCalls != 1) {
            throw new IllegalStateException("SDK disconnect failure path was not attempted once");
        }
        if (secondActivity.unbindCalls != 1) {
            throw new IllegalStateException("manual unbind did not run after SDK disconnect failure");
        }
        System.out.println("TEST19_R2_RUNTIME_DISCONNECT_POLICY=PASS");
    }
}
'''


def main() -> int:
    javac = shutil.which("javac")
    if not javac:
        print("TEST19_R2_JAVA_COMPILE=SKIP_JAVAC_UNAVAILABLE")
        return 0
    with tempfile.TemporaryDirectory(prefix="test19-r2-compile-") as temp_value:
        temp = Path(temp_value)
        stub_root = temp / "stubs"
        for relative, source in STUBS.items():
            path = stub_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        harness_path = temp / "harness/org/aimindseye/rokid/cxrlqualification/RuntimeRepairHarness.java"
        harness_path.parent.mkdir(parents=True, exist_ok=True)
        harness_path.write_text(RUNTIME_HARNESS, encoding="utf-8")
        out = temp / "classes"
        out.mkdir()
        sources = [str(path) for path in stub_root.rglob("*.java")]
        sources.extend(str(path) for path in sorted(APP.glob("*.java")))
        sources.append(str(harness_path))
        completed = subprocess.run(
            [javac, "-Xlint:all", "-d", str(out), *sources],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            print(completed.stdout, end="")
            print(completed.stderr, end="")
            print("TEST19_R2_JAVA_COMPILE=FAIL")
            return completed.returncode
        runtime = subprocess.run(
            [shutil.which("java") or "java", "-cp", str(out),
             "org.aimindseye.rokid.cxrlqualification.RuntimeRepairHarness"],
            check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp,
        )
        print(runtime.stdout, end="")
        if runtime.returncode != 0:
            print(runtime.stderr, end="")
            print("TEST19_R2_RUNTIME_DISCONNECT_POLICY=FAIL")
            return runtime.returncode
    print("TEST19_R2_JAVA_COMPILE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
