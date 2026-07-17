# Endpoint Inventory

Purposes below are evidence-based interpretations, not vendor-confirmed
service definitions.

| Host | Sanitized path or role | First test | Interpretation |
|---|---|---:|---|
| `firebase-settings.crashlytics.com` | Crashlytics settings | 00 | Crash-report configuration |
| `firebaseinstallations.googleapis.com` | Firebase installation | 00 | Firebase installation identity |
| `rcs-internal.rokid.com` | `/gather/batchSend` | 00/03b | Telemetry or batched event collection |
| `rcs-internal.rokid.com` | `/talos/checkFunctionAvailable` | 03b | Feature availability |
| `rcs-internal.rokid.com` | `/ymir/user/getHomeInfo` | 03b | Home/account content |
| `rcs-internal.rokid.com` | `/ymir/user/getHomePage` | 03b | Home-page content |
| `rcs-internal.rokid.com` | `/device/bindGlassesDevice` | 03b | Device binding |
| `xr-cloud-global.rokid.com` | `/biz/glasses/v1/api/flight` | 03b | Glasses feature/catalog data |
| `xr-cloud-global.rokid.com` | `/auth/base/asr/getToken` | 03b | ASR token issuance |
| `xr-cloud-global.rokid.com` | `/geolocation/queryCountryCode` | 03b | Country lookup |
| `ar-service.rokid.com` | `/oauth/token` | 03b | Application OAuth token request |
| `ar-service.rokid.com` | `/oauth2/appUpgrade` | 03b | Application upgrade metadata |
| `device-account-prod.rokid.com` | `/device/loginV6.do` | 03b | Device/account login |
| `ai-cloud-global.rokid.com` | `/manager/v3/api/model/aggregate` | 03b | Model catalog/selection metadata |
| `ai-cloud-global.rokid.com` | `/ws/ai` | 03b | AI WebSocket gateway |
| `ota.rokid.com` | `/v1/extended/ota/check` | 03b | OTA check |
| `ota-g.rokidcdn.com` | Android metadata JSON | 03b | CDN-hosted update metadata |
| `imgs-ac.alipay.com` | `/imgw.htm` | 03b | Image service used by bundled component |
| `firebaselogging-pa.googleapis.com` | Firebase batch logging | 03b | Firebase telemetry |

The generated public request inventory under `evidence/sanitized/03b/` is the
canonical sanitized path list for Test 03b.
