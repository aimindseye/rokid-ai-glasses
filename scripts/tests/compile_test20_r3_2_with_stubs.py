#!/usr/bin/env python3
from pathlib import Path
import shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
PKG=ROOT/'android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification'
STUBS={
'android/Manifest.java':'package android; public final class Manifest { public static final class permission { public static final String BLUETOOTH_CONNECT="x"; } }',
'android/os/Bundle.java':'package android.os; public class Bundle {}',
'android/os/Build.java':'package android.os; public final class Build { public static final class VERSION { public static int SDK_INT=36; } }',
'android/os/Looper.java':'package android.os; public class Looper { public static Looper getMainLooper(){return new Looper();} }',
'android/os/Handler.java':'package android.os; public class Handler { public Handler(Looper l){} public boolean postDelayed(Runnable r,long d){return true;} public void removeCallbacksAndMessages(Object o){} }',
'android/os/SystemClock.java':'package android.os; public class SystemClock { public static long elapsedRealtime(){return 1L;} }',
'android/content/Context.java':'package android.content; import android.content.pm.PackageManager; import android.content.res.Resources; import java.io.File; public class Context { public static final int BIND_AUTO_CREATE=1; public Context getApplicationContext(){return this;} public File getExternalFilesDir(String s){return new File(".");} public PackageManager getPackageManager(){return new PackageManager();} public String getPackageName(){return "x";} public boolean bindService(Intent i,ServiceConnection c,int f){return true;} public void unbindService(ServiceConnection c){} public Resources getResources(){return new Resources();} }',
'android/content/Intent.java':'package android.content; public class Intent { public Intent(){} public Intent(String a){} public Intent setPackage(String p){return this;} public Intent setComponent(ComponentName c){return this;} public Intent putExtra(String k,String v){return this;} public String getStringExtra(String k){return null;} public ComponentName getComponent(){return null;} }',
'android/content/ComponentName.java':'package android.content; public class ComponentName { public ComponentName(String p,String c){} public String getPackageName(){return "";} public String getClassName(){return "";} public String flattenToShortString(){return "";} }',
'android/content/ServiceConnection.java':'package android.content; public interface ServiceConnection {}',
'android/content/pm/PackageInfo.java':'package android.content.pm; public class PackageInfo { public String versionName=""; public long getLongVersionCode(){return 1;} }',
'android/content/pm/ActivityInfo.java':'package android.content.pm; public class ActivityInfo { public boolean exported; public String packageName=""; public String name=""; }',
'android/content/pm/ServiceInfo.java':'package android.content.pm; public class ServiceInfo { public boolean exported; public String packageName=""; public String name=""; }',
'android/content/pm/ResolveInfo.java':'package android.content.pm; public class ResolveInfo { public ActivityInfo activityInfo; public ServiceInfo serviceInfo; }',
'android/content/pm/PackageManager.java':'package android.content.pm; import android.content.Intent; public class PackageManager { public static final int PERMISSION_GRANTED=0; public static final int MATCH_DEFAULT_ONLY=1; public static final class PackageInfoFlags { public static PackageInfoFlags of(long x){return new PackageInfoFlags();} } public static class NameNotFoundException extends Exception {} public PackageInfo getPackageInfo(String p,int f) throws NameNotFoundException{return new PackageInfo();} public PackageInfo getPackageInfo(String p,PackageInfoFlags f) throws NameNotFoundException{return new PackageInfo();} public ResolveInfo resolveActivity(Intent i,int f){return new ResolveInfo();} public ResolveInfo resolveService(Intent i,int f){return new ResolveInfo();} }',
'android/content/res/Resources.java':'package android.content.res; import android.util.DisplayMetrics; public class Resources { public DisplayMetrics getDisplayMetrics(){return new DisplayMetrics();} }',
'android/app/Activity.java':'package android.app; import android.content.*; import android.content.pm.*; import android.content.res.Resources; import android.os.Bundle; public class Activity extends Context { public static final int RESULT_OK=-1; public static final int RESULT_CANCELED=0; protected void onCreate(Bundle b){} protected void onDestroy(){} protected void onActivityResult(int a,int b,Intent c){} public Intent getIntent(){return new Intent();} public void setContentView(Object v){} public void startActivityForResult(Intent i,int c){} public int checkSelfPermission(String p){return 0;} public void requestPermissions(String[] p,int c){} public void runOnUiThread(Runnable r){r.run();} public Resources getResources(){return new Resources();} }',
'android/util/Log.java':'package android.util; public class Log { public static int i(String t,String m){return 0;} public static int e(String t,String m,Throwable x){return 0;} }',
'android/util/DisplayMetrics.java':'package android.util; public class DisplayMetrics { public float density=1.0f; }',
'android/view/View.java':'package android.view; public class View { public interface OnClickListener { void onClick(View v); } }',
'android/widget/TextView.java':'package android.widget; import android.content.Context; public class TextView { public TextView(Context c){} public void setText(String s){} public void setTextSize(float s){} public void setPadding(int a,int b,int c,int d){} }',
'android/widget/Button.java':'package android.widget; import android.content.Context; import android.view.View; public class Button extends TextView { public Button(Context c){super(c);} public void setAllCaps(boolean b){} public void setEnabled(boolean b){} public void setOnClickListener(View.OnClickListener l){} }',
'android/widget/LinearLayout.java':'package android.widget; import android.content.Context; public class LinearLayout { public static final int VERTICAL=1; public LinearLayout(Context c){} public void setOrientation(int o){} public void setPadding(int a,int b,int c,int d){} public void addView(Object v){} }',
'android/widget/ScrollView.java':'package android.widget; import android.content.Context; public class ScrollView { public ScrollView(Context c){} public void addView(Object v){} }',
'android/graphics/BitmapFactory.java':'package android.graphics; public class BitmapFactory { public static class Options { public boolean inJustDecodeBounds; public int outWidth=1; public int outHeight=1; public String outMimeType="image/jpeg"; } public static Object decodeByteArray(byte[] b,int o,int l,Options x){return null;} }',
'org/json/JSONException.java':'package org.json; public class JSONException extends Exception {}',
'org/json/JSONObject.java':'package org.json; public class JSONObject { public JSONObject put(String k,Object v) throws JSONException{return this;} public String toString(){return "{}";} }',
'com/rokid/cxr/link/callbacks/ICXRLinkCbk.java':'package com.rokid.cxr.link.callbacks; public interface ICXRLinkCbk { void onCXRLConnected(boolean b); void onGlassBtConnected(boolean b); void onGlassAiAssistStart(); void onGlassAiAssistStop(); }',
'com/rokid/cxr/link/callbacks/IImageStreamCbk.java':'package com.rokid.cxr.link.callbacks; public interface IImageStreamCbk { void onImageReceived(byte[] b); void onImageError(int c,String m); }',
'com/rokid/cxr/link/utils/CxrDefs.java':'package com.rokid.cxr.link.utils; public final class CxrDefs { public enum CXRSessionType { NONE,CUSTOMVIEW,CUSTOMAPP } public static final class CXRSession { public CXRSession(CXRSessionType t,String p){} } }',
'com/rokid/cxr/link/CXRLink.java':'package com.rokid.cxr.link; import android.content.*; import com.rokid.cxr.link.callbacks.*; import com.rokid.cxr.link.utils.CxrDefs; public class CXRLink { private ServiceConnection connection; public CXRLink(Context c){} public void setCXRLinkCbk(ICXRLinkCbk c){} public void setCXRImageCbk(IImageStreamCbk c){} public boolean configCXRSession(CxrDefs.CXRSession s){return true;} public boolean connect(String t){return false;} public void disconnect(){} public String getServiceVersion(){return "1";} public Integer getServiceVersionCode(){return 1;} public boolean isGlassBtConnected(){return true;} public boolean takePhoto(int a,int b,int c){return true;} }',
}
def main():
    if shutil.which('javac') is None: print('FAIL: javac unavailable',file=sys.stderr); return 1
    sources=sorted(PKG.glob('*.java'))
    if len(sources)!=6: print(f'FAIL: expected 6 Java sources, found {len(sources)}',file=sys.stderr); return 1
    with tempfile.TemporaryDirectory(prefix='test20-r3-2-javac-') as t:
        t=Path(t); st=t/'stubs'; out=t/'classes'; out.mkdir()
        for rel,content in STUBS.items():
            p=st/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content+'\n')
        cmd=['javac','-source','17','-target','17','-d',str(out),*[str(p) for p in sorted(st.rglob('*.java'))],*[str(p) for p in sources]]
        r=subprocess.run(cmd,text=True,capture_output=True)
        if r.returncode:
            print(r.stdout,end=''); print(r.stderr,end='',file=sys.stderr); print('TEST20_R3_2_JAVA_STUB_COMPILE=FAIL'); return r.returncode
    print('TEST20_R3_2_JAVA_SOURCE_COUNT=6')
    print('TEST20_R3_2_JAVA_STUB_COMPILE=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
