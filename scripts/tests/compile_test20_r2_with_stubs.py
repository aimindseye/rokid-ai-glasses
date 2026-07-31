#!/usr/bin/env python3
"""Compile Test 20 r2 Java sources against controlled Android/CXR-L stubs."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "android-client/test20r2/src/main/java"
PACKAGE_ROOT = SOURCE_ROOT / "org/aimindseye/rokid/cxreventqualification"

STUBS = {
    "android/Manifest.java": """package android; public final class Manifest { public static final class permission { public static final String BLUETOOTH_CONNECT=\"android.permission.BLUETOOTH_CONNECT\"; } }""",
    "android/app/Activity.java": """package android.app; import android.content.*; import android.content.pm.*; import android.content.res.Resources; import android.os.Bundle; public class Activity extends Context { public static final int RESULT_CANCELED=0; public void startActivityForResult(Intent i,int r){} protected void onActivityResult(int a,int b,Intent c){} protected void onCreate(Bundle b){} protected void onDestroy(){} public void runOnUiThread(Runnable r){r.run();} public Intent getIntent(){return new Intent();} public void setContentView(Object v){} public int checkSelfPermission(String p){return PackageManager.PERMISSION_GRANTED;} public void requestPermissions(String[] p,int r){} public Resources getResources(){return new Resources();} }""",
    "android/content/Context.java": """package android.content; import android.content.pm.PackageManager; import java.io.File; public class Context { public static final int BIND_AUTO_CREATE=1; public Context getApplicationContext(){return this;} public String getPackageName(){return \"stub\";} public PackageManager getPackageManager(){return new PackageManager();} public File getExternalFilesDir(String t){return new File(System.getProperty(\"java.io.tmpdir\"));} public boolean bindService(Intent i, ServiceConnection c, int f){return true;} public void unbindService(ServiceConnection c){} }""",
    "android/content/ComponentName.java": """package android.content; public class ComponentName { public ComponentName(String p,String c){} public String flattenToShortString(){return \"stub\";} }""",
    "android/content/Intent.java": """package android.content; public class Intent { public Intent(){} public Intent(String a){} public Intent setComponent(ComponentName c){return this;} public Intent setPackage(String p){return this;} public Intent putExtra(String k,String v){return this;} public String getStringExtra(String k){return null;} }""",
    "android/content/ServiceConnection.java": """package android.content; public interface ServiceConnection {}""",
    "android/content/pm/PackageManager.java": """package android.content.pm; import android.content.Intent; public class PackageManager { public static final int MATCH_DEFAULT_ONLY=65536; public static final int PERMISSION_GRANTED=0; public PackageInfo getPackageInfo(String p,int f) throws NameNotFoundException{return new PackageInfo();} public PackageInfo getPackageInfo(String p,PackageInfoFlags f) throws NameNotFoundException{return new PackageInfo();} public ResolveInfo resolveActivity(Intent i,int f){return new ResolveInfo();} public ResolveInfo resolveService(Intent i,int f){return new ResolveInfo();} public static final class PackageInfoFlags { public static PackageInfoFlags of(long v){return new PackageInfoFlags();} } public static class NameNotFoundException extends Exception {} }""",
    "android/content/pm/PackageInfo.java": """package android.content.pm; public class PackageInfo { public String versionName=\"1.0-test20-r2\"; public long getLongVersionCode(){return 1;} }""",
    "android/content/pm/ResolveInfo.java": """package android.content.pm; public class ResolveInfo { public ActivityInfo activityInfo=new ActivityInfo(); public ServiceInfo serviceInfo=new ServiceInfo(); }""",
    "android/content/pm/ActivityInfo.java": """package android.content.pm; public class ActivityInfo { public boolean exported=true; public String packageName=\"stub\"; public String name=\"stub\"; }""",
    "android/content/pm/ServiceInfo.java": """package android.content.pm; public class ServiceInfo { public boolean exported=true; public String packageName=\"stub\"; public String name=\"stub\"; }""",
    "android/content/res/Resources.java": """package android.content.res; import android.util.DisplayMetrics; public class Resources { public DisplayMetrics getDisplayMetrics(){return new DisplayMetrics();} }""",
    "android/os/Build.java": """package android.os; public final class Build { public static final class VERSION { public static int SDK_INT=36; } }""",
    "android/os/Bundle.java": """package android.os; public class Bundle {}""",
    "android/os/Looper.java": """package android.os; public class Looper { public static Looper getMainLooper(){return new Looper();} }""",
    "android/os/Handler.java": """package android.os; public class Handler { public Handler(Looper l){} public boolean postDelayed(Runnable r,long d){return true;} public void removeCallbacksAndMessages(Object t){} }""",
    "android/os/SystemClock.java": """package android.os; public final class SystemClock { public static long elapsedRealtime(){return 1L;} }""",
    "android/util/Log.java": """package android.util; public final class Log { public static int i(String t,String m){return 0;} public static int e(String t,String m,Throwable x){return 0;} }""",
    "android/util/DisplayMetrics.java": """package android.util; public class DisplayMetrics { public float density=1.0f; }""",
    "android/widget/TextView.java": """package android.widget; import android.content.Context; public class TextView { public TextView(Context c){} public void setText(String s){} public void setTextSize(float s){} public void setPadding(int a,int b,int c,int d){} }""",
    "android/widget/Button.java": """package android.widget; import android.content.Context; import android.view.View; public class Button extends TextView { public Button(Context c){super(c);} public void setAllCaps(boolean b){} public void setEnabled(boolean b){} public void setOnClickListener(View.OnClickListener l){} }""",
    "android/widget/LinearLayout.java": """package android.widget; import android.content.Context; public class LinearLayout { public static final int VERTICAL=1; public LinearLayout(Context c){} public void setOrientation(int o){} public void setPadding(int a,int b,int c,int d){} public void addView(Object v){} }""",
    "android/widget/ScrollView.java": """package android.widget; import android.content.Context; public class ScrollView { public ScrollView(Context c){} public void addView(Object v){} }""",
    "android/view/View.java": """package android.view; public class View { public interface OnClickListener { void onClick(View v); } }""",
    "org/json/JSONException.java": """package org.json; public class JSONException extends Exception { public JSONException(){} public JSONException(String s){super(s);} }""",
    "org/json/JSONObject.java": """package org.json; import java.util.*; public class JSONObject { private final Map<String,Object> m=new HashMap<>(); public JSONObject put(String k,Object v) throws JSONException {m.put(k,v); return this;} public String toString(){return m.toString();} }""",
    "com/rokid/cxr/link/callbacks/ICXRLinkCbk.java": """package com.rokid.cxr.link.callbacks; public interface ICXRLinkCbk { void onCXRLConnected(boolean b); void onGlassBtConnected(boolean b); void onGlassAiAssistStart(); void onGlassAiAssistStop(); }""",
    "com/rokid/cxr/link/utils/CxrDefs.java": """package com.rokid.cxr.link.utils; public final class CxrDefs { public enum CXRSessionType { NONE,CUSTOMVIEW,CUSTOMAPP } public static final class CXRSession { public CXRSession(CXRSessionType t,String p){} } }""",
    "com/rokid/cxr/link/CXRLink.java": """package com.rokid.cxr.link; import android.content.Context; import android.content.ServiceConnection; import com.rokid.cxr.link.callbacks.ICXRLinkCbk; import com.rokid.cxr.link.utils.CxrDefs; public class CXRLink { private ServiceConnection connection; public CXRLink(Context c){} public void setCXRLinkCbk(ICXRLinkCbk c){} public boolean configCXRSession(CxrDefs.CXRSession s){return true;} public boolean connect(String t){return false;} public void disconnect(){} }""",
}


def main() -> int:
    if shutil.which("javac") is None:
        print("FAIL: javac is unavailable", file=sys.stderr)
        return 1
    sources = sorted(PACKAGE_ROOT.glob("*.java"))
    if len(sources) != 6:
        print(f"FAIL: expected 6 Test 20 r2 Java sources, found {len(sources)}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="test20-r2-javac-") as temp:
        temp_root = Path(temp)
        stub_root = temp_root / "stubs"
        classes = temp_root / "classes"
        classes.mkdir()
        for rel, content in STUBS.items():
            path = stub_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content + "\n", encoding="utf-8")
        command = [
            "javac", "-source", "17", "-target", "17", "-d", str(classes),
            *[str(path) for path in sorted(stub_root.rglob("*.java"))],
            *[str(path) for path in sources],
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            print("TEST20_R2_JAVA_STUB_COMPILE=FAIL")
            return completed.returncode
    print("TEST20_R2_JAVA_SOURCE_COUNT=6")
    print("TEST20_R2_JAVA_STUB_COMPILE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
