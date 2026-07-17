# Test 03b — Sanitized HTTP Request Paths

All query values and identifier-like path segments are redacted.

| Method | Host | Sanitized path | Count |
|---|---|---|---:|
| `POST` | `rcs-internal.rokid.com` | `/gather/batchSend` | 1 |
| `GET` | `xr-cloud-global.rokid.com` | `/biz/glasses/v1/api/flight?pageNum=[REDACTED]&pageSize=[REDACTED]` | 1 |
| `POST` | `rcs-internal.rokid.com` | `/talos/checkFunctionAvailable` | 1 |
| `POST` | `ar-service.rokid.com` | `/oauth/token?clientId=[REDACTED]&clientSecret=[REDACTED]&grantType=[REDACTED]` | 1 |
| `POST` | `rcs-internal.rokid.com` | `/ymir/user/getHomeInfo` | 1 |
| `POST` | `rcs-internal.rokid.com` | `/ymir/user/getHomePage` | 2 |
| `POST` | `ar-service.rokid.com` | `/oauth2/appUpgrade?source=[REDACTED]&languageType=[REDACTED]` | 1 |
| `GET` | `xr-cloud-global.rokid.com` | `/auth/base/asr/getToken` | 2 |
| `POST` | `device-account-prod.rokid.com` | `/device/loginV6.do?deviceTypeId=[REDACTED]&deviceId=[REDACTED]&time=[REDACTED]&sign=[REDACTED]&userId=[REDACTED]&appName=[REDACTED]&namespaces=[REDACTED]&mobilePlatform=[REDACTED]` | 1 |
| `POST` | `rcs-internal.rokid.com` | `/device/bindGlassesDevice` | 1 |
| `GET` | `xr-cloud-global.rokid.com` | `/geolocation/queryCountryCode` | 1 |
| `GET` | `ai-cloud-global.rokid.com` | `/manager/v3/api/model/aggregate?modelZone=[REDACTED]&companyId=[REDACTED]&countryCode=[REDACTED]` | 2 |
| `GET` | `ai-cloud-global.rokid.com` | `/ws/ai` | 1 |
| `POST` | `imgs-ac.alipay.com` | `/imgw.htm` | 3 |
| `POST` | `ota.rokid.com` | `/v1/extended/ota/check` | 1 |
| `GET` | `ota-g.rokidcdn.com` | `/sdk/AI/wend/android.latest.json` | 1 |
| `POST` | `firebaselogging-pa.googleapis.com` | `/v1/firelog/legacy/batchlog` | 1 |
