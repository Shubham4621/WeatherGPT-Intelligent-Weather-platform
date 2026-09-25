# Phase 5 IMD access and district mapping

WeatherGPT uses only the official IMD district-warning service:

`https://mausam.imd.gov.in/api/warnings_district_api.php?id=<obj_id>`

The request was tested from the backend environment on 2026-09-24 with `id=0` to verify reachability. IMD returned HTTP 401 and the response body `IP 152.59.61.186 needs to be whitelisted`. This is an access denial, not a warning response. No warning value is inferred from it.

The official IMD API reference documents `Obj_id`, `Date`, `UTC`, `District`, `Day_1` through `Day_5`, and their color fields. It documents warning codes 1–17 and color codes 1–4. The reference's example ID is not Dhule's ID. A Dhule ID could not be independently verified from an official source in the available environment, so the application intentionally leaves `IMD_DHULE_OBJ_ID` empty. Do not fill it with a guessed identifier.

To enable the Dhule request, IMD must whitelist the backend's outbound public IP and provide/confirm Dhule's district object ID through an authoritative IMD source. Set `IMD_DHULE_OBJ_ID` in the backend environment after verification. Add further supported districts to `ImdAlertService.resolve_district` only with verified IMD IDs.

While the ID is unset or IMD is inaccessible, `/api/v1/weather/alerts` returns `WEATHER_ALERT_PROVIDER_UNAVAILABLE`. This state is distinct from a successful response whose official codes say no warning. The frontend and chat preserve that distinction.
