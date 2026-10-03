# Phase 11: Official IMD district warnings

## Source and flow

WeatherGPT retrieves district warnings from the official IMD endpoint configured by `IMD_DISTRICT_WARNING_URL` (default: `https://mausam.imd.gov.in/api/warnings_district_api.php`). `GET /api/v1/weather/alerts?city=<location>` resolves the city alias to an IMD district and verified `Obj_id`, requests the provider, normalizes the returned five-day record, and returns only official IMD warning facts. The normalized response labels `source`, `official`, `provider_status`, `issued_at`, `retrieved_at`, and the reference ID.

## Location mapping

Configure `IMD_DISTRICT_MAPPINGS` as JSON. Each entry has `aliases`, `district`, `state`, and `obj_id`, for example:

```json
{"sample":{"aliases":["Example City"],"district":"Example District","state":"Example State","obj_id":"VERIFIED_ID"}}
```

Only add IDs verified from an authoritative IMD source. `IMD_DHULE_OBJ_ID` remains supported for backward compatibility, but the project has no authoritative Dhule ID and leaves it empty. Dhule consequently reports `location_mapping_unresolved`; unknown locations report `UNSUPPORTED_LOCATION`.

## Normalization

The service accepts the IMD `Obj_id`, `Date`, `UTC`, `District`, `Day1`–`Day5` fields (and legacy underscore spellings) plus per-day color fields. Warning codes 1–17 are retained; code 1 means no warning. Color codes 1–4 map consistently to Red, Orange, Yellow, Green. Unknown numeric codes remain visible with their numeric reference; malformed provider records fail as unavailable rather than generating a clear state.

## Provider failure and cache

HTTP 401/403 returns HTTP 503 with `status=unavailable`, `source=IMD`, and reason `provider_authorization_required`. Timeouts, connection errors, malformed responses, and other provider errors also return explicit unavailable states with machine-readable reasons. The upstream response body is never exposed or logged. Successful normalized responses alone enter the in-process cache; TTL is configured by `IMD_ALERT_CACHE_TTL_SECONDS`. Failures are not cached and no stale fallback is used.

IMD authorization is external to WeatherGPT. If the provider reports an IP whitelist requirement, IMD must authorize the backend's outbound public IP. Code changes do not grant that access.

## Keep data classes separate

- **Official IMD warning:** only the structured district-warning API response.
- **WeatherGPT prediction:** output of a WeatherGPT model, with its own model and training provenance.
- **WeatherGPT advisory:** deterministic activity/risk guidance from available forecasts and observations. It may include an explicitly sourced IMD warning as context but cannot change or relabel that warning. Its risk classification is not an IMD warning level.

Chat alert answers are composed from the alert tool's structured result. An unavailable lookup is described as unavailable and never as “no warnings.” A successful response with no active warning codes is the only basis for a no-warning statement.

## Configuration

Set `IMD_DISTRICT_WARNING_URL`, `IMD_ALERT_TIMEOUT`, `IMD_ALERT_CACHE_TTL_SECONDS`, and `IMD_DISTRICT_MAPPINGS` in the backend environment. Do not put credentials or secrets in mappings. No frontend secret is required.

## Live validation

1. Verify the district alias and object ID against an authoritative IMD source.
2. Ask IMD to whitelist the backend's outbound public IP if requests receive HTTP 401/403.
3. Configure the mapping and restart the backend.
4. Request `/api/v1/weather/alerts?city=<alias>` and confirm HTTP 200, `source` is IMD, `official` is true, provider status is available, and issue/retrieval timestamps are present.
5. Confirm each returned day against the official IMD response. A 401/403 must remain an unavailable response, never an all-clear result.

The previously documented live check (2026-09-24) received HTTP 401 with an IP-whitelisting message. No live success is claimed until authorization and an authoritative district ID are available.
