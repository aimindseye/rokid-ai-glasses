package org.aimindseye.rokid.test22wifi;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.RouteInfo;
import android.net.wifi.WifiConfiguration;
import android.net.wifi.WifiManager;
import android.os.Build;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.util.Base64;

import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.TrustManagerFactory;

@SuppressWarnings("deprecation")
public final class Test22Probe {
    private static final String SCHEMA = "rokid.test22.app-result.v1";
    private static final long WIFI_ENABLE_TIMEOUT_MS = 20_000L;
    private static final long WIFI_NETWORK_TIMEOUT_MS = 45_000L;
    private static final int SOCKET_TIMEOUT_MS = 12_000;

    private final Context context;
    private final JSONObject config;

    public Test22Probe(Context context, JSONObject config) {
        this.context = context.getApplicationContext();
        this.config = config;
    }

    public JSONObject run() throws Exception {
        long started = System.currentTimeMillis();
        JSONObject result = new JSONObject();
        result.put("schema", SCHEMA);
        result.put("started_unix_ms", started);
        result.put("sdk_int", Build.VERSION.SDK_INT);
        result.put("package_name", context.getPackageName());
        result.put("control_plane_marker", MainActivity.CONTROL_PLANE_MARKER);

        ApplicationInfo appInfo = context.getApplicationInfo();
        result.put("target_sdk", appInfo.targetSdkVersion);
        result.put("bluetooth_api_used", false);
        result.put("cxr_api_used", false);
        result.put("phone_companion_api_used", false);
        result.put("default_network_socket_used", false);
        result.put("config_transport", "adb_forward_loopback_json");
        result.put("result_transport", "adb_forward_loopback_json");
        result.put("probe_execution_started", true);

        String ssid = decodeRequired("ssid_b64");
        String psk = decodeRequired("psk_b64");
        String backendHost = required("backend_host");
        int backendPort = Integer.parseInt(required("backend_port"));
        String nonce = required("nonce");
        String commandNonce = required("command_nonce");
        String dnsName = optional("dns_name");
        byte[] caPem = Base64.getDecoder().decode(required("ca_pem_b64"));

        result.put("ssid_sha256", sha256(ssid));
        result.put("backend_host_sha256", sha256(backendHost));
        result.put("nonce_sha256", sha256(nonce));
        result.put("command_nonce_sha256", sha256(commandNonce));
        result.put("dns_requested", !dnsName.isEmpty());
        if (!dnsName.isEmpty()) {
            result.put("dns_name_sha256", sha256(dnsName));
        }

        PackageManager packageManager = context.getPackageManager();
        boolean featureWifi = packageManager.hasSystemFeature(PackageManager.FEATURE_WIFI);
        result.put("feature_wifi", featureWifi);

        Test22ControlService.noteWifiApiTouched();
        result.put("wifi_api_touched", true);
        WifiManager wifi = (WifiManager) context.getSystemService(Context.WIFI_SERVICE);
        ConnectivityManager connectivity =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        result.put("wifi_service_present", wifi != null);
        result.put("connectivity_service_present", connectivity != null);

        int networkId = -1;
        boolean addedByTest = false;
        boolean wifiEnabledBefore = false;
        try {
            if (!featureWifi || wifi == null || connectivity == null) {
                result.put("completed", true);
                result.put("phase_terminal", "NO_WIFI_FRAMEWORK_CAPABILITY");
                return finish(result, started);
            }

            wifiEnabledBefore = wifi.isWifiEnabled();
            result.put("wifi_enabled_before", wifiEnabledBefore);

            boolean enableRequested = false;
            boolean enableReturn = true;
            if (!wifiEnabledBefore) {
                enableRequested = true;
                enableReturn = wifi.setWifiEnabled(true);
            }
            result.put("wifi_enable_requested_by_app", enableRequested);
            result.put("wifi_enable_request_return", enableReturn);
            boolean enabledAfterRequest = waitForWifiEnabled(wifi, WIFI_ENABLE_TIMEOUT_MS);
            result.put("wifi_enabled_after_request", enabledAfterRequest);
            if (!enabledAfterRequest) {
                result.put("completed", true);
                result.put("phase_terminal", "WIFI_ENABLE_BLOCKED_OR_TIMED_OUT");
                return finish(result, started);
            }

            WifiConfiguration network = new WifiConfiguration();
            network.SSID = quote(ssid);
            network.preSharedKey = quote(psk);
            network.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_PSK);
            networkId = wifi.addNetwork(network);
            addedByTest = networkId >= 0;
            result.put("wifi_network_add_id_nonnegative", addedByTest);
            if (!addedByTest) {
                result.put("completed", true);
                result.put("phase_terminal", "WIFI_CONFIGURATION_ADD_BLOCKED");
                return finish(result, started);
            }

            boolean enableNetworkReturn = wifi.enableNetwork(networkId, true);
            boolean reconnectReturn = wifi.reconnect();
            result.put("wifi_enable_network_return", enableNetworkReturn);
            result.put("wifi_reconnect_return", reconnectReturn);

            WifiSelection selection = waitForWifiNetwork(connectivity, WIFI_NETWORK_TIMEOUT_MS);
            result.put("wifi_transport_found", selection != null);
            if (selection == null) {
                result.put("completed", true);
                result.put("phase_terminal", "WIFI_ASSOCIATION_OR_ROUTE_TIMED_OUT");
                return finish(result, started);
            }

            result.put("wifi_interface", selection.interfaceName == null ? "" : selection.interfaceName);
            result.put("wifi_default_route", selection.defaultRoute);
            result.put("wifi_ipv4_link_present", selection.ipv4Address != null);
            if (selection.ipv4Address != null) {
                result.put("wifi_local_ip_sha256", sha256(selection.ipv4Address.getHostAddress()));
            }
            result.put("wifi_network_handle", selection.network.getNetworkHandle());

            if (!dnsName.isEmpty()) {
                try {
                    InetAddress[] resolved = selection.network.getAllByName(dnsName);
                    result.put("dns_success", resolved != null && resolved.length > 0);
                    result.put("dns_answer_count", resolved == null ? 0 : resolved.length);
                } catch (Exception error) {
                    result.put("dns_success", false);
                    result.put("dns_error_class", error.getClass().getName());
                }
            }

            try {
                runTlsProbe(result, selection, caPem, backendHost, backendPort, nonce);
                result.put("phase_terminal", "PROBE_COMPLETED");
            } catch (Exception error) {
                result.put("tls_probe_error_class", error.getClass().getName());
                result.put("phase_terminal", "DIRECT_TLS_PROBE_FAILED");
            }
            result.put("completed", true);
            return finish(result, started);
        } finally {
            JSONObject cleanup = new JSONObject();
            if (wifi != null && addedByTest && networkId >= 0) {
                try {
                    cleanup.put("remove_test_network_return", wifi.removeNetwork(networkId));
                } catch (Exception error) {
                    cleanup.put("remove_test_network_error_class", error.getClass().getName());
                }
            }
            if (wifi != null && !wifiEnabledBefore) {
                try {
                    cleanup.put("restore_wifi_disabled_return", wifi.setWifiEnabled(false));
                } catch (Exception error) {
                    cleanup.put("restore_wifi_error_class", error.getClass().getName());
                }
            }
            result.put("cleanup", cleanup);
        }
    }

    private void runTlsProbe(
            JSONObject result,
            WifiSelection selection,
            byte[] caPem,
            String backendHost,
            int backendPort,
            String nonce) throws Exception {
        SSLContext sslContext = sslContext(caPem);
        Socket raw = selection.network.getSocketFactory().createSocket();
        raw.connect(new InetSocketAddress(backendHost, backendPort), SOCKET_TIMEOUT_MS);
        raw.setSoTimeout(SOCKET_TIMEOUT_MS);
        result.put("tcp_connect_success", true);

        InetAddress local = raw.getLocalAddress();
        String localHash = sha256(local.getHostAddress());
        result.put("socket_local_ip_sha256", localHash);
        result.put("socket_local_matches_wifi_link_address",
                selection.ipv4Address != null
                        && local.getHostAddress().equals(selection.ipv4Address.getHostAddress()));

        SSLSocket tls = (SSLSocket) sslContext.getSocketFactory()
                .createSocket(raw, backendHost, backendPort, true);
        SSLParameters parameters = tls.getSSLParameters();
        parameters.setEndpointIdentificationAlgorithm("HTTPS");
        tls.setSSLParameters(parameters);
        tls.startHandshake();
        result.put("tls_handshake_success", true);
        result.put("tls_protocol", tls.getSession().getProtocol());

        OutputStreamWriter writer = new OutputStreamWriter(tls.getOutputStream(), StandardCharsets.UTF_8);
        BufferedReader reader = new BufferedReader(
                new InputStreamReader(tls.getInputStream(), StandardCharsets.UTF_8));
        writer.write("TEST22|" + nonce + "\n");
        writer.flush();
        String response = reader.readLine();
        boolean echo = ("TEST22-OK|" + nonce).equals(response);
        result.put("tls_echo_verified", echo);
        tls.close();
    }

    private static SSLContext sslContext(byte[] caPem) throws Exception {
        CertificateFactory factory = CertificateFactory.getInstance("X.509");
        Certificate ca;
        try (ByteArrayInputStream input = new ByteArrayInputStream(caPem)) {
            ca = factory.generateCertificate(input);
        }
        KeyStore store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null, null);
        store.setCertificateEntry("test22-ca", ca);
        TrustManagerFactory tmf = TrustManagerFactory.getInstance(
                TrustManagerFactory.getDefaultAlgorithm());
        tmf.init(store);
        SSLContext context = SSLContext.getInstance("TLS");
        context.init(null, tmf.getTrustManagers(), null);
        return context;
    }

    private static WifiSelection waitForWifiNetwork(
            ConnectivityManager connectivity, long timeoutMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            for (Network network : connectivity.getAllNetworks()) {
                NetworkCapabilities capabilities = connectivity.getNetworkCapabilities(network);
                if (capabilities == null
                        || !capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                    continue;
                }
                LinkProperties links = connectivity.getLinkProperties(network);
                if (links == null) {
                    continue;
                }
                Inet4Address ipv4 = null;
                for (LinkAddress link : links.getLinkAddresses()) {
                    if (link.getAddress() instanceof Inet4Address) {
                        ipv4 = (Inet4Address) link.getAddress();
                        break;
                    }
                }
                boolean defaultRoute = false;
                for (RouteInfo route : links.getRoutes()) {
                    if (route.isDefaultRoute()) {
                        defaultRoute = true;
                        break;
                    }
                }
                if (ipv4 != null) {
                    return new WifiSelection(network, links.getInterfaceName(), ipv4, defaultRoute);
                }
            }
            Thread.sleep(500L);
        }
        return null;
    }

    private static boolean waitForWifiEnabled(WifiManager wifi, long timeoutMs)
            throws InterruptedException {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (wifi.isWifiEnabled()) {
                return true;
            }
            Thread.sleep(250L);
        }
        return wifi.isWifiEnabled();
    }

    private static JSONObject finish(JSONObject result, long started) throws Exception {
        result.put("finished_unix_ms", System.currentTimeMillis());
        result.put("duration_ms", System.currentTimeMillis() - started);
        return result;
    }

    private String required(String name) {
        String value = config == null ? "" : config.optString(name, "");
        value = value == null ? "" : value.trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("missing required control field: " + name);
        }
        return value;
    }

    private String optional(String name) {
        String value = config == null ? "" : config.optString(name, "");
        return value == null ? "" : value.trim();
    }

    private String decodeRequired(String name) {
        return new String(Base64.getDecoder().decode(required(name)), StandardCharsets.UTF_8);
    }

    private static String quote(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static String sha256(String value) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder output = new StringBuilder(bytes.length * 2);
        for (byte item : bytes) {
            output.append(String.format("%02x", item & 0xff));
        }
        return output.toString();
    }

    private static final class WifiSelection {
        final Network network;
        final String interfaceName;
        final Inet4Address ipv4Address;
        final boolean defaultRoute;

        WifiSelection(Network network, String interfaceName, Inet4Address ipv4Address,
                boolean defaultRoute) {
            this.network = network;
            this.interfaceName = interfaceName;
            this.ipv4Address = ipv4Address;
            this.defaultRoute = defaultRoute;
        }
    }
}
