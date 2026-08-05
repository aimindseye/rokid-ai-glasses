#!/usr/bin/env python3
"""Compile Test22 r4.3 Java sources against bounded Android stubs."""
from __future__ import annotations
import shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'android-client/test22/src/main/java/org/aimindseye/rokid/test22wifi'
STUBS={
'android/R.java':'package android; public final class R { public static final class drawable { public static final int stat_sys_data_bluetooth=1; } }',
'android/app/Activity.java':'package android.app; public class Activity extends android.content.Context { protected void onCreate(android.os.Bundle b){} public void finish(){} }',
'android/app/Service.java':'package android.app; public class Service extends android.content.Context { public static final int START_STICKY=1; public void onCreate(){} public int onStartCommand(android.content.Intent i,int f,int id){return 0;} public android.os.IBinder onBind(android.content.Intent i){return null;} public void onDestroy(){} public void startForeground(int id, Notification n){} }',
'android/app/Notification.java':'package android.app; public class Notification { public static class Builder { public Builder(android.content.Context c){} public Builder(android.content.Context c,String s){} public Builder setSmallIcon(int i){return this;} public Builder setContentTitle(String s){return this;} public Builder setContentText(String s){return this;} public Builder setOngoing(boolean b){return this;} public Notification build(){return new Notification();} } }',
'android/app/NotificationChannel.java':'package android.app; public class NotificationChannel { public NotificationChannel(String a,String b,int c){} public void setDescription(String s){} }',
'android/app/NotificationManager.java':'package android.app; public class NotificationManager { public static final int IMPORTANCE_LOW=2; public void createNotificationChannel(NotificationChannel c){} }',
'android/os/Bundle.java':'package android.os; public class Bundle {}',
'android/os/IBinder.java':'package android.os; public interface IBinder {}',
'android/os/Build.java':'package android.os; public class Build { public static class VERSION { public static int SDK_INT=32; } }',
'android/content/Intent.java':'package android.content; public class Intent { public static final String ACTION_MY_PACKAGE_REPLACED="android.intent.action.MY_PACKAGE_REPLACED"; private String a=""; public Intent(){} public Intent(Context c, Class<?> k){} public Intent setAction(String s){a=s; return this;} public String getAction(){return a;} }',
'android/content/BroadcastReceiver.java':'package android.content; public abstract class BroadcastReceiver { public abstract void onReceive(Context c, Intent i); }',
'android/content/pm/ApplicationInfo.java':'package android.content.pm; public class ApplicationInfo { public int targetSdkVersion=28; }',
'android/content/pm/PackageManager.java':'package android.content.pm; public class PackageManager { public static final String FEATURE_WIFI="wifi"; public boolean hasSystemFeature(String s){return true;} }',
'android/content/Context.java':'package android.content; import java.io.File; public class Context { public static final String WIFI_SERVICE="wifi"; public static final String CONNECTIVITY_SERVICE="connectivity"; public static final String NOTIFICATION_SERVICE="notification"; public Context getApplicationContext(){return this;} public Object getSystemService(String s){ if(WIFI_SERVICE.equals(s)) return new android.net.wifi.WifiManager(); if(CONNECTIVITY_SERVICE.equals(s)) return new android.net.ConnectivityManager(); if(NOTIFICATION_SERVICE.equals(s)) return new android.app.NotificationManager(); return null; } public android.content.pm.PackageManager getPackageManager(){return new android.content.pm.PackageManager();} public android.content.pm.ApplicationInfo getApplicationInfo(){return new android.content.pm.ApplicationInfo();} public String getPackageName(){return "org.aimindseye.rokid.test22wifi";} public File getExternalFilesDir(String s){return new File(".");} public String getPackageCodePath(){return "./base.apk";} public Intent startForegroundService(Intent i){return i;} public Intent startService(Intent i){return i;} }',
'android/net/wifi/WifiConfiguration.java':'package android.net.wifi; import java.util.BitSet; public class WifiConfiguration { public String SSID; public String preSharedKey; public BitSet allowedKeyManagement=new BitSet(); public static class KeyMgmt { public static final int WPA_PSK=1; } }',
'android/net/wifi/WifiManager.java':'package android.net.wifi; public class WifiManager { public boolean isWifiEnabled(){return true;} public boolean setWifiEnabled(boolean b){return true;} public int addNetwork(WifiConfiguration c){return 1;} public boolean enableNetwork(int i,boolean b){return true;} public boolean reconnect(){return true;} public boolean removeNetwork(int i){return true;} }',
'android/net/NetworkCapabilities.java':'package android.net; public class NetworkCapabilities { public static final int TRANSPORT_WIFI=1; public boolean hasTransport(int t){return true;} }',
'android/net/Network.java':'package android.net; import java.net.*; public class Network { public long getNetworkHandle(){return 1L;} public InetAddress[] getAllByName(String s) throws UnknownHostException{return InetAddress.getAllByName("127.0.0.1");} public SocketFactory getSocketFactory(){return new SocketFactory();} public static class SocketFactory { public Socket createSocket(){return new Socket();} } }',
'android/net/LinkAddress.java':'package android.net; import java.net.*; public class LinkAddress { public InetAddress getAddress(){try{return InetAddress.getByName("192.168.1.2");}catch(Exception e){return null;}} }',
'android/net/RouteInfo.java':'package android.net; public class RouteInfo { public boolean isDefaultRoute(){return true;} }',
'android/net/LinkProperties.java':'package android.net; import java.util.*; public class LinkProperties { public java.util.List<LinkAddress> getLinkAddresses(){return java.util.Arrays.asList(new LinkAddress());} public java.util.List<RouteInfo> getRoutes(){return java.util.Arrays.asList(new RouteInfo());} public String getInterfaceName(){return "wlan0";} }',
'android/net/ConnectivityManager.java':'package android.net; public class ConnectivityManager { public Network[] getAllNetworks(){return new Network[]{new Network()};} public NetworkCapabilities getNetworkCapabilities(Network n){return new NetworkCapabilities();} public LinkProperties getLinkProperties(Network n){return new LinkProperties();} }',
'org/json/JSONObject.java':'package org.json; public class JSONObject { public JSONObject(){} public JSONObject(String s){} public JSONObject put(String k,Object v){return this;} public String optString(String k,String d){return d;} public String toString(){return "{}";} public String toString(int i){return "{}";} }',
}

def main():
    javac=shutil.which('javac')
    if not javac:
        print('TEST22_R4_3_JAVA_COMPILE=SKIP_JAVAC_UNAVAILABLE'); return 0
    with tempfile.TemporaryDirectory(prefix='test22-r43-compile-') as td:
        t=Path(td); st=t/'stubs'; out=t/'classes'; out.mkdir()
        for rel,src in STUBS.items():
            p=st/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(src)
        sources=[str(p) for p in st.rglob('*.java')]+[str(p) for p in APP.glob('*.java')]
        c=subprocess.run([javac,'-Xlint:none','-d',str(out),*sources],text=True,capture_output=True)
        if c.returncode:
            print(c.stdout,end=''); print(c.stderr,end=''); print('TEST22_R4_3_JAVA_COMPILE=FAIL'); return c.returncode
    print('TEST22_R4_3_JAVA_COMPILE=PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
